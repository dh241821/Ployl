from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..models.entities import Attachment, SafetyCheck
from ..schemas.base import AttachmentRead, SafetyCheckCreate, SafetyCheckRead
from ..services.device_service import create_safety_check
from ..utils.uploads import save_upload
from .dependencies import get_db_session

router = APIRouter(prefix="/checks", tags=["checks"])


@router.post("/", response_model=SafetyCheckRead, status_code=status.HTTP_201_CREATED)
async def create_check(
    payload: SafetyCheckCreate, session: AsyncSession = Depends(get_db_session)
) -> SafetyCheck:
    safety_check = await create_safety_check(session, payload)
    await session.commit()
    await session.refresh(safety_check)
    return safety_check


@router.get("/", response_model=list[SafetyCheckRead])
async def list_checks(
    check_type: str | None = None,
    device_id: int | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> list[SafetyCheck]:
    stmt = select(SafetyCheck)
    if check_type:
        stmt = stmt.where(SafetyCheck.check_type == check_type.upper())
    if device_id:
        stmt = stmt.where(SafetyCheck.device_id == device_id)
    result = await session.execute(stmt)
    return list(result.scalars())


@router.get("/{check_id}", response_model=SafetyCheckRead)
async def get_check(check_id: int, session: AsyncSession = Depends(get_db_session)) -> SafetyCheck:
    safety_check = await session.get(SafetyCheck, check_id)
    if not safety_check:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Safety check not found")
    return safety_check


@router.post(
    "/{check_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_check_document(
    check_id: int,
    file: UploadFile = File(...),
    description: str | None = Form(None),
    session: AsyncSession = Depends(get_db_session),
) -> Attachment:
    safety_check = await session.get(SafetyCheck, check_id)
    if not safety_check:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Safety check not found")

    settings = get_settings()
    relative_path = await save_upload(file, settings.upload_dir, "checks", check_id)

    attachment = Attachment(
        safety_check_id=check_id,
        file_path=str(relative_path).replace("\\", "/"),
        description=description,
    )
    session.add(attachment)
    await session.commit()
    await session.refresh(attachment)
    return attachment


__all__ = ["router"]
