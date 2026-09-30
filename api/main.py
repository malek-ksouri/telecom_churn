"""API FastAPI du projet churn (E13) : `make api` puis http://localhost:8000/docs.

L'API reste fine : chaque router appelle une fonction de ``churn.services`` et valide la
réponse avec ``api.schemas``. Aucune logique métier ici.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import campaign, customers, drivers, filters, health, kpis, risk, segments
from churn.logging_setup import setup_logging
from churn.services import CustomerNotFoundError, get_store

logger = logging.getLogger("api")
API_PREFIX = "/api"
FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]

DESCRIPTION = """
API du tableau de bord de rétention (prédiction du churn télécom).

**Deux natures d'effectifs**, toujours nommées explicitement :

- `n_rows` : **clients dans la base** (lignes réelles du jeu de données, environ 50 % de
  churners) : listes, filtres, pagination ;
- `n_portfolio_equiv` : **estimation** de l'effectif équivalent dans un portefeuille réel de
  100 000 clients au taux de churn **supposé** de 2 % par mois (hypothèse) : KPI, campagne.
  Les churners attendus et le revenu en jeu sont dans cette unité.

**Hypothèses** : taux de churn réel supposé (2 %) ; le taux de succès de l'offre et son coût
sont saisis par l'utilisateur dans le simulateur (jamais inventés). Les explications SHAP
décrivent le modèle, pas des causes.

**Filtres** : paramètres de requête répétables (`?risk_level=High&risk_level=Medium`) ; valeurs
possibles sur `GET /api/filters`.
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Charge les artefacts au démarrage : la première requête reste rapide."""
    setup_logging()
    store = get_store()
    logger.info("API prête : %d clients", len(store.scores))
    yield


app = FastAPI(title="Telecom Churn API", version="1.0.0", description=DESCRIPTION,
              lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=FRONTEND_ORIGINS, allow_methods=["GET"],
                   allow_headers=["*"])

for module in (health, kpis, filters, risk, segments, drivers, campaign, customers):
    app.include_router(module.router, prefix=API_PREFIX)


@app.exception_handler(CustomerNotFoundError)
async def customer_not_found(_: Request, exc: CustomerNotFoundError) -> JSONResponse:
    """404 propre pour un client inconnu."""
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def invalid_value(_: Request, exc: ValueError) -> JSONResponse:
    """Paramètre accepté par le schéma mais refusé par le service (ex. x = y)."""
    return JSONResponse(status_code=422, content={"detail": str(exc)})
