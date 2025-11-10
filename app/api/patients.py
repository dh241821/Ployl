from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db import models
from app.schemas import (
    PatientCreate,
    PatientRead,
    PatientTransportCreate,
    PatientTransportRead,
    PatientTransportUpdate,
    PatientUpdate,
)
from app.services import crud

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientRead])
async def list_patients(session: AsyncSession = Depends(get_db)) -> list[PatientRead]:
    patients = await crud.list_patients(session)
    return patients


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
async def create_patient(payload: PatientCreate, session: AsyncSession = Depends(get_db)) -> PatientRead:
    incident = await session.get(models.Incident, payload.incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    patient = await crud.create_patient(session, payload)
    await session.commit()
    return patient


async def get_patient_or_404(patient_id: int, session: AsyncSession) -> models.Patient:
    patient = await session.get(models.Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    return patient


@router.patch("/{patient_id}", response_model=PatientRead)
async def update_patient(patient_id: int, payload: PatientUpdate, session: AsyncSession = Depends(get_db)) -> PatientRead:
    patient = await get_patient_or_404(patient_id, session)
    await crud.update_patient(session, patient, payload)
    await session.commit()
    return patient


@router.post("/{patient_id}/transports", response_model=PatientTransportRead, status_code=status.HTTP_201_CREATED)
async def assign_transport(patient_id: int, payload: PatientTransportCreate, session: AsyncSession = Depends(get_db)) -> PatientTransportRead:
    patient = await get_patient_or_404(patient_id, session)
    if payload.patient_id != patient.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Patient mismatch")
    vehicle = await session.get(models.Vehicle, payload.vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    hospital = await session.get(models.Hospital, payload.hospital_id)
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")
    required = patient.required_capabilities or []
    capabilities = hospital.capabilities or []
    if any(req not in capabilities for req in required):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hospital lacks required capabilities")
    transport = await crud.create_transport(session, payload)
    await session.commit()
    return transport


@router.patch("/transports/{transport_id}", response_model=PatientTransportRead)
async def update_transport(transport_id: int, payload: PatientTransportUpdate, session: AsyncSession = Depends(get_db)) -> PatientTransportRead:
    transport = await session.get(models.PatientTransport, transport_id)
    if not transport:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transport not found")
    await crud.update_transport(session, transport, payload)
    await session.commit()
    return transport


@router.get("/transports", response_model=list[PatientTransportRead])
async def list_transports(session: AsyncSession = Depends(get_db)) -> list[PatientTransportRead]:
    transports = await crud.list_transports(session)
    return transports
