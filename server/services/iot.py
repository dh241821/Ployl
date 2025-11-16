"""IoT integration helpers for sensor ingestion and alerting."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List

from sqlalchemy.orm import Session

from ..config import settings
from ..models import SensorDevice, SensorReading


class IoTService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def register_device(self, name: str, sensor_type: str, location: str | None, metadata: Dict[str, object] | None) -> SensorDevice:
        device = SensorDevice(
            name=name,
            sensor_type=sensor_type,
            location=location,
            details=json.dumps(metadata or {}),
        )
        self.session.add(device)
        self.session.commit()
        self.session.refresh(device)
        return device

    def list_devices(self) -> List[SensorDevice]:
        return self.session.query(SensorDevice).order_by(SensorDevice.created_at.desc()).all()

    def record_reading(
        self,
        device_id: int,
        metric: str,
        value: float,
        unit: str | None,
        recorded_at: datetime | None,
    ) -> SensorReading:
        reading = SensorReading(
            device_id=device_id,
            metric=metric,
            value=value,
            unit=unit,
            recorded_at=recorded_at or datetime.utcnow(),
        )
        self.session.add(reading)
        self.session.commit()
        self.session.refresh(reading)
        return reading

    def generate_alerts(self, device_id: int) -> List[Dict[str, float | str]]:
        readings = (
            self.session.query(SensorReading)
            .filter(SensorReading.device_id == device_id)
            .order_by(SensorReading.recorded_at.desc())
            .limit(20)
            .all()
        )
        alerts: List[Dict[str, float | str]] = []
        for reading in readings:
            if reading.metric.lower().startswith("temp") and reading.value > settings.iot_temperature_threshold:
                alerts.append(
                    {
                        "metric": reading.metric,
                        "value": reading.value,
                        "threshold": settings.iot_temperature_threshold,
                        "message": "Temperatur über Schwellwert",
                    }
                )
            if reading.metric.lower().startswith("hum") and reading.value > settings.iot_humidity_threshold:
                alerts.append(
                    {
                        "metric": reading.metric,
                        "value": reading.value,
                        "threshold": settings.iot_humidity_threshold,
                        "message": "Luftfeuchtigkeit zu hoch",
                    }
                )
        return alerts

