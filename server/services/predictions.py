"""Predictive analytics helpers for inventory forecasting."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from ..config import settings
from ..models import InventoryForecast, Material


class PredictionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def refresh_inventory_forecasts(self) -> list[InventoryForecast]:
        horizon = settings.prediction_horizon_days
        forecasts: list[InventoryForecast] = []
        today = date.today()
        materials = self.session.query(Material).all()
        for material in materials:
            if material.soll_bestand is None or material.soll_bestand == 0:
                continue
            deficit = max(material.soll_bestand - material.ist_bestand, 0)
            probability = min(deficit / material.soll_bestand, 1)
            order_in_days = max(int((1 - probability) * horizon), 0)
            recommended = today + timedelta(days=order_in_days)
            forecast = (
                self.session.query(InventoryForecast)
                .filter(
                    InventoryForecast.material_id == material.id,
                    InventoryForecast.horizon_days == horizon,
                )
                .first()
            )
            if not forecast:
                forecast = InventoryForecast(material_id=material.id, horizon_days=horizon)
            forecast.predicted_on = today
            forecast.stockout_probability = round(probability, 3)
            forecast.recommended_order_date = recommended
            forecast.model_version = settings.maintenance_model_version
            self.session.add(forecast)
            forecasts.append(forecast)
        self.session.commit()
        return forecasts

