"""Predictive analytics endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_session
from ..schemas import InventoryForecastRead
from ..services.predictions import PredictionService

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.post("/inventory", response_model=list[InventoryForecastRead])
def refresh_inventory(
    session: Session = Depends(get_session),
    _user=Depends(get_current_user),
) -> list[InventoryForecastRead]:
    service = PredictionService(session)
    forecasts = service.refresh_inventory_forecasts()
    return [InventoryForecastRead.from_orm(forecast) for forecast in forecasts]
