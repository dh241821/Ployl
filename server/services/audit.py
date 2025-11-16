"""Audit trail helpers with digital signature support."""
from __future__ import annotations

"""Audit trail helpers with digital signature support."""
import hashlib
import hmac
import json
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from typing import Any, Dict, Iterable, Tuple, Type

from sqlalchemy import event, inspect
from sqlalchemy.orm import Mapper, Session, object_session

from ..config import settings
from ..models import AuditLog

_AUDIT_USER: ContextVar[str] = ContextVar("audit_user", default="system")


@contextmanager
def audit_context(username: str) -> Iterable[None]:
    token = _AUDIT_USER.set(username or "system")
    try:
        yield
    finally:
        _AUDIT_USER.reset(token)


def _serialize_entity(target: Any) -> Dict[str, Any]:
    mapper = inspect(target).mapper
    data: Dict[str, Any] = {}
    for column in mapper.columns:
        value = getattr(target, column.key)
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        data[column.key] = value
    return data


def _signature(payload: str) -> str:
    secret = settings.audit_secret.encode("utf-8")
    return hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _log_change(target: Any, action: str) -> None:
    if isinstance(target, AuditLog):  # pragma: no cover - defensive
        return
    session = object_session(target)
    if session is None:
        return
    payload_dict = _serialize_entity(target)
    payload = json.dumps(payload_dict, sort_keys=True, ensure_ascii=False)
    entry = AuditLog(
        entity_type=target.__class__.__name__,
        entity_id=getattr(target, "id", None),
        action=action,
        payload=payload,
        benutzername=_AUDIT_USER.get(),
        signature=_signature(payload),
    )
    session.add(entry)


def _after_insert(mapper: Mapper, connection, target: Any) -> None:  # pragma: no cover - SQLAlchemy hook
    _log_change(target, "insert")


def _after_update(mapper: Mapper, connection, target: Any) -> None:  # pragma: no cover - SQLAlchemy hook
    _log_change(target, "update")


def _after_delete(mapper: Mapper, connection, target: Any) -> None:  # pragma: no cover - SQLAlchemy hook
    _log_change(target, "delete")


def configure_audit_events(models: Tuple[Type[Any], ...]) -> None:
    for model in models:
        event.listen(model, "after_insert", _after_insert, propagate=True)
        event.listen(model, "after_update", _after_update, propagate=True)
        event.listen(model, "after_delete", _after_delete, propagate=True)


def verify_signature(entry: AuditLog) -> bool:
    expected = _signature(entry.payload)
    return hmac.compare_digest(expected, entry.signature)


def attach_user(session: Session, username: str) -> None:
    """Attach the username to the audit context for manual operations."""

    with audit_context(username):
        session.flush()
