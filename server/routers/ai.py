"""AI assistant endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_session
from ..schemas import (
    AnomalyDetectionRequest,
    AnomalyDetectionResponse,
    CategorizationRequest,
    CategorizationResponse,
    ChatRequest,
    ChatResponse,
)
from ..services.ai import AIService

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    session: Session = Depends(get_session),
    _user=Depends(get_current_user),
) -> ChatResponse:
    service = AIService(session)
    response, intent, confidence = service.chat(request.prompt, request.context)
    return ChatResponse(response=response, intent=intent, confidence=confidence)


@router.post("/categorize", response_model=CategorizationResponse)
def categorize(
    request: CategorizationRequest,
    session: Session = Depends(get_session),
    _user=Depends(get_current_user),
) -> CategorizationResponse:
    service = AIService(session)
    category, confidence, rationale = service.categorise(request.name, request.beschreibung, request.produkt_id)
    return CategorizationResponse(suggested_kategorie=category, confidence=confidence, rationale=rationale)


@router.post("/anomaly", response_model=AnomalyDetectionResponse)
def anomaly(
    request: AnomalyDetectionRequest,
    session: Session = Depends(get_session),
    _user=Depends(get_current_user),
) -> AnomalyDetectionResponse:
    service = AIService(session)
    anomaly, score, threshold, details = service.detect_anomaly(request.values, request.metric, request.scope, request.reference_id)
    return AnomalyDetectionResponse(anomaly=anomaly, score=score, threshold=threshold, details=details)

