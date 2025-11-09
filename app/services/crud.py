from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import IncidentStatus, VehicleStatus
from app.db import models
from app.schemas import (
    CrewMemberCreate,
    CrewMemberUpdate,
    IncidentCreate,
    IncidentUpdate,
    PatientCreate,
    PatientTransportCreate,
    PatientTransportUpdate,
    PatientUpdate,
    VehicleStatusChange,
    VehicleCreate,
    VehicleUpdate,
    HospitalCreate,
    HospitalUpdate,
    PersonnelCreate,
    PersonnelUpdate,
)


async def list_vehicles(session: AsyncSession) -> Sequence[models.Vehicle]:
    result = await session.execute(select(models.Vehicle).order_by(models.Vehicle.callsign))
    return result.scalars().unique().all()


async def create_vehicle(session: AsyncSession, data: VehicleCreate) -> models.Vehicle:
    crew_data = data.crew or []
    vehicle_payload = data.dict(exclude={"crew"})
    vehicle = models.Vehicle(**vehicle_payload)
    if crew_data:
        vehicle.crew = [models.CrewMember(**member.dict()) for member in crew_data]
    session.add(vehicle)
    await session.flush()
    await log_vehicle_status(session, vehicle, VehicleStatusChange(status=vehicle.status, note="Initial state"))
    return vehicle


async def update_vehicle(session: AsyncSession, vehicle: models.Vehicle, data: VehicleUpdate) -> models.Vehicle:
    for key, value in data.dict(exclude_unset=True).items():
        setattr(vehicle, key, value)
    await session.flush()
    return vehicle


async def upsert_crew_member(
    session: AsyncSession,
    vehicle: models.Vehicle | None,
    payload: CrewMemberCreate | CrewMemberUpdate,
    crew_id: int | None = None,
) -> models.CrewMember:
    if crew_id is None:
        if vehicle is None:
            raise ValueError("Vehicle must be provided when creating crew")
        crew_member = models.CrewMember(vehicle=vehicle, **payload.dict(exclude_unset=True))
        session.add(crew_member)
    else:
        crew_member = await session.get(models.CrewMember, crew_id)
        if not crew_member:
            raise ValueError("Crew member not found")
        for key, value in payload.dict(exclude_unset=True).items():
            setattr(crew_member, key, value)
    await session.flush()
    return crew_member


async def delete_crew_member(session: AsyncSession, crew_member: models.CrewMember) -> None:
    await session.delete(crew_member)
    await session.flush()


async def log_vehicle_status(session: AsyncSession, vehicle: models.Vehicle, change: VehicleStatusChange) -> models.VehicleStatusLog:
    status_log = models.VehicleStatusLog(
        vehicle=vehicle,
        status=change.status,
        note=change.note,
        timestamp=change.timestamp or datetime.utcnow(),
        payload=change.payload,
    )
    vehicle.status = change.status
    session.add(status_log)
    await session.flush()
    return status_log


async def create_incident(session: AsyncSession, payload: IncidentCreate) -> models.Incident:
    incident = models.Incident(**payload.dict())
    session.add(incident)
    await session.flush()
    return incident


async def list_incidents(session: AsyncSession) -> Sequence[models.Incident]:
    result = await session.execute(select(models.Incident).order_by(models.Incident.created_at.desc()))
    return result.scalars().unique().all()


async def update_incident(session: AsyncSession, incident: models.Incident, payload: IncidentUpdate) -> models.Incident:
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(incident, key, value)
    await session.flush()
    return incident


async def assign_vehicle_to_incident(session: AsyncSession, incident: models.Incident, vehicle: models.Vehicle) -> models.IncidentAssignment:
    assignment = models.IncidentAssignment(incident=incident, vehicle=vehicle, dispatched_at=datetime.utcnow())
    session.add(assignment)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ValueError("Vehicle already assigned to this incident") from exc
    return assignment


async def acknowledge_assignment(session: AsyncSession, assignment: models.IncidentAssignment) -> models.IncidentAssignment:
    assignment.acknowledged_at = datetime.utcnow()
    await session.flush()
    return assignment


async def report_breakdown(session: AsyncSession, assignment: models.IncidentAssignment, note: str | None = None) -> models.IncidentAssignment:
    assignment.breakdown_reported = True
    await session.flush()
    await log_vehicle_status(session, assignment.vehicle, VehicleStatusChange(status=VehicleStatus.SERVICE_TRIP, note=note or "Breakdown reported"))
    return assignment


async def mark_incident_status(session: AsyncSession, incident: models.Incident, status: IncidentStatus) -> models.Incident:
    incident.status = status
    await session.flush()
    return incident


async def create_hospital(session: AsyncSession, payload: HospitalCreate) -> models.Hospital:
    hospital = models.Hospital(**payload.dict())
    session.add(hospital)
    await session.flush()
    return hospital


async def list_hospitals(session: AsyncSession) -> Sequence[models.Hospital]:
    result = await session.execute(select(models.Hospital).order_by(models.Hospital.name))
    return result.scalars().unique().all()


async def update_hospital(session: AsyncSession, hospital: models.Hospital, payload: HospitalUpdate) -> models.Hospital:
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(hospital, key, value)
    await session.flush()
    return hospital


async def create_personnel(session: AsyncSession, payload: PersonnelCreate) -> models.Personnel:
    personnel = models.Personnel(**payload.dict())
    session.add(personnel)
    await session.flush()
    return personnel


async def list_personnel(session: AsyncSession) -> Sequence[models.Personnel]:
    result = await session.execute(select(models.Personnel).order_by(models.Personnel.name))
    return result.scalars().unique().all()


async def update_personnel(session: AsyncSession, personnel: models.Personnel, payload: PersonnelUpdate) -> models.Personnel:
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(personnel, key, value)
    await session.flush()
    return personnel


async def create_patient(session: AsyncSession, payload: PatientCreate) -> models.Patient:
    patient = models.Patient(**payload.dict())
    session.add(patient)
    await session.flush()
    return patient


async def update_patient(session: AsyncSession, patient: models.Patient, payload: PatientUpdate) -> models.Patient:
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(patient, key, value)
    await session.flush()
    return patient


async def create_transport(session: AsyncSession, payload: PatientTransportCreate) -> models.PatientTransport:
    transport = models.PatientTransport(**payload.dict())
    session.add(transport)
    await session.flush()
    return transport


async def update_transport(session: AsyncSession, transport: models.PatientTransport, payload: PatientTransportUpdate) -> models.PatientTransport:
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(transport, key, value)
    await session.flush()
    return transport


async def list_patients(session: AsyncSession) -> Sequence[models.Patient]:
    result = await session.execute(select(models.Patient))
    return result.scalars().unique().all()


async def list_transports(session: AsyncSession) -> Sequence[models.PatientTransport]:
    result = await session.execute(select(models.PatientTransport))
    return result.scalars().unique().all()
