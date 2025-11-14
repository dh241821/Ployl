"""Audit trail access endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_session
from ..models import AuditLog
from ..schemas import AuditLogRead
from ..services.audit import verify_signature

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=List[AuditLogRead])
def list_audit_logs(
    session: Session = Depends(get_session),
    user=Depends(require_admin),
) -> List[AuditLogRead]:
    logs = session.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(500).all()
    result: List[AuditLogRead] = []
    for entry in logs:
        result.append(
            AuditLogRead(
                id=entry.id,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                action=entry.action,
                payload=entry.payload,
                benutzername=entry.benutzername,
                created_at=entry.created_at,
                signature_valid=verify_signature(entry),
            )
        )
    return result
