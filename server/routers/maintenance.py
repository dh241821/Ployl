"""Maintenance planning endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_session
from ..models import Produkt, WartungsInsight
from ..schemas import MaintenanceRecommendation
from ..services.audit import audit_context
from ..services.maintenance_planner import MaintenancePlanner

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


@router.post("/refresh", response_model=List[MaintenanceRecommendation])
def refresh_predictions(
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
) -> List[MaintenanceRecommendation]:
    planner = MaintenancePlanner(session)
    with audit_context(user.username):
        insights = planner.refresh_insights()
    return [_serialize_insight(insight) for insight in insights]


@router.get("", response_model=List[MaintenanceRecommendation])
def list_predictions(
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
) -> List[MaintenanceRecommendation]:
    insights = session.query(WartungsInsight).all()
    produkt_map = {p.id: p for p in session.query(Produkt).filter(Produkt.id.in_([i.produkt_id for i in insights]))}
    return [_serialize_insight(insight, produkt_map.get(insight.produkt_id)) for insight in insights]


def _serialize_insight(
    insight: WartungsInsight, produkt: Optional[Produkt] = None
) -> MaintenanceRecommendation:
    produkt = produkt or insight.produkt
    return MaintenanceRecommendation(
        produkt_id=insight.produkt_id,
        produkt_name=produkt.name if produkt else "Unbekannt",
        predicted_date=insight.prognose_datum,
        window_start=insight.fenster_start,
        window_end=insight.fenster_ende,
        confidence=insight.konfidens,
        model_version=insight.modell_version,
        data_points=insight.datenpunkte,
        method=insight.methode,
    )
