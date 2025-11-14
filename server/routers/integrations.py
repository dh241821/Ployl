"""Integration endpoints for HL7, FHIR, ERP and warehouse systems."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_session
from ..services.integrations import IntegrationService
from ..schemas import IntegrationRequest, IntegrationResponse

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


@router.post("/dispatch", response_model=IntegrationResponse)
def dispatch_integration(
    request: IntegrationRequest,
    session: Session = Depends(get_session),
    _user=Depends(require_admin),
) -> IntegrationResponse:
    service = IntegrationService(session)
    handlers = {
        "hl7": service.export_hl7,
        "fhir": service.export_fhir,
        "erp": service.sync_erp,
        "lager": service.sync_inventory,
    }
    handler = handlers.get(request.integration)
    if not handler:  # pragma: no cover - validation should prevent this
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported integration")
    result = handler(request.payload)
    return IntegrationResponse(**result)

