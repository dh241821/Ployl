"""Endpoints supporting barcode/QR workflows."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_session
from ..models import Material, Produkt
from ..schemas import ScanResult

router = APIRouter(prefix="/api/scanner", tags=["scanner"])


@router.get("/lookup", response_model=ScanResult)
def lookup(payload: str, session: Session = Depends(get_session), user=Depends(get_current_user)) -> ScanResult:
    produkt = session.query(Produkt).filter(Produkt.qr_payload == payload).first()
    if produkt:
        return ScanResult(produkt=produkt, material_bestand=None, message="Produkt gefunden")
    material = session.query(Material).filter(Material.name == payload).first()
    if material:
        return ScanResult(produkt=None, material_bestand=material.ist_bestand, message="Materialbestand gefunden")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kein Eintrag für Scan gefunden")


@router.post("/transfer", response_model=ScanResult)
def transfer(payload: str, target_vehicle_id: int, session: Session = Depends(get_session), user=Depends(get_current_user)) -> ScanResult:
    produkt = session.query(Produkt).filter(Produkt.qr_payload == payload).first()
    if not produkt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produkt nicht gefunden")
    produkt.fahrzeug_id = target_vehicle_id
    session.add(produkt)
    session.commit()
    session.refresh(produkt)
    return ScanResult(produkt=produkt, material_bestand=None, message="Produkttransfer dokumentiert")
