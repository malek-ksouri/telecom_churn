"""Construction des features : transformer sklearn **sans état appris**.

Chaque feature est une règle fixe (ratio, seuil, indicateur) : ``fit`` n'apprend rien,
le transformer peut donc être appliqué avant ou dans la validation croisée sans fuite.
Les familles sont activables par paramètre (``features.groups`` dans la config) pour
l'ablation (E6) et le test de fuite « déjà parti » (D32, E8).

Les seuils 11-12 mois et 300 jours viennent de l'EDA (E4) sur le train entier : ils
influencent légèrement la validation croisée ; le jeu de test, lui, reste intact.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin

from churn.data.validate import NEGATIVE_FLAG_SUFFIX, NEGATIVE_TO_NAN_COLUMNS

# --- Définition des familles -------------------------------------------------------------
CONTRACT_END_MONTHS = (11, 12)   # pic de churn en EDA (E4) ; pas de pic à 23-24 mois (E6)
HANDSET_OLD_DAYS = 300           # rupture du churn vers 305 jours d'âge du terminal (E4)
DAYS_PER_MONTH = 30

# Indicateurs de manquants d'origine, un par motif (E2, E5) : nom -> colonne représentante.
MISSING_PATTERNS: dict[str, str] = {
    "manquant_numbcars": "numbcars",
    "manquant_dwllsize": "dwllsize",
    "manquant_HHstatin": "HHstatin",
    "manquant_ownrent": "ownrent",
    "manquant_dwlltype": "dwlltype",
    "manquant_lor": "lor",
    "manquant_income": "income",
    "manquant_adults": "adults",
    "manquant_infobase": "infobase",
    "manquant_hnd_webcap": "hnd_webcap",
    "manquant_prizm_social_one": "prizm_social_one",
    "manquant_avg6mou_bloc": "avg6mou",
    "manquant_truck_bloc": "truck",
    "manquant_hnd_price": "hnd_price",
    "manquant_area": "area",
}
# Groupe séparé (D32) : absence totale d'usage et absence de variation d'usage, qui
# pourraient traduire un client déjà parti au moment de la mesure.
ALREADY_GONE_PATTERNS: dict[str, str] = {
    "sans_usage": "rev_Mean",
    "change_manquant": "change_mou",
}
NEGATIVE_FLAGS = [f"{c}{NEGATIVE_FLAG_SUFFIX}" for c in NEGATIVE_TO_NAN_COLUMNS]

FEATURE_GROUPS: dict[str, list[str]] = {
    "cycle_engagement": ["in_contract_end", "handset_old", "eqpdays_per_tenure_day"],
    "tendance_usage": ["ratio_mou_3m_6m", "ratio_rev_3m_6m"],
    "qualite_reseau": ["drop_blk_rate", "complete_rate"],
    "service_client": ["has_custcare", "custcare_per_mou"],
    "forfait": ["overage_share_rev", "recurring_share_rev"],
    "compte_terminal": ["active_lines_share", "phones_per_month"],
    "indicateurs_manquants": list(MISSING_PATTERNS) + NEGATIVE_FLAGS,
    "deja_parti": list(ALREADY_GONE_PATTERNS),
}
ALL_GROUPS: tuple[str, ...] = tuple(FEATURE_GROUPS)


def safe_divide(num: pd.Series, den: pd.Series) -> pd.Series:
    """Division où un dénominateur nul ou manquant donne NaN (jamais ±inf)."""
    num = num.astype(float)
    den = den.astype(float)
    out = num / den.where(den != 0)
    return out.where(np.isfinite(out))


def _source_missing(df: pd.DataFrame, col: str) -> pd.Series:
    """Manquant d'origine : NaN qui ne vient pas d'une valeur négative mise à NaN par clean()."""
    missing = df[col].isna()
    flag = f"{col}{NEGATIVE_FLAG_SUFFIX}"
    if flag in df:
        missing &= df[flag] == 0
    return missing.astype("int8")


class FeatureBuilder(BaseEstimator, TransformerMixin):
    """Ajoute les familles de features demandées aux colonnes d'origine.

    Sans état : ``fit`` ne fait que valider les paramètres, ``transform`` n'utilise que
    des règles fixes. Les indicateurs ``_was_negative`` ne sont conservés que si la
    famille ``indicateurs_manquants`` est active (sinon la référence les contiendrait déjà).

    Args:
        groups: familles à ajouter (``None`` = toutes). Liste vide = variables d'origine seules.
        drop_columns: colonnes à retirer de la sortie (identifiant, cible, variables exclues).
    """

    def __init__(self, groups: Sequence[str] | None = None,
                 drop_columns: Sequence[str] = ()) -> None:
        self.groups = groups
        self.drop_columns = drop_columns

    def _groups(self) -> list[str]:
        groups = list(ALL_GROUPS) if self.groups is None else list(self.groups)
        unknown = set(groups) - set(ALL_GROUPS)
        if unknown:
            raise ValueError(f"Familles inconnues : {sorted(unknown)} ; connues : {ALL_GROUPS}")
        return groups

    def fit(self, X: pd.DataFrame, y: pd.Series | None = None) -> FeatureBuilder:
        """Aucun apprentissage : valide seulement les familles demandées."""
        self._groups()
        return self

    def __sklearn_tags__(self):  # noqa: D105 - le transformer n'a pas besoin d'être ajusté
        tags = super().__sklearn_tags__()
        tags.requires_fit = False
        return tags

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Renvoie les variables d'origine (moins ``drop_columns``) + les familles actives."""
        groups = self._groups()
        base = X.drop(columns=[c for c in self.drop_columns if c in X]
                      + [c for c in NEGATIVE_FLAGS if c in X])
        new: dict[str, pd.Series] = {}
        if "cycle_engagement" in groups:
            new["in_contract_end"] = X["months"].isin(CONTRACT_END_MONTHS).astype("int8")
            new["handset_old"] = (X["eqpdays"] >= HANDSET_OLD_DAYS).astype("int8")
            new["eqpdays_per_tenure_day"] = safe_divide(X["eqpdays"],
                                                        X["months"] * DAYS_PER_MONTH)
        if "tendance_usage" in groups:
            new["ratio_mou_3m_6m"] = safe_divide(X["avg3mou"], X["avg6mou"])
            new["ratio_rev_3m_6m"] = safe_divide(X["avg3rev"], X["avg6rev"])
        if "qualite_reseau" in groups:
            new["drop_blk_rate"] = safe_divide(X["drop_blk_Mean"], X["attempt_Mean"])
            new["complete_rate"] = safe_divide(X["complete_Mean"], X["attempt_Mean"])
        if "service_client" in groups:
            new["has_custcare"] = (X["custcare_Mean"] > 0).astype("int8")
            new["custcare_per_mou"] = safe_divide(X["custcare_Mean"], X["mou_Mean"] + 1)
        if "forfait" in groups:
            new["overage_share_rev"] = safe_divide(X["ovrrev_Mean"], X["rev_Mean"])
            new["recurring_share_rev"] = safe_divide(X["totmrc_Mean"], X["rev_Mean"])
        if "compte_terminal" in groups:
            new["active_lines_share"] = safe_divide(X["actvsubs"], X["uniqsubs"])
            new["phones_per_month"] = safe_divide(X["phones"], X["months"])
        if "indicateurs_manquants" in groups:
            for name, col in MISSING_PATTERNS.items():
                new[name] = _source_missing(X, col)
            for flag in NEGATIVE_FLAGS:
                new[flag] = X[flag].astype("int8")
        if "deja_parti" in groups:
            for name, col in ALREADY_GONE_PATTERNS.items():
                new[name] = _source_missing(X, col)
        return pd.concat([base, pd.DataFrame(new, index=X.index)], axis=1)

    def get_feature_names_out(self, input_features: Sequence[str] | None = None) -> np.ndarray:
        """Noms des colonnes produites (nécessite les noms d'entrée)."""
        if input_features is None:
            raise ValueError("input_features est requis (transformer sans état).")
        base = [c for c in input_features
                if c not in self.drop_columns and c not in NEGATIVE_FLAGS]
        added = [f for g in self._groups() for f in FEATURE_GROUPS[g]]
        return np.array(base + added, dtype=object)
