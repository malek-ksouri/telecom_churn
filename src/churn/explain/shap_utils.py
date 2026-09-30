"""Valeurs SHAP du LightGBM final (E11).

- ``TreeExplainer`` sur le LightGBM du pipeline : valeurs SHAP exactes, sur l'échelle
  **log-odds** (la somme des contributions + la valeur de base = log-odds du modèle brut).
  La calibration sigmoïde (E10) est une transformation monotone appliquée ensuite : elle ne
  change ni le classement ni le sens des effets.
- Les features dérivées (E6) sont **regroupées sur leur variable d'origine** : les valeurs SHAP
  étant additives, la contribution d'un groupe est la somme de celles de ses colonnes.

SHAP explique le **modèle**, pas la causalité : une contribution positive signifie « selon le
modèle, cette caractéristique est associée à un risque plus élevé ».
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import shap
from sklearn.pipeline import Pipeline

from churn.data.validate import NEGATIVE_FLAG_SUFFIX
from churn.features.build import ALREADY_GONE_PATTERNS, MISSING_PATTERNS

# Features dérivées (E6) -> variable d'origine à laquelle leur effet est rattaché.
DERIVED_TO_SOURCE: dict[str, str] = {
    "in_contract_end": "months",
    "handset_old": "eqpdays",
    "eqpdays_per_tenure_day": "eqpdays",
    "ratio_mou_3m_6m": "avg3mou",
    "ratio_rev_3m_6m": "avg3rev",
    "drop_blk_rate": "drop_blk_Mean",
    "complete_rate": "complete_Mean",
    "has_custcare": "custcare_Mean",
    "custcare_per_mou": "custcare_Mean",
    "overage_share_rev": "ovrrev_Mean",
    "recurring_share_rev": "totmrc_Mean",
    "active_lines_share": "actvsubs",
    "phones_per_month": "phones",
    **MISSING_PATTERNS,
    **ALREADY_GONE_PATTERNS,
}

# Libellés lisibles des variables d'origine (les autres gardent leur nom technique).
LABELS: dict[str, str] = {
    "months": "Ancienneté",
    "eqpdays": "Âge du terminal",
    "change_mou": "Évolution de l'usage",
    "change_rev": "Évolution de la facture",
    "mou_Mean": "Minutes d'appel par mois",
    "avg3mou": "Usage récent (3 mois / 6 mois)",
    "avg3rev": "Facture récente (3 mois / 6 mois)",
    "avgqty": "Appels par mois depuis l'ouverture",
    "avgmou": "Minutes par mois depuis l'ouverture",
    "avgrev": "Facture moyenne depuis l'ouverture",
    "rev_Mean": "Facture mensuelle",
    "totmrc_Mean": "Forfait mensuel",
    "ovrrev_Mean": "Dépassements de forfait",
    "hnd_price": "Prix du terminal",
    "hnd_webcap": "Capacité web du terminal",
    "crclscod": "Classe de crédit",
    "area": "Région",
    "lor": "Durée de résidence",
    "drop_vce_Mean": "Appels coupés",
    "drop_blk_Mean": "Appels coupés ou bloqués",
    "blck_vce_Mean": "Appels bloqués",
    "unan_vce_Mean": "Appels sans réponse",
    "custcare_Mean": "Appels au service client",
    "phones": "Nombre de terminaux",
    "models": "Nombre de modèles de terminal",
    "actvsubs": "Lignes actives",
    "uniqsubs": "Lignes ouvertes",
    "asl_flag": "Limite de dépense",
    "dualband": "Terminal bi-bande",
    "refurb_new": "Terminal reconditionné",
    "prizm_social_one": "Type de zone d'habitation",
    "income": "Tranche de revenu",
    "totrev": "Revenu total",
    "roam_Mean": "Itinérance",
    "mou_cvce_Mean": "Minutes d'appels aboutis",
    "mouowylisv_Mean": "Minutes d'appels sortants sans réponse",
    "mouiwylisv_Mean": "Minutes d'appels entrants manqués",
    "recv_vce_Mean": "Appels reçus",
    "da_Mean": "Appels à l'assistance annuaire",
    "callwait_Mean": "Double appel",
    "avg6rev": "Facture moyenne sur 6 mois",
    "avg6mou": "Minutes moyennes sur 6 mois",
    "avg6qty": "Appels moyens sur 6 mois",
    "avg3qty": "Appels moyens sur 3 mois",
    "adults": "Adultes dans le foyer",
    "numbcars": "Véhicules du foyer",
    "marital": "Situation familiale",
    "creditcd": "Carte de crédit",
    "new_cell": "Nouvel utilisateur de mobile",
    "ovrmou_Mean": "Minutes hors forfait",
    "vceovr_Mean": "Dépassements voix",
    "datovr_Mean": "Dépassements data",
    "totmou": "Minutes depuis l'ouverture",
    "totcalls": "Appels depuis l'ouverture",
    "adjmou": "Minutes ajustées depuis l'ouverture",
    "adjqty": "Appels ajustés depuis l'ouverture",
    "adjrev": "Revenu ajusté depuis l'ouverture",
    "attempt_Mean": "Tentatives d'appel",
    "complete_Mean": "Appels aboutis",
    "comp_vce_Mean": "Appels voix aboutis",
    "plcd_vce_Mean": "Appels voix passés",
    "peak_vce_Mean": "Appels voix en heures pleines",
    "opk_vce_Mean": "Appels voix en heures creuses",
    "mou_peav_Mean": "Minutes voix en heures pleines",
    "mou_opkv_Mean": "Minutes voix en heures creuses",
    "mou_rvce_Mean": "Minutes d'appels reçus",
    "inonemin_Mean": "Appels entrants de moins d'une minute",
    "owylis_vce_Mean": "Appels sortants vers messagerie",
    "iwylis_vce_Mean": "Appels entrants vers messagerie",
    "threeway_Mean": "Conférences à trois",
    "callfwdv_Mean": "Renvois d'appel",
    "cc_mou_Mean": "Minutes au service client",
    "ccrndmou_Mean": "Minutes arrondies au service client",
    "drop_dat_Mean": "Sessions data coupées",
    "blck_dat_Mean": "Sessions data bloquées",
    "recv_sms_Mean": "SMS reçus",
    "HHstatin": "Statut du foyer",
    "dwllsize": "Taille du logement",
    "dwlltype": "Type de logement",
    "ownrent": "Propriétaire ou locataire",
    "infobase": "Source des données client",
    "forgntvl": "Voyages à l'étranger",
    "truck": "Possède un utilitaire",
    "rv": "Possède un camping-car",
    "kid0_2": "Enfant de 0 à 2 ans",
    "kid3_5": "Enfant de 3 à 5 ans",
    "kid6_10": "Enfant de 6 à 10 ans",
    "kid11_15": "Enfant de 11 à 15 ans",
    "kid16_17": "Enfant de 16 à 17 ans",
}


def source_variable(feature: str) -> str:
    """Variable d'origine d'une feature (elle-même si ce n'est pas une feature dérivée)."""
    if feature in DERIVED_TO_SOURCE:
        return DERIVED_TO_SOURCE[feature]
    if feature.endswith(NEGATIVE_FLAG_SUFFIX):
        return feature.removesuffix(NEGATIVE_FLAG_SUFFIX)
    return feature


def label(variable: str) -> str:
    """Libellé lisible d'une variable d'origine."""
    return LABELS.get(variable, variable)


@dataclass
class ShapResult:
    """Valeurs SHAP d'un lot de clients.

    Attributes:
        values: contributions (log-odds) par feature du modèle, une ligne par client.
        features: valeurs des features vues par le modèle (après ``FeatureBuilder``).
        base_value: log-odds moyen du modèle (point de départ de l'explication).
    """

    values: pd.DataFrame
    features: pd.DataFrame
    base_value: float

    def grouped(self) -> pd.DataFrame:
        """Contributions regroupées par variable d'origine (somme des colonnes du groupe)."""
        groups = {c: source_variable(c) for c in self.values.columns}
        return self.values.T.groupby(groups).sum().T

    def log_odds(self) -> pd.Series:
        """Log-odds du modèle brut reconstitué (valeur de base + somme des contributions)."""
        return self.base_value + self.values.sum(axis=1)


class ShapExplainer:
    """Explique le LightGBM d'un pipeline ``features -> model`` (``build_pipeline("lightgbm")``)."""

    def __init__(self, pipeline: Pipeline) -> None:
        self.features_step = pipeline.named_steps["features"]
        self.model = pipeline.named_steps["model"]
        self.explainer = shap.TreeExplainer(self.model)

    def explain(self, X: pd.DataFrame) -> ShapResult:
        """Valeurs SHAP (log-odds) des clients de ``X`` (colonnes d'origine, nettoyées)."""
        features = self.features_step.transform(X)
        values = self.explainer.shap_values(features)
        values = values[1] if isinstance(values, list) else values
        base = self.explainer.expected_value
        base = float(base[1] if np.ndim(base) else base)
        return ShapResult(values=pd.DataFrame(values, index=X.index, columns=features.columns),
                          features=features, base_value=base)


def global_importance(result: ShapResult, grouped: bool = True) -> pd.DataFrame:
    """Importance globale = moyenne de |SHAP| par variable (ou par feature), avec libellé."""
    values = result.grouped() if grouped else result.values
    imp = values.abs().mean().sort_values(ascending=False)
    out = imp.rename("shap_abs_moyen").to_frame()
    out["libelle"] = [label(v) if grouped else label(source_variable(v)) for v in out.index]
    out["part_pct"] = (100 * out["shap_abs_moyen"] / out["shap_abs_moyen"].sum()).round(1)
    return out
