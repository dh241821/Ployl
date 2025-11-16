# Benutzerhandbuch

Dieses Handbuch beschreibt die wichtigsten Arbeitsabläufe für Anwenderinnen und Anwender des Medizinprodukte-Management Systems.

## 1. Anmeldung

1. Starte die Desktop-App (`python main_app.py`).
2. Melde dich mit deiner **Dienstnummer** und deinem Passwort an.
3. Beim ersten Login empfiehlt es sich, das Standardpasswort über **Benutzerprofil → Passwort ändern** anzupassen.

## 2. Dashboard verstehen

- **Kennzahlenkarten** zeigen fällige Wartungen, Geräte in Reparatur, ausgemusterte Produkte und kritische Materialbestände.
- Die **Status-Grafik** visualisiert die Verteilung „Im Dienst“, „In Reparatur“ und „Ausgeschieden“.
- Über das **Suchfeld** kannst du Produkte, Fahrzeuge oder Materialien live filtern.

## 3. Produkte verwalten

### 3.1 Neues Produkt anlegen

1. Öffne den Tab **Produkte** und klicke auf **Neues Produkt**.
2. Fülle die Pflichtfelder aus:
   - **Produkttyp**, **Modell**, **Seriennummer**
   - **Standort** und entweder **Fahrzeug (Funkkennung)** oder **Lagerort**
3. Wähle optional STK/MTK-Intervalle und nutze den Button **Termin berechnen**, um das nächste Prüfdatum zu setzen.
4. Trage interne Kennung, Informationstext sowie Hersteller ein.
5. Nutze die Reiter **Komponenten** und **Wartungen**, um Teilkomponenten oder geplante Kontrollen zu erfassen, bevor du speicherst.
6. Schließe mit **Speichern** ab.

### 3.2 Produkt bearbeiten

- Doppelklicke auf ein Produkt oder nutze **Bearbeiten** im Kontextmenü.
- Änderungen an Standort, Fahrzeug, Status oder STK/MTK-Daten werden versioniert protokolliert.
- Der Lebenslauf-Bericht wird automatisch mit dem Schema `JJJJ-MM-TT_Produkttyp_Modell_InterneKennung` benannt und enthält eine Einsatzfahrzeug-Timeline, die jede Zuordnung zu Funkkennungen inklusive Zeitraum dokumentiert.
- Fahrzeughistorien werden über den Tab **Fahrzeuge** exportiert; der Produkt-Lebenslauf enthält bereits eine eigene Einsatz-Timeline mit allen bisherigen Funkkennungen.

### 3.3 Reparatur melden

1. Wähle ein Produkt und öffne den Reiter **Reparaturen**.
2. Gib Reparaturtyp (aus Stammdaten), Kosten, Beschreibung und Status an.
3. Lade optional Dateien hoch und kategorisiere die Anhänge (z. B. Rechnung, Prüfbericht).
4. Setze den Status auf **In Reparatur** oder zurück auf **Im Dienst**, sobald die Maßnahme erledigt ist.

### 3.4 Produkt ausscheiden

- Setze den Status auf **Ausgeschieden**. Das Produkt bleibt erhalten, wird aber standardmäßig ausgeblendet.
- Aktiviere/Deaktiviere den Button **Ausgeschiedene anzeigen**, um archivierte Geräte einzublenden.

### 3.5 Komponenten suchen & Status ändern

- Über den Arbeitsbereich **Komponenten** filterst du Teilkomponenten nach Name, Seriennummer, Standort oder Status.
- Wähle eine Komponente aus und nutze die Buttons **Reparatur**, **Reparatur beendet**, **Ausscheiden** oder **Aktivieren**, um den Lebenszyklus zu pflegen.
- Dieselben Aktionen stehen auch im Produkteditor im Reiter **Komponenten** zur Verfügung; alle Schritte werden automatisch im Produkt-Lebenslauf protokolliert.
- Beim Melden einer Komponentenreparatur stehen dir nun Reparaturtyp, Kontakt, Kostenfeld sowie Datei-Uploads mit Kategorien genauso wie bei Produkten zur Verfügung.
- Über **Reparaturen anzeigen** öffnest du die vollständige Komponentenhistorie inklusive Anhänge-Übersicht.
- Der Button **Komponenten-Lebenslauf** erzeugt einen HTML-Bericht mit Einsatzhistorie (welches Produkt, welches Fahrzeug, Zeitraum) sowie allen Reparaturen und kann direkt aus dem Komponenten-Arbeitsbereich oder dem Produkteditor geöffnet werden.

## 4. Fahrzeuge verwalten

1. Tab **Fahrzeuge** → **Neues Fahrzeug**.
2. Gib **Bezeichnung/Funkkennung**, **Kategorie** (RTW, KTW, …), **Marke**, **Typ** und **Standort** ein.
3. Hinterlege **Inbetriebnahme** sowie optional **Außerbetriebnahme** mit Datum und Checkbox.
4. Aktualisiere Kilometerstände über den Button **KM-Stand buchen**.

## 5. Materialverwaltung

- Materialeinträge nutzen **Bezeichnung** (Auto-Vervollständigung), **Kategorie**, **Lagerort** sowie eine optionale **Verfallsdatum-Checkbox**.
- Bestandsänderungen werden in der Historie dokumentiert und fließen in die Dashboard-KPIs ein.

## 6. Stammdaten pflegen

- **Standorte:** Abbildung der Hierarchie Landesverband → Bereich → Bezirk → Bezirksstelle → Ortsstelle.
- **Hersteller, Produkttypen, Modelle, Komponenten- und Wartungstypen** lassen sich hinzufügen oder entfernen.
- **Kontakte:** Zusätzliche Felder für Unternehmen, Website und Info unterstützen Reparatur- und Lieferantenverwaltung.
- **Upload-Kategorien & Ablage:** Verwaltet Kategorien und öffnet eine Upload-Ablage, in der du Dateien zentral speicherst und später in Reparaturen referenzierst.
- **Benutzer:** Weise Lese-/Schreibrechte pro Modul und optional pro Standort zu.

## 7. Auswertungen & Exporte

- Register **Auswertung** liefert Kostentrends, Reparaturausgaben pro Kategorie/Fahrzeug und Statusstatistiken.
- **Druckfunktionen** erzeugen HTML-Listen für Fahrzeuge, Standorte oder Produktgruppen.
- Über den Web-Zugang (PWA) lassen sich Produkte und Reparaturen auch von mobilen Geräten erfassen.

## 8. Personalisierung

- Unter **Einstellungen → Personalisierung** stehen helle/dunkle Designs, Glas-Effekte und individuelle Schriftgrößen zur Auswahl.
- Die gewählten Einstellungen werden benutzerspezifisch gespeichert.

## 9. Hilfe & Support

- Die integrierte **Wissensbasis** (Fragezeichen-Symbol) bietet Kurzvideos und FAQ-Einträge.
- Für technische Unterstützung: `support@medizinprodukte-app.example` oder das Ticketsystem im Menü **Hilfe**.

