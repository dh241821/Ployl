"""Geo tracking services for vehicles."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from geopy.distance import geodesic
from sqlalchemy.orm import Session

from ..models import Fahrzeug, FahrzeugPosition


class GeoTrackingService:
    """Persist positions and compute derived route analytics."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def record_position(
        self,
        *,
        fahrzeug_id: int,
        latitude: float,
        longitude: float,
        accuracy: Optional[float],
        zeitstempel: Optional[datetime] = None,
    ) -> FahrzeugPosition:
        position = FahrzeugPosition(
            fahrzeug_id=fahrzeug_id,
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            zeitstempel=zeitstempel or datetime.utcnow(),
        )
        self.session.add(position)
        self.session.flush()
        return position

    def vehicle_route(self, fahrzeug_id: int, limit: int = 250) -> Tuple[List[FahrzeugPosition], float]:
        positions = (
            self.session.query(FahrzeugPosition)
            .filter(FahrzeugPosition.fahrzeug_id == fahrzeug_id)
            .order_by(FahrzeugPosition.zeitstempel.desc())
            .limit(limit)
            .all()
        )
        positions = list(reversed(positions))

        total_distance = 0.0
        for prev, curr in zip(positions, positions[1:]):
            total_distance += geodesic((prev.latitude, prev.longitude), (curr.latitude, curr.longitude)).kilometers

        return positions, total_distance

    def ensure_vehicle_exists(self, fahrzeug_id: int) -> Fahrzeug:
        fahrzeug = self.session.query(Fahrzeug).filter(Fahrzeug.id == fahrzeug_id).first()
        if not fahrzeug:
            raise ValueError(f"Fahrzeug {fahrzeug_id} existiert nicht")
        return fahrzeug
