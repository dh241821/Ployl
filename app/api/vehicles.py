from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import Vehicle
from ..schemas.base import VehicleCreate, VehicleRead, VehicleUpdate
from ..services.device_service import create_vehicle
from .dependencies import get_db_session

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.post("/", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
async def create_vehicle_endpoint(
    payload: VehicleCreate, session: AsyncSession = Depends(get_db_session)
) -> Vehicle:
    vehicle = await create_vehicle(session, payload)
    await session.commit()
    await session.refresh(vehicle)
    return vehicle


@router.get("/", response_model=list[VehicleRead])
async def list_vehicles(session: AsyncSession = Depends(get_db_session)) -> list[Vehicle]:
    result = await session.execute(select(Vehicle))
    return list(result.scalars())


@router.get("/{vehicle_id}", response_model=VehicleRead)
async def get_vehicle(vehicle_id: int, session: AsyncSession = Depends(get_db_session)) -> Vehicle:
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    return vehicle


@router.patch("/{vehicle_id}", response_model=VehicleRead)
async def update_vehicle(
    vehicle_id: int, payload: VehicleUpdate, session: AsyncSession = Depends(get_db_session)
) -> Vehicle:
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    for field, value in payload.dict(exclude_unset=True).items():
        setattr(vehicle, field, value)

    await session.commit()
    await session.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(vehicle_id: int, session: AsyncSession = Depends(get_db_session)) -> None:
    vehicle = await session.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    await session.delete(vehicle)
    await session.commit()


__all__ = ["router"]
