"""Product related validation and helper utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterable, List, Optional, TYPE_CHECKING

from .maintenance import update_maintenance_dates

if TYPE_CHECKING:  # pragma: no cover - only used for typing
    from app.database import DatabaseManager


@dataclass
class ValidationError(Exception):
    """Raised when product validation fails."""

    errors: List[str]

    def __str__(self) -> str:  # pragma: no cover - inherited behavior
        return "; ".join(self.errors)


def _require(value: Any, label: str, errors: List[str]) -> None:
    if value is None or value == "":
        errors.append(f"{label} ist erforderlich")


def validate_product(
    data: Dict[str, Any], *, db: Optional["DatabaseManager"] = None
) -> List[str]:
    errors: List[str] = []
    _require(data.get("seriennummer"), "Seriennummer", errors)
    if not data.get("standort_id") and not data.get("fahrzeug_id"):
        errors.append("Standort oder Fahrzeug muss zugeordnet werden")
    if data.get("stk_aktiv") and not data.get("stk_intervall"):
        errors.append("STK-Intervall erforderlich, wenn STK aktiv ist")
    if data.get("mtk_aktiv") and not data.get("mtk_intervall"):
        errors.append("MTK-Intervall erforderlich, wenn MTK aktiv ist")

    if db and data.get("seriennummer"):
        exclude = data.get("produkt_id")
        if db.serial_exists(str(data["seriennummer"]), exclude_id=exclude):
            errors.append("Seriennummer bereits vergeben")

    for field_name in ("letzte_stk", "letzte_mtk"):
        last = data.get(field_name)
        if last and isinstance(last, str):
            data[field_name] = date.fromisoformat(last)

    update_maintenance_dates(data)
    return errors


def mark_product_retired(
    db: "DatabaseManager",
    produkt_id: int,
    datum: date,
    grund: str,
    user_id: Optional[int],
) -> None:
    db.log_event(
        ebene="INFO",
        nachricht=f"Produkt {produkt_id} ausgeschieden: {grund}",
        benutzer_id=user_id,
    )
    db.record_audit(
        "produkte",
        produkt_id,
        "ausscheidung",
        before=None,
        after=grund,
        user_id=user_id,
    )
    db.mark_product_retired(produkt_id, datum, grund, user_id=user_id)


__all__ = ["ValidationError", "validate_product", "mark_product_retired"]
