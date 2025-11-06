from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    func,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Vehicle(Base):
    __tablename__ = "vehicle"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    radio_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    in_service_since: Mapped[Optional[date]] = mapped_column(Date())
    out_of_service: Mapped[Optional[date]] = mapped_column(Date())

    assignments: Mapped[list["DeviceAssignment"]] = relationship(back_populates="vehicle")


class DeviceType(Base):
    __tablename__ = "device_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(128))
    model: Mapped[Optional[str]] = mapped_column(String(128))
    default_mtk_interval_days: Mapped[Optional[int]] = mapped_column(Integer)
    default_stk_interval_days: Mapped[Optional[int]] = mapped_column(Integer)
    is_composite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    component_types: Mapped[list["ComponentType"]] = relationship(
        back_populates="device_type", cascade="all, delete-orphan"
    )
    devices: Mapped[list["Device"]] = relationship(back_populates="device_type")


class ComponentType(Base):
    __tablename__ = "component_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_type_id: Mapped[int] = mapped_column(ForeignKey("device_type.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    device_type: Mapped[DeviceType] = relationship(back_populates="component_types")
    components: Mapped[list["DeviceComponent"]] = relationship(back_populates="component_type")

    __table_args__ = (UniqueConstraint("device_type_id", "name", name="uq_component_type"),)


class Device(Base):
    __tablename__ = "device"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inventory_number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_type_id: Mapped[int] = mapped_column(ForeignKey("device_type.id"))
    serial_number: Mapped[Optional[str]] = mapped_column(String(128))
    purchase_date: Mapped[Optional[date]] = mapped_column(Date())
    status: Mapped[str] = mapped_column(String(32), default="aktiv", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text())

    device_type: Mapped[DeviceType] = relationship(back_populates="devices")
    components: Mapped[list["DeviceComponent"]] = relationship(
        back_populates="device", cascade="all, delete-orphan"
    )
    assignments: Mapped[list["DeviceAssignment"]] = relationship(back_populates="device")
    safety_checks: Mapped[list["SafetyCheck"]] = relationship(back_populates="device")
    repairs: Mapped[list["RepairLog"]] = relationship(back_populates="device")


class DeviceComponent(Base):
    __tablename__ = "device_component"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("device.id", ondelete="CASCADE"))
    component_type_id: Mapped[int] = mapped_column(ForeignKey("component_type.id"))
    serial_number: Mapped[Optional[str]] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="aktiv", nullable=False)

    device: Mapped[Device] = relationship(back_populates="components")
    component_type: Mapped[ComponentType] = relationship(back_populates="components")
    assignments: Mapped[list["DeviceAssignment"]] = relationship(back_populates="component")
    safety_checks: Mapped[list["SafetyCheck"]] = relationship(back_populates="component")
    repairs: Mapped[list["RepairLog"]] = relationship(back_populates="component")

    __table_args__ = (
        UniqueConstraint("device_id", "component_type_id", name="uq_device_component_type"),
    )

    @property
    def component_type_name(self) -> Optional[str]:
        return self.component_type.name if self.component_type else None


class DeviceAssignment(Base):
    __tablename__ = "device_assignment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("device.id"))
    component_id: Mapped[Optional[int]] = mapped_column(ForeignKey("device_component.id"))
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicle.id"))
    assigned_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    assigned_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[Optional[str]] = mapped_column(String(128))
    notes: Mapped[Optional[str]] = mapped_column(Text())

    device: Mapped[Device] = relationship(back_populates="assignments")
    component: Mapped[Optional[DeviceComponent]] = relationship(back_populates="assignments")
    vehicle: Mapped[Vehicle] = relationship(back_populates="assignments")


class SafetyCheck(Base):
    __tablename__ = "safety_check"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("device.id"))
    component_id: Mapped[Optional[int]] = mapped_column(ForeignKey("device_component.id"))
    check_type: Mapped[str] = mapped_column(String(3))
    performed_on: Mapped[date] = mapped_column(Date(), nullable=False)
    due_on: Mapped[Optional[date]] = mapped_column(Date())
    performed_by: Mapped[Optional[str]] = mapped_column(String(128))
    result: Mapped[Optional[str]] = mapped_column(String(32))
    certificate_path: Mapped[Optional[str]] = mapped_column(String(512))
    notes: Mapped[Optional[str]] = mapped_column(Text())

    device: Mapped[Device] = relationship(back_populates="safety_checks")
    component: Mapped[Optional[DeviceComponent]] = relationship(back_populates="safety_checks")
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="safety_check", cascade="all, delete-orphan"
    )


class RepairLog(Base):
    __tablename__ = "repair_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("device.id"))
    component_id: Mapped[Optional[int]] = mapped_column(ForeignKey("device_component.id"))
    reported_on: Mapped[date] = mapped_column(Date(), nullable=False)
    repaired_on: Mapped[Optional[date]] = mapped_column(Date())
    reported_issue: Mapped[str] = mapped_column(Text(), nullable=False)
    repair_action: Mapped[Optional[str]] = mapped_column(Text())
    repaired_by: Mapped[Optional[str]] = mapped_column(String(128))
    cost: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    document_path: Mapped[Optional[str]] = mapped_column(String(512))
    notes: Mapped[Optional[str]] = mapped_column(Text())

    device: Mapped[Device] = relationship(back_populates="repairs")
    component: Mapped[Optional[DeviceComponent]] = relationship(back_populates="repairs")
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="repair", cascade="all, delete-orphan"
    )


class Attachment(Base):
    __tablename__ = "attachment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repair_id: Mapped[Optional[int]] = mapped_column(ForeignKey("repair_log.id", ondelete="CASCADE"))
    safety_check_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("safety_check.id", ondelete="CASCADE")
    )
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(256))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    repair: Mapped[Optional[RepairLog]] = relationship(back_populates="attachments")
    safety_check: Mapped[Optional[SafetyCheck]] = relationship(back_populates="attachments")


@event.listens_for(DeviceAssignment, "before_insert")
def set_assignment_start(mapper, connection, target: DeviceAssignment) -> None:
    if target.assigned_from is None:
        target.assigned_from = datetime.utcnow()


@event.listens_for(SafetyCheck, "before_insert")
def set_due_on(mapper, connection, target: SafetyCheck) -> None:
    if target.due_on is not None:
        return

    device_type_id = connection.execute(
        select(Device.device_type_id).where(Device.id == target.device_id)
    ).scalar_one_or_none()
    if device_type_id is None:
        return

    device_type_row = connection.execute(
        select(
            DeviceType.default_mtk_interval_days, DeviceType.default_stk_interval_days
        ).where(DeviceType.id == device_type_id)
    ).one()

    interval_days: Optional[int]
    if target.check_type.upper() == "MTK":
        interval_days = device_type_row.default_mtk_interval_days
    else:
        interval_days = device_type_row.default_stk_interval_days

    if interval_days:
        target.due_on = target.performed_on + timedelta(days=interval_days)


__all__ = [
    "Vehicle",
    "DeviceType",
    "ComponentType",
    "Device",
    "DeviceComponent",
    "DeviceAssignment",
    "SafetyCheck",
    "RepairLog",
    "Attachment",
]
