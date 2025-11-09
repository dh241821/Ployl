from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DifficultyLevel, IncidentStatus, VehicleStatus, VehicleType
from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    callsign: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    vehicle_type: Mapped[VehicleType] = mapped_column(Enum(VehicleType), nullable=False)
    status: Mapped[VehicleStatus] = mapped_column(Enum(VehicleStatus), default=VehicleStatus.OFF_DUTY)
    location_name: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    minutes_to_dispatch_site: Mapped[int | None] = mapped_column(Integer)
    kilometers_to_dispatch_site: Mapped[float | None] = mapped_column(Float)
    minutes_to_destination: Mapped[int | None] = mapped_column(Integer)
    kilometers_to_destination: Mapped[float | None] = mapped_column(Float)
    is_operational: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)

    crew: Mapped[list[CrewMember]] = relationship("CrewMember", back_populates="vehicle", cascade="all, delete-orphan", lazy="selectin")
    assignments: Mapped[list[IncidentAssignment]] = relationship("IncidentAssignment", back_populates="vehicle", lazy="selectin")
    status_history: Mapped[list[VehicleStatusLog]] = relationship("VehicleStatusLog", back_populates="vehicle", cascade="all, delete-orphan", lazy="selectin")
    transports: Mapped[list[PatientTransport]] = relationship("PatientTransport", back_populates="vehicle", lazy="selectin")


class CrewMember(Base, TimestampMixin):
    __tablename__ = "crew_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(80), nullable=False)
    qualifications: Mapped[list[str] | None] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"))

    vehicle: Mapped[Vehicle | None] = relationship("Vehicle", back_populates="crew", lazy="selectin")


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    incident_type: Mapped[str] = mapped_column(String(80), nullable=False)
    difficulty: Mapped[DifficultyLevel] = mapped_column(Enum(DifficultyLevel), default=DifficultyLevel.BASIC)
    status: Mapped[IncidentStatus] = mapped_column(Enum(IncidentStatus), default=IncidentStatus.CREATED)
    location_name: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    expected_patients: Mapped[int | None] = mapped_column(Integer)

    assignments: Mapped[list[IncidentAssignment]] = relationship("IncidentAssignment", back_populates="incident", cascade="all, delete-orphan", lazy="selectin")
    patients: Mapped[list[Patient]] = relationship("Patient", back_populates="incident", cascade="all, delete-orphan", lazy="selectin")


class IncidentAssignment(Base, TimestampMixin):
    __tablename__ = "incident_assignments"
    __table_args__ = (UniqueConstraint("incident_id", "vehicle_id", name="uq_incident_vehicle"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrival_at_scene: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    departed_scene_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    breakdown_reported: Mapped[bool] = mapped_column(Boolean, default=False)

    incident: Mapped[Incident] = relationship("Incident", back_populates="assignments", lazy="selectin")
    vehicle: Mapped[Vehicle] = relationship("Vehicle", back_populates="assignments", lazy="selectin")


class Hospital(Base, TimestampMixin):
    __tablename__ = "hospitals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    location_name: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    max_capacity: Mapped[int | None] = mapped_column(Integer)
    specialty_capacity: Mapped[dict[str, int] | None] = mapped_column(JSON)
    capabilities: Mapped[list[str] | None] = mapped_column(JSON)

    transports: Mapped[list[PatientTransport]] = relationship("PatientTransport", back_populates="hospital", lazy="selectin")


class Personnel(Base, TimestampMixin):
    __tablename__ = "personnel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(80), nullable=False)
    skills: Mapped[list[str] | None] = mapped_column(JSON)
    organization: Mapped[str | None] = mapped_column(String(120))


class Patient(Base, TimestampMixin):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    identifier: Mapped[str] = mapped_column(String(80), nullable=False)
    condition: Mapped[str | None] = mapped_column(String(120))
    priority: Mapped[str | None] = mapped_column(String(40))
    required_capabilities: Mapped[list[str] | None] = mapped_column(JSON)

    incident: Mapped[Incident] = relationship("Incident", back_populates="patients", lazy="selectin")
    transports: Mapped[list[PatientTransport]] = relationship("PatientTransport", back_populates="patient", cascade="all, delete-orphan", lazy="selectin")


class PatientTransport(Base, TimestampMixin):
    __tablename__ = "patient_transports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)
    hospital_id: Mapped[int] = mapped_column(ForeignKey("hospitals.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="assigned")

    patient: Mapped[Patient] = relationship("Patient", back_populates="transports", lazy="selectin")
    vehicle: Mapped[Vehicle] = relationship("Vehicle", back_populates="transports", lazy="selectin")
    hospital: Mapped[Hospital] = relationship("Hospital", back_populates="transports", lazy="selectin")


class VehicleStatusLog(Base):
    __tablename__ = "vehicle_status_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[VehicleStatus] = mapped_column(Enum(VehicleStatus), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    vehicle: Mapped[Vehicle] = relationship("Vehicle", back_populates="status_history", lazy="selectin")
