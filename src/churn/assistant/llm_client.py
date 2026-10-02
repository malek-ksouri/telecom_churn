"""Clients LLM de l'assistant (E16) : interface commune, Gemini et mode démonstration.

- ``LLMClient`` : conversation avec outils (function calling) en **streaming** ; le format des
  messages est neutre (``ChatMessage``), chaque client le traduit pour son fournisseur.
- ``GeminiClient`` : SDK officiel ``google-genai`` ; modèle et clé lus dans ``.env``
  (``LLM_MODEL``, ``LLM_API_KEY``), jamais écrits dans le code ni dans les journaux.
- ``DemoClient`` : réponses déterministes, sans clé, pour les 8 questions du scénario de
  soutenance. Il appelle **les vrais outils** (les chiffres viennent des artefacts) ; seul le
  texte est préparé. Activé si ``LLM_PROVIDER=demo`` ou si la clé est absente.
- ``LLMError`` : quota dépassé (429), clé invalide, délai dépassé, modèle introuvable ->
  message clair en français ; l'agent peut alors basculer sur ``DemoClient``.
"""

from __future__ import annotations

import logging
import os
import re
import time
import unicodedata
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from dotenv import dotenv_values

from churn.config import get_config

logger = logging.getLogger(__name__)

Role = Literal["user", "assistant", "tool"]
# Attentes avant de retenter un appel refusé pour surcharge (503).
RETRY_DELAYS_S = (2.0, 5.0)


# --- Messages neutres ------------------------------------------------------------------------

@dataclass
class ToolCall:
    """Appel d'outil demandé par le LLM."""

    name: str
    args: dict[str, Any]
    id: str = ""


@dataclass
class ChatMessage:
    """Message de conversation, indépendant du fournisseur.

    ``raw`` conserve le message natif du fournisseur (ex. ``types.Content`` de Gemini, avec
    ses signatures de raisonnement) pour le renvoyer tel quel au tour suivant.
    """

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_name: str | None = None
    tool_result: dict[str, Any] | None = None
    raw: Any = None


@dataclass(frozen=True)
class ToolSpec:
    """Déclaration d'un outil pour le LLM (nom, description, schéma JSON des arguments)."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass
class StreamChunk:
    """Morceau de réponse : ``text`` (jeton) ou ``end`` (message complet de l'assistant)."""

    kind: Literal["text", "end"]
    text: str = ""
    message: ChatMessage | None = None


class LLMError(Exception):
    """Erreur du fournisseur, traduite en message clair pour l'utilisateur."""

    MESSAGES = {
        "quota": "Le quota de l'API du modèle de langage est dépassé (erreur 429). Réessayez "
                 "dans quelques minutes ; en attendant, le mode démonstration peut répondre.",
        "auth": "La clé API du modèle de langage est invalide ou non autorisée. Vérifiez "
                "LLM_API_KEY dans le fichier .env.",
        "timeout": "Le modèle de langage n'a pas répondu dans le délai imparti.",
        "unavailable": "Le service du modèle de langage est momentanément indisponible.",
        "model": "Le modèle configuré (LLM_MODEL dans .env) est introuvable ou non autorisé "
                 "pour cette clé.",
        "config": "L'assistant n'est pas configuré (LLM_PROVIDER, LLM_API_KEY, LLM_MODEL).",
        "other": "Erreur inattendue du modèle de langage.",
    }

    def __init__(self, kind: str, detail: str = "") -> None:
        self.kind = kind if kind in self.MESSAGES else "other"
        self.detail = detail
        super().__init__(self.MESSAGES[self.kind])

    @property
    def user_message(self) -> str:
        return self.MESSAGES[self.kind]

    @property
    def can_fallback(self) -> bool:
        """Erreurs pour lesquelles basculer en mode démonstration a du sens."""
        return self.kind in ("quota", "auth", "timeout", "unavailable", "model", "config")


class LLMClient(ABC):
    """Interface commune des clients LLM."""

    provider: str = "abstract"
    model: str = ""

    @abstractmethod
    def stream(self, messages: list[ChatMessage], tools: list[ToolSpec] | None,
               system: str) -> Iterator[StreamChunk]:
        """Réponse en streaming : des ``text`` puis un ``end`` avec le message complet
        (texte et éventuels appels d'outils)."""

    def chat(self, messages: list[ChatMessage], tools: list[ToolSpec] | None,
             system: str) -> ChatMessage:
        """Réponse complète (consomme le streaming)."""
        final = None
        for chunk in self.stream(messages, tools, system):
            if chunk.kind == "end":
                final = chunk.message
        if final is None:
            raise LLMError("other", "réponse vide")
        return final


# --- Configuration ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LLMSettings:
    """Réglages lus dans ``.env`` (ou l'environnement). La clé n'apparaît jamais dans ``repr``."""

    provider: str
    model: str | None
    timeout_s: float
    api_key: str | None = field(default=None, repr=False)

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)


def load_settings() -> LLMSettings:
    """Variables ``LLM_*`` : l'environnement du processus prime sur le fichier ``.env``."""
    file_values = dotenv_values(get_config().root / ".env")

    def read(name: str, default: str | None = None) -> str | None:
        value = os.environ.get(name) or file_values.get(name) or default
        return value.strip() if isinstance(value, str) and value.strip() else None

    return LLMSettings(provider=(read("LLM_PROVIDER", "demo") or "demo").lower(),
                       model=read("LLM_MODEL"), timeout_s=float(read("LLM_TIMEOUT_S", "45")),
                       api_key=read("LLM_API_KEY"))


def make_client(settings: LLMSettings | None = None) -> tuple[LLMClient, str | None]:
    """Client selon la configuration, et raison d'un éventuel passage en mode démonstration."""
    settings = settings or load_settings()
    if settings.provider == "demo":
        return DemoClient(), "mode démonstration demandé (LLM_PROVIDER=demo)"
    if settings.provider != "gemini":
        return DemoClient(), f"fournisseur non pris en charge : {settings.provider}"
    if not settings.has_key:
        return DemoClient(), "clé API absente (LLM_API_KEY)"
    if not settings.model:
        return DemoClient(), "modèle non renseigné (LLM_MODEL)"
    return GeminiClient(settings.api_key, settings.model, settings.timeout_s), None


# --- Gemini ----------------------------------------------------------------------------------

class GeminiClient(LLMClient):
    """Gemini via le SDK officiel ``google-genai`` (function calling manuel, streaming)."""

    provider = "gemini"

    def __init__(self, api_key: str, model: str, timeout_s: float = 45,
                 temperature: float = 0.2) -> None:
        from google import genai
        from google.genai import types

        self._types = types
        self.model = model
        self.temperature = temperature
        self._client = genai.Client(api_key=api_key,
                                    http_options=types.HttpOptions(timeout=int(timeout_s * 1000)))

    def _contents(self, messages: list[ChatMessage]) -> list[Any]:
        t = self._types
        contents: list[Any] = []
        for m in messages:
            if m.role == "user":
                contents.append(t.Content(role="user", parts=[t.Part(text=m.content)]))
            elif m.role == "assistant":
                if m.raw is not None:
                    contents.append(m.raw)
                    continue
                parts = [t.Part(text=m.content)] if m.content else []
                parts += [t.Part(function_call=t.FunctionCall(name=c.name, args=c.args))
                          for c in m.tool_calls]
                contents.append(t.Content(role="model", parts=parts))
            else:
                part = t.Part.from_function_response(name=m.tool_name or "",
                                                     response={"result": m.tool_result})
                # Réponses d'appels parallèles : regroupées dans un même message.
                last = contents[-1] if contents else None
                if last is not None and last.role == "user" and last.parts and all(
                        p.function_response is not None for p in last.parts):
                    last.parts.append(part)
                else:
                    contents.append(t.Content(role="user", parts=[part]))
        return contents

    def _config(self, tools: list[ToolSpec] | None, system: str) -> Any:
        t = self._types
        declarations = [t.FunctionDeclaration(name=s.name, description=s.description,
                                              parameters_json_schema=s.parameters)
                        for s in tools or []]
        return t.GenerateContentConfig(
            system_instruction=system, temperature=self.temperature,
            tools=[t.Tool(function_declarations=declarations)] if declarations else None,
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True))

    def stream(self, messages: list[ChatMessage], tools: list[ToolSpec] | None,
               system: str) -> Iterator[StreamChunk]:
        t = self._types
        contents, config = self._contents(messages), self._config(tools, system)
        for attempt in range(len(RETRY_DELAYS_S) + 1):
            parts: list[Any] = []
            text: list[str] = []
            calls: list[ToolCall] = []
            try:
                for chunk in self._client.models.generate_content_stream(
                        model=self.model, contents=contents, config=config):
                    candidate = chunk.candidates[0] if chunk.candidates else None
                    content = candidate.content if candidate else None
                    for part in (content.parts or []) if content else []:
                        parts.append(part)
                        if part.function_call is not None:
                            fc = part.function_call
                            calls.append(ToolCall(name=fc.name or "", args=dict(fc.args or {}),
                                                  id=fc.id or ""))
                        elif part.text and not part.thought:
                            text.append(part.text)
                            yield StreamChunk("text", text=part.text)
            except Exception as exc:  # noqa: BLE001 - traduit en LLMError
                error = _map_error(exc)
                # Surcharge passagère (503) : nouvelle tentative si rien n'a encore été émis.
                if error.kind == "unavailable" and not parts and attempt < len(RETRY_DELAYS_S):
                    logger.info("Gemini surchargé, nouvelle tentative dans %.0f s",
                                RETRY_DELAYS_S[attempt])
                    time.sleep(RETRY_DELAYS_S[attempt])
                    continue
                raise error from exc
            raw = t.Content(role="model", parts=parts) if parts else None
            yield StreamChunk("end", message=ChatMessage("assistant", "".join(text), calls,
                                                         raw=raw))
            return


def _map_error(exc: Exception) -> LLMError:
    """Erreur du SDK ou du réseau -> ``LLMError`` (sans jamais recopier la clé)."""
    import httpx
    from google.genai import errors

    if isinstance(exc, LLMError):
        return exc
    if isinstance(exc, httpx.TimeoutException) or "timed out" in str(exc).lower():
        return LLMError("timeout")
    if isinstance(exc, errors.APIError):
        code = exc.code or 0
        status = (exc.status or "").upper()
        message = (exc.message or "").lower()
        if code == 429 or status == "RESOURCE_EXHAUSTED":
            return LLMError("quota", status)
        if code in (401, 403) or "api key" in message or "api_key" in message:
            return LLMError("auth", status)
        if code == 404:
            return LLMError("model", status)
        if code in (408, 504) or status == "DEADLINE_EXCEEDED":
            return LLMError("timeout", status)
        if code >= 500:
            return LLMError("unavailable", status)
        return LLMError("other", f"{code} {status}")
    return LLMError("other", type(exc).__name__)


# --- Mode démonstration ----------------------------------------------------------------------

def _norm(text: str) -> str:
    """Minuscules sans accents (correspondance robuste des mots-clés)."""
    return "".join(c for c in unicodedata.normalize("NFD", text.lower())
                   if unicodedata.category(c) != "Mn")


def fr(x: float | None, nd: int = 0) -> str:
    """Nombre au format français (espace des milliers, virgule décimale)."""
    if x is None:
        return "n.d."
    return f"{x:,.{nd}f}".replace(",", " ").replace(".", ",")


def _results(messages: list[ChatMessage]) -> dict[str, list[dict[str, Any]]]:
    """Résultats d'outils du tour en cours (depuis le dernier message utilisateur)."""
    last_user = max(i for i, m in enumerate(messages) if m.role == "user")
    out: dict[str, list[dict[str, Any]]] = {}
    for m in messages[last_user + 1:]:
        if m.role == "tool" and m.tool_name:
            out.setdefault(m.tool_name, []).append(m.tool_result or {})
    return out


@dataclass(frozen=True)
class Scenario:
    """Question du scénario : mots-clés, outils à appeler, rédaction à partir des résultats."""

    key: str
    match: Callable[[str], bool]
    plan: Callable[[str], list[ToolCall]]
    render: Callable[[dict[str, list[dict[str, Any]]], str], str]


def _first(results: dict[str, list[dict[str, Any]]], name: str) -> dict[str, Any]:
    return (results.get(name) or [{}])[0]


def _render_overview(r: dict, _: str) -> str:
    k = _first(r, "get_kpis")
    if not k or "error" in k:
        return "Je n'ai pas pu lire les indicateurs du portefeuille."
    high = next((lv for lv in k["par_niveau"] if lv["niveau"] == "High"), {})
    camp = k.get("campagne_officielle") or {}
    return (
        "**Situation du portefeuille** (estimations pour un portefeuille de "
        f"{fr(k['equivalent_portefeuille'])} clients au taux de churn supposé de 2 %) :\n"
        f"- **{fr(k['churners_attendus_par_mois'])}** départs attendus sur un mois ;\n"
        f"- **{fr(k['revenu_mensuel_en_jeu_dollars'])} $** de revenu mensuel en jeu "
        f"({fr(k['part_de_la_facture_en_jeu_pct'], 2)} % de la facture) ;\n"
        f"- clients **High** : **{fr(high.get('equivalent_portefeuille'))}** en équivalent "
        f"portefeuille ({fr(high.get('clients_dans_la_base'))} clients dans la base), risque "
        f"mensuel moyen **{fr(high.get('risque_mensuel_moyen_pct'), 2)} %** ;\n"
        f"- campagne officielle (top {fr(camp.get('capacite_pct'))} % des actifs) : "
        f"**{fr(camp.get('churners_pour_1000_contactes'), 1)}** futurs churners pour 1 000 "
        f"clients contactés, contre {fr(camp.get('au_hasard_pour_1000'))} au hasard.\n\n"
        "Les départs évités dépendent du taux de succès de l'offre, à mesurer.")


def _render_at_risk(r: dict, _: str) -> str:
    lst = _first(r, "list_at_risk")
    if not lst.get("clients"):
        return "Aucun client ne correspond à ces critères."
    lines = [f"- **{c['client']}** : risque mensuel **{fr(c['risque_mensuel_pct'], 2)} %**, "
             f"{c['raison_principale'] or 'raison non disponible'} → *{c['action_suggeree']}*"
             for c in lst["clients"]]
    return (f"**Clients à contacter en priorité** ({fr(lst['clients_correspondants_dans_la_base'])}"
            " clients High dans la base ; voici les plus risqués) :\n" + "\n".join(lines)
            + "\n\nLes raisons décrivent ce qui pèse sur le score selon le modèle, pas des causes.")


def _render_customer(r: dict, _: str) -> str:
    c = _first(r, "get_customer")
    if not c or "error" in c:
        return c.get("error", "Client introuvable.")
    reasons = "\n".join(f"- {f['situation']} ({f['effet']})" for f in c["raisons_actionnables"])
    return (f"**Client {c['client']}** : niveau **{c['niveau']}**, risque mensuel "
            f"**{fr(c['risque_mensuel_pct'], 2)} %** (taux de churn réel supposé de 2 %).\n\n"
            f"Selon le modèle, les facteurs actionnables qui pèsent le plus :\n{reasons}\n\n"
            f"Action suggérée : **{c['action_suggeree']}**. Ce sont des associations apprises, "
            "pas des causes prouvées du départ.")


def _render_segments(r: dict, _: str) -> str:
    s = _first(r, "segment_stats")
    items = sorted(s.get("modalites", []), key=lambda i: -i["risque_mensuel_moyen_pct"])
    if not items:
        return "Je n'ai pas pu lire les segments."
    by_revenue = max(items, key=lambda i: i["part_du_revenu_en_jeu_pct"])
    lines = [f"- **{i['modalite']}** : risque mensuel **{fr(i['risque_mensuel_moyen_pct'], 2)} %**"
             f", {fr(i['part_high_pct'], 1)} % de clients High, "
             f"{fr(i['part_du_revenu_en_jeu_pct'], 1)} % du revenu en jeu" for i in items[:3]]
    return ("**Segments les plus risqués** (estimations au taux de churn supposé de 2 %) :\n"
            + "\n".join(lines) + f"\n\nEn revenu, le segment **{by_revenue['modalite']}** pèse "
            f"le plus : **{fr(by_revenue['part_du_revenu_en_jeu_pct'], 1)} %** du revenu en jeu.")


def _render_drivers(r: dict, _: str) -> str:
    d = _first(r, "global_drivers")
    items = d.get("facteurs_actionnables", [])[:3]
    if not items:
        return "Je n'ai pas pu lire les facteurs."
    lines = [f"- **{i['facteur']}** ({i['famille']}) : {fr(i['part_importance_pct'], 1)} % de "
             "l'importance" for i in items]
    return ("**Principaux facteurs actionnables, selon le modèle** :\n" + "\n".join(lines)
            + "\n\nCe sont des associations apprises par le modèle (SHAP), pas des causes : "
              "agir sur un facteur ne garantit pas de réduire le risque.")


def _render_campaign(r: dict, _: str) -> str:
    s = _first(r, "simulate_campaign")
    res = s.get("resultat")
    if not res:
        return s.get("error", "Simulation impossible.")
    h = s["hypotheses_saisies"]
    return (
        f"**Campagne sur {fr(res['capacite_pct'])} % du portefeuille** "
        f"({fr(res['clients_cibles_equivalent_portefeuille'])} clients en équivalent portefeuille, "
        f"taux de churn supposé {fr(h['taux_de_churn_reel_suppose_pct'])} %) :\n"
        f"- **{fr(res['churners_attendus'])}** churners attendus parmi les ciblés, contre "
        f"{fr(res['churners_au_hasard'])} au hasard (facteur {fr(res['facteur_vs_hasard'], 2)}) ;\n"
        f"- **{fr(res['revenu_mensuel_en_jeu_dollars'])} $** de revenu mensuel en jeu ;\n"
        f"- *Hypothèse* d'un taux de succès de {fr(h['taux_de_succes_suppose_pct'])} % : environ "
        f"**{fr(res['HYPOTHESE_departs_evites'])}** départs évités et "
        f"**{fr(res['HYPOTHESE_revenu_mensuel_preserve_dollars'])} $** de revenu mensuel "
        "préservé.\n\nLe taux de succès est une hypothèse à mesurer (groupe témoin) ; aucun coût "
        "n'a été supposé.")


def _render_avoided(r: dict, _: str) -> str:
    k = _first(r, "get_kpis")
    camp = k.get("campagne_officielle") or {}
    return (
        "**On ne peut pas le savoir avec le modèle seul.** Il indique *qui* risque de partir, "
        "pas si l'offre le retiendra.\n"
        f"- Ce qu'on sait : en ciblant le top {fr(camp.get('capacite_pct'))} % des actifs, on "
        f"atteint environ **{fr(camp.get('churners_pour_1000_contactes'), 1)}** futurs churners "
        f"pour 1 000 clients contactés, contre {fr(camp.get('au_hasard_pour_1000'))} au hasard ;\n"
        "- départs évités = churners ciblés × **taux de succès de l'offre**, inconnu tant qu'il "
        "n'est pas mesuré (groupe témoin).\n\nLe simulateur de campagne permet de tester un taux "
        "de succès, présenté comme hypothèse.")


def _render_method(r: dict, _: str) -> str:
    m = _first(r, "explain_method")
    return m.get("explication", "Je n'ai pas trouvé cette explication.")


def _method_topic(q: str) -> str:
    if "51" in q or "1 000" in q or "1000" in q:
        return "chiffre_51"
    if "calibr" in q:
        return "calibration"
    if "shap" in q or "causal" in q or "cause" in q:
        return "shap"
    if "taux reel" in q or "2 %" in q or "2%" in q:
        return "taux_reel"
    if "lift" in q:
        return "lift"
    return "auc"


def _percentages(q: str) -> list[float]:
    return [float(x.replace(",", ".")) for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", q)]


SENSITIVE_WORDS = ("ethni", "origine", "religion", "revenu du foyer", "revenus des clients",
                   "situation familiale", "marie", "enfant", "celibataire")
OUT_OF_SCOPE = ("Je réponds uniquement aux questions sur le churn de ce portefeuille : "
                "indicateurs, clients à risque, segments, facteurs, campagnes et méthode du "
                "modèle. Par exemple : « Quelle est la situation globale ? » ou « Qui "
                "sont les clients à contacter en priorité ? »")
SENSITIVE_REFUSAL = ("Je ne réponds pas sur les caractéristiques socio-démographiques "
                     "sensibles des clients : elles ne sont ni utilisées pour cibler ni "
                     "présentées par l'assistant. Je peux en revanche détailler les facteurs "
                     "actionnables (terminal, usage, forfait, fin d'engagement).")

SCENARIOS: list[Scenario] = [
    Scenario("customer", lambda q: re.search(r"\b\d{7}\b", q) is not None,
             lambda q: [ToolCall("get_customer",
                                 {"customer_id": int(re.search(r"\b\d{7}\b", q).group())})],
             _render_customer),
    Scenario("avoided", lambda q: any(w in q for w in ("evit", "sauver", "retenir", "preserv")),
             lambda q: [ToolCall("get_kpis", {}),
                        ToolCall("explain_method", {"topic": "departs_evites"})],
             _render_avoided),
    Scenario("method", lambda q: any(w in q for w in (
        "auc", "fiable", "precis", "performan", "calibr", "shap", "causal", "51 pour",
        "taux reel", "lift", "methode")),
             lambda q: [ToolCall("explain_method", {"topic": _method_topic(q)})],
             _render_method),
    Scenario("campaign", lambda q: any(w in q for w in ("campagne", "simul", "capacite", "succes")),
             lambda q: [ToolCall("simulate_campaign", {
                 "capacity_pct": (_percentages(q) or [10])[0],
                 "success_rate": ((_percentages(q)[1:] or [20])[0]) / 100})],
             _render_campaign),
    Scenario("segments", lambda q: "segment" in q,
             lambda q: [ToolCall("segment_stats", {"dimension": "cluster"})], _render_segments),
    Scenario("drivers", lambda q: "facteur" in q or "pourquoi les clients" in q
             or "raisons du churn" in q,
             lambda q: [ToolCall("global_drivers", {"top": 5})], _render_drivers),
    Scenario("at_risk", lambda q: ("cibler" in q and "client" in q) or (
        "risque" in q and any(w in q for w in ("qui", "liste", "contacter", "priorit", "clients"))
        and "situation" not in q),
             lambda q: [ToolCall("list_at_risk", {"risk_level": ["High"], "limit": 5})],
             _render_at_risk),
    Scenario("overview", lambda q: any(w in q for w in (
        "situation", "vue d'ensemble", "kpi", "indicateur", "combien de clients", "resume",
        "portefeuille")),
             lambda q: [ToolCall("get_kpis", {})], _render_overview),
]


def match_scenario(question: str) -> Scenario | None:
    """Scénario correspondant à la question (``None`` : hors périmètre)."""
    q = _norm(question)
    return next((s for s in SCENARIOS if s.match(q)), None)


class DemoClient(LLMClient):
    """Réponses déterministes sans clé : outils réels, texte préparé (scénario de soutenance)."""

    provider = "demo"
    model = "scénario de démonstration"

    def stream(self, messages: list[ChatMessage], tools: list[ToolSpec] | None,
               system: str) -> Iterator[StreamChunk]:
        question = next((m.content for m in reversed(messages) if m.role == "user"), "")
        q = _norm(question)
        results = _results(messages)
        calls: list[ToolCall] = []
        if any(w in q for w in SENSITIVE_WORDS):
            text = SENSITIVE_REFUSAL
        elif (scenario := match_scenario(question)) is None:
            text = OUT_OF_SCOPE
        elif not results and tools:
            calls, text = scenario.plan(q), ""
        else:
            text = scenario.render(results, q)
        for token in re.findall(r"\S+\s*|\s+", text):
            yield StreamChunk("text", text=token)
        yield StreamChunk("end", message=ChatMessage("assistant", text, calls))
