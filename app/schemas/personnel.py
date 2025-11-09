from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from app.schemas.common import Timestamped


class PersonnelBase(BaseModel):
    name: str = Field(..., max_length=120)
    role: str = Field(..., max_length=80)
    skills: List[str] | None = None
    organization: str | None = Field(default=None, max_length=120)


class PersonnelCreate(PersonnelBase):
    pass


class PersonnelUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    role: str | None = Field(default=None, max_length=80)
    skills: List[str] | None = None
    organization: str | None = Field(default=None, max_length=120)


class PersonnelRead(PersonnelBase, Timestamped):
    id: int
