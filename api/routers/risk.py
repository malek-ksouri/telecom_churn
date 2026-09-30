"""Distribution du risque."""

from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_filters
from api.schemas import RiskDistribution
from churn.services import Filters, get_risk_distribution

router = APIRouter(tags=["risk"])


@router.get("/risk/distribution", response_model=RiskDistribution,
            summary="Histogramme des probabilités et répartition par niveau")
def risk_distribution(filters: Annotated[Filters, Depends(get_filters)]) -> dict:
    """Histogramme de la probabilité mensuelle corrigée (classes de 0,5 point, dernière classe
    ouverte à 15 %), empilé par niveau, quantiles et seuils des niveaux."""
    return get_risk_distribution(filters)
