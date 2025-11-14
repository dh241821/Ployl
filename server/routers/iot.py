"""IoT sensor endpoints."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_session
from ..models import SensorDevice
from ..schemas import SensorAlert, SensorDeviceCreate, SensorDeviceRead, SensorReadingCreate
from ..services.iot import IoTService

router = APIRouter(prefix="/api/iot", tags=["iot"])


def _to_schema(device: SensorDevice) -> SensorDeviceRead:
    metadata = {}
    if device.details:
        try:
            metadata = json.loads(device.details)
        except json.JSONDecodeError:  # pragma: no cover - defensive
            metadata = {}
    return SensorDeviceRead(id=device.id, name=device.name, location=device.location, sensor_type=device.sensor_type, metadata=metadata)


@router.post("/devices", response_model=SensorDeviceRead)
def register_device(
    request: SensorDeviceCreate,
    session: Session = Depends(get_session),
    _user=Depends(require_admin),
) -> SensorDeviceRead:
    service = IoTService(session)
    device = service.register_device(request.name, request.sensor_type, request.location, request.metadata)
    return _to_schema(device)


@router.get("/devices", response_model=list[SensorDeviceRead])
def list_devices(session: Session = Depends(get_session), _user=Depends(get_current_user)) -> list[SensorDeviceRead]:
    service = IoTService(session)
    return [_to_schema(device) for device in service.list_devices()]


@router.post("/devices/{device_id}/readings", response_model=SensorAlert, status_code=status.HTTP_201_CREATED)
def record_reading(
    device_id: int,
    request: SensorReadingCreate,
    session: Session = Depends(get_session),
    _user=Depends(get_current_user),
) -> SensorAlert:
    service = IoTService(session)
    device = session.query(SensorDevice).filter(SensorDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    service.record_reading(device_id, request.metric, request.value, request.unit, request.recorded_at)
    alerts = service.generate_alerts(device_id)
    if alerts:
        alert = alerts[0]
        return SensorAlert(**alert)
    return SensorAlert(metric=request.metric, value=request.value, threshold=request.value, message="OK")


@router.get("/devices/{device_id}/alerts", response_model=list[SensorAlert])
def get_alerts(
    device_id: int,
    session: Session = Depends(get_session),
    _user=Depends(get_current_user),
) -> list[SensorAlert]:
    service = IoTService(session)
    return [SensorAlert(**alert) for alert in service.generate_alerts(device_id)]

