"""Clients : liste paginée, fiche et explication."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from api.dependencies import get_filters
from api.schemas import (
    CustomerDetail,
    CustomerExplanation,
    CustomerPage,
    ErrorResponse,
    SortField,
)
from churn.services import Filters, explain_customer, get_customer, list_customers

router = APIRouter(prefix="/customers", tags=["customers"])
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Client introuvable"}}
CustomerId = Annotated[int, Path(description="Identifiant client (Customer_ID).",
                                 examples=[1035033])]


@router.get("", response_model=CustomerPage, summary="Liste paginée des clients")
def customers(
    filters: Annotated[Filters, Depends(get_filters)],
    sort: Annotated[SortField, Query(description="Champ de tri.")] = "p_real",
    order: Annotated[str, Query(pattern="^(asc|desc)$", description="asc ou desc.")] = "desc",
    page: Annotated[int, Query(ge=1, description="Page, à partir de 1.")] = 1,
    size: Annotated[int, Query(ge=1, le=200, description="Clients par page.")] = 25,
    search: Annotated[str | None, Query(max_length=20, description="Fragment d'identifiant.")
                      ] = None,
) -> dict:
    """Pagination côté serveur. `total_n_rows` compte des clients de la base (lignes réelles)."""
    return list_customers(filters, sort, order, page, size, search)


@router.get("/{customer_id}", response_model=CustomerDetail, responses=NOT_FOUND,
            summary="Fiche client")
def customer(customer_id: CustomerId) -> dict:
    """Profil, probabilités, niveau, segment, 3 raisons actionnables, contexte et action."""
    return get_customer(customer_id)


@router.get("/{customer_id}/explanation", response_model=CustomerExplanation,
            responses=NOT_FOUND, summary="Contributions SHAP (cascade)")
def customer_explanation(customer_id: CustomerId,
                         top: Annotated[int, Query(ge=1, le=40)] = 12) -> dict:
    """De la valeur de base au log-odds du client : contributions les plus fortes, puis la
    somme des autres."""
    return explain_customer(customer_id, top)
