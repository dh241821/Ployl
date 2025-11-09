from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.core.enums import VehicleStatus


class ORMModel(BaseModel):
    class Config:
        orm_mode = True


class Timestamped(ORMModel):
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StatusLog(ORMModel):
    id: int
    status: VehicleStatus
    note: str | None
    timestamp: datetime
    payload: dict[str, Any] | None
