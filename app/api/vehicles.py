from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.enums import VehicleStatus
from app.db import models
from app.schemas import (
    CrewMemberCreate,
    CrewMemberRead,
    CrewMemberUpdate,
    VehicleCreate,
    VehicleRead,
    VehicleStatusChange,
    VehicleUpdate,
)
from app.schemas.common import StatusLog
from app.services import crud
from app.services.event_bus import event_bus

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("", response_model=list[VehicleRead])
async def list_vehicles(session: AsyncSession = Depends(get_db)) -> list[VehicleRead]:
    vehicles = await crud.list_vehicles(session)
    return vehicles


@router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
async def create_vehicle(payload: VehicleCreate, session: AsyncSession = Depends(get_db)) -> VehicleRead:
    vehicle = await crud.create_vehicle(session, payload)
    await session.commit()
    await event_bus.publish("vehicles", {"event": "vehicle_created", "vehicle_id": vehicle.id})
    return vehicle


async def get_vehicle_or_404(vehicle_id: int, session: AsyncSession) -> models.Vehicle:
    vehicle = await session.get(models.Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    return vehicle


@router.get("/{vehicle_id}", response_model=VehicleRead)
async def read_vehicle(vehicle_id: int, session: AsyncSession = Depends(get_db)) -> VehicleRead:
    vehicle = await get_vehicle_or_404(vehicle_id, session)
    return vehicle


@router.patch("/{vehicle_id}", response_model=VehicleRead)
async def update_vehicle(vehicle_id: int, payload: VehicleUpdate, session: AsyncSession = Depends(get_db)) -> VehicleRead:
    vehicle = await get_vehicle_or_404(vehicle_id, session)
    await crud.update_vehicle(session, vehicle, payload)
    await session.commit()
    await event_bus.publish("vehicles", {"event": "vehicle_updated", "vehicle_id": vehicle.id})
    return vehicle


@router.post("/{vehicle_id}/status", response_model=StatusLog)
async def change_vehicle_status(vehicle_id: int, payload: VehicleStatusChange, session: AsyncSession = Depends(get_db)) -> StatusLog:
    vehicle = await get_vehicle_or_404(vehicle_id, session)
    log_entry = await crud.log_vehicle_status(session, vehicle, payload)
    await session.commit()
    await event_bus.publish(
        "vehicles",
        {
            "event": "vehicle_status_changed",
            "vehicle_id": vehicle.id,
            "status": vehicle.status.value if isinstance(vehicle.status, VehicleStatus) else vehicle.status,
        },
    )
    return log_entry


@router.post("/{vehicle_id}/crew", response_model=CrewMemberRead, status_code=status.HTTP_201_CREATED)
async def add_crew_member(vehicle_id: int, payload: CrewMemberCreate, session: AsyncSession = Depends(get_db)) -> CrewMemberRead:
    vehicle = await get_vehicle_or_404(vehicle_id, session)
    member = await crud.upsert_crew_member(session, vehicle, payload)
    await session.commit()
    await event_bus.publish("vehicles", {"event": "vehicle_crew_updated", "vehicle_id": vehicle.id})
    return member


@router.patch("/{vehicle_id}/crew/{crew_id}", response_model=CrewMemberRead)
async def update_crew_member(
    vehicle_id: int,
    crew_id: int,
    payload: CrewMemberUpdate,
    session: AsyncSession = Depends(get_db),
) -> CrewMemberRead:
    await get_vehicle_or_404(vehicle_id, session)
    member = await crud.upsert_crew_member(session, vehicle=None, payload=payload, crew_id=crew_id)
    await session.commit()
    await event_bus.publish("vehicles", {"event": "vehicle_crew_updated", "vehicle_id": vehicle_id})
    return member


@router.delete("/{vehicle_id}/crew/{crew_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_crew_member(vehicle_id: int, crew_id: int, session: AsyncSession = Depends(get_db)) -> None:
    vehicle = await get_vehicle_or_404(vehicle_id, session)
    member = await session.get(models.CrewMember, crew_id)
    if not member or member.vehicle_id != vehicle.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crew member not found")
    await crud.delete_crew_member(session, member)
    await session.commit()
    await event_bus.publish("vehicles", {"event": "vehicle_crew_updated", "vehicle_id": vehicle.id})


@router.websocket("/ws")
async def vehicles_stream(websocket: WebSocket):
    await websocket.accept()
    queue = event_bus.subscribe("vehicles")
    try:
        while True:
            message = await queue.get()
            await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        event_bus.unsubscribe("vehicles", queue)
        await websocket.close()
