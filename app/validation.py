"""Reusable validation helpers for form data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ValidationIssue:
    field: Optional[str]
    message: str


class ValidationError(Exception):
    def __init__(self, issues: List[ValidationIssue]):
        super().__init__("; ".join(issue.message for issue in issues))
        self.issues = issues


def _require(value: Any, label: str, *, field: Optional[str] = None) -> Optional[ValidationIssue]:
    if value is None or value == "":
        return ValidationIssue(field, f"{label} ist erforderlich")
    return None


def validate_material(data: Dict[str, Any]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    for field, label in (("name", "Bezeichnung"), ("kategorie_id", "Kategorie")):
        issue = _require(data.get(field), label, field=field)
        if issue:
            issues.append(issue)
    ist = data.get("ist_bestand")
    soll = data.get("soll_bestand")
    if ist is not None and soll is not None and int(ist) < 0:
        issues.append(ValidationIssue("ist_bestand", "Ist-Bestand darf nicht negativ sein"))
    if soll is not None and int(soll) < 0:
        issues.append(ValidationIssue("soll_bestand", "Soll-Bestand darf nicht negativ sein"))
    return issues


def validate_vehicle(data: Dict[str, Any]) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    for field, label in (("name", "Bezeichnung"), ("kategorie", "Kategorie")):
        issue = _require(data.get(field), label, field=field)
        if issue:
            issues.append(issue)
    if data.get("fahrzeug") and not data.get("funkkennung"):
        issues.append(ValidationIssue("funkkennung", "Funkkennung ist erforderlich"))
    return issues


__all__ = [
    "ValidationError",
    "ValidationIssue",
    "validate_material",
    "validate_vehicle",
]
