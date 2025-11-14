"""Blockchain ledger endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_session
from ..schemas import LedgerEntryRequest, LedgerVerification
from ..services.blockchain import BlockchainService

router = APIRouter(prefix="/api/blockchain", tags=["blockchain"])


@router.post("/record", response_model=LedgerVerification)
def record(
    request: LedgerEntryRequest,
    session: Session = Depends(get_session),
    _user=Depends(require_admin),
) -> LedgerVerification:
    service = BlockchainService(session)
    service.add_entry(request.payload)
    valid, entries = service.verify()
    message = "Ledger extended" if valid else "Ledger verification failed"
    return LedgerVerification(valid=valid, entries=len(entries), message=message)


@router.get("/verify", response_model=LedgerVerification)
def verify(session: Session = Depends(get_session), _user=Depends(require_admin)) -> LedgerVerification:
    service = BlockchainService(session)
    valid, entries = service.verify()
    message = "Ledger valid" if valid else "Ledger verification failed"
    return LedgerVerification(valid=valid, entries=len(entries), message=message)

