"""SQLite database management for the Medizinprodukte Management System."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import io
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import qrcode

DATABASE_FILE = Path("medizinprodukte.db")

STATUS_LABELS: Dict[str, str] = {
    "im_dienst": "Im Dienst",
    "in_reparatur": "In Reparatur",
    "ausgeschieden": "Ausgeschieden",
}


PERMISSION_MODULES: List[Tuple[str, str]] = [
    ("standorte", "Standorte"),
    ("produkte", "Produkte"),
    ("material", "Material"),
    ("fahrzeuge", "Fahrzeuge"),
]

PERMISSION_COLUMNS: List[str] = [
    f"{module}_{suffix}"
    for module, _label in PERMISSION_MODULES
    for suffix in ("lesen", "schreiben")
]

PERMISSION_DEFAULTS: Dict[str, bool] = {column: True for column in PERMISSION_COLUMNS}


@dataclass
class LocationPermission:
    """Represents read/write permissions for a specific location."""

    standort_id: int
    lesen: bool
    schreiben: bool
    label: str = ""


@dataclass
class User:
    """Represents an authenticated user."""

    id: int
    username: str
    full_name: str
    role: str
    standorte_lesen: bool
    standorte_schreiben: bool
    produkte_lesen: bool
    produkte_schreiben: bool
    material_lesen: bool
    material_schreiben: bool
    fahrzeuge_lesen: bool
    fahrzeuge_schreiben: bool
    location_permissions: Dict[int, LocationPermission] = field(default_factory=dict)

    def can_read(self, module: str) -> bool:
        """Return whether the user is allowed to read the given module."""

        return bool(getattr(self, f"{module}_lesen", False))

    def can_write(self, module: str) -> bool:
        """Return whether the user is allowed to write the given module."""

        return bool(getattr(self, f"{module}_schreiben", False))

    def can_read_location(self, standort_id: Optional[int]) -> bool:
        """Return whether the user may read data for the given location."""

        if not self.location_permissions:
            return True
        if standort_id is None:
            return True
        permission = self.location_permissions.get(int(standort_id))
        return bool(permission and permission.lesen)

    def can_write_location(self, standort_id: Optional[int]) -> bool:
        """Return whether the user may write data for the given location."""

        if not self.location_permissions:
            return True
        if standort_id is None:
            return True
        permission = self.location_permissions.get(int(standort_id))
        return bool(permission and permission.schreiben)


class DatabaseManager:
    """High level database helper that wraps raw SQLite access."""

    def __init__(self, db_path: Path = DATABASE_FILE) -> None:
        self.db_path = db_path
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._location_cache: Dict[int, sqlite3.Row] = {}
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
                    role TEXT NOT NULL CHECK(role IN ('admin', 'benutzer')),
                    vorname TEXT,
                    nachname TEXT,
                    dienstnummer TEXT,
                    standorte_lesen INTEGER NOT NULL DEFAULT 1,
                    standorte_schreiben INTEGER NOT NULL DEFAULT 1,
                    produkte_lesen INTEGER NOT NULL DEFAULT 1,
                    produkte_schreiben INTEGER NOT NULL DEFAULT 1,
                    material_lesen INTEGER NOT NULL DEFAULT 1,
                    material_schreiben INTEGER NOT NULL DEFAULT 1,
                    fahrzeuge_lesen INTEGER NOT NULL DEFAULT 1,
                    fahrzeuge_schreiben INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS benutzer_standorte (
                    benutzer_id INTEGER NOT NULL,
                    standort_id INTEGER NOT NULL,
                    lesen INTEGER NOT NULL DEFAULT 1,
                    schreiben INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (benutzer_id, standort_id),
                    FOREIGN KEY(benutzer_id) REFERENCES benutzer(id) ON DELETE CASCADE,
                    FOREIGN KEY(standort_id) REFERENCES standorte(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS kategorien (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    typ TEXT NOT NULL CHECK(typ IN ('produkt', 'material'))
                );

                CREATE TABLE IF NOT EXISTS produkt_typen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS produkt_modelle (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    typ_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    FOREIGN KEY(typ_id) REFERENCES produkt_typen(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS produkt_hersteller (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS komponententypen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS reparatur_arten (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS upload_kategorien (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
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
                    kontaktperson TEXT,
                    unternehmen TEXT,
                    website TEXT,
                    info TEXT
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
                    ausserbetrieb INTEGER NOT NULL DEFAULT 0,
                    ausserbetriebnahme_datum TEXT,
                    marke_id INTEGER,
                    fahrzeugtyp_id INTEGER,
                    fahrzeugkategorie_id INTEGER,
                    FOREIGN KEY(standort_id) REFERENCES standorte(id)
                );

                CREATE TABLE IF NOT EXISTS fahrzeug_marken (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS fahrzeug_modelle (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    marke_id INTEGER,
                    name TEXT NOT NULL,
                    FOREIGN KEY(marke_id) REFERENCES fahrzeug_marken(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS fahrzeug_kategorien (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
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
                    naechste_stk TEXT,
                    naechste_mtk TEXT,
                    stk_aktiv INTEGER NOT NULL DEFAULT 1,
                    mtk_aktiv INTEGER NOT NULL DEFAULT 1,
                    lagerort TEXT,
                    produkt_typ_id INTEGER,
                    produkt_modell_id INTEGER,
                    informationstext TEXT,
                    FOREIGN KEY(kategorie_id) REFERENCES kategorien(id),
                    FOREIGN KEY(standort_id) REFERENCES standorte(id),
                    FOREIGN KEY(fahrzeug_id) REFERENCES fahrzeuge(id),
                    FOREIGN KEY(produkt_typ_id) REFERENCES produkt_typen(id) ON DELETE SET NULL,
                    FOREIGN KEY(produkt_modell_id) REFERENCES produkt_modelle(id) ON DELETE SET NULL
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
                     komponententyp_id INTEGER,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS reparaturen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER NOT NULL,
                    datum TEXT NOT NULL,
                    kosten REAL,
                    kontakt_id INTEGER,
                    beschreibung TEXT,
                    reparatur_art_id INTEGER,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE,
                    FOREIGN KEY(kontakt_id) REFERENCES kontakte(id),
                    FOREIGN KEY(reparatur_art_id) REFERENCES reparatur_arten(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS reparatur_dateien (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reparatur_id INTEGER NOT NULL,
                    dateiname TEXT NOT NULL,
                    speicherpfad TEXT NOT NULL,
                    upload_kategorie_id INTEGER,
                    FOREIGN KEY(reparatur_id) REFERENCES reparaturen(id) ON DELETE CASCADE,
                    FOREIGN KEY(upload_kategorie_id) REFERENCES upload_kategorien(id) ON DELETE SET NULL
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

                CREATE TABLE IF NOT EXISTS material_bezeichnungen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS benutzer_einstellungen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    benutzer_id INTEGER NOT NULL,
                    schluessel TEXT NOT NULL,
                    wert TEXT NOT NULL,
                    UNIQUE(benutzer_id, schluessel),
                    FOREIGN KEY(benutzer_id) REFERENCES benutzer(id) ON DELETE CASCADE
                );
                """
            )

        self._seed_defaults()
        self._ensure_columns()
        self._backfill_product_manufacturers()

    def _ensure_columns(self) -> None:
        self._ensure_column("produkte", "naechste_stk", "TEXT")
        self._ensure_column("produkte", "naechste_mtk", "TEXT")
        self._ensure_column("produkte", "stk_aktiv", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column("produkte", "mtk_aktiv", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column("produkte", "lagerort", "TEXT")
        self._ensure_column("produkte", "produkt_typ_id", "INTEGER REFERENCES produkt_typen(id)")
        self._ensure_column("produkte", "produkt_modell_id", "INTEGER REFERENCES produkt_modelle(id)")
        self._ensure_column(
            "produkte",
            "produkt_hersteller_id",
            "INTEGER REFERENCES produkt_hersteller(id)",
        )
        self._ensure_column("produkte", "informationstext", "TEXT")

        self._ensure_column("fahrzeuge", "ausserbetrieb", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("fahrzeuge", "ausserbetriebnahme_datum", "TEXT")
        self._ensure_column("fahrzeuge", "marke_id", "INTEGER REFERENCES fahrzeug_marken(id)")
        self._ensure_column("fahrzeuge", "fahrzeugtyp_id", "INTEGER REFERENCES fahrzeug_modelle(id)")
        self._ensure_column("fahrzeuge", "fahrzeugkategorie_id", "INTEGER REFERENCES fahrzeug_kategorien(id)")

        self._ensure_column("produkt_komponenten", "komponententyp_id", "INTEGER REFERENCES komponententypen(id)")
        self._ensure_column("reparaturen", "reparatur_art_id", "INTEGER REFERENCES reparatur_arten(id)")

        self._ensure_column("benutzer", "vorname", "TEXT")
        self._ensure_column("benutzer", "nachname", "TEXT")
        self._ensure_column("benutzer", "dienstnummer", "TEXT")
        for column in PERMISSION_COLUMNS:
            self._ensure_column("benutzer", column, "INTEGER NOT NULL DEFAULT 1")

        self._ensure_column("kontakte", "unternehmen", "TEXT")
        self._ensure_column("kontakte", "website", "TEXT")
        self._ensure_column("kontakte", "info", "TEXT")

    def _backfill_product_manufacturers(self) -> None:
        with self.connection:
            existing: Dict[str, int] = {
                row["name"]: int(row["id"])
                for row in self.connection.execute(
                    "SELECT id, name FROM produkt_hersteller"
                )
            }
            for (name,) in self.connection.execute(
                "SELECT DISTINCT hersteller FROM produkte "
                "WHERE hersteller IS NOT NULL AND TRIM(hersteller) <> ''"
            ):
                trimmed = name.strip()
                if trimmed and trimmed not in existing:
                    cur = self.connection.execute(
                        "INSERT OR IGNORE INTO produkt_hersteller (name) VALUES (?)",
                        (trimmed,),
                    )
                    if cur.lastrowid:
                        existing[trimmed] = int(cur.lastrowid)
                    else:
                        row = self.connection.execute(
                            "SELECT id FROM produkt_hersteller WHERE name = ?",
                            (trimmed,),
                        ).fetchone()
                        if row:
                            existing[trimmed] = int(row["id"])

            for row in self.connection.execute(
                "SELECT id, hersteller FROM produkte "
                "WHERE produkt_hersteller_id IS NULL AND hersteller IS NOT NULL "
                "AND TRIM(hersteller) <> ''"
            ):
                hersteller_name = row["hersteller"].strip()
                hersteller_id = existing.get(hersteller_name)
                if hersteller_id:
                    self.connection.execute(
                        "UPDATE produkte SET produkt_hersteller_id = ? WHERE id = ?",
                        (hersteller_id, row["id"]),
                    )

    def _seed_defaults(self) -> None:
        with self.connection:
            existing = {
                row[0]
                for row in self.connection.execute("SELECT name FROM fahrzeug_kategorien")
            }
            for eintrag in ["RTW-C", "RTW", "KTW", "BKTW", "NEF", "BEL", "MTF", "Sonstiges"]:
                if eintrag not in existing:
                    self.connection.execute(
                        "INSERT INTO fahrzeug_kategorien (name) VALUES (?)",
                        (eintrag,),
                    )

            if not list(self.connection.execute("SELECT id FROM upload_kategorien")):
                for name in ["Rechnung", "Bild", "Protokoll", "Sonstiges"]:
                    self.connection.execute(
                        "INSERT INTO upload_kategorien (name) VALUES (?)",
                        (name,),
                    )

            if not list(self.connection.execute("SELECT id FROM reparatur_arten")):
                for name in ["Elektronik", "Mechanik", "Software", "Kalibrierung"]:
                    self.connection.execute(
                        "INSERT INTO reparatur_arten (name) VALUES (?)",
                        (name,),
                    )

            if not list(self.connection.execute("SELECT id FROM standorte")):
                bereichs_map = {
                    "Waldviertel": [
                        "Gmünd",
                        "Horn",
                        "Krems (Land)",
                        "Krems (Stadt)",
                        "Waidhofen an der Thaya",
                        "Zwettl",
                    ],
                    "Weinviertel": [
                        "Gänserndorf",
                        "Hollabrunn",
                        "Korneuburg",
                        "Mistelbach",
                    ],
                    "Mostviertel": [
                        "Amstetten",
                        "Lilienfeld",
                        "Melk",
                        "Scheibbs",
                        "St. Pölten (Land)",
                        "St. Pölten (Stadt)",
                        "Waidhofen an der Ybbs",
                    ],
                    "Industrieviertel": [
                        "Baden",
                        "Bruck an der Leitha",
                        "Mödling",
                        "Neunkirchen",
                        "Tulln",
                        "Wiener Neustadt (Land)",
                        "Wiener Neustadt (Stadt)",
                    ],
                    "Katastrophenhilfsdienst": ["Landesweit"],
                }
                for bereich, bezirke in bereichs_map.items():
                    for bezirk in bezirke:
                        self.connection.execute(
                            """
                            INSERT INTO standorte (land, bereich, bezirk, bezirksstelle, ortsstelle, beschreibung)
                            VALUES (?, ?, ?, ?, ?, ?)
                            """,
                            ("Niederösterreich", bereich, bezirk, "", "", ""),
                        )

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        cur = self.connection.execute(f"PRAGMA table_info({table})")
        if column in {row[1] for row in cur.fetchall()}:
            return
        self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _location_label_from_row(row: sqlite3.Row, prefix: str = "") -> str:
        parts: List[str] = []
        for key in ("land", "bereich", "bezirk", "bezirksstelle", "ortsstelle"):
            column = f"{prefix}{key}" if prefix else key
            if column in row.keys():
                value = row[column]
                if value:
                    parts.append(value)
        return " / ".join(parts)

    def location_label(self, standort_id: Optional[int]) -> str:
        if not standort_id:
            return ""
        if standort_id not in self._location_cache:
            row = self.connection.execute(
                "SELECT * FROM standorte WHERE id = ?",
                (standort_id,),
            ).fetchone()
            if not row:
                return ""
            self._location_cache[standort_id] = row
        return self._location_label_from_row(self._location_cache[standort_id])

    def location_label_from_product(self, row: sqlite3.Row) -> str:
        if "standort_id" in row.keys() and row["standort_id"]:
            return self.location_label(int(row["standort_id"]))
        if any(
            key in row.keys()
            for key in (
                "standort_land",
                "standort_bereich",
                "standort_bezirk",
                "standort_bezirksstelle",
                "standort_ortsstelle",
            )
        ):
            return self._location_label_from_row(row, prefix="standort_")
        return ""

    def ensure_default_admin(self) -> None:
        """Create the default admin user if no users exist."""

        with self.connection:
            count = self.connection.execute("SELECT COUNT(*) FROM benutzer").fetchone()[0]
            if count:
                return
            password_hash = self.hash_password("admin")
            columns_sql = ", ".join(PERMISSION_COLUMNS)
            placeholders = ", ".join(["?"] * len(PERMISSION_COLUMNS))
            permission_values = [1 if PERMISSION_DEFAULTS[column] else 0 for column in PERMISSION_COLUMNS]
            self.connection.execute(
                f"""
                INSERT INTO benutzer (username, password_hash, full_name, role, vorname, nachname, dienstnummer, {columns_sql})
                VALUES (?, ?, ?, ?, ?, ?, ?, {placeholders})
                """,
                ("admin", password_hash, "Administrator", "admin", "Admin", "Account", "0000", *permission_values),
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

    def authenticate(
        self, username: str, password: str, *, identifier: Optional[str] = None
    ) -> Optional[User]:
        row: Optional[sqlite3.Row] = None
        columns_sql = ", ".join(PERMISSION_COLUMNS)
        if identifier:
            row = self.connection.execute(
                f"""
                SELECT id, username, full_name, role, password_hash, {columns_sql}
                FROM benutzer
                WHERE dienstnummer = ? COLLATE NOCASE
                """,
                (identifier,),
            ).fetchone()
        if not row:
            row = self.connection.execute(
                f"SELECT id, username, full_name, role, password_hash, {columns_sql} FROM benutzer WHERE username = ?",
                (username,),
            ).fetchone()
        if not row:
            return None
        if row["password_hash"] != self.hash_password(password):
            return None
        permission_kwargs = {column: bool(row[column]) for column in PERMISSION_COLUMNS}
        location_entries = self.list_user_location_permissions(row["id"])
        location_permissions = {
            entry["standort_id"]: LocationPermission(
                standort_id=entry["standort_id"],
                lesen=entry["lesen"],
                schreiben=entry["schreiben"],
                label=entry["label"],
            )
            for entry in location_entries
        }
        return User(
            id=row["id"],
            username=row["username"],
            full_name=row["full_name"],
            role=row["role"],
            **permission_kwargs,
            location_permissions=location_permissions,
        )

    def list_user_identifiers(self) -> List[Dict[str, str]]:
        rows = self.connection.execute(
            """
            SELECT username, full_name, COALESCE(dienstnummer, username) AS identifier
            FROM benutzer
            ORDER BY identifier COLLATE NOCASE
            """
        ).fetchall()
        return [
            {
                "username": row["username"],
                "full_name": row["full_name"],
                "identifier": row["identifier"] or row["username"],
            }
            for row in rows
        ]

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

    def list_product_types(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM produkt_typen ORDER BY name")
        )

    def add_product_type(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO produkt_typen (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def delete_product_type(self, typ_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM produkt_typen WHERE id = ?",
                (typ_id,),
            )

    def list_product_models(self, typ_id: Optional[int] = None) -> List[sqlite3.Row]:
        query = (
            "SELECT pm.*, pt.name AS typ_name FROM produkt_modelle AS pm "
            "LEFT JOIN produkt_typen AS pt ON pt.id = pm.typ_id"
        )
        params: Tuple[Any, ...] = ()
        if typ_id:
            query += " WHERE pm.typ_id = ?"
            params = (typ_id,)
        query += " ORDER BY name"
        return list(self.connection.execute(query, params))

    def add_product_model(self, typ_id: int, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO produkt_modelle (typ_id, name) VALUES (?, ?)",
                (typ_id, name),
            )
            return int(cur.lastrowid)

    def delete_product_model(self, modell_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM produkt_modelle WHERE id = ?",
                (modell_id,),
            )

    def list_product_manufacturers(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM produkt_hersteller ORDER BY name")
        )

    def add_product_manufacturer(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO produkt_hersteller (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def delete_product_manufacturer(self, hersteller_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM produkt_hersteller WHERE id = ?",
                (hersteller_id,),
            )

    def list_component_types(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM komponententypen ORDER BY name")
        )

    def add_component_type(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO komponententypen (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def delete_component_type(self, typ_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM komponententypen WHERE id = ?",
                (typ_id,),
            )

    def list_repair_types(self) -> List[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM reparatur_arten ORDER BY name"))

    def add_repair_type(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO reparatur_arten (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def delete_repair_type(self, typ_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM reparatur_arten WHERE id = ?",
                (typ_id,),
            )

    def list_upload_categories(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM upload_kategorien ORDER BY name")
        )

    def add_upload_category(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO upload_kategorien (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def delete_upload_category(self, category_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM upload_kategorien WHERE id = ?",
                (category_id,),
            )

    def list_material_names(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM material_bezeichnungen ORDER BY name")
        )

    def add_material_name(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO material_bezeichnungen (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def delete_material_name(self, name_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM material_bezeichnungen WHERE id = ?",
                (name_id,),
            )

    def _ensure_material_name_entry(self, name: str) -> None:
        trimmed = name.strip()
        if not trimmed:
            return
        existing = self.connection.execute(
            "SELECT id FROM material_bezeichnungen WHERE name = ?",
            (trimmed,),
        ).fetchone()
        if not existing:
            self.add_material_name(trimmed)

    def list_vehicle_brands(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM fahrzeug_marken ORDER BY name")
        )

    def add_vehicle_brand(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO fahrzeug_marken (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def delete_vehicle_brand(self, brand_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM fahrzeug_marken WHERE id = ?",
                (brand_id,),
            )

    def list_vehicle_models(self, marke_id: Optional[int] = None) -> List[sqlite3.Row]:
        query = (
            "SELECT fm.*, mb.name AS marke_name FROM fahrzeug_modelle AS fm "
            "LEFT JOIN fahrzeug_marken AS mb ON mb.id = fm.marke_id"
        )
        params: Tuple[Any, ...] = ()
        if marke_id:
            query += " WHERE fm.marke_id = ?"
            params = (marke_id,)
        query += " ORDER BY name"
        return list(self.connection.execute(query, params))

    def add_vehicle_model(self, marke_id: Optional[int], name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO fahrzeug_modelle (marke_id, name) VALUES (?, ?)",
                (marke_id, name),
            )
            return int(cur.lastrowid)

    def delete_vehicle_model(self, model_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM fahrzeug_modelle WHERE id = ?",
                (model_id,),
            )

    def list_vehicle_categories(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM fahrzeug_kategorien ORDER BY name")
        )

    def add_vehicle_category(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO fahrzeug_kategorien (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def delete_vehicle_category(self, category_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM fahrzeug_kategorien WHERE id = ?",
                (category_id,),
            )

    def get_user_preferences(self, benutzer_id: int) -> Dict[str, str]:
        rows = self.connection.execute(
            "SELECT schluessel, wert FROM benutzer_einstellungen WHERE benutzer_id = ?",
            (benutzer_id,),
        ).fetchall()
        return {row["schluessel"]: row["wert"] for row in rows}

    def set_user_preference(self, benutzer_id: int, schluessel: str, wert: str) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO benutzer_einstellungen (benutzer_id, schluessel, wert)
                VALUES (?, ?, ?)
                ON CONFLICT(benutzer_id, schluessel) DO UPDATE SET wert = excluded.wert
                """,
                (benutzer_id, schluessel, wert),
            )

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
        self._location_cache.clear()
        return int(cur.lastrowid)

    def get_location(self, location_id: int) -> Optional[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM standorte WHERE id = ?",
            (location_id,),
        ).fetchone()

    def update_location(
        self,
        location_id: int,
        land: str,
        bereich: str,
        bezirk: str,
        bezirksstelle: str,
        ortsstelle: str,
        beschreibung: str,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE standorte
                SET land = ?, bereich = ?, bezirk = ?, bezirksstelle = ?, ortsstelle = ?, beschreibung = ?
                WHERE id = ?
                """,
                (land, bereich, bezirk, bezirksstelle, ortsstelle, beschreibung, location_id),
            )
        self._location_cache.clear()

    def delete_location(self, location_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM standorte WHERE id = ?",
                (location_id,),
            )
        self._location_cache.clear()

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
        unternehmen: str,
        website: str,
        info: str,
    ) -> int:
        with self.connection:
            if kontakt_id:
                self.connection.execute(
                    """
                    UPDATE kontakte
                    SET name = ?, adresse = ?, telefon = ?, email = ?, kontaktperson = ?,
                        unternehmen = ?, website = ?, info = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        adresse,
                        telefon,
                        email,
                        kontaktperson,
                        unternehmen,
                        website,
                        info,
                        kontakt_id,
                    ),
                )
                return kontakt_id
            cur = self.connection.execute(
                """
                INSERT INTO kontakte (name, adresse, telefon, email, kontaktperson, unternehmen, website, info)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, adresse, telefon, email, kontaktperson, unternehmen, website, info),
            )
        return int(cur.lastrowid)

    def delete_contact(self, kontakt_id: int) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM kontakte WHERE id = ?", (kontakt_id,))

    # ------------------------------------------------------------------
    # vehicle management
    # ------------------------------------------------------------------
    def list_vehicles(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT f.*,
                       s.land AS standort_land,
                       s.bereich AS standort_bereich,
                       s.bezirk AS standort_bezirk,
                       s.bezirksstelle AS standort_bezirksstelle,
                       s.ortsstelle AS standort_ortsstelle,
                       COALESCE(s.ortsstelle, s.bezirksstelle, s.bezirk, s.bereich, s.land, '') AS standort_name,
                       fm.name AS marke_name,
                       fmo.name AS fahrzeug_typ_name,
                       fk.name AS fahrzeug_kategorie_name
                FROM fahrzeuge AS f
                LEFT JOIN standorte AS s ON s.id = f.standort_id
                LEFT JOIN fahrzeug_marken AS fm ON fm.id = f.marke_id
                LEFT JOIN fahrzeug_modelle AS fmo ON fmo.id = f.fahrzeugtyp_id
                LEFT JOIN fahrzeug_kategorien AS fk ON fk.id = f.fahrzeugkategorie_id
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
        marke_id: Optional[int],
        fahrzeugtyp_id: Optional[int],
        fahrzeugkategorie_id: Optional[int],
        ausserbetrieb: bool,
        ausserbetriebnahme: Optional[date],
    ) -> int:
        with self.connection:
            inbetriebnahme_str = self._format_date(inbetriebnahme)
            ausserbetrieb_str = self._format_date(ausserbetriebnahme)
            ausserbetrieb_flag = 1 if ausserbetrieb else 0
            if fahrzeug_id:
                self.connection.execute(
                    """
                    UPDATE fahrzeuge
                    SET name = ?, kennzeichen = ?, marke = ?, typ = ?, kategorie = ?,
                        inbetriebnahme = ?, standort_id = ?, kilometerstand = ?, status = ?,
                        marke_id = ?, fahrzeugtyp_id = ?, fahrzeugkategorie_id = ?,
                        ausserbetrieb = ?, ausserbetriebnahme_datum = ?
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
                        marke_id,
                        fahrzeugtyp_id,
                        fahrzeugkategorie_id,
                        ausserbetrieb_flag,
                        ausserbetrieb_str,
                        fahrzeug_id,
                    ),
                )
                self.add_vehicle_log(fahrzeug_id, "aktualisiert", "Fahrzeugdaten aktualisiert")
                return fahrzeug_id
            cur = self.connection.execute(
                """
                INSERT INTO fahrzeuge (
                    name, kennzeichen, marke, typ, kategorie, inbetriebnahme, standort_id,
                    kilometerstand, status, marke_id, fahrzeugtyp_id, fahrzeugkategorie_id,
                    ausserbetrieb, ausserbetriebnahme_datum
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    marke_id,
                    fahrzeugtyp_id,
                    fahrzeugkategorie_id,
                    ausserbetrieb_flag,
                    ausserbetrieb_str,
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
                SELECT p.*,
                       k.name AS kategorie_name,
                       s.land AS standort_land,
                       s.bereich AS standort_bereich,
                       s.bezirk AS standort_bezirk,
                       s.bezirksstelle AS standort_bezirksstelle,
                       s.ortsstelle AS standort_ortsstelle,
                       COALESCE(s.ortsstelle, s.bezirksstelle, s.bezirk, s.bereich, s.land, '') AS standort_name,
                       f.name AS fahrzeug_name,
                       pt.name AS produkt_typ_name,
                       pm.name AS produkt_modell_name,
                       ph.name AS produkt_hersteller_name
                FROM produkte AS p
                LEFT JOIN kategorien AS k ON k.id = p.kategorie_id
                LEFT JOIN standorte AS s ON s.id = p.standort_id
                LEFT JOIN fahrzeuge AS f ON f.id = p.fahrzeug_id
                LEFT JOIN produkt_typen AS pt ON pt.id = p.produkt_typ_id
                LEFT JOIN produkt_modelle AS pm ON pm.id = p.produkt_modell_id
                LEFT JOIN produkt_hersteller AS ph ON ph.id = p.produkt_hersteller_id
                ORDER BY p.name
                """
            )
        )

    def get_product(self, produkt_id: int) -> Optional[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT p.*,
                   k.name AS kategorie_name,
                   s.land AS standort_land,
                   s.bereich AS standort_bereich,
                   s.bezirk AS standort_bezirk,
                   s.bezirksstelle AS standort_bezirksstelle,
                   s.ortsstelle AS standort_ortsstelle,
                   COALESCE(s.ortsstelle, s.bezirksstelle, s.bezirk, s.bereich, s.land, '') AS standort_name,
                   f.name AS fahrzeug_name,
                   pt.name AS produkt_typ_name,
                   pm.name AS produkt_modell_name,
                   ph.name AS produkt_hersteller_name
            FROM produkte AS p
            LEFT JOIN kategorien AS k ON k.id = p.kategorie_id
            LEFT JOIN standorte AS s ON s.id = p.standort_id
            LEFT JOIN fahrzeuge AS f ON f.id = p.fahrzeug_id
            LEFT JOIN produkt_typen AS pt ON pt.id = p.produkt_typ_id
            LEFT JOIN produkt_modelle AS pm ON pm.id = p.produkt_modell_id
            LEFT JOIN produkt_hersteller AS ph ON ph.id = p.produkt_hersteller_id
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
        stk_aktiv: bool,
        mtk_aktiv: bool,
        letzte_stk: Optional[date],
        letzte_mtk: Optional[date],
        naechste_stk: Optional[date],
        naechste_mtk: Optional[date],
        lagerort: str,
        produkt_typ_id: Optional[int],
        produkt_modell_id: Optional[int],
        produkt_hersteller_id: Optional[int],
        informationstext: str,
    ) -> int:
        anschaffungsdatum_str = self._format_date(anschaffungsdatum)
        letzte_stk_str = self._format_date(letzte_stk)
        letzte_mtk_str = self._format_date(letzte_mtk)
        naechste_stk_str = self._format_date(naechste_stk)
        naechste_mtk_str = self._format_date(naechste_mtk)
        stk_flag = 1 if stk_aktiv else 0
        mtk_flag = 1 if mtk_aktiv else 0
        with self.connection:
            if produkt_id:
                self.connection.execute(
                    """
                    UPDATE produkte
                    SET name = ?, typ = ?, seriennummer = ?, hersteller = ?, anschaffungsdatum = ?,
                        kategorie_id = ?, standort_id = ?, fahrzeug_id = ?, status = ?, interne_kennung = ?,
                        stk_intervall = ?, mtk_intervall = ?, letzte_stk = ?, letzte_mtk = ?, naechste_stk = ?,
                        naechste_mtk = ?, stk_aktiv = ?, mtk_aktiv = ?, lagerort = ?, produkt_typ_id = ?,
                        produkt_modell_id = ?, produkt_hersteller_id = ?, informationstext = ?
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
                        letzte_stk_str,
                        letzte_mtk_str,
                        naechste_stk_str,
                        naechste_mtk_str,
                        stk_flag,
                        mtk_flag,
                        lagerort,
                        produkt_typ_id,
                        produkt_modell_id,
                        produkt_hersteller_id,
                        informationstext,
                        produkt_id,
                    ),
                )
                self.add_product_log(produkt_id, "aktualisiert", "Produktdaten aktualisiert")
                return produkt_id
            cur = self.connection.execute(
                """
                INSERT INTO produkte (
                    name, typ, seriennummer, hersteller, anschaffungsdatum, kategorie_id, standort_id,
                    fahrzeug_id, status, interne_kennung, stk_intervall, mtk_intervall, letzte_stk,
                    letzte_mtk, naechste_stk, naechste_mtk, stk_aktiv, mtk_aktiv, lagerort, produkt_typ_id,
                    produkt_modell_id, produkt_hersteller_id, informationstext
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    letzte_stk_str,
                    letzte_mtk_str,
                    naechste_stk_str,
                    naechste_mtk_str,
                    stk_flag,
                    mtk_flag,
                    lagerort,
                    produkt_typ_id,
                    produkt_modell_id,
                    produkt_hersteller_id,
                    informationstext,
                ),
            )
            new_id = int(cur.lastrowid)
            self.add_product_log(new_id, "angelegt", "Produkt erstellt")
            return new_id

    def mark_product_retired(self, produkt_id: int, datum: date, grund: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE produkte SET status = 'ausgeschieden' WHERE id = ?",
                (produkt_id,),
            )
            self.connection.execute(
                "INSERT INTO ausscheidungen (produkt_id, datum, grund) VALUES (?, ?, ?)",
                (produkt_id, datum.isoformat(), grund),
            )
            self.add_product_log(produkt_id, "ausgeschieden", grund)

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

        status_label = STATUS_LABELS.get(product["status"], product["status"])
        detail_rows = [
            ("Name", product["name"]),
            ("Typ/Modell", product["typ"] or ""),
            ("Hersteller", product["hersteller"] or ""),
            ("Seriennummer", product["seriennummer"]),
            ("Kategorie", product["kategorie_name"] or ""),
            ("Standort", self.location_label_from_product(product)),
            ("Fahrzeug", product["fahrzeug_name"] or ""),
            ("Status", status_label),
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
                """
                SELECT pk.*, kt.name AS komponententyp_name
                FROM produkt_komponenten AS pk
                LEFT JOIN komponententypen AS kt ON kt.id = pk.komponententyp_id
                WHERE pk.produkt_id = ?
                ORDER BY pk.name
                """,
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
        komponententyp_id: Optional[int],
    ) -> int:
        anschaffungsdatum_str = self._format_date(anschaffungsdatum)
        with self.connection:
            if komponent_id:
                self.connection.execute(
                    """
                    UPDATE produkt_komponenten
                    SET name = ?, hersteller = ?, seriennummer = ?, anschaffungsdatum = ?, bemerkung = ?,
                        komponententyp_id = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        hersteller,
                        seriennummer,
                        anschaffungsdatum_str,
                        bemerkung,
                        komponententyp_id,
                        komponent_id,
                    ),
                )
                return komponent_id
            cur = self.connection.execute(
                """
                INSERT INTO produkt_komponenten (
                    produkt_id, name, hersteller, seriennummer, anschaffungsdatum, bemerkung, komponententyp_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    produkt_id,
                    name,
                    hersteller,
                    seriennummer,
                    anschaffungsdatum_str,
                    bemerkung,
                    komponententyp_id,
                ),
            )
            return int(cur.lastrowid)

    def list_repairs(self, produkt_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT r.*, k.name AS kontakt_name, ra.name AS reparatur_art_name
                FROM reparaturen AS r
                LEFT JOIN kontakte AS k ON k.id = r.kontakt_id
                LEFT JOIN reparatur_arten AS ra ON ra.id = r.reparatur_art_id
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
        reparatur_art_id: Optional[int],
    ) -> int:
        with self.connection:
            cur = self.connection.execute(
                """
                INSERT INTO reparaturen (produkt_id, datum, kosten, kontakt_id, beschreibung, reparatur_art_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    produkt_id,
                    datum.isoformat(),
                    kosten,
                    kontakt_id,
                    beschreibung,
                    reparatur_art_id,
                ),
            )
            self.connection.execute(
                "UPDATE produkte SET status = 'in_reparatur' WHERE id = ?",
                (produkt_id,),
            )
            self.add_product_log(produkt_id, "reparatur", beschreibung)
            return int(cur.lastrowid)

    def delete_component(self, komponent_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM produkt_komponenten WHERE id = ?",
                (komponent_id,),
            )

    def add_repair_attachment(
        self,
        *,
        reparatur_id: int,
        dateiname: str,
        speicherpfad: str,
        upload_kategorie_id: Optional[int],
    ) -> int:
        with self.connection:
            cur = self.connection.execute(
                """
                INSERT INTO reparatur_dateien (reparatur_id, dateiname, speicherpfad, upload_kategorie_id)
                VALUES (?, ?, ?, ?)
                """,
                (reparatur_id, dateiname, speicherpfad, upload_kategorie_id),
            )
            return int(cur.lastrowid)

    def list_repair_attachments(self, reparatur_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT rd.*, uk.name AS upload_kategorie_name
                FROM reparatur_dateien AS rd
                LEFT JOIN upload_kategorien AS uk ON uk.id = rd.upload_kategorie_id
                WHERE rd.reparatur_id = ?
                ORDER BY rd.id
                """,
                (reparatur_id,),
            )
        )

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
        self._ensure_material_name_entry(name)
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

    def list_users(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM benutzer ORDER BY nachname, vorname"
            )
        )

    def list_user_location_permissions(self, benutzer_id: int) -> List[Dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT bs.standort_id,
                   bs.lesen,
                   bs.schreiben
            FROM benutzer_standorte AS bs
            WHERE bs.benutzer_id = ?
            ORDER BY bs.standort_id
            """,
            (benutzer_id,),
        ).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            label = self.location_label(row["standort_id"]) if row["standort_id"] else ""
            result.append(
                {
                    "standort_id": row["standort_id"],
                    "lesen": bool(row["lesen"]),
                    "schreiben": bool(row["schreiben"]),
                    "label": label,
                }
            )
        return result

    def _replace_user_location_permissions(
        self, benutzer_id: int, permissions: Dict[int, Dict[str, bool]]
    ) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM benutzer_standorte WHERE benutzer_id = ?",
                (benutzer_id,),
            )
            for standort_id, flags in permissions.items():
                if standort_id is None:
                    continue
                lesen = 1 if flags.get("lesen") else 0
                schreiben = 1 if flags.get("schreiben") else 0
                if schreiben and not lesen:
                    lesen = 1
                self.connection.execute(
                    """
                    INSERT INTO benutzer_standorte (benutzer_id, standort_id, lesen, schreiben)
                    VALUES (?, ?, ?, ?)
                    """,
                    (benutzer_id, standort_id, lesen, schreiben),
                )

    def add_or_update_user(
        self,
        *,
        benutzer_id: Optional[int],
        vorname: str,
        nachname: str,
        dienstnummer: str,
        rolle: str,
        permissions: Optional[Dict[str, bool]] = None,
        location_permissions: Optional[Dict[int, Dict[str, bool]]] = None,
    ) -> int:
        username = dienstnummer.strip()
        if not username:
            raise ValueError("Dienstnummer darf nicht leer sein")
        full_name = f"{vorname.strip()} {nachname.strip()}".strip()
        merged_permissions = PERMISSION_DEFAULTS.copy()
        if permissions:
            for key, value in permissions.items():
                if key in merged_permissions:
                    merged_permissions[key] = bool(value)
        permission_values = [1 if merged_permissions[column] else 0 for column in PERMISSION_COLUMNS]
        with self.connection:
            if benutzer_id:
                set_clause = ", ".join(f"{column} = ?" for column in PERMISSION_COLUMNS)
                self.connection.execute(
                    f"""
                    UPDATE benutzer
                    SET username = ?, full_name = ?, role = ?, vorname = ?, nachname = ?, dienstnummer = ?, {set_clause}
                    WHERE id = ?
                    """,
                    (
                        username,
                        full_name or username,
                        rolle,
                        vorname,
                        nachname,
                        dienstnummer,
                        *permission_values,
                        benutzer_id,
                    ),
                )
                user_id = benutzer_id
            else:
                columns_sql = ", ".join(PERMISSION_COLUMNS)
                placeholders = ", ".join(["?"] * len(PERMISSION_COLUMNS))
                cur = self.connection.execute(
                    f"""
                    INSERT INTO benutzer (username, password_hash, full_name, role, vorname, nachname, dienstnummer, {columns_sql})
                    VALUES (?, ?, ?, ?, ?, ?, ?, {placeholders})
                    """,
                    (
                        username,
                        self.hash_password(dienstnummer),
                        full_name or username,
                        rolle,
                        vorname,
                        nachname,
                        dienstnummer,
                        *permission_values,
                    ),
                )
                user_id = int(cur.lastrowid)

        if location_permissions is not None:
            self._replace_user_location_permissions(user_id, location_permissions)

        return user_id

    def set_user_password(self, benutzer_id: int, password: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE benutzer SET password_hash = ? WHERE id = ?",
                (self.hash_password(password), benutzer_id),
            )

    def delete_user(self, benutzer_id: int) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM benutzer WHERE id = ?", (benutzer_id,))

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

    def delete_maintenance(self, wartung_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM wartungen WHERE id = ?",
                (wartung_id,),
            )

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

    def repair_cost_total(self) -> float:
        value = self.connection.execute(
            "SELECT SUM(kosten) AS summe FROM reparaturen WHERE kosten IS NOT NULL"
        ).fetchone()
        total = value["summe"] if value and value["summe"] is not None else 0.0
        return float(total)

    def repair_costs_by_category(self) -> List[Tuple[str, float]]:
        rows = self.connection.execute(
            """
            SELECT COALESCE(k.name, 'Ohne Kategorie') AS kategorie,
                   SUM(r.kosten) AS summe
            FROM reparaturen AS r
            JOIN produkte AS p ON p.id = r.produkt_id
            LEFT JOIN kategorien AS k ON k.id = p.kategorie_id
            WHERE r.kosten IS NOT NULL
            GROUP BY kategorie
            ORDER BY summe DESC
            """
        ).fetchall()
        return [(row["kategorie"], float(row["summe"] or 0.0)) for row in rows]

    def repair_costs_by_vehicle(self) -> List[Tuple[str, float]]:
        rows = self.connection.execute(
            """
            SELECT COALESCE(f.name, 'Ohne Fahrzeug') AS fahrzeug,
                   SUM(r.kosten) AS summe
            FROM reparaturen AS r
            LEFT JOIN produkte AS p ON p.id = r.produkt_id
            LEFT JOIN fahrzeuge AS f ON f.id = p.fahrzeug_id
            WHERE r.kosten IS NOT NULL
            GROUP BY fahrzeug
            ORDER BY summe DESC
            """
        ).fetchall()
        return [(row["fahrzeug"], float(row["summe"] or 0.0)) for row in rows]

    def filtered_products(
        self,
        *,
        fahrzeug_id: Optional[int] = None,
        land: Optional[str] = None,
        bereich: Optional[str] = None,
        bezirk: Optional[str] = None,
        bezirksstelle: Optional[str] = None,
        ortsstelle: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        rows = self.list_products()
        if fahrzeug_id:
            rows = [row for row in rows if row["fahrzeug_id"] == fahrzeug_id]
        if any([land, bereich, bezirk, bezirksstelle, ortsstelle]):
            location_cache = {row["id"]: row for row in self.list_locations()}

            def matches_location(row: sqlite3.Row) -> bool:
                standort_id = row["standort_id"] if "standort_id" in row.keys() else None
                if not standort_id:
                    return False
                location = location_cache.get(standort_id)
                if not location:
                    return False
                return all(
                    (
                        (value is None)
                        or (value == "")
                        or ((location[key] or "") == value)
                    )
                    for key, value in [
                        ("land", land),
                        ("bereich", bereich),
                        ("bezirk", bezirk),
                        ("bezirksstelle", bezirksstelle),
                        ("ortsstelle", ortsstelle),
                    ]
                )

            rows = [row for row in rows if matches_location(row)]
        return rows

    def export_products_filtered_html(
        self,
        *,
        fahrzeug_id: Optional[int] = None,
        land: Optional[str] = None,
        bereich: Optional[str] = None,
        bezirk: Optional[str] = None,
        bezirksstelle: Optional[str] = None,
        ortsstelle: Optional[str] = None,
        title: str = "Produktliste",
    ) -> str:
        rows = self.filtered_products(
            fahrzeug_id=fahrzeug_id,
            land=land,
            bereich=bereich,
            bezirk=bezirk,
            bezirksstelle=bezirksstelle,
            ortsstelle=ortsstelle,
        )
        subtitle_parts = []
        if fahrzeug_id:
            fahrzeug = self.connection.execute(
                "SELECT name FROM fahrzeuge WHERE id = ?",
                (fahrzeug_id,),
            ).fetchone()
            if fahrzeug:
                subtitle_parts.append(f"Fahrzeug: {fahrzeug['name']}")
        location_parts = [part for part in [land, bereich, bezirk, bezirksstelle, ortsstelle] if part]
        if location_parts:
            subtitle_parts.append(f"Standort: {' / '.join(location_parts)}")
        subtitle = "<p>" + " | ".join(subtitle_parts) + "</p>" if subtitle_parts else ""
        html_rows = "".join(
            "<tr>"
            + "".join(
                f"<td>{value}</td>"
                for value in [
                    row["id"],
                    row["name"],
                    row["seriennummer"],
                    STATUS_LABELS.get(row["status"], row["status"]),
                    row["kategorie_name"] or "",
                    self.location_label_from_product(row),
                    row["fahrzeug_name"] or "",
                ]
            )
            + "</tr>"
            for row in rows
        )
        return "".join(
            [
                "<html><head><meta charset='utf-8'>",
                "<style>body{font-family:Arial,sans-serif;margin:2rem;}table{border-collapse:collapse;width:100%;}th,td{border:1px solid #ccc;padding:0.5rem;text-align:left;}h1{margin-bottom:0.5rem;}p{margin:0 0 1rem 0;}</style>",
                "</head><body>",
                f"<h1>{title}</h1>",
                subtitle,
                "<table><thead><tr><th>ID</th><th>Name</th><th>Seriennummer</th><th>Status</th><th>Kategorie</th><th>Standort</th><th>Fahrzeug</th></tr></thead><tbody>",
                html_rows,
                "</tbody></table>",
                "</body></html>",
            ]
        )

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
            status_label = STATUS_LABELS.get(row["status"], row["status"] or "")
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
                        self.location_label_from_product(row),
                        row["fahrzeug_name"] or "",
                        status_label,
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
                    STATUS_LABELS.get(row["status"], row["status"]),
                    row["kategorie_name"] or "",
                    self.location_label_from_product(row),
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
