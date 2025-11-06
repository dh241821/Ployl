from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VehicleBase(BaseModel):
    radio_id: str
    vehicle_type: str
    name: str
    in_service_since: Optional[date] = None
    out_of_service: Optional[date] = None


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    radio_id: Optional[str] = None
    vehicle_type: Optional[str] = None
    name: Optional[str] = None
    in_service_since: Optional[date] = None
    out_of_service: Optional[date] = None


class VehicleRead(ORMBase, VehicleBase):
    id: int


class ComponentTypeCreate(BaseModel):
    name: str


class ComponentTypeRead(ORMBase):
    id: int
    name: str


class DeviceTypeBase(BaseModel):
    name: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    default_mtk_interval_days: Optional[int] = Field(default=None, ge=1)
    default_stk_interval_days: Optional[int] = Field(default=None, ge=1)
    is_composite: bool = False


class DeviceTypeCreate(DeviceTypeBase):
    components: list[ComponentTypeCreate] = Field(default_factory=list)


class DeviceTypeUpdate(BaseModel):
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    default_mtk_interval_days: Optional[int] = Field(default=None, ge=1)
    default_stk_interval_days: Optional[int] = Field(default=None, ge=1)
    is_composite: Optional[bool] = None


class DeviceTypeRead(ORMBase, DeviceTypeBase):
    id: int
    components: list[ComponentTypeRead] = Field(default_factory=list)


class DeviceBase(BaseModel):
    inventory_number: str
    device_type_id: int
    serial_number: Optional[str] = None
    purchase_date: Optional[date] = None
    status: str = "aktiv"
    notes: Optional[str] = None


class DeviceCreate(DeviceBase):
    component_serials: dict[int, str | None] = Field(default_factory=dict)


class DeviceUpdate(BaseModel):
    serial_number: Optional[str] = None
    purchase_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class DeviceComponentRead(ORMBase):
    id: int
    component_type_id: int
    component_type_name: str
    serial_number: Optional[str]
    status: str


class DeviceRead(ORMBase, DeviceBase):
    id: int
    device_type: DeviceTypeRead
    components: list[DeviceComponentRead] = Field(default_factory=list)


class AssignmentBase(BaseModel):
    device_id: int
    vehicle_id: int
    component_id: Optional[int] = None
    assigned_from: Optional[datetime] = None
    assigned_to: Optional[datetime] = None
    assigned_by: Optional[str] = None
    notes: Optional[str] = None


class AssignmentCreate(AssignmentBase):
    pass


class AssignmentRead(ORMBase, AssignmentBase):
    id: int


class SafetyCheckBase(BaseModel):
    device_id: int
    component_id: Optional[int] = None
    check_type: str
    performed_on: date
    due_on: Optional[date] = None
    performed_by: Optional[str] = None
    result: Optional[str] = None
    certificate_path: Optional[str] = None
    notes: Optional[str] = None


class SafetyCheckCreate(SafetyCheckBase):
    attachments: list["AttachmentCreate"] = Field(default_factory=list)


class SafetyCheckRead(ORMBase, SafetyCheckBase):
    id: int
    attachments: list["AttachmentRead"] = Field(default_factory=list)


class RepairLogBase(BaseModel):
    device_id: int
    component_id: Optional[int] = None
    reported_on: date
    repaired_on: Optional[date] = None
    reported_issue: str
    repair_action: Optional[str] = None
    repaired_by: Optional[str] = None
    cost: Optional[float] = Field(default=None, ge=0)
    document_path: Optional[str] = None
    notes: Optional[str] = None


class RepairLogCreate(RepairLogBase):
    attachments: list["AttachmentCreate"] = Field(default_factory=list)


class RepairLogRead(ORMBase, RepairLogBase):
    id: int
    attachments: list["AttachmentRead"] = Field(default_factory=list)


class RepairLogUpdate(BaseModel):
    component_id: Optional[int] = None
    reported_on: Optional[date] = None
    repaired_on: Optional[date] = None
    reported_issue: Optional[str] = None
    repair_action: Optional[str] = None
    repaired_by: Optional[str] = None
    cost: Optional[float] = Field(default=None, ge=0)
    document_path: Optional[str] = None
    notes: Optional[str] = None


class AttachmentBase(BaseModel):
    file_path: str
    description: Optional[str] = None


class AttachmentCreate(AttachmentBase):
    pass


class AttachmentRead(ORMBase, AttachmentBase):
    id: int
    uploaded_at: datetime


class MaintenanceWindow(BaseModel):
    device_id: int
    device_inventory_number: str
    check_type: str
    due_on: date
    days_until_due: int
    component_id: Optional[int] = None
    component_name: Optional[str] = None


class MaintenanceAlertRead(ORMBase):
    id: int
    device_id: int
    component_id: Optional[int] = None
    check_type: str
    due_on: date
    severity: str
    days_until_due: int
    message: Optional[str] = None
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class MaintenanceAlertUpdate(BaseModel):
    acknowledged: Optional[bool] = None
    resolve: Optional[bool] = None


SafetyCheckRead.update_forward_refs()
RepairLogRead.update_forward_refs()
