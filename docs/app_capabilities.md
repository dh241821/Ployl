# Funktionsübersicht – Medizinprodukte-Management-System

Diese Liste sammelt die wichtigsten Funktionen der Anwendung in kompakter Form. Sie ergänzt das Benutzerhandbuch und die technische Dokumentation um eine schnell scanbare Übersicht, was Desktop-App, Backend und PWA leisten.

## Kernfunktionen der Desktop-App
- **Rollen- & Standortbewusster Login:** Dienstnummer/Benutzername mit Passwort, Rechte pro Rolle *und* Standort (inkl. geerbter Rechte über Bezirke/Bezirksstellen/Ortsstellen), MFA/SSO optional.
- **Personalisierung & Barrierefreiheit:** Hell/Dunkelmodus, Schriftgrößen-Scaling, gespeicherte Filter und Dashboard-Layouts, konfigurierbare KPI-Widgets.
- **Globale Suche & Tastaturkürzel:** Ein Suchfeld durchsucht Produkte, Fahrzeuge, Material und Kontakte gleichzeitig; viele Dialoge besitzen Shortcuts (z. B. `Ctrl+F` für Filter).
- **Scrollbare, linke Navigation:** Arbeitsbereiche (Dashboard, Produkte, Fahrzeuge, Material, Komponenten, Bestellungen, Wartung, Auswertungen, Stammdaten, Konto/Hilfe) sind linksbündig in einer Sidebar erreichbar, alle Grids auto-sizen ihre Spalten.

## Produktverwaltung
- **Anlage & Bearbeitung:** Pflichtfeld Seriennummer (unique), STK/MTK-Intervalle, Hersteller-Dropdown, Typ/Modell-Autocomplete, Standort- und Fahrzeugzuordnung mit Funkkennung, interne Kennung, Status (Im Dienst/In Reparatur/Ausgeschieden), Freitextinfos.
- **Komponenten & Wartungen als Reiter:** Bereits beim Anlegen nutzbar; Komponenten können gesucht, repariert, reaktiviert oder ausgeschieden werden – mit Dateiuploads, Kontakten, Kosten und Historie.
- **Reparaturen & Wartungen:** Reparaturarten/Wartungstypen aus Stammdaten, Upload-Kategorien, Kostenfelder, Kontakte, Abschluss- und Freigabe-Buttons; ICS-Export für Fälligkeiten.
- **Lebenslauf & Exporte:** HTML/PDF/CSV/ICS-Exporte mit automatischer Dateibenennung, Produkt-Lebenslauf inkl. Fahrzeug-Einsatzhistorie; Button zum verknüpften Fahrzeug-Lebenslauf.
- **Batch-Funktionen:** Massenupload gleichartiger Produkte mit unterschiedlichen Seriennummern, Standort-/Fahrzeugwechsel aller Produkte eines Fahrzeugs, Import/Export-Optionen.

## Komponenten-Workspace
- **Globale Komponentensuche:** Standort- und Fahrzeugkontext, Statusfilter (aktiv, in Reparatur, ausgeschieden), Autocomplete für Typen und Upload-Kategorien.
- **Reparaturparität:** Identische Reparaturdialoge wie bei Produkten (Typ, Kontakt, Kosten, Anhänge, Abschluss), Lifecycle-Export je Komponente inkl. Einsatz in Produkten/Fahrzeugen.
- **Statuswechsel:** Aktivieren, Reparatur melden/abschließen, ausscheiden und reaktivieren mit Audit-Log und Historieneintrag.

## Wartungsplanung & Automatisierung
- **STK/MTK & Wartungspläne:** DateEntry-Kalender, Intervallberechnung, nächste Fälligkeiten im Dashboard, ICS-Export und Kalender-Integration.
- **Predictive Maintenance:** ML-Modell schlägt Servicefenster vor (`/api/maintenance`), Wartungs-Refresh via Scheduler oder API.
- **Benachrichtigungen:** E-Mail/SMS/Push (über Backend-Notifier), Start-Popups für fällige Wartungen, optionale Kalender-Reminders.

## Fahrzeuge
- **Fahrzeugakten:** Kategorien (RTW, KTW, NEF, Logistik, etc.), Marke/Typ-Relation mit Autocomplete, Funkkennung, Fahrgestellnummer optional, In-/Außerbetriebnahme mit Datum.
- **Produktübernahme:** Produkte eines Fahrzeugs auf ein anderes verschieben, Fahrzeug-Lebenslauf (HTML/PDF) mit Produkt- und Wartungshistorie.
- **Filter & Suche:** Standort-/Typ-/Kategorie-Filter, globale Suche liefert Kennzeichen/Funkkennung.

## Materialverwaltung
- **Bestände & Verfall:** Bezeichnung mit Autocomplete, Kategorie (statt ID), Lagerort als Funkkennung/Standort, Verfallsdatum mit deaktivierbarer Checkbox, Niedrig-/Abgelaufen-Filter, Statistik über hinzugefügtes Material.
- **Bestellungen & Buchungen:** Bestelllisten/CSV/PDF, Bestell-Workflow mit Freigabe, Bestandänderung mit Audit.

## Stammdaten & Rechte
- **Hierarchische Standorte:** Landesverband → Bereich → Bezirk → Bezirksstelle → Ortsstelle mit Funkkennung; Rechte vererben sich abwärts, Standortfilter besitzen Autocomplete und breite Eingabefelder.
- **Kataloge & Vorschlagslisten:** Produkt-/Materialkategorien, Typen/Modelle, Hersteller, Komponenten- und Wartungstypen, Reparatur- und Uploadkategorien, Ausscheidungsgründe, Fahrzeugkategorien/Marken/Modelle – alles bearbeitbar und per One-Click-Seeding befüllbar.
- **Benutzer & Rollen:** Vordefinierte Rollen (Admin, Leitstelle, Technik, Lager, Viewer, Mitarbeiter, Manager) mit sinnvollen Read/Write-Presets; Benutzerverwaltung nur für Admin sichtbar; Standortrechte je Ebene editierbar.

## Sicherheit, Audit & Governance
- **Passwort-Hashing & MFA/SSO:** PBKDF2-Hashing mit Salt, optionale MFA-Login-Syntax `passwort::totp`, SSO-Redirects und verschlüsselte Dokumente/Backups.
- **Audit-Log & System-Log:** Jede Änderung schreibt Before/After in `audit_log`; System-Log hält Fehler/Events fest; Log-Viewer im Admin-Bereich, Export/Filter verfügbar.
- **Mandantenfähigkeit:** `mandant_id` pro Datensatz, Abfragen automatisch mandantenbegrenzt; Rechteprüfungen pro Mandant und Standort.

## Backend, API & PWA
- **FastAPI-Backend:** Auth/JWT, Rollenprüfung, REST-Router für Produkte, Reparaturen, Wartungen, Kosten, Geo-Tracking, Integrationen (HL7/FHIR/ERP), IoT, KI, Offline-Queue, Blockchain, AR/Scanner.
- **Scheduler & Jobs:** APScheduler für Wartungs-Refresh, Benachrichtigungen, Backups und Predictive Tasks.
- **PWA/Frontend:** Dashboard mit KPI/Charts, QR/Barcode-Scanner, Offline-Caching, Dark-Mode, Produkt-/Reparatur-Formulare, mobile Optimierung.

## Exporte, Backup & Wiederherstellung
- **Berichte & Formate:** HTML/PDF/CSV/ICS-Exports für Produkte, Komponenten, Fahrzeuge, Wartungen, Bestellungen, Auswertungen; automatisch benannte Dateien im `exports/`-Verzeichnis.
- **Backups & Restore:** Automatisches Backup beim Beenden; Backup/Restore-Dialog mit Dateiauswahl und Sicherheitsabfragen; Archivierung/Kompression älterer Logs möglich.
- **Dokumentenablage:** Upload-Ablage mit Kategorien, Öffnen/Löschen aus der GUI, Filesystem-Speicherort via Konfiguration.

## Validierung & Qualität
- **Zentralisierte Regeln:** Seriennummern-Eindeutigkeit, Pflichtstandort/Fahrzeug, Wartungsdaten- und Intervallprüfung, Plausibilitätschecks (z. B. Anschaffung < Wartung < Ausscheidung), Dublettenerkennung bei Kontakten/Herstellern.
- **Tests & Migrationen:** Pytest-Suite für Datenbank, Permissions, Validierungen, Governance; Schema-Versionierung und Spalten-Nachrüstungen über `_ensure_columns`.

## Hilfen & Onboarding
- **Benutzerhandbuch & Hilfedialog:** Kontextbezogene Tooltips, Hilfe-Fenster mit Screenshots und Prozessbeschreibungen, Onboarding-Hinweise beim ersten Start.
- **Roadmap & Architektur:** Klar priorisierte Roadmap, technische Dokumentation (Datenbank, Module, Deployment) und Windows-spezifische Installationshilfe.
