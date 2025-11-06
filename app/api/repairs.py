from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import RepairLog
from ..schemas.base import RepairLogCreate, RepairLogRead, RepairLogUpdate
from ..services.device_service import create_repair_log, update_repair_log
from .dependencies import get_db_session

router = APIRouter(prefix="/repairs", tags=["repairs"])


@router.post("/", response_model=RepairLogRead, status_code=status.HTTP_201_CREATED)
async def create_repair(
    payload: RepairLogCreate, session: AsyncSession = Depends(get_db_session)
) -> RepairLog:
    repair = await create_repair_log(session, payload)
    await session.commit()
    await session.refresh(repair)
    return repair


@router.get("/", response_model=list[RepairLogRead])
async def list_repairs(session: AsyncSession = Depends(get_db_session)) -> list[RepairLog]:
    result = await session.execute(select(RepairLog))
    return list(result.scalars())


@router.get("/{repair_id}", response_model=RepairLogRead)
async def get_repair(repair_id: int, session: AsyncSession = Depends(get_db_session)) -> RepairLog:
    repair = await session.get(RepairLog, repair_id)
    if not repair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repair not found")
    return repair


@router.patch("/{repair_id}", response_model=RepairLogRead)
async def patch_repair(
    repair_id: int,
    payload: RepairLogUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> RepairLog:
    repair = await update_repair_log(session, repair_id, payload)
    if not repair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repair not found")
    await session.commit()
    await session.refresh(repair)
    return repair


__all__ = ["router"]
