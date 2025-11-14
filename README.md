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
