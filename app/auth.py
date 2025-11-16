"""Authentication and authorization helpers for the desktop application."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# permission metadata
# ---------------------------------------------------------------------------

PERMISSION_MODULES: List[tuple[str, str]] = [
    ("standorte", "Standorte"),
    ("produkte", "Produkte"),
    ("material", "Material"),
    ("fahrzeuge", "Fahrzeuge"),
]

PERMISSION_COLUMNS: List[str] = [
    f"{module}_{flag}"
    for module, _label in PERMISSION_MODULES
    for flag in ("lesen", "schreiben")
]


def _permission_map(default: bool) -> Dict[str, bool]:
    return {column: default for column in PERMISSION_COLUMNS}


PERMISSION_DEFAULTS: Dict[str, bool] = _permission_map(True)

ROLE_PERMISSION_PRESETS: Dict[str, Dict[str, bool]] = {
    "admin": _permission_map(True),
    "leitstelle": {
        **_permission_map(False),
        "standorte_lesen": True,
        "standorte_schreiben": True,
        "fahrzeuge_lesen": True,
        "fahrzeuge_schreiben": True,
        "produkte_lesen": True,
    },
    "technik": {
        **_permission_map(False),
        "produkte_lesen": True,
        "produkte_schreiben": True,
        "fahrzeuge_lesen": True,
        "material_lesen": True,
        "material_schreiben": True,
    },
    "lager": {
        **_permission_map(False),
        "material_lesen": True,
        "material_schreiben": True,
    },
    "benutzer": {
        **_permission_map(False),
        "standorte_lesen": True,
        "produkte_lesen": True,
        "produkte_schreiben": True,
        "material_lesen": True,
        "material_schreiben": True,
        "fahrzeuge_lesen": True,
    },
    "viewer": {
        **_permission_map(False),
        "standorte_lesen": True,
        "produkte_lesen": True,
        "material_lesen": True,
        "fahrzeuge_lesen": True,
    },
}

ROLE_CHOICES: List[str] = list(ROLE_PERMISSION_PRESETS.keys())


@dataclass
class LocationPermission:
    """Represents read/write permissions for a specific location."""

    standort_id: int
    lesen: bool
    schreiben: bool
    label: str = ""


@dataclass
class User:
    """Represents an authenticated user with module and location rights."""

    id: int
    username: str
    full_name: str
    role: str
    email: str
    mandant_id: int
    standorte_lesen: bool
    standorte_schreiben: bool
    produkte_lesen: bool
    produkte_schreiben: bool
    material_lesen: bool
    material_schreiben: bool
    fahrzeuge_lesen: bool
    fahrzeuge_schreiben: bool
    location_permissions: Dict[int, LocationPermission] = field(default_factory=dict)

    def can_read(self, module: str) -> bool:
        return bool(getattr(self, f"{module}_lesen", False))

    def can_write(self, module: str) -> bool:
        return bool(getattr(self, f"{module}_schreiben", False))

    def can_read_location(self, standort_id: Optional[int]) -> bool:
        if not self.location_permissions:
            return True
        if standort_id is None:
            return True
        permission = self.location_permissions.get(int(standort_id))
        return bool(permission and permission.lesen)

    def can_write_location(self, standort_id: Optional[int]) -> bool:
        if not self.location_permissions:
            return True
        if standort_id is None:
            return True
        permission = self.location_permissions.get(int(standort_id))
        return bool(permission and permission.schreiben)


__all__ = [
    "LocationPermission",
    "PERMISSION_COLUMNS",
    "PERMISSION_DEFAULTS",
    "PERMISSION_MODULES",
    "ROLE_CHOICES",
    "ROLE_PERMISSION_PRESETS",
    "User",
]
