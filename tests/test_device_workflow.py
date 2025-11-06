from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.scheduler import maintenance_job

@pytest.mark.asyncio
async def test_full_device_workflow(client):
    # Create vehicle
    vehicle_payload = {
        "radio_id": "RTW-C-01",
        "vehicle_type": "RTW-C",
        "name": "RTW-C Unit 1",
    }
    vehicle_resp = await client.post("/vehicles/", json=vehicle_payload)
    assert vehicle_resp.status_code == 201, vehicle_resp.text
    vehicle_id = vehicle_resp.json()["id"]

    # Create device type with components
    device_type_payload = {
        "name": "Corpuls 3",
        "manufacturer": "GS",
        "model": "C3",
        "default_mtk_interval_days": 7,
        "default_stk_interval_days": 14,
        "is_composite": True,
        "components": [
            {"name": "Patientenmodul"},
            {"name": "Monitoreinheit"},
            {"name": "Therapieeinheit"},
        ],
    }
    device_type_resp = await client.post("/device-types/", json=device_type_payload)
    assert device_type_resp.status_code == 201, device_type_resp.text
    device_type_id = device_type_resp.json()["id"]

    components = device_type_resp.json()["components"]
    component_serials = {str(component["id"]): f"SERIAL-{component['name']}" for component in components}

    device_payload = {
        "inventory_number": "INV-1000",
        "device_type_id": device_type_id,
        "serial_number": "SN-1000",
        "component_serials": {int(k): v for k, v in component_serials.items()},
    }
    device_resp = await client.post("/devices/", json=device_payload)
    assert device_resp.status_code == 201, device_resp.text
    device_id = device_resp.json()["id"]

    # Assignment
    assignment_payload = {
        "device_id": device_id,
        "vehicle_id": vehicle_id,
        "assigned_by": "Techniker",
    }
    assignment_resp = await client.post("/assignments/", json=assignment_payload)
    assert assignment_resp.status_code == 201, assignment_resp.text

    # MTK check without due date -> auto compute
    past_date = date.today() - timedelta(days=10)
    check_payload = {
        "device_id": device_id,
        "check_type": "MTK",
        "performed_on": past_date.isoformat(),
        "performed_by": "Service GmbH",
        "result": "bestanden",
    }
    check_resp = await client.post("/checks/", json=check_payload)
    assert check_resp.status_code == 201, check_resp.text
    due_on = check_resp.json()["due_on"]
    assert due_on is not None

    # Repair log with attachment
    repair_payload = {
        "device_id": device_id,
        "reported_on": date.today().isoformat(),
        "reported_issue": "Defektes Kabel",
        "repair_action": "Austausch",
        "attachments": [
            {"file_path": "docs/repair1.pdf", "description": "Bericht"}
        ],
    }
    repair_resp = await client.post("/repairs/", json=repair_payload)
    assert repair_resp.status_code == 201, repair_resp.text
    repair_id = repair_resp.json()["id"]

    device_after_repair = await client.get(f"/devices/{device_id}")
    assert device_after_repair.status_code == 200
    assert device_after_repair.json()["status"] == "in_wartung"

    # Run maintenance job to create alert for overdue MTK
    await maintenance_job()

    alerts_resp = await client.get("/maintenance/alerts")
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert["severity"] == "critical"
    assert alert["days_until_due"] < 0

    ack_resp = await client.post(
        f"/maintenance/alerts/{alert['id']}", json={"acknowledged": True}
    )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["acknowledged_at"] is not None

    # Maintenance view should include the device when due within window (set to 365 days default -> due date 1 year)
    upcoming_resp = await client.get("/maintenance/upcoming", params={"days": 400})
    assert upcoming_resp.status_code == 200
    windows = upcoming_resp.json()
    assert any(window["device_id"] == device_id for window in windows)

    # Create follow-up check to resolve alert and create new warning
    new_check_payload = {
        "device_id": device_id,
        "check_type": "MTK",
        "performed_on": date.today().isoformat(),
        "performed_by": "Service GmbH",
        "result": "bestanden",
    }
    new_check_resp = await client.post("/checks/", json=new_check_payload)
    assert new_check_resp.status_code == 201, new_check_resp.text

    await maintenance_job()

    open_alerts_resp = await client.get("/maintenance/alerts")
    assert open_alerts_resp.status_code == 200
    open_alerts = open_alerts_resp.json()
    assert len(open_alerts) == 1
    new_alert = open_alerts[0]
    assert new_alert["severity"] == "warning"
    assert new_alert["days_until_due"] >= 0

    resolved_alerts_resp = await client.get(
        "/maintenance/alerts", params={"include_resolved": True}
    )
    resolved_alerts = resolved_alerts_resp.json()
    assert any(alert_row["resolved_at"] is not None for alert_row in resolved_alerts)

    # Device history contains records
    history_resp = await client.get(f"/devices/{device_id}/history")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert history["assignments"]
    assert history["safety_checks"]
    assert history["repairs"]

    # Complete repair and ensure status resets
    repair_update_resp = await client.patch(
        f"/repairs/{repair_id}", json={"repaired_on": date.today().isoformat()}
    )
    assert repair_update_resp.status_code == 200

    device_after_fix = await client.get(f"/devices/{device_id}")
    assert device_after_fix.status_code == 200
    assert device_after_fix.json()["status"] == "aktiv"
