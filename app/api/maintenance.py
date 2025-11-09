from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.base import MaintenanceAlertRead, MaintenanceAlertUpdate, MaintenanceWindow
from ..services.device_service import (
    get_alerts,
    get_upcoming_maintenance,
    update_alert,
)
from .dependencies import get_db_session

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.get("/upcoming", response_model=list[MaintenanceWindow])
async def maintenance_due(
    days: int | None = None, session: AsyncSession = Depends(get_db_session)
) -> list[MaintenanceWindow]:
    return await get_upcoming_maintenance(session, days)


@router.get("/alerts", response_model=list[MaintenanceAlertRead])
async def list_alerts(
    include_resolved: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> list[MaintenanceAlertRead]:
    alerts = await get_alerts(session, include_resolved)
    return alerts


@router.post("/alerts/{alert_id}", response_model=MaintenanceAlertRead)
async def modify_alert(
    alert_id: int,
    payload: MaintenanceAlertUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> MaintenanceAlertRead:
    alert = await update_alert(session, alert_id, payload)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    await session.commit()
    await session.refresh(alert)
    return alert


__all__ = ["router"]
