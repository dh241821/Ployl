from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..database import AsyncSessionFactory
from ..models.entities import (
    Device,
    DeviceAssignment,
    DeviceCategory,
    DeviceComponent,
    DeviceType,
    RepairLog,
    SafetyCheck,
    Vehicle,
)

FRONTEND_DIR = Path(__file__).resolve().parent
STATIC_DIR = FRONTEND_DIR / "static"
TEMPLATES = Jinja2Templates(directory=str(FRONTEND_DIR / "templates"))

router = APIRouter(include_in_schema=False)


async def _load_devices(session):
    stmt = (
        select(Device)
        .options(
            selectinload(Device.device_type).selectinload(DeviceType.category),
            selectinload(Device.components).selectinload(DeviceComponent.component_type),
        )
        .order_by(Device.inventory_number)
    )
    result = await session.execute(stmt)
    return list(result.scalars().unique())


@router.get("/", response_class=HTMLResponse)
async def overview(request: Request) -> HTMLResponse:
    async with AsyncSessionFactory() as session:
        vehicles = list(
            (
                await session.execute(select(Vehicle).order_by(Vehicle.radio_id))
            ).scalars()
        )
        assignments = list(
            (
                await session.execute(
                    select(DeviceAssignment)
                    .where(DeviceAssignment.assigned_to.is_(None))
                    .options(
                        selectinload(DeviceAssignment.device)
                        .selectinload(Device.device_type)
                        .selectinload(DeviceType.category)
                    )
                    .options(selectinload(DeviceAssignment.vehicle))
                )
            ).scalars()
        )
        devices = await _load_devices(session)

    return TEMPLATES.TemplateResponse(
        "overview.html",
        {
            "request": request,
            "app_title": getattr(request.app, "title", "Ployl"),
            "page": "overview",
            "vehicles": vehicles,
            "assignments": assignments,
            "devices": devices,
        },
    )


@router.get("/devices", response_class=HTMLResponse)
async def devices_page(request: Request) -> HTMLResponse:
    async with AsyncSessionFactory() as session:
        categories = list(
            (
                await session.execute(select(DeviceCategory).order_by(DeviceCategory.name))
            ).scalars()
        )
        device_types = list(
            (
                await session.execute(
                    select(DeviceType)
                    .options(selectinload(DeviceType.category))
                    .options(selectinload(DeviceType.component_types))
                    .order_by(DeviceType.name)
                )
            ).scalars().unique()
        )
        devices = await _load_devices(session)

    return TEMPLATES.TemplateResponse(
        "devices.html",
        {
            "request": request,
            "app_title": getattr(request.app, "title", "Ployl"),
            "page": "devices",
            "categories": categories,
            "device_types": device_types,
            "devices": devices,
        },
    )


@router.get("/devices/{device_id}", response_class=HTMLResponse)
async def device_detail(request: Request, device_id: int) -> HTMLResponse:
    async with AsyncSessionFactory() as session:
        device = await session.get(
            Device,
            device_id,
            options=[
                selectinload(Device.device_type).selectinload(DeviceType.category),
                selectinload(Device.components).selectinload(DeviceComponent.component_type),
            ],
        )
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        history_assignments = list(
            (
                await session.execute(
                    select(DeviceAssignment)
                    .where(DeviceAssignment.device_id == device_id)
                    .order_by(DeviceAssignment.assigned_from.desc())
                    .options(selectinload(DeviceAssignment.vehicle))
                    .options(selectinload(DeviceAssignment.component))
                )
            ).scalars()
        )
        checks = list(
            (
                await session.execute(
                    select(SafetyCheck)
                    .where(SafetyCheck.device_id == device_id)
                    .order_by(SafetyCheck.performed_on.desc())
                    .options(selectinload(SafetyCheck.attachments))
                )
            ).scalars()
        )
        repairs = list(
            (
                await session.execute(
                    select(RepairLog)
                    .where(RepairLog.device_id == device_id)
                    .order_by(RepairLog.reported_on.desc())
                    .options(selectinload(RepairLog.attachments))
                )
            ).scalars()
        )
        vehicles = list(
            (
                await session.execute(select(Vehicle).order_by(Vehicle.radio_id))
            ).scalars()
        )

    return TEMPLATES.TemplateResponse(
        "device_detail.html",
        {
            "request": request,
            "app_title": getattr(request.app, "title", "Ployl"),
            "page": "device-detail",
            "title": device.inventory_number,
            "device": device,
            "assignments": history_assignments,
            "checks": checks,
            "repairs": repairs,
            "now": datetime.utcnow,
            "vehicles": vehicles,
        },
    )


@router.get("/repairs", response_class=HTMLResponse)
async def repairs_page(request: Request) -> HTMLResponse:
    async with AsyncSessionFactory() as session:
        categories = list(
            (
                await session.execute(select(DeviceCategory).order_by(DeviceCategory.name))
            ).scalars()
        )
        devices = await _load_devices(session)

    return TEMPLATES.TemplateResponse(
        "repairs.html",
        {
            "request": request,
            "app_title": getattr(request.app, "title", "Ployl"),
            "page": "repairs",
            "categories": categories,
            "devices": devices,
        },
    )


@router.get("/checks/{check_type}", response_class=HTMLResponse)
async def checks_page(request: Request, check_type: str) -> HTMLResponse:
    check_type = check_type.upper()
    if check_type not in {"MTK", "STK"}:
        raise HTTPException(status_code=404, detail="Unknown check type")

    async with AsyncSessionFactory() as session:
        checks = list(
            (
                await session.execute(
                    select(SafetyCheck)
                    .where(SafetyCheck.check_type == check_type)
                    .order_by(SafetyCheck.performed_on.desc())
                    .options(selectinload(SafetyCheck.attachments))
                )
            ).scalars()
        )

    return TEMPLATES.TemplateResponse(
        "checks.html",
        {
            "request": request,
            "app_title": getattr(request.app, "title", "Ployl"),
            "page": f"checks-{check_type.lower()}",
            "title": f"{check_type} Kontrollen",
            "check_type": check_type,
            "checks": checks,
        },
    )


__all__ = ["router", "STATIC_DIR", "TEMPLATES"]
