from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
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
from ..services.device_service import get_upcoming_maintenance

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
        open_repairs = await session.execute(
            select(func.count()).select_from(RepairLog).where(RepairLog.repaired_on.is_(None))
        )
        maintenance_windows = await get_upcoming_maintenance(session)

    overview_data = {
        "vehicles": [
            {
                "id": vehicle.id,
                "radio_id": vehicle.radio_id,
                "vehicle_type": vehicle.vehicle_type,
                "in_service_since": vehicle.in_service_since.isoformat()
                if vehicle.in_service_since
                else None,
                "out_of_service": vehicle.out_of_service.isoformat()
                if vehicle.out_of_service
                else None,
            }
            for vehicle in vehicles
        ],
        "assignments": [
            {
                "id": assignment.id,
                "vehicle_id": assignment.vehicle_id,
                "device_id": assignment.device_id,
                "assigned_from": assignment.assigned_from.isoformat()
                if assignment.assigned_from
                else None,
                "component_id": assignment.component_id,
            }
            for assignment in assignments
        ],
        "devices": [
            {
                "id": device.id,
                "inventory_number": device.inventory_number,
                "serial_number": device.serial_number,
                "status": device.status,
                "device_type": {
                    "name": device.device_type.name,
                    "category": device.device_type.category.name
                    if device.device_type and device.device_type.category
                    else None,
                },
            }
            for device in devices
        ],
    }

    metrics = {
        "total_devices": len(devices),
        "active_devices": sum(1 for device in devices if (device.status or "").lower() == "aktiv"),
        "active_assignments": len({assignment.device_id for assignment in assignments}),
        "open_repairs": open_repairs.scalar_one(),
        "mtk_due": sum(
            1
            for window in maintenance_windows
            if (window.check_type or "").lower() == "mtk"
        ),
        "stk_due": sum(
            1
            for window in maintenance_windows
            if (window.check_type or "").lower() == "stk"
        ),
    }

    return TEMPLATES.TemplateResponse(
        "overview.html",
        {
            "request": request,
            "app_title": getattr(request.app, "title", "Ployl"),
            "page": "overview",
            "vehicles": vehicles,
            "assignments": assignments,
            "devices": devices,
            "overview_data": overview_data,
            "metrics": metrics,
        },
    )


@router.get("/ui/devices", response_class=HTMLResponse)
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

    devices_data = {
        "categories": [
            {"id": category.id, "name": category.name} for category in categories
        ],
        "device_types": [
            {
                "id": product.id,
                "name": product.name,
                "manufacturer": product.manufacturer,
                "model": product.model,
                "category_id": product.category.id if product.category else None,
                "is_composite": product.is_composite,
                "components": [
                    {"id": component.id, "name": component.name}
                    for component in product.components
                ],
            }
            for product in device_types
        ],
        "devices": [
            {
                "id": device.id,
                "inventory_number": device.inventory_number,
                "serial_number": device.serial_number,
                "status": device.status,
                "purchase_date": device.purchase_date.isoformat()
                if device.purchase_date
                else None,
                "notes": device.notes,
                "device_type_id": device.device_type.id,
                "device_type_name": device.device_type.name,
                "category_id": device.device_type.category.id
                if device.device_type and device.device_type.category
                else None,
            }
            for device in devices
        ],
    }

    return TEMPLATES.TemplateResponse(
        "devices.html",
        {
            "request": request,
            "app_title": getattr(request.app, "title", "Ployl"),
            "page": "devices",
            "categories": categories,
            "device_types": device_types,
            "devices": devices,
            "devices_data": devices_data,
        },
    )


@router.get("/ui/devices/{device_id}", response_class=HTMLResponse)
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

    device_detail_data = {
        "device": {
            "id": device.id,
            "inventory_number": device.inventory_number,
            "status": device.status,
            "serial_number": device.serial_number,
            "device_type": {
                "name": device.device_type.name,
                "category": device.device_type.category.name
                if device.device_type and device.device_type.category
                else None,
            },
        },
        "assignments": [
            {
                "id": assignment.id,
                "vehicle_id": assignment.vehicle_id,
                "vehicle": assignment.vehicle.radio_id if assignment.vehicle else None,
                "assigned_from": assignment.assigned_from.isoformat()
                if assignment.assigned_from
                else None,
                "assigned_to": assignment.assigned_to.isoformat()
                if assignment.assigned_to
                else None,
            }
            for assignment in history_assignments
        ],
        "checks": [
            {
                "id": check.id,
                "check_type": check.check_type,
                "performed_on": check.performed_on.isoformat()
                if check.performed_on
                else None,
                "due_on": check.due_on.isoformat() if check.due_on else None,
                "result": check.result,
                "attachments": [
                    {
                        "id": attachment.id,
                        "file_path": attachment.file_path,
                        "description": attachment.description,
                    }
                    for attachment in check.attachments
                ],
            }
            for check in checks
        ],
        "repairs": [
            {
                "id": repair.id,
                "reported_on": repair.reported_on.isoformat()
                if repair.reported_on
                else None,
                "repaired_on": repair.repaired_on.isoformat()
                if repair.repaired_on
                else None,
                "reported_issue": repair.reported_issue,
                "repair_action": repair.repair_action,
                "attachments": [
                    {
                        "id": attachment.id,
                        "file_path": attachment.file_path,
                        "description": attachment.description,
                    }
                    for attachment in repair.attachments
                ],
            }
            for repair in repairs
        ],
        "vehicles": [
            {
                "id": vehicle.id,
                "radio_id": vehicle.radio_id,
                "vehicle_type": vehicle.vehicle_type,
            }
            for vehicle in vehicles
        ],
    }

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
            "device_detail_data": device_detail_data,
        },
    )


@router.get("/ui/repairs", response_class=HTMLResponse)
async def repairs_page(request: Request) -> HTMLResponse:
    async with AsyncSessionFactory() as session:
        categories = list(
            (
                await session.execute(select(DeviceCategory).order_by(DeviceCategory.name))
            ).scalars()
        )
        devices = await _load_devices(session)

    repairs_data = {
        "devices": [
            {
                "id": device.id,
                "inventory_number": device.inventory_number,
                "serial_number": device.serial_number,
                "device_type": {
                    "name": device.device_type.name,
                    "category_id": device.device_type.category.id
                    if device.device_type and device.device_type.category
                    else None,
                    "category": device.device_type.category.name
                    if device.device_type and device.device_type.category
                    else None,
                },
            }
            for device in devices
        ],
    }

    return TEMPLATES.TemplateResponse(
        "repairs.html",
        {
            "request": request,
            "app_title": getattr(request.app, "title", "Ployl"),
            "page": "repairs",
            "categories": categories,
            "devices": devices,
            "repairs_data": repairs_data,
        },
    )


@router.get("/ui/checks/{check_type}", response_class=HTMLResponse)
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
