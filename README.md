# Ployl Medical Device Manager

Eine lauffähige Referenzimplementierung zum Verwalten von Medizinprodukten für RTW-C/NEF
und KTW Niederösterreich. Die Anwendung basiert auf FastAPI und SQLAlchemy und deckt
sämtliche im Auftrag genannten Anforderungen sowie zusätzliche Automatisierungen ab.

## Features

- Verwaltung von Fahrzeugen inklusive Funkkennung
- Verwaltung von Gerätetypen (inkl. Verbundgeräte wie Trage oder Corpuls) und deren
  Komponenten
- Anlage konkreter Geräte samt Komponenten-Seriennummern
- Historie der Fahrzeugzuordnungen mit automatischem Schließen vorheriger Zuordnungen
- Dokumentation von MTK- und STK-Prüfungen inkl. PDF-Belegen
- Reparaturlog mit Dokumentenanhang
- Vollständige Gerätehistorie (Zuordnungen, Prüfungen, Reparaturen)
- Wartungsübersicht mit Berechnung bevorstehender MTK/STK Fälligkeiten
- Automatischer Hintergrundjob (APScheduler) zur Benachrichtigung über fällige Checks
- Typer-CLI für Migrationen, Konfigurationsübersicht und Wartungsreport

## Schnellstart

1. Virtuelle Umgebung erstellen und aktivieren:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Abhängigkeiten installieren:

   ```bash
   pip install -e .[dev]
   ```

3. Datenbankmigrationen ausführen:

   ```bash
   python -m app.cli migrate
   ```

4. Server starten:

   ```bash
   uvicorn app.main:app --reload
   ```

Die API ist anschließend unter `http://localhost:8000` erreichbar. Die OpenAPI-Dokumentation
findet sich unter `http://localhost:8000/docs`.

## Tests

```bash
pytest
```

## Wichtige Umgebungsvariablen

| Variable | Beschreibung | Standard |
| --- | --- | --- |
| `DATABASE_URL` | SQLAlchemy-URL (z. B. `sqlite+aiosqlite:///./ployl.db`) | SQLite-Datei im Projektordner |
| `RUN_MIGRATIONS_ON_STARTUP` | Automatisch Migrationen beim Start ausführen | `True` |
| `ENVIRONMENT` | `development`, `testing` oder `production` | `development` |
| `MAINTENANCE_DUE_WINDOW_DAYS` | Lookahead für Wartungsliste | `30` |

## CLI-Befehle

```bash
python -m app.cli migrate   # Schema erstellen
python -m app.cli upcoming  # Fällige MTK/STK Checks anzeigen
python -m app.cli settings  # Effektive Konfiguration ausgeben
```

## Datenmodell

Das relationale Schema entspricht exakt der zuvor skizzierten Struktur und unterstützt
Verbundgeräte (Trage, Corpuls) inklusive Komponentenverwaltung. Automatisierte Trigger
berechnen das Fälligkeitsdatum bei Prüfungen und schließen laufende Zuordnungen.

