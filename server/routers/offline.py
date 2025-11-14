"""Offline queue endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_session
from ..schemas import OfflineChangeCreate, OfflineSyncResponse
from ..services.offline import OfflineService

router = APIRouter(prefix="/api/offline", tags=["offline"])


@router.post("/queue", response_model=OfflineSyncResponse, status_code=status.HTTP_202_ACCEPTED)
def queue_change(
    request: OfflineChangeCreate,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
) -> OfflineSyncResponse:
    service = OfflineService(session)
    try:
        service.queue_change(getattr(user, "id", None), request.entity_type, request.payload, request.checksum)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    pending = service.list_pending()
    return OfflineSyncResponse(queued=len(pending), synced=0)


@router.post("/sync", response_model=OfflineSyncResponse)
def mark_synced(
    change_ids: List[int],
    session: Session = Depends(get_session),
    _user=Depends(get_current_user),
) -> OfflineSyncResponse:
    service = OfflineService(session)
    updated = service.mark_synced(change_ids)
    pending = service.list_pending()
    return OfflineSyncResponse(queued=len(pending), synced=updated)

