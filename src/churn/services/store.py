"""Chargement des artefacts (une seule fois, en cache) et tranches d'affichage (E13).

Les services ne recalculent aucun modèle : ils lisent ``artifacts/`` (produit par
``make artifacts``) et agrègent. Le chargement prend ~1 s et est fait une fois par processus ;
chaque requête travaille ensuite sur des tableaux en mémoire.

Deux natures d'effectifs (voir ``churn.business.campaign``) :

- ``n_rows`` : lignes réelles de la base (listes, filtres) ;
- ``n_portfolio_equiv`` : estimation pour un portefeuille réel au taux supposé (KPI, campagne),
  via la colonne ``poids_portefeuille``.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np
import pandas as pd

from churn.business.campaign import PORTFOLIO_WEIGHT
from churn.config import get_config

logger = logging.getLogger(__name__)

# Tranches d'affichage (bornes métier issues de l'EDA : fin d'engagement 11-12 mois,
# terminal ancien à partir de 300 jours). Ordre = ordre d'affichage.
TENURE_BANDS = ["0-5 mois", "6-10 mois", "11-12 mois (fin d'engagement)", "13-24 mois",
                "25-36 mois", "37 mois et plus"]
HANDSET_AGE_BANDS = ["moins de 6 mois", "6-9 mois", "10-12 mois", "1-2 ans", "plus de 2 ans",
                     "inconnu"]
USAGE_BANDS = ["aucun usage (0 min ou non mesuré)", "1-100 min", "101-300 min", "301-600 min",
               "plus de 600 min"]
UNKNOWN_AREA = "inconnue"


def tenure_band(months: pd.Series) -> pd.Series:
    """Tranche d'ancienneté (mois)."""
    return pd.cut(months, [-np.inf, 5, 10, 12, 24, 36, np.inf], labels=TENURE_BANDS).astype(str)


def handset_age_band(eqpdays: pd.Series) -> pd.Series:
    """Tranche d'âge du terminal (jours ; seuil de 300 jours de l'EDA)."""
    band = pd.cut(eqpdays, [-np.inf, 182, 299, 365, 730, np.inf], labels=HANDSET_AGE_BANDS[:-1])
    return band.astype(str).where(eqpdays.notna(), HANDSET_AGE_BANDS[-1])


def usage_band(mou: pd.Series) -> pd.Series:
    """Tranche d'usage (minutes d'appel par mois) ; 0 ou non mesuré = inactif (D86)."""
    band = pd.cut(mou, [0, 100, 300, 600, np.inf], labels=USAGE_BANDS[1:]).astype(str)
    return band.where(mou.fillna(0) > 0, USAGE_BANDS[0])


@dataclass(frozen=True)
class Store:
    """Artefacts en mémoire.

    Attributes:
        scores: une ligne par client, index = identifiant client (``Customer_ID``).
        shap: contributions SHAP (log-odds) par variable d'origine, lignes alignées sur
            ``scores``.
        shap_columns: variables d'origine (colonnes de ``shap``).
        factors: 8 premiers facteurs de chaque client (phrases), index = identifiant client.
        kpis: contenu de ``kpis.json`` (seuils, contrôles, hypothèses).
    """

    scores: pd.DataFrame
    shap: np.ndarray
    shap_columns: list[str]
    factors: pd.DataFrame
    kpis: dict[str, Any]

    @property
    def total_portfolio(self) -> float:
        """Équivalent portefeuille de toute la base (``portfolio_size``)."""
        return float(self.scores[PORTFOLIO_WEIGHT].sum())


def load_store() -> Store:
    """Lit les artefacts et prépare les colonnes dérivées (tranches, identifiant texte)."""
    cfg = get_config()
    art = cfg.paths.artifacts_dir
    id_col = cfg.data.id_col
    missing = [f for f in ("scores.parquet", "shap.parquet", "shap_values.parquet", "kpis.json")
               if not (art / f).is_file()]
    if missing:
        raise FileNotFoundError(f"Artefacts absents ({', '.join(missing)}) : lancer "
                                "`make artifacts`.")
    scores = pd.read_parquet(art / "scores.parquet")
    scores["niveau"] = scores["niveau"].astype(str)
    scores["area"] = scores["area"].astype("string").fillna(UNKNOWN_AREA).astype(str)
    scores["tenure_band"] = tenure_band(scores["months"])
    scores["handset_age_band"] = handset_age_band(scores["eqpdays"])
    scores["usage_band"] = usage_band(scores["mou_Mean"])
    scores["id_text"] = scores[id_col].astype(str)
    scores = scores.set_index(id_col, drop=False)

    matrix = pd.read_parquet(art / "shap_values.parquet").set_index(id_col).loc[scores.index]
    factors = pd.read_parquet(art / "shap.parquet").set_index(id_col).sort_index()
    kpis = json.loads((art / "kpis.json").read_text(encoding="utf-8"))
    logger.info("Artefacts chargés : %d clients, %d variables SHAP", len(scores),
                matrix.shape[1])
    return Store(scores=scores, shap=matrix.to_numpy(dtype=np.float32),
                 shap_columns=list(matrix.columns), factors=factors, kpis=kpis)


@lru_cache(maxsize=1)
def get_store() -> Store:
    """Artefacts chargés une fois par processus."""
    return load_store()
