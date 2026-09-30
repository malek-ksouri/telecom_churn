"""Dépendances communes : filtres passés en paramètres de requête."""

from __future__ import annotations

from typing import Annotated

from fastapi import Query

from churn.services import Filters

_HELP = "Valeurs possibles : GET /api/filters. Répéter le paramètre pour plusieurs valeurs (OU)."


def _values(v: list[str] | None) -> tuple[str, ...] | None:
    return tuple(v) if v else None


def get_filters(
    risk_level: Annotated[list[str] | None, Query(description="Niveau de risque. " + _HELP,
                                                  examples=["High"])] = None,
    cluster: Annotated[list[str] | None, Query(description="Segment K-means. " + _HELP)] = None,
    area: Annotated[list[str] | None, Query(description="Région. " + _HELP)] = None,
    tenure_band: Annotated[list[str] | None, Query(description="Tranche d'ancienneté. "
                                                               + _HELP)] = None,
    handset_age_band: Annotated[list[str] | None, Query(description="Tranche d'âge du terminal. "
                                                                    + _HELP)] = None,
    usage_band: Annotated[list[str] | None, Query(description="Tranche d'usage. " + _HELP)] = None,
    action: Annotated[list[str] | None, Query(description="Action suggérée. " + _HELP)] = None,
) -> Filters:
    """Filtres communs (dimensions combinées par ET, valeurs d'une dimension par OU)."""
    return Filters(risk_level=_values(risk_level), cluster=_values(cluster), area=_values(area),
                   tenure_band=_values(tenure_band), handset_age_band=_values(handset_age_band),
                   usage_band=_values(usage_band), action=_values(action))
