"""Document management endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_session
from ..schemas import DocumentRead
from ..services.audit import audit_context
from ..services.documents import DocumentService

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentRead)
async def upload_document(
    titel: str = Form(...),
    produkt_id: Optional[int] = Form(None),
    fahrzeug_id: Optional[int] = Form(None),
    tags: Optional[str] = Form(None),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
) -> DocumentRead:
    payload = await file.read()
    tag_list = [tag.strip() for tag in (tags.split(",") if tags else []) if tag.strip()]
    service = DocumentService(session)
    with audit_context(user.username):
        dokument = service.save_document(
            titel=titel,
            filename=file.filename,
            content_type=file.content_type,
            payload=payload,
            produkt_id=produkt_id,
            fahrzeug_id=fahrzeug_id,
            tags=tag_list,
        )
    return DocumentRead.from_orm(dokument)


@router.get("", response_model=List[DocumentRead])
def search_documents(
    query: Optional[str] = None,
    tag: Optional[str] = None,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
) -> List[DocumentRead]:
    tags = [t.strip() for t in tag.split(",")] if tag else None
    service = DocumentService(session)
    results = service.search(query=query, tags=tags)
    return [DocumentRead.from_orm(doc) for doc in results]
