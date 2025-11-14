# Ployl

Medizinprodukte-Management System mit Desktop-GUI **und** Netzwerk-Backend. Die ausführliche Dokumentation findest du unter [`docs/medizinprodukte_management_system.md`](docs/medizinprodukte_management_system.md).

## Desktop Schnellstart

```bash
pip install -r requirements.txt
python main_app.py
```

Beim ersten Start wird automatisch ein Administrator-Account `admin` mit dem Passwort `admin` angelegt.

## Netzwerk & Web Cockpit

Das neue FastAPI-Backend ermöglicht Mehrbenutzerbetrieb mit PostgreSQL/MySQL sowie eine Progressive Web App mit QR-Workflows.

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/medizinprodukte"
export APP_SECRET_KEY="change-me"
pip install -r requirements.txt
uvicorn server.main:app --reload
```

Der erste Start erzeugt automatisch den Benutzer `admin` / `admin`. Die Weboberfläche ist unter [http://localhost:8000](http://localhost:8000) erreichbar.

### Erweiterungen (Phase 2)

- **Automatisierte Wartungsplanung:** `POST /api/maintenance/refresh` trainiert das ML-Modell, `GET /api/maintenance` liefert Empfehlungen inkl. Konfidenz.
- **Kostenmanagement & ROI:** Kostenbuchungen via `POST /api/costs/entries`, Auswertung per `GET /api/costs/lifecycle`.
- **Dokumenten-OCR & Cloud-Link:** Uploads an `/api/documents/upload`, optionale Cloud-URL über `CLOUD_STORAGE_BASE_URL`.
- **Geo-Tracking:** Fahrzeugpositionen mit `POST /api/geo/positions`, Route über `GET /api/geo/vehicles/{id}/route`.
- **Audit-Trail:** Signierte Historie per `GET /api/audit` (Adminrolle), Signatur-Schlüssel `AUDIT_SECRET`.

**Zusätzliche Umgebungsvariablen:**

```bash
export OCR_LANGUAGES="deu+eng"         # Tesseract Sprachpakete
export CLOUD_STORAGE_BASE_URL="https://files.example.com/medizin"
export AUDIT_SECRET="change-me-too"
```
