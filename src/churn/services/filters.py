"""Filtres communs à tous les services (E13).

Chaque dimension d'analyse est aussi un filtre : une modalité cliquée dans un graphique
(drill-down) devient un filtre de la requête suivante. Plusieurs valeurs d'une même dimension
se combinent par OU, les dimensions entre elles par ET.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

import numpy as np
import pandas as pd

from churn.business.scoring import TIERS
from churn.services.store import HANDSET_AGE_BANDS, TENURE_BANDS, USAGE_BANDS

# Dimension de l'API -> colonne des scores.
DIMENSIONS: dict[str, str] = {
    "risk_level": "niveau",
    "cluster": "segment",
    "area": "area",
    "tenure_band": "tenure_band",
    "handset_age_band": "handset_age_band",
    "usage_band": "usage_band",
    "action": "action",
}
# Ordre d'affichage fixe des dimensions ordonnées (les autres : par effectif décroissant).
ORDERED: dict[str, list[str]] = {
    "risk_level": TIERS,
    "tenure_band": TENURE_BANDS,
    "handset_age_band": HANDSET_AGE_BANDS,
    "usage_band": USAGE_BANDS,
}
DIMENSION_LABELS: dict[str, str] = {
    "risk_level": "Niveau de risque",
    "cluster": "Segment comportemental",
    "area": "Région",
    "tenure_band": "Ancienneté",
    "handset_age_band": "Âge du terminal",
    "usage_band": "Usage mensuel",
    "action": "Action suggérée",
}


@dataclass(frozen=True)
class Filters:
    """Filtres de la requête ; ``None`` ou liste vide = pas de filtre sur la dimension."""

    risk_level: tuple[str, ...] | None = None
    cluster: tuple[str, ...] | None = None
    area: tuple[str, ...] | None = None
    tenure_band: tuple[str, ...] | None = None
    handset_age_band: tuple[str, ...] | None = None
    usage_band: tuple[str, ...] | None = None
    action: tuple[str, ...] | None = None

    def active(self) -> dict[str, list[str]]:
        """Filtres effectivement appliqués (dimension -> valeurs)."""
        return {f.name: list(v) for f in fields(self) if (v := getattr(self, f.name))}


def filter_mask(scores: pd.DataFrame, filters: Filters | None) -> np.ndarray:
    """Masque booléen des clients qui respectent tous les filtres."""
    mask = np.ones(len(scores), dtype=bool)
    if filters is None:
        return mask
    for dim, values in filters.active().items():
        mask &= scores[DIMENSIONS[dim]].isin(values).to_numpy()
    return mask


def dimension_values(scores: pd.DataFrame, dimension: str) -> list[str]:
    """Modalités d'une dimension dans l'ordre d'affichage."""
    column = DIMENSIONS[dimension]
    present = set(scores[column].dropna().unique())
    if dimension in ORDERED:
        return [v for v in ORDERED[dimension] if v in present]
    counts = scores[column].value_counts()
    return [str(v) for v in counts.index if v in present]
