"""Assistant IA : conversation en streaming SSE, textes pour les conseillers, résumé exécutif."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from fastapi.responses import StreamingResponse

from api.dependencies import AssistantClient, get_assistant_client
from api.schemas import (
    AdvisorExplanation,
    AssistantStatus,
    ChatAnswer,
    ChatRequest,
    ErrorResponse,
    ExecutiveSummary,
    RetentionMessage,
)
from churn.assistant.agent import (
    MAX_HISTORY,
    Agent,
    executive_summary,
    explain_for_advisor,
    retention_message,
    status,
)

router = APIRouter(tags=["assistant"])
Client = Annotated[AssistantClient, Depends(get_assistant_client)]
CustomerId = Annotated[int, Path(description="Identifiant client (Customer_ID).",
                                 examples=[1072931])]
NOT_FOUND = {404: {"model": ErrorResponse, "description": "Client introuvable"}}

SSE_DESCRIPTION = """Réponse en **Server-Sent Events** (`text/event-stream`). Événements :

- `token` : `{"text": "...", "step": n}` — morceau de texte ;
- `tool_call` : `{"name": "...", "args": {...}}` — outil appelé ;
- `tool_result` : `{"name", "args", "duration_ms", "ok", "result"}` ;
- `done` : réponse finale (schéma `ChatAnswer` : réponse, outils appelés, avertissements) ;
- `error` : `{"message", "kind", "recoverable"}` ; si `recoverable`, la réponse continue en
  mode démonstration.

5 appels d'outils au plus par question ; seuls les 10 derniers messages d'historique sont
transmis au modèle."""


def _sse(events: Iterator) -> Iterator[str]:
    for event in events:
        yield f"event: {event.type}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"


@router.post("/chat", summary="Poser une question à l'assistant (streaming SSE)",
             description=SSE_DESCRIPTION,
             responses={200: {"content": {"text/event-stream": {}},
                              "description": "Flux d'événements ; `done` suit le schéma "
                                             "ChatAnswer.",
                              "model": ChatAnswer}})
def chat(request: ChatRequest, client: Client) -> StreamingResponse:
    history = [t.model_dump() for t in request.history][-MAX_HISTORY:]
    events = Agent(client=client.client).run(request.message, history)
    return StreamingResponse(_sse(events), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/customers/{customer_id}/explain-ai", response_model=AdvisorExplanation,
             responses=NOT_FOUND, summary="Explication du risque pour un conseiller (IA)")
def explain_ai(customer_id: CustomerId, client: Client) -> dict:
    """3 à 4 phrases à partir de la fiche et des contributions SHAP du client, « selon le
    modèle » ; nombres contrôlés par les garde-fous."""
    return explain_for_advisor(customer_id, client.client)


@router.post("/customers/{customer_id}/retention-message", response_model=RetentionMessage,
             responses=NOT_FOUND, summary="SMS et email de rétention (IA)")
def retention(customer_id: CustomerId, client: Client) -> dict:
    """SMS (300 caractères au plus) et email adaptés au facteur dominant et à l'action, sans
    promesse chiffrée."""
    return retention_message(customer_id, client.client)


@router.get("/summary", response_model=ExecutiveSummary,
            summary="Résumé exécutif « Ce qu'il faut retenir »")
def summary(client: Client) -> dict:
    """4 à 5 puces à partir des KPI et des statistiques par segment, mises en cache."""
    return executive_summary(client.client)


@router.get("/assistant/status", response_model=AssistantStatus,
            summary="Fournisseur actif de l'assistant")
def assistant_status(client: Client) -> dict:
    """Fournisseur (gemini ou demo), modèle et raison d'un éventuel mode démonstration. Ne fait
    aucun appel au fournisseur et n'expose jamais la clé."""
    return status(client.client, client.demo_reason)
