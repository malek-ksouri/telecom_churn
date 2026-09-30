"""Facteurs de risque (SHAP agrégé)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_filters
from api.schemas import Drivers
from churn.services import Filters, get_drivers

router = APIRouter(tags=["drivers"])


@router.get("/drivers", response_model=Drivers, summary="Importance des facteurs (SHAP)")
def drivers(filters: Annotated[Filters, Depends(get_filters)],
            top: Annotated[int, Query(ge=1, le=60, description="Facteurs par liste.")] = 15
            ) -> dict:
    """Moyenne de |SHAP| sur les clients filtrés, facteurs actionnables et de contexte séparés,
    et parts par famille. SHAP explique le modèle, pas la causalité."""
    return get_drivers(filters, top)
