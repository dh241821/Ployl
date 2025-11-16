"""Geo-tracking endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_session
from ..schemas import GeoPositionCreate, GeoPositionRead, GeoRouteRead
from ..services.audit import audit_context
from ..services.geo import GeoTrackingService

router = APIRouter(prefix="/api/geo", tags=["geo"])


@router.post("/positions", response_model=GeoPositionRead, status_code=status.HTTP_201_CREATED)
def record_position(
    payload: GeoPositionCreate,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
) -> GeoPositionRead:
    service = GeoTrackingService(session)
    try:
        service.ensure_vehicle_exists(payload.fahrzeug_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    with audit_context(user.username):
        position = service.record_position(
            fahrzeug_id=payload.fahrzeug_id,
            latitude=payload.latitude,
            longitude=payload.longitude,
            accuracy=payload.accuracy,
            zeitstempel=payload.zeitstempel,
        )
    return GeoPositionRead.from_orm(position)


@router.get("/vehicles/{fahrzeug_id}/route", response_model=GeoRouteRead)
def vehicle_route(
    fahrzeug_id: int,
    limit: int = 250,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
) -> GeoRouteRead:
    service = GeoTrackingService(session)
    try:
        service.ensure_vehicle_exists(fahrzeug_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    positions, total_distance = service.vehicle_route(fahrzeug_id, limit)
    return GeoRouteRead(
        fahrzeug_id=fahrzeug_id,
        total_distance_km=total_distance,
        positions=[GeoPositionRead.from_orm(pos) for pos in positions],
    )
