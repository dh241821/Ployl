# Technische Dokumentation

Diese Dokumentation fasst Aufbau und Hauptkomponenten des Medizinprodukte-Management Systems zusammen.

## 1. Gesamtübersicht

Das System besteht aus drei Schichten:

1. **Desktop-Client (`main_app.py`)** – Tk/ttkbootstrap-Anwendung für Inventarverwaltung, Wartungen und Stammdatenpflege.
2. **Backend (`server/`)** – FastAPI-Server mit REST-Schnittstellen, Authentifizierung und Hintergrundjobs.
3. **Progressive Web App (`server/static/`)** – Browseroberfläche zum mobilen Erfassen von Produkten und Reparaturen.

Alle Varianten greifen auf ein gemeinsames Datenbankmodell zu (SQLite lokal oder PostgreSQL/MySQL im Serverbetrieb).

## 2. Datenbankmodell (Ausschnitt)

| Tabelle                      | Zweck                                                     |
|------------------------------|-----------------------------------------------------------|
| `produkte`                   | Geräte-Stammdaten, Status, Zuordnung, STK/MTK             |
| `produkt_komponenten`        | Einzelteile/Module eines Produkts                         |
| `wartungen`                  | Geplante und durchgeführte Wartungen inkl. Typen          |
| `reparaturen`                | Reparaturmaßnahmen, Anhänge, Kosten                       |
| `fahrzeuge`                  | Fahrzeugdaten inkl. Kategorien, Kilometer, Historie       |
| `verbrauchsmaterial`         | Materialien mit Beständen und Verfallsdaten               |
| `standorte`                  | Landesverband → Bereich → Bezirk → Bezirksstelle → Ortsstelle |
| `benutzer`, `benutzerrechte` | Benutzerdaten, Modulrechte, standortspezifische Berechtigungen |
| `kostenbuchungen`            | Ausgaben für TCO/ROI-Analysen                             |
| `wartungs_insights`          | ML-Empfehlungen für Wartungsplanung                       |

Migrationen werden beim Start automatisch ausgeführt (`app.database.ensure_schema`).

## 3. Desktop-App Architektur

- **`MedizinprodukteApp`** initialisiert Fenster, Tabs, Datenbank und Personalisierung.
- Tabs:
  - `ProductWorkspace` – Listenansicht, Filter, Editor mit Unterreitern (Details, Komponenten, Wartungen, Reparaturen).
  - `VehicleWorkspace`, `MaterialWorkspace`, `LocationManager`, `MasterDataManager`, `AnalysisView` u. a.
- **Dialoge** (z. B. `ProductEditor`, `MaintenanceDialog`, `RepairDialog`) teilen sich Hilfsfunktionen aus `app.database`.
- **Personalisierung** wird pro Benutzer in `user_settings` gespeichert (Theme, Schriftgröße, Begrüßung).

## 4. Backend-Komponenten

- **`server/main.py`** konfiguriert FastAPI, registriert Router und startet Scheduler-Jobs.
- Router nach Funktionsbereichen (`server/routers/*`): Authentifizierung, Produkte, Wartungen, Kosten, Dokumente, IoT, Offline, Blockchain etc.
- **Services (`server/services/*`)** kapseln Geschäftslogik wie OCR-Uploads, IoT-Sensorverarbeitung oder KI-Modelle.
- **`server/models.py`** enthält SQLAlchemy-Modelle mit Beziehungen, Validierung und Audit-Feldern.
- JWT-Authentifizierung (Access & Refresh Tokens) plus optionaler TOTP-2FA.

## 5. Progressive Web App

- **`server/static/index.html`** ist das Shell-Dokument mit moderner UI, Dark Mode und QR-Scanner.
- **`pwa.js`** verwaltet State, API-Aufrufe, Offline-Queue und Installation.
- **`service-worker.js`** cached Kernressourcen, synchronisiert Warteschlangen und liefert Push-Benachrichtigungen.

## 6. Hintergrundprozesse

- APScheduler führt periodisch Jobs aus (`server/services/scheduler.py`):
  - Wartungsplanung aktualisieren
  - Benachrichtigungen per E-Mail/SMS versenden
  - Sensor-Daten aggregieren (IoT)
  - Blockchain-Signaturen erneuern

## 7. Integration & Erweiterbarkeit

- **REST-API**: JSON-Schema in `server/schemas.py`. Alle Endpunkte sind im README mit Beispielaufrufen dokumentiert.
- **Scanner-Anbindung**: Barcode-/QR-Daten werden in `/api/scanner/decode` verarbeitet.
- **Dokumentenverwaltung**: Uploads landen in `storage/documents`, Metadaten werden verschlüsselt gespeichert.
- **Erweiterte Sicherheit**: Rollenbasierte Autorisierung, Standortrechte, Audit-Trail und Versionierung.

## 8. Deployment-Hinweise

- Produktionsbetrieb mit Reverse Proxy (nginx) und systemd-Services (`docs/deployment_example.md`).
- Datenbank-Backups per `python -m app.database backup --target <pfad>`.
- Monitoring über Prometheus-kompatible `/metrics`-Route.

## 9. Referenzen

- Benutzerhandbuch: [docs/benutzerhandbuch.md](benutzerhandbuch.md)
- Windows-Setup: [docs/windows_installation.md](windows_installation.md)
- Ursprüngliche erweiterte Dokumentation: [docs/medizinprodukte_management_system.md](medizinprodukte_management_system.md)

