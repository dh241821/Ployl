# Entwicklungsroadmap

Diese Roadmap priorisiert die Arbeiten am Medizinprodukte-Management-System. Sie ist so strukturiert, dass die Punkte von oben nach unten abgearbeitet werden können. Jede Phase baut auf der vorherigen auf.

## Phase 1 – Basis zum Laufen bringen (P1 – höchste Priorität)

### 1. DatabaseManager-Grundgerüst fertigstellen
- **Ziel:** Alle Aufrufe aus `main_app.py` verursachen keine `AttributeError` mehr.
- **Aufgaben:**
  - Klasse `DatabaseManager` mit Konstruktor, der die SQLite-DB öffnet (Pfad aus Konfiguration) und `row_factory = sqlite3.Row` setzt.
  - Platzhaltermethoden (mit sinnvollen Signaturen, ggf. Dummy-Rückgaben) bereitstellen:
    - `list_products(...)`, `get_product(produkt_id)`, `add_or_update_product(data)`, `delete_product(produkt_id)`
    - `list_materials(...)`, `list_vehicles(...)`
    - `product_status_counts()`, `due_products()`, `products_in_repair()`
    - `material_statistics()`, `search_global(term)`
  - Jede Methode fängt `sqlite3.Error` ab, nutzt `_log_internal_error(message, exc)` und liefert je nach Kontext eine leere Liste oder wirft eine definierte Exception.

### 2. SQLite-Schema & `initialize_schema()`
- **Ziel:** DB-Struktur entspricht grob den Erwartungen der GUI.
- **Aufgaben:**
  - `initialize_schema()` legt mindestens folgende Tabellen an: `produkte`, `fahrzeuge`, `material`, `benutzer`, `rollen` (oder Rollenfeld), `standorte`, `system_log`, `audit_log`, optional `mandanten`.
  - Wichtige Felder sicherstellen (z. B. `produkte.seriennummer`, `produkte.standort_id`, `material.verfallsdatum`, `fahrzeuge.fahrzeug_typ` usw.).
  - Tabelle `schema_version` mit Versionseintrag anlegen; beim ersten Start komplette Initialisierung durchführen und Version auf `1` setzen.

### 3. User-Modell & Berechtigungslogik
- **Ziel:** GUI kann zuverlässig Rechte prüfen.
- **Aufgaben:**
  - `User`-Klasse (z. B. in `app/auth.py`) mit Feldern `id`, `username`, `full_name`, `role`, `mandant_id`, `location_permissions`.
  - Methoden `can_read(module)`, `can_write(module)`, `can_read_location(location_id)`, `can_write_location(location_id)` implementieren.
  - Rollen definieren (`admin`, `manager`, `mitarbeiter`) und einfache Regelwerke hinterlegen.
  - `DatabaseManager.authenticate(username, password)` implementieren, die einen `User` zurückgibt oder `None`.

## Phase 2 – Stabilität & Fachlogik (P2)

### 4. Business-Regeln zentralisieren
- `services/maintenance.py`: Funktionen `calculate_next_due` und `update_maintenance_dates`.
- `services/products.py`: `validate_product`, `mark_product_retired`.
- `DatabaseManager.add_or_update_product` ruft `validate_product` auf und wirft eine definierte `ValidationError` bei Problemen.

### 5. Validierung & Fehlermeldungen
- Modul `validation.py` mit Funktionen wie `validate_material`, `validate_vehicle` und strukturierten Fehlermeldungen.
- GUI fängt `ValidationError` ab und zeigt Meldungen konsistent an.

### 6. Mandantenfähigkeit absichern
- `DatabaseManager` speichert `current_mandant_id` und stellt `set_active_mandant` bereit.
- Alle SELECTs beinhalten `WHERE mandant_id = ...`, Inserts setzen `mandant_id` automatisch.
- Tests für Mandantentrennung.

### 7. Logging & Audit konsolidieren
- `DatabaseManager.log_event(level, message, user_id=None)` schreibt ins `system_log`.
- `DatabaseManager.record_audit(table, record_id, action, before, after, user_id=None)` protokolliert Änderungen.
- In Produkt-, Material-, Fahrzeug- und CAPA-Workflows konsequent nutzen.

## Phase 3 – Qualität, Sicherheit, Komfort (P3)

### 8. Teststruktur
- Ordner `tests/` mit `test_database_manager_basic.py`, `test_user_permissions.py`, `test_validation.py`.
- Tests nutzen In-Memory-SQLite.

### 9. Konfiguration & Pfadmanagement
- Modul `config.py` für `get_db_path()`, `get_storage_dir()`, `get_exports_dir()` etc.
- `DatabaseManager` und GUI lesen Pfade nur noch über `config`.

### 10. Security-Verbesserungen
- Modul `security.py` mit `hash_password`/`verify_password` (PBKDF2 + Salt).
- `DatabaseManager.authenticate` nutzt die neue Verifikation und beachtet `is_active`.

### 11. Architektur aufräumen
- `main_app.py` verschlanken; neue Module `app/views/...` und `utils.py` einführen.
- Schrittweise Migration der View-Logik.

### 12. Styling & UI-Konsistenz
- Modul `ui_style.py` mit `setup_styles` für Fonts, Farben, KPI-Karten usw.
- Alle Views verwenden die zentralen Styles.

### 13. Dokumentation
- `docs/benutzerhandbuch.md` mit Kapiteln für Kernprozesse.
- `docs/technik.md` (oder `medizinprodukte_management_system.md`) mit Architektur- und Backup-Infos.

## Phase 4 – Nice-to-have & Zukunft (P4)
1. Backup-Dialog & automatisierte Backups.
2. Archivierung alter Daten (Logs, ausgeschiedene Produkte, CAPA).
3. Diagnostics-/"Systeminfo"-Funktion.
4. Internationalisierung (Sprachdateien, `tr()`-Helper).
5. Barcode-/Label-Integration.

---

## Startempfehlung
1. `DatabaseManager` inkl. `initialize_schema()` und `User`-Modell fertigstellen, bis die App ohne AttributeErrors startet.
2. Erst danach Business-Regeln/Mandanten-Logik vertiefen.
3. Dann Tests, Konfiguration und Sicherheitsmodule ergänzen.

Diese Liste kann direkt als GitHub-Issue-Liste oder Sprint-Backlog verwendet werden.
