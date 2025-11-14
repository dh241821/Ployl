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
- **Lebenslauf**: Detaillierter HTML-Bericht mit QR-Code (Dateimenü)
- **Listendruck**: Aktuelle Filterliste als HTML drucken
- **CSV-Export**: Alle Produkte als CSV exportieren (für Excel)

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

### Priorität 2: Mittlere Verbesserungen

6. **Automatisierte Wartungsplanung**
   - ML-basierte Vorhersage von Ausfallzeiten
   - Automatische Wartungsplanung nach Nutzungsdaten
   - Optimale Servicefenster-Vorschläge
   - **Vorteil:** Weniger ungeplante Ausfallzeiten

7. **Kostenmanagement**
   - Detaillierte Reparaturen-Kostenerfassung
   - Lebenszyklus-Kostenanalyse (TCO)
   - ROI-Berechnung für Produkte
   - Vergleich: Reparatur vs. Neukauf
   - **Vorteil:** Bessere Budget-Planung

8. **Dokumentenverwaltung**
   - OCR für gescannte Rechnungen/Handbücher
   - Automatische Katalog-Verschlagwortung
   - Volltextsuche in Dokumenten
   - Cloud-Integration (OneDrive/Google Drive)
   - **Vorteil:** Alle Dokumente zentral abrufbar

9. **Geo-Location & Asset-Tracking**
   - GPS-Tracking für Fahrzeuge (Live-Map)
   - Automatische Standort-Bestimmung
   - Routenoptimierung für Wartungen
   - **Vorteil:** Know wo deine Fahrzeuge sind

10. **Audit-Trail & Compliance**
    - Detailliertes Änderungsprotokoll (wer, wann, was)
    - Digitale Signaturen für Wartungen
    - Compliance-Berichte (DIN, MDR etc.)
    - Datenexporte für Behörden
    - **Vorteil:** Regulatorische Anforderungen erfüllt

---

### Priorität 3: Nice-to-Have Funktionen

11. **Integrationen mit Drittanbieter-Systemen**
    - HL7/FHIR für Krankenhäuser
    - Integration mit ERP-Systemen (SAP, Oracle)
    - Automatische Rechnungsstellung
    - Bestandsabstimmung mit Lagerverwaltung
    - **Vorteil:** Weniger manuelle Synchronisation

12. **KI-gestützte Features**
    - Chatbot für Häufige Fragen
    - Automatische Kategorisierung von Produkten
    - Anomalie-Erkennung (ungewöhnliche Reparaturmuster)
    - **Vorteil:** Intelligente Unterstützung

13. **Erweiterte Sicherheit**
    - Two-Factor Authentication (2FA)
    - SSO-Integration (Active Directory)
    - Datenverschlüsselung (AES-256)
    - Compliance mit DSGVO/GDPR
    - **Vorteil:** Erhöhte Sicherheit & Datenschutz

14. **Dark Mode & Accessibility**
    - Dark Mode für nächtliche Arbeit
    - Großkopf-Modus für ältere Benutzer
    - Sprachausgabe/Screenreader-Support
    - Tastatur-Navigation
    - **Vorteil:** Barrierefreier Zugang

15. **Offline-Funktionalität**
    - Lokal arbeitendes Mini-System
    - Automatische Sync beim Online-Gehen
    - Konfliktauflösung bei Änderungen
    - **Vorteil:** Nutzbar auch ohne Internet

---

### Priorität 4: Langfristige Visionen

16. **IoT-Integration**
    - Sensoranbindung für Temperatur/Lagerbedingungen
    - Automatische Reparaturbenachrichtigungen (z.B. von Geräte-Fehler)
    - Smart Locker mit Zugangsprotokoll
    - **Vorteil:** Vollständig automatisierte Überwachung

17. **Machine Learning Optimierung**
    - Automatische Bestands-Optimierung
    - Vorhersage von Material-Verfallsdaten
    - Anomalie-Erkennung bei Nutzungsmustern
    - **Vorteil:** Intelligente Ressourcen-Nutzung

18. **Blockchain für Supply Chain**
    - Unveränderliche Lieferketten-Dokumentation
    - Transparente Reparaturhistorie
    - **Vorteil:** Vertrauenswürdige Herkunftsnachweise

19. **AR/VR Wartungsanleitung**
    - Augmented Reality zur Wartung
    - Interaktive 3D-Modelle von Geräten
    - **Vorteil:** Weniger Fehler bei komplexen Wartungen

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
