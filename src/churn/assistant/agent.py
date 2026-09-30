"""Agent de l'assistant (E16) : boucle d'appels d'outils écrite à la main (sans LangChain).

Pour une question :

1. le LLM reçoit le prompt système, l'historique (10 derniers messages) et la liste des outils ;
2. tant qu'il demande des outils (5 appels au plus par question), l'agent les exécute
   (``churn.assistant.tools``) et lui renvoie les résultats ;
3. la réponse finale est contrôlée par les garde-fous (chiffres présents dans les résultats,
   aucune variable sensible) ; les écarts deviennent des avertissements visibles.

Tout est émis sous forme d'événements (``token``, ``tool_call``, ``tool_result``, ``done``,
``error``) : l'API les relaie en streaming SSE. En cas de quota dépassé, de clé invalide ou de
délai dépassé, l'agent bascule sur le mode démonstration et le signale.

Même module : explication courte pour un conseiller, messages de rétention et résumé exécutif,
construits sur les mêmes outils, clients LLM et garde-fous.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from typing import Any, Literal

from churn.assistant.guardrails import check_answer, extract_numbers
from churn.assistant.llm_client import (
    ChatMessage,
    DemoClient,
    LLMClient,
    LLMError,
    ToolSpec,
    fr,
    make_client,
)
from churn.assistant.prompts import (
    EXPLAIN_CUSTOMER_PROMPT,
    RETENTION_MESSAGE_PROMPT,
    SUMMARY_PROMPT,
    SYSTEM_PROMPT,
)
from churn.assistant.tools import TOOLS, run_tool

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS = 5
MAX_HISTORY = 10
SMS_MAX_CHARS = 300

EventType = Literal["token", "tool_call", "tool_result", "done", "error"]


@dataclass
class AgentEvent:
    """Événement de la boucle, relayé tel quel en SSE."""

    type: EventType
    data: dict[str, Any]


@dataclass
class ToolRecord:
    """Trace d'un appel d'outil."""

    name: str
    args: dict[str, Any]
    duration_ms: float
    ok: bool


@dataclass
class AgentResult:
    """Réponse complète d'une question."""

    answer: str
    tool_calls: list[ToolRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provider: str = ""
    model: str = ""


# --- Client actif ----------------------------------------------------------------------------

@dataclass
class _State:
    last_error: str | None = None


STATE = _State()


@lru_cache(maxsize=1)
def default_client() -> tuple[LLMClient, str | None]:
    """Client configuré par ``.env`` (une fois par processus) et raison d'un mode démo."""
    return make_client()


def tool_specs() -> list[ToolSpec]:
    """Déclarations des outils pour le LLM."""
    return [ToolSpec(t.name, t.description, t.json_schema()) for t in TOOLS.values()]


# --- Boucle de conversation ------------------------------------------------------------------

class Agent:
    """Boucle question -> outils -> réponse contrôlée."""

    def __init__(self, client: LLMClient | None = None, fallback: bool = True,
                 max_tool_calls: int = MAX_TOOL_CALLS, system: str = SYSTEM_PROMPT) -> None:
        self.client = client or default_client()[0]
        self.fallback = fallback
        self.max_tool_calls = max_tool_calls
        self.system = system

    def run(self, question: str, history: list[dict[str, str]] | None = None
            ) -> Iterator[AgentEvent]:
        """Traite une question et émet les événements de la boucle."""
        base = [ChatMessage(h["role"], h["content"]) for h in (history or [])[-MAX_HISTORY:]
                if h.get("role") in ("user", "assistant") and h.get("content")]
        base.append(ChatMessage("user", question))
        client, specs = self.client, tool_specs()
        messages, records, results, warnings = list(base), [], [], []
        step = 0
        while True:
            tools_allowed = len(records) < self.max_tool_calls
            try:
                message = None
                for chunk in client.stream(messages, specs if tools_allowed else None,
                                           self.system):
                    if chunk.kind == "text":
                        yield AgentEvent("token", {"text": chunk.text, "step": step})
                    else:
                        message = chunk.message
            except LLMError as exc:
                STATE.last_error = exc.kind
                logger.warning("Erreur LLM (%s) : %s", exc.kind, exc.detail)
                if self.fallback and exc.can_fallback and not isinstance(client, DemoClient):
                    notice = f"{exc.user_message} Réponse produite en mode démonstration."
                    warnings.append(notice)
                    yield AgentEvent("error", {"message": notice, "kind": exc.kind,
                                               "recoverable": True, "fallback": "demo"})
                    client, messages, records, results = DemoClient(), list(base), [], []
                    step += 1
                    continue
                yield AgentEvent("error", {"message": exc.user_message, "kind": exc.kind,
                                           "recoverable": False})
                return
            if message is None:
                yield AgentEvent("error", {"message": "Réponse vide du modèle.",
                                           "kind": "other", "recoverable": False})
                return
            messages.append(message)
            step += 1
            if message.tool_calls and tools_allowed:
                for call in message.tool_calls:
                    if len(records) >= self.max_tool_calls:
                        # Le fournisseur attend une réponse pour chaque appel demandé.
                        messages.append(ChatMessage("tool", tool_name=call.name, tool_result={
                            "error": "Limite de 5 appels d'outils atteinte : réponds avec les "
                                     "résultats déjà obtenus."}))
                        if not any("Limite" in w for w in warnings):
                            warnings.append("Limite de 5 appels d'outils atteinte pour cette "
                                            "question.")
                        continue
                    yield AgentEvent("tool_call", {"name": call.name, "args": call.args})
                    start = time.perf_counter()
                    result = run_tool(call.name, call.args)
                    duration = 1000 * (time.perf_counter() - start)
                    record = ToolRecord(call.name, call.args, round(duration, 1),
                                        "error" not in result)
                    records.append(record)
                    results.extend([result, call.args])
                    messages.append(ChatMessage("tool", tool_name=call.name, tool_result=result))
                    yield AgentEvent("tool_result", {**asdict(record), "result": result})
                continue
            answer = message.content.strip()
            if not answer:
                answer = "Je n'ai pas pu formuler de réponse à partir des outils."
                warnings.append("Le modèle n'a pas produit de texte final.")
            report = check_answer(answer, results, question)
            warnings.extend(report.warnings)
            yield AgentEvent("done", {
                "answer": answer, "tool_calls": [asdict(r) for r in records],
                "warnings": warnings, "provider": client.provider, "model": client.model})
            return

    def ask(self, question: str, history: list[dict[str, str]] | None = None) -> AgentResult:
        """Version non streamée : consomme les événements et renvoie la réponse finale."""
        result = AgentResult(answer="")
        for event in self.run(question, history):
            if event.type == "done":
                result = AgentResult(
                    answer=event.data["answer"],
                    tool_calls=[ToolRecord(**r) for r in event.data["tool_calls"]],
                    warnings=event.data["warnings"], provider=event.data["provider"],
                    model=event.data["model"])
            elif event.type == "error" and not event.data.get("recoverable"):
                result = AgentResult(answer=event.data["message"],
                                     warnings=[event.data["message"]],
                                     provider=self.client.provider, model=self.client.model)
        return result


# --- Générations dédiées (fiche client, messages, résumé) ------------------------------------

def _generate(client: LLMClient, prompt: str, data: dict[str, Any]
              ) -> tuple[str | None, LLMClient, list[str]]:
    """Un appel sans outils ; en cas d'erreur récupérable, renvoie ``None`` (mode démo)."""
    try:
        message = client.chat([ChatMessage("user", prompt.format(
            data=json.dumps(data, ensure_ascii=False, indent=1)))], None, SYSTEM_PROMPT)
        return message.content.strip(), client, []
    except LLMError as exc:
        STATE.last_error = exc.kind
        if not exc.can_fallback:
            raise
        return None, DemoClient(), [f"{exc.user_message} Texte produit en mode démonstration."]


def _customer_data(customer_id: int) -> dict[str, Any]:
    data = {"fiche": run_tool("get_customer", {"customer_id": customer_id}),
            "contributions": run_tool("explain_customer", {"customer_id": customer_id,
                                                           "top": 6})}
    if "error" in data["fiche"]:
        from churn.services import CustomerNotFoundError
        raise CustomerNotFoundError(data["fiche"]["error"])
    return data


def _demo_explanation(data: dict[str, Any]) -> str:
    c = data["fiche"]
    reasons = [r["situation"].lower() if r["situation"] else r["facteur"].lower()
               for r in c["raisons_actionnables"][:2]]
    factors = " et ".join(reasons) if reasons else "aucun facteur actionnable marqué"
    return (f"Ce client est classé {c['niveau']} : son risque de départ est estimé à "
            f"{fr(c['risque_mensuel_pct'], 2)} % sur un mois, au taux de churn supposé de 2 %. "
            f"Selon le modèle, ce qui pèse le plus sur son score est : {factors}. "
            f"L'action suggérée est « {c['action_suggeree']} ». Ce sont des associations "
            "apprises par le modèle, pas des causes prouvées de départ.")


def explain_for_advisor(customer_id: int, client: LLMClient | None = None) -> dict[str, Any]:
    """Explication en 3 à 4 phrases pour un conseiller (fiche + SHAP du client)."""
    client = client or default_client()[0]
    data = _customer_data(customer_id)
    text, used, warnings = (None, client, [])
    if not isinstance(client, DemoClient):
        text, used, warnings = _generate(client, EXPLAIN_CUSTOMER_PROMPT, data)
    text = text or _demo_explanation(data)
    warnings += check_answer(text, [data]).warnings
    return {"customer_id": customer_id, "text": text, "warnings": warnings,
            "provider": used.provider, "model": used.model}


RETENTION_TEMPLATES: dict[str, tuple[str, str, str]] = {
    "terminal": ("Bonjour, votre téléphone commence à dater ? Nous avons préparé pour vous une "
                 "offre personnalisée de renouvellement. Passez en boutique ou répondez à ce SMS "
                 "pour être rappelé par un conseiller.",
                 "Une offre de renouvellement pensée pour vous",
                 "Bonjour,\n\nVotre téléphone vous accompagne depuis un moment. Nous avons "
                 "préparé une offre personnalisée pour le renouveler dans les meilleures "
                 "conditions. Un conseiller peut vous la présenter en boutique ou par téléphone, "
                 "au moment qui vous convient.\n\nÀ bientôt,\nVotre service client"),
    "engagement": ("Bonjour, votre engagement arrive à échéance. Nous serions ravis de continuer "
                   "ensemble : une offre personnalisée vous attend. Répondez à ce SMS pour être "
                   "rappelé par un conseiller.",
                   "Continuons ensemble : une offre pour vous",
                   "Bonjour,\n\nVotre engagement arrive bientôt à son terme et nous tenons à "
                   "vous remercier de votre fidélité. Nous avons préparé une offre "
                   "personnalisée pour la suite. Un conseiller peut vous la présenter quand "
                   "vous le souhaitez.\n\nÀ bientôt,\nVotre service client"),
    "usage": ("Bonjour, vos besoins ont peut-être changé. Un conseiller peut vous proposer une "
              "offre mieux adaptée à votre utilisation. Répondez à ce SMS pour être rappelé.",
              "Une offre adaptée à votre utilisation",
              "Bonjour,\n\nVotre façon d'utiliser votre ligne a évolué ces derniers mois. Nous "
              "pouvons vous proposer une offre personnalisée, mieux adaptée à vos besoins "
              "actuels. Un conseiller se tient à votre disposition pour en parler.\n\nÀ "
              "bientôt,\nVotre service client"),
    "forfait": ("Bonjour, votre forfait est-il toujours adapté ? Un conseiller peut faire le "
                "point avec vous et vous proposer une offre personnalisée. Répondez à ce SMS "
                "pour être rappelé.",
                "Faisons le point sur votre forfait",
                "Bonjour,\n\nNous vous proposons de faire le point sur votre forfait afin qu'il "
                "corresponde au mieux à votre utilisation. Un conseiller peut vous présenter une "
                "offre personnalisée, sans engagement de votre part.\n\nÀ bientôt,\nVotre "
                "service client"),
    "reseau": ("Bonjour, nous avons constaté que votre qualité de service n'a pas toujours été à "
               "la hauteur. Un conseiller va vous contacter pour trouver une solution et vous "
               "proposer un geste commercial.",
               "Votre qualité de service nous importe",
               "Bonjour,\n\nNous avons constaté que votre qualité de service n'a pas toujours "
               "été à la hauteur de vos attentes. Nos équipes techniques sont informées et un "
               "conseiller va vous contacter pour vous proposer un geste commercial.\n\nÀ "
               "bientôt,\nVotre service client"),
}
DEFAULT_TEMPLATE = ("Bonjour, merci pour votre fidélité. Un conseiller peut vous présenter une "
                    "offre personnalisée adaptée à vos besoins. Répondez à ce SMS pour être "
                    "rappelé.", "Une attention pour vous",
                    "Bonjour,\n\nMerci pour votre fidélité. Nous avons préparé une offre "
                    "personnalisée et un conseiller peut vous la présenter au moment qui vous "
                    "convient.\n\nÀ bientôt,\nVotre service client")
INACTIVE_TEMPLATE = ("Bonjour, nous n'avons pas constaté d'utilisation récente de votre ligne. "
                     "Tout fonctionne-t-il bien ? Répondez à ce SMS ou contactez-nous pour "
                     "vérifier votre ligne.", "Votre ligne fonctionne-t-elle bien ?",
                     "Bonjour,\n\nNous n'avons pas constaté d'utilisation récente de votre "
                     "ligne. Nous souhaitons vérifier avec vous que tout fonctionne "
                     "correctement. Un conseiller se tient à votre disposition.\n\nÀ bientôt,\n"
                     "Votre service client")


def _shorten_sms(sms: str) -> str:
    """SMS limité à 300 caractères, coupé en fin de phrase si possible."""
    if len(sms) <= SMS_MAX_CHARS:
        return sms
    cut = sms[:SMS_MAX_CHARS]
    end = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
    return cut[:end + 1] if end > 80 else cut[:SMS_MAX_CHARS - 1].rstrip() + "…"


def retention_message(customer_id: int, client: LLMClient | None = None) -> dict[str, Any]:
    """SMS (<= 300 caractères) et email adaptés au facteur dominant et à l'action suggérée."""
    from churn.services import get_customer

    client = client or default_client()[0]
    data = _customer_data(customer_id)
    detail = get_customer(customer_id)
    family = detail["dominant_family"]
    template = (INACTIVE_TEMPLATE if detail["inactive"]
                else RETENTION_TEMPLATES.get(family or "", DEFAULT_TEMPLATE))
    prompt_data = {"action_suggeree": detail["action"], "facteur_dominant": family,
                   "raisons": data["fiche"]["raisons_actionnables"],
                   "segment": data["fiche"]["segment"], "inactif": detail["inactive"]}
    used, warnings, parsed = client, [], None
    if not isinstance(client, DemoClient):
        text, used, warnings = _generate(client, RETENTION_MESSAGE_PROMPT, prompt_data)
        if text:
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            try:
                parsed = json.loads(match.group()) if match else None
            except json.JSONDecodeError:
                parsed = None
            if not parsed or not all(k in parsed for k in ("sms", "email_subject", "email_body")):
                warnings.append("Réponse du modèle illisible : messages types utilisés.")
                parsed = None
    sms, subject, body = ((parsed["sms"], parsed["email_subject"], parsed["email_body"])
                          if parsed else template)
    if len(sms) > SMS_MAX_CHARS:
        warnings.append(f"SMS raccourci à {SMS_MAX_CHARS} caractères.")
        sms = _shorten_sms(sms)
    all_text = f"{sms}\n{subject}\n{body}"
    if extract_numbers(all_text) or re.search(r"[%€$]", all_text):
        warnings.append("Vérification automatique : le message contient des chiffres ou un "
                        "montant ; vérifier qu'aucune promesse chiffrée n'est faite.")
    return {"customer_id": customer_id, "dominant_family": family, "action": detail["action"],
            "sms": sms, "sms_length": len(sms), "email_subject": subject, "email_body": body,
            "warnings": warnings, "provider": used.provider, "model": used.model}


def _summary_data() -> dict[str, Any]:
    return {"kpis": run_tool("get_kpis", {}),
            "segments": run_tool("segment_stats", {"dimension": "cluster"})}


def _demo_summary(data: dict[str, Any]) -> list[str]:
    k, s = data["kpis"], data["segments"]["modalites"]
    high = next(lv for lv in k["par_niveau"] if lv["niveau"] == "High")
    riskiest = max(s, key=lambda i: i["risque_mensuel_moyen_pct"])
    richest = max(s, key=lambda i: i["part_du_revenu_en_jeu_pct"])
    camp = k["campagne_officielle"]
    return [
        f"Environ **{fr(k['churners_attendus_par_mois'])}** départs attendus par mois et "
        f"**{fr(k['revenu_mensuel_en_jeu_dollars'])} $** de revenu mensuel en jeu (estimations "
        "pour 100 000 clients au taux de churn supposé de 2 %).",
        f"Les clients **High** représentent **{fr(high['part_du_portefeuille_pct'], 1)} %** du "
        f"portefeuille, avec un risque mensuel moyen de **{fr(high['risque_mensuel_moyen_pct'], 2)}"
        " %**.",
        f"Cibler le top {fr(camp['capacite_pct'])} % des clients actifs atteint environ "
        f"**{fr(camp['churners_pour_1000_contactes'], 1)}** futurs churners pour 1 000 contacts, "
        f"contre {fr(camp['au_hasard_pour_1000'])} au hasard.",
        f"Segment le plus risqué : **{riskiest['modalite']}** "
        f"({fr(riskiest['risque_mensuel_moyen_pct'], 2)} % de risque mensuel) ; segment qui pèse "
        f"le plus en revenu : **{richest['modalite']}** "
        f"({fr(richest['part_du_revenu_en_jeu_pct'], 1)} % du revenu en jeu).",
        "Les départs évités dépendent du taux de succès des offres, à mesurer avec un groupe "
        "témoin avant tout engagement chiffré.",
    ]


_SUMMARY_CACHE: dict[str, dict[str, Any]] = {}


def executive_summary(client: LLMClient | None = None, refresh: bool = False) -> dict[str, Any]:
    """Résumé « Ce qu'il faut retenir » (4 à 5 puces), mis en cache par fournisseur."""
    client = client or default_client()[0]
    key = f"{client.provider}:{client.model}"
    if key in _SUMMARY_CACHE and not refresh:
        return {**_SUMMARY_CACHE[key], "cached": True}
    data = _summary_data()
    bullets, used, warnings = None, client, []
    if not isinstance(client, DemoClient):
        text, used, warnings = _generate(client, SUMMARY_PROMPT, data)
        if text:
            bullets = [re.sub(r"^[-*•]\s*", "", line).strip() for line in text.splitlines()
                       if re.match(r"^\s*[-*•]", line)]
            if not 3 <= len(bullets) <= 6:
                warnings.append("Format du résumé inattendu : résumé type utilisé.")
                bullets = None
    bullets = bullets or _demo_summary(data)
    warnings += check_answer("\n".join(bullets), [data]).warnings
    out = {"title": "Ce qu'il faut retenir", "bullets": bullets, "warnings": warnings,
           "provider": used.provider, "model": used.model,
           "generated_at": time.strftime("%Y-%m-%dT%H:%M")}
    if not warnings or used.provider == "demo":
        _SUMMARY_CACHE[key] = out
    return {**out, "cached": False}


def status(client: LLMClient | None = None, reason: str | None = None) -> dict[str, Any]:
    """Fournisseur actif, modèle, disponibilité (sans appel réseau ni affichage de la clé)."""
    if client is None:
        client, reason = default_client()
    return {"provider": client.provider, "model": client.model,
            "available": True, "live_llm": client.provider != "demo",
            "demo_reason": reason, "last_error": STATE.last_error,
            "max_tool_calls": MAX_TOOL_CALLS, "max_history_messages": MAX_HISTORY}
