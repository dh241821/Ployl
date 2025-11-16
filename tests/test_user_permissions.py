from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.auth import LocationPermission, User


def test_permission_checks():
    user = User(
        id=1,
        username="demo",
        full_name="Demo",
        role="technik",
        email="",
        mandant_id=1,
        standorte_lesen=True,
        standorte_schreiben=False,
        produkte_lesen=True,
        produkte_schreiben=False,
        material_lesen=True,
        material_schreiben=True,
        fahrzeuge_lesen=False,
        fahrzeuge_schreiben=False,
        location_permissions={
            5: LocationPermission(standort_id=5, lesen=True, schreiben=False, label="Test"),
        },
    )

    assert user.can_read("produkte") is True
    assert user.can_write("produkte") is False
    assert user.can_read_location(5) is True
    assert user.can_write_location(5) is False
    assert user.can_read_location(6) is False
