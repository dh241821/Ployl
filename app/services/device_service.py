from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models.entities import (
    Attachment,
    ComponentType,
    Device,
    DeviceAssignment,
    DeviceComponent,
    DeviceType,
    RepairLog,
    SafetyCheck,
)
from ..schemas.base import (
    AssignmentCreate,
    DeviceCreate,
    DeviceTypeCreate,
    MaintenanceWindow,
    RepairLogCreate,
    SafetyCheckCreate,
    VehicleCreate,
)


async def create_vehicle(session: AsyncSession, payload: VehicleCreate) -> Vehicle:
    vehicle = Vehicle(**payload.dict())
    session.add(vehicle)
    await session.flush()
    return vehicle


async def create_device_type(
    session: AsyncSession, payload: DeviceTypeCreate
) -> DeviceType:
    device_type = DeviceType(
        name=payload.name,
        manufacturer=payload.manufacturer,
        model=payload.model,
        default_mtk_interval_days=payload.default_mtk_interval_days,
        default_stk_interval_days=payload.default_stk_interval_days,
        is_composite=payload.is_composite,
    )
    for component in payload.components:
        device_type.component_types.append(ComponentType(name=component.name))
    session.add(device_type)
    await session.flush()
    return device_type


async def create_device(session: AsyncSession, payload: DeviceCreate) -> Device:
    device = Device(
        inventory_number=payload.inventory_number,
        device_type_id=payload.device_type_id,
        serial_number=payload.serial_number,
        purchase_date=payload.purchase_date,
        status=payload.status,
        notes=payload.notes,
    )
    session.add(device)
    await session.flush()

    # Create components where applicable
    if payload.component_serials:
        component_types = await session.execute(
            select(ComponentType).where(ComponentType.device_type_id == payload.device_type_id)
        )
        for component_type in component_types.scalars():
            serial = payload.component_serials.get(component_type.id)
            device.components.append(
                DeviceComponent(
                    component_type_id=component_type.id,
                    serial_number=serial,
                )
            )
    await session.flush()
    return device


async def assign_device(session: AsyncSession, payload: AssignmentCreate) -> DeviceAssignment:
    # Close open assignment for same device/component
    existing_stmt = select(DeviceAssignment).where(
        DeviceAssignment.device_id == payload.device_id,
        DeviceAssignment.component_id == payload.component_id,
        DeviceAssignment.assigned_to.is_(None),
    )
    existing_assignment = await session.execute(existing_stmt)
    for assignment in existing_assignment.scalars():
        assignment.assigned_to = payload.assigned_from or datetime.utcnow()

    assignment = DeviceAssignment(**payload.dict())
    session.add(assignment)
    await session.flush()
    return assignment


async def create_safety_check(
    session: AsyncSession, payload: SafetyCheckCreate
) -> SafetyCheck:
    safety_check = SafetyCheck(
        device_id=payload.device_id,
        component_id=payload.component_id,
        check_type=payload.check_type,
        performed_on=payload.performed_on,
        due_on=payload.due_on,
        performed_by=payload.performed_by,
        result=payload.result,
        certificate_path=payload.certificate_path,
        notes=payload.notes,
    )
    session.add(safety_check)
    await session.flush()

    for attachment in payload.attachments:
        safety_check.attachments.append(
            Attachment(file_path=attachment.file_path, description=attachment.description)
        )

    await session.flush()
    return safety_check


async def create_repair_log(session: AsyncSession, payload: RepairLogCreate) -> RepairLog:
    repair = RepairLog(
        device_id=payload.device_id,
        component_id=payload.component_id,
        reported_on=payload.reported_on,
        repaired_on=payload.repaired_on,
        reported_issue=payload.reported_issue,
        repair_action=payload.repair_action,
        repaired_by=payload.repaired_by,
        cost=payload.cost,
        document_path=payload.document_path,
        notes=payload.notes,
    )
    session.add(repair)
    await session.flush()

    for attachment in payload.attachments:
        repair.attachments.append(
            Attachment(file_path=attachment.file_path, description=attachment.description)
        )

    await session.flush()
    return repair


async def get_upcoming_maintenance(
    session: AsyncSession,
    days: Optional[int] = None,
) -> list[MaintenanceWindow]:
    settings = get_settings()
    window = days or settings.maintenance_due_window_days

    stmt = (
        select(
            SafetyCheck.device_id,
            Device.inventory_number,
            SafetyCheck.check_type,
            SafetyCheck.due_on,
        )
        .join(Device, Device.id == SafetyCheck.device_id)
        .where(SafetyCheck.due_on.is_not(None))
        .where(SafetyCheck.due_on <= date.today() + timedelta(days=window))
        .order_by(SafetyCheck.due_on)
    )
    rows = await session.execute(stmt)

    results: list[MaintenanceWindow] = []
    for row in rows:
        if row.due_on is None:
            continue
        days_until_due = (row.due_on - date.today()).days
        results.append(
            MaintenanceWindow(
                device_id=row.device_id,
                device_inventory_number=row.inventory_number,
                check_type=row.check_type,
                due_on=row.due_on,
                days_until_due=days_until_due,
            )
        )
    return results


async def get_active_assignments(session: AsyncSession, vehicle_id: Optional[int] = None) -> list[DeviceAssignment]:
    stmt: Select[tuple[DeviceAssignment]] = select(DeviceAssignment).where(
        DeviceAssignment.assigned_to.is_(None)
    )
    if vehicle_id is not None:
        stmt = stmt.where(DeviceAssignment.vehicle_id == vehicle_id)
    stmt = stmt.order_by(DeviceAssignment.assigned_from.desc())

    result = await session.execute(stmt)
    return list(result.scalars())


async def get_device_history(session: AsyncSession, device_id: int) -> dict[str, list]:
    assignments = await session.execute(
        select(DeviceAssignment).where(DeviceAssignment.device_id == device_id).order_by(
            DeviceAssignment.assigned_from.desc()
        )
    )
    checks = await session.execute(
        select(SafetyCheck).where(SafetyCheck.device_id == device_id).order_by(
            SafetyCheck.performed_on.desc()
        )
    )
    repairs = await session.execute(
        select(RepairLog).where(RepairLog.device_id == device_id).order_by(
            RepairLog.reported_on.desc()
        )
    )
    return {
        "assignments": list(assignments.scalars()),
        "safety_checks": list(checks.scalars()),
        "repairs": list(repairs.scalars()),
    }


async def detach_device(
    session: AsyncSession, device_id: int, component_id: Optional[int] = None
) -> None:
    stmt = (
        update(DeviceAssignment)
        .where(
            DeviceAssignment.device_id == device_id,
            DeviceAssignment.component_id.is_(component_id),
            DeviceAssignment.assigned_to.is_(None),
        )
        .values(assigned_to=datetime.utcnow())
    )
    await session.execute(stmt)


__all__ = [
    "create_vehicle",
    "create_device_type",
    "create_device",
    "assign_device",
    "create_safety_check",
    "create_repair_log",
    "get_upcoming_maintenance",
    "get_active_assignments",
    "get_device_history",
    "detach_device",
]
