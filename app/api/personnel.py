from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db import models
from app.schemas import PersonnelCreate, PersonnelRead, PersonnelUpdate
from app.services import crud

router = APIRouter(prefix="/personnel", tags=["personnel"])


@router.get("", response_model=list[PersonnelRead])
async def list_personnel(session: AsyncSession = Depends(get_db)) -> list[PersonnelRead]:
    people = await crud.list_personnel(session)
    return people


@router.post("", response_model=PersonnelRead, status_code=status.HTTP_201_CREATED)
async def create_personnel(payload: PersonnelCreate, session: AsyncSession = Depends(get_db)) -> PersonnelRead:
    person = await crud.create_personnel(session, payload)
    await session.commit()
    return person


async def get_personnel_or_404(personnel_id: int, session: AsyncSession) -> models.Personnel:
    person = await session.get(models.Personnel, personnel_id)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Personnel not found")
    return person


@router.patch("/{personnel_id}", response_model=PersonnelRead)
async def update_personnel(personnel_id: int, payload: PersonnelUpdate, session: AsyncSession = Depends(get_db)) -> PersonnelRead:
    person = await get_personnel_or_404(personnel_id, session)
    await crud.update_personnel(session, person, payload)
    await session.commit()
    return person
