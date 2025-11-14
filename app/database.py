"""SQLite database management for the Medizinprodukte Management System."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import qrcode

DATABASE_FILE = Path("medizinprodukte.db")


@dataclass
class User:
    """Represents an authenticated user."""

    id: int
    username: str
    full_name: str
    role: str


class DatabaseManager:
    """High level database helper that wraps raw SQLite access."""

    def __init__(self, db_path: Path = DATABASE_FILE) -> None:
        self.db_path = db_path
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.initialize_schema()
        self.ensure_default_admin()

    # ------------------------------------------------------------------
    # schema
    # ------------------------------------------------------------------
    def initialize_schema(self) -> None:
        """Create all tables if they do not yet exist."""

        with self.connection:
            self.connection.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS benutzer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'benutzer'))
                );

                CREATE TABLE IF NOT EXISTS kategorien (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    typ TEXT NOT NULL CHECK(typ IN ('produkt', 'material'))
                );

                CREATE TABLE IF NOT EXISTS standorte (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    land TEXT,
                    bereich TEXT,
                    bezirk TEXT,
                    bezirksstelle TEXT,
                    ortsstelle TEXT,
                    beschreibung TEXT
                );

                CREATE TABLE IF NOT EXISTS kontakte (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    adresse TEXT,
                    telefon TEXT,
                    email TEXT,
                    kontaktperson TEXT
                );

                CREATE TABLE IF NOT EXISTS fahrzeuge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    kennzeichen TEXT,
                    marke TEXT,
                    typ TEXT,
                    kategorie TEXT,
                    inbetriebnahme TEXT,
                    standort_id INTEGER,
                    kilometerstand INTEGER DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'im_dienst',
                    FOREIGN KEY(standort_id) REFERENCES standorte(id)
                );

                CREATE TABLE IF NOT EXISTS fahrzeug_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fahrzeug_id INTEGER NOT NULL,
                    eintragstyp TEXT NOT NULL,
                    beschreibung TEXT,
                    zeitstempel TEXT NOT NULL,
                    FOREIGN KEY(fahrzeug_id) REFERENCES fahrzeuge(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS produkte (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    typ TEXT,
                    seriennummer TEXT UNIQUE NOT NULL,
                    hersteller TEXT,
                    anschaffungsdatum TEXT,
                    kategorie_id INTEGER,
                    standort_id INTEGER,
                    fahrzeug_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'im_dienst',
                    interne_kennung TEXT,
                    stk_intervall INTEGER DEFAULT 12,
                    mtk_intervall INTEGER DEFAULT 24,
                    letzte_stk TEXT,
                    letzte_mtk TEXT,
                    FOREIGN KEY(kategorie_id) REFERENCES kategorien(id),
                    FOREIGN KEY(standort_id) REFERENCES standorte(id),
                    FOREIGN KEY(fahrzeug_id) REFERENCES fahrzeuge(id)
                );

                CREATE TABLE IF NOT EXISTS produkt_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER NOT NULL,
                    eintragstyp TEXT NOT NULL,
                    beschreibung TEXT,
                    zeitstempel TEXT NOT NULL,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS produkt_komponenten (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    hersteller TEXT,
                    seriennummer TEXT,
                    anschaffungsdatum TEXT,
                    bemerkung TEXT,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS reparaturen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER NOT NULL,
                    datum TEXT NOT NULL,
                    kosten REAL,
                    kontakt_id INTEGER,
                    beschreibung TEXT,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE,
                    FOREIGN KEY(kontakt_id) REFERENCES kontakte(id)
                );

                CREATE TABLE IF NOT EXISTS ausscheidungen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER NOT NULL,
                    datum TEXT NOT NULL,
                    grund TEXT,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS wartungen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER NOT NULL,
                    geplanter_termin TEXT NOT NULL,
                    wartungstyp TEXT NOT NULL,
                    beschreibung TEXT,
                    durchgefuehrt_am TEXT,
                    durchgefuehrt_von TEXT,
                    bemerkung TEXT,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS verbrauchsmaterial (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    kategorie_id INTEGER,
                    lagerort TEXT,
                    soll_bestand INTEGER DEFAULT 0,
                    ist_bestand INTEGER DEFAULT 0,
                    verfallsdatum TEXT,
                    FOREIGN KEY(kategorie_id) REFERENCES kategorien(id)
                );
                """
            )

    def ensure_default_admin(self) -> None:
        """Create the default admin user if no users exist."""

        with self.connection:
            count = self.connection.execute("SELECT COUNT(*) FROM benutzer").fetchone()[0]
            if count:
                return
            password_hash = self.hash_password("admin")
            self.connection.execute(
                "INSERT INTO benutzer (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                ("admin", password_hash, "Administrator", "admin"),
            )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    @staticmethod
    def _parse_date(value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        return datetime.strptime(value, "%Y-%m-%d").date()

    @staticmethod
    def _format_date(value: Optional[date]) -> Optional[str]:
        if not value:
            return None
        return value.isoformat()

    def authenticate(self, username: str, password: str) -> Optional[User]:
        row = self.connection.execute(
            "SELECT id, username, full_name, role, password_hash FROM benutzer WHERE username = ?",
            (username,),
        ).fetchone()
        if not row:
            return None
        if row["password_hash"] != self.hash_password(password):
            return None
        return User(id=row["id"], username=row["username"], full_name=row["full_name"], role=row["role"])

    # ------------------------------------------------------------------
    # category and location management
    # ------------------------------------------------------------------
    def list_categories(self, typ: Optional[str] = None) -> List[sqlite3.Row]:
        query = "SELECT * FROM kategorien"
        params: Tuple[Any, ...] = ()
        if typ:
            query += " WHERE typ = ?"
            params = (typ,)
        return list(self.connection.execute(query, params))

    def add_category(self, name: str, typ: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO kategorien (name, typ) VALUES (?, ?)",
                (name, typ),
            )
            return int(cur.lastrowid)

    def list_locations(self) -> List[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM standorte ORDER BY land, bereich, bezirk"))

    def add_location(
        self,
        land: str,
        bereich: str,
        bezirk: str,
        bezirksstelle: str,
        ortsstelle: str,
        beschreibung: str,
    ) -> int:
        with self.connection:
            cur = self.connection.execute(
                """
                INSERT INTO standorte (land, bereich, bezirk, bezirksstelle, ortsstelle, beschreibung)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (land, bereich, bezirk, bezirksstelle, ortsstelle, beschreibung),
            )
        return int(cur.lastrowid)

    # ------------------------------------------------------------------
    # contacts
    # ------------------------------------------------------------------
    def list_contacts(self) -> List[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM kontakte ORDER BY name"))

    def add_or_update_contact(
        self,
        *,
        kontakt_id: Optional[int],
        name: str,
        adresse: str,
        telefon: str,
        email: str,
        kontaktperson: str,
    ) -> int:
        with self.connection:
            if kontakt_id:
                self.connection.execute(
                    """
                    UPDATE kontakte
                    SET name = ?, adresse = ?, telefon = ?, email = ?, kontaktperson = ?
                    WHERE id = ?
                    """,
                    (name, adresse, telefon, email, kontaktperson, kontakt_id),
                )
                return kontakt_id
            cur = self.connection.execute(
                """
                INSERT INTO kontakte (name, adresse, telefon, email, kontaktperson)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, adresse, telefon, email, kontaktperson),
            )
            return int(cur.lastrowid)

    # ------------------------------------------------------------------
    # vehicle management
    # ------------------------------------------------------------------
    def list_vehicles(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT f.*, s.ortsstelle AS standort_name
                FROM fahrzeuge AS f
                LEFT JOIN standorte AS s ON s.id = f.standort_id
                ORDER BY f.name
                """
            )
        )

    def add_or_update_vehicle(
        self,
        *,
        fahrzeug_id: Optional[int],
        name: str,
        kennzeichen: str,
        marke: str,
        typ: str,
        kategorie: str,
        inbetriebnahme: Optional[date],
        standort_id: Optional[int],
        kilometerstand: int,
        status: str,
    ) -> int:
        with self.connection:
            inbetriebnahme_str = self._format_date(inbetriebnahme)
            if fahrzeug_id:
                self.connection.execute(
                    """
                    UPDATE fahrzeuge
                    SET name = ?, kennzeichen = ?, marke = ?, typ = ?, kategorie = ?,
                        inbetriebnahme = ?, standort_id = ?, kilometerstand = ?, status = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        kennzeichen,
                        marke,
                        typ,
                        kategorie,
                        inbetriebnahme_str,
                        standort_id,
                        kilometerstand,
                        status,
                        fahrzeug_id,
                    ),
                )
                self.add_vehicle_log(fahrzeug_id, "aktualisiert", "Fahrzeugdaten aktualisiert")
                return fahrzeug_id
            cur = self.connection.execute(
                """
                INSERT INTO fahrzeuge (name, kennzeichen, marke, typ, kategorie, inbetriebnahme, standort_id, kilometerstand, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    kennzeichen,
                    marke,
                    typ,
                    kategorie,
                    inbetriebnahme_str,
                    standort_id,
                    kilometerstand,
                    status,
                ),
            )
            new_id = int(cur.lastrowid)
            self.add_vehicle_log(new_id, "angelegt", "Fahrzeug erstellt")
            return new_id

    def add_vehicle_log(self, fahrzeug_id: int, eintragstyp: str, beschreibung: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO fahrzeug_log (fahrzeug_id, eintragstyp, beschreibung, zeitstempel) VALUES (?, ?, ?, ?)",
                (fahrzeug_id, eintragstyp, beschreibung, datetime.now().isoformat()),
            )

    def vehicle_history(self, fahrzeug_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM fahrzeug_log WHERE fahrzeug_id = ? ORDER BY zeitstempel DESC",
                (fahrzeug_id,),
            )
        )

    # ------------------------------------------------------------------
    # product management
    # ------------------------------------------------------------------
    def list_products(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT p.*, k.name AS kategorie_name, s.ortsstelle AS standort_name, f.name AS fahrzeug_name
                FROM produkte AS p
                LEFT JOIN kategorien AS k ON k.id = p.kategorie_id
                LEFT JOIN standorte AS s ON s.id = p.standort_id
                LEFT JOIN fahrzeuge AS f ON f.id = p.fahrzeug_id
                ORDER BY p.name
                """
            )
        )

    def get_product(self, produkt_id: int) -> Optional[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT p.*, k.name AS kategorie_name, s.ortsstelle AS standort_name, f.name AS fahrzeug_name
            FROM produkte AS p
            LEFT JOIN kategorien AS k ON k.id = p.kategorie_id
            LEFT JOIN standorte AS s ON s.id = p.standort_id
            LEFT JOIN fahrzeuge AS f ON f.id = p.fahrzeug_id
            WHERE p.id = ?
            """,
            (produkt_id,),
        ).fetchone()

    def add_or_update_product(
        self,
        *,
        produkt_id: Optional[int],
        name: str,
        typ: str,
        seriennummer: str,
        hersteller: str,
        anschaffungsdatum: Optional[date],
        kategorie_id: Optional[int],
        standort_id: Optional[int],
        fahrzeug_id: Optional[int],
        status: str,
        interne_kennung: str,
        stk_intervall: int,
        mtk_intervall: int,
    ) -> int:
        anschaffungsdatum_str = self._format_date(anschaffungsdatum)
        with self.connection:
            if produkt_id:
                self.connection.execute(
                    """
                    UPDATE produkte
                    SET name = ?, typ = ?, seriennummer = ?, hersteller = ?, anschaffungsdatum = ?,
                        kategorie_id = ?, standort_id = ?, fahrzeug_id = ?, status = ?, interne_kennung = ?,
                        stk_intervall = ?, mtk_intervall = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        typ,
                        seriennummer,
                        hersteller,
                        anschaffungsdatum_str,
                        kategorie_id,
                        standort_id,
                        fahrzeug_id,
                        status,
                        interne_kennung,
                        stk_intervall,
                        mtk_intervall,
                        produkt_id,
                    ),
                )
                self.add_product_log(produkt_id, "aktualisiert", "Produktdaten aktualisiert")
                return produkt_id
            cur = self.connection.execute(
                """
                INSERT INTO produkte (
                    name, typ, seriennummer, hersteller, anschaffungsdatum, kategorie_id, standort_id,
                    fahrzeug_id, status, interne_kennung, stk_intervall, mtk_intervall
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    typ,
                    seriennummer,
                    hersteller,
                    anschaffungsdatum_str,
                    kategorie_id,
                    standort_id,
                    fahrzeug_id,
                    status,
                    interne_kennung,
                    stk_intervall,
                    mtk_intervall,
                ),
            )
            new_id = int(cur.lastrowid)
            self.add_product_log(new_id, "angelegt", "Produkt erstellt")
            return new_id

    def delete_product(self, produkt_id: int) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM produkte WHERE id = ?", (produkt_id,))

    def add_product_log(self, produkt_id: int, eintragstyp: str, beschreibung: str) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO produkt_log (produkt_id, eintragstyp, beschreibung, zeitstempel) VALUES (?, ?, ?, ?)",
                (produkt_id, eintragstyp, beschreibung, datetime.now().isoformat()),
            )

    def product_history(self, produkt_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM produkt_log WHERE produkt_id = ? ORDER BY zeitstempel DESC",
                (produkt_id,),
            )
        )

    def product_lifecycle_report(self, produkt_id: int) -> str:
        product = self.get_product(produkt_id)
        if not product:
            raise ValueError("Produkt nicht gefunden")

        components = self.list_components(produkt_id)
        repairs = self.list_repairs(produkt_id)
        maintenance = self.list_maintenance(produkt_id)
        history = self.product_history(produkt_id)

        qr = qrcode.make(f"produkt:{produkt_id}:{product['seriennummer']}")
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        qr_data = base64.b64encode(buffer.getvalue()).decode("ascii")

        def table(rows: List[sqlite3.Row], headers: Tuple[str, ...], row_builder) -> str:
            if not rows:
                return "<p>Keine Daten vorhanden.</p>"
            head_html = "".join(f"<th>{header}</th>" for header in headers)
            body_html = "".join(
                "<tr>" + "".join(f"<td>{value}</td>" for value in row_builder(row)) + "</tr>"
                for row in rows
            )
            return f"<table class='data'><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"

        html = [
            "<html><head><meta charset='utf-8'>",
            "<style>body{font-family:Arial,sans-serif;margin:2rem;}table{border-collapse:collapse;width:100%;margin-bottom:1.5rem;}th,td{border:1px solid #ccc;padding:0.5rem;text-align:left;}h1{margin-bottom:0;}h2{margin-top:2rem;}figure{float:right;margin:0 0 1rem 1rem;}</style>",
            "</head><body>",
            f"<h1>Produkt-Lebenslauf: {product['name']}</h1>",
            "<figure>",
            f"<img src='data:image/png;base64,{qr_data}' alt='QR Code' width='160' height='160'>",
            f"<figcaption>Seriennummer: {product['seriennummer']}</figcaption>",
            "</figure>",
            "<section>",
            "<h2>Produktdetails</h2>",
            "<table class='data'><tbody>",
        ]

        detail_rows = [
            ("Name", product["name"]),
            ("Typ/Modell", product["typ"] or ""),
            ("Hersteller", product["hersteller"] or ""),
            ("Seriennummer", product["seriennummer"]),
            ("Kategorie", product["kategorie_name"] or ""),
            ("Standort", product["standort_name"] or ""),
            ("Fahrzeug", product["fahrzeug_name"] or ""),
            ("Status", product["status"]),
            ("Interne Kennung", product["interne_kennung"] or ""),
            ("Anschaffungsdatum", product["anschaffungsdatum"] or ""),
            ("STK Intervall", f"{product['stk_intervall']} Monate"),
            ("MTK Intervall", f"{product['mtk_intervall']} Monate"),
        ]
        html.extend(f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in detail_rows)
        html.append("</tbody></table></section>")

        html.append("<section><h2>Komponenten</h2>")
        html.append(
            table(
                components,
                ("Name", "Hersteller", "Seriennummer", "Anschaffungsdatum", "Bemerkung"),
                lambda row: (
                    row["name"],
                    row["hersteller"] or "",
                    row["seriennummer"] or "",
                    row["anschaffungsdatum"] or "",
                    row["bemerkung"] or "",
                ),
            )
        )
        html.append("</section>")

        html.append("<section><h2>Reparaturen</h2>")
        html.append(
            table(
                repairs,
                ("Datum", "Kosten", "Dienstleister", "Beschreibung"),
                lambda row: (
                    row["datum"] or "",
                    f"{row['kosten']:.2f} €" if row["kosten"] is not None else "",
                    row["kontakt_name"] or "",
                    row["beschreibung"] or "",
                ),
            )
        )
        html.append("</section>")

        html.append("<section><h2>Wartungen</h2>")
        html.append(
            table(
                maintenance,
                ("Geplant", "Typ", "Durchgeführt", "Beschreibung"),
                lambda row: (
                    row["geplanter_termin"] or "",
                    row["wartungstyp"],
                    row["durchgefuehrt_am"] or "",
                    row["beschreibung"] or "",
                ),
            )
        )
        html.append("</section>")

        html.append("<section><h2>Verlauf</h2>")
        html.append(
            table(
                history,
                ("Zeitstempel", "Aktion", "Beschreibung"),
                lambda row: (
                    row["zeitstempel"],
                    row["eintragstyp"],
                    row["beschreibung"] or "",
                ),
            )
        )
        html.append("</section>")

        html.append("</body></html>")
        return "".join(html)

    # ------------------------------------------------------------------
    # components and repairs
    # ------------------------------------------------------------------
    def list_components(self, produkt_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM produkt_komponenten WHERE produkt_id = ? ORDER BY name",
                (produkt_id,),
            )
        )

    def add_or_update_component(
        self,
        *,
        komponent_id: Optional[int],
        produkt_id: int,
        name: str,
        hersteller: str,
        seriennummer: str,
        anschaffungsdatum: Optional[date],
        bemerkung: str,
    ) -> int:
        anschaffungsdatum_str = self._format_date(anschaffungsdatum)
        with self.connection:
            if komponent_id:
                self.connection.execute(
                    """
                    UPDATE produkt_komponenten
                    SET name = ?, hersteller = ?, seriennummer = ?, anschaffungsdatum = ?, bemerkung = ?
                    WHERE id = ?
                    """,
                    (name, hersteller, seriennummer, anschaffungsdatum_str, bemerkung, komponent_id),
                )
                return komponent_id
            cur = self.connection.execute(
                """
                INSERT INTO produkt_komponenten (produkt_id, name, hersteller, seriennummer, anschaffungsdatum, bemerkung)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (produkt_id, name, hersteller, seriennummer, anschaffungsdatum_str, bemerkung),
            )
            return int(cur.lastrowid)

    def list_repairs(self, produkt_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT r.*, k.name AS kontakt_name
                FROM reparaturen AS r
                LEFT JOIN kontakte AS k ON k.id = r.kontakt_id
                WHERE r.produkt_id = ?
                ORDER BY r.datum DESC
                """,
                (produkt_id,),
            )
        )

    def add_repair(
        self,
        *,
        produkt_id: int,
        datum: date,
        kosten: float,
        kontakt_id: Optional[int],
        beschreibung: str,
    ) -> int:
        with self.connection:
            cur = self.connection.execute(
                """
                INSERT INTO reparaturen (produkt_id, datum, kosten, kontakt_id, beschreibung)
                VALUES (?, ?, ?, ?, ?)
                """,
                (produkt_id, datum.isoformat(), kosten, kontakt_id, beschreibung),
            )
            self.connection.execute(
                "UPDATE produkte SET status = 'in_reparatur' WHERE id = ?",
                (produkt_id,),
            )
            self.add_product_log(produkt_id, "reparatur", beschreibung)
            return int(cur.lastrowid)

    # ------------------------------------------------------------------
    # material management
    # ------------------------------------------------------------------
    def list_materials(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT m.*, k.name AS kategorie_name
                FROM verbrauchsmaterial AS m
                LEFT JOIN kategorien AS k ON k.id = m.kategorie_id
                ORDER BY m.name
                """
            )
        )

    def add_or_update_material(
        self,
        *,
        material_id: Optional[int],
        name: str,
        kategorie_id: Optional[int],
        lagerort: str,
        soll_bestand: int,
        ist_bestand: int,
        verfallsdatum: Optional[date],
    ) -> int:
        verfallsdatum_str = self._format_date(verfallsdatum)
        with self.connection:
            if material_id:
                self.connection.execute(
                    """
                    UPDATE verbrauchsmaterial
                    SET name = ?, kategorie_id = ?, lagerort = ?, soll_bestand = ?, ist_bestand = ?, verfallsdatum = ?
                    WHERE id = ?
                    """,
                    (name, kategorie_id, lagerort, soll_bestand, ist_bestand, verfallsdatum_str, material_id),
                )
                return material_id
            cur = self.connection.execute(
                """
                INSERT INTO verbrauchsmaterial (name, kategorie_id, lagerort, soll_bestand, ist_bestand, verfallsdatum)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, kategorie_id, lagerort, soll_bestand, ist_bestand, verfallsdatum_str),
            )
            return int(cur.lastrowid)

    # ------------------------------------------------------------------
    # maintenance
    # ------------------------------------------------------------------
    def list_maintenance(self, produkt_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM wartungen WHERE produkt_id = ? ORDER BY geplanter_termin",
                (produkt_id,),
            )
        )

    def add_or_update_maintenance(
        self,
        *,
        wartung_id: Optional[int],
        produkt_id: int,
        geplanter_termin: date,
        wartungstyp: str,
        beschreibung: str,
        durchgefuehrt_am: Optional[date],
        durchgefuehrt_von: str,
        bemerkung: str,
    ) -> int:
        geplanter_str = geplanter_termin.isoformat()
        durchgefuehrt_str = self._format_date(durchgefuehrt_am)
        with self.connection:
            if wartung_id:
                self.connection.execute(
                    """
                    UPDATE wartungen
                    SET geplanter_termin = ?, wartungstyp = ?, beschreibung = ?, durchgefuehrt_am = ?,
                        durchgefuehrt_von = ?, bemerkung = ?
                    WHERE id = ?
                    """,
                    (
                        geplanter_str,
                        wartungstyp,
                        beschreibung,
                        durchgefuehrt_str,
                        durchgefuehrt_von,
                        bemerkung,
                        wartung_id,
                    ),
                )
                return wartung_id
            cur = self.connection.execute(
                """
                INSERT INTO wartungen (produkt_id, geplanter_termin, wartungstyp, beschreibung, durchgefuehrt_am, durchgefuehrt_von, bemerkung)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    produkt_id,
                    geplanter_str,
                    wartungstyp,
                    beschreibung,
                    durchgefuehrt_str,
                    durchgefuehrt_von,
                    bemerkung,
                ),
            )
            return int(cur.lastrowid)

    # ------------------------------------------------------------------
    # analytics helpers
    # ------------------------------------------------------------------
    def due_products(self) -> List[sqlite3.Row]:
        today_str = date.today().isoformat()
        return list(
            self.connection.execute(
                """
                SELECT p.*
                FROM produkte AS p
                LEFT JOIN wartungen AS w ON w.produkt_id = p.id
                WHERE (
                    p.status = 'im_dienst' AND (
                        (w.durchgefuehrt_am IS NULL AND w.geplanter_termin <= ?)
                        OR (
                            w.durchgefuehrt_am IS NOT NULL
                            AND DATE(w.durchgefuehrt_am, printf('+%d months', p.stk_intervall)) <= ?
                        )
                    )
                )
                GROUP BY p.id
                """,
                (today_str, today_str),
            )
        )

    def products_in_repair(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM produkte WHERE status = 'in_reparatur' ORDER BY name"
            )
        )

    def expired_materials(self) -> List[sqlite3.Row]:
        today_str = date.today().isoformat()
        return list(
            self.connection.execute(
                "SELECT * FROM verbrauchsmaterial WHERE verfallsdatum IS NOT NULL AND verfallsdatum < ?",
                (today_str,),
            )
        )

    def low_stock_materials(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM verbrauchsmaterial WHERE ist_bestand < soll_bestand"
            )
        )

    def product_status_counts(self) -> Dict[str, int]:
        rows = self.connection.execute(
            "SELECT status, COUNT(*) AS count FROM produkte GROUP BY status"
        ).fetchall()
        return {row["status"]: row["count"] for row in rows}

    # ------------------------------------------------------------------
    def export_products_as_csv(self) -> str:
        """Return CSV data for all products."""

        rows = self.list_products()
        headers = [
            "ID",
            "Name",
            "Typ",
            "Seriennummer",
            "Hersteller",
            "Anschaffungsdatum",
            "Kategorie",
            "Standort",
            "Fahrzeug",
            "Status",
            "Interne Kennung",
            "STK Intervall",
            "MTK Intervall",
        ]
        lines = [";".join(headers)]
        for row in rows:
            lines.append(
                ";".join(
                    [
                        str(row["id"]),
                        row["name"] or "",
                        row["typ"] or "",
                        row["seriennummer"] or "",
                        row["hersteller"] or "",
                        row["anschaffungsdatum"] or "",
                        row["kategorie_name"] or "",
                        row["standort_name"] or "",
                        row["fahrzeug_name"] or "",
                        row["status"] or "",
                        row["interne_kennung"] or "",
                        str(row["stk_intervall"]),
                        str(row["mtk_intervall"]),
                    ]
                )
            )
        return "\n".join(lines)

    def export_products_as_html(self) -> str:
        rows = self.list_products()
        html_rows = "".join(
            "<tr>"
            + "".join(
                f"<td>{value}</td>"
                for value in [
                    row["id"],
                    row["name"],
                    row["seriennummer"],
                    row["status"],
                    row["kategorie_name"] or "",
                    row["standort_name"] or "",
                    row["fahrzeug_name"] or "",
                ]
            )
            + "</tr>"
            for row in rows
        )
        return "".join(
            [
                "<html><head><meta charset='utf-8'>",
                "<style>body{font-family:Arial,sans-serif;margin:2rem;}table{border-collapse:collapse;width:100%;}th,td{border:1px solid #ccc;padding:0.5rem;text-align:left;}h1{margin-bottom:1rem;}</style>",
                "</head><body>",
                "<h1>Produktliste</h1>",
                "<table><thead><tr><th>ID</th><th>Name</th><th>Seriennummer</th><th>Status</th><th>Kategorie</th><th>Standort</th><th>Fahrzeug</th></tr></thead><tbody>",
                html_rows,
                "</tbody></table>",
                "</body></html>",
            ]
        )

    def export_maintenance_ics(self) -> str:
        rows = self.connection.execute(
            """
            SELECT w.id, w.geplanter_termin, w.wartungstyp, w.beschreibung, p.name AS produkt_name
            FROM wartungen AS w
            JOIN produkte AS p ON p.id = w.produkt_id
            WHERE w.geplanter_termin IS NOT NULL
            ORDER BY w.geplanter_termin
            """
        ).fetchall()
        now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Ployl//Medizinprodukte//DE"]
        for row in rows:
            start = datetime.strptime(row["geplanter_termin"], "%Y-%m-%d").strftime("%Y%m%d")
            summary = f"{row['produkt_name']} - {row['wartungstyp']}"
            description = (row["beschreibung"] or "").replace("\n", "\\n")
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:wartung-{row['id']}@ployl",
                    f"DTSTAMP:{now}",
                    f"DTSTART;VALUE=DATE:{start}",
                    f"SUMMARY:{summary}",
                    f"DESCRIPTION:{description}",
                    "END:VEVENT",
                ]
            )
        lines.append("END:VCALENDAR")
        return "\n".join(lines)

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.connection.close()
