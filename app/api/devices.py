from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.entities import Device, DeviceComponent, DeviceType
from ..schemas.base import DeviceCreate, DeviceRead, DeviceUpdate
from ..services.device_service import create_device, get_device_history
from .dependencies import get_db_session

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/", response_model=DeviceRead, status_code=status.HTTP_201_CREATED)
async def create_device_endpoint(
    payload: DeviceCreate, session: AsyncSession = Depends(get_db_session)
) -> Device:
    device = await create_device(session, payload)
    await session.commit()
    await session.refresh(
        device,
        attribute_names=["components", "device_type"],
    )
    return device


@router.get("/", response_model=list[DeviceRead])
async def list_devices(session: AsyncSession = Depends(get_db_session)) -> list[Device]:
    result = await session.execute(
        select(Device)
        .options(
            selectinload(Device.device_type).selectinload(DeviceType.category)
        )
        .options(
            selectinload(Device.components).selectinload(DeviceComponent.component_type)
        )
        .order_by(Device.inventory_number)
    )
    return list(result.scalars().unique())


@router.get("/{device_id}", response_model=DeviceRead)
async def get_device(device_id: int, session: AsyncSession = Depends(get_db_session)) -> Device:
    device = await session.get(
        Device,
        device_id,
        options=[
            selectinload(Device.device_type).selectinload(DeviceType.category),
            selectinload(Device.components).selectinload(DeviceComponent.component_type),
        ],
    )
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


@router.patch("/{device_id}", response_model=DeviceRead)
async def update_device(
    device_id: int, payload: DeviceUpdate, session: AsyncSession = Depends(get_db_session)
) -> Device:
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(device, field, value)

    await session.commit()
    await session.refresh(
        device,
        attribute_names=["components", "device_type"],
    )
    return device


@router.get("/{device_id}/history")
async def device_history(
    device_id: int, session: AsyncSession = Depends(get_db_session)
) -> dict[str, list]:
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    history = await get_device_history(session, device_id)
    return {
        "assignments": history["assignments"],
        "safety_checks": history["safety_checks"],
        "repairs": history["repairs"],
    }


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(
    device_id: int, session: AsyncSession = Depends(get_db_session)
) -> None:
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    await session.delete(device)
    await session.commit()


__all__ = ["router"]
