from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import DeviceCategory
from ..schemas.base import DeviceCategoryCreate, DeviceCategoryRead, DeviceCategoryUpdate
from ..services.device_service import create_device_category
from .dependencies import get_db_session

router = APIRouter(prefix="/categories", tags=["categories"])


@router.post("/", response_model=DeviceCategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: DeviceCategoryCreate, session: AsyncSession = Depends(get_db_session)
) -> DeviceCategory:
    category = await create_device_category(session, payload)
    await session.commit()
    await session.refresh(category)
    return category


@router.get("/", response_model=list[DeviceCategoryRead])
async def list_categories(
    session: AsyncSession = Depends(get_db_session),
) -> list[DeviceCategory]:
    result = await session.execute(select(DeviceCategory).order_by(DeviceCategory.name))
    return list(result.scalars())


@router.get("/{category_id}", response_model=DeviceCategoryRead)
async def get_category(
    category_id: int, session: AsyncSession = Depends(get_db_session)
) -> DeviceCategory:
    category = await session.get(DeviceCategory, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


@router.patch("/{category_id}", response_model=DeviceCategoryRead)
async def update_category(
    category_id: int,
    payload: DeviceCategoryUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> DeviceCategory:
    category = await session.get(DeviceCategory, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(category, field, value)

    await session.commit()
    await session.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int, session: AsyncSession = Depends(get_db_session)
) -> None:
    category = await session.get(DeviceCategory, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")

    await session.delete(category)
    await session.commit()


__all__ = ["router"]
