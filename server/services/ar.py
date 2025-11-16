"""Augmented reality helper service."""
from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from ..models import ArInstruction


class ARService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_instruction(self, produkt_id: int | None, title: str | None = None) -> ArInstruction:
        query = self.session.query(ArInstruction)
        if produkt_id:
            query = query.filter(ArInstruction.produkt_id == produkt_id)
        if title:
            query = query.filter(ArInstruction.title == title)
        instruction = query.first()
        if instruction:
            return instruction
        steps = [
            "Gerät visuell prüfen",
            "QR-Code scannen",
            "Schritt-für-Schritt Anleitung im PWA öffnen",
        ]
        instruction = ArInstruction(
            produkt_id=produkt_id,
            title=title or "Standard-AR-Workflow",
            steps="\n".join(steps),
            asset_url="https://example.org/ar/assets/default.glb",
        )
        self.session.add(instruction)
        self.session.commit()
        self.session.refresh(instruction)
        return instruction

    @staticmethod
    def parse_steps(instruction: ArInstruction) -> List[str]:
        return [step.strip() for step in instruction.steps.split("\n") if step.strip()]

