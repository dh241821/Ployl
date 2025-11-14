"""Pydantic models for API serialization."""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: str
    exp: datetime


class BenutzerBase(BaseModel):
    username: str
    full_name: str
    role: str
    email: Optional[str]


class BenutzerRead(BenutzerBase):
    id: int

    class Config:
        orm_mode = True


class BenutzerCreate(BenutzerBase):
    password: str = Field(min_length=6)


class StandortRead(BaseModel):
    id: int
    land: Optional[str]
    bereich: Optional[str]
    bezirk: Optional[str]
    bezirksstelle: Optional[str]
    ortsstelle: Optional[str]
    beschreibung: Optional[str]

    class Config:
        orm_mode = True


class KategorieRead(BaseModel):
    id: int
    name: str
    typ: str

    class Config:
        orm_mode = True


class ProduktComponentRead(BaseModel):
    id: int
    name: str
    hersteller: Optional[str]
    seriennummer: Optional[str]
    bemerkung: Optional[str]

    class Config:
        orm_mode = True


class ProduktRead(BaseModel):
    id: int
    name: str
    typ: Optional[str]
    seriennummer: str
    status: str
    interne_kennung: Optional[str]
    anschaffungsdatum: Optional[date]
    stk_intervall: Optional[int]
    mtk_intervall: Optional[int]
    letzte_stk: Optional[date]
    letzte_mtk: Optional[date]
    standort: Optional[StandortRead]
    kategorie: Optional[KategorieRead]
    komponenten: List[ProduktComponentRead] = []

    class Config:
        orm_mode = True


class DashboardKPI(BaseModel):
    due_products: int
    in_repair: int
    expired_materials: int
    low_stock_materials: int
    maintenance_due_within_30_days: int


class DashboardChart(BaseModel):
    labels: List[str]
    values: List[int]


class DashboardResponse(BaseModel):
    kpis: DashboardKPI
    product_status_chart: DashboardChart
    category_cost_chart: DashboardChart
    repair_frequency_chart: DashboardChart


class MaintenanceReminder(BaseModel):
    produkt_id: int
    produkt_name: str
    due_date: date
    typ: str


class NotificationResult(BaseModel):
    recipients: List[str]
    reminders: List[MaintenanceReminder]


class ScanResult(BaseModel):
    produkt: Optional[ProduktRead]
    material_bestand: Optional[int]
    message: str


class RepairCostTrend(BaseModel):
    month: str
    total_cost: float
