from datetime import date
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from app.database import DatabaseManager
except ModuleNotFoundError as exc:  # pragma: no cover
    pytest.skip(f"Abhängigkeit fehlt: {exc}", allow_module_level=True)


def _create_db(tmp_path):
    db_path = tmp_path / "manager.db"
    return DatabaseManager(db_path)


def test_product_roundtrip(tmp_path):
    manager = _create_db(tmp_path)
    standort = manager.add_location("AT", "Bereich", "Bezirk", "Stelle", "Ort", "Test")
    produkt_id = manager.add_or_update_product(
        produkt_id=None,
        name="Corpuls",
        typ="Defi",
        seriennummer="XYZ",
        hersteller="Corpuls",
        anschaffungsdatum=date(2024, 1, 1),
        kategorie_id=None,
        standort_id=standort,
        fahrzeug_id=None,
        status="im_dienst",
        interne_kennung="IK-2",
        stk_intervall=12,
        mtk_intervall=24,
        stk_aktiv=True,
        mtk_aktiv=True,
        letzte_stk=date(2024, 1, 1),
        letzte_mtk=None,
        naechste_stk=None,
        naechste_mtk=None,
        lagerort="Lager",
        produkt_typ_id=None,
        produkt_modell_id=None,
        produkt_hersteller_id=None,
        informationstext="",
    )
    product = manager.get_product(produkt_id)
    assert product["seriennummer"] == "XYZ"
    assert product["standort_id"] == standort


def test_serial_uniqueness(tmp_path):
    manager = _create_db(tmp_path)
    standort = manager.add_location("AT", "B", "C", "D", "E", "Test")
    kwargs = dict(
        produkt_id=None,
        name="Gerät",
        typ="Monitor",
        seriennummer="SN",
        hersteller="Acme",
        anschaffungsdatum=None,
        kategorie_id=None,
        standort_id=standort,
        fahrzeug_id=None,
        status="im_dienst",
        interne_kennung="IK",
        stk_intervall=12,
        mtk_intervall=24,
        stk_aktiv=True,
        mtk_aktiv=True,
        letzte_stk=None,
        letzte_mtk=None,
        naechste_stk=None,
        naechste_mtk=None,
        lagerort="",
        produkt_typ_id=None,
        produkt_modell_id=None,
        produkt_hersteller_id=None,
        informationstext="",
    )
    manager.add_or_update_product(**kwargs)
    with pytest.raises(Exception):
        manager.add_or_update_product(**kwargs)
