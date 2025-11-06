from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas.base import MaintenanceWindow
from ..services.device_service import get_upcoming_maintenance
from .dependencies import get_db_session

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


@router.get("/upcoming", response_model=list[MaintenanceWindow])
async def maintenance_due(
    days: int | None = None, session: AsyncSession = Depends(get_db_session)
) -> list[MaintenanceWindow]:
    return await get_upcoming_maintenance(session, days)


__all__ = ["router"]
