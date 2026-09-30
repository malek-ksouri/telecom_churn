"""Santé de l'API."""

from fastapi import APIRouter

from api.schemas import Health
from churn.services import get_store

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health, summary="État de l'API et des artefacts")
def health() -> dict:
    """Vérifie que les artefacts sont chargés et renvoie leur date de construction."""
    store = get_store()
    return {"status": "ok", "n_rows": len(store.scores),
            "artifacts_date": store.kpis.get("date"), "model": store.kpis.get("modele"),
            "calibration": store.kpis.get("calibration")}
