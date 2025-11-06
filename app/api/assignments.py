from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.entities import DeviceAssignment
from ..schemas.base import AssignmentCreate, AssignmentRead
from ..services.device_service import assign_device, detach_device, get_active_assignments
from .dependencies import get_db_session

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.post("/", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
async def assign_device_endpoint(
    payload: AssignmentCreate, session: AsyncSession = Depends(get_db_session)
) -> DeviceAssignment:
    assignment = await assign_device(session, payload)
    await session.commit()
    await session.refresh(assignment)
    return assignment


@router.get("/active", response_model=list[AssignmentRead])
async def list_active_assignments(
    vehicle_id: int | None = None, session: AsyncSession = Depends(get_db_session)
) -> list[DeviceAssignment]:
    return await get_active_assignments(session, vehicle_id)


@router.post("/{assignment_id}/release", status_code=status.HTTP_204_NO_CONTENT)
async def release_assignment(
    assignment_id: int, session: AsyncSession = Depends(get_db_session)
) -> None:
    assignment = await session.get(DeviceAssignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    assignment.assigned_to = assignment.assigned_to or assignment.assigned_from
    await session.commit()


@router.post("/detach", status_code=status.HTTP_204_NO_CONTENT)
async def detach_device_endpoint(
    device_id: int, component_id: int | None = None, session: AsyncSession = Depends(get_db_session)
) -> None:
    await detach_device(session, device_id, component_id)
    await session.commit()


__all__ = ["router"]
