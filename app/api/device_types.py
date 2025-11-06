from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.entities import ComponentType, Device, DeviceType
from ..schemas.base import (
    ComponentTypeCreate,
    DeviceTypeCreate,
    DeviceTypeRead,
    DeviceTypeUpdate,
)
from ..services.device_service import create_device_type
from .dependencies import get_db_session

router = APIRouter(prefix="/device-types", tags=["device-types"])


@router.post("/", response_model=DeviceTypeRead, status_code=status.HTTP_201_CREATED)
async def create_device_type_endpoint(
    payload: DeviceTypeCreate, session: AsyncSession = Depends(get_db_session)
) -> DeviceType:
    device_type = await create_device_type(session, payload)
    await session.commit()
    await session.refresh(device_type, attribute_names=["component_types", "category"])
    return device_type


@router.get("/", response_model=list[DeviceTypeRead])
async def list_device_types(session: AsyncSession = Depends(get_db_session)) -> list[DeviceType]:
    result = await session.execute(
        select(DeviceType)
        .options(selectinload(DeviceType.component_types))
        .options(selectinload(DeviceType.category))
        .order_by(DeviceType.name)
    )
    return list(result.scalars().unique())


@router.get("/{device_type_id}", response_model=DeviceTypeRead)
async def get_device_type(
    device_type_id: int, session: AsyncSession = Depends(get_db_session)
) -> DeviceType:
    device_type = await session.get(
        DeviceType,
        device_type_id,
        options=[
            selectinload(DeviceType.component_types),
            selectinload(DeviceType.category),
        ],
    )
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device type not found")
    return device_type


@router.patch("/{device_type_id}", response_model=DeviceTypeRead)
async def update_device_type(
    device_type_id: int,
    payload: DeviceTypeUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> DeviceType:
    device_type = await session.get(DeviceType, device_type_id)
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device type not found")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(device_type, field, value)

    await session.commit()
    await session.refresh(device_type, attribute_names=["component_types", "category"])
    return device_type


@router.post("/{device_type_id}/components", response_model=DeviceTypeRead)
async def add_component_type(
    device_type_id: int,
    components: list[ComponentTypeCreate],
    session: AsyncSession = Depends(get_db_session),
) -> DeviceType:
    device_type = await session.get(
        DeviceType,
        device_type_id,
        options=[selectinload(DeviceType.component_types)],
    )
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device type not found")

    for component in components:
        device_type.component_types.append(ComponentType(name=component.name))

    await session.commit()
    await session.refresh(device_type, attribute_names=["component_types", "category"])
    return device_type


@router.delete("/{device_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device_type(
    device_type_id: int, session: AsyncSession = Depends(get_db_session)
) -> None:
    device_type = await session.get(DeviceType, device_type_id)
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device type not found")

    device_count = await session.execute(
        select(func.count()).select_from(Device).where(Device.device_type_id == device_type_id)
    )
    if device_count.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Produkt ist noch Geräten zugeordnet und kann nicht gelöscht werden.",
        )

    await session.delete(device_type)
    await session.commit()


__all__ = ["router"]
