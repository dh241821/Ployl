"""SQLAlchemy ORM models for the Medizinprodukte network backend."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class TimestampMixin:
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Benutzer(TimestampMixin, Base):
    __tablename__ = "benutzer"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default="benutzer")
    email = Column(String(120), nullable=True)


class Kategorie(Base):
    __tablename__ = "kategorien"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    typ = Column(String(32), nullable=False)


class Standort(Base):
    __tablename__ = "standorte"

    id = Column(Integer, primary_key=True)
    land = Column(String(50))
    bereich = Column(String(50))
    bezirk = Column(String(50))
    bezirksstelle = Column(String(50))
    ortsstelle = Column(String(50))
    beschreibung = Column(Text)


class Kontakt(Base):
    __tablename__ = "kontakte"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    adresse = Column(Text)
    telefon = Column(String(50))
    email = Column(String(120))
    kontaktperson = Column(String(120))


class Fahrzeug(TimestampMixin, Base):
    __tablename__ = "fahrzeuge"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    kennzeichen = Column(String(50))
    marke = Column(String(80))
    typ = Column(String(80))
    kategorie = Column(String(50))
    inbetriebnahme = Column(Date)
    standort_id = Column(Integer, ForeignKey("standorte.id"))
    kilometerstand = Column(Integer, default=0)
    status = Column(String(32), nullable=False, default="im_dienst")

    standort = relationship("Standort")
    produkte = relationship("Produkt", back_populates="fahrzeug")
    dokumente = relationship("Dokument", back_populates="fahrzeug", cascade="all,delete-orphan")
    kostenbuchungen = relationship("Kostenbuchung", back_populates="fahrzeug", cascade="all,delete-orphan")
    positionen = relationship("FahrzeugPosition", back_populates="fahrzeug", cascade="all,delete-orphan")


class FahrzeugLog(Base):
    __tablename__ = "fahrzeug_log"

    id = Column(Integer, primary_key=True)
    fahrzeug_id = Column(Integer, ForeignKey("fahrzeuge.id"), nullable=False)
    eintragstyp = Column(String(80), nullable=False)
    beschreibung = Column(Text)
    zeitstempel = Column(DateTime, default=datetime.utcnow, nullable=False)

    fahrzeug = relationship("Fahrzeug", backref="logeintraege")


class Produkt(TimestampMixin, Base):
    __tablename__ = "produkte"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    typ = Column(String(120))
    seriennummer = Column(String(120), unique=True, nullable=False)
    hersteller = Column(String(120))
    anschaffungsdatum = Column(Date)
    kategorie_id = Column(Integer, ForeignKey("kategorien.id"))
    standort_id = Column(Integer, ForeignKey("standorte.id"))
    fahrzeug_id = Column(Integer, ForeignKey("fahrzeuge.id"))
    status = Column(String(32), nullable=False, default="im_dienst")
    interne_kennung = Column(String(120))
    anschaffungskosten = Column(Float, default=0.0)
    restwert = Column(Float, default=0.0)
    nutzungsdauer_monate = Column(Integer, default=60)
    stk_intervall = Column(Integer, default=12)
    mtk_intervall = Column(Integer, default=24)
    letzte_stk = Column(Date)
    letzte_mtk = Column(Date)
    qr_payload = Column(String(255))

    kategorie = relationship("Kategorie")
    standort = relationship("Standort")
    fahrzeug = relationship("Fahrzeug", back_populates="produkte")
    komponenten = relationship("ProduktKomponente", back_populates="produkt", cascade="all,delete")
    reparaturen = relationship("Reparatur", back_populates="produkt", cascade="all,delete")
    wartungen = relationship("Wartung", back_populates="produkt", cascade="all,delete")
    dokumente = relationship("Dokument", back_populates="produkt", cascade="all,delete-orphan")
    kostenbuchungen = relationship("Kostenbuchung", back_populates="produkt", cascade="all,delete-orphan")
    planungs_insights = relationship("WartungsInsight", back_populates="produkt", cascade="all,delete-orphan")


class ProduktLog(Base):
    __tablename__ = "produkt_log"

    id = Column(Integer, primary_key=True)
    produkt_id = Column(Integer, ForeignKey("produkte.id"), nullable=False)
    eintragstyp = Column(String(80), nullable=False)
    beschreibung = Column(Text)
    zeitstempel = Column(DateTime, default=datetime.utcnow, nullable=False)

    produkt = relationship("Produkt", backref="logeintraege")


class ProduktKomponente(Base):
    __tablename__ = "produkt_komponenten"

    id = Column(Integer, primary_key=True)
    produkt_id = Column(Integer, ForeignKey("produkte.id"), nullable=False)
    name = Column(String(120), nullable=False)
    hersteller = Column(String(120))
    seriennummer = Column(String(120))
    anschaffungsdatum = Column(Date)
    bemerkung = Column(Text)

    produkt = relationship("Produkt", back_populates="komponenten")


class Reparatur(Base):
    __tablename__ = "reparaturen"

    id = Column(Integer, primary_key=True)
    produkt_id = Column(Integer, ForeignKey("produkte.id"), nullable=False)
    datum = Column(Date, nullable=False)
    kosten = Column(Float)
    kontakt_id = Column(Integer, ForeignKey("kontakte.id"))
    beschreibung = Column(Text)
    abgeschlossen = Column(Boolean, default=False)

    produkt = relationship("Produkt", back_populates="reparaturen")
    kontakt = relationship("Kontakt")


class Wartung(Base):
    __tablename__ = "wartungen"

    id = Column(Integer, primary_key=True)
    produkt_id = Column(Integer, ForeignKey("produkte.id"), nullable=False)
    geplantes_datum = Column(Date, nullable=False)
    typ = Column(String(80), nullable=False)
    beschreibung = Column(Text)
    durchgefuehrt_am = Column(Date)
    durchgefuehrt_von = Column(String(120))
    bemerkung = Column(Text)

    produkt = relationship("Produkt", back_populates="wartungen")


class Material(TimestampMixin, Base):
    __tablename__ = "verbrauchsmaterial"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    kategorie_id = Column(Integer, ForeignKey("kategorien.id"))
    lagerort = Column(String(120))
    soll_bestand = Column(Integer, default=0)
    ist_bestand = Column(Integer, default=0)
    verfallsdatum = Column(Date)

    kategorie = relationship("Kategorie")


class Ausscheidung(Base):
    __tablename__ = "ausscheidungen"

    id = Column(Integer, primary_key=True)
    produkt_id = Column(Integer, ForeignKey("produkte.id"), nullable=False)
    grund = Column(Text)
    datum = Column(Date, nullable=False)

    produkt = relationship("Produkt")


class Dokument(TimestampMixin, Base):
    __tablename__ = "dokumente"

    id = Column(Integer, primary_key=True)
    produkt_id = Column(Integer, ForeignKey("produkte.id"))
    fahrzeug_id = Column(Integer, ForeignKey("fahrzeuge.id"))
    titel = Column(String(200), nullable=False)
    original_name = Column(String(255))
    content_type = Column(String(80))
    dateipfad = Column(String(255), nullable=False)
    cloud_url = Column(String(255))
    tags = Column(Text)
    ocr_text = Column(Text)
    checksum = Column(String(64))

    produkt = relationship("Produkt", back_populates="dokumente")
    fahrzeug = relationship("Fahrzeug", back_populates="dokumente")


class Kostenbuchung(TimestampMixin, Base):
    __tablename__ = "kostenbuchungen"

    id = Column(Integer, primary_key=True)
    produkt_id = Column(Integer, ForeignKey("produkte.id"))
    fahrzeug_id = Column(Integer, ForeignKey("fahrzeuge.id"))
    datum = Column(Date, nullable=False)
    betrag = Column(Float, nullable=False)
    typ = Column(String(50), nullable=False)
    beschreibung = Column(Text)
    quelle = Column(String(120))

    produkt = relationship("Produkt", back_populates="kostenbuchungen")
    fahrzeug = relationship("Fahrzeug", back_populates="kostenbuchungen")


class WartungsInsight(TimestampMixin, Base):
    __tablename__ = "wartungs_insights"

    id = Column(Integer, primary_key=True)
    produkt_id = Column(Integer, ForeignKey("produkte.id"), nullable=False)
    modell_version = Column(String(40), nullable=False)
    prognose_datum = Column(Date, nullable=False)
    fenster_start = Column(Date, nullable=False)
    fenster_ende = Column(Date, nullable=False)
    konfidens = Column(Float, nullable=False)
    datenpunkte = Column(Integer, default=0)
    methode = Column(String(120))
    metadaten = Column(Text)

    produkt = relationship("Produkt", back_populates="planungs_insights")


class FahrzeugPosition(Base):
    __tablename__ = "fahrzeug_positionen"

    id = Column(Integer, primary_key=True)
    fahrzeug_id = Column(Integer, ForeignKey("fahrzeuge.id"), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy = Column(Float)
    zeitstempel = Column(DateTime, default=datetime.utcnow, nullable=False)

    fahrzeug = relationship("Fahrzeug", back_populates="positionen")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    entity_type = Column(String(80), nullable=False)
    entity_id = Column(Integer)
    action = Column(String(40), nullable=False)
    payload = Column(Text, nullable=False)
    benutzername = Column(String(120))
    signature = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
