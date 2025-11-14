"""Cost analytics and lifecycle endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_session
from ..schemas import CostEntryCreate, CostEntryRead, LifecycleCostSummary
from ..services.audit import audit_context
from ..services.costs import CostAnalyticsService

router = APIRouter(prefix="/api/costs", tags=["costs"])


@router.post("/entries", response_model=CostEntryRead, status_code=status.HTTP_201_CREATED)
def create_cost_entry(
    payload: CostEntryCreate,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
) -> CostEntryRead:
    service = CostAnalyticsService(session)
    with audit_context(user.username):
        entry = service.create_entry(
            produkt_id=payload.produkt_id,
            fahrzeug_id=payload.fahrzeug_id,
            datum=payload.datum,
            betrag=payload.betrag,
            typ=payload.typ,
            beschreibung=payload.beschreibung,
            quelle=payload.quelle,
        )
    return CostEntryRead.from_orm(entry)


@router.get("/lifecycle", response_model=List[LifecycleCostSummary])
def lifecycle_overview(
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
) -> List[LifecycleCostSummary]:
    service = CostAnalyticsService(session)
    summaries = service.lifecycle_costs()
    return [LifecycleCostSummary(**summary.__dict__) for summary in summaries]
