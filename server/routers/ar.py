"""Augmented reality endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_session
from ..schemas import ArInstructionRead
from ..services.ar import ARService

router = APIRouter(prefix="/api/ar", tags=["ar"])


@router.get("/instructions/{produkt_id}", response_model=ArInstructionRead)
def get_instruction(
    produkt_id: int,
    session: Session = Depends(get_session),
    _user=Depends(get_current_user),
) -> ArInstructionRead:
    service = ARService(session)
    instruction = service.get_instruction(produkt_id)
    steps = ARService.parse_steps(instruction)
    return ArInstructionRead(produkt_id=instruction.produkt_id, title=instruction.title, steps=steps, asset_url=instruction.asset_url)

