from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from app.database import DatabaseManager
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency missing
    pytest.skip(f"Abhängigkeit fehlt: {exc}", allow_module_level=True)


def test_governance_features(tmp_path):
    db_path = tmp_path / "test.db"
    manager = DatabaseManager(db_path)
    manager.set_active_mandant(1)

    product_id = manager.add_or_update_product(
        produkt_id=None,
        name="Testgerät",
        typ="Monitor",
        seriennummer="SN-001",
        hersteller="Acme",
        anschaffungsdatum=None,
        kategorie_id=None,
        standort_id=None,
        fahrzeug_id=None,
        status="im_dienst",
        interne_kennung="IK-1",
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

    approval_id = manager.create_product_approval(
        produkt_id=product_id,
        schritt="Ersteinweisung",
        kommentar="",
        benutzer_id=None,
    )
    approvals = manager.list_product_approvals()
    assert any(row["id"] == approval_id for row in approvals)

    manager.update_product_approval_status(
        approval_id,
        status="genehmigt",
        benutzer_id=None,
        kommentar="ok",
    )

    capa_id = manager.create_capa_action(
        produkt_id=product_id,
        beschreibung="Prüfung dokumentieren",
        faellig_am=None,
        verantwortlicher_id=None,
    )
    capas = manager.list_capa_actions()
    assert any(row["id"] == capa_id for row in capas)

    regelwerk_id = manager.save_regelwerk(
        regelwerk_id=None,
        name="Demo-Regel",
        beschreibung="Test",
        intervall_monate=6,
    )
    assert any(row["id"] == regelwerk_id for row in manager.list_regelwerke())
    manager.assign_regelwerk_to_product(
        produkt_id=product_id,
        regelwerk_id=regelwerk_id,
        letzter_abgleich=None,
        naechster_abgleich=None,
    )

    verfahren = manager.list_verfahren()
    if verfahren:
        manager.confirm_training(benutzer_id=1, verfahren_id=verfahren[0]["id"])
        trainings = manager.list_user_trainings(1)
        assert trainings

    manager.save_dashboard_layout(1, {"kpi": True})
    layout = manager.load_dashboard_layout(1)
    assert layout and layout["kpi"]

    manager.save_filter_set(benutzer_id=1, bereich="produkte", name="Alle", daten={})
    assert manager.list_filter_sets(1, "produkte")

    manager.record_cockpit_snapshot({"ok": True})
    help_entries = manager.list_help_articles()
    assert help_entries
