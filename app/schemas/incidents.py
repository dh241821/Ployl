from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from app.core.enums import DifficultyLevel, IncidentStatus
from app.schemas.common import Timestamped


class IncidentBase(BaseModel):
    incident_code: str = Field(..., max_length=40)
    title: str = Field(..., max_length=120)
    description: str | None = None
    incident_type: str = Field(..., max_length=80)
    difficulty: DifficultyLevel = DifficultyLevel.BASIC
    location_name: str | None = Field(default=None, max_length=120)
    latitude: float | None = None
    longitude: float | None = None
    expected_patients: int | None = Field(default=None, ge=0)


class IncidentCreate(IncidentBase):
    pass


class IncidentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    description: str | None = None
    difficulty: DifficultyLevel | None = None
    status: IncidentStatus | None = None
    location_name: str | None = Field(default=None, max_length=120)
    latitude: float | None = None
    longitude: float | None = None
    expected_patients: int | None = Field(default=None, ge=0)


class IncidentAssignmentRead(BaseModel):
    id: int
    vehicle_id: int
    incident_id: int
    dispatched_at: datetime | None
    acknowledged_at: datetime | None
    arrival_at_scene: datetime | None
    departed_scene_at: datetime | None
    breakdown_reported: bool

    class Config:
        orm_mode = True


class IncidentRead(IncidentBase, Timestamped):
    id: int
    status: IncidentStatus
    assignments: List[IncidentAssignmentRead] = []
