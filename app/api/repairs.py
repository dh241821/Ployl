from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models.entities import Attachment, RepairLog
from ..schemas.base import (
    AttachmentRead,
    RepairLogCreate,
    RepairLogRead,
    RepairLogUpdate,
)
from ..services.device_service import (
    create_repair_log,
    get_repairs_filtered,
    update_repair_log,
)
from ..utils.uploads import save_upload
from .dependencies import get_db_session

router = APIRouter(prefix="/repairs", tags=["repairs"])


@router.post("/", response_model=RepairLogRead, status_code=status.HTTP_201_CREATED)
async def create_repair(
    payload: RepairLogCreate, session: AsyncSession = Depends(get_db_session)
) -> RepairLog:
    repair = await create_repair_log(session, payload)
    await session.commit()
    await session.refresh(repair)
    return repair


@router.get("/", response_model=list[RepairLogRead])
async def list_repairs(
    category_id: int | None = None,
    serial_number: str | None = None,
    device_id: int | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> list[RepairLog]:
    if category_id is None and serial_number is None and device_id is None:
        result = await session.execute(select(RepairLog))
        return list(result.scalars())
    if device_id is not None:
        result = await session.execute(
            select(RepairLog).where(RepairLog.device_id == device_id)
        )
        return list(result.scalars())
    repairs = await get_repairs_filtered(session, category_id, serial_number)
    return repairs


@router.get("/{repair_id}", response_model=RepairLogRead)
async def get_repair(repair_id: int, session: AsyncSession = Depends(get_db_session)) -> RepairLog:
    repair = await session.get(RepairLog, repair_id)
    if not repair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repair not found")
    return repair


@router.patch("/{repair_id}", response_model=RepairLogRead)
async def patch_repair(
    repair_id: int,
    payload: RepairLogUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> RepairLog:
    repair = await update_repair_log(session, repair_id, payload)
    if not repair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repair not found")
    await session.commit()
    await session.refresh(repair)
    return repair


@router.post(
    "/{repair_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_repair_document(
    repair_id: int,
    file: UploadFile = File(...),
    description: str | None = Form(None),
    session: AsyncSession = Depends(get_db_session),
) -> Attachment:
    repair = await session.get(RepairLog, repair_id)
    if not repair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repair not found")

    settings = get_settings()
    relative_path = await save_upload(file, settings.upload_dir, "repairs", repair_id)

    attachment = Attachment(
        repair_id=repair_id,
        file_path=str(relative_path).replace("\\", "/"),
        description=description,
    )
    session.add(attachment)
    await session.commit()
    await session.refresh(attachment)
    return attachment


__all__ = ["router"]
