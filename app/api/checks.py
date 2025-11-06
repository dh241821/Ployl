from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import SafetyCheck
from ..schemas.base import SafetyCheckCreate, SafetyCheckRead
from ..services.device_service import create_safety_check
from .dependencies import get_db_session

router = APIRouter(prefix="/checks", tags=["checks"])


@router.post("/", response_model=SafetyCheckRead, status_code=status.HTTP_201_CREATED)
async def create_check(
    payload: SafetyCheckCreate, session: AsyncSession = Depends(get_db_session)
) -> SafetyCheck:
    safety_check = await create_safety_check(session, payload)
    await session.commit()
    await session.refresh(safety_check)
    return safety_check


@router.get("/", response_model=list[SafetyCheckRead])
async def list_checks(session: AsyncSession = Depends(get_db_session)) -> list[SafetyCheck]:
    result = await session.execute(select(SafetyCheck))
    return list(result.scalars())


@router.get("/{check_id}", response_model=SafetyCheckRead)
async def get_check(check_id: int, session: AsyncSession = Depends(get_db_session)) -> SafetyCheck:
    safety_check = await session.get(SafetyCheck, check_id)
    if not safety_check:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Safety check not found")
    return safety_check


__all__ = ["router"]
