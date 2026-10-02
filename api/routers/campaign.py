"""Simulateur de campagne."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.dependencies import get_filters
from api.schemas import CampaignSimulation
from churn.services import Filters, simulate_campaign

router = APIRouter(tags=["campaign"])


@router.get("/campaign/simulate", response_model=CampaignSimulation,
            summary="Simuler une campagne de rétention")
def simulate(
    filters: Annotated[Filters, Depends(get_filters)],
    capacity_pct: Annotated[float, Query(gt=0, le=100, description="Part du périmètre contactée "
                                                                   "(%).", examples=[10])] = 10,
    success_rate: Annotated[float, Query(ge=0, le=1, description="HYPOTHÈSE : part des churners "
                                         "ciblés retenus par l'offre (0-1).",
                                         examples=[0.2])] = 0.2,
    offer_cost: Annotated[float | None, Query(ge=0, description="Coût de l'offre par client "
                                              "contacté ($). Sans valeur : ni coût ni solde.")
                          ] = None,
    revenue_horizon_months: Annotated[int, Query(ge=1, le=36, description="HYPOTHÈSE : mois de "
                                                 "revenu préservé comptés (revenu sur "
                                                 "l'horizon et solde).")] = 1,
) -> dict:
    """Clients ciblés (actifs, par risque décroissant), churners attendus contre hasard, revenu
    en jeu ; départs évités et revenu préservé selon le taux de succès **supposé** ; coût et
    solde seulement si `offer_cost` est fourni. Inclut la courbe de 1 à 50 % et les inactifs
    (non ciblés, traités à part)."""
    return simulate_campaign(capacity_pct, success_rate, offer_cost, filters,
                             revenue_horizon_months)
