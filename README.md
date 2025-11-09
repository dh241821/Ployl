# Ployl Incident Management Backend

Dieses Projekt stellt einen Python-basierten FastAPI-Backend-Dienst für das Großeinsatz-Management-Planspiel des Roten Kreuzes zur Verfügung. Die Anwendung modelliert Fahrzeuge, Einsätze, Personal, Patienten und Zielkliniken und bildet zentrale Workflows wie Alarmierung, Statuswechsel, Transportzuweisung und Zielortprüfung ab.

## Funktionsüberblick

- **Fahrzeugverwaltung**: Anlegen, Aktualisieren und Live-Überwachung von Fahrzeugdaten inklusive Crew, Standort, Verfügbarkeitsstatus und Pannenmeldungen.
- **Einsatzmanagement**: Einsätze erfassen, Fahrzeuge zuordnen und Statusphasen (alarmiert, unterwegs, am Einsatzort usw.) verfolgen.
- **Patientenfluss**: Patienten erfassen, Transportfahrzeuge auswählen und passende Zielkliniken anhand benötigter Fähigkeiten validieren.
- **Krankenhaus- und Personal-Stammdaten**: Hinterlegung von Fachgebieten und Kapazitäten für Zielkliniken sowie Pflege externer Einsatzkräfte.
- **Echtzeit-Updates**: WebSocket-Kanäle für Fahrzeuge und Einsätze liefern Live-Ereignisse an Leitstellen- oder Einsatzleiter-Frontends.

## Technologie-Stack

- [FastAPI](https://fastapi.tiangolo.com/) für REST- und WebSocket-Schnittstellen
- Asynchrone [SQLAlchemy 2.0](https://docs.sqlalchemy.org/en/20/) mit SQLite (`aiosqlite`) als persistente Datenbank
- Pydantic-Schemas zur Datenvalidierung

## Projektstruktur

```
app/
  api/                # API-Router für Fahrzeuge, Einsätze, Krankenhäuser, Personal, Patienten
  core/               # Konfiguration und Enums
  db/                 # Datenbank-Setup und ORM-Modelle
  schemas/            # Pydantic-Schemas für Ein- und Ausgabe
  services/           # CRUD-Operationen und Event-Bus für Live-Updates
  main.py             # FastAPI-Anwendung inkl. Lifespan-Hook
requirements.txt      # Abhängigkeiten
```

## Entwicklung & Betrieb

### Umgebung vorbereiten

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> **Hinweis für Python 3.12**: Die Abhängigkeiten basieren weiterhin auf Pydantic v1.
> Während der Startphase patcht `app.core.compat` automatisch das geänderte
> Forward-Reference-Verhalten von Python 3.12, damit FastAPI problemlos geladen
> werden kann. Du musst hierfür nichts weiter tun – der Fix greift beim Import
> der Anwendung.

### Anwendung starten

```bash
uvicorn app.main:app --reload
```

Standardmäßig verwendet die Anwendung eine SQLite-Datenbank `plosl.db` im Projektstamm. Über die Umgebungsvariable `DATABASE_URL` kann eine alternative Datenbank angebunden werden (z. B. PostgreSQL).

### API testen

Nach dem Start steht die interaktive Dokumentation unter <http://localhost:8000/docs> zur Verfügung.

Beispiel-Workflow:

1. Fahrzeuge mit Crew anlegen (`POST /vehicles`).
2. Einsätze anlegen und Fahrzeuge zuordnen (`POST /incidents`, `POST /incidents/{id}/assign/{vehicle_id}`).
3. Fahrzeugstatus überführen und Live-Updates via `ws://localhost:8000/vehicles/ws` empfangen.
4. Patienten einem Einsatz zuordnen und geeignete Krankenhäuser prüfen (`POST /patients`, `POST /patients/{id}/transports`).

## Erweiterungsmöglichkeiten

- Mehrstufige Schwierigkeitsgrade über Szenarien und Vorlagen
- Rollenbasierte Authentifizierung und Autorisierung
- Geodaten-Integration für Kartenfrontends
- Simulation von Funkverkehr und Eskalationsketten

## Lizenz

Dieses Projekt steht unter der [MIT-Lizenz](LICENSE).
