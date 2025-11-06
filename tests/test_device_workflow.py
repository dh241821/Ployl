from __future__ import annotations

from datetime import date

import pytest

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
        "default_mtk_interval_days": 365,
        "default_stk_interval_days": 730,
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
    check_payload = {
        "device_id": device_id,
        "check_type": "MTK",
        "performed_on": date.today().isoformat(),
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

    # Maintenance view should include the device when due within window (set to 365 days default -> due date 1 year)
    upcoming_resp = await client.get("/maintenance/upcoming", params={"days": 400})
    assert upcoming_resp.status_code == 200
    windows = upcoming_resp.json()
    assert any(window["device_id"] == device_id for window in windows)

    # Device history contains records
    history_resp = await client.get(f"/devices/{device_id}/history")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert history["assignments"]
    assert history["safety_checks"]
    assert history["repairs"]
