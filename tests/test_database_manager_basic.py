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


def test_component_status_flow(tmp_path):
    manager = _create_db(tmp_path)
    standort = manager.add_location("AT", "B", "C", "D", "E", "Test")
    produkt_id = manager.add_or_update_product(
        produkt_id=None,
        name="Corpuls",
        typ="Defi",
        seriennummer="XYZ-123",
        hersteller="Corpuls",
        anschaffungsdatum=None,
        kategorie_id=None,
        standort_id=standort,
        fahrzeug_id=None,
        status="im_dienst",
        interne_kennung="IK-3",
        stk_intervall=12,
        mtk_intervall=24,
        stk_aktiv=True,
        mtk_aktiv=True,
        letzte_stk=None,
        letzte_mtk=None,
        naechste_stk=None,
        naechste_mtk=None,
        lagerort="Lager",
        produkt_typ_id=None,
        produkt_modell_id=None,
        produkt_hersteller_id=None,
        informationstext="",
    )
    component_id = manager.add_or_update_component(
        komponent_id=None,
        produkt_id=produkt_id,
        name="Akku",
        hersteller="Corpuls",
        seriennummer="AKKU-1",
        anschaffungsdatum=None,
        bemerkung="",
        komponententyp_id=None,
    )

    repair_id = manager.add_component_repair(
        komponent_id=component_id,
        datum=date(2024, 5, 1),
        kosten=125.0,
        kontakt_id=None,
        beschreibung="Werkstatt", 
        reparatur_art_id=None,
        benutzer_id=None,
    )
    component = manager.get_component(component_id)
    assert component["status"] == "in_reparatur"
    repairs = manager.list_component_repairs(component_id)
    assert any(row["id"] == repair_id for row in repairs)

    manager.complete_component_repair(component_id)
    component = manager.get_component(component_id)
    assert component["status"] == "im_dienst"

    manager.retire_component(component_id, datum=date(2024, 6, 1), grund="Defekt")
    component = manager.get_component(component_id)
    assert component["status"] == "ausgeschieden"

    results = manager.search_components(term="Akku")
    assert any(row["id"] == component_id for row in results)


def test_product_vehicle_history(tmp_path):
    manager = _create_db(tmp_path)
    standort = manager.add_location("AT", "B", "C", "D", "E", "Test")
    fahrzeug1 = manager.add_or_update_vehicle(
        fahrzeug_id=None,
        name="RTW 1",
        kennzeichen="RT-100",
        marke="Mercedes",
        typ="Sprinter",
        kategorie="RTW",
        inbetriebnahme=None,
        standort_id=standort,
        kilometerstand=0,
        status="im_dienst",
        marke_id=None,
        fahrzeugtyp_id=None,
        fahrzeugkategorie_id=None,
        ausserbetrieb=False,
        ausserbetriebnahme=None,
        fahrgestellnummer="VIN-1",
    )
    produkt_id = manager.add_or_update_product(
        produkt_id=None,
        name="Corpuls",
        typ="Defi",
        seriennummer="HX-1",
        hersteller="Corpuls",
        anschaffungsdatum=None,
        kategorie_id=None,
        standort_id=standort,
        fahrzeug_id=fahrzeug1,
        status="im_dienst",
        interne_kennung="IK-HX",
        stk_intervall=12,
        mtk_intervall=24,
        stk_aktiv=True,
        mtk_aktiv=True,
        letzte_stk=None,
        letzte_mtk=None,
        naechste_stk=None,
        naechste_mtk=None,
        lagerort="Lager",
        produkt_typ_id=None,
        produkt_modell_id=None,
        produkt_hersteller_id=None,
        informationstext="",
    )
    history = manager.list_product_vehicle_history(produkt_id)
    assert any(row["fahrzeug_id"] == fahrzeug1 for row in history)

    fahrzeug2 = manager.add_or_update_vehicle(
        fahrzeug_id=None,
        name="RTW 2",
        kennzeichen="RT-200",
        marke="Volkswagen",
        typ="Crafter",
        kategorie="RTW",
        inbetriebnahme=None,
        standort_id=standort,
        kilometerstand=0,
        status="im_dienst",
        marke_id=None,
        fahrzeugtyp_id=None,
        fahrzeugkategorie_id=None,
        ausserbetrieb=False,
        ausserbetriebnahme=None,
        fahrgestellnummer="VIN-2",
    )
    manager.add_or_update_product(
        produkt_id=produkt_id,
        name="Corpuls",
        typ="Defi",
        seriennummer="HX-1",
        hersteller="Corpuls",
        anschaffungsdatum=None,
        kategorie_id=None,
        standort_id=standort,
        fahrzeug_id=fahrzeug2,
        status="im_dienst",
        interne_kennung="IK-HX",
        stk_intervall=12,
        mtk_intervall=24,
        stk_aktiv=True,
        mtk_aktiv=True,
        letzte_stk=None,
        letzte_mtk=None,
        naechste_stk=None,
        naechste_mtk=None,
        lagerort="Lager",
        produkt_typ_id=None,
        produkt_modell_id=None,
        produkt_hersteller_id=None,
        informationstext="",
    )
    history = manager.list_product_vehicle_history(produkt_id)
    ids = {row["fahrzeug_id"] for row in history if row["fahrzeug_id"]}
    assert ids == {fahrzeug1, fahrzeug2}
    closed = [row for row in history if row["fahrzeug_id"] == fahrzeug1]
    assert closed and all(row["entfernt_am"] for row in closed)


def test_component_assignment_history(tmp_path):
    manager = _create_db(tmp_path)
    standort = manager.add_location("AT", "B", "C", "D", "E", "Test")
    fahrzeug1 = manager.add_or_update_vehicle(
        fahrzeug_id=None,
        name="KTW 1",
        kennzeichen="KT-10",
        marke="Ford",
        typ="Transit",
        kategorie="KTW",
        inbetriebnahme=None,
        standort_id=standort,
        kilometerstand=0,
        status="im_dienst",
        marke_id=None,
        fahrzeugtyp_id=None,
        fahrzeugkategorie_id=None,
        ausserbetrieb=False,
        ausserbetriebnahme=None,
        fahrgestellnummer="VIN-10",
    )
    produkt_id = manager.add_or_update_product(
        produkt_id=None,
        name="Monitor",
        typ="Corpuls",
        seriennummer="CMP-1",
        hersteller="Corpuls",
        anschaffungsdatum=None,
        kategorie_id=None,
        standort_id=standort,
        fahrzeug_id=fahrzeug1,
        status="im_dienst",
        interne_kennung="IK-CMP",
        stk_intervall=12,
        mtk_intervall=24,
        stk_aktiv=True,
        mtk_aktiv=True,
        letzte_stk=None,
        letzte_mtk=None,
        naechste_stk=None,
        naechste_mtk=None,
        lagerort="Zentrallager",
        produkt_typ_id=None,
        produkt_modell_id=None,
        produkt_hersteller_id=None,
        informationstext="",
    )
    component_id = manager.add_or_update_component(
        komponent_id=None,
        produkt_id=produkt_id,
        name="Akku",
        hersteller="Corpuls",
        seriennummer="AK-10",
        anschaffungsdatum=None,
        bemerkung="",
        komponententyp_id=None,
    )
    history = manager.list_component_assignment_history(component_id)
    assert history and history[0]["fahrzeug_id"] == fahrzeug1

    fahrzeug2 = manager.add_or_update_vehicle(
        fahrzeug_id=None,
        name="KTW 2",
        kennzeichen="KT-20",
        marke="MAN",
        typ="TGE",
        kategorie="KTW",
        inbetriebnahme=None,
        standort_id=standort,
        kilometerstand=0,
        status="im_dienst",
        marke_id=None,
        fahrzeugtyp_id=None,
        fahrzeugkategorie_id=None,
        ausserbetrieb=False,
        ausserbetriebnahme=None,
        fahrgestellnummer="VIN-20",
    )
    manager.add_or_update_product(
        produkt_id=produkt_id,
        name="Monitor",
        typ="Corpuls",
        seriennummer="CMP-1",
        hersteller="Corpuls",
        anschaffungsdatum=None,
        kategorie_id=None,
        standort_id=standort,
        fahrzeug_id=fahrzeug2,
        status="im_dienst",
        interne_kennung="IK-CMP",
        stk_intervall=12,
        mtk_intervall=24,
        stk_aktiv=True,
        mtk_aktiv=True,
        letzte_stk=None,
        letzte_mtk=None,
        naechste_stk=None,
        naechste_mtk=None,
        lagerort="Zentrallager",
        produkt_typ_id=None,
        produkt_modell_id=None,
        produkt_hersteller_id=None,
        informationstext="",
    )
    history = manager.list_component_assignment_history(component_id)
    assert history[0]["fahrzeug_id"] == fahrzeug2
    assert any(row["fahrzeug_id"] == fahrzeug1 for row in history)
    retired_entry = next(row for row in history if row["fahrzeug_id"] == fahrzeug1)
    assert retired_entry["entfernt_am"]
