"""Lifecycle cost analytics helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Kostenbuchung, Produkt, Reparatur


@dataclass
class LifecycleCost:
    produkt_id: int
    produkt_name: str
    anschaffungskosten: float
    reparaturkosten: float
    laufende_kosten: float
    gesamtkosten: float
    roi: float
    kosten_pro_monat: float
    datenpunkte: int


class CostAnalyticsService:
    """Aggregate cost data to support decision making."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create_entry(
        self,
        *,
        produkt_id: Optional[int],
        fahrzeug_id: Optional[int],
        datum: date,
        betrag: float,
        typ: str,
        beschreibung: Optional[str],
        quelle: Optional[str],
    ) -> Kostenbuchung:
        entry = Kostenbuchung(
            produkt_id=produkt_id,
            fahrzeug_id=fahrzeug_id,
            datum=datum,
            betrag=betrag,
            typ=typ,
            beschreibung=beschreibung,
            quelle=quelle,
        )
        self.session.add(entry)
        self.session.flush()
        return entry

    def lifecycle_costs(self) -> List[LifecycleCost]:
        produkte = self.session.query(Produkt).all()
        summaries: List[LifecycleCost] = []

        for produkt in produkte:
            anschaffung = float(produkt.anschaffungskosten or 0.0)

            reparaturkosten = (
                self.session.query(func.coalesce(func.sum(Reparatur.kosten), 0.0))
                .filter(Reparatur.produkt_id == produkt.id)
                .scalar()
            )
            reparaturkosten = float(reparaturkosten or 0.0)

            laufende_kosten = (
                self.session.query(func.coalesce(func.sum(Kostenbuchung.betrag), 0.0))
                .filter(Kostenbuchung.produkt_id == produkt.id, Kostenbuchung.typ != "anschaffung")
                .scalar()
            )
            laufende_kosten = float(laufende_kosten or 0.0)

            gesamtkosten = anschaffung + reparaturkosten + laufende_kosten

            monate_im_dienst = 1
            if produkt.anschaffungsdatum:
                delta = (date.today() - produkt.anschaffungsdatum)
                monate_im_dienst = max(1, delta.days // 30)
            kosten_pro_monat = gesamtkosten / monate_im_dienst

            roi = 0.0
            if anschaffung:
                roi = (float(produkt.restwert or 0.0) - gesamtkosten) / anschaffung

            datenpunkte = (
                self.session.query(Kostenbuchung)
                .filter(Kostenbuchung.produkt_id == produkt.id)
                .count()
            )

            summaries.append(
                LifecycleCost(
                    produkt_id=produkt.id,
                    produkt_name=produkt.name,
                    anschaffungskosten=anschaffung,
                    reparaturkosten=reparaturkosten,
                    laufende_kosten=laufende_kosten,
                    gesamtkosten=gesamtkosten,
                    roi=roi,
                    kosten_pro_monat=kosten_pro_monat,
                    datenpunkte=datenpunkte,
                )
            )

        return summaries
