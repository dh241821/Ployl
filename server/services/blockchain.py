"""Minimal blockchain-style ledger for compliance evidence."""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List

from sqlalchemy.orm import Session

from ..models import LedgerEntry
from .security import SecurityService


class BlockchainService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.security = SecurityService(session)

    def add_entry(self, payload: Dict[str, object]) -> LedgerEntry:
        payload_json = json.dumps(payload, sort_keys=True, default=str)
        last_entry = (
            self.session.query(LedgerEntry).order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc()).first()
        )
        previous_hash = last_entry.record_hash if last_entry else ""
        signature = self.security.sign_payload(payload_json)
        record_hash = hashlib.sha256(f"{previous_hash}{payload_json}{signature}".encode("utf-8")).hexdigest()
        entry = LedgerEntry(previous_hash=previous_hash or None, record_hash=record_hash, payload=payload_json, signature=signature)
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def verify(self) -> tuple[bool, List[LedgerEntry]]:
        entries = self.session.query(LedgerEntry).order_by(LedgerEntry.created_at.asc(), LedgerEntry.id.asc()).all()
        previous_hash = ""
        for entry in entries:
            if not self.security.verify_signature(entry.payload, entry.signature):
                return False, entries
            recalculated = hashlib.sha256(f"{previous_hash}{entry.payload}{entry.signature}".encode("utf-8")).hexdigest()
            if recalculated != entry.record_hash:
                return False, entries
            previous_hash = entry.record_hash
        return True, entries

