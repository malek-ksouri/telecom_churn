"""KPI globaux du périmètre filtré."""

from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_filters
from api.schemas import Kpis
from churn.services import Filters, get_kpis

router = APIRouter(tags=["kpis"])


@router.get("/kpis", response_model=Kpis, summary="KPI du périmètre filtré")
def kpis(filters: Annotated[Filters, Depends(get_filters)]) -> dict:
    """Effectifs (`n_rows` : base ; `n_portfolio_equiv` : estimation au taux supposé), churners
    attendus, revenu en jeu, répartition par niveau et campagne officielle (capacité 10 %,
    inactifs à part)."""
    return get_kpis(filters)
