"""Pydantic models for API serialization."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


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
    mfa_enabled: bool
    sso_subject: Optional[str]

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


class MaintenanceRecommendation(BaseModel):
    produkt_id: int
    produkt_name: str
    predicted_date: date
    window_start: date
    window_end: date
    confidence: float
    model_version: str
    data_points: int
    method: str


class CostEntryBase(BaseModel):
    produkt_id: Optional[int]
    fahrzeug_id: Optional[int]
    datum: date
    betrag: float
    typ: str
    beschreibung: Optional[str]
    quelle: Optional[str]


class CostEntryCreate(CostEntryBase):
    pass


class CostEntryRead(CostEntryBase):
    id: int

    class Config:
        orm_mode = True


class LifecycleCostSummary(BaseModel):
    produkt_id: int
    produkt_name: str
    anschaffungskosten: float
    reparaturkosten: float
    laufende_kosten: float
    gesamtkosten: float
    roi: float
    kosten_pro_monat: float
    datenpunkte: int


class DocumentRead(BaseModel):
    id: int
    titel: str
    original_name: Optional[str]
    content_type: Optional[str]
    cloud_url: Optional[str]
    tags: List[str] = []
    produkt_id: Optional[int]
    fahrzeug_id: Optional[int]
    created_at: datetime

    class Config:
        orm_mode = True

    @validator("tags", pre=True)
    def split_tags(cls, value: Optional[str]) -> List[str]:  # noqa: D401
        """Split comma separated tag strings into a list."""

        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [tag.strip() for tag in value.split(",") if tag.strip()]


class GeoPositionCreate(BaseModel):
    fahrzeug_id: int
    latitude: float
    longitude: float
    accuracy: Optional[float]
    zeitstempel: Optional[datetime]


class GeoPositionRead(BaseModel):
    id: int
    fahrzeug_id: int
    latitude: float
    longitude: float
    accuracy: Optional[float]
    zeitstempel: datetime

    class Config:
        orm_mode = True


class GeoRouteRead(BaseModel):
    fahrzeug_id: int
    total_distance_km: float
    positions: List[GeoPositionRead]


class AuditLogRead(BaseModel):
    id: int
    entity_type: str
    entity_id: Optional[int]
    action: str
    payload: str
    benutzername: Optional[str]
    created_at: datetime
    signature_valid: bool


class IntegrationRequest(BaseModel):
    integration: str = Field(regex="^(hl7|fhir|erp|lager)$")
    payload: Dict[str, Any]


class IntegrationResponse(BaseModel):
    correlation_id: str
    status: str
    artifact: Dict[str, Any]


class ChatRequest(BaseModel):
    prompt: str
    context: Optional[str]


class ChatResponse(BaseModel):
    response: str
    intent: Optional[str]
    confidence: float


class CategorizationRequest(BaseModel):
    produkt_id: Optional[int]
    name: str
    beschreibung: Optional[str]


class CategorizationResponse(BaseModel):
    suggested_kategorie: str
    confidence: float
    rationale: str


class AnomalyDetectionRequest(BaseModel):
    scope: str
    values: List[float]
    reference_id: Optional[int]
    metric: str


class AnomalyDetectionResponse(BaseModel):
    anomaly: bool
    score: float
    threshold: float
    details: str


class MFASetupResponse(BaseModel):
    secret: str
    otpauth_url: str


class MFAEnableRequest(BaseModel):
    secret: str
    code: str


class MFADisableRequest(BaseModel):
    code: str


class SSOInitiateResponse(BaseModel):
    authorization_url: str


class SSOCallbackRequest(BaseModel):
    code: str
    state: str


class OfflineChangeCreate(BaseModel):
    entity_type: str
    payload: Dict[str, Any]
    checksum: str


class OfflineSyncResponse(BaseModel):
    queued: int
    synced: int


class SensorDeviceCreate(BaseModel):
    name: str
    location: Optional[str]
    sensor_type: str
    metadata: Optional[Dict[str, Any]]


class SensorDeviceRead(BaseModel):
    id: int
    name: str
    location: Optional[str]
    sensor_type: str
    metadata: Optional[Dict[str, Any]]

    class Config:
        orm_mode = True


class SensorReadingCreate(BaseModel):
    metric: str
    value: float
    unit: Optional[str]
    recorded_at: Optional[datetime]


class SensorAlert(BaseModel):
    metric: str
    value: float
    threshold: float
    message: str


class InventoryForecastRead(BaseModel):
    material_id: int
    horizon_days: int
    predicted_on: date
    stockout_probability: float
    recommended_order_date: date
    model_version: str

    class Config:
        orm_mode = True


class LedgerEntryRequest(BaseModel):
    payload: Dict[str, Any]


class LedgerVerification(BaseModel):
    valid: bool
    entries: int
    message: str


class ArInstructionRead(BaseModel):
    produkt_id: Optional[int]
    title: str
    steps: List[str]
    asset_url: Optional[str]
