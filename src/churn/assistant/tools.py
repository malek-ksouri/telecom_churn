"""Outils de l'assistant IA (E16) : fines enveloppes de ``churn.services``.

Règles :

- **aucun calcul** ici : chaque outil appelle un service, puis se contente de sélectionner,
  renommer et arrondir les champs utiles (réponses courtes pour le LLM) ;
- chaque outil a un schéma d'arguments pydantic : il sert à la fois à valider les arguments
  proposés par le LLM et à générer la déclaration de fonction envoyée au fournisseur ;
- les variables socio-démographiques sensibles ne sortent **jamais** d'un outil ;
- toute erreur (client inconnu, argument invalide) est renvoyée au LLM sous la forme
  ``{"error": "..."}`` plutôt que levée.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from churn import services
from churn.business.actions import SENSITIVE_VARIABLES
from churn.services import CustomerNotFoundError, Filters

logger = logging.getLogger(__name__)

MAX_LIST = 20


def _r(x: Any, nd: int = 2) -> Any:
    """Arrondi lisible (les nombres cités par le LLM doivent pouvoir être retrouvés)."""
    return None if x is None else round(float(x), nd)


def _pct(x: Any, nd: int = 2) -> Any:
    """Proportion (0-1) -> pourcentage arrondi."""
    return None if x is None else round(100 * float(x), nd)


# --- Arguments -------------------------------------------------------------------------------

RiskLevel = Literal["High", "Medium", "Low", "Inactif"]
Dimension = Literal["risk_level", "cluster", "area", "tenure_band", "handset_age_band",
                    "usage_band", "action"]


class FilterArgs(BaseModel):
    """Filtres communs (valeurs exactes : voir les modalités renvoyées par segment_stats)."""

    risk_level: list[RiskLevel] | None = Field(None, description="Niveaux de risque.")
    cluster: list[str] | None = Field(None, description="Segments comportementaux (noms exacts).")
    area: list[str] | None = Field(None, description="Régions (noms exacts, en majuscules).")
    tenure_band: list[str] | None = Field(None, description="Tranches d'ancienneté.")
    handset_age_band: list[str] | None = Field(None, description="Tranches d'âge du terminal.")
    usage_band: list[str] | None = Field(None, description="Tranches d'usage mensuel.")
    action: list[str] | None = Field(None, description="Actions suggérées.")

    def to_filters(self) -> Filters:
        return Filters(**{k: tuple(v) if v else None for k, v in self.model_dump(
            include=set(FilterArgs.model_fields)).items()})


class KpiArgs(FilterArgs):
    pass


class CustomerArgs(BaseModel):
    customer_id: int = Field(description="Identifiant client (Customer_ID), ex. 1072931.")


class ExplainArgs(CustomerArgs):
    top: int = Field(8, ge=1, le=15, description="Nombre de contributions renvoyées.")


class ListArgs(FilterArgs):
    limit: int = Field(10, ge=1, le=MAX_LIST, description="Nombre de clients (20 au plus).")
    sort: Literal["p_real", "revenue_at_risk_monthly"] = Field(
        "p_real", description="Tri décroissant : risque ou revenu en jeu.")
    include_inactive: bool = Field(
        False, description="Inclure les clients inactifs (sans usage, probablement déjà perdus, "
                           "traités à part). Par défaut : non, liste de clients à fidéliser.")


class SegmentArgs(FilterArgs):
    dimension: Dimension = Field(description="Dimension d'analyse.")


class DriversArgs(FilterArgs):
    top: int = Field(8, ge=1, le=15, description="Facteurs par liste.")


class CampaignArgs(FilterArgs):
    capacity_pct: float = Field(10, gt=0, le=50, description="Part du périmètre contactée (%).")
    success_rate: float = Field(0.2, ge=0, le=1, description="HYPOTHÈSE : taux de succès de "
                                                             "l'offre (0-1).")
    offer_cost: float | None = Field(None, ge=0, description="HYPOTHÈSE : coût par client "
                                                             "contacté ($) ; omis = pas de coût.")
    revenue_horizon_months: int = Field(1, ge=1, le=36, description="HYPOTHÈSE : mois de revenu "
                                                                    "préservé dans le solde.")


MethodTopic = Literal["auc", "lift", "calibration", "taux_reel", "shap", "chiffre_51",
                      "niveaux", "effectifs", "inactifs", "departs_evites"]


class MethodArgs(BaseModel):
    topic: MethodTopic = Field(description="Sujet de méthodologie.")


# --- Fonctions -------------------------------------------------------------------------------

def _hyp(h: dict[str, Any]) -> str:
    return h["note"]


def get_kpis(args: KpiArgs) -> dict[str, Any]:
    k = services.get_kpis(args.to_filters())
    camp = k["official_campaign"] or {}
    return {
        "filtres": k["filters"],
        "clients_dans_la_base": k["n_rows"],
        "equivalent_portefeuille": _r(k["n_portfolio_equiv"], 0),
        "part_du_portefeuille_pct": _pct(k["share_of_portfolio"], 1),
        "churners_attendus_par_mois": _r(k["expected_churners"], 0),
        "risque_mensuel_moyen_pct": _pct(k["expected_churn_rate"]),
        "revenu_mensuel_en_jeu_dollars": _r(k["revenue_at_risk_monthly"], 0),
        "part_de_la_facture_en_jeu_pct": _pct(k["revenue_at_risk_share_of_bill"]),
        "clients_inactifs_dans_la_base": k["inactive_n_rows"],
        "par_niveau": [{
            "niveau": lv["risk_level"], "clients_dans_la_base": lv["n_rows"],
            "equivalent_portefeuille": _r(lv["n_portfolio_equiv"], 0),
            "part_du_portefeuille_pct": _pct(lv.get("share_of_portfolio"), 1),
            "risque_mensuel_moyen_pct": _pct(lv.get("expected_churn_rate")),
            "churners_attendus": _r(lv.get("expected_churners"), 0),
            "revenu_en_jeu_dollars": _r(lv.get("revenue_at_risk"), 0),
        } for lv in k["by_risk_level"]],
        "campagne_officielle": {
            "capacite_pct": camp.get("capacity_pct"),
            "churners_pour_1000_contactes": _r(camp.get("churners_per_1000_contacted"), 1),
            "au_hasard_pour_1000": _r(camp.get("random_churners_per_1000_contacted"), 0),
            "facteur_vs_hasard": _r(camp.get("lift_vs_random")),
            "revenu_mensuel_en_jeu_dollars": _r(camp.get("revenue_at_risk_monthly"), 0),
        } if camp else None,
        "auc_test": _r(k["model"]["auc_test"], 4),
        "nature_des_effectifs": "clients_dans_la_base = lignes réelles ; les autres effectifs et "
                                "montants = " + _hyp(k["hypothesis"]),
    }


def _factor(f: dict[str, Any]) -> dict[str, Any]:
    return {"facteur": f["label"], "situation": f["text"], "effet": f["effect"],
            "contribution_log_odds": _r(f["contribution_log_odds"], 3)}


def get_customer(args: CustomerArgs) -> dict[str, Any]:
    c = services.get_customer(args.customer_id)
    profile = {p["label"]: (f"{p['value']} {p['unit']}".strip() if p["value"] is not None
                            else "non renseigné")
               for p in c["profile"] if p["variable"] not in SENSITIVE_VARIABLES}
    return {
        "client": c["customer_id"],
        "niveau": c["risk_level"],
        "inactif": c["inactive"],
        "risque_mensuel_pct": _pct(c["scores"]["p_real"]),
        "note_risque": c["scores"]["p_real_note"],
        "segment": c["segment"]["name"],
        "action_suggeree": c["action"],
        "raisons_actionnables": [_factor(f) for f in c["reasons"]],
        "contexte": [_factor(f) for f in c["context"] if f["variable"] not in SENSITIVE_VARIABLES],
        "facture_mensuelle_dollars": _r(c["monthly_bill"]),
        "revenu_mensuel_en_jeu_dollars": _r(c["revenue_at_risk_monthly"]),
        "profil": profile,
        "avertissement": c["note"],
    }


def explain_customer(args: ExplainArgs) -> dict[str, Any]:
    e = services.explain_customer(args.customer_id, top=args.top)
    kept = [c for c in e["contributions"] if c["variable"] not in SENSITIVE_VARIABLES]
    return {
        "client": e["customer_id"],
        "unite": e["unit"],
        "valeur_de_base_log_odds": _r(e["base_value_log_odds"], 3),
        "contributions": [{**_factor(c), "actionnable": c["actionable"]} for c in kept],
        "variables_sensibles_masquees": len(e["contributions"]) - len(kept),
        "log_odds_du_client": _r(e["log_odds"], 3),
        "avertissement": e["note"],
    }


def list_at_risk(args: ListArgs) -> dict[str, Any]:
    if not args.include_inactive and not args.risk_level:
        args = args.model_copy(update={"risk_level": ["High", "Medium", "Low"]})
    page = services.list_customers(args.to_filters(), sort=args.sort, order="desc",
                                   page=1, size=args.limit)
    return {
        "filtres": page["filters"],
        "clients_correspondants_dans_la_base": page["total_n_rows"],
        "clients": [{
            "client": i["customer_id"], "niveau": i["risk_level"],
            "risque_mensuel_pct": _pct(i["p_real"]), "segment": i["segment"],
            "action_suggeree": i["action"], "raison_principale": i["top_reason"],
            "revenu_mensuel_en_jeu_dollars": _r(i["revenue_at_risk_monthly"]),
        } for i in page["items"]],
    }


def segment_stats(args: SegmentArgs) -> dict[str, Any]:
    s = services.get_segments(args.dimension, args.to_filters())
    return {
        "dimension": s["label"],
        "filtres": s["filters"],
        "modalites": [{
            "modalite": i["value"], "clients_dans_la_base": i["n_rows"],
            "equivalent_portefeuille": _r(i["n_portfolio_equiv"], 0),
            "part_du_portefeuille_pct": _pct(i["share_of_portfolio"], 1),
            "risque_mensuel_moyen_pct": _pct(i["expected_churn_rate"]),
            "churn_observe_dans_la_base_pct": _pct(i["observed_churn_rate_in_base"], 1),
            "part_high_pct": _pct(i["share_high"], 1),
            "churners_attendus": _r(i["expected_churners"], 0),
            "revenu_mensuel_en_jeu_dollars": _r(i["revenue_at_risk"], 0),
            "part_du_revenu_en_jeu_pct": _pct(i["share_of_revenue_at_risk"], 1),
        } for i in s["items"]],
        "nature_des_effectifs": "clients_dans_la_base = lignes réelles ; equivalent_portefeuille "
                                "et montants = " + _hyp(s["hypothesis"]),
    }


def global_drivers(args: DriversArgs) -> dict[str, Any]:
    d = services.get_drivers(args.to_filters(), top=args.top + 5)

    def keep(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"facteur": i["label"], "famille": i["family_label"],
                 "part_importance_pct": _r(i["share_pct"], 1),
                 "part_clients_ou_le_facteur_augmente_le_risque_pct": _pct(
                     i["share_rows_increasing"], 0)}
                for i in items if i["variable"] not in SENSITIVE_VARIABLES][:args.top]

    return {"filtres": d["filters"], "clients_dans_la_base": d["n_rows"],
            "facteurs_actionnables": keep(d["actionable"]),
            "facteurs_de_contexte": keep(d["context"]),
            "avertissement": d["note"]}


def simulate_campaign(args: CampaignArgs) -> dict[str, Any]:
    s = services.simulate_campaign(args.capacity_pct, args.success_rate, args.offer_cost,
                                   args.to_filters(), args.revenue_horizon_months)
    res = s["result"] or {}
    return {
        "hypotheses_saisies": {
            "taux_de_succes_suppose_pct": _pct(args.success_rate, 1),
            "cout_par_contact_suppose_dollars": args.offer_cost,
            "horizon_de_revenu_suppose_mois": args.revenue_horizon_months,
            "taux_de_churn_reel_suppose_pct": _pct(s["hypothesis"]["real_churn_rate"], 1),
            "portefeuille_de_reference_clients": s["hypothesis"]["portfolio_size"],
        },
        "resultat": {
            "capacite_pct": res.get("capacity_pct"),
            "clients_cibles_dans_la_base": res.get("targeted_n_rows"),
            "clients_cibles_equivalent_portefeuille": _r(res.get("targeted_n_portfolio_equiv"), 0),
            "churners_attendus": _r(res.get("expected_churners"), 0),
            "churners_au_hasard": _r(res.get("random_churners"), 0),
            "facteur_vs_hasard": _r(res.get("lift_vs_random")),
            "churners_pour_1000_contactes": _r(res.get("churners_per_1000_contacted"), 1),
            "revenu_mensuel_en_jeu_dollars": _r(res.get("revenue_at_risk_monthly"), 0),
            "HYPOTHESE_departs_evites": _r(res.get("avoided_departures_hypothesis"), 0),
            "HYPOTHESE_revenu_mensuel_preserve_dollars": _r(
                res.get("preserved_revenue_monthly_hypothesis"), 0),
            "HYPOTHESE_cout_campagne_dollars": _r(res.get("campaign_cost"), 0),
            "HYPOTHESE_solde_dollars": _r(res.get("net_balance"), 0),
        } if res else None,
        "inactifs_hors_campagne": {
            "clients_dans_la_base": s["inactive"]["n_rows"],
            "equivalent_portefeuille": _r(s["inactive"]["n_portfolio_equiv"], 0),
            "action": s["inactive"]["action"],
        },
        "avertissement": s["user_hypotheses"]["note"],
    }


def _method_texts() -> dict[str, str]:
    """Textes de méthodologie (rédigés par l'équipe), complétés par les chiffres des artefacts."""
    k = services.get_kpis()
    auc = k["model"]["auc_test"]
    auc_oof = k["model"]["auc_out_of_fold_train"]
    per_1000 = k["official_campaign"]["churners_per_1000_contacted"]
    fmt = lambda x, nd=2: f"{x:.{nd}f}".replace(".", ",")  # noqa: E731
    return {
        "auc": f"L'AUC est la probabilité qu'un churner tiré au hasard ait un score plus élevé "
               f"qu'un non-churner tiré au hasard (0,5 = hasard, 1 = parfait). Le modèle final "
               f"(LightGBM calibré) obtient {fmt(auc, 4)} sur le jeu de test, qui n'a servi à "
               f"aucun choix de modèle, et {fmt(auc_oof, 4)} en validation hors fold sur le train. "
               f"C'est un bon classement pour ce jeu où chaque variable, seule, est peu liée au "
               f"churn.",
        "lift": "Le lift compare le taux de churn des clients ciblés au taux moyen. Sur "
                "l'échantillon, les 10 % les mieux classés ont un lift de 1,60 ; dans un "
                "portefeuille réel au taux supposé de 2 %, le même ciblage atteint environ 2,5 "
                "à 2,8 fois le hasard.",
        "calibration": "La calibration (sigmoïde, apprise en validation croisée) fait qu'une "
                       "probabilité annoncée de 0,7 corresponde à environ 70 % de churners sur "
                       "l'échantillon. L'erreur de calibration (ECE) passe de 0,0122 à 0,0046 "
                       "sur le test, sans changer le classement.",
        "taux_reel": "Le jeu de données contient environ 50 % de churners, bien plus qu'un "
                     "opérateur réel. Les probabilités sont donc ramenées à un taux de churn "
                     "réel SUPPOSÉ de 2 % par mois (hypothèse, sensibilité 1 à 3 %). Cette "
                     "correction ne change pas l'ordre des clients : elle ne change que les "
                     "chiffres absolus.",
        "shap": "Les explications viennent de SHAP : la contribution de chaque caractéristique "
                "au score d'un client, selon le modèle. Ce sont des associations apprises sur "
                "des données d'observation, pas des causes : agir sur un facteur ne garantit "
                "pas de réduire le risque.",
        "chiffre_51": f"En ciblant les 10 % de clients actifs les plus risqués, on atteint "
                      f"environ {fmt(per_1000, 0)} futurs churners pour 1 000 clients contactés, "
                      f"contre 20 au hasard (taux réel supposé de 2 %). Les inactifs sont traités "
                      f"à part. Le chiffre de 56 pour 1 000 mesurait la performance du modèle, "
                      f"inactifs compris. Les départs évités dépendent du taux de succès de "
                      f"l'offre, à mesurer.",
        "niveaux": "High = les 10 % du portefeuille les plus risqués (capacité de campagne). "
                   "Medium = les tranches suivantes tant que leur taux de churn dépasse 1,2 fois "
                   "la moyenne (jusqu'à 30 % du portefeuille). Low = le reste. Inactif = aucune "
                   "minute d'appel ou usage non mesuré, traité à part.",
        "effectifs": "Deux natures d'effectifs : « clients dans la base » = lignes réelles du "
                     "jeu de données (listes, filtres) ; « équivalent portefeuille » = "
                     "estimation pour un portefeuille réel de 100 000 clients au taux de churn "
                     "supposé de 2 % (KPI, campagne).",
        "inactifs": "Les clients sans aucune minute d'appel (ou dont l'usage n'est pas mesuré) "
                    "sont classés « Inactif / probablement déjà perdu » : on propose de vérifier "
                    "la ligne ou une reconquête, pas une offre de fidélisation.",
        "departs_evites": "Le modèle dit QUI risque de partir, pas si l'offre le retiendra. "
                          "Départs évités = churners ciblés × taux de succès de l'offre. Ce "
                          "taux est inconnu : il se mesure avec un groupe témoin. Tout chiffre "
                          "de départs évités ou de revenu préservé est donc une hypothèse.",
    }


def explain_method(args: MethodArgs) -> dict[str, Any]:
    return {"sujet": args.topic, "explication": _method_texts()[args.topic]}


# --- Registre --------------------------------------------------------------------------------

@dataclass(frozen=True)
class Tool:
    """Outil exposé au LLM."""

    name: str
    description: str
    args_model: type[BaseModel]
    func: Callable[[Any], dict[str, Any]]

    def json_schema(self) -> dict[str, Any]:
        """Schéma JSON des arguments, aplati et sans titres (accepté par les fournisseurs)."""
        return simplify_schema(self.args_model.model_json_schema())


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("get_kpis", "KPI du portefeuille (éventuellement filtré) : clients, churners attendus, "
         "revenu mensuel en jeu, répartition par niveau de risque, campagne officielle.",
         KpiArgs, get_kpis),
    Tool("get_customer", "Fiche d'un client : niveau, risque mensuel, segment, 3 raisons "
         "actionnables, contexte, action suggérée.", CustomerArgs, get_customer),
    Tool("explain_customer", "Contributions SHAP d'un client (log-odds), de la plus forte à la "
         "plus faible.", ExplainArgs, explain_customer),
    Tool("list_at_risk", "Liste des clients les plus à risque (ou au plus fort revenu en jeu), "
         "filtrable, 20 au plus ; inactifs exclus sauf demande explicite.", ListArgs,
         list_at_risk),
    Tool("segment_stats", "Indicateurs par modalité d'une dimension (niveau, segment, région, "
         "ancienneté, âge du terminal, usage, action).", SegmentArgs, segment_stats),
    Tool("global_drivers", "Principaux facteurs de risque selon le modèle (SHAP agrégé), "
         "actionnables et de contexte.", DriversArgs, global_drivers),
    Tool("simulate_campaign", "Simulation d'une campagne de rétention : clients ciblés, "
         "churners attendus contre hasard, revenu en jeu ; départs évités, revenu préservé, coût "
         "et solde selon des HYPOTHÈSES saisies (taux de succès, coût, horizon).",
         CampaignArgs, simulate_campaign),
    Tool("explain_method", "Explication de méthode rédigée par l'équipe : AUC, lift, "
         "calibration, taux réel supposé, SHAP, chiffre 51 pour 1 000, niveaux, effectifs, "
         "inactifs, départs évités.", MethodArgs, explain_method),
]}


def simplify_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Aplati un schéma pydantic : références résolues, ``anyOf [X, null]`` -> X (un champ
    facultatif est simplement absent de ``required``), titres et défauts nuls retirés. Les
    fournisseurs de LLM n'acceptent qu'un sous-ensemble de JSON Schema."""
    defs = schema.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            if "anyOf" in node:
                options = [o for o in node["anyOf"] if o.get("type") != "null"]
                merged = {k: v for k, v in node.items() if k != "anyOf"}
                if len(options) == 1:
                    return walk({**options[0], **merged})
            return {k: (walk(v) if k != "properties" else {p: walk(s) for p, s in v.items()})
                    for k, v in node.items()
                    if k not in ("title", "$defs") and not (k == "default" and v is None)}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


def run_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    """Valide les arguments et exécute l'outil ; les erreurs sont renvoyées, pas levées."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"Outil inconnu : {name}"}
    try:
        args = tool.args_model.model_validate(arguments or {})
    except ValidationError as exc:
        return {"error": f"Arguments invalides pour {name} : {exc.errors(include_url=False)}"}
    start = time.perf_counter()
    try:
        return tool.func(args)
    except CustomerNotFoundError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}
    finally:
        logger.info("Outil %s exécuté en %.0f ms", name, 1000 * (time.perf_counter() - start))
