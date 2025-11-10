from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from app.schemas.common import Timestamped


class PatientBase(BaseModel):
    incident_id: int
    identifier: str = Field(..., max_length=80)
    condition: str | None = Field(default=None, max_length=120)
    priority: str | None = Field(default=None, max_length=40)
    required_capabilities: List[str] | None = None


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    condition: str | None = Field(default=None, max_length=120)
    priority: str | None = Field(default=None, max_length=40)
    required_capabilities: List[str] | None = None


class PatientRead(PatientBase, Timestamped):
    id: int


class PatientTransportBase(BaseModel):
    patient_id: int
    vehicle_id: int
    hospital_id: int
    status: str = Field(default="assigned", max_length=40)


class PatientTransportCreate(PatientTransportBase):
    pass


class PatientTransportUpdate(BaseModel):
    status: str | None = Field(default=None, max_length=40)


class PatientTransportRead(PatientTransportBase, Timestamped):
    id: int
