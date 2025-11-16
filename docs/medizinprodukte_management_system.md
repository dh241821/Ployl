# Medizinprodukte-Management System - Erweiterte Dokumentation

## 1. Detaillierte Benutzeranleitung

### 1.1 Voraussetzungen & Installation

**Systemanforderungen:**
- Python 3.8 oder höher
- Mindestens 50 MB freier Speicherplatz
- Kompatibel mit Windows, macOS und Linux

**Erforderliche Bibliotheken:**
```bash
pip install tkinter ttkbootstrap sqlite3 matplotlib qrcode[pil]
```

**Installation:**
1. Speichere `main_app.py` in einem beliebigen Verzeichnis
2. Öffne ein Terminal/CMD in diesem Verzeichnis
3. Starte mit: `python main_app.py`
4. Beim ersten Start wird die Datenbank (`medizinprodukte.db`) automatisch erstellt

---

### 1.2 Anmeldung & Erstkonfiguration

**Beim ersten Start:**
- **Benutzerkürzel:** (wird vom Administrator festgelegt)
- **Passwort:** Wird vom Administrator vergeben
- **Vorsicht:** Passwörter werden verschlüsselt gespeichert (SHA-256)

**Benutzerrollen:**
- **Admin:** Vollständiger Zugriff auf alle Funktionen, Benutzerverwaltung
- **Benutzer:** Eingeschränkter Zugriff, Datenbearbeitung begrenzt

---

### 1.3 Dashboard - Erste Orientierung

Das Dashboard ist die Startseite nach dem Login. Es zeigt:

1. **KPI-Widgets (Schlüsselzahlen):**
   - 🔴 Fällige Produkte (rot - heute überfällig)
   - 🟡 Produkte in Reparatur (gelb - aktuell defekt)
   - 🔴 Material mit abgelaufenem Verfallsdatum
   - 🟡 Material mit zu niedrigem Bestand

2. **Visuelle Diagramme:**
   - Balkendiagramm: Status-Verteilung (Im Dienst/Reparatur/Ausgeschieden)
   - Auswertungen nach Kategorie oder Standort

3. **Live-Suchfeld:** 
   - Suche über alle Produkte in Echtzeit

4. **Schnellfilter:**
   - Mit "In Reparatur" und "Fällig" schnell kritische Produkte anzeigen

---

### 1.4 Produkt-Management (Tab "Produkte")

#### Produktliste anzeigen
- **Standard:** Alle Produkte tabellarisch mit Spalten: Name, Typ, Seriennummer, Hersteller, Status, Standort, Kategorie, Anschaffungsdatum, Interne Kennung
- **Sortierung:** Klick auf Spaltenheader zum Sortieren
- **Filter:** Nutze die Filterfelder links um nach Kategorie, Status, Fahrzeug oder Standort zu filtern

#### Neues Produkt anlegen
1. Klick auf "Neues Produkt" oder Rechtsklick → "Neues Produkt"
2. **Schnell-Editor:** Für einfache Einträge
3. **Vollständiger Editor:** Für detaillierte Eingaben
4. **Felder im Produkt-Editor:**
   - **Name*** (erforderlich): Produktbezeichnung (z.B. "Blutdruckmessgerät")
   - **Typ/Modell**: Konkrete Modellbezeichnung (z.B. "Omron BP785")
   - **Seriennummer*** (erforderlich): Eindeutige Seriennummer
   - **Hersteller**: Herstellername (z.B. "Omron Healthcare")
   - **Anschaffungsdatum**: Kaufdatum (Dropdown-Kalender)
   - **Kategorie**: Automatische oder manuelle Kategorisierung
   - **Standort/Fahrzeug**: Zuordnung zu RTW, KTW oder Lagerstelle
   - **Fahrzeug-Kategorie**: Optional für Fahrzeugbezug
   - **Status**: Im Dienst / In Reparatur / Ausgeschieden
   - **Interne Kennung**: Funkkennung oder Betriebsnummer
   - **Prüffristen (STK/MTK)**: Wartungsintervalle in Monaten (z.B. 12 für jährlich)

5. Klick "Speichern" zum Anlegen

#### Produkt bearbeiten
- **Doppelklick** auf Produktzeile, oder
- **Rechtsklick** → "Bearbeiten", oder
- Produkt markieren + Doppelklick
- Änderungen speichern

#### Produkt löschen
- Rechtsklick auf Produkt → "Löschen" (mit Bestätigung)
- **Hinweis:** Gelöschte Produkte können nicht wiederhergestellt werden

#### Komponenten verwalten (für Produkte)
1. Produkt öffnen
2. Im Editor: Reiter "Komponenten" anklicken
3. Neue Komponente hinzufügen:
   - **Name**, **Hersteller**, **Seriennummer**, **Anschaffungsdatum**, **Bemerkung**
4. Komponenten sind hilfreich für Geräte mit mehreren verwaltbaren Teilen
- Der globale Arbeitsbereich **Komponenten** erlaubt standort- oder fahrzeugübergreifende Suche, Statuswechsel und Reparaturmeldungen.
- Komponentenreparaturen unterstützen dieselben Felder wie Produktreparaturen (Typ, Dienstleister, Kosten, Datei-Uploads).
- Der Button **Komponenten-Lebenslauf** erzeugt einen HTML-Bericht mit Einsatzhistorie (Produkt & Fahrzeug) sowie allen Reparaturen.

#### Reparaturen melden
1. Produkt markieren → Rechtsklick → "Reparaturen verwalten"
2. Neue Reparatur:
   - **Datum**: Reparaturdatum
   - **Kosten**: In Euro (z.B. "120.50")
   - **Durchgeführt von**: Reparaturfirma (aus Kontaktliste)
   - **Beschreibung**: Was wurde repariert?
   - **Datei-Anhänge**: Rechnungen etc. (optional)
3. Status wird automatisch auf "In Reparatur" gesetzt

#### Ausscheidung dokumentieren
1. Produkt markieren → Rechtsklick → "Produkt ausscheiden"
2. **Grund**: Warum wird das Produkt ausgeschieden? (z.B. "Defekt", "Abgelaufen", "Verschlissen")
3. **Datum**: Wann wird es ausgeschieden?
4. Status ändert sich zu "Ausgeschieden"

#### Produkt-Berichte
- **Lebenslauf**: Detaillierter HTML-Bericht mit QR-Code und Einsatzfahrzeug-Timeline
- **Listendruck**: Aktuelle Filterliste als HTML drucken
- **CSV-Export**: Alle Produkte als CSV exportieren (für Excel)
- **Fahrzeug-Lebenslauf**: Direkt aus dem Produkteditor abrufbar und zeigt alle Ereignisse des zugeordneten Fahrzeugs
- **Komponenten-Lebenslauf**: Dokumentiert jede Komponente inklusive Einsatz- und Reparaturhistorie

---

### 1.5 Fahrzeug-Management (Tab "Fahrzeuge")

#### Fahzeugliste
- Tabellarische Übersicht aller Fahrzeuge (RTW, KTW, LTW etc.)
- **Spalten:** Name, Kennzeichen, Marke/Typ, KM-Stand, Status, Inbetriebnahme-Datum

#### Neues Fahrzeug anlegen
1. Klick "Neues Fahrzeug"
2. **Felder:**
   - **Name/Kennung**: z.B. "RTW 58/001" oder "KTW 58/002"
   - **Kennzeichen/Info**: Behördlich registriertes Kennzeichen
   - **Marke**: Hersteller (z.B. "Mercedes-Benz")
   - **Typ**: Modellbezeichnung (z.B. "Sprinter 319CDI")
   - **Kategorie**: RTW/KTW/LTW/Sonstiges
   - **Inbetriebnahme**: Erstzulassungsdatum
   - **Standort**: Wo ist das Fahrzeug stationiert?
   - **Kilometerstand**: Start-Kilometerstand (bei Neueintrag)
3. Speichern

#### Kilometerstand aktualisieren
1. Fahrzeug öffnen/bearbeiten
2. "Neuer KM-Stand" eingeben
3. Automatisch wird ein Logbuch-Eintrag erstellt

#### Fahrzeug-Historie
- Jede Änderung wird im Logbuch dokumentiert
- **Fahrzeug-Lebenslauf**: HTML-Report mit allen Ereignissen, Produkten und Wartungen

#### Fahrzeugtausch dokumentieren
- Rechtsklick auf Fahrzeug → "Fahrzeugtausch"
- Alle Produkte werden einem neuen Fahrzeug zugeordnet

#### Fahrzeug ausscheiden
- Status auf "Ausgeschieden" setzen
- Grund und Datum dokumentieren

---

### 1.6 Material-Management (Tab "Material")

#### Materialien anlegen
1. Klick "Neues Material"
2. **Felder:**
   - **Name**: z.B. "Verbandsmaterial Größe A"
   - **Kategorie**: Kategorisierung (z.B. "Verbandsmaterial", "Medikamente")
   - **Lagerort**: Wo wird es gelagert? (z.B. "Sanitätskammer Station Horn")
   - **Soll-Bestand**: Wünschter Bestand (z.B. "20 Stück")
   - **Ist-Bestand**: Aktueller Bestand bei Anlage
   - **Verfallsdatum**: Wann verfällt das Material? (optional)
3. Speichern

#### Bestand verwalten
1. Material öffnen/bearbeiten
2. "Bestandsänderung" eingeben
3. **Verfallsdatum** aktualisieren (wenn nötig)
4. **Status:** 🔴 Rot = abgelaufen, 🟡 Gelb = niedrig, 🟢 Grün = ok

#### Filter für Material
- **Abgelaufen:** Zeige Material mit überschrittenem Verfallsdatum
- **Niedrig:** Zeige Material mit Bestand unter Soll-Bestand
- **Bestellliste generieren:** HTML mit allen Materialien unter Soll-Bestand

#### Material exportieren/drucken
- CSV-Export für Inventur
- HTML-Bestellliste (z.B. für Lieferanten)

---

### 1.7 Stammdaten (Tab "Stammdaten")

#### Standorte verwalten
- **Hierarchie:** Land → Bereich → Bezirk → Bezirksstelle → Ortsstelle
- Für österreichisches Rotes Kreuz optimiert
- **Beispiel:** Österreich → Niederösterreich → Bezirk Horn → Bezirksstelle Horn → Ortsstelle Horn
- Standorte bearbeiten/hinzufügen über Dialog

#### Kategorien verwalten
- **Produktkategorien:** z.B. "Blutdruckmessgerät", "Defibrilator", "Verbandsmaterial"
- Neue Kategorien hinzufügen für Klassifizierung

#### Benutzer verwalten
- Nur **Admin** kann Benutzer verwalten
- **Felder:**
  - **Name**: Vollständiger Name
  - **Kürzel/Login**: Eindeutige Benutzer-ID (z.B. "jployl")
  - **Rolle**: Admin oder Benutzer
  - **Passwort:** Nach dem Speichern setzen
- Passwörter werden mit SHA-256 verschlüsselt

#### Kontakte verwalten
- Reparaturbetriebe, Lieferanten etc.
- **Felder:** Name, Adresse, Telefon, Email, Kontaktperson
- Wird verwendet für Reparaturen und Bestellungen

---

### 1.8 Wartungsplanung (in allen Produkten)

#### Automatische Fälligkeitsprüfung
- **STK (Sicherheitstechnische Kontrolle):** z.B. alle 12 Monate
- **MTK (Messtechnische Kontrolle):** z.B. alle 24 Monate
- Berechnung: Anschaffungsdatum + Intervall

#### Wartungen manuell eintragen
1. Produkt öffnen
2. Reiter "Wartungen" → "Neue Wartung"
3. **Felder:**
   - **Geplantes Datum**: Wann soll gewartet werden?
   - **Typ**: STK, MTK, Inspektion, Kalibrierung etc.
   - **Beschreibung**: Was ist zu tun?
4. Nach Durchführung:
   - **Durchgeführt am**: Aktuelles Datum
   - **Durchgeführt von**: Wer hat es gemacht?
   - **Bemerkung**: Z.B. Befund oder Besonderheiten

#### Wartungs-Report
- Dateimenü → "Wartungs-Report drucken"
- Übersicht aller fälligen und überfälligen Wartungen
- Als HTML für Planung

#### ICS-Export (für Kalender)
- Dateimenü → "Fälligkeiten als ICS exportieren"
- Öffnet die Datei in Outlook, Google Calendar, Apple Calendar etc.
- Automatische Benachrichtigungen möglich

---

### 1.9 Berichte & Exporte

| Berichttyp | Format | Verwendung |
|-----------|--------|-----------|
| Produkt-Lebenslauf | HTML + QR-Code | Detaillierte Produkthistorie |
| Fahrzeug-Lebenslauf | HTML | Alle Fahrzeuginformationen & Wartungen |
| Produktliste | HTML | Nach Kategorie oder Standort sortiert |
| Wartungs-Report | HTML | Fällige & überfällige Wartungen |
| Material-Bestellliste | HTML | Material mit zu niedrigem Bestand |
| Produkte | CSV | Für Excel/Weiterbearbeitung |
| Komponenten | CSV | Für Inventur |
| Fälligkeiten | ICS | Für Kalender-Integration |
| Datenbank | .db | Backup |

#### CSV Import
- Dateimenü → "CSV Importieren"
- Erleichtert Masseneingabe von Produkten

#### QR-Code Funktion
- Jedes Produkt erhält automatisch einen QR-Code
- Scanbar mit Smartphone-Kameras
- Im Produkt-Lebenslauf-Bericht enthalten

---

### 1.10 Alltägliche Workflows

#### Workflow 1: Neues Produkt in Dienst stellen
1. Dashboard: "Neues Produkt" Schnell-Editor
2. Grunddaten eingeben (Name, Seriennummer, Hersteller)
3. Fahrzeug/Standort zuordnen
4. Status = "Im Dienst"
5. Speichern
6. Optional: QR-Code ausdrucken und anbringen

#### Workflow 2: Wartung durchführen
1. Dashboard: Klick auf KPI "Fällig" oder Wartungs-Report öffnen
2. Fälliges Produkt anklicken
3. "Wartung abschließen" im Editor
4. Durchführungsdatum & Benutzer eintragen
5. Bemerkung hinzufügen
6. Speichern → Wartung ist dokumentiert

#### Workflow 3: Reparatur melden
1. Produkt öffnen
2. Status zu "In Reparatur" ändern
3. "Reparation verwalten" → Neue Reparatur
4. Reparaturfirma, Kosten, Beschreibung eintragen
5. Evtl. Rechnung als PDF anhängen
6. Nach Reparatur: Status zu "Im Dienst" zurückändern

#### Workflow 4: Material bestellen
1. Material-Tab → "Abgelaufen" oder "Niedrig" Filter
2. Bestellliste generieren (HTML-Export)
3. Mit Lieferant abstimmen
4. Nach Ankunft: Bestand aktualisieren
5. Optional: Verfallsdatum neu eintragen

#### Workflow 5: Regelmäßiges Backup
1. Dateimenü → "Backup erstellen"
2. Speicherort wählen
3. Eine .db-Datei wird mit Zeitstempel erstellt
4. Sicherung (z.B. auf USB oder Cloud)

---

### 1.11 Tipps & Tricks

- **Schnellsuche:** STRG+F öffnet Live-Suchfeld (auf aktuellem Tab)
- **Doppelklick:** Schnellste Bearbeitung von Produkten/Fahrzeugen
- **Rechtsklick:** Kontextmenüs mit Schnellaktionen
- **Filter speichern:** Gefilterte Ansichten können exportiert werden
- **QR-Codes:** Druckbar auf Labeln für Geräte-Markierung
- **Spalten-Breite:** Mit Maus an Spalten-Rändern justierbar
- **Tastaturkürzel:** Tab wechseln mit ALT + Pfeiltasten
- **Schriftgröße:** Ansicht → Schriftgröße anpassen (für Beamer/Präsentation)

---

### 1.12 Netzwerk-Backend & Mobile Web-App

- **FastAPI-Server:** Start via `uvicorn server.main:app --reload` (env `DATABASE_URL`, `APP_SECRET_KEY`).
- **Mehrbenutzerbetrieb:** Login per OAuth2 Password Flow, Rollensteuerung (Admin/Benutzer).
- **PWA Dashboard:** Browseroberfläche mit PicoCSS, Chart.js und html5-qrcode für QR-Scanner.
- **Offline-Fähigkeit:** Service Worker & Manifest erlauben Installation als App.
- **Benachrichtigungen:** `/api/notifications/dispatch` versendet ICS-Kalender mit Wartungen an Admins.
- **APScheduler:** Täglicher Autoversand um 06:00 Uhr lokaler Zeit (Europe/Vienna).
- **Scanner-Workflows:** `/api/scanner/lookup` & `/api/scanner/transfer` erfassen QR-Codes und Fahrzeugwechsel.
- **Dashboard-API:** `/api/dashboard` liefert KPIs, Status- und Kostenverläufe für Chart.js.

---

### 1.13 Automatisierte Wartungsplanung (ML)

- **Endpunkte:** `/api/maintenance` liefert Prognosen, `/api/maintenance/refresh` trainiert das Modell neu.
- **ML-Modell:** Linear Regression über historische Wartungsintervalle, Mindestbasis sind STK/MTK-Intervalle.
- **Konfidenzwerte:** Anzeige im Dashboard (PWA) für Priorisierung; Fenster ±7 Tage um prognostizierten Termin.
- **Workflow:** 1. Wartungsabschlüsse pflegen → 2. Refresh auslösen (cron oder manuell) → 3. Empfehlungen übernehmen.
- **Persistenz:** Ergebnisse werden als `wartungs_insights` gespeichert und bei jeder Berechnung überschrieben.

---

### 1.14 Kostenmanagement & ROI

- **Kostenbuchungen:** POST `/api/costs/entries` (Typen: `anschaffung`, `wartung`, `betrieb`, `sonstiges`).
- **Lifecycle-Analyse:** GET `/api/costs/lifecycle` liefert Gesamt-, Monats- und ROI-Werte je Produkt.
- **Produktfelder:** `Anschaffungskosten`, `Restwert`, `Nutzungsdauer` ergänzen bestehende Produktstammdaten.
- **Dashboard-Integration:** ROI-Ampel und TCO-Tabelle in der PWA für Budget-Entscheidungen.
- **Export:** Ergebnisse können als CSV aus dem PWA-Dashboard exportiert werden.

---

### 1.15 Dokumentenverwaltung & OCR

- **Upload:** `/api/documents/upload` akzeptiert Mehrteil-Formdaten (Titel, Produkt/Fahrzeug, Tags, Datei).
- **Speicherung:** Dateien landen im Verzeichnis `storage/documents/`, SHA-Checksumme sichert Integrität.
- **OCR:** Optional via Tesseract (`pytesseract`), Sprache konfigurierbar über `OCR_LANGUAGES`.
- **Tagging & Suche:** Volltextsuche über OCR-Inhalte, Tag-Filter als Komma-Liste.
- **Cloud-Link:** Automatisch generierter Link (`CLOUD_STORAGE_BASE_URL`) für externe Archivierung.

---

### 1.16 Geo-Tracking & Routenanalyse

- **Positions-API:** POST `/api/geo/positions` protokolliert GPS-Daten mit Genauigkeit & Zeitstempel.
- **Routenabruf:** GET `/api/geo/vehicles/{id}/route` liefert chronologische Trackpunkte & Gesamtstrecke.
- **Distanzberechnung:** Geodesic (geopy) berechnet Kilometer, Limit der Punkte per Parameter (`limit`).
- **Integrationen:** PWA-Karte zeigt letzte Route, CSV-Export für Einsatzprotokolle möglich.

---

### 1.17 Integrationen & externe Systeme

- **Endpunkt:** POST `/api/integrations/dispatch` mit `integration=hl7|fhir|erp|lager`.
- **HL7:** Erzeugt ORU^R01-Nachrichten inkl. Timestamp und Observation (z. B. Geräteverfügbarkeit) für Kliniksysteme.
- **FHIR:** Liefert Device-Ressourcen mit Hersteller, Typ und Notiz – ideal für FHIR-basierte Inventar-Backends.
- **ERP/Lager:** Summiert Bestellpositionen, markiert Low-Stock-Materialien und protokolliert alles in `integration_events`.
- **Monitoring:** Ereignisse erscheinen im Audit-Log und können per SQL oder Reporting-Tool ausgewertet werden.

---

### 1.18 KI-Assistent & Automatisierung

- **Chatbot:** POST `/api/ai/chat` – Antworten erscheinen unmittelbar in der PWA (Sektion „KI-Assistent“).
- **Kategorisierung:** POST `/api/ai/categorize` empfiehlt Kategorien auf Basis von Stichworten und speichert die Vorschläge.
- **Anomalie-Erkennung:** POST `/api/ai/anomaly` analysiert Zahlenreihen (z. B. Reparaturkosten); Ergebnis wird im Audit geloggt.
- **Offline:** PWA puffert Anfragen über die Offline-Queue, synchronisiert automatisch bei Rückkehr ins Netz.

---

### 1.19 Sicherheit, MFA & Verschlüsselung

- **MFA-Setup:** POST `/api/security/mfa/setup` liefert Secret & QR-URL (z. B. für Microsoft/Google Authenticator).
- **Aktivierung:** POST `/api/security/mfa/enable` mit Secret+Code; Login dann mit Syntax `passwort::123456`.
- **Deaktivierung:** POST `/api/security/mfa/disable` benötigt den aktuellen TOTP-Code.
- **SSO:** GET `/api/security/sso/initiate` startet den OAuth-Handschlag, POST `/api/security/sso/callback` speichert das Subject.
- **Dokumentenverschlüsselung:** Uploads werden vor dem Speichern mit Fernet (AES-128 GCM) verschlüsselt; Schlüssel aus `ENCRYPTION_KEY`.

---

### 1.20 Dark Mode & Accessibility

- **Theme-Toggle:** In der PWA über den Button „Dark Mode“; Zustand wird im LocalStorage abgelegt.
- **Aria-Live Regionen:** Statusmeldungen (Offline-Indikator, KI-Antworten) sind screenreader-tauglich.
- **Reduced Motion:** CSS respektiert `prefers-reduced-motion`; Fokus-Reihenfolge optimiert für Tastaturnutzer.
- **Installierbarkeit:** `beforeinstallprompt` wird abgefangen und via „App installieren“-Button ausgelöst.

---

### 1.21 Offline-Queue & Synchronisation

- **Clientseitig:** `pwa.js` speichert Aktionen (z. B. KI-Anfragen) mit SHA-256 in `offlineQueue`.
- **Serverseitig:** POST `/api/offline/queue` validiert Checksumme und persistiert `offline_changes`.
- **Status:** GET/POST `/api/offline/sync` liefert Überblick über noch nicht synchronisierte Änderungen.
- **UI:** Toolbar zeigt „Offline · X Offline-Aktionen“ sobald Einträge vorhanden sind.

---

### 1.22 IoT-Sensorik & Live-Alarme

- **Geräteverwaltung:** POST `/api/iot/devices` (Admin) legt Sensoren an, GET `/api/iot/devices` listet sie.
- **Messwerte:** POST `/api/iot/devices/{id}/readings` mit `metric=value`; Alerts werden anhand der Settings ausgelöst.
- **Alarmabruf:** GET `/api/iot/devices/{id}/alerts` liefert Temperatur-/Feuchtigkeitswarnungen.
- **PWA:** Sektion „IoT-Sensoren“ zeigt eine Liste inkl. Standort & Sensortyp, aktualisiert alle 60 Sekunden.

---

### 1.23 Predictive Inventory & Forecasts

- **Berechnung:** POST `/api/predictions/inventory` aktualisiert `inventory_forecasts` basierend auf Soll-/Ist-Beständen.
- **Konfiguration:** `PREDICTION_HORIZON_DAYS` steuert den Planungshorizont (Standard 30 Tage).
- **Ergebnisfelder:** `stockout_probability`, `recommended_order_date`, `model_version` für Nachvollziehbarkeit.
- **Automation:** Kann via Scheduler (cron) regelmäßig ausgeführt werden, Ergebnisse fließen in Einkauf & Controlling.

---

### 1.24 Blockchain-Ledger & AR-Workflows

- **Ledger:** POST `/api/blockchain/record` fügt Einträge hinzu, GET `/api/blockchain/verify` prüft die Kette.
- **Signaturen:** Basieren auf `BLOCKCHAIN_SALT`; Einträge werden HMAC-signiert und mit dem Vorgänger verknüpft.
- **AR-Anleitungen:** GET `/api/ar/instructions/{produkt_id}` liefert Schrittlisten + `asset_url` für 3D/AR Viewer.
- **PWA:** Zeigt die Schritte als nummerierte Liste, kann mit externen AR-Brillen verknüpft werden.
- **Validierung:** API überprüft Fahrzeug-ID und gibt 404 bei unbekannten Fahrzeugen.

---

### 1.25 Audit-Trail & Compliance (Detail)

- **Automatisches Logging:** Insert/Update/Delete auf Kernobjekten erzeugen signierte Einträge (`audit_log`).
- **Digitale Signatur:** HMAC-SHA256 über Payload (`AUDIT_SECRET`) → Manipulationsschutz.
- **Abruf:** GET `/api/audit` (Admin) liefert letzte 500 Einträge inkl. Signaturprüfung.
- **Benutzerkontext:** `audit_context`-Wrapper setzt ausführenden Benutzer, Scheduler läuft als `system`.
- **Compliance:** Exportierbar für MDR/DIN-Audits, Signaturstatus dient als Nachweis der Unverändertheit.

---

## 2. Mögliche Erweiterungen

### Priorität 1: Hochwertige Verbesserungen (umgesetzt)

1. **Multi-Benutzer & Netzwerk-Funktionalität** ✅
   - FastAPI-Backend mit SQLAlchemy und Unterstützung für PostgreSQL/MySQL.
   - JWT-basierte Authentifizierung und Rollenverwaltung.
   - APScheduler-basierte Hintergrundjobs für tägliche Wartungsbenachrichtigungen.

2. **Mobile App (Web-Interface)** ✅
   - Progressive Web App (PWA) mit Chart.js-Dashboards und responsive PicoCSS-Oberfläche.
   - Offline-Unterstützung via Service Worker und installierbares Manifest.

3. **Erweitertes Benachrichtigungssystem** ✅
   - Wartungserinnerungen mit ICS-Kalenderanhängen per SMTP (aiosmtplib).
   - API-Endpunkt zum manuellen Auslösen und Dashboard mit Erinnerungsstatus.

4. **Barcode/QR-Code Integration** ✅
   - Browserbasierter QR-Scanner (html5-qrcode) für Produkt-Suche und Fahrzeugtransfer.
   - REST-Endpunkte für Lookup- und Transfer-Workflows.

5. **Erweiterte Berichte & Dashboards** ✅
   - Echtzeit-KPIs zu Wartungen, Reparaturstatus und Materialbeständen.
   - Verlaufsgrafiken für Reparaturkosten und Statusverteilung via Chart.js.

---

### Priorität 2: Mittlere Verbesserungen (umgesetzt)

6. **Automatisierte Wartungsplanung** ✅
   - ML-gestützte Prognosen mit linearer Regression auf Wartungshistorie.
   - Empfehlungen inklusive Zeitfenster & Konfidenz; speicherbar und exportierbar.
   - REST-API & Scheduler-Integration ermöglichen nächtliche Aktualisierung.

7. **Kostenmanagement** ✅
   - Lebenszyklus-Kostenrechnung (TCO) inkl. ROI & Kosten/Monat je Produkt.
   - Zusätzliche Kostenbuchungen (Wartung, Betrieb) und Reparaturkostenaggregation.
   - Visualisierung in der PWA und CSV-Exports für Controlling.

8. **Dokumentenverwaltung** ✅
   - OCR-gestützte Volltextsuche, Tagging und Cloud-Verlinkung.
   - Sichere Ablage mit Prüfsumme & API-Upload.

9. **Geo-Location & Asset-Tracking** ✅
   - GPS-Positions-Logging, Distanzberechnung und Routendarstellung.
   - API-gestützter Export für Einsatz- und Wartungsplanung.

10. **Audit-Trail & Compliance** ✅
    - Lückenlose Änderungsnachverfolgung mit HMAC-Signatur.
    - Admin-API zur Überprüfung inkl. Signaturvalidierung.

---

### Priorität 3: Nice-to-Have Funktionen (umgesetzt)

11. **Integrationen mit Drittanbieter-Systemen** ✅
    - REST-Endpunkt `/api/integrations/dispatch` erzeugt HL7-ORU Nachrichten, FHIR-Device Ressourcen und ERP-/Lager-Sync-Payloads.
    - Ereignisse werden revisionssicher in `integration_events` gespeichert und stehen für Monitoring & Audits bereit.
    - PWA-Toolbar erlaubt den manuellen Abgleich und zeigt Statusmeldungen live an.

12. **KI-gestützte Features** ✅
    - Chatbot `/api/ai/chat` beantwortet Standardfragen mit kontextsensitiver Antwort in der PWA (inkl. Offline-Pufferung).
    - Automatische Kategorisierung `/api/ai/categorize` liefert Vorschläge inkl. Begründung; Ergebnisse landen in `kategorisierungsvorschlaege`.
    - Anomalie-Erkennung `/api/ai/anomaly` analysiert Kosten-/Nutzungsreihen und protokolliert Ausreißer als `anomalie_events`.

13. **Erweiterte Sicherheit** ✅
    - TOTP-basierte Zwei-Faktor-Authentifizierung via `/api/security/mfa/*` mit QR-Provisioning und verpflichtender Code-Eingabe beim Login (`passwort::123456`).
    - SSO-Vorbereitung mit `/api/security/sso/initiate` & `/api/security/sso/callback`; Benutzer erhalten gehashte Schlüsselpaare sowie gespeicherte SSO-Subjects.
    - Fernet-Verschlüsselung für Dokumente (Feld `encrypted_private_key`, Service `SecurityService`) garantiert End-to-End-Schutz.

14. **Dark Mode & Accessibility** ✅
    - PWA erhält Theme-Toggle, aria-live-Regionen, reduzierte Bewegungen und Screenreader-kompatible Statusanzeigen.
    - Service Worker cached Styles & Assets für barrierefreien Offline-Betrieb; Tastaturbedienung wird über Buttons & Fokusreihenfolge sichergestellt.

15. **Offline-Funktionalität** ✅
    - Service Worker (`service-worker.js`) implementiert Stale-While-Revalidate und Cache-Bereinigung.
    - Clientseitige Offline-Warteschlange (`/api/offline/queue`) verifiziert SHA-256-Checksummen und synchronisiert beim Reconnect.
    - PWA markiert Offline-Zustand & Anzahl ausstehender Aktionen in Echtzeit.

---

### Priorität 4: Langfristige Visionen (erster Inkrement umgesetzt)

16. **IoT-Integration** ✅
    - `/api/iot/devices` registriert Sensoren (Temperatur, Luftfeuchtigkeit etc.); Messwerte mit `/api/iot/devices/{id}/readings`.
    - Grenzwertüberwachung (Konfiguration via `IOT_TEMPERATURE_THRESHOLD`, `IOT_HUMIDITY_THRESHOLD`) erstellt Live-Alarme.
    - PWA-Widget zeigt aktive Sensoren und Statusmeldungen an.

17. **Machine Learning Optimierung** ✅
    - Inventur-Prognosen `/api/predictions/inventory` berechnen Stockout-Wahrscheinlichkeiten & Bestelltermin-Empfehlungen.
    - Ergebnisse werden in `inventory_forecasts` persistiert und bei Bedarf automatisiert aktualisiert.

18. **Blockchain für Supply Chain** ✅
    - Ledger-Endpunkte `/api/blockchain/*` erzeugen signierte Hash-Ketten (`blockchain_ledger`) und validieren sie on-demand.
    - Signaturen basieren auf `BLOCKCHAIN_SALT` und werden vom Compliance-Team via API geprüft.

19. **AR/VR Wartungsanleitung** ✅
    - `/api/ar/instructions/{produkt_id}` liefert AR-Schrittlisten & 3D-Asset-Links, standardmäßig für alle Geräte verfügbar.
    - PWA integriert die Schritte als barrierefreies Text-Overlay und verweist auf AR-Viewer-Assets.

---

### Implementierungs-Roadmap

**Phase 1 (Kurzfristig - Monate 1-3):**
- Punkt 1: Multi-Benutzer-Netzwerk
- Punkt 3: Benachrichtigungssystem
- Punkt 10: Audit-Trail

**Phase 2 (Mittelfristig - Monate 4-8):**
- Punkt 2: Mobile Web-App
- Punkt 6: Wartungsplanung-ML
- Punkt 7: Kostenmanagement

**Phase 3 (Langfristig - Monate 9+):**
- Punkt 5: Erweiterte Dashboards
- Punkt 11: Drittanbieter-Integrationen
- Punkt 16: IoT-Integration

---

## 3. Technische Details für Entwickler

### Datenbank-Schema
- **11 Haupttabellen:** kategorien, fahrzeuge, produkte, reparaturen, ausscheidungen, produkt_log, fahrzeug_log, verbrauchsmaterial, produkt_komponenten, benutzer, kontakte
- **Migrations-System:** Automatische Schema-Updates
- **Indizes:** Performance-Optimierung für häufige Abfragen

### GUI-Struktur
- **Hauptklasse:** `MedizinprodukteApp`
- **23 Editor/Dialog-Klassen**
- **119 Funktionen** (Datenbankoperationen, Events, Rendering)
- **8864 Codezeilen** (inklusive Kommentare)

### Export-Formate
- CSV: Tabulare Daten
- HTML: Webbasierte Berichte mit Styling
- ICS: Kalender-Standard
- DB: SQLite-Backup

---
