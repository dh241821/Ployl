from __future__ import annotations

import csv
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.entities import Device, DeviceComponent, DeviceType
from ..schemas.base import DeviceCreate, DeviceRead, DeviceUpdate
from ..services.device_service import create_device, get_device_history, get_devices
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
async def list_devices(
    category_id: int | None = None,
    device_type_id: int | None = None,
    status: str | None = None,
    location_id: int | None = None,
    assigned: bool | None = None,
    search: str | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> list[Device]:
    devices = await get_devices(
        session,
        category_id=category_id,
        device_type_id=device_type_id,
        status=status,
        location_id=location_id,
        assigned=assigned,
        search=search,
    )
    return devices


@router.get("/export", response_class=StreamingResponse)
async def export_devices(
    category_id: int | None = None,
    device_type_id: int | None = None,
    status: str | None = None,
    location_id: int | None = None,
    assigned: bool | None = None,
    search: str | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    devices = await get_devices(
        session,
        category_id=category_id,
        device_type_id=device_type_id,
        status=status,
        location_id=location_id,
        assigned=assigned,
        search=search,
    )

    def iter_rows():
        header = [
            "Inventarnummer",
            "Produkt",
            "Kategorie",
            "Seriennummer",
            "Status",
            "Standort",
        ]
        buffer = StringIO()
        writer = csv.writer(buffer, delimiter=";")
        writer.writerow(header)
        yield buffer.getvalue()

        for device in devices:
            buffer = StringIO()
            writer = csv.writer(buffer, delimiter=";")
            device_type = device.device_type.name if device.device_type else ""
            category = (
                device.device_type.category.name
                if device.device_type and device.device_type.category
                else ""
            )
            assignment = device.active_assignment
            location = ""
            if assignment and assignment.vehicle:
                vehicle = assignment.vehicle
                location = (
                    f"{vehicle.radio_id} ({vehicle.vehicle_type})"
                    if vehicle.vehicle_type
                    else vehicle.radio_id
                )
            writer.writerow(
                [
                    device.inventory_number,
                    device_type,
                    category,
                    device.serial_number or "",
                    device.status or "",
                    location,
                ]
            )
            yield buffer.getvalue()

    headers = {
        "Content-Disposition": "attachment; filename=medizingeraete.csv",
    }
    return StreamingResponse(iter_rows(), media_type="text/csv", headers=headers)


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
