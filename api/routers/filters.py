"""Valeurs possibles des filtres."""

from fastapi import APIRouter

from api.schemas import FilterOptions
from churn.services import get_filter_options

router = APIRouter(tags=["filters"])


@router.get("/filters", response_model=FilterOptions, summary="Modalités de chaque filtre")
def filter_options() -> dict:
    """Modalités de chaque dimension (ordre d'affichage) avec leur nombre de lignes, champs de
    tri de la liste des clients et bornes du curseur de capacité."""
    return get_filter_options()
