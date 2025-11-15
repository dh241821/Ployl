# Ployl

Medizinprodukte-Management System mit Desktop-GUI **und** Netzwerk-Backend. Die ausführliche Dokumentation findest du unter [`docs/medizinprodukte_management_system.md`](docs/medizinprodukte_management_system.md) oder komfortabel gerendert als [HTML-Version](docs/medizinprodukte_management_system.html).

- **Windows-Anleitung:** [docs/windows_installation.md](docs/windows_installation.md)
- **Benutzerhandbuch:** [docs/benutzerhandbuch.md](docs/benutzerhandbuch.md)
- **Technische Dokumentation:** [docs/system_architecture.md](docs/system_architecture.md)
- **Roadmap & Prioritäten:** [docs/roadmap.md](docs/roadmap.md)

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

### Erweiterungen (Phase 3 & 4)

- **Integrationen:** POST `/api/integrations/dispatch` erzeugt HL7/FHIR-/ERP-Payloads und protokolliert sie in `integration_events`.
- **KI-Services:** `/api/ai/chat`, `/api/ai/categorize`, `/api/ai/anomaly` für Chatbot, Klassifikation und Ausreißeranalyse.
- **Security:** MFA-/SSO-Endpunkte unter `/api/security/*`, Dokumentverschlüsselung via Fernet, Login mit `passwort::totp` bei aktivem MFA.
- **Offline & PWA:** Service Worker (`service-worker.js`) cached Ressourcen, Offline-Queue an `/api/offline/queue`, Dark-Mode-Button in der Oberfläche.
- **IoT & Prognosen:** Sensor-APIs `/api/iot/*`, Inventur-Prognosen `/api/predictions/inventory`, Blockchain-Ledger `/api/blockchain/*`, AR-Anleitungen `/api/ar/instructions/{id}`.

**Neue Umgebungsvariablen:**

```bash
export ENCRYPTION_KEY="base64-fernet-key"     # optional, sonst aus APP_SECRET_KEY abgeleitet
export MFA_ISSUER="Medizinprodukte"          # Name im Authenticator
export SSO_CLIENT_ID="demo-client"           # für den SSO-Redirect
export BLOCKCHAIN_SALT="change-me-ledger"    # Signatur der Ledger-Einträge
export OFFLINE_CACHE_DIR="storage/offline"   # Persistenz für Offline-Sync
export IOT_TEMPERATURE_THRESHOLD=8.0
export IOT_HUMIDITY_THRESHOLD=70.0
export PREDICTION_HORIZON_DAYS=30
```

**Login-Hinweis bei MFA:** Passwort und TOTP-Code werden mit `::` kombiniert (`passwort::123456`).
