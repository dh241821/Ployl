from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.validation import validate_material, validate_vehicle


def test_validate_material_requires_fields():
    issues = validate_material({})
    assert any(issue.field == "name" for issue in issues)
    assert any(issue.field == "kategorie_id" for issue in issues)


def test_validate_vehicle_rules():
    issues = validate_vehicle({"name": "RTW"})
    assert any(issue.field == "kategorie" for issue in issues)
