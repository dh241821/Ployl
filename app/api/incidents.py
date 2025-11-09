from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.enums import IncidentStatus
from app.db import models
from app.schemas import IncidentCreate, IncidentRead, IncidentUpdate
from app.services import crud
from app.services.event_bus import event_bus

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentRead])
async def list_incidents(session: AsyncSession = Depends(get_db)) -> list[IncidentRead]:
    incidents = await crud.list_incidents(session)
    return incidents


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
async def create_incident(payload: IncidentCreate, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    incident = await crud.create_incident(session, payload)
    await session.commit()
    await event_bus.publish("incidents", {"event": "incident_created", "incident_id": incident.id})
    return incident


async def get_incident_or_404(incident_id: int, session: AsyncSession) -> models.Incident:
    incident = await session.get(models.Incident, incident_id)
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return incident


@router.get("/{incident_id}", response_model=IncidentRead)
async def read_incident(incident_id: int, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    incident = await get_incident_or_404(incident_id, session)
    return incident


@router.patch("/{incident_id}", response_model=IncidentRead)
async def update_incident(incident_id: int, payload: IncidentUpdate, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    incident = await get_incident_or_404(incident_id, session)
    await crud.update_incident(session, incident, payload)
    await session.commit()
    await event_bus.publish("incidents", {"event": "incident_updated", "incident_id": incident.id})
    return incident


@router.post("/{incident_id}/assign/{vehicle_id}", response_model=IncidentRead)
async def assign_vehicle(
    incident_id: int,
    vehicle_id: int,
    session: AsyncSession = Depends(get_db),
) -> IncidentRead:
    incident = await get_incident_or_404(incident_id, session)
    vehicle = await session.get(models.Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    await crud.assign_vehicle_to_incident(session, incident, vehicle)
    await session.commit()
    await event_bus.publish("incidents", {"event": "incident_assignment", "incident_id": incident.id, "vehicle_id": vehicle_id})
    return incident


@router.post("/{incident_id}/status/{status_value}", response_model=IncidentRead)
async def set_incident_status(incident_id: int, status_value: IncidentStatus, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    incident = await get_incident_or_404(incident_id, session)
    await crud.mark_incident_status(session, incident, status_value)
    await session.commit()
    await event_bus.publish("incidents", {"event": "incident_status", "incident_id": incident.id, "status": status_value.value})
    return incident


@router.websocket("/ws")
async def incidents_stream(websocket: WebSocket):
    await websocket.accept()
    queue = event_bus.subscribe("incidents")
    try:
        while True:
            message = await queue.get()
            await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe("incidents", queue)
        await websocket.close()
