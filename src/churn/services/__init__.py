"""Couche de services : fonctions pures sur les artefacts, appelées par l'API et l'assistant."""

from churn.services.analytics import (
    get_drivers,
    get_filter_options,
    get_heatmap,
    get_kpis,
    get_risk_distribution,
    get_segment_profiles,
    get_segments,
)
from churn.services.campaign import simulate_campaign
from churn.services.customers import (
    CustomerNotFoundError,
    explain_customer,
    export_customers,
    get_customer,
    list_customers,
)
from churn.services.filters import DIMENSIONS, Filters
from churn.services.store import get_store

__all__ = [
    "DIMENSIONS",
    "CustomerNotFoundError",
    "Filters",
    "explain_customer",
    "export_customers",
    "get_customer",
    "get_drivers",
    "get_filter_options",
    "get_heatmap",
    "get_kpis",
    "get_risk_distribution",
    "get_segment_profiles",
    "get_segments",
    "get_store",
    "list_customers",
    "simulate_campaign",
]
