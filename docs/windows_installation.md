# Windows-Installation

Diese Anleitung führt dich Schritt für Schritt durch die Einrichtung der Desktop-Anwendung sowie des FastAPI-Backends unter Windows.

## 1. Voraussetzungen prüfen

1. Öffne **Einstellungen → Apps → Installierte Apps** und kontrolliere, ob **Python 3.10 oder neuer** installiert ist.
2. Falls Python fehlt, lade den offiziellen Installer von [python.org](https://www.python.org/downloads/windows/) herunter.
   - Während der Installation unbedingt **"Add python.exe to PATH"** aktivieren.
3. Installiere die Abhängigkeiten für Tesseract-OCR, falls du die Dokumentenerkennung nutzen möchtest:
   - Lade das Windows-Setup von [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) herunter und folge dem Setup-Assistenten.

## 2. Projekt herunterladen

1. Öffne den **Datei-Explorer** und navigiere zu dem Ordner, in dem du arbeiten möchtest (z. B. `C:\Users\<DeinName>\Documents`).
2. Klicke mit der rechten Maustaste → **"Git Bash here"** (oder öffne die Windows-Terminal App).
3. Klone das Repository:

```bash
git clone https://github.com/<dein-account>/Ployl.git
cd Ployl
```

> Alternativ kannst du das ZIP-Archiv von GitHub herunterladen und entpacken.

## 3. Virtuelle Umgebung erstellen

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

> Im Windows-Terminal genügt `& .\.venv\Scripts\Activate.ps1`.

Aktiviere die Umgebung bei jedem neuen Terminalfenster erneut.

## 4. Abhängigkeiten installieren

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### Zusatzpakete (optional)

| Paket                | Wann nötig?                                  |
|----------------------|----------------------------------------------|
| `pypiwin32`          | Für Drucker- oder COM-Port-Anbindung         |
| `psycopg2-binary`    | Wenn du mit PostgreSQL statt SQLite arbeitest |
| `mysqlclient`        | Für MySQL/MariaDB als Serverdatenbank         |

## 5. Desktop-App starten

```powershell
python main_app.py
```

Beim ersten Start erstellt die Anwendung die SQLite-Datenbank `medizinprodukte.db` sowie einen Administrator-Account `admin` / `admin`.

## 6. FastAPI-Backend starten (optional)

1. Setze die Umgebungsvariablen in PowerShell:

```powershell
$env:DATABASE_URL = "sqlite:///./medizinprodukte.db"   # oder PostgreSQL/MySQL URL
$env:APP_SECRET_KEY = "change-me"
```

2. Starte den Server:

```powershell
uvicorn server.main:app --reload
```

3. Öffne [http://localhost:8000](http://localhost:8000) im Browser. Die PWA lässt sich über das Browsermenü installieren.

## 7. Dienste als Autostart hinterlegen

- **Desktop-App:** Lege eine Verknüpfung in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup` ab.
- **FastAPI-Backend:** Nutze den Windows-Taskplaner mit dem Trigger "Beim Anmelden" und dem Befehl `powershell.exe -File start_backend.ps1` (siehe Beispielskript im Repository).

## 8. Fehlerbehebung

| Problem                                | Lösungsvorschlag |
|----------------------------------------|------------------|
| `ModuleNotFoundError` beim Start       | Stelle sicher, dass die virtuelle Umgebung aktiviert ist. |
| `ImportError: DLL load failed`         | Installiere das passende Visual C++ Redistributable (x64). |
| Tkinter-Fenster öffnet nicht           | Kontrolliere, ob eine weitere Instanz bereits läuft. |
| Tesseract wird nicht gefunden          | Ergänze den Installationspfad (z. B. `C:\Program Files\Tesseract-OCR`) zur `PATH`-Variable. |

## 9. Updates einspielen

```powershell
git pull
pip install -r requirements.txt
```

Danach die Desktop-App bzw. den Server neu starten.

