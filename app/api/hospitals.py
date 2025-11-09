from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db import models
from app.schemas import HospitalCreate, HospitalRead, HospitalUpdate
from app.services import crud

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


@router.get("", response_model=list[HospitalRead])
async def list_hospitals(session: AsyncSession = Depends(get_db)) -> list[HospitalRead]:
    hospitals = await crud.list_hospitals(session)
    return hospitals


@router.post("", response_model=HospitalRead, status_code=status.HTTP_201_CREATED)
async def create_hospital(payload: HospitalCreate, session: AsyncSession = Depends(get_db)) -> HospitalRead:
    hospital = await crud.create_hospital(session, payload)
    await session.commit()
    return hospital


async def get_hospital_or_404(hospital_id: int, session: AsyncSession) -> models.Hospital:
    hospital = await session.get(models.Hospital, hospital_id)
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")
    return hospital


@router.get("/{hospital_id}", response_model=HospitalRead)
async def read_hospital(hospital_id: int, session: AsyncSession = Depends(get_db)) -> HospitalRead:
    hospital = await get_hospital_or_404(hospital_id, session)
    return hospital


@router.patch("/{hospital_id}", response_model=HospitalRead)
async def update_hospital(hospital_id: int, payload: HospitalUpdate, session: AsyncSession = Depends(get_db)) -> HospitalRead:
    hospital = await get_hospital_or_404(hospital_id, session)
    await crud.update_hospital(session, hospital, payload)
    await session.commit()
    return hospital
