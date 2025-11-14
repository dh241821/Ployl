"""Third-party integration helpers for HL7/FHIR/ERP connectors."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from sqlalchemy.orm import Session

from ..models import IntegrationEvent


class IntegrationService:
    """Persist integration events and build vendor specific payloads."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _create_event(self, integration: str, payload: Dict[str, Any], response: Dict[str, Any]) -> IntegrationEvent:
        event = IntegrationEvent(
            integration_type=integration,
            status="completed",
            payload=json.dumps(payload, default=str),
            response=json.dumps(response, default=str),
            correlation_id=uuid4().hex,
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def export_hl7(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a simple HL7 ORU^R01 message for device updates."""

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        message = "|".join(
            [
                "MSH",
                "^~\\&",
                "MEDSYS",
                payload.get("sending_facility", "HQ"),
                payload.get("receiving_application", "ERP"),
                payload.get("receiving_facility", "Supply"),
                timestamp,
                "",
                "ORU^R01",
                uuid4().hex,
                "P",
                "2.5",
            ]
        )
        obx = "|".join(
            [
                "OBX",
                "1",
                "TX",
                payload.get("observation_id", "DEVICE"),
                "1",
                payload.get("observation_value", "Update"),
                "",
                "",
                "F",
            ]
        )
        hl7_payload = f"{message}\r{obx}"
        response = {"hl7": hl7_payload, "generated_at": timestamp}
        event = self._create_event("hl7", payload, response)
        return {"correlation_id": event.correlation_id, "artifact": response, "status": event.status}

    def export_fhir(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resource = {
            "resourceType": "Device",
            "id": payload.get("id", uuid4().hex),
            "status": payload.get("status", "active"),
            "manufacturer": payload.get("manufacturer"),
            "type": {
                "text": payload.get("type", "Medical Device"),
            },
            "note": [{"text": payload.get("note", "")}] if payload.get("note") else [],
        }
        event = self._create_event("fhir", payload, resource)
        return {"correlation_id": event.correlation_id, "artifact": resource, "status": event.status}

    def sync_erp(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        summary = {
            "order_number": payload.get("order_number", uuid4().hex[:8]),
            "line_items": len(payload.get("items", [])),
            "total": sum(item.get("price", 0.0) * item.get("quantity", 1) for item in payload.get("items", [])),
            "status": "queued",
        }
        event = self._create_event("erp", payload, summary)
        return {"correlation_id": event.correlation_id, "artifact": summary, "status": event.status}

    def sync_inventory(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            "warehouse": payload.get("warehouse", "Zentrallager"),
            "synced_items": len(payload.get("materials", [])),
            "low_stock": [
                item
                for item in payload.get("materials", [])
                if item.get("ist_bestand", 0) < item.get("soll_bestand", 0)
            ],
        }
        event = self._create_event("lager", payload, result)
        return {"correlation_id": event.correlation_id, "artifact": result, "status": event.status}

