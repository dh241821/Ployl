"""Product and repair submission endpoints for the PWA."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_session
from ..models import Kategorie, Kontakt, Produkt, Reparatur, Standort, Fahrzeug
from ..schemas import (
    Choice,
    ProductReferenceData,
    ProduktCreateRequest,
    ProduktRead,
    RepairCreateRequest,
    RepairRead,
    StatusChoice,
)
from ..services.audit import audit_context

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=List[ProduktRead])
def list_products(
    session: Session = Depends(get_session),
    _user=Depends(get_current_user),
) -> List[ProduktRead]:
    """Return all products for selection lists."""

    return session.query(Produkt).order_by(Produkt.name.asc()).all()


@router.get("/references", response_model=ProductReferenceData)
def product_references(
    session: Session = Depends(get_session),
    _user=Depends(get_current_user),
) -> ProductReferenceData:
    """Provide dropdown data for the HTML forms."""

    locations = session.query(Standort).order_by(Standort.land, Standort.bereich, Standort.bezirk).all()
    vehicles = session.query(Fahrzeug).order_by(Fahrzeug.name.asc()).all()
    categories = session.query(Kategorie).order_by(Kategorie.name.asc()).all()
    contacts = session.query(Kontakt).order_by(Kontakt.name.asc()).all()
    products = session.query(Produkt).order_by(Produkt.name.asc()).all()

    return ProductReferenceData(
        locations=[Choice(id=loc.id, label=_format_location(loc)) for loc in locations],
        vehicles=[Choice(id=vehicle.id, label=_format_vehicle(vehicle)) for vehicle in vehicles],
        categories=[Choice(id=cat.id, label=f"{cat.name} ({cat.typ})") for cat in categories],
        contacts=[Choice(id=contact.id, label=contact.name) for contact in contacts],
        products=[Choice(id=produkt.id, label=_format_product(produkt)) for produkt in products],
        statuses=[
            StatusChoice(value="im_dienst", label="Im Dienst"),
            StatusChoice(value="in_reparatur", label="In Reparatur"),
            StatusChoice(value="ausgeschieden", label="Ausgeschieden"),
        ],
    )


@router.post("", response_model=ProduktRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProduktCreateRequest,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
) -> ProduktRead:
    """Create a product based on the submitted form payload."""

    existing = session.query(Produkt).filter(Produkt.seriennummer == payload.seriennummer).first()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Seriennummer ist bereits vergeben")

    name = payload.name or _derive_product_name(payload)
    status_value = payload.status or "im_dienst"

    produkt = Produkt(
        name=name,
        typ=payload.typ,
        seriennummer=payload.seriennummer,
        hersteller=payload.hersteller,
        anschaffungsdatum=payload.anschaffungsdatum,
        kategorie_id=payload.kategorie_id,
        standort_id=payload.standort_id,
        fahrzeug_id=payload.fahrzeug_id,
        status=status_value,
        interne_kennung=payload.interne_kennung,
        stk_intervall=payload.stk_intervall or 12,
        mtk_intervall=payload.mtk_intervall or 24,
        letzte_stk=payload.letzte_stk,
        letzte_mtk=payload.letzte_mtk,
    )

    with audit_context(getattr(user, "username", "system")):
        session.add(produkt)
        session.commit()
        session.refresh(produkt)

    return produkt


@router.post("/{produkt_id}/repairs", response_model=RepairRead, status_code=status.HTTP_201_CREATED)
def create_repair(
    produkt_id: int,
    payload: RepairCreateRequest,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
) -> RepairRead:
    """Record a repair for a product."""

    produkt = session.get(Produkt, produkt_id)
    if not produkt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produkt nicht gefunden")

    reparatur = Reparatur(
        produkt_id=produkt_id,
        datum=payload.datum,
        kosten=payload.kosten,
        kontakt_id=payload.kontakt_id,
        beschreibung=payload.beschreibung,
        abgeschlossen=payload.abgeschlossen,
    )

    with audit_context(getattr(user, "username", "system")):
        session.add(reparatur)
        if payload.abgeschlossen:
            produkt.status = "im_dienst"
        elif payload.mark_as_in_repair:
            produkt.status = "in_reparatur"
        session.commit()
        session.refresh(reparatur)

    return reparatur


def _derive_product_name(payload: ProduktCreateRequest) -> str:
    parts = [value for value in (payload.typ, payload.hersteller) if value]
    if parts:
        return " ".join(parts)
    return payload.seriennummer


def _format_location(location: Standort) -> str:
    pieces = [location.land, location.bereich, location.bezirk, location.bezirksstelle, location.ortsstelle]
    label = " · ".join([piece for piece in pieces if piece])
    return label or f"Standort #{location.id}"


def _format_vehicle(vehicle: Fahrzeug) -> str:
    suffix = f" ({vehicle.kennzeichen})" if vehicle.kennzeichen else ""
    return f"{vehicle.name}{suffix}"


def _format_product(produkt: Produkt) -> str:
    serial = produkt.seriennummer or ""
    if serial:
        return f"{produkt.name} · SN {serial}"
    return produkt.name

