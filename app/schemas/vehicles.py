from __future__ import annotations

from datetime import datetime
from typing import Any, List

from pydantic import BaseModel, Field

from app.core.enums import VehicleStatus, VehicleType
from app.schemas.common import ORMModel, StatusLog, Timestamped


class CrewMemberBase(BaseModel):
    name: str = Field(..., max_length=120)
    role: str = Field(..., max_length=80)
    qualifications: List[str] | None = None
    is_active: bool = True


class CrewMemberCreate(CrewMemberBase):
    pass


class CrewMemberUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, max_length=80)
    qualifications: List[str] | None = None
    is_active: bool | None = None


class CrewMemberRead(CrewMemberBase, Timestamped):
    id: int
    vehicle_id: int | None


class VehicleBase(BaseModel):
    callsign: str = Field(..., max_length=50)
    vehicle_type: VehicleType
    status: VehicleStatus = VehicleStatus.OFF_DUTY
    location_name: str | None = Field(default=None, max_length=120)
    latitude: float | None = None
    longitude: float | None = None
    minutes_to_dispatch_site: int | None = Field(default=None, ge=0)
    kilometers_to_dispatch_site: float | None = Field(default=None, ge=0)
    minutes_to_destination: int | None = Field(default=None, ge=0)
    kilometers_to_destination: float | None = Field(default=None, ge=0)
    is_operational: bool = True
    notes: str | None = None


class VehicleCreate(VehicleBase):
    crew: List[CrewMemberCreate] | None = None


class VehicleUpdate(BaseModel):
    status: VehicleStatus | None = None
    location_name: str | None = Field(default=None, max_length=120)
    latitude: float | None = None
    longitude: float | None = None
    minutes_to_dispatch_site: int | None = Field(default=None, ge=0)
    kilometers_to_dispatch_site: float | None = Field(default=None, ge=0)
    minutes_to_destination: int | None = Field(default=None, ge=0)
    kilometers_to_destination: float | None = Field(default=None, ge=0)
    is_operational: bool | None = None
    notes: str | None = None


class VehicleRead(VehicleBase, Timestamped):
    id: int
    crew: List[CrewMemberRead] | None = None
    status_history: List[StatusLog] | None = None


class VehicleStatusChange(BaseModel):
    status: VehicleStatus
    note: str | None = None
    timestamp: datetime | None = None
    payload: dict[str, Any] | None = None
