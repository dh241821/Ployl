"""Offline change queue helpers."""
from __future__ import annotations

import json
import hashlib
from typing import Dict, List

from sqlalchemy.orm import Session

from ..models import OfflineChange


class OfflineService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def queue_change(self, user_id: int | None, entity_type: str, payload: Dict[str, object], checksum: str) -> OfflineChange:
        serialized = json.dumps(payload, sort_keys=True, default=str)
        expected = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        if expected != checksum:
            raise ValueError("Checksum mismatch")
        change = OfflineChange(user_id=user_id, entity_type=entity_type, payload=serialized, checksum=checksum)
        self.session.add(change)
        self.session.commit()
        self.session.refresh(change)
        return change

    def list_pending(self) -> List[OfflineChange]:
        return (
            self.session.query(OfflineChange)
            .filter(OfflineChange.synced.is_(False))
            .order_by(OfflineChange.created_at.asc())
            .all()
        )

    def mark_synced(self, change_ids: List[int]) -> int:
        updated = (
            self.session.query(OfflineChange)
            .filter(OfflineChange.id.in_(change_ids))
            .update({OfflineChange.synced: True}, synchronize_session=False)
        )
        self.session.commit()
        return updated or 0

