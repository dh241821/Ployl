from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field

from app.schemas.common import Timestamped


class HospitalBase(BaseModel):
    name: str = Field(..., max_length=120)
    location_name: str | None = Field(default=None, max_length=120)
    latitude: float | None = None
    longitude: float | None = None
    max_capacity: int | None = Field(default=None, ge=0)
    specialty_capacity: Dict[str, int] | None = None
    capabilities: List[str] | None = None


class HospitalCreate(HospitalBase):
    pass


class HospitalUpdate(BaseModel):
    location_name: str | None = Field(default=None, max_length=120)
    latitude: float | None = None
    longitude: float | None = None
    max_capacity: int | None = Field(default=None, ge=0)
    specialty_capacity: Dict[str, int] | None = None
    capabilities: List[str] | None = None


class HospitalRead(HospitalBase, Timestamped):
    id: int
