"""Notification management endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_session
from ..services.notifications import NotificationService
from ..schemas import NotificationResult

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.post("/dispatch", response_model=NotificationResult)
def dispatch_notifications(within_days: int = 30, session: Session = Depends(get_session), user=Depends(require_admin)) -> NotificationResult:
    service = NotificationService(session)
    return service.send_notifications_for_admins(within_days=within_days)
