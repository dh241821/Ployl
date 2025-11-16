"""SQLite database management for the Medizinprodukte Management System."""

from __future__ import annotations

import base64
import contextlib
import io
import json
import logging
import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

import qrcode
from app.auth import (
    LocationPermission,
    PERMISSION_COLUMNS,
    PERMISSION_DEFAULTS,
    PERMISSION_MODULES,
    ROLE_CHOICES,
    ROLE_PERMISSION_PRESETS,
    User,
)
from app.config import get_db_path, get_storage_dir
from app.security import hash_password, verify_password
from app.services import (
    ValidationError as ProductValidationError,
    validate_product,
)

STATUS_LABELS: Dict[str, str] = {
    "im_dienst": "Im Dienst",
    "in_reparatur": "In Reparatur",
    "ausgeschieden": "Ausgeschieden",
}


BEREICH_BEZIRK_MAP: Dict[str, List[str]] = {
    "Waldviertel": [
        "Gmünd",
        "Horn",
        "Krems (Land)",
        "Krems (Stadt)",
        "Waidhofen an der Thaya",
        "Zwettl",
    ],
    "Weinviertel": [
        "Gänserndorf",
        "Hollabrunn",
        "Korneuburg",
        "Mistelbach",
    ],
    "Mostviertel": [
        "Amstetten",
        "Lilienfeld",
        "Melk",
        "Scheibbs",
        "St. Pölten (Land)",
        "St. Pölten (Stadt)",
        "Waidhofen an der Ybbs",
    ],
    "Industrieviertel": [
        "Baden",
        "Bruck an der Leitha",
        "Mödling",
        "Neunkirchen",
        "Tulln",
        "Wiener Neustadt (Land)",
        "Wiener Neustadt (Stadt)",
    ],
    "Katastrophenhilfsdienst": ["Landesweit"],
}

BEZIRK_TO_BEREICH: Dict[str, str] = {
    bezirk: bereich for bereich, bezirke in BEREICH_BEZIRK_MAP.items() for bezirk in bezirke
}


FAHRZEUG_KATEGORIEN: List[str] = [
    "RTW – Rettungswagen",
    "KTW – Krankentransportwagen",
    "NAW – Notarztwagen",
    "NEF – Notarzteinsatzfahrzeug",
    "ITW – Intensivtransportwagen",
    "GRTW – Großraumrettungswagen",
    "E-RTW – elektrisches Rettungsfahrzeug",
    "First-Responder-Fahrzeug",
    "First-Responder-Motorrad",
    "LNA-/OrgL-Fahrzeug",
    "Dienst-PKW",
    "Dienst-PKW Einsatzleitung",
    "Fahrzeugeinsatzleitung",
    "Logistikfahrzeug",
    "Logistikbus Material",
    "Materialbus",
    "Anhänger (Material / Technik)",
    "Sonderfahrzeug (SEG / Katastrophenschutz)",
    "Schulungsfahrzeug",
]

PRODUKT_KATEGORIEN: List[str] = [
    "Monitoring",
    "Beatmung & Sauerstoff",
    "Defibrillation & Reanimation",
    "Infusion & Spritzenpumpen",
    "Diagnostik (Blutdruck, Temperatur, SpO₂, etc.)",
    "Transport & Immobilisation",
    "Notfallrucksäcke & -taschen",
    "Kommunikation & IT",
    "Inkubatoren & Wärmesysteme",
    "OP- / Eingriffsgeräte",
    "Labor & Point-of-Care",
    "Möbel & Einrichtung",
    "Logistik & Lagertechnik",
    "Sonstige Medizinprodukte",
]

MATERIAL_KATEGORIEN: List[str] = [
    "Verbandmaterial",
    "Beatmungszubehör (Masken, Tuben, Filter)",
    "Infusions- & Injektionsmaterial",
    "Desinfektion & Hygiene",
    "Einmalinstrumente",
    "Schutzausrüstung (PSA)",
    "Diagnostik-Einmalmaterial (Teststreifen, Lanzetten, etc.)",
    "Laborverbrauchsmaterial",
    "Büro- & Organisationsmaterial",
    "Fahrzeug-/Rettungsmittelausstattung (kleinteilig)",
    "Sonstiges Verbrauchsmaterial",
]

PRODUKT_VORSCHLAEGE: List[str] = [
    "Defibrillator / Monitor-Defi",
    "AED (Automatisierter Externer Defibrillator)",
    "Transportmonitor-Defi Kombination",
    "Patientenmonitor",
    "EKG-Schreibgerät",
    "Beatmungsgerät transportabel",
    "Beatmungsgerät stationär",
    "Sauerstoffkonzentrator",
    "Spritzenpumpe",
    "Infusionspumpe",
    "Perfusor",
    "Absaugpumpe mobil",
    "Absaugpumpe stationär",
    "Pulsoxymeter Handgerät",
    "Blutzuckermessgerät",
    "Blutdruckmessgerät automatisiert",
    "Inkubator Transport",
    "Wärmedecke / Wärmesystem",
    "Notfallrucksack Erwachsener",
    "Notfallrucksack Pädiatrie",
    "Intubationsset / Airway-Set",
    "Intubationsvideo-Laryngoskop",
    "Spineboard",
    "Vakuummatratze",
    "Schaufeltrage",
    "Fahrtrage RTW",
    "Tragestuhl",
    "Schienensatz (SAM-Splint etc.)",
    "EpiPen / Autoinjektortrainer",
    "Einsatztablet",
    "Einsatzhandy",
    "Funkgerät HRT",
    "Funkgerät MRT",
    "Ladehalterung Defibrillator",
    "Ladegerät Akkus",
    "Medizingeräteschrank / Materialschrank",
    "Medikamentenkoffer",
    "Thoraxkompressionsgerät",
    "Mobile Ultraschallgeräte (Handheld)",
    "Point-of-Care Blutgasanalysengerät",
    "Mobile CT oder C-Bogen",
    "Isolations-/Infektionswagen",
    "Telemedizin-Kit für Rettungsdienst",
    "Mobile Patientenlagerungs-/Verlagerungssysteme",
    "Sanitär-/Hygiene-Station Transport",
    "Kühlung & Hitze-Notfallausrüstung",
    "Hilfeleistungsausrüstung Technische Rettung",
    "CPAP-Therapiesystem",
    "Infusionswärmer",
    "Transportinkubator neonatal",
    "Mechanische Reanimationshilfe",
    "Digitales Stethoskop",
    "Mobiles Laborpanel",
    "Telemedizinische Konsolestation",
    "POC-Gerinnungsgerät",
    "CBRN-Messkoffer",
    "Einsatzdrohne zur Lageerkundung",
]

MATERIAL_VORSCHLAEGE: List[str] = [
    "Venenverweilkanüle 18G (grün)",
    "Venenverweilkanüle 20G (rosa)",
    "Venenverweilkanüle 16G (grau)",
    "Venenverweilkanüle 14G (gelb)",
    "Venenverweilkanüle 22G (schwarz)",
    "Infusionslösung NaCl 0,9 % 500 ml",
    "Infusionslösung Ringer 500 ml",
    "Infusionslösung Ringer L 1000 ml",
    "Infusionslösung Glukose 5 % 500 ml",
    "Infusionsbesteck Einweg",
    "Infusionsbesteck mit Injektionsanschluss",
    "Dreiwegehahn Luer-Lock",
    "Dreiwegehahn Luer-Lock mit Stopfen",
    "Spritze 2 ml Luer-Lock",
    "Spritze 5 ml Luer-Lock",
    "Spritze 10 ml Luer-Lock",
    "Spritze 20 ml Luer-Lock",
    "Kanüle 21G (grün)",
    "Kanüle 23G (blau)",
    "Kanüle 18G (grau)",
    "Guedel-Tubus Größe 2",
    "Guedel-Tubus Größe 3",
    "Guedel-Tubus Größe 4",
    "Guedel-Tubus Größe 5",
    "Larynxtubus Größe 3",
    "Larynxtubus Größe 4",
    "Larynxtubus Größe 2",
    "Sauerstoffmaske Erwachsener",
    "Sauerstoffmaske Kind",
    "Sauerstoffbrille Erwachsener",
    "Sauerstoffbrille Kind",
    "Beatmungsbeutel Erwachsener mit Reservoir",
    "Beatmungsbeutel Erwachsener ohne Reservoir",
    "Beatmungsbeutel Kind mit Reservoir",
    "Beatmungsbeutel Neugeboren mit Reservoir",
    "PEEP-Ventil",
    "PEEP-Ventil für Beatmung",
    "Filter HMEF",
    "Filter HMEF Standard",
    "Filter HMEF mit CO₂ Messanschluss",
    "OP-Mundschutz Typ IIR",
    "OP-Mundschutz Typ II",
    "Untersuchungshandschuhe Nitril M",
    "Untersuchungshandschuhe Nitril L",
    "Untersuchungshandschuhe Nitril XS",
    "Untersuchungshandschuhe Nitril XL",
    "Schutzkittel Einweg",
    "Schutzkittel Steril Einweg",
    "Fixierpflaster 2,5 cm x 9,2 m",
    "Fixierpflaster 5 cm x 5 m",
    "Heftpflaster Strips",
    "Heftpflaster superfine 1 cm x 6 m",
    "Wundkompresse steril 10x10 cm",
    "Wundkompresse steril 5x5 cm",
    "Wundkompresse unsteril 10x20 cm",
    "Mullbinde 8 cm",
    "Mullbinde 10 cm",
    "Rettungsdecke gold/silber",
    "Rettungsdecke gold/silber XXL",
    "Desinfektion Hände",
    "Desinfektion Hände Alkohollösung 500 ml",
    "Flächendesinfektion 1 l",
    "Flächendesinfektion 5 l",
    "Teststreifen Blutzucker",
    "Teststreifen Blutzucker Spezial",
    "Lanzetten für Blutzuckergerät",
    "Lanzetten für Blutzuckergerät steril",
    "Elektroden EKG Einmal",
    "Elektroden EKG Einmal erwachsen",
    "Elektroden EKG Einmal Kind",
    "Manschette Blutdruck Erwachsene",
    "Manschette Blutdruck Erwachsene groß",
    "Manschette Blutdruck Erwachsene klein",
    "Manschette Blutdruck Kinder",
    "Schienensatz SAM Splint Universal",
    "Spineboard Aluminium mit Kopffixierung",
    "Vakuummatratze aufblasbar",
    "Schaufeltrage mit Rettungskissen",
    "Tragestuhl klappbar",
    "Notfallrucksack Erwachsener Alpha-Kit",
    "Notfallrucksack Pädiatrie Beta-Kit",
    "Einsatztablet ruggedized",
    "Funkgerät HRT Handgerät",
    "Ladehalterung Defibrillator Wandmontage",
    "Wartungstimer Gerät",
    "Sauerstoffflasche 2 l (gefüllt)",
    "Sauerstoffflasche 10 l (gefüllt)",
    "CPAP-Maske Einweg",
    "NIV-Maske Erwachsene",
    "Verbrennungstuch steril",
    "Augenspülung 500 ml",
    "Infusionswärmeschlauch",
    "Hypothermie-Care-Paket",
    "Kälte-/Hitze-Gelkompresse",
    "CPR-Board",
]

HERSTELLER_VORSCHLAEGE: List[str] = [
    "Corpuls",
    "Zoll Medical",
    "Physio-Control (Stryker)",
    "Stryker",
    "Philips Healthcare",
    "Dräger",
    "Hamilton Medical",
    "Weinmann Emergency",
    "Weinmann",
    "Laerdal",
    "B. Braun",
    "Fresenius Kabi",
    "Fresenius Medical Care",
    "Fresenius MedCare",
    "Mindray",
    "GE Healthcare",
    "Nihon Kohden",
    "Teleflex",
    "Hartmann",
    "Paul Hartmann AG",
    "Lohmann & Rauscher",
    "Masimo",
    "Medtronic",
    "Smiths Medical",
    "Getinge (Maquet)",
    "Maquet (Getinge)",
    "Ambu",
    "Welch Allyn",
    "Covidien",
    "3M",
    "Karl Storz",
    "Storz",
    "Heine Optotechnik",
    "Terumo",
    "BD (Becton Dickinson)",
    "ResMed",
    "Agfa HealthCare",
]

TYP_MODELL_VORSCHLAEGE: List[Tuple[str, str]] = [
    ("Defibrillator / Monitor-Defi", "Corpuls3"),
    ("Defibrillator / Monitor-Defi", "Corpuls1"),
    ("Defibrillator / Monitor-Defi", "Lifepak 12"),
    ("Defibrillator / Monitor-Defi", "Lifepak 15"),
    ("Defibrillator / Monitor-Defi", "Lifepak 20e"),
    ("Defibrillator / Monitor-Defi", "Zoll X Series"),
    ("Defibrillator / Monitor-Defi", "Zoll E Series"),
    ("Defibrillator / Monitor-Defi", "Zoll M Series"),
    ("Defibrillator / Monitor-Defi", "Philips HeartStart MRx"),
    ("Defibrillator / Monitor-Defi", "Philips Efficia DFM100"),
    ("Patientenmonitor", "Welch Allyn Propaq CS"),
    ("Patientenmonitor", "Mindray BeneHeart D3"),
    ("Patientenmonitor", "Mindray BeneHeart C2"),
    ("Patientenmonitor", "Mindray BeneVision N12"),
    ("Patientenmonitor", "GE Dash 3000"),
    ("Patientenmonitor", "GE Dash 4000"),
    ("Patientenmonitor", "Philips IntelliVue MP2"),
    ("Patientenmonitor", "Philips IntelliVue MX450"),
    ("Beatmungsgerät transportabel", "Hamilton T1"),
    ("Beatmungsgerät transportabel", "Hamilton C1"),
    ("Beatmungsgerät transportabel", "Hamilton C3"),
    ("Beatmungsgerät transportabel", "Dräger Oxylog 2000"),
    ("Beatmungsgerät transportabel", "Dräger Oxylog 2000 plus"),
    ("Beatmungsgerät transportabel", "Dräger Oxylog 3000"),
    ("Beatmungsgerät transportabel", "Dräger Oxylog 3000 plus"),
    ("Beatmungsgerät transportabel", "Weinmann Medumat Standard"),
    ("Beatmungsgerät transportabel", "Weinmann Medumat Transport"),
    ("Beatmungsgerät transportabel", "Weinmann Medumat Easy"),
    ("Absaugpumpe mobil", "Weinmann Accuvac Pro"),
    ("Absaugpumpe mobil", "Weinmann Accuvac Rescue"),
    ("Absaugpumpe mobil", "Laerdal Suction Unit LSU"),
    ("Infusionspumpe", "Fresenius Agilia"),
    ("Infusionspumpe", "B. Braun Infusomat Space"),
    ("Perfusor", "B. Braun Perfusor Space"),
    ("Perfusor", "B. Braun Perfusor Compact"),
    ("Intubationsset / Airway-Set", "Storz C-MAC Videolaryngoskop"),
    ("Intubationsset / Airway-Set", "Ambu King Vision"),
    ("Thoraxkompressionsgerät", "Laerdal LUCAS 2"),
    ("Thoraxkompressionsgerät", "Laerdal LUCAS 3"),
    ("Kommunikation & IT", "Einsatztablet"),
    ("Kommunikation & IT", "Einsatzhandy"),
    ("AED (Automatisierter Externer Defibrillator)", "Zoll AED Plus"),
    ("AED (Automatisierter Externer Defibrillator)", "Zoll AED 3"),
    ("AED (Automatisierter Externer Defibrillator)", "Lifepak CR Plus"),
    ("AED (Automatisierter Externer Defibrillator)", "Lifepak CR2"),
    ("AED (Automatisierter Externer Defibrillator)", "Philips HeartStart HS1"),
    ("AED (Automatisierter Externer Defibrillator)", "Philips FRx"),
    ("Patientenmonitor", "Masimo Rad-97"),
    ("Patientenmonitor", "Mindray BeneVision N15"),
    ("Beatmungsgerät transportabel", "ResMed Lumis 150"),
    ("Beatmungsgerät transportabel", "Dräger Carina"),
    ("Infusionspumpe", "Terumo TE-171"),
    ("Infusionspumpe", "BD Alaris GW"),
    ("Perfusor", "Smiths Medical CADD-Solis"),
    ("Kommunikation & IT", "Panasonic Toughpad FZ-G2"),
    ("Kommunikation & IT", "Getac UX10"),
    ("Intubationsset / Airway-Set", "Verathon GlideScope Core"),
]

KOMPONENTEN_VORSCHLAEGE: List[str] = [
    "Akku / Batteriemodul",
    "Ladegerät / Ladestation",
    "Netzteil",
    "Stromkabel",
    "EKG-Patientenkabel",
    "EKG-Elektrodenkabel",
    "SpO₂-Sensor Fingerclip",
    "SpO₂-Verlängerungskabel",
    "NIBP-Schlauch",
    "NIBP-Manschette Erwachsener",
    "NIBP-Manschette Kinder",
    "CO₂-Sensor / Mainstream",
    "CO₂-Sensor / Sidestream",
    "Sauerstoffschlauch",
    "O₂-Druckminderer",
    "O₂-Flowmeter",
    "Atemkreisset Beatmungsgerät",
    "Filter / HME-Filter",
    "Schlauchsystem Absaugung",
    "Ansaugschlauch",
    "Kanister Absaugpumpe",
    "Halterung Gerät Fahrzeug",
    "Wandhalterung Ladegerät",
    "Softwarelizenz",
    "Speicherkarte / SD-Karte",
    "Drucker / Protokolldrucker",
    "Papierrolle Drucker",
    "SpO₂-Sensor Neugeboren",
    "NIBP-Adapter Kinder-Manschette",
    "Sauerstoff-Druckminderer mit Flowmeter",
    "Absaugpumpe geräuschreduziert",
    "Kanister Ersatz für Absaugpumpe",
    "Geräteladegerät (12 V / 220 V)",
    "KFZ-Ladeadapter (Fahrzeug)",
    "Halterung Fahrzeugleitung (Magnetfuß)",
    "Ersatz-Speicherkarte Protokollierung",
    "Drucker Papierrolle 80 mm",
    "USB-Stick geschütztes Backup",
    "Softwarelizenz Monitoring Modul 5 Jahre",
    "Firmware-Booster Karte",
    "Netzfilter Überspannungsschutz",
    "Kabelsatz Ethernet-Medizin (shielded)",
    "Patientenmonitoring Modul (invasive BP)",
    "Temperaturfühler-Anschluss",
    "EtCO₂-Schlauch steril",
    "HFNC-Schlauchsystem",
    "CPAP-Kopfband",
    "Batteriemodul Monitor",
    "Infusionswärmer-Sonde",
    "Datenlogger/SD-Modul",
    "Sicherungsset Halterung",
]

AUSSCHEIDUNGSGRUND_VORSCHLAEGE: List[str] = [
    "Technischer Defekt – wirtschaftlicher Totalschaden",
    "Technisch überholt / veraltet",
    "Ende Lebensdauer laut Hersteller (EoL)",
    "End-of-Life Hersteller",
    "Ersatz durch Neugerät",
    "Ersatzgerät eingeführt",
    "Serienfehler / Rückruf",
    "Rückruf durch Hersteller",
    "Verlust",
    "Diebstahl",
    "Unfall-/Sturzschaden",
    "Unfallgerät irreparabel",
    "Kontamination nicht sanierbar",
    "Kontamination (Biohazard)",
    "Unzureichende Dokumentation / unbekannter Zustand",
    "Projektende / Bedarf entfällt",
    "Projektende / Bedarf eingestellt",
    "Verschrottung gemäß Entsorgungsrichtlinie",
    "Verschrottung gem. Umweltvorgaben",
    "Spendenabgabe",
    "Spende an Hilfsorganisation",
    "Leasing-Rückgabe",
    "Defektkosten höher als Neugerät",
    "Umbau zum Schulungsgerät",
]

REPARATUR_DATEI_KATEGORIEN: List[str] = [
    "Kostenvoranschlag",
    "Reparaturbericht",
    "Foto Schaden",
    "Foto Gerät",
    "Rechnung",
    "Lieferschein",
    "Prüfprotokoll STK",
    "Prüfprotokoll MTK",
    "Prüfprotokoll DGUV V3",
    "Herstellerkorrespondenz",
    "Servicevertrag / Wartungsvertrag",
    "Versicherungsunterlagen",
    "Rückrufschreiben (FSN)",
    "Übergabedokumentation",
    "Betriebsanleitung",
    "Kurzanleitung / Quick-Guide",
    "Schulungsunterlagen",
    "Zertifikate / Konformitätserklärung",
    "Wartungsvertrag",
    "Übergabeprotokoll Fahrzeug",
    "Übergabeprotokoll Gerät",
    "Betriebsanleitung PDF",
    "Schulungsvideo",
    "Validierungs-/Prüfprotokoll",
    "Dienstfahrzeugcheckliste Foto",
    "Servicevertrag Scans",
    "Versicherungsunterlagen Fahrzeug/Medizintechnik",
    "Lieferantenkorrespondenz",
    "Gefahrstoffdatenblatt (GSD)",
    "Datenschutzerklärung / Datenschutz-Dokument",
    "Risikoanalyse Gerät",
]

REPARATUR_ARTEN_VORSCHLAEGE: List[str] = [
    "Fehleranalyse / Diagnose",
    "Elektronikdefekt",
    "Display / Bedieneinheit defekt",
    "Akku defekt",
    "Kabel / Anschluss defekt",
    "Sensor defekt",
    "Gehäusebruch / mechanischer Schaden",
    "Wasserschaden / Kontamination",
    "Softwarefehler / Absturz",
    "Kalibrierung erforderlich",
    "Austauschgerät geliefert",
    "Rückrufaktion Hersteller",
    "Transport-/Sturzschaden",
    "Verschleiß / Alterung",
    "Austausch Akku",
    "Austausch Sensor",
    "Austausch Display",
    "Kabelbruch / Steckerkorrosion",
    "Fehlerhafte Firmware",
    "Wassereintritt",
    "Verschmutzung / Verunreinigung",
    "Serienfehler Hersteller",
    "Transportschaden Gerät",
    "Kalibrierung nicht bestanden",
    "Versicherungsfall (Schaden)",
    "Austauschgerät gestellt",
    "Rücktritt / Rückrufaktion",
    "Mechanische Beschädigung",
    "Bedienfehler",
    "Korrosion",
    "Justage erforderlich",
]

WARTUNGSTYPEN_VORSCHLAEGE: List[str] = [
    "STK – Sicherheitstechnische Kontrolle",
    "MTK – Messtechnische Kontrolle",
    "Funktionsprüfung jährlich",
    "Funktionsprüfung nach Reparatur",
    "Kalibrierung",
    "DGUV V3 / E-Check",
    "Software-Update",
    "Firmware-Update",
    "Akkuwechsel / Batteriewechsel",
    "Reinigung / Grundreinigung",
    "Validierte Desinfektion",
    "Sichtprüfung (Checkliste)",
    "Ersteinsatzprüfung (Neugerät)",
    "Rückruf / Field Safety Notice Bearbeitung",
    "Sicherheitsprüfung nach Fahrzeugaufbau",
    "Funktionsprüfung nach Einsatz",
    "Kalibrierung Sensoren CO₂/SpO₂",
    "DGUV V3 / E-Prüfung jährlich",
    "Softwarelizenz-Refresh",
    "Firmware-Update Safety-Critical",
    "Akkuwechsel Ersatzteil",
    "Reinigung validiert Klasse C",
    "Sichtprüfung nach Transportunfall",
    "Erstinbetriebnahme Prüfung",
    "Lebensdauerende Gerät (EoL)",
    "Validierung Mess- und Prüfmittel",
    "Infusionswärmer-Test",
    "CPAP-Systemprüfung",
    "Ultraschall-Sondenkalibrierung",
]

VEHICLE_BRANDS: List[str] = [
    "Mercedes-Benz",
    "Volkswagen",
    "MAN",
    "Ford",
    "Opel",
    "Fiat",
    "Peugeot",
    "Citroën",
    "Renault",
    "Iveco",
    "Scania",
    "Volvo",
    "Skoda",
    "BMW",
    "Toyota",
    "Nissan",
    "Hyundai",
]

VEHICLE_MODEL_VORSCHLAEGE: List[Tuple[str, str]] = [
    ("Mercedes-Benz", "Sprinter 316 CDI"),
    ("Mercedes-Benz", "Sprinter 319 CDI"),
    ("Mercedes-Benz", "Sprinter 519 CDI"),
    ("Mercedes-Benz", "Vito 116 CDI"),
    ("Mercedes-Benz", "Vito 119 CDI"),
    ("Volkswagen", "T6.1 Transporter"),
    ("Volkswagen", "T5 Transporter"),
    ("Volkswagen", "Crafter 35"),
    ("Volkswagen", "Crafter 50"),
    ("Volkswagen", "T6 Transporter"),
    ("MAN", "TGE 3.140"),
    ("Ford", "Transit Custom"),
    ("Ford", "Transit 350 L3H2"),
    ("Opel", "Movano L3H2"),
    ("Fiat", "Ducato L3H2"),
    ("Fiat", "Ducato L4H2"),
    ("Peugeot", "Boxer L3H2"),
    ("Citroën", "Jumper L3H2"),
    ("Renault", "Master L3H2"),
    ("Iveco", "Daily 35C18"),
    ("Volvo", "XC60"),
    ("Skoda", "Octavia Combi"),
    ("Volvo", "XC60 Einsatzleitung"),
    ("Skoda", "Octavia Combi NEF Variante"),
    ("BMW", "X5 Einsatzleitung"),
    ("Toyota", "RAV4 Hybrid Logistik"),
    ("Nissan", "NV300 Materialbus"),
    ("Hyundai", "H350 Rettungsfahrzeug"),
    ("Mercedes-Benz", "EQV 300"),
]


BEZIRKSSTELLEN_RAW = """
Bezirksstelle ALLENTSTEIG
Spitalstraße 16-20
3804 Allentsteig
Tel.: +43 59144 72400

Bezirksstelle AMSTETTEN
Krankenhausstraße 10
3300 Amstetten
Tel.: +43 59144 51000

Bezirksstelle ATZENBRUGG-HEILIGENEICH
Hütteldorfstraße 4
3452 Heiligeneich
Tel.: +43 59144 69400

Bezirksstelle BADEN
Rotes Kreuz Gasse 6
2500 Baden
Tel.: +43 59144 52000

Bezirksstelle BRUCK AN DER LEITHA
Höfleiner Straße 18
2460 Bruck an der Leitha
Tel.: +43 59144 53000

Bezirksstelle BRUNN AM GEBIRGE
Alexander Groß Gasse 71
2345 Brunn am Gebirge
Tel.: +43 59144 64400

Bezirksstelle GÄNSERNDORF-MARCHEGG
Henri Dunant Straße 1
2230 Gänserndorf
Tel.: +43 59144 54000

Bezirksstelle GLOGGNITZ
Semmeringstraße 87
2640 Gloggnitz
Tel.: +43 59144 65600

Bezirksstelle GMÜND
Weitraer Straße 54
3950 Gmünd
Tel.: +43 59144 55000

Bezirksstelle GROSSWEIKERSDORF
Schmidastraße 4
3701 Großweikersdorf
Tel.: +43 59144 69600

Bezirksstelle HAAG
Elisabethstraße 9
3350 Haag
Tel.: +43 59144 51600

Bezirksstelle HAINBURG
Rot-Kreuz-Straße 14
2410 Hainburg an der Donau
Tel.: +43 59144 53600

Bezirksstelle HAINFELD
Ramsauer Straße 17
3170 Hainfeld
Tel.: +43 59144 61400

Bezirksstelle HERZOGENBURG
Sankt Pöltner Straße 43
3130 Herzogenburg
Tel.: +43 59144 67400

Bezirksstelle HOLLABRUNN
Robert Löffler Straße 21/30
2020 Hollabrunn
Tel.: +43 59144 57000

Bezirksstelle HORN
Spitalgasse 10b
3580 Horn
Tel.: +43 59144 58000

Bezirksstelle KIRCHSCHLAG
Hofwiese 23
2860 Kirchschlag
Tel.: +43 59144 71000

Bezirksstelle KLOSTERNEUBURG
Kreutzergasse 11
3400 Klosterneuburg
Tel.: +43 59144 56000

Bezirksstelle KORNEUBURG
Jahnstraße 7
2100 Korneuburg
Tel.: +43 59144 59000

Bezirksstelle KOTTINGBRUNN
Dammgasse 1
2542 Kottingbrunn
Tel.: +43 59144 52600

Bezirksstelle KREMS
Mitterweg 11
3500 Krems an der Donau
Tel.: +43 59144 75000

Bezirksstelle LAA AN DER THAYA
Simon Scheiner Straße 14
2136 Laa an der Thaya
Tel.: +43 59144 63600

Bezirksstelle LANGENLOIS
Kamptalstraße 83
3550 Langenlois
Tel.: +43 59144 60000

Bezirksstelle LITSCHAU
Schulstraße 8
3874 Litschau
Tel.: +43 59144 55400

Bezirksstelle MARCHFELD
Freiherr von Smola-Straße 1/1
2301 Groß-Enzersdorf
Tel.: +43 59144 54500

Bezirksstelle MELK
Spielberger Straße 15
3390 Melk
Tel.: +43 59144 62000

Bezirksstelle MISTELBACH
Liechtensteinstraße 63
2130 Mistelbach
Tel.: +43 59144 63000

Bezirksstelle MÖDLING
Neusiedler Straße 20
2340 Mödling
Tel.: +43 59144 64000

Bezirksstelle NEULENGBACH
Hainfelder Straße 58
3040 Neulengbach
Tel.: +43 59144 67000

Bezirksstelle NEUNKIRCHEN
Rotkreuz-Straße 4
2620 Neunkirchen
Tel.: +43 59144 65000

Bezirksstelle PERNITZ
Peter Rosegger Straße 5
2763 Pernitz
Tel.: +43 59144 71400

Bezirksstelle PÖGGSTALL
Rogendorferstraße 5
3650 Pöggstall
Tel.: +43 59144 62600

Bezirksstelle PURKERSDORF-GABLITZ
Kaiser Josef-Straße 65
3002 Purkersdorf
Tel.: +43 59144 66000

Bezirksstelle RETZ
Jahnstraße 1
2070 Retz
Tel.: +43 59144 57400

Bezirksstelle SCHEIBBS
Rutesheimerstraße 3
3270 Scheibbs
Tel.: +43 59144 68000

Bezirksstelle SCHWECHAT
Bruck Hainburger-Straße 27
2320 Schwechat
Tel.: +43 59144 77000

Bezirksstelle SOLLENAU-FELIXDORF
Gutensteiner Straße 2
2601 Sollenau
Tel.: +43 59144 71600

Bezirksstelle ST. PETER IN DER AU
Burgholz 1
3352 St. Peter in der Au
Tel.: +43 59144 51800

Bezirksstelle ST. PÖLTEN
Dr. Theodor Körner-Straße 43
3100 St. Pölten
Tel.: +43 59144 73000

Bezirksstelle ST. VALENTIN
Neubaustraße 25
4300 St. Valentin
Tel.: +43 59144 51400

Bezirksstelle TRAISENTAL
Liese Prokop Straße 8
3180 Lilienfeld
Tel.: +43 59144 61000

Bezirksstelle TRIESTINGTAL
Leobersdorferstraße 56
2560 Berndorf
Tel.: +43 59144 52400

Bezirksstelle TULLN
Dr. Karl-Landsteiner-Straße 1
3430 Tulln
Tel.: +43 59144 69000

Bezirksstelle WAIDHOFEN AN DER THAYA
Moritz-Schadek-Gasse 30a
3830 Waidhofen an der Thaya
Tel.: +43 59144 70000

Bezirksstelle WAIDHOFEN AN DER YBBS
Pestalozzistraße 6
3340 Waidhofen an der Ybbs
Tel.: +43 59144 76000

Bezirksstelle WEITRA
Gmünder Straße 137
3970 Weitra
Tel.: +43 59144 55600

Bezirksstelle WIENER NEUSTADT
Grazer Straße 41
2700 Wiener Neustadt
Tel.: +43 59144 74000

Bezirksstelle YBBS
Ybbsflussstraße 1
3370 Ybbs an der Donau
Tel.: +43 59144 62400

Bezirksstelle ZIERSDORF
Erlenaugasse 28
3710 Ziersdorf
Tel.: +43 59144 57200

Bezirksstelle ZISTERSDORF
Windisch Baumgartner Straße 1
2225 Zistersdorf
Tel.: +43 59144 54600

Bezirksstelle ZWETTL
Propstei 45
3910 Zwettl
Tel.: +43 59144 72000
"""


def _parse_bezirksstellen(raw: str) -> List[Dict[str, str]]:
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in (raw or "").splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(stripped)
    if current:
        blocks.append(current)

    entries: List[Dict[str, str]] = []
    for block in blocks:
        if len(block) < 3:
            continue
        title = block[0]
        name = title.replace("Bezirksstelle", "").strip()
        address_line = block[1]
        city_line = block[2]
        phone_line = block[3] if len(block) > 3 else ""
        nice_name = name.title()
        description_parts = [address_line, city_line]
        if phone_line:
            description_parts.append(phone_line)
        entries.append(
            {
                "raw_name": name,
                "name": nice_name,
                "address": address_line,
                "city": city_line,
                "telefon": phone_line,
                "beschreibung": "\n".join(description_parts),
            }
        )
    return entries


BEZIRKSSTELLEN_DATEN: List[Dict[str, str]] = _parse_bezirksstellen(BEZIRKSSTELLEN_RAW)
BEZIRKSSTELLEN_VORSCHLAEGE: List[str] = [entry["name"] for entry in BEZIRKSSTELLEN_DATEN]

BEZIRKSSTELLE_TO_BEZIRK: Dict[str, str] = {
    "Allentsteig": "Zwettl",
    "Amstetten": "Amstetten",
    "Atzenbrugg-Heiligeneich": "Tulln",
    "Baden": "Baden",
    "Bruck An Der Leitha": "Bruck an der Leitha",
    "Brunn Am Gebirge": "Mödling",
    "Gänserndorf-Marchegg": "Gänserndorf",
    "Gloggnitz": "Neunkirchen",
    "Gmünd": "Gmünd",
    "Grossweikersdorf": "Tulln",
    "Haag": "Amstetten",
    "Hainburg": "Bruck an der Leitha",
    "Hainfeld": "Lilienfeld",
    "Herzogenburg": "St. Pölten (Land)",
    "Hollabrunn": "Hollabrunn",
    "Horn": "Horn",
    "Kirchschlag": "Wiener Neustadt (Land)",
    "Klosterneuburg": "Tulln",
    "Korneuburg": "Korneuburg",
    "Kottingbrunn": "Baden",
    "Krems": "Krems (Stadt)",
    "Laa An Der Thaya": "Mistelbach",
    "Langenlois": "Krems (Land)",
    "Litschau": "Gmünd",
    "Marchfeld": "Gänserndorf",
    "Melk": "Melk",
    "Mistelbach": "Mistelbach",
    "Mödling": "Mödling",
    "Neulengbach": "St. Pölten (Land)",
    "Neunkirchen": "Neunkirchen",
    "Pernitz": "Wiener Neustadt (Land)",
    "Pöggstall": "Melk",
    "Purkersdorf-Gablitz": "St. Pölten (Land)",
    "Retz": "Hollabrunn",
    "Scheibbs": "Scheibbs",
    "Schwechat": "Bruck an der Leitha",
    "Sollenau-Felixdorf": "Wiener Neustadt (Land)",
    "St. Peter In Der Au": "Amstetten",
    "St. Pölten": "St. Pölten (Stadt)",
    "St. Valentin": "Amstetten",
    "Traisental": "Lilienfeld",
    "Triestingtal": "Baden",
    "Tulln": "Tulln",
    "Waidhofen An Der Thaya": "Waidhofen an der Thaya",
    "Waidhofen An Der Ybbs": "Waidhofen an der Ybbs",
    "Weitra": "Gmünd",
    "Wiener Neustadt": "Wiener Neustadt (Stadt)",
    "Ybbs": "Melk",
    "Ziersdorf": "Hollabrunn",
    "Zistersdorf": "Gänserndorf",
    "Zwettl": "Zwettl",
}

LAND_VORSCHLAEGE: List[str] = ["Niederösterreich", "Österreich"]
BEREICH_VORSCHLAEGE: List[str] = list(BEREICH_BEZIRK_MAP.keys())
BEZIRK_VORSCHLAEGE: List[str] = sorted(BEZIRK_TO_BEREICH.keys())


class DatabaseManager:
    """High level database helper that wraps raw SQLite access."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        resolved_path = Path(db_path) if db_path is not None else get_db_path()
        self.db_path = resolved_path
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self._location_cache: Dict[int, sqlite3.Row] = {}
        self._active_mandant_id: int = 1
        self.initialize_schema()
        self.ensure_default_admin()

    def _log_internal_error(self, message: str, exc: Exception) -> None:
        """Log unexpected database errors without interrupting the UI."""

        logging.getLogger(__name__).error("%s: %s", message, exc)

    def _table_exists(self, name: str, *, kind: str = "table") -> bool:
        row = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = ? AND name = ?",
            (kind, name),
        ).fetchone()
        return bool(row)

    def _ensure_schema_version(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    version INTEGER NOT NULL
                )
                """
            )
        row = self.connection.execute(
            "SELECT version FROM schema_version WHERE id = 1"
        ).fetchone()
        if not row:
            with self.connection:
                self.connection.execute(
                    "INSERT INTO schema_version (id, version) VALUES (1, 1)"
                )

    def _ensure_audit_storage(self) -> None:
        has_audit_table = self._table_exists("audit_log")
        has_system_table = self._table_exists("system_audit")
        with self.connection:
            if not has_audit_table and has_system_table:
                self.connection.execute("ALTER TABLE system_audit RENAME TO audit_log")
                has_audit_table = True
                has_system_table = False
            elif not has_audit_table:
                self.connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tabelle TEXT NOT NULL,
                        datensatz_id INTEGER,
                        aktion TEXT NOT NULL,
                        vorher TEXT,
                        nachher TEXT,
                        zeitstempel TEXT NOT NULL,
                        benutzer_id INTEGER,
                        mandant_id INTEGER NOT NULL DEFAULT 1,
                        FOREIGN KEY(benutzer_id) REFERENCES benutzer(id) ON DELETE SET NULL
                    )
                    """
                )
        if not has_system_table and not self._table_exists("system_audit", kind="view"):
            with self.connection:
                self.connection.execute(
                    "CREATE VIEW IF NOT EXISTS system_audit AS SELECT * FROM audit_log"
                )

    # ------------------------------------------------------------------
    # schema
    # ------------------------------------------------------------------
    def initialize_schema(self) -> None:
        """Create all tables if they do not yet exist."""

        with self.connection:
            self.connection.executescript(
                """
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS benutzer (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin', 'benutzer')),
                    vorname TEXT,
                    nachname TEXT,
                    dienstnummer TEXT,
                    email TEXT,
                    standorte_lesen INTEGER NOT NULL DEFAULT 1,
                    standorte_schreiben INTEGER NOT NULL DEFAULT 1,
                    produkte_lesen INTEGER NOT NULL DEFAULT 1,
                    produkte_schreiben INTEGER NOT NULL DEFAULT 1,
                    material_lesen INTEGER NOT NULL DEFAULT 1,
                    material_schreiben INTEGER NOT NULL DEFAULT 1,
                    fahrzeuge_lesen INTEGER NOT NULL DEFAULT 1,
                    fahrzeuge_schreiben INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS benutzer_standorte (
                    benutzer_id INTEGER NOT NULL,
                    standort_id INTEGER NOT NULL,
                    lesen INTEGER NOT NULL DEFAULT 1,
                    schreiben INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (benutzer_id, standort_id),
                    FOREIGN KEY(benutzer_id) REFERENCES benutzer(id) ON DELETE CASCADE,
                    FOREIGN KEY(standort_id) REFERENCES standorte(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS kategorien (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    typ TEXT NOT NULL CHECK(typ IN ('produkt', 'material'))
                );

                CREATE TABLE IF NOT EXISTS produkt_typen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS produkt_modelle (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    typ_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    FOREIGN KEY(typ_id) REFERENCES produkt_typen(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS produkt_hersteller (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS komponententypen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS reparatur_arten (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS upload_kategorien (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS upload_ablage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    speicherpfad TEXT NOT NULL,
                    upload_kategorie_id INTEGER,
                    created_at TEXT NOT NULL,
                    mandant_id INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(upload_kategorie_id) REFERENCES upload_kategorien(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS ausscheidungsgruende (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    mandant_id INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS standorte (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    land TEXT,
                    bereich TEXT,
                    bezirk TEXT,
                    bezirksstelle TEXT,
                    ortsstelle TEXT,
                    beschreibung TEXT,
                    ist_fahrzeug INTEGER NOT NULL DEFAULT 0,
                    funkkennung TEXT,
                    mandant_id INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS kontakte (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    adresse TEXT,
                    telefon TEXT,
                    email TEXT,
                    kontaktperson TEXT,
                    unternehmen TEXT,
                    website TEXT,
                    info TEXT
                );

                CREATE TABLE IF NOT EXISTS fahrzeuge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    kennzeichen TEXT,
                    marke TEXT,
                    typ TEXT,
                    kategorie TEXT,
                    inbetriebnahme TEXT,
                    standort_id INTEGER,
                    kilometerstand INTEGER DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'im_dienst',
                    ausserbetrieb INTEGER NOT NULL DEFAULT 0,
                    ausserbetriebnahme_datum TEXT,
                    marke_id INTEGER,
                    fahrzeugtyp_id INTEGER,
                    fahrzeugkategorie_id INTEGER,
                    FOREIGN KEY(standort_id) REFERENCES standorte(id)
                );

                CREATE TABLE IF NOT EXISTS fahrzeug_marken (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS fahrzeug_modelle (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    marke_id INTEGER,
                    name TEXT NOT NULL,
                    FOREIGN KEY(marke_id) REFERENCES fahrzeug_marken(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS fahrzeug_kategorien (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS fahrzeug_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fahrzeug_id INTEGER NOT NULL,
                    eintragstyp TEXT NOT NULL,
                    beschreibung TEXT,
                    zeitstempel TEXT NOT NULL,
                    FOREIGN KEY(fahrzeug_id) REFERENCES fahrzeuge(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS produkte (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    typ TEXT,
                    seriennummer TEXT UNIQUE NOT NULL,
                    hersteller TEXT,
                    anschaffungsdatum TEXT,
                    kategorie_id INTEGER,
                    standort_id INTEGER,
                    fahrzeug_id INTEGER,
                    mandant_id INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'im_dienst',
                    interne_kennung TEXT,
                    stk_intervall INTEGER DEFAULT 12,
                    mtk_intervall INTEGER DEFAULT 24,
                    letzte_stk TEXT,
                    letzte_mtk TEXT,
                    naechste_stk TEXT,
                    naechste_mtk TEXT,
                    stk_aktiv INTEGER NOT NULL DEFAULT 1,
                    mtk_aktiv INTEGER NOT NULL DEFAULT 1,
                    lagerort TEXT,
                    produkt_typ_id INTEGER,
                    produkt_modell_id INTEGER,
                    informationstext TEXT,
                    FOREIGN KEY(kategorie_id) REFERENCES kategorien(id),
                    FOREIGN KEY(standort_id) REFERENCES standorte(id),
                    FOREIGN KEY(fahrzeug_id) REFERENCES fahrzeuge(id),
                    FOREIGN KEY(produkt_typ_id) REFERENCES produkt_typen(id) ON DELETE SET NULL,
                    FOREIGN KEY(produkt_modell_id) REFERENCES produkt_modelle(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS produkt_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER NOT NULL,
                    eintragstyp TEXT NOT NULL,
                    beschreibung TEXT,
                    zeitstempel TEXT NOT NULL,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS produkt_fahrzeug_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER NOT NULL,
                    fahrzeug_id INTEGER,
                    fahrzeug_name_snapshot TEXT,
                    fahrzeug_kennzeichen TEXT,
                    zugeordnet_am TEXT NOT NULL,
                    entfernt_am TEXT,
                    mandant_id INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE,
                    FOREIGN KEY(fahrzeug_id) REFERENCES fahrzeuge(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS produkt_komponenten (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    hersteller TEXT,
                    seriennummer TEXT,
                    anschaffungsdatum TEXT,
                    bemerkung TEXT,
                    komponententyp_id INTEGER,
                    status TEXT NOT NULL DEFAULT 'im_dienst',
                    reparatur_notiz TEXT,
                    reparatur_datum TEXT,
                    ausscheidungsgrund TEXT,
                    ausscheidungsdatum TEXT,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE,
                    FOREIGN KEY(komponententyp_id) REFERENCES komponententypen(id)
                );

                CREATE TABLE IF NOT EXISTS komponenten_einsatz_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    komponent_id INTEGER NOT NULL,
                    produkt_id INTEGER NOT NULL,
                    fahrzeug_id INTEGER,
                    produkt_name_snapshot TEXT,
                    produkt_seriennummer_snapshot TEXT,
                    fahrzeug_name_snapshot TEXT,
                    zugeordnet_am TEXT NOT NULL,
                    entfernt_am TEXT,
                    mandant_id INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(komponent_id) REFERENCES produkt_komponenten(id) ON DELETE CASCADE,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE,
                    FOREIGN KEY(fahrzeug_id) REFERENCES fahrzeuge(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS reparaturen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER NOT NULL,
                    datum TEXT NOT NULL,
                    kosten REAL,
                    kontakt_id INTEGER,
                    beschreibung TEXT,
                    reparatur_art_id INTEGER,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE,
                    FOREIGN KEY(kontakt_id) REFERENCES kontakte(id),
                    FOREIGN KEY(reparatur_art_id) REFERENCES reparatur_arten(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS reparatur_dateien (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reparatur_id INTEGER NOT NULL,
                    dateiname TEXT NOT NULL,
                    speicherpfad TEXT NOT NULL,
                    upload_kategorie_id INTEGER,
                    FOREIGN KEY(reparatur_id) REFERENCES reparaturen(id) ON DELETE CASCADE,
                    FOREIGN KEY(upload_kategorie_id) REFERENCES upload_kategorien(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS komponenten_reparaturen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    komponent_id INTEGER NOT NULL,
                    datum TEXT NOT NULL,
                    kosten REAL,
                    kontakt_id INTEGER,
                    beschreibung TEXT,
                    reparatur_art_id INTEGER,
                    FOREIGN KEY(komponent_id) REFERENCES produkt_komponenten(id) ON DELETE CASCADE,
                    FOREIGN KEY(kontakt_id) REFERENCES kontakte(id),
                    FOREIGN KEY(reparatur_art_id) REFERENCES reparatur_arten(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS komponenten_reparatur_dateien (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    komponenten_reparatur_id INTEGER NOT NULL,
                    dateiname TEXT NOT NULL,
                    speicherpfad TEXT NOT NULL,
                    upload_kategorie_id INTEGER,
                    FOREIGN KEY(komponenten_reparatur_id) REFERENCES komponenten_reparaturen(id) ON DELETE CASCADE,
                    FOREIGN KEY(upload_kategorie_id) REFERENCES upload_kategorien(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS wartungstypen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS ausscheidungen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER NOT NULL,
                    datum TEXT NOT NULL,
                    grund TEXT,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS wartungen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER NOT NULL,
                    geplanter_termin TEXT NOT NULL,
                    wartungstyp TEXT NOT NULL,
                    beschreibung TEXT,
                    durchgefuehrt_am TEXT,
                    durchgefuehrt_von TEXT,
                    bemerkung TEXT,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS verbrauchsmaterial (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    kategorie_id INTEGER,
                    lagerort TEXT,
                    soll_bestand INTEGER DEFAULT 0,
                    ist_bestand INTEGER DEFAULT 0,
                    verfallsdatum TEXT,
                    FOREIGN KEY(kategorie_id) REFERENCES kategorien(id)
                );

                CREATE TABLE IF NOT EXISTS bestellungen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    erstellt_am TEXT NOT NULL,
                    erstellt_von INTEGER,
                    status TEXT NOT NULL,
                    standort_id INTEGER,
                    genehmigt_am TEXT,
                    abgeschlossen_am TEXT,
                    bemerkung TEXT,
                    FOREIGN KEY(erstellt_von) REFERENCES benutzer(id) ON DELETE SET NULL,
                    FOREIGN KEY(standort_id) REFERENCES standorte(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS bestellpositionen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bestellung_id INTEGER NOT NULL,
                    material_id INTEGER,
                    beschreibung TEXT,
                    menge INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(bestellung_id) REFERENCES bestellungen(id) ON DELETE CASCADE,
                    FOREIGN KEY(material_id) REFERENCES verbrauchsmaterial(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS system_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    zeitstempel TEXT NOT NULL,
                    ebene TEXT NOT NULL,
                    nachricht TEXT NOT NULL,
                    benutzer_id INTEGER,
                    FOREIGN KEY(benutzer_id) REFERENCES benutzer(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS ics_importe (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quelle TEXT NOT NULL,
                    importiert_am TEXT NOT NULL,
                    zusammenfassung TEXT,
                    start TEXT,
                    ende TEXT,
                    produkt_id INTEGER,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS archivierte_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_typ TEXT NOT NULL,
                    inhalt BLOB NOT NULL,
                    erstellt_am TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS material_bezeichnungen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                );

                CREATE TABLE IF NOT EXISTS benutzer_einstellungen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    benutzer_id INTEGER NOT NULL,
                    schluessel TEXT NOT NULL,
                    wert TEXT NOT NULL,
                    UNIQUE(benutzer_id, schluessel),
                    FOREIGN KEY(benutzer_id) REFERENCES benutzer(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS mandanten (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    aktiv INTEGER NOT NULL DEFAULT 1,
                    kontakt_email TEXT,
                    notizen TEXT
                );

                CREATE TABLE IF NOT EXISTS produkt_freigaben (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER NOT NULL,
                    schritt TEXT NOT NULL,
                    status TEXT NOT NULL,
                    kommentar TEXT,
                    erstellt_am TEXT NOT NULL,
                    angelegt_von INTEGER,
                    genehmigt_von INTEGER,
                    genehmigt_am TEXT,
                    mandant_id INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE,
                    FOREIGN KEY(angelegt_von) REFERENCES benutzer(id) ON DELETE SET NULL,
                    FOREIGN KEY(genehmigt_von) REFERENCES benutzer(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS capa_massnahmen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER,
                    beschreibung TEXT NOT NULL,
                    status TEXT NOT NULL,
                    faellig_am TEXT,
                    verantwortlicher_id INTEGER,
                    erstellt_am TEXT NOT NULL,
                    mandant_id INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE SET NULL,
                    FOREIGN KEY(verantwortlicher_id) REFERENCES benutzer(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS regelwerke (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    beschreibung TEXT,
                    intervall_monate INTEGER,
                    mandant_id INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS produkt_regelwerke (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    produkt_id INTEGER NOT NULL,
                    regelwerk_id INTEGER NOT NULL,
                    letzter_abgleich TEXT,
                    naechster_abgleich TEXT,
                    mandant_id INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(produkt_id, regelwerk_id),
                    FOREIGN KEY(produkt_id) REFERENCES produkte(id) ON DELETE CASCADE,
                    FOREIGN KEY(regelwerk_id) REFERENCES regelwerke(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS verfahren (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    titel TEXT NOT NULL,
                    version TEXT NOT NULL,
                    beschreibung TEXT,
                    dokument TEXT,
                    mandant_id INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS schulungsnachweise (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    benutzer_id INTEGER NOT NULL,
                    verfahren_id INTEGER NOT NULL,
                    bestaetigt_am TEXT NOT NULL,
                    mandant_id INTEGER NOT NULL DEFAULT 1,
                    UNIQUE(benutzer_id, verfahren_id),
                    FOREIGN KEY(benutzer_id) REFERENCES benutzer(id) ON DELETE CASCADE,
                    FOREIGN KEY(verfahren_id) REFERENCES verfahren(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS dashboard_layouts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    benutzer_id INTEGER NOT NULL,
                    layout TEXT NOT NULL,
                    erstellt_am TEXT NOT NULL,
                    mandant_id INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(benutzer_id) REFERENCES benutzer(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS gespeicherte_filter (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    benutzer_id INTEGER NOT NULL,
                    bereich TEXT NOT NULL,
                    name TEXT NOT NULL,
                    daten TEXT NOT NULL,
                    erstellt_am TEXT NOT NULL,
                    mandant_id INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(benutzer_id) REFERENCES benutzer(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS hilfe_artikel (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bereich TEXT NOT NULL,
                    titel TEXT NOT NULL,
                    inhalt TEXT NOT NULL,
                    mandant_id INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS cockpit_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    erstellt_am TEXT NOT NULL,
                    daten TEXT NOT NULL,
                    mandant_id INTEGER NOT NULL DEFAULT 1
                );
                """
            )

        self._ensure_schema_version()
        self._ensure_audit_storage()
        self._seed_defaults()
        self._ensure_columns()
        self._backfill_product_manufacturers()

    def _ensure_columns(self) -> None:
        self._ensure_column("produkte", "naechste_stk", "TEXT")
        self._ensure_column("produkte", "naechste_mtk", "TEXT")
        self._ensure_column("produkte", "stk_aktiv", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column("produkte", "mtk_aktiv", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column("produkte", "lagerort", "TEXT")
        self._ensure_column("produkte", "produkt_typ_id", "INTEGER REFERENCES produkt_typen(id)")
        self._ensure_column("produkte", "produkt_modell_id", "INTEGER REFERENCES produkt_modelle(id)")
        self._ensure_column(
            "produkte",
            "produkt_hersteller_id",
            "INTEGER REFERENCES produkt_hersteller(id)",
        )
        self._ensure_column("produkte", "informationstext", "TEXT")
        self._ensure_column("produkte", "mandant_id", "INTEGER NOT NULL DEFAULT 1")

        self._ensure_column("fahrzeuge", "ausserbetrieb", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("fahrzeuge", "ausserbetriebnahme_datum", "TEXT")
        self._ensure_column("fahrzeuge", "marke_id", "INTEGER REFERENCES fahrzeug_marken(id)")
        self._ensure_column("fahrzeuge", "fahrzeugtyp_id", "INTEGER REFERENCES fahrzeug_modelle(id)")
        self._ensure_column("fahrzeuge", "fahrzeugkategorie_id", "INTEGER REFERENCES fahrzeug_kategorien(id)")
        self._ensure_column("fahrzeuge", "fahrgestellnummer", "TEXT")

        self._ensure_column("standorte", "ist_fahrzeug", "INTEGER NOT NULL DEFAULT 0")
        self._ensure_column("standorte", "funkkennung", "TEXT")

        self._ensure_column("produkt_komponenten", "komponententyp_id", "INTEGER REFERENCES komponententypen(id)")
        self._ensure_column("produkt_komponenten", "status", "TEXT NOT NULL DEFAULT 'im_dienst'")
        self._ensure_column("produkt_komponenten", "reparatur_notiz", "TEXT")
        self._ensure_column("produkt_komponenten", "reparatur_datum", "TEXT")
        self._ensure_column("produkt_komponenten", "ausscheidungsgrund", "TEXT")
        self._ensure_column("produkt_komponenten", "ausscheidungsdatum", "TEXT")
        self._ensure_column("reparaturen", "reparatur_art_id", "INTEGER REFERENCES reparatur_arten(id)")

        self._ensure_column("produkt_log", "benutzer_id", "INTEGER REFERENCES benutzer(id)")
        self._ensure_column("fahrzeug_log", "benutzer_id", "INTEGER REFERENCES benutzer(id)")

        self._ensure_column("benutzer", "vorname", "TEXT")
        self._ensure_column("benutzer", "nachname", "TEXT")
        self._ensure_column("benutzer", "dienstnummer", "TEXT")
        self._ensure_column("benutzer", "email", "TEXT")
        for column in PERMISSION_COLUMNS:
            self._ensure_column("benutzer", column, "INTEGER NOT NULL DEFAULT 1")

        self._ensure_column("system_log", "benutzer_id", "INTEGER REFERENCES benutzer(id)")
        self._ensure_column("audit_log", "benutzer_id", "INTEGER REFERENCES benutzer(id)")

        self._ensure_column("kontakte", "unternehmen", "TEXT")
        self._ensure_column("kontakte", "website", "TEXT")
        self._ensure_column("kontakte", "info", "TEXT")

        # multi-tenant defaults
        self._ensure_column("benutzer", "mandant_id", "INTEGER NOT NULL DEFAULT 1")
        for table in (
            "standorte",
            "fahrzeuge",
            "produkte",
            "produkt_komponenten",
            "reparaturen",
            "wartungen",
            "verbrauchsmaterial",
            "kontakte",
            "bestellungen",
            "bestellpositionen",
            "system_log",
            "audit_log",
            "produkt_log",
            "fahrzeug_log",
            "ics_importe",
            "capa_massnahmen",
            "produkt_freigaben",
            "verfahren",
            "schulungsnachweise",
            "dashboard_layouts",
            "gespeicherte_filter",
            "regelwerke",
            "produkt_regelwerke",
            "hilfe_artikel",
            "cockpit_snapshots",
            "ausscheidungsgruende",
        ):
            self._ensure_column(table, "mandant_id", "INTEGER NOT NULL DEFAULT 1")

    def _backfill_product_manufacturers(self) -> None:
        with self.connection:
            existing: Dict[str, int] = {
                row["name"]: int(row["id"])
                for row in self.connection.execute(
                    "SELECT id, name FROM produkt_hersteller"
                )
            }
            for (name,) in self.connection.execute(
                "SELECT DISTINCT hersteller FROM produkte "
                "WHERE hersteller IS NOT NULL AND TRIM(hersteller) <> ''"
            ):
                trimmed = name.strip()
                if trimmed and trimmed not in existing:
                    cur = self.connection.execute(
                        "INSERT OR IGNORE INTO produkt_hersteller (name) VALUES (?)",
                        (trimmed,),
                    )
                    if cur.lastrowid:
                        existing[trimmed] = int(cur.lastrowid)
                    else:
                        row = self.connection.execute(
                            "SELECT id FROM produkt_hersteller WHERE name = ?",
                            (trimmed,),
                        ).fetchone()
                        if row:
                            existing[trimmed] = int(row["id"])

            for row in self.connection.execute(
                "SELECT id, hersteller FROM produkte "
                "WHERE produkt_hersteller_id IS NULL AND hersteller IS NOT NULL "
                "AND TRIM(hersteller) <> ''"
            ):
                hersteller_name = row["hersteller"].strip()
                hersteller_id = existing.get(hersteller_name)
                if hersteller_id:
                    self.connection.execute(
                        "UPDATE produkte SET produkt_hersteller_id = ? WHERE id = ?",
                        (hersteller_id, row["id"]),
                    )

    def _seed_simple_list(
        self,
        table: str,
        values: Iterable[str],
        *,
        column: str = "name",
    ) -> None:
        existing: Dict[str, None] = {
            (row[0] or "").strip(): None
            for row in self.connection.execute(f"SELECT {column} FROM {table}")
            if (row[0] or "").strip()
        }
        for value in values:
            trimmed = (value or "").strip()
            if not trimmed or trimmed in existing:
                continue
            self.connection.execute(
                f"INSERT INTO {table} ({column}) VALUES (?)",
                (trimmed,),
            )
            existing[trimmed] = None

    def _seed_categories(self, values: Iterable[str], typ: str) -> None:
        existing: Dict[str, None] = {
            (row["name"] or "").strip(): None
            for row in self.connection.execute(
                "SELECT name FROM kategorien WHERE typ = ?",
                (typ,),
            )
            if (row["name"] or "").strip()
        }
        for value in values:
            trimmed = (value or "").strip()
            if not trimmed or trimmed in existing:
                continue
            self.connection.execute(
                "INSERT INTO kategorien (name, typ) VALUES (?, ?)",
                (trimmed, typ),
            )
            existing[trimmed] = None

    def _seed_defaults(self) -> None:
        with self.connection:
            existing_categories = {
                row[0] for row in self.connection.execute("SELECT name FROM fahrzeug_kategorien")
            }
            for eintrag in FAHRZEUG_KATEGORIEN:
                if eintrag not in existing_categories:
                    self.connection.execute(
                        "INSERT INTO fahrzeug_kategorien (name) VALUES (?)",
                        (eintrag,),
                    )

            self._seed_simple_list("upload_kategorien", REPARATUR_DATEI_KATEGORIEN)
            self._seed_simple_list("reparatur_arten", REPARATUR_ARTEN_VORSCHLAEGE)
            self._seed_simple_list("wartungstypen", WARTUNGSTYPEN_VORSCHLAEGE)

            self._seed_categories(PRODUKT_KATEGORIEN, "produkt")
            self._seed_categories(MATERIAL_KATEGORIEN, "material")
            self._seed_simple_list("produkt_typen", PRODUKT_VORSCHLAEGE)
            self._seed_simple_list("produkt_hersteller", HERSTELLER_VORSCHLAEGE)
            self._seed_simple_list("komponententypen", KOMPONENTEN_VORSCHLAEGE)
            self._seed_simple_list("material_bezeichnungen", MATERIAL_VORSCHLAEGE)
            self._seed_simple_list("ausscheidungsgruende", AUSSCHEIDUNGSGRUND_VORSCHLAEGE)

            brand_index: Dict[str, int] = {
                row["name"]: int(row["id"])
                for row in self.connection.execute("SELECT id, name FROM fahrzeug_marken")
            }
            for brand in VEHICLE_BRANDS:
                trimmed_brand = (brand or "").strip()
                if not trimmed_brand or trimmed_brand in brand_index:
                    continue
                cur = self.connection.execute(
                    "INSERT INTO fahrzeug_marken (name) VALUES (?)",
                    (trimmed_brand,),
                )
                brand_index[trimmed_brand] = int(cur.lastrowid)

            for brand_name, model_name in VEHICLE_MODEL_VORSCHLAEGE:
                trimmed_model = (model_name or "").strip()
                trimmed_brand = (brand_name or "").strip()
                if not trimmed_model:
                    continue
                brand_id: Optional[int] = None
                if trimmed_brand:
                    brand_id = brand_index.get(trimmed_brand)
                    if not brand_id:
                        cur = self.connection.execute(
                            "INSERT INTO fahrzeug_marken (name) VALUES (?)",
                            (trimmed_brand,),
                        )
                        brand_id = int(cur.lastrowid)
                        brand_index[trimmed_brand] = brand_id
                exists = self.connection.execute(
                    "SELECT 1 FROM fahrzeug_modelle WHERE name = ? AND IFNULL(marke_id, 0) = IFNULL(?, 0)",
                    (trimmed_model, brand_id or 0),
                ).fetchone()
                if exists:
                    continue
                self.connection.execute(
                    "INSERT INTO fahrzeug_modelle (marke_id, name) VALUES (?, ?)",
                    (brand_id, trimmed_model),
                )

            typ_index: Dict[str, int] = {
                row["name"]: int(row["id"])
                for row in self.connection.execute("SELECT id, name FROM produkt_typen")
            }
            for typ_name, modell_name in TYP_MODELL_VORSCHLAEGE:
                trimmed_type = typ_name.strip()
                trimmed_model = modell_name.strip()
                if not trimmed_type or not trimmed_model:
                    continue
                typ_id = typ_index.get(trimmed_type)
                if not typ_id:
                    cur = self.connection.execute(
                        "INSERT INTO produkt_typen (name) VALUES (?)",
                        (trimmed_type,),
                    )
                    typ_id = int(cur.lastrowid)
                    typ_index[trimmed_type] = typ_id
                exists = self.connection.execute(
                    "SELECT 1 FROM produkt_modelle WHERE typ_id = ? AND name = ?",
                    (typ_id, trimmed_model),
                ).fetchone()
                if not exists:
                    self.connection.execute(
                        "INSERT INTO produkt_modelle (typ_id, name) VALUES (?, ?)",
                        (typ_id, trimmed_model),
                    )

            if not list(self.connection.execute("SELECT id FROM regelwerke")):
                defaults = [
                    ("MDR Basisprüfung", "Grundlegende medizinprodukterelevante Prüfung", 12),
                    ("ISO 13485 Audit", "Qualitätsmanagement-Audit", 36),
                ]
                for name, beschreibung, intervall in defaults:
                    self.connection.execute(
                        "INSERT INTO regelwerke (name, beschreibung, intervall_monate) VALUES (?, ?, ?)",
                        (name, beschreibung, intervall),
                    )

            if not list(self.connection.execute("SELECT id FROM verfahren")):
                verfahren_defaults = [
                    (
                        "Geräteeinweisung",
                        "1.0",
                        "Standardarbeitsanweisung für die Einweisung neuer Geräte.",
                        "Einweisungsschritte dokumentieren",
                    ),
                    (
                        "Reparaturworkflow",
                        "1.0",
                        "Ablauf zur Meldung und Dokumentation von Reparaturen.",
                        "Defekte melden, Reparatur protokollieren, Freigabe einholen",
                    ),
                ]
                for titel, version, beschreibung, dokument in verfahren_defaults:
                    self.connection.execute(
                        "INSERT INTO verfahren (titel, version, beschreibung, dokument) VALUES (?, ?, ?, ?)",
                        (titel, version, beschreibung, dokument),
                    )

            if not list(self.connection.execute("SELECT id FROM hilfe_artikel")):
                hilfe_defaults = [
                    (
                        "produkte",
                        "Neues Produkt anlegen",
                        "Öffnen Sie das Produktmodul, wählen Sie 'Neu' und folgen Sie dem Assistenten. Speichern nicht vergessen!",
                    ),
                    (
                        "reparaturen",
                        "Reparatur melden",
                        "Markieren Sie das Gerät, öffnen Sie den Reparaturdialog und dokumentieren Sie Kosten sowie Dateien.",
                    ),
                ]
                for bereich, titel, inhalt in hilfe_defaults:
                    self.connection.execute(
                        "INSERT INTO hilfe_artikel (bereich, titel, inhalt) VALUES (?, ?, ?)",
                        (bereich, titel, inhalt),
                    )

            existing_locations = {
                (
                    row["land"],
                    row["bereich"],
                    row["bezirk"],
                    row["bezirksstelle"],
                    row["ortsstelle"],
                )
                for row in self.connection.execute(
                    "SELECT land, bereich, bezirk, bezirksstelle, ortsstelle FROM standorte"
                )
            }
            for bereich, bezirke in BEREICH_BEZIRK_MAP.items():
                for bezirk in bezirke:
                    key = ("Niederösterreich", bereich, bezirk, "", "")
                    if key in existing_locations:
                        continue
                    self.connection.execute(
                        """
                        INSERT INTO standorte (
                            land, bereich, bezirk, bezirksstelle, ortsstelle, beschreibung
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        ("Niederösterreich", bereich, bezirk, "", "", ""),
                    )
                    existing_locations.add(key)

            for entry in BEZIRKSSTELLEN_DATEN:
                name = entry["name"]
                bezirk = BEZIRKSSTELLE_TO_BEZIRK.get(name, name)
                bereich = BEZIRK_TO_BEREICH.get(bezirk, "")
                key = ("Niederösterreich", bereich, bezirk, name, "")
                if key in existing_locations:
                    continue
                self.connection.execute(
                    """
                    INSERT INTO standorte (
                        land, bereich, bezirk, bezirksstelle, ortsstelle, beschreibung
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "Niederösterreich",
                        bereich,
                        bezirk,
                        name,
                        "",
                        entry["beschreibung"],
                    ),
                )
                existing_locations.add(key)

            self._seed_product_vehicle_history()
            self._seed_component_assignment_history()

    def _seed_product_vehicle_history(self) -> None:
        if not self._table_exists("produkt_fahrzeug_history"):
            return
        rows = self.connection.execute(
            "SELECT id, fahrzeug_id FROM produkte WHERE fahrzeug_id IS NOT NULL AND mandant_id = ?",
            (self._active_mandant_id,),
        ).fetchall()
        for row in rows:
            produkt_id = int(row["id"])
            fahrzeug_id = row["fahrzeug_id"]
            if not fahrzeug_id:
                continue
            exists = self.connection.execute(
                """
                SELECT 1 FROM produkt_fahrzeug_history
                WHERE produkt_id = ? AND fahrzeug_id = ? AND entfernt_am IS NULL
                """,
                (produkt_id, fahrzeug_id),
            ).fetchone()
            if exists:
                continue
            self._open_product_vehicle_history_entry(produkt_id, fahrzeug_id)

    def _seed_component_assignment_history(self) -> None:
        if not self._table_exists("komponenten_einsatz_history"):
            return
        rows = self.connection.execute(
            """
            SELECT pk.id AS komponent_id, pk.produkt_id
            FROM produkt_komponenten AS pk
            JOIN produkte AS p ON p.id = pk.produkt_id
            WHERE p.mandant_id = ?
            """,
            (self._active_mandant_id,),
        ).fetchall()
        for row in rows:
            komponent_id = int(row["komponent_id"])
            exists = self.connection.execute(
                "SELECT 1 FROM komponenten_einsatz_history WHERE komponent_id = ? AND entfernt_am IS NULL",
                (komponent_id,),
            ).fetchone()
            if exists:
                continue
            self._record_component_assignment(komponent_id, int(row["produkt_id"]))

    def _vehicle_snapshot(self, fahrzeug_id: Optional[int]) -> Tuple[Optional[str], Optional[str]]:
        if not fahrzeug_id:
            return None, None
        row = self.connection.execute(
            "SELECT name, kennzeichen FROM fahrzeuge WHERE id = ?",
            (fahrzeug_id,),
        ).fetchone()
        if not row:
            return None, None
        return row["name"], row["kennzeichen"]

    def _open_product_vehicle_history_entry(
        self, produkt_id: int, fahrzeug_id: Optional[int], *, timestamp: Optional[str] = None
    ) -> None:
        if fahrzeug_id is None:
            return
        fahrzeug_name, kennzeichen = self._vehicle_snapshot(fahrzeug_id)
        ts = timestamp or datetime.now().isoformat()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO produkt_fahrzeug_history (
                    produkt_id, fahrzeug_id, fahrzeug_name_snapshot, fahrzeug_kennzeichen,
                    zugeordnet_am, mandant_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    produkt_id,
                    fahrzeug_id,
                    fahrzeug_name,
                    kennzeichen,
                    ts,
                    self._active_mandant_id,
                ),
            )

    def _close_product_vehicle_history_entries(
        self, produkt_id: int, fahrzeug_id: Optional[int], *, timestamp: Optional[str] = None
    ) -> None:
        if fahrzeug_id is None:
            return
        ts = timestamp or datetime.now().isoformat()
        with self.connection:
            self.connection.execute(
                """
                UPDATE produkt_fahrzeug_history
                SET entfernt_am = COALESCE(entfernt_am, ?)
                WHERE produkt_id = ? AND fahrzeug_id = ? AND entfernt_am IS NULL
                """,
                (ts, produkt_id, fahrzeug_id),
            )

    def _close_all_product_vehicle_history(self, produkt_id: int) -> None:
        ts = datetime.now().isoformat()
        with self.connection:
            self.connection.execute(
                """
                UPDATE produkt_fahrzeug_history
                SET entfernt_am = COALESCE(entfernt_am, ?)
                WHERE produkt_id = ? AND entfernt_am IS NULL
                """,
                (ts, produkt_id),
            )

    def _reset_component_assignments_for_product(
        self, produkt_id: int, *, timestamp: Optional[str] = None
    ) -> None:
        ts = timestamp or datetime.now().isoformat()
        with self.connection:
            self.connection.execute(
                """
                UPDATE komponenten_einsatz_history
                SET entfernt_am = COALESCE(entfernt_am, ?)
                WHERE produkt_id = ? AND entfernt_am IS NULL
                """,
                (ts, produkt_id),
            )

    def _open_component_assignments_for_product(
        self, produkt_id: int, *, timestamp: Optional[str] = None
    ) -> None:
        product = self.connection.execute(
            "SELECT id, name, seriennummer, fahrzeug_id FROM produkte WHERE id = ? AND mandant_id = ?",
            (produkt_id, self._active_mandant_id),
        ).fetchone()
        if not product:
            return
        rows = self.connection.execute(
            """
            SELECT id, status FROM produkt_komponenten
            WHERE produkt_id = ?
            """,
            (produkt_id,),
        ).fetchall()
        for row in rows:
            status = (row["status"] or "").lower()
            if status == "ausgeschieden":
                continue
            self._record_component_assignment(
                int(row["id"]),
                produkt_id,
                timestamp=timestamp,
                produkt_row=product,
            )

    def _record_component_assignment(
        self,
        komponent_id: int,
        produkt_id: int,
        *,
        timestamp: Optional[str] = None,
        produkt_row: Optional[sqlite3.Row] = None,
    ) -> None:
        product = produkt_row
        if not product:
            product = self.connection.execute(
                """
                SELECT id, name, seriennummer, fahrzeug_id
                FROM produkte
                WHERE id = ? AND mandant_id = ?
                """,
                (produkt_id, self._active_mandant_id),
            ).fetchone()
        if not product:
            return
        fahrzeug_id = product["fahrzeug_id"] if "fahrzeug_id" in product.keys() else None
        fahrzeug_name, _kennzeichen = self._vehicle_snapshot(fahrzeug_id)
        ts = timestamp or datetime.now().isoformat()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO komponenten_einsatz_history (
                    komponent_id, produkt_id, fahrzeug_id, produkt_name_snapshot,
                    produkt_seriennummer_snapshot, fahrzeug_name_snapshot, zugeordnet_am, mandant_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    komponent_id,
                    produkt_id,
                    fahrzeug_id,
                    product["name"],
                    product["seriennummer"],
                    fahrzeug_name,
                    ts,
                    self._active_mandant_id,
                ),
            )

    def _close_component_assignment(
        self, komponent_id: int, *, timestamp: Optional[str] = None
    ) -> None:
        ts = timestamp or datetime.now().isoformat()
        with self.connection:
            self.connection.execute(
                """
                UPDATE komponenten_einsatz_history
                SET entfernt_am = COALESCE(entfernt_am, ?)
                WHERE komponent_id = ? AND entfernt_am IS NULL
                """,
                (ts, komponent_id),
            )

    def _sync_product_vehicle_history(
        self,
        produkt_id: int,
        previous_vehicle_id: Optional[int],
        new_vehicle_id: Optional[int],
    ) -> None:
        if previous_vehicle_id == new_vehicle_id:
            return
        timestamp = datetime.now().isoformat()
        if previous_vehicle_id is not None:
            self._close_product_vehicle_history_entries(
                produkt_id,
                previous_vehicle_id,
                timestamp=timestamp,
            )
        if new_vehicle_id is not None:
            self._open_product_vehicle_history_entry(
                produkt_id,
                new_vehicle_id,
                timestamp=timestamp,
            )
        self._reset_component_assignments_for_product(produkt_id, timestamp=timestamp)
        self._open_component_assignments_for_product(produkt_id, timestamp=timestamp)

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        cur = self.connection.execute(f"PRAGMA table_info({table})")
        if column in {row[1] for row in cur.fetchall()}:
            return
        self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _location_label_from_row(row: sqlite3.Row, prefix: str = "") -> str:
        parts: List[str] = []
        for key in ("land", "bereich", "bezirk", "bezirksstelle", "ortsstelle"):
            column = f"{prefix}{key}" if prefix else key
            if column in row.keys():
                value = row[column]
                if value:
                    parts.append(value)
        label = " / ".join(parts)
        funk_key = f"{prefix}funkkennung" if prefix else "funkkennung"
        if funk_key in row.keys():
            funkkennung = row[funk_key]
            if funkkennung:
                label = f"{label} ({funkkennung})" if label else str(funkkennung)
        return label

    def location_label(self, standort_id: Optional[int]) -> str:
        if not standort_id:
            return ""
        if standort_id not in self._location_cache:
            row = self.connection.execute(
                "SELECT * FROM standorte WHERE id = ?",
                (standort_id,),
            ).fetchone()
            if not row:
                return ""
            self._location_cache[standort_id] = row
        return self._location_label_from_row(self._location_cache[standort_id])

    def location_label_from_product(self, row: sqlite3.Row) -> str:
        if "standort_id" in row.keys() and row["standort_id"]:
            return self.location_label(int(row["standort_id"]))
        if any(
            key in row.keys()
            for key in (
                "standort_land",
                "standort_bereich",
                "standort_bezirk",
                "standort_bezirksstelle",
                "standort_ortsstelle",
            )
        ):
            return self._location_label_from_row(row, prefix="standort_")
        return ""

    def ensure_default_admin(self) -> None:
        """Create the default admin user if no users exist."""

        with self.connection:
            count = self.connection.execute("SELECT COUNT(*) FROM benutzer").fetchone()[0]
            if count:
                return
            password_hash = hash_password("admin")
            columns_sql = ", ".join(PERMISSION_COLUMNS)
            placeholders = ", ".join(["?"] * len(PERMISSION_COLUMNS))
            admin_preset = ROLE_PERMISSION_PRESETS.get("admin", PERMISSION_DEFAULTS)
            permission_values = [1 if admin_preset[column] else 0 for column in PERMISSION_COLUMNS]
            self.connection.execute(
                f"""
                INSERT INTO benutzer (username, password_hash, full_name, role, vorname, nachname, dienstnummer, email, {columns_sql})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, {placeholders})
                """,
                (
                    "admin",
                    password_hash,
                    "Administrator",
                    "admin",
                    "Admin",
                    "Account",
                    "0000",
                    "admin@example.com",
                    *permission_values,
                ),
            )
            self.connection.execute(
                "INSERT OR IGNORE INTO mandanten (id, name, aktiv) VALUES (1, 'Standardmandant', 1)"
            )

    # ------------------------------------------------------------------
    # tenant helpers
    # ------------------------------------------------------------------
    def set_active_mandant(self, mandant_id: Optional[int]) -> None:
        self._active_mandant_id = int(mandant_id or 1)

    def active_mandant_id(self) -> int:
        return self._active_mandant_id

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_date(value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        return datetime.strptime(value, "%Y-%m-%d").date()

    @staticmethod
    def _format_date(value: Optional[date]) -> Optional[str]:
        if not value:
            return None
        return value.isoformat()

    @staticmethod
    def _format_timestamp(value: Optional[str]) -> str:
        if not value:
            return ""
        try:
            ts = datetime.fromisoformat(value)
            return ts.strftime("%d.%m.%Y %H:%M")
        except ValueError:
            return value

    def authenticate(
        self, username: str, password: str, *, identifier: Optional[str] = None
    ) -> Optional[User]:
        row: Optional[sqlite3.Row] = None
        columns_sql = ", ".join(PERMISSION_COLUMNS)
        if identifier:
            row = self.connection.execute(
                f"""
                SELECT id, username, full_name, role, email, mandant_id, password_hash, {columns_sql}
                FROM benutzer
                WHERE dienstnummer = ? COLLATE NOCASE
                """,
                (identifier,),
            ).fetchone()
        if not row:
            row = self.connection.execute(
                f"""
                SELECT id, username, full_name, role, email, mandant_id, password_hash, {columns_sql}
                FROM benutzer
                WHERE username = ?
                """,
                (username,),
            ).fetchone()
        if not row:
            return None
        if not verify_password(password, row["password_hash"]):
            return None
        permission_kwargs = {column: bool(row[column]) for column in PERMISSION_COLUMNS}
        location_entries = self.list_user_location_permissions(row["id"])
        location_permissions = {
            int(entry["standort_id"]): LocationPermission(
                standort_id=int(entry["standort_id"]),
                lesen=bool(entry["lesen"]),
                schreiben=bool(entry["schreiben"]),
                label=str(entry["label"]),
            )
            for entry in location_entries
        }
        return User(
            id=int(row["id"]),
            username=row["username"],
            full_name=row["full_name"],
            role=row["role"],
            email=row["email"] or "",
            mandant_id=int(row["mandant_id"] or 1),
            **permission_kwargs,
            location_permissions=location_permissions,
        )

    def list_user_identifiers(self) -> List[Dict[str, str]]:
        rows = self.connection.execute(
            """
            SELECT username, full_name, COALESCE(dienstnummer, username) AS identifier
            FROM benutzer
            ORDER BY identifier COLLATE NOCASE
            """
        ).fetchall()
        return [
            {
                "username": row["username"],
                "full_name": row["full_name"],
                "identifier": row["identifier"] or row["username"],
            }
            for row in rows
        ]

    # ------------------------------------------------------------------
    # category and location management
    # ------------------------------------------------------------------
    def list_categories(self, typ: Optional[str] = None) -> List[sqlite3.Row]:
        query = "SELECT * FROM kategorien"
        params: Tuple[Any, ...] = ()
        if typ:
            query += " WHERE typ = ?"
            params = (typ,)
        return list(self.connection.execute(query, params))

    def add_category(self, name: str, typ: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO kategorien (name, typ) VALUES (?, ?)",
                (name, typ),
            )
            return int(cur.lastrowid)

    def update_category(self, category_id: int, name: str, typ: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE kategorien SET name = ?, typ = ? WHERE id = ?",
                (name, typ, category_id),
            )

    def delete_category(self, category_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM kategorien WHERE id = ?",
                (category_id,),
            )

    def list_product_types(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM produkt_typen ORDER BY name")
        )

    def add_product_type(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO produkt_typen (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def update_product_type(self, typ_id: int, name: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE produkt_typen SET name = ? WHERE id = ?",
                (name, typ_id),
            )

    def delete_product_type(self, typ_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM produkt_typen WHERE id = ?",
                (typ_id,),
            )

    def list_product_models(self, typ_id: Optional[int] = None) -> List[sqlite3.Row]:
        query = (
            "SELECT pm.*, pt.name AS typ_name FROM produkt_modelle AS pm "
            "LEFT JOIN produkt_typen AS pt ON pt.id = pm.typ_id"
        )
        params: Tuple[Any, ...] = ()
        if typ_id:
            query += " WHERE pm.typ_id = ?"
            params = (typ_id,)
        query += " ORDER BY name"
        return list(self.connection.execute(query, params))

    def add_product_model(self, typ_id: int, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO produkt_modelle (typ_id, name) VALUES (?, ?)",
                (typ_id, name),
            )
            return int(cur.lastrowid)

    def update_product_model(self, modell_id: int, typ_id: int, name: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE produkt_modelle SET typ_id = ?, name = ? WHERE id = ?",
                (typ_id, name, modell_id),
            )

    def delete_product_model(self, modell_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM produkt_modelle WHERE id = ?",
                (modell_id,),
            )

    def list_product_manufacturers(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM produkt_hersteller ORDER BY name")
        )

    def add_product_manufacturer(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO produkt_hersteller (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def update_product_manufacturer(self, hersteller_id: int, name: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE produkt_hersteller SET name = ? WHERE id = ?",
                (name, hersteller_id),
            )

    def delete_product_manufacturer(self, hersteller_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM produkt_hersteller WHERE id = ?",
                (hersteller_id,),
            )

    def list_component_types(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM komponententypen ORDER BY name")
        )

    def add_component_type(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO komponententypen (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def update_component_type(self, typ_id: int, name: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE komponententypen SET name = ? WHERE id = ?",
                (name, typ_id),
            )

    def delete_component_type(self, typ_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM komponententypen WHERE id = ?",
                (typ_id,),
            )

    def list_retirement_reasons(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM ausscheidungsgruende WHERE mandant_id = ? ORDER BY name",
                (self._active_mandant_id,),
            )
        )

    def add_retirement_reason(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO ausscheidungsgruende (name, mandant_id) VALUES (?, ?)",
                (name, self._active_mandant_id),
            )
            return int(cur.lastrowid)

    def update_retirement_reason(self, reason_id: int, name: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE ausscheidungsgruende SET name = ? WHERE id = ? AND mandant_id = ?",
                (name, reason_id, self._active_mandant_id),
            )

    def delete_retirement_reason(self, reason_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM ausscheidungsgruende WHERE id = ? AND mandant_id = ?",
                (reason_id, self._active_mandant_id),
            )

    def list_maintenance_types(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM wartungstypen ORDER BY name")
        )

    def add_maintenance_type(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO wartungstypen (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def update_maintenance_type(self, typ_id: int, name: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE wartungstypen SET name = ? WHERE id = ?",
                (name, typ_id),
            )

    def delete_maintenance_type(self, typ_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM wartungstypen WHERE id = ?",
                (typ_id,),
            )

    def list_repair_types(self) -> List[sqlite3.Row]:
        return list(self.connection.execute("SELECT * FROM reparatur_arten ORDER BY name"))

    def add_repair_type(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO reparatur_arten (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def update_repair_type(self, typ_id: int, name: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE reparatur_arten SET name = ? WHERE id = ?",
                (name, typ_id),
            )

    def delete_repair_type(self, typ_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM reparatur_arten WHERE id = ?",
                (typ_id,),
            )

    def list_upload_categories(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM upload_kategorien ORDER BY name")
        )

    def add_upload_category(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO upload_kategorien (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def update_upload_category(self, category_id: int, name: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE upload_kategorien SET name = ? WHERE id = ?",
                (name, category_id),
            )

    def delete_upload_category(self, category_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM upload_kategorien WHERE id = ?",
                (category_id,),
            )

    def list_upload_documents(self) -> List[sqlite3.Row]:
        try:
            return list(
                self.connection.execute(
                    """
                    SELECT ua.*, uk.name AS upload_kategorie_name
                    FROM upload_ablage AS ua
                    LEFT JOIN upload_kategorien AS uk ON uk.id = ua.upload_kategorie_id
                    WHERE ua.mandant_id = ?
                    ORDER BY datetime(ua.created_at) DESC
                    """,
                    (self._active_mandant_id,),
                )
            )
        except sqlite3.Error as exc:  # pragma: no cover
            self._log_internal_error("list_upload_documents failed", exc)
            return []

    def add_upload_document(
        self,
        *,
        name: str,
        source_path: Path,
        upload_kategorie_id: Optional[int],
    ) -> int:
        storage_dir = get_storage_dir() / "uploads"
        storage_dir.mkdir(parents=True, exist_ok=True)
        destination_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex}{source_path.suffix}"
        destination = storage_dir / destination_name
        shutil.copy2(source_path, destination)
        created_at = datetime.utcnow().isoformat()
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO upload_ablage (
                    name, original_name, speicherpfad, upload_kategorie_id, created_at, mandant_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    source_path.name,
                    str(destination),
                    upload_kategorie_id,
                    created_at,
                    self._active_mandant_id,
                ),
            )
        return int(cursor.lastrowid)

    def get_upload_document(self, document_id: int) -> Optional[sqlite3.Row]:
        cursor = self.connection.execute(
            """
            SELECT ua.*, uk.name AS upload_kategorie_name
            FROM upload_ablage AS ua
            LEFT JOIN upload_kategorien AS uk ON uk.id = ua.upload_kategorie_id
            WHERE ua.id = ? AND ua.mandant_id = ?
            """,
            (document_id, self._active_mandant_id),
        )
        return cursor.fetchone()

    def delete_upload_document(self, document_id: int) -> None:
        row = self.get_upload_document(document_id)
        file_path = Path(row["speicherpfad"]) if row and row["speicherpfad"] else None
        with self.connection:
            self.connection.execute("DELETE FROM upload_ablage WHERE id = ?", (document_id,))
        if file_path and file_path.exists():
            with contextlib.suppress(OSError):
                file_path.unlink()

    def list_material_names(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM material_bezeichnungen ORDER BY name")
        )

    def add_material_name(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO material_bezeichnungen (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def update_material_name(self, name_id: int, name: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE material_bezeichnungen SET name = ? WHERE id = ?",
                (name, name_id),
            )

    def delete_material_name(self, name_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM material_bezeichnungen WHERE id = ?",
                (name_id,),
            )

    def _ensure_material_name_entry(self, name: str) -> None:
        trimmed = name.strip()
        if not trimmed:
            return
        existing = self.connection.execute(
            "SELECT id FROM material_bezeichnungen WHERE name = ?",
            (trimmed,),
        ).fetchone()
        if not existing:
            self.add_material_name(trimmed)

    def list_vehicle_brands(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM fahrzeug_marken ORDER BY name")
        )

    def add_vehicle_brand(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO fahrzeug_marken (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def update_vehicle_brand(self, brand_id: int, name: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE fahrzeug_marken SET name = ? WHERE id = ?",
                (name, brand_id),
            )

    def delete_vehicle_brand(self, brand_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM fahrzeug_marken WHERE id = ?",
                (brand_id,),
            )

    def list_vehicle_models(self, marke_id: Optional[int] = None) -> List[sqlite3.Row]:
        query = (
            "SELECT fm.*, mb.name AS marke_name FROM fahrzeug_modelle AS fm "
            "LEFT JOIN fahrzeug_marken AS mb ON mb.id = fm.marke_id"
        )
        params: Tuple[Any, ...] = ()
        if marke_id:
            query += " WHERE fm.marke_id = ?"
            params = (marke_id,)
        query += " ORDER BY name"
        return list(self.connection.execute(query, params))

    def add_vehicle_model(self, marke_id: Optional[int], name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO fahrzeug_modelle (marke_id, name) VALUES (?, ?)",
                (marke_id, name),
            )
            return int(cur.lastrowid)

    def update_vehicle_model(self, model_id: int, marke_id: Optional[int], name: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE fahrzeug_modelle SET marke_id = ?, name = ? WHERE id = ?",
                (marke_id, name, model_id),
            )

    def delete_vehicle_model(self, model_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM fahrzeug_modelle WHERE id = ?",
                (model_id,),
            )

    def list_vehicle_categories(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute("SELECT * FROM fahrzeug_kategorien ORDER BY name")
        )

    def add_vehicle_category(self, name: str) -> int:
        with self.connection:
            cur = self.connection.execute(
                "INSERT INTO fahrzeug_kategorien (name) VALUES (?)",
                (name,),
            )
            return int(cur.lastrowid)

    def update_vehicle_category(self, category_id: int, name: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE fahrzeug_kategorien SET name = ? WHERE id = ?",
                (name, category_id),
            )

    def delete_vehicle_category(self, category_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM fahrzeug_kategorien WHERE id = ?",
                (category_id,),
            )

    def get_user_preferences(self, benutzer_id: int) -> Dict[str, str]:
        rows = self.connection.execute(
            "SELECT schluessel, wert FROM benutzer_einstellungen WHERE benutzer_id = ?",
            (benutzer_id,),
        ).fetchall()
        return {row["schluessel"]: row["wert"] for row in rows}

    def set_user_preference(self, benutzer_id: int, schluessel: str, wert: str) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO benutzer_einstellungen (benutzer_id, schluessel, wert)
                VALUES (?, ?, ?)
                ON CONFLICT(benutzer_id, schluessel) DO UPDATE SET wert = excluded.wert
                """,
                (benutzer_id, schluessel, wert),
            )

    def list_locations(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM standorte WHERE mandant_id = ? ORDER BY land, bereich, bezirk",
                (self._active_mandant_id,),
            )
        )

    def add_location(
        self,
        land: str,
        bereich: str,
        bezirk: str,
        bezirksstelle: str,
        ortsstelle: str,
        beschreibung: str,
        *,
        ist_fahrzeug: bool = False,
        funkkennung: str = "",
    ) -> int:
        with self.connection:
            cur = self.connection.execute(
                """
                INSERT INTO standorte (
                    land, bereich, bezirk, bezirksstelle, ortsstelle, beschreibung, ist_fahrzeug, funkkennung, mandant_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    land,
                    bereich,
                    bezirk,
                    bezirksstelle,
                    ortsstelle,
                    beschreibung,
                    1 if ist_fahrzeug else 0,
                    funkkennung.strip() or None,
                    self._active_mandant_id,
                ),
            )
        self._location_cache.clear()
        return int(cur.lastrowid)

    def get_location(self, location_id: int) -> Optional[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM standorte WHERE id = ? AND mandant_id = ?",
            (location_id, self._active_mandant_id),
        ).fetchone()

    def update_location(
        self,
        location_id: int,
        land: str,
        bereich: str,
        bezirk: str,
        bezirksstelle: str,
        ortsstelle: str,
        beschreibung: str,
        *,
        ist_fahrzeug: bool = False,
        funkkennung: str = "",
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE standorte
                SET land = ?, bereich = ?, bezirk = ?, bezirksstelle = ?, ortsstelle = ?, beschreibung = ?,
                    ist_fahrzeug = ?, funkkennung = ?
                WHERE id = ? AND mandant_id = ?
                """,
                (
                    land,
                    bereich,
                    bezirk,
                    bezirksstelle,
                    ortsstelle,
                    beschreibung,
                    1 if ist_fahrzeug else 0,
                    funkkennung.strip() or None,
                    location_id,
                    self._active_mandant_id,
                ),
            )
        self._location_cache.clear()

    def delete_location(self, location_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM standorte WHERE id = ? AND mandant_id = ?",
                (location_id, self._active_mandant_id),
            )
        self._location_cache.clear()

    # ------------------------------------------------------------------
    # contacts
    # ------------------------------------------------------------------
    def list_contacts(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM kontakte WHERE mandant_id = ? ORDER BY name",
                (self._active_mandant_id,),
            )
        )

    def add_or_update_contact(
        self,
        *,
        kontakt_id: Optional[int],
        name: str,
        adresse: str,
        telefon: str,
        email: str,
        kontaktperson: str,
        unternehmen: str,
        website: str,
        info: str,
    ) -> int:
        with self.connection:
            if kontakt_id:
                self.connection.execute(
                    """
                    UPDATE kontakte
                    SET name = ?, adresse = ?, telefon = ?, email = ?, kontaktperson = ?,
                        unternehmen = ?, website = ?, info = ?
                    WHERE id = ? AND mandant_id = ?
                    """,
                    (
                        name,
                        adresse,
                        telefon,
                        email,
                        kontaktperson,
                        unternehmen,
                        website,
                        info,
                        kontakt_id,
                        self._active_mandant_id,
                    ),
                )
                return kontakt_id
            cur = self.connection.execute(
                """
                INSERT INTO kontakte (
                    name, adresse, telefon, email, kontaktperson, unternehmen, website, info, mandant_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    adresse,
                    telefon,
                    email,
                    kontaktperson,
                    unternehmen,
                    website,
                    info,
                    self._active_mandant_id,
                ),
            )
        return int(cur.lastrowid)

    def delete_contact(self, kontakt_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM kontakte WHERE id = ? AND mandant_id = ?",
                (kontakt_id, self._active_mandant_id),
            )

    # ------------------------------------------------------------------
    # vehicle management
    # ------------------------------------------------------------------
    def list_vehicles(self) -> List[sqlite3.Row]:
        try:
            return list(
                self.connection.execute(
                    """
                    SELECT f.*,
                           s.land AS standort_land,
                           s.bereich AS standort_bereich,
                           s.bezirk AS standort_bezirk,
                           s.bezirksstelle AS standort_bezirksstelle,
                           s.ortsstelle AS standort_ortsstelle,
                           COALESCE(s.ortsstelle, s.bezirksstelle, s.bezirk, s.bereich, s.land, '') AS standort_name,
                           fm.name AS marke_name,
                           fmo.name AS fahrzeug_typ_name,
                           fk.name AS fahrzeug_kategorie_name
                    FROM fahrzeuge AS f
                    LEFT JOIN standorte AS s ON s.id = f.standort_id
                    LEFT JOIN fahrzeug_marken AS fm ON fm.id = f.marke_id
                    LEFT JOIN fahrzeug_modelle AS fmo ON fmo.id = f.fahrzeugtyp_id
                    LEFT JOIN fahrzeug_kategorien AS fk ON fk.id = f.fahrzeugkategorie_id
                    WHERE f.mandant_id = ?
                    ORDER BY f.name
                    """,
                    (self._active_mandant_id,),
                )
            )
        except sqlite3.Error as exc:
            self._log_internal_error("list_vehicles failed", exc)
            return []

    def get_vehicle(self, fahrzeug_id: int) -> Optional[sqlite3.Row]:
        return self.connection.execute(
            """
            SELECT f.*,
                   s.land AS standort_land,
                   s.bereich AS standort_bereich,
                   s.bezirk AS standort_bezirk,
                   s.bezirksstelle AS standort_bezirksstelle,
                   s.ortsstelle AS standort_ortsstelle,
                   COALESCE(s.ortsstelle, s.bezirksstelle, s.bezirk, s.bereich, s.land, '') AS standort_name,
                   fm.name AS marke_name,
                   fmo.name AS fahrzeug_typ_name,
                   fk.name AS fahrzeug_kategorie_name
            FROM fahrzeuge AS f
            LEFT JOIN standorte AS s ON s.id = f.standort_id
            LEFT JOIN fahrzeug_marken AS fm ON fm.id = f.marke_id
            LEFT JOIN fahrzeug_modelle AS fmo ON fmo.id = f.fahrzeugtyp_id
            LEFT JOIN fahrzeug_kategorien AS fk ON fk.id = f.fahrzeugkategorie_id
            WHERE f.id = ?
            """,
            (fahrzeug_id,),
        ).fetchone()

    def add_or_update_vehicle(
        self,
        *,
        fahrzeug_id: Optional[int],
        name: str,
        kennzeichen: str,
        marke: str,
        typ: str,
        kategorie: str,
        inbetriebnahme: Optional[date],
        standort_id: Optional[int],
        kilometerstand: int,
        status: str,
        marke_id: Optional[int],
        fahrzeugtyp_id: Optional[int],
        fahrzeugkategorie_id: Optional[int],
        ausserbetrieb: bool,
        ausserbetriebnahme: Optional[date],
        fahrgestellnummer: str,
        user_id: Optional[int] = None,
    ) -> int:
        with self.connection:
            inbetriebnahme_str = self._format_date(inbetriebnahme)
            ausserbetrieb_str = self._format_date(ausserbetriebnahme)
            ausserbetrieb_flag = 1 if ausserbetrieb else 0
            if fahrzeug_id:
                self.connection.execute(
                    """
                    UPDATE fahrzeuge
                    SET name = ?, kennzeichen = ?, marke = ?, typ = ?, kategorie = ?,
                        inbetriebnahme = ?, standort_id = ?, kilometerstand = ?, status = ?,
                        marke_id = ?, fahrzeugtyp_id = ?, fahrzeugkategorie_id = ?,
                        ausserbetrieb = ?, ausserbetriebnahme_datum = ?, fahrgestellnummer = ?
                    WHERE id = ? AND mandant_id = ?
                    """,
                    (
                        name,
                        kennzeichen,
                        marke,
                        typ,
                        kategorie,
                        inbetriebnahme_str,
                        standort_id,
                        kilometerstand,
                        status,
                        marke_id,
                        fahrzeugtyp_id,
                        fahrzeugkategorie_id,
                        ausserbetrieb_flag,
                        ausserbetrieb_str,
                        fahrgestellnummer,
                        fahrzeug_id,
                        self._active_mandant_id,
                    ),
                )
                self.add_vehicle_log(
                    fahrzeug_id,
                    "aktualisiert",
                    "Fahrzeugdaten aktualisiert",
                    benutzer_id=user_id,
                )
                return fahrzeug_id
            cur = self.connection.execute(
                """
                INSERT INTO fahrzeuge (
                    name, kennzeichen, marke, typ, kategorie, inbetriebnahme, standort_id,
                    kilometerstand, status, marke_id, fahrzeugtyp_id, fahrzeugkategorie_id,
                    ausserbetrieb, ausserbetriebnahme_datum, fahrgestellnummer, mandant_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    kennzeichen,
                    marke,
                    typ,
                    kategorie,
                    inbetriebnahme_str,
                    standort_id,
                    kilometerstand,
                    status,
                    marke_id,
                    fahrzeugtyp_id,
                    fahrzeugkategorie_id,
                    ausserbetrieb_flag,
                    ausserbetrieb_str,
                    fahrgestellnummer,
                    self._active_mandant_id,
                ),
            )
            new_id = int(cur.lastrowid)
            self.add_vehicle_log(new_id, "angelegt", "Fahrzeug erstellt", benutzer_id=user_id)
            return new_id

    def add_vehicle_log(
        self,
        fahrzeug_id: int,
        eintragstyp: str,
        beschreibung: str,
        *,
        benutzer_id: Optional[int] = None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO fahrzeug_log (
                    fahrzeug_id, eintragstyp, beschreibung, zeitstempel, benutzer_id, mandant_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    fahrzeug_id,
                    eintragstyp,
                    beschreibung,
                    datetime.now().isoformat(),
                    benutzer_id,
                    self._active_mandant_id,
                ),
            )

    def vehicle_history(self, fahrzeug_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT fl.*, b.full_name AS benutzer_name, b.dienstnummer
                FROM fahrzeug_log AS fl
                LEFT JOIN benutzer AS b ON b.id = fl.benutzer_id
                WHERE fl.fahrzeug_id = ? AND fl.mandant_id = ?
                ORDER BY fl.zeitstempel DESC
                """,
                (fahrzeug_id, self._active_mandant_id),
            )
        )

    def list_products_for_vehicle(self, fahrzeug_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT p.id, p.name, p.typ, p.seriennummer, p.status,
                       k.name AS kategorie_name,
                       pt.name AS produkt_typ_name,
                       pm.name AS produkt_modell_name
                FROM produkte AS p
                LEFT JOIN kategorien AS k ON k.id = p.kategorie_id
                LEFT JOIN produkt_typen AS pt ON pt.id = p.produkt_typ_id
                LEFT JOIN produkt_modelle AS pm ON pm.id = p.produkt_modell_id
                WHERE p.fahrzeug_id = ? AND p.mandant_id = ?
                ORDER BY p.name
                """,
                (fahrzeug_id, self._active_mandant_id),
            )
        )

    def transfer_vehicle_products(
        self,
        source_vehicle_id: int,
        target_vehicle_id: Optional[int],
        *,
        user_id: Optional[int] = None,
    ) -> int:
        with self.connection:
            rows = self.connection.execute(
                "SELECT id FROM produkte WHERE fahrzeug_id = ? AND mandant_id = ?",
                (source_vehicle_id, self._active_mandant_id),
            ).fetchall()
            product_ids = [int(row["id"]) for row in rows]
            if target_vehicle_id is None:
                self.connection.execute(
                    """
                    UPDATE produkte
                    SET fahrzeug_id = NULL
                    WHERE fahrzeug_id = ? AND mandant_id = ?
                    """,
                    (source_vehicle_id, self._active_mandant_id),
                )
            else:
                self.connection.execute(
                    """
                    UPDATE produkte
                    SET fahrzeug_id = ?
                    WHERE fahrzeug_id = ? AND mandant_id = ?
                    """,
                    (target_vehicle_id, source_vehicle_id, self._active_mandant_id),
                )
        for produkt_id in product_ids:
            ziel_text = "kein Fahrzeug" if not target_vehicle_id else f"Fahrzeug {target_vehicle_id}"
            self.add_product_log(
                produkt_id,
                "verschoben",
                f"Produkt auf {ziel_text} übertragen",
                benutzer_id=user_id,
            )
            self._sync_product_vehicle_history(
                produkt_id,
                source_vehicle_id,
                target_vehicle_id,
            )
        return len(product_ids)

    # ------------------------------------------------------------------
    # product management
    # ------------------------------------------------------------------
    def list_products(self) -> List[sqlite3.Row]:
        try:
            return list(
                self.connection.execute(
                    """
                    SELECT p.*,
                           k.name AS kategorie_name,
                           s.land AS standort_land,
                           s.bereich AS standort_bereich,
                           s.bezirk AS standort_bezirk,
                           s.bezirksstelle AS standort_bezirksstelle,
                           s.ortsstelle AS standort_ortsstelle,
                           COALESCE(s.ortsstelle, s.bezirksstelle, s.bezirk, s.bereich, s.land, '') AS standort_name,
                           f.name AS fahrzeug_name,
                           pt.name AS produkt_typ_name,
                           pm.name AS produkt_modell_name,
                           ph.name AS produkt_hersteller_name
                    FROM produkte AS p
                    LEFT JOIN kategorien AS k ON k.id = p.kategorie_id
                    LEFT JOIN standorte AS s ON s.id = p.standort_id
                    LEFT JOIN fahrzeuge AS f ON f.id = p.fahrzeug_id
                    LEFT JOIN produkt_typen AS pt ON pt.id = p.produkt_typ_id
                    LEFT JOIN produkt_modelle AS pm ON pm.id = p.produkt_modell_id
                    LEFT JOIN produkt_hersteller AS ph ON ph.id = p.produkt_hersteller_id
                    WHERE p.mandant_id = ?
                    ORDER BY p.name
                    """,
                    (self._active_mandant_id,),
                )
            )
        except sqlite3.Error as exc:
            self._log_internal_error("list_products failed", exc)
            return []

    def get_product(self, produkt_id: int) -> Optional[sqlite3.Row]:
        try:
            return self.connection.execute(
                """
                SELECT p.*,
                       k.name AS kategorie_name,
                       s.land AS standort_land,
                       s.bereich AS standort_bereich,
                       s.bezirk AS standort_bezirk,
                       s.bezirksstelle AS standort_bezirksstelle,
                       s.ortsstelle AS standort_ortsstelle,
                       COALESCE(s.ortsstelle, s.bezirksstelle, s.bezirk, s.bereich, s.land, '') AS standort_name,
                       f.name AS fahrzeug_name,
                       pt.name AS produkt_typ_name,
                       pm.name AS produkt_modell_name,
                       ph.name AS produkt_hersteller_name
                FROM produkte AS p
                LEFT JOIN kategorien AS k ON k.id = p.kategorie_id
                LEFT JOIN standorte AS s ON s.id = p.standort_id
                LEFT JOIN fahrzeuge AS f ON f.id = p.fahrzeug_id
                LEFT JOIN produkt_typen AS pt ON pt.id = p.produkt_typ_id
                LEFT JOIN produkt_modelle AS pm ON pm.id = p.produkt_modell_id
                LEFT JOIN produkt_hersteller AS ph ON ph.id = p.produkt_hersteller_id
                WHERE p.id = ? AND p.mandant_id = ?
                """,
                (produkt_id, self._active_mandant_id),
            ).fetchone()
        except sqlite3.Error as exc:
            self._log_internal_error("get_product failed", exc)
            return None

    def serial_exists(self, seriennummer: str, *, exclude_id: Optional[int] = None) -> bool:
        query = "SELECT id FROM produkte WHERE seriennummer = ?"
        params: Tuple[Any, ...] = (seriennummer,)
        if exclude_id is not None:
            query += " AND id <> ?"
            params = (seriennummer, exclude_id)
        row = self.connection.execute(query, params).fetchone()
        return bool(row)

    def add_or_update_product(
        self,
        *,
        produkt_id: Optional[int],
        name: str,
        typ: str,
        seriennummer: str,
        hersteller: str,
        anschaffungsdatum: Optional[date],
        kategorie_id: Optional[int],
        standort_id: Optional[int],
        fahrzeug_id: Optional[int],
        status: str,
        interne_kennung: str,
        stk_intervall: int,
        mtk_intervall: int,
        stk_aktiv: bool,
        mtk_aktiv: bool,
        letzte_stk: Optional[date],
        letzte_mtk: Optional[date],
        naechste_stk: Optional[date],
        naechste_mtk: Optional[date],
        lagerort: str,
        produkt_typ_id: Optional[int],
        produkt_modell_id: Optional[int],
        produkt_hersteller_id: Optional[int],
        informationstext: str,
        user_id: Optional[int] = None,
    ) -> int:
        previous_vehicle_id: Optional[int] = None
        if produkt_id:
            row = self.connection.execute(
                "SELECT fahrzeug_id FROM produkte WHERE id = ? AND mandant_id = ?",
                (produkt_id, self._active_mandant_id),
            ).fetchone()
            if row:
                previous_vehicle_id = row["fahrzeug_id"]
        payload = {
            "produkt_id": produkt_id,
            "name": name,
            "typ": typ,
            "seriennummer": seriennummer,
            "hersteller": hersteller,
            "anschaffungsdatum": anschaffungsdatum,
            "kategorie_id": kategorie_id,
            "standort_id": standort_id,
            "fahrzeug_id": fahrzeug_id,
            "status": status,
            "interne_kennung": interne_kennung,
            "stk_intervall": stk_intervall,
            "mtk_intervall": mtk_intervall,
            "stk_aktiv": stk_aktiv,
            "mtk_aktiv": mtk_aktiv,
            "letzte_stk": letzte_stk,
            "letzte_mtk": letzte_mtk,
            "naechste_stk": naechste_stk,
            "naechste_mtk": naechste_mtk,
            "lagerort": lagerort,
            "produkt_typ_id": produkt_typ_id,
            "produkt_modell_id": produkt_modell_id,
            "produkt_hersteller_id": produkt_hersteller_id,
            "informationstext": informationstext,
            "user_id": user_id,
        }
        errors = validate_product(payload, db=self)
        if errors:
            raise ProductValidationError(errors)
        try:
            produkt_identifier = self._add_or_update_product_impl(
                **payload,
            )
        except sqlite3.Error as exc:
            self._log_internal_error("add_or_update_product failed", exc)
            raise
        self._sync_product_vehicle_history(
            produkt_identifier,
            previous_vehicle_id,
            fahrzeug_id,
        )
        return produkt_identifier

    def _add_or_update_product_impl(
        self,
        *,
        produkt_id: Optional[int],
        name: str,
        typ: str,
        seriennummer: str,
        hersteller: str,
        anschaffungsdatum: Optional[date],
        kategorie_id: Optional[int],
        standort_id: Optional[int],
        fahrzeug_id: Optional[int],
        status: str,
        interne_kennung: str,
        stk_intervall: int,
        mtk_intervall: int,
        stk_aktiv: bool,
        mtk_aktiv: bool,
        letzte_stk: Optional[date],
        letzte_mtk: Optional[date],
        naechste_stk: Optional[date],
        naechste_mtk: Optional[date],
        lagerort: str,
        produkt_typ_id: Optional[int],
        produkt_modell_id: Optional[int],
        produkt_hersteller_id: Optional[int],
        informationstext: str,
        user_id: Optional[int] = None,
    ) -> int:
        anschaffungsdatum_str = self._format_date(anschaffungsdatum)
        letzte_stk_str = self._format_date(letzte_stk)
        letzte_mtk_str = self._format_date(letzte_mtk)
        naechste_stk_str = self._format_date(naechste_stk)
        naechste_mtk_str = self._format_date(naechste_mtk)
        stk_flag = 1 if stk_aktiv else 0
        mtk_flag = 1 if mtk_aktiv else 0
        with self.connection:
            if produkt_id:
                self.connection.execute(
                    """
                    UPDATE produkte
                    SET name = ?, typ = ?, seriennummer = ?, hersteller = ?, anschaffungsdatum = ?,
                        kategorie_id = ?, standort_id = ?, fahrzeug_id = ?, status = ?, interne_kennung = ?,
                        stk_intervall = ?, mtk_intervall = ?, letzte_stk = ?, letzte_mtk = ?, naechste_stk = ?,
                        naechste_mtk = ?, stk_aktiv = ?, mtk_aktiv = ?, lagerort = ?, produkt_typ_id = ?,
                        produkt_modell_id = ?, produkt_hersteller_id = ?, informationstext = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        typ,
                        seriennummer,
                        hersteller,
                        anschaffungsdatum_str,
                        kategorie_id,
                        standort_id,
                        fahrzeug_id,
                        status,
                        interne_kennung,
                        stk_intervall,
                        mtk_intervall,
                        letzte_stk_str,
                        letzte_mtk_str,
                        naechste_stk_str,
                        naechste_mtk_str,
                        stk_flag,
                        mtk_flag,
                        lagerort,
                        produkt_typ_id,
                        produkt_modell_id,
                        produkt_hersteller_id,
                        informationstext,
                        produkt_id,
                    ),
                )
                self.add_product_log(
                    produkt_id,
                    "aktualisiert",
                    "Produktdaten aktualisiert",
                    benutzer_id=user_id,
                )
                return produkt_id
            values = (
                name,
                typ,
                seriennummer,
                hersteller,
                anschaffungsdatum_str,
                kategorie_id,
                standort_id,
                fahrzeug_id,
                status,
                interne_kennung,
                stk_intervall,
                mtk_intervall,
                letzte_stk_str,
                letzte_mtk_str,
                naechste_stk_str,
                naechste_mtk_str,
                stk_flag,
                mtk_flag,
                lagerort,
                produkt_typ_id,
                produkt_modell_id,
                produkt_hersteller_id,
                informationstext,
            )
            placeholders = ", ".join(["?"] * len(values))
            cur = self.connection.execute(
                f"""
                INSERT INTO produkte (
                    name, typ, seriennummer, hersteller, anschaffungsdatum, kategorie_id, standort_id,
                    fahrzeug_id, status, interne_kennung, stk_intervall, mtk_intervall, letzte_stk,
                    letzte_mtk, naechste_stk, naechste_mtk, stk_aktiv, mtk_aktiv, lagerort, produkt_typ_id,
                    produkt_modell_id, produkt_hersteller_id, informationstext
                )
                VALUES ({placeholders})
                """,
                values,
            )
            new_id = int(cur.lastrowid)
            self.add_product_log(new_id, "angelegt", "Produkt erstellt", benutzer_id=user_id)
            return new_id

    def bulk_add_products(
        self,
        serial_numbers: List[str],
        *,
        name: str,
        typ: str,
        hersteller: str,
        anschaffungsdatum: Optional[date],
        kategorie_id: Optional[int],
        standort_id: Optional[int],
        fahrzeug_id: Optional[int],
        status: str,
        interne_kennung_prefix: str,
        stk_intervall: int,
        mtk_intervall: int,
        stk_aktiv: bool,
        mtk_aktiv: bool,
        letzte_stk: Optional[date],
        letzte_mtk: Optional[date],
        naechste_stk: Optional[date],
        naechste_mtk: Optional[date],
        lagerort: str,
        produkt_typ_id: Optional[int],
        produkt_modell_id: Optional[int],
        produkt_hersteller_id: Optional[int],
        informationstext: str,
        user_id: Optional[int] = None,
    ) -> Tuple[int, List[str]]:
        created = 0
        errors: List[str] = []
        serials = [serial.strip() for serial in serial_numbers if serial.strip()]
        if not serials:
            return 0, ["Keine gültigen Seriennummern übergeben."]

        typ_label = typ
        if produkt_typ_id:
            row = self.connection.execute(
                "SELECT name FROM produkt_typen WHERE id = ?",
                (produkt_typ_id,),
            ).fetchone()
            if row and row["name"]:
                typ_label = row["name"]
        model_label = ""
        if produkt_modell_id:
            row = self.connection.execute(
                "SELECT name FROM produkt_modelle WHERE id = ?",
                (produkt_modell_id,),
            ).fetchone()
            if row and row["name"]:
                model_label = row["name"]

        base_name = name.strip()
        if not base_name:
            base_name = " ".join(part for part in (typ_label, model_label) if part)

        for serial in serials:
            try:
                current_name = base_name or serial
                interne = interne_kennung_prefix.strip()
                if interne:
                    interne = f"{interne}-{serial}"
                self.add_or_update_product(
                    produkt_id=None,
                    name=current_name,
                    typ=typ_label or typ,
                    seriennummer=serial,
                    hersteller=hersteller,
                    anschaffungsdatum=anschaffungsdatum,
                    kategorie_id=kategorie_id,
                    standort_id=standort_id,
                    fahrzeug_id=fahrzeug_id,
                    status=status,
                    interne_kennung=interne,
                    stk_intervall=stk_intervall,
                    mtk_intervall=mtk_intervall,
                    stk_aktiv=stk_aktiv,
                    mtk_aktiv=mtk_aktiv,
                    letzte_stk=letzte_stk,
                    letzte_mtk=letzte_mtk,
                    naechste_stk=naechste_stk,
                    naechste_mtk=naechste_mtk,
                    lagerort=lagerort,
                    produkt_typ_id=produkt_typ_id,
                    produkt_modell_id=produkt_modell_id,
                    produkt_hersteller_id=produkt_hersteller_id,
                    informationstext=informationstext,
                    user_id=user_id,
                )
                created += 1
            except sqlite3.IntegrityError:
                errors.append(f"Seriennummer bereits vorhanden: {serial}")
            except Exception as exc:  # pragma: no cover
                errors.append(f"{serial}: {exc}")
        return created, errors

    def delete_product(self, produkt_id: int) -> None:
        self._close_all_product_vehicle_history(produkt_id)
        try:
            with self.connection:
                self.connection.execute(
                    "DELETE FROM produkte WHERE id = ? AND mandant_id = ?",
                    (produkt_id, self._active_mandant_id),
                )
        except sqlite3.Error as exc:
            self._log_internal_error("delete_product failed", exc)
            raise

    def mark_product_retired(
        self, produkt_id: int, datum: date, grund: str, *, user_id: Optional[int] = None
    ) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE produkte SET status = 'ausgeschieden' WHERE id = ?",
                (produkt_id,),
            )
            self.connection.execute(
                "INSERT INTO ausscheidungen (produkt_id, datum, grund) VALUES (?, ?, ?)",
                (produkt_id, datum.isoformat(), grund),
            )
            self.add_product_log(produkt_id, "ausgeschieden", grund, benutzer_id=user_id)

    def add_product_log(
        self,
        produkt_id: int,
        eintragstyp: str,
        beschreibung: str,
        *,
        benutzer_id: Optional[int] = None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO produkt_log (produkt_id, eintragstyp, beschreibung, zeitstempel, benutzer_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (produkt_id, eintragstyp, beschreibung, datetime.now().isoformat(), benutzer_id),
            )

    def product_history(self, produkt_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT pl.*, b.full_name AS benutzer_name, b.dienstnummer
                FROM produkt_log AS pl
                LEFT JOIN benutzer AS b ON b.id = pl.benutzer_id
                WHERE pl.produkt_id = ?
                ORDER BY pl.zeitstempel DESC
                """,
                (produkt_id,),
            )
        )

    def list_product_vehicle_history(self, produkt_id: int) -> List[sqlite3.Row]:
        try:
            return list(
                self.connection.execute(
                    """
                    SELECT pfh.*, f.name AS fahrzeug_name_live, f.kennzeichen AS fahrzeug_kennzeichen_live
                    FROM produkt_fahrzeug_history AS pfh
                    LEFT JOIN fahrzeuge AS f ON f.id = pfh.fahrzeug_id
                    WHERE pfh.produkt_id = ?
                    ORDER BY pfh.zugeordnet_am DESC, pfh.id DESC
                    """,
                    (produkt_id,),
                )
            )
        except sqlite3.Error as exc:
            self._log_internal_error("list_product_vehicle_history failed", exc)
            return []

    def product_lifecycle_report(self, produkt_id: int) -> str:
        product = self.get_product(produkt_id)
        if not product:
            raise ValueError("Produkt nicht gefunden")

        components = self.list_components(produkt_id)
        repairs = self.list_repairs(produkt_id)
        maintenance = self.list_maintenance(produkt_id)
        history = self.product_history(produkt_id)
        vehicle_assignments = self.list_product_vehicle_history(produkt_id)

        qr = qrcode.make(f"produkt:{produkt_id}:{product['seriennummer']}")
        buffer = io.BytesIO()
        qr.save(buffer, format="PNG")
        qr_data = base64.b64encode(buffer.getvalue()).decode("ascii")

        def table(rows: List[sqlite3.Row], headers: Tuple[str, ...], row_builder) -> str:
            if not rows:
                return "<p>Keine Daten vorhanden.</p>"
            head_html = "".join(f"<th>{header}</th>" for header in headers)
            body_html = "".join(
                "<tr>" + "".join(f"<td>{value}</td>" for value in row_builder(row)) + "</tr>"
                for row in rows
            )
            return f"<table class='data'><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"

        html = [
            "<html><head><meta charset='utf-8'>",
            "<style>body{font-family:Arial,sans-serif;margin:2rem;}table{border-collapse:collapse;width:100%;margin-bottom:1.5rem;}th,td{border:1px solid #ccc;padding:0.5rem;text-align:left;}h1{margin-bottom:0;}h2{margin-top:2rem;}figure{float:right;margin:0 0 1rem 1rem;}.hint{color:#555;font-style:italic;margin:0.5rem 0 1rem;}</style>",
            "</head><body>",
            f"<h1>Produkt-Lebenslauf: {product['name']}</h1>",
            "<figure>",
            f"<img src='data:image/png;base64,{qr_data}' alt='QR Code' width='160' height='160'>",
            f"<figcaption>Seriennummer: {product['seriennummer']}</figcaption>",
            "</figure>",
            "<section>",
            "<h2>Produktdetails</h2>",
            "<table class='data'><tbody>",
        ]

        status_label = STATUS_LABELS.get(product["status"], product["status"])
        detail_rows = [
            ("Name", product["name"]),
            ("Typ/Modell", product["typ"] or ""),
            ("Hersteller", product["hersteller"] or ""),
            ("Seriennummer", product["seriennummer"]),
            ("Kategorie", product["kategorie_name"] or ""),
            ("Standort", self.location_label_from_product(product)),
            ("Fahrzeug", product["fahrzeug_name"] or ""),
            ("Status", status_label),
            ("Interne Kennung", product["interne_kennung"] or ""),
            ("Anschaffungsdatum", product["anschaffungsdatum"] or ""),
            ("STK Intervall", f"{product['stk_intervall']} Monate"),
            ("MTK Intervall", f"{product['mtk_intervall']} Monate"),
        ]
        html.extend(f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in detail_rows)
        html.append("</tbody></table></section>")

        if vehicle_assignments:
            html.append("<section><h2>Einsatzfahrzeuge</h2>")
            html.append(
                table(
                    vehicle_assignments,
                    ("Von", "Bis", "Fahrzeug", "Kennzeichen"),
                    lambda row: (
                        self._format_timestamp(row["zugeordnet_am"]),
                        self._format_timestamp(row["entfernt_am"]) or "",
                        row["fahrzeug_name_snapshot"]
                        or row["fahrzeug_name_live"]
                        or "",
                        row["fahrzeug_kennzeichen"]
                        or row["fahrzeug_kennzeichen_live"]
                        or "",
                    ),
                )
            )
            html.append("</section>")

        html.append("<section><h2>Komponenten</h2>")
        html.append(
            table(
                components,
                ("Name", "Hersteller", "Seriennummer", "Anschaffungsdatum", "Bemerkung"),
                lambda row: (
                    row["name"],
                    row["hersteller"] or "",
                    row["seriennummer"] or "",
                    row["anschaffungsdatum"] or "",
                    row["bemerkung"] or "",
                ),
            )
        )
        html.append("</section>")

        html.append("<section><h2>Reparaturen</h2>")
        html.append(
            table(
                repairs,
                ("Datum", "Kosten", "Dienstleister", "Beschreibung"),
                lambda row: (
                    row["datum"] or "",
                    f"{row['kosten']:.2f} €" if row["kosten"] is not None else "",
                    row["kontakt_name"] or "",
                    row["beschreibung"] or "",
                ),
            )
        )
        html.append("</section>")

        html.append("<section><h2>Wartungen</h2>")
        html.append(
            table(
                maintenance,
                ("Geplant", "Typ", "Durchgeführt", "Beschreibung"),
                lambda row: (
                    row["geplanter_termin"] or "",
                    row["wartungstyp"],
                    row["durchgefuehrt_am"] or "",
                    row["beschreibung"] or "",
                ),
            )
        )
        html.append("</section>")

        html.append("<section><h2>Verlauf</h2>")
        html.append(
            table(
                history,
                ("Zeitstempel", "Aktion", "Benutzer", "Beschreibung"),
                lambda row: (
                    row["zeitstempel"],
                    row["eintragstyp"],
                    row["benutzer_name"]
                    or row["dienstnummer"]
                    or "",
                    row["beschreibung"] or "",
                ),
            )
        )
        html.append("</section>")

        html.append("</body></html>")
        return "".join(html)

    def component_lifecycle_report(self, komponent_id: int) -> str:
        component = self.connection.execute(
            """
            SELECT pk.*, p.name AS produkt_name, p.seriennummer AS produkt_seriennummer,
                   p.id AS produkt_id, f.name AS fahrzeug_name, f.kennzeichen,
                   kt.name AS komponententyp_name
            FROM produkt_komponenten AS pk
            JOIN produkte AS p ON p.id = pk.produkt_id
            LEFT JOIN fahrzeuge AS f ON f.id = p.fahrzeug_id
            LEFT JOIN komponententypen AS kt ON kt.id = pk.komponententyp_id
            WHERE pk.id = ?
            """,
            (komponent_id,),
        ).fetchone()
        if not component:
            raise ValueError("Komponente nicht gefunden")

        produkt_id = int(component["produkt_id"])
        repairs = self.list_component_repairs(komponent_id)
        assignment_history = self.list_component_assignment_history(komponent_id)
        product_vehicle_history = self.list_product_vehicle_history(produkt_id)

        def table(rows: List[sqlite3.Row], headers: Tuple[str, ...], row_builder) -> str:
            if not rows:
                return "<p>Keine Daten vorhanden.</p>"
            head_html = "".join(f"<th>{header}</th>" for header in headers)
            body_html = "".join(
                "<tr>" + "".join(f"<td>{value}</td>" for value in row_builder(row)) + "</tr>"
                for row in rows
            )
            return f"<table class='data'><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"

        html = [
            "<html><head><meta charset='utf-8'>",
            "<style>body{font-family:Arial,sans-serif;margin:2rem;}table{border-collapse:collapse;width:100%;margin-bottom:1.5rem;}th,td{border:1px solid #ccc;padding:0.5rem;text-align:left;}h1{margin-bottom:0;}h2{margin-top:2rem;}</style>",
            "</head><body>",
            f"<h1>Komponenten-Lebenslauf: {component['name']}</h1>",
            "<section>",
            "<h2>Komponentendetails</h2>",
            "<table class='data'><tbody>",
        ]

        status_label = STATUS_LABELS.get(component["status"], component["status"])
        detail_rows = [
            ("Typ", component["komponententyp_name"] or ""),
            ("Hersteller", component["hersteller"] or ""),
            ("Seriennummer", component["seriennummer"] or ""),
            ("Status", status_label),
            ("Anschaffungsdatum", component["anschaffungsdatum"] or ""),
            ("Produkt", component["produkt_name"] or ""),
            ("Produkt-Seriennummer", component["produkt_seriennummer"] or ""),
            ("Aktuelles Fahrzeug", component["fahrzeug_name"] or ""),
            ("Aktuelles Kennzeichen", component["kennzeichen"] or ""),
            ("Bemerkung", component["bemerkung"] or ""),
        ]
        html.extend(f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in detail_rows)
        html.append("</tbody></table></section>")

        html.append("<section><h2>Einsatzhistorie</h2>")
        html.append(
            table(
                assignment_history,
                ("Produkt", "Geräte-SN", "Fahrzeug", "Von", "Bis"),
                lambda row: (
                    row["produkt_name_snapshot"]
                    or row["produkt_name_live"]
                    or "",
                    row["produkt_seriennummer_snapshot"]
                    or row["produkt_sn_live"]
                    or "",
                    row["fahrzeug_name_snapshot"]
                    or row["fahrzeug_name_live"]
                    or "",
                    self._format_timestamp(row["zugeordnet_am"]),
                    self._format_timestamp(row["entfernt_am"]) or "",
                ),
            )
        )
        html.append("</section>")

        if product_vehicle_history:
            html.append("<section><h2>Fahrzeughistorie des Gerätes</h2>")
            html.append(
                table(
                    product_vehicle_history,
                    ("Von", "Bis", "Fahrzeug", "Kennzeichen"),
                    lambda row: (
                        self._format_timestamp(row["zugeordnet_am"]),
                        self._format_timestamp(row["entfernt_am"]) or "",
                        row["fahrzeug_name_snapshot"]
                        or row["fahrzeug_name_live"]
                        or "",
                        row["fahrzeug_kennzeichen"]
                        or row["fahrzeug_kennzeichen_live"]
                        or "",
                    ),
                )
            )
            html.append("</section>")

        html.append("<section><h2>Reparaturen</h2>")
        html.append(
            table(
                repairs,
                ("Datum", "Kosten", "Typ", "Dienstleister", "Beschreibung", "Anhänge"),
                lambda row: (
                    row["datum"] or "",
                    f"{row['kosten']:.2f} €" if row["kosten"] is not None else "",
                    row["reparatur_art_name"] or "",
                    row["kontakt_name"] or "",
                    row["beschreibung"] or "",
                    row["attachment_count"],
                ),
            )
        )
        html.append("</section>")

        html.append("</body></html>")
        return "".join(html)

    def vehicle_lifecycle_report(self, fahrzeug_id: int) -> str:
        vehicle = self.get_vehicle(fahrzeug_id)
        if not vehicle:
            raise ValueError("Fahrzeug nicht gefunden")

        products = self.list_products_for_vehicle(fahrzeug_id)
        history = self.vehicle_history(fahrzeug_id)

        def table(rows: List[sqlite3.Row], headers: Tuple[str, ...], row_builder) -> str:
            if not rows:
                return "<p>Keine Daten vorhanden.</p>"
            head_html = "".join(f"<th>{header}</th>" for header in headers)
            body_html = "".join(
                "<tr>" + "".join(f"<td>{value}</td>" for value in row_builder(row)) + "</tr>"
                for row in rows
            )
            return f"<table class='data'><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table>"

        html = [
            "<html><head><meta charset='utf-8'>",
            "<style>body{font-family:Arial,sans-serif;margin:2rem;}table{border-collapse:collapse;width:100%;margin-bottom:1.5rem;}"
            "th,td{border:1px solid #ccc;padding:0.5rem;text-align:left;}h1{margin-bottom:0;}h2{margin-top:2rem;}"
            "</style>",
            "</head><body>",
            f"<h1>Fahrzeug-Lebenslauf: {vehicle['name']}</h1>",
            "<section>",
            "<h2>Fahrzeugdetails</h2>",
            "<table class='data'><tbody>",
        ]

        detail_rows = [
            ("Funkkennung", vehicle["name"] or ""),
            ("Kennzeichen", vehicle["kennzeichen"] or ""),
            ("Marke", vehicle["marke_name"] or vehicle["marke"] or ""),
            ("Typ", vehicle["fahrzeug_typ_name"] or vehicle["typ"] or ""),
            ("Kategorie", vehicle["fahrzeug_kategorie_name"] or vehicle["kategorie"] or ""),
            ("Fahrgestellnummer", vehicle["fahrgestellnummer"] or ""),
            ("Inbetriebnahme", vehicle["inbetriebnahme"] or ""),
            ("Außerbetriebnahme", vehicle["ausserbetriebnahme_datum"] or ""),
            ("Status", STATUS_LABELS.get(vehicle["status"], vehicle["status"])),
            ("Kilometerstand", vehicle["kilometerstand"] or ""),
            ("Standort", vehicle["standort_name"] or ""),
        ]
        html.extend(f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in detail_rows)
        html.append("</tbody></table></section>")

        html.append("<section><h2>Zugeordnete Produkte</h2>")
        html.append(
            table(
                products,
                ("Produkt", "Typ", "Seriennummer", "Status", "Kategorie"),
                lambda row: (
                    row["name"],
                    row["produkt_typ_name"] or row["typ"] or "",
                    row["seriennummer"],
                    STATUS_LABELS.get(row["status"], row["status"]),
                    row["kategorie_name"] or "",
                ),
            )
        )
        html.append("</section>")

        html.append("<section><h2>Verlauf</h2>")
        html.append(
            table(
                history,
                ("Zeitstempel", "Aktion", "Benutzer", "Beschreibung"),
                lambda row: (
                    row["zeitstempel"],
                    row["eintragstyp"],
                    row["benutzer_name"] or row["dienstnummer"] or "",
                    row["beschreibung"] or "",
                ),
            )
        )
        html.append("</section>")

        html.append("</body></html>")
        return "".join(html)

    # ------------------------------------------------------------------
    # components and repairs
    # ------------------------------------------------------------------
    def list_components(self, produkt_id: int) -> List[sqlite3.Row]:
        try:
            return list(
                self.connection.execute(
                    """
                    SELECT pk.*, kt.name AS komponententyp_name
                    FROM produkt_komponenten AS pk
                    LEFT JOIN komponententypen AS kt ON kt.id = pk.komponententyp_id
                    WHERE pk.produkt_id = ?
                    ORDER BY pk.name
                    """,
                    (produkt_id,),
                )
            )
        except sqlite3.Error as exc:  # pragma: no cover - defensive logging
            self._log_internal_error("list_components failed", exc)
            return []

    def get_component(self, komponent_id: int) -> Optional[sqlite3.Row]:
        try:
            return self.connection.execute(
                """
                SELECT pk.*, p.name AS produkt_name
                FROM produkt_komponenten AS pk
                JOIN produkte AS p ON p.id = pk.produkt_id
                WHERE pk.id = ? AND p.mandant_id = ?
                """,
                (komponent_id, self._active_mandant_id),
            ).fetchone()
        except sqlite3.Error as exc:  # pragma: no cover - defensive logging
            self._log_internal_error("get_component failed", exc)
            return None

    def add_or_update_component(
        self,
        *,
        komponent_id: Optional[int],
        produkt_id: int,
        name: str,
        hersteller: str,
        seriennummer: str,
        anschaffungsdatum: Optional[date],
        bemerkung: str,
        komponententyp_id: Optional[int],
    ) -> int:
        anschaffungsdatum_str = self._format_date(anschaffungsdatum)
        with self.connection:
            if komponent_id:
                self.connection.execute(
                    """
                    UPDATE produkt_komponenten
                    SET name = ?, hersteller = ?, seriennummer = ?, anschaffungsdatum = ?, bemerkung = ?,
                        komponententyp_id = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        hersteller,
                        seriennummer,
                        anschaffungsdatum_str,
                        bemerkung,
                        komponententyp_id,
                        komponent_id,
                    ),
                )
                return komponent_id
            cur = self.connection.execute(
                """
                INSERT INTO produkt_komponenten (
                    produkt_id, name, hersteller, seriennummer, anschaffungsdatum, bemerkung, komponententyp_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    produkt_id,
                    name,
                    hersteller,
                    seriennummer,
                    anschaffungsdatum_str,
                    bemerkung,
                    komponententyp_id,
                ),
            )
            new_id = int(cur.lastrowid)
        self._record_component_assignment(new_id, produkt_id)
        return new_id

    def list_component_repairs(self, komponent_id: int) -> List[sqlite3.Row]:
        try:
            return list(
                self.connection.execute(
                    """
                    SELECT cr.*, k.name AS kontakt_name, ra.name AS reparatur_art_name,
                           COUNT(crd.id) AS attachment_count
                    FROM komponenten_reparaturen AS cr
                    LEFT JOIN kontakte AS k ON k.id = cr.kontakt_id
                    LEFT JOIN reparatur_arten AS ra ON ra.id = cr.reparatur_art_id
                    LEFT JOIN komponenten_reparatur_dateien AS crd
                        ON crd.komponenten_reparatur_id = cr.id
                    WHERE cr.komponent_id = ?
                    GROUP BY cr.id
                    ORDER BY cr.datum DESC, cr.id DESC
                    """,
                    (komponent_id,),
                )
            )
        except sqlite3.Error as exc:  # pragma: no cover - defensive logging
            self._log_internal_error("list_component_repairs failed", exc)
            return []

    def add_component_repair(
        self,
        *,
        komponent_id: int,
        datum: date,
        kosten: Optional[float],
        kontakt_id: Optional[int],
        beschreibung: str,
        reparatur_art_id: Optional[int],
        benutzer_id: Optional[int] = None,
    ) -> int:
        datum_str = datum.isoformat()
        with self.connection:
            cur = self.connection.execute(
                """
                INSERT INTO komponenten_reparaturen (
                    komponent_id, datum, kosten, kontakt_id, beschreibung, reparatur_art_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    komponent_id,
                    datum_str,
                    kosten,
                    kontakt_id,
                    beschreibung,
                    reparatur_art_id,
                ),
            )
        # status update + logging via existing helper
        self.mark_component_in_repair(
            komponent_id,
            beschreibung=beschreibung,
            datum=datum,
            benutzer_id=benutzer_id,
        )
        return int(cur.lastrowid)

    def add_component_repair_attachment(
        self,
        *,
        komponenten_reparatur_id: int,
        dateiname: str,
        speicherpfad: str,
        upload_kategorie_id: Optional[int],
    ) -> int:
        with self.connection:
            cur = self.connection.execute(
                """
                INSERT INTO komponenten_reparatur_dateien (
                    komponenten_reparatur_id, dateiname, speicherpfad, upload_kategorie_id
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    komponenten_reparatur_id,
                    dateiname,
                    speicherpfad,
                    upload_kategorie_id,
                ),
            )
            return int(cur.lastrowid)

    def list_component_repair_attachments(
        self, komponenten_reparatur_id: int
    ) -> List[sqlite3.Row]:
        try:
            return list(
                self.connection.execute(
                    """
                    SELECT crd.*, uk.name AS upload_kategorie_name
                    FROM komponenten_reparatur_dateien AS crd
                    LEFT JOIN upload_kategorien AS uk ON uk.id = crd.upload_kategorie_id
                    WHERE crd.komponenten_reparatur_id = ?
                    ORDER BY crd.id
                    """,
                    (komponenten_reparatur_id,),
                )
            )
        except sqlite3.Error as exc:  # pragma: no cover - defensive logging
            self._log_internal_error("list_component_repair_attachments failed", exc)
            return []

    def list_component_assignment_history(self, komponent_id: int) -> List[sqlite3.Row]:
        try:
            return list(
                self.connection.execute(
                    """
                    SELECT keh.*, p.name AS produkt_name_live, p.seriennummer AS produkt_sn_live,
                           f.name AS fahrzeug_name_live, f.kennzeichen AS fahrzeug_kennzeichen_live
                    FROM komponenten_einsatz_history AS keh
                    LEFT JOIN produkte AS p ON p.id = keh.produkt_id
                    LEFT JOIN fahrzeuge AS f ON f.id = keh.fahrzeug_id
                    WHERE keh.komponent_id = ?
                    ORDER BY keh.zugeordnet_am DESC, keh.id DESC
                    """,
                    (komponent_id,),
                )
            )
        except sqlite3.Error as exc:  # pragma: no cover - defensive logging
            self._log_internal_error("list_component_assignment_history failed", exc)
            return []

    def list_repairs(self, produkt_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT r.*, k.name AS kontakt_name, ra.name AS reparatur_art_name
                FROM reparaturen AS r
                LEFT JOIN kontakte AS k ON k.id = r.kontakt_id
                LEFT JOIN reparatur_arten AS ra ON ra.id = r.reparatur_art_id
                WHERE r.produkt_id = ?
                ORDER BY r.datum DESC
                """,
                (produkt_id,),
            )
        )

    def add_repair(
        self,
        *,
        produkt_id: int,
        datum: date,
        kosten: float,
        kontakt_id: Optional[int],
        beschreibung: str,
        reparatur_art_id: Optional[int],
        user_id: Optional[int] = None,
    ) -> int:
        with self.connection:
            cur = self.connection.execute(
                """
                INSERT INTO reparaturen (produkt_id, datum, kosten, kontakt_id, beschreibung, reparatur_art_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    produkt_id,
                    datum.isoformat(),
                    kosten,
                    kontakt_id,
                    beschreibung,
                    reparatur_art_id,
                ),
            )
            self.connection.execute(
                "UPDATE produkte SET status = 'in_reparatur' WHERE id = ?",
                (produkt_id,),
            )
            self.add_product_log(
                produkt_id,
                "reparatur",
                beschreibung,
                benutzer_id=user_id,
            )
            return int(cur.lastrowid)

    def delete_component(self, komponent_id: int) -> None:
        self._close_component_assignment(komponent_id)
        with self.connection:
            self.connection.execute(
                "DELETE FROM produkt_komponenten WHERE id = ?",
                (komponent_id,),
            )

    def search_components(
        self,
        term: str = "",
        *,
        status: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        like = f"%{term.lower()}%"
        standort_name_expr = "COALESCE(s.ortsstelle, s.bezirksstelle, s.bezirk, s.bereich, s.land, '')"
        query = [
            f"""
            SELECT pk.*, p.name AS produkt_name, p.seriennummer AS produkt_seriennummer,
                   p.id AS produkt_id, p.status AS produkt_status, p.interne_kennung,
                   p.standort_id, p.fahrzeug_id,
                   {standort_name_expr} AS standort_name, f.name AS fahrzeug_name,
                   kt.name AS komponententyp_name
            FROM produkt_komponenten AS pk
            JOIN produkte AS p ON p.id = pk.produkt_id
            LEFT JOIN standorte AS s ON s.id = p.standort_id
            LEFT JOIN fahrzeuge AS f ON f.id = p.fahrzeug_id
            LEFT JOIN komponententypen AS kt ON kt.id = pk.komponententyp_id
            WHERE p.mandant_id = ?
            """
        ]
        params: List[Any] = [self._active_mandant_id]
        if term:
            query.append(
                f"AND (LOWER(pk.name) LIKE ? OR LOWER(pk.seriennummer) LIKE ? OR LOWER(p.name) LIKE ? "
                f"OR LOWER(p.seriennummer) LIKE ? OR LOWER({standort_name_expr}) LIKE ?)"
            )
            params.extend([like, like, like, like, like])
        if status:
            query.append("AND pk.status = ?")
            params.append(status)
        query.append("ORDER BY pk.name COLLATE NOCASE")
        sql = "\n".join(query)
        try:
            return list(self.connection.execute(sql, tuple(params)))
        except sqlite3.Error as exc:  # pragma: no cover - defensive logging
            self._log_internal_error("search_components failed", exc)
            return []

    def mark_component_in_repair(
        self,
        komponent_id: int,
        *,
        beschreibung: str = "",
        datum: Optional[date] = None,
        benutzer_id: Optional[int] = None,
    ) -> None:
        component = self.get_component(komponent_id)
        if not component:
            raise ValueError("Komponente nicht gefunden")
        datum_str = datum.isoformat() if datum else None
        with self.connection:
            self.connection.execute(
                """
                UPDATE produkt_komponenten
                SET status = 'in_reparatur', reparatur_notiz = ?, reparatur_datum = ?,
                    ausscheidungsgrund = NULL, ausscheidungsdatum = NULL
                WHERE id = ?
                """,
                (beschreibung or None, datum_str, komponent_id),
            )
        self.add_product_log(
            int(component["produkt_id"]),
            "komponente_reparatur",
            f"{component['name']} in Reparatur: {beschreibung or 'ohne Beschreibung'}",
            benutzer_id=benutzer_id,
        )

    def complete_component_repair(
        self,
        komponent_id: int,
        *,
        benutzer_id: Optional[int] = None,
    ) -> None:
        component = self.get_component(komponent_id)
        if not component:
            raise ValueError("Komponente nicht gefunden")
        with self.connection:
            self.connection.execute(
                """
                UPDATE produkt_komponenten
                SET status = 'im_dienst', reparatur_notiz = NULL, reparatur_datum = NULL
                WHERE id = ?
                """,
                (komponent_id,),
            )
        self.add_product_log(
            int(component["produkt_id"]),
            "komponente_reparatur_abgeschlossen",
            f"{component['name']} wieder im Dienst",
            benutzer_id=benutzer_id,
        )

    def retire_component(
        self,
        komponent_id: int,
        *,
        datum: Optional[date],
        grund: str,
        benutzer_id: Optional[int] = None,
    ) -> None:
        component = self.get_component(komponent_id)
        if not component:
            raise ValueError("Komponente nicht gefunden")
        datum_str = datum.isoformat() if datum else None
        with self.connection:
            self.connection.execute(
                """
                UPDATE produkt_komponenten
                SET status = 'ausgeschieden', ausscheidungsdatum = ?, ausscheidungsgrund = ?,
                    reparatur_notiz = NULL, reparatur_datum = NULL
                WHERE id = ?
                """,
                (datum_str, grund or None, komponent_id),
            )
        beschreibung = grund or "Komponente ausgeschieden"
        self._close_component_assignment(komponent_id, timestamp=datum_str)
        self.add_product_log(
            int(component["produkt_id"]),
            "komponente_ausgeschieden",
            f"{component['name']} ausgeschieden: {beschreibung}",
            benutzer_id=benutzer_id,
        )

    def reactivate_component(self, komponent_id: int, *, benutzer_id: Optional[int] = None) -> None:
        component = self.get_component(komponent_id)
        if not component:
            raise ValueError("Komponente nicht gefunden")
        with self.connection:
            self.connection.execute(
                """
                UPDATE produkt_komponenten
                SET status = 'im_dienst', reparatur_notiz = NULL, reparatur_datum = NULL,
                    ausscheidungsgrund = NULL, ausscheidungsdatum = NULL
                WHERE id = ?
                """,
                (komponent_id,),
            )
        self._record_component_assignment(
            komponent_id,
            int(component["produkt_id"]),
        )
        self.add_product_log(
            int(component["produkt_id"]),
            "komponente_reaktiviert",
            f"{component['name']} wieder aktiv",
            benutzer_id=benutzer_id,
        )

    def add_repair_attachment(
        self,
        *,
        reparatur_id: int,
        dateiname: str,
        speicherpfad: str,
        upload_kategorie_id: Optional[int],
    ) -> int:
        with self.connection:
            cur = self.connection.execute(
                """
                INSERT INTO reparatur_dateien (reparatur_id, dateiname, speicherpfad, upload_kategorie_id)
                VALUES (?, ?, ?, ?)
                """,
                (reparatur_id, dateiname, speicherpfad, upload_kategorie_id),
            )
            return int(cur.lastrowid)

    def list_repair_attachments(self, reparatur_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT rd.*, uk.name AS upload_kategorie_name
                FROM reparatur_dateien AS rd
                LEFT JOIN upload_kategorien AS uk ON uk.id = rd.upload_kategorie_id
                WHERE rd.reparatur_id = ?
                ORDER BY rd.id
                """,
                (reparatur_id,),
            )
        )

    # ------------------------------------------------------------------
    # material management
    # ------------------------------------------------------------------
    def list_materials(self) -> List[sqlite3.Row]:
        try:
            return list(
                self.connection.execute(
                    """
                    SELECT m.*, k.name AS kategorie_name
                    FROM verbrauchsmaterial AS m
                    LEFT JOIN kategorien AS k ON k.id = m.kategorie_id
                    WHERE m.mandant_id = ?
                    ORDER BY m.name
                    """,
                    (self._active_mandant_id,),
                )
            )
        except sqlite3.Error as exc:
            self._log_internal_error("list_materials failed", exc)
            return []

    def add_or_update_material(
        self,
        *,
        material_id: Optional[int],
        name: str,
        kategorie_id: Optional[int],
        lagerort: str,
        soll_bestand: int,
        ist_bestand: int,
        verfallsdatum: Optional[date],
    ) -> int:
        verfallsdatum_str = self._format_date(verfallsdatum)
        self._ensure_material_name_entry(name)
        with self.connection:
            if material_id:
                self.connection.execute(
                    """
                    UPDATE verbrauchsmaterial
                    SET name = ?, kategorie_id = ?, lagerort = ?, soll_bestand = ?, ist_bestand = ?, verfallsdatum = ?
                    WHERE id = ? AND mandant_id = ?
                    """,
                    (
                        name,
                        kategorie_id,
                        lagerort,
                        soll_bestand,
                        ist_bestand,
                        verfallsdatum_str,
                        material_id,
                        self._active_mandant_id,
                    ),
                )
                return material_id
            cur = self.connection.execute(
                """
                INSERT INTO verbrauchsmaterial (
                    name, kategorie_id, lagerort, soll_bestand, ist_bestand, verfallsdatum, mandant_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    kategorie_id,
                    lagerort,
                    soll_bestand,
                    ist_bestand,
                    verfallsdatum_str,
                    self._active_mandant_id,
                ),
            )
            return int(cur.lastrowid)

    def material_statistics(self) -> Dict[str, Any]:
        try:
            total_items = self.connection.execute(
                "SELECT COUNT(*) FROM verbrauchsmaterial WHERE mandant_id = ?",
                (self._active_mandant_id,),
            ).fetchone()[0]
            total_bestand = self.connection.execute(
                "SELECT COALESCE(SUM(ist_bestand), 0) FROM verbrauchsmaterial WHERE mandant_id = ?",
                (self._active_mandant_id,),
            ).fetchone()[0]
            categories = [
                (
                    row["name"],
                    int(row["anzahl"] or 0),
                    int(row["bestand"] or 0),
                )
                for row in self.connection.execute(
                    """
                    SELECT COALESCE(k.name, 'Ohne Kategorie') AS name,
                           COUNT(*) AS anzahl,
                           COALESCE(SUM(m.ist_bestand), 0) AS bestand
                    FROM verbrauchsmaterial AS m
                    LEFT JOIN kategorien AS k ON k.id = m.kategorie_id
                    WHERE m.mandant_id = ?
                    GROUP BY name
                    ORDER BY name
                    """,
                    (self._active_mandant_id,),
                )
            ]
            expiring = self.connection.execute(
                "SELECT COUNT(*) FROM verbrauchsmaterial WHERE verfallsdatum IS NOT NULL AND mandant_id = ?",
                (self._active_mandant_id,),
            ).fetchone()[0]
        except sqlite3.Error as exc:
            self._log_internal_error("material_statistics failed", exc)
            return {"total_items": 0, "total_bestand": 0, "expiring": 0, "categories": []}
        return {
            "total_items": int(total_items or 0),
            "total_bestand": int(total_bestand or 0),
            "expiring": int(expiring or 0),
            "categories": categories,
        }

    def list_users(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM benutzer ORDER BY nachname, vorname"
            )
        )

    def get_user(self, benutzer_id: int) -> Optional[sqlite3.Row]:
        return self.connection.execute(
            "SELECT * FROM benutzer WHERE id = ?",
            (benutzer_id,),
        ).fetchone()

    def update_user_profile(
        self,
        *,
        benutzer_id: int,
        vorname: str,
        nachname: str,
        email: str,
    ) -> None:
        full_name = f"{vorname.strip()} {nachname.strip()}".strip() or email or "Benutzer"
        with self.connection:
            self.connection.execute(
                """
                UPDATE benutzer
                SET vorname = ?, nachname = ?, email = ?, full_name = ?
                WHERE id = ?
                """,
                (vorname, nachname, email, full_name, benutzer_id),
            )

    def list_user_location_permissions(self, benutzer_id: int) -> List[Dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT bs.standort_id,
                   bs.lesen,
                   bs.schreiben
            FROM benutzer_standorte AS bs
            WHERE bs.benutzer_id = ?
            ORDER BY bs.standort_id
            """,
            (benutzer_id,),
        ).fetchall()
        result: List[Dict[str, Any]] = []
        for row in rows:
            label = self.location_label(row["standort_id"]) if row["standort_id"] else ""
            result.append(
                {
                    "standort_id": row["standort_id"],
                    "lesen": bool(row["lesen"]),
                    "schreiben": bool(row["schreiben"]),
                    "label": label,
                }
            )
        return result

    def _replace_user_location_permissions(
        self, benutzer_id: int, permissions: Dict[int, Dict[str, bool]]
    ) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM benutzer_standorte WHERE benutzer_id = ?",
                (benutzer_id,),
            )
            for standort_id, flags in permissions.items():
                if standort_id is None:
                    continue
                lesen = 1 if flags.get("lesen") else 0
                schreiben = 1 if flags.get("schreiben") else 0
                if schreiben and not lesen:
                    lesen = 1
                self.connection.execute(
                    """
                    INSERT INTO benutzer_standorte (benutzer_id, standort_id, lesen, schreiben)
                    VALUES (?, ?, ?, ?)
                    """,
                    (benutzer_id, standort_id, lesen, schreiben),
                )

    def add_or_update_user(
        self,
        *,
        benutzer_id: Optional[int],
        vorname: str,
        nachname: str,
        dienstnummer: str,
        rolle: str,
        email: str = "",
        permissions: Optional[Dict[str, bool]] = None,
        location_permissions: Optional[Dict[int, Dict[str, bool]]] = None,
    ) -> int:
        username = dienstnummer.strip()
        if not username:
            raise ValueError("Dienstnummer darf nicht leer sein")
        full_name = f"{vorname.strip()} {nachname.strip()}".strip()
        role_preset = ROLE_PERMISSION_PRESETS.get(rolle, PERMISSION_DEFAULTS)
        merged_permissions = role_preset.copy()
        if permissions:
            for key, value in permissions.items():
                if key in merged_permissions:
                    merged_permissions[key] = bool(value)
        permission_values = [1 if merged_permissions[column] else 0 for column in PERMISSION_COLUMNS]
        with self.connection:
            if benutzer_id:
                set_clause = ", ".join(f"{column} = ?" for column in PERMISSION_COLUMNS)
                self.connection.execute(
                    f"""
                    UPDATE benutzer
                    SET username = ?, full_name = ?, role = ?, vorname = ?, nachname = ?, dienstnummer = ?, email = ?, {set_clause}
                    WHERE id = ?
                    """,
                    (
                        username,
                        full_name or username,
                        rolle,
                        vorname,
                        nachname,
                        dienstnummer,
                        email,
                        *permission_values,
                        benutzer_id,
                    ),
                )
                user_id = benutzer_id
            else:
                columns_sql = ", ".join(PERMISSION_COLUMNS)
                placeholders = ", ".join(["?"] * len(PERMISSION_COLUMNS))
                cur = self.connection.execute(
                    f"""
                    INSERT INTO benutzer (username, password_hash, full_name, role, vorname, nachname, dienstnummer, email, {columns_sql})
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, {placeholders})
                    """,
                    (
                        username,
                        hash_password(dienstnummer),
                        full_name or username,
                        rolle,
                        vorname,
                        nachname,
                        dienstnummer,
                        email,
                        *permission_values,
                    ),
                )
                user_id = int(cur.lastrowid)

        if location_permissions is not None:
            self._replace_user_location_permissions(user_id, location_permissions)

        return user_id

    def set_user_password(self, benutzer_id: int, password: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE benutzer SET password_hash = ? WHERE id = ?",
                (hash_password(password), benutzer_id),
            )

    def delete_user(self, benutzer_id: int) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM benutzer WHERE id = ?", (benutzer_id,))

    # ------------------------------------------------------------------
    # maintenance
    # ------------------------------------------------------------------
    def list_maintenance(self, produkt_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM wartungen WHERE produkt_id = ? ORDER BY geplanter_termin",
                (produkt_id,),
            )
        )

    def add_or_update_maintenance(
        self,
        *,
        wartung_id: Optional[int],
        produkt_id: int,
        geplanter_termin: date,
        wartungstyp: str,
        beschreibung: str,
        durchgefuehrt_am: Optional[date],
        durchgefuehrt_von: str,
        bemerkung: str,
    ) -> int:
        geplanter_str = geplanter_termin.isoformat()
        durchgefuehrt_str = self._format_date(durchgefuehrt_am)
        with self.connection:
            if wartung_id:
                self.connection.execute(
                    """
                    UPDATE wartungen
                    SET geplanter_termin = ?, wartungstyp = ?, beschreibung = ?, durchgefuehrt_am = ?,
                        durchgefuehrt_von = ?, bemerkung = ?
                    WHERE id = ?
                    """,
                    (
                        geplanter_str,
                        wartungstyp,
                        beschreibung,
                        durchgefuehrt_str,
                        durchgefuehrt_von,
                        bemerkung,
                        wartung_id,
                    ),
                )
                return wartung_id
            cur = self.connection.execute(
                """
                INSERT INTO wartungen (produkt_id, geplanter_termin, wartungstyp, beschreibung, durchgefuehrt_am, durchgefuehrt_von, bemerkung)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    produkt_id,
                    geplanter_str,
                    wartungstyp,
                    beschreibung,
                    durchgefuehrt_str,
                    durchgefuehrt_von,
                    bemerkung,
                ),
            )
            return int(cur.lastrowid)

    def delete_maintenance(self, wartung_id: int) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM wartungen WHERE id = ?",
                (wartung_id,),
            )

    # ------------------------------------------------------------------
    # analytics helpers
    # ------------------------------------------------------------------
    def due_products(self) -> List[sqlite3.Row]:
        today_str = date.today().isoformat()
        try:
            return list(
                self.connection.execute(
                    """
                    SELECT p.*
                    FROM produkte AS p
                    LEFT JOIN wartungen AS w ON w.produkt_id = p.id
                    WHERE (
                        p.status = 'im_dienst' AND (
                            (w.durchgefuehrt_am IS NULL AND w.geplanter_termin <= ?)
                            OR (
                                w.durchgefuehrt_am IS NOT NULL
                                AND DATE(w.durchgefuehrt_am, printf('+%d months', p.stk_intervall)) <= ?
                            )
                        )
                    )
                    GROUP BY p.id
                    """,
                    (today_str, today_str),
                )
            )
        except sqlite3.Error as exc:
            self._log_internal_error("due_products failed", exc)
            return []

    def products_in_repair(self) -> List[sqlite3.Row]:
        try:
            return list(
                self.connection.execute(
                    "SELECT * FROM produkte WHERE status = 'in_reparatur' ORDER BY name"
                )
            )
        except sqlite3.Error as exc:
            self._log_internal_error("products_in_repair failed", exc)
            return []

    def expired_materials(self) -> List[sqlite3.Row]:
        today_str = date.today().isoformat()
        return list(
            self.connection.execute(
                "SELECT * FROM verbrauchsmaterial WHERE verfallsdatum IS NOT NULL AND verfallsdatum < ?",
                (today_str,),
            )
        )

    def low_stock_materials(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM verbrauchsmaterial WHERE ist_bestand < soll_bestand"
            )
        )

    def product_status_counts(self) -> Dict[str, int]:
        try:
            rows = self.connection.execute(
                "SELECT status, COUNT(*) AS count FROM produkte GROUP BY status"
            ).fetchall()
        except sqlite3.Error as exc:
            self._log_internal_error("product_status_counts failed", exc)
            return {}
        return {row["status"]: row["count"] for row in rows}

    def repair_cost_total(self) -> float:
        value = self.connection.execute(
            "SELECT SUM(kosten) AS summe FROM reparaturen WHERE kosten IS NOT NULL"
        ).fetchone()
        total = value["summe"] if value and value["summe"] is not None else 0.0
        return float(total)

    def repair_costs_by_category(self) -> List[Tuple[str, float]]:
        rows = self.connection.execute(
            """
            SELECT COALESCE(k.name, 'Ohne Kategorie') AS kategorie,
                   SUM(r.kosten) AS summe
            FROM reparaturen AS r
            JOIN produkte AS p ON p.id = r.produkt_id
            LEFT JOIN kategorien AS k ON k.id = p.kategorie_id
            WHERE r.kosten IS NOT NULL
            GROUP BY kategorie
            ORDER BY summe DESC
            """
        ).fetchall()
        return [(row["kategorie"], float(row["summe"] or 0.0)) for row in rows]

    def repair_costs_by_vehicle(self) -> List[Tuple[str, float]]:
        rows = self.connection.execute(
            """
            SELECT COALESCE(f.name, 'Ohne Fahrzeug') AS fahrzeug,
                   SUM(r.kosten) AS summe
            FROM reparaturen AS r
            LEFT JOIN produkte AS p ON p.id = r.produkt_id
            LEFT JOIN fahrzeuge AS f ON f.id = p.fahrzeug_id
            WHERE r.kosten IS NOT NULL
            GROUP BY fahrzeug
            ORDER BY summe DESC
            """
        ).fetchall()
        return [(row["fahrzeug"], float(row["summe"] or 0.0)) for row in rows]

    def filtered_products(
        self,
        *,
        fahrzeug_id: Optional[int] = None,
        land: Optional[str] = None,
        bereich: Optional[str] = None,
        bezirk: Optional[str] = None,
        bezirksstelle: Optional[str] = None,
        ortsstelle: Optional[str] = None,
    ) -> List[sqlite3.Row]:
        rows = self.list_products()
        if fahrzeug_id:
            rows = [row for row in rows if row["fahrzeug_id"] == fahrzeug_id]
        if any([land, bereich, bezirk, bezirksstelle, ortsstelle]):
            location_cache = {row["id"]: row for row in self.list_locations()}

            def matches_location(row: sqlite3.Row) -> bool:
                standort_id = row["standort_id"] if "standort_id" in row.keys() else None
                if not standort_id:
                    return False
                location = location_cache.get(standort_id)
                if not location:
                    return False
                return all(
                    (
                        (value is None)
                        or (value == "")
                        or ((location[key] or "") == value)
                    )
                    for key, value in [
                        ("land", land),
                        ("bereich", bereich),
                        ("bezirk", bezirk),
                        ("bezirksstelle", bezirksstelle),
                        ("ortsstelle", ortsstelle),
                    ]
                )

            rows = [row for row in rows if matches_location(row)]
        return rows

    def export_products_filtered_html(
        self,
        *,
        fahrzeug_id: Optional[int] = None,
        land: Optional[str] = None,
        bereich: Optional[str] = None,
        bezirk: Optional[str] = None,
        bezirksstelle: Optional[str] = None,
        ortsstelle: Optional[str] = None,
        title: str = "Produktliste",
    ) -> str:
        rows = self.filtered_products(
            fahrzeug_id=fahrzeug_id,
            land=land,
            bereich=bereich,
            bezirk=bezirk,
            bezirksstelle=bezirksstelle,
            ortsstelle=ortsstelle,
        )
        subtitle_parts = []
        if fahrzeug_id:
            fahrzeug = self.connection.execute(
                "SELECT name FROM fahrzeuge WHERE id = ?",
                (fahrzeug_id,),
            ).fetchone()
            if fahrzeug:
                subtitle_parts.append(f"Fahrzeug: {fahrzeug['name']}")
        location_parts = [part for part in [land, bereich, bezirk, bezirksstelle, ortsstelle] if part]
        if location_parts:
            subtitle_parts.append(f"Standort: {' / '.join(location_parts)}")
        subtitle = "<p>" + " | ".join(subtitle_parts) + "</p>" if subtitle_parts else ""
        html_rows = "".join(
            "<tr>"
            + "".join(
                f"<td>{value}</td>"
                for value in [
                    row["id"],
                    row["name"],
                    row["seriennummer"],
                    STATUS_LABELS.get(row["status"], row["status"]),
                    row["kategorie_name"] or "",
                    self.location_label_from_product(row),
                    row["fahrzeug_name"] or "",
                ]
            )
            + "</tr>"
            for row in rows
        )
        return "".join(
            [
                "<html><head><meta charset='utf-8'>",
                "<style>body{font-family:Arial,sans-serif;margin:2rem;}table{border-collapse:collapse;width:100%;}th,td{border:1px solid #ccc;padding:0.5rem;text-align:left;}h1{margin-bottom:0.5rem;}p{margin:0 0 1rem 0;}</style>",
                "</head><body>",
                f"<h1>{title}</h1>",
                subtitle,
                "<table><thead><tr><th>ID</th><th>Name</th><th>Seriennummer</th><th>Status</th><th>Kategorie</th><th>Standort</th><th>Fahrzeug</th></tr></thead><tbody>",
                html_rows,
                "</tbody></table>",
                "</body></html>",
            ]
        )

    # ------------------------------------------------------------------
    def export_products_as_csv(self) -> str:
        """Return CSV data for all products."""

        rows = self.list_products()
        headers = [
            "ID",
            "Name",
            "Typ",
            "Seriennummer",
            "Hersteller",
            "Anschaffungsdatum",
            "Kategorie",
            "Standort",
            "Fahrzeug",
            "Status",
            "Interne Kennung",
            "STK Intervall",
            "MTK Intervall",
        ]
        lines = [";".join(headers)]
        for row in rows:
            status_label = STATUS_LABELS.get(row["status"], row["status"] or "")
            lines.append(
                ";".join(
                    [
                        str(row["id"]),
                        row["name"] or "",
                        row["typ"] or "",
                        row["seriennummer"] or "",
                        row["hersteller"] or "",
                        row["anschaffungsdatum"] or "",
                        row["kategorie_name"] or "",
                        self.location_label_from_product(row),
                        row["fahrzeug_name"] or "",
                        status_label,
                        row["interne_kennung"] or "",
                        str(row["stk_intervall"]),
                        str(row["mtk_intervall"]),
                    ]
                )
            )
        return "\n".join(lines)

    def export_products_as_html(self) -> str:
        rows = self.list_products()
        html_rows = "".join(
            "<tr>"
            + "".join(
                f"<td>{value}</td>"
                for value in [
                    row["id"],
                    row["name"],
                    row["seriennummer"],
                    STATUS_LABELS.get(row["status"], row["status"]),
                    row["kategorie_name"] or "",
                    self.location_label_from_product(row),
                    row["fahrzeug_name"] or "",
                ]
            )
            + "</tr>"
            for row in rows
        )
        return "".join(
            [
                "<html><head><meta charset='utf-8'>",
                "<style>body{font-family:Arial,sans-serif;margin:2rem;}table{border-collapse:collapse;width:100%;}th,td{border:1px solid #ccc;padding:0.5rem;text-align:left;}h1{margin-bottom:1rem;}</style>",
                "</head><body>",
                "<h1>Produktliste</h1>",
                "<table><thead><tr><th>ID</th><th>Name</th><th>Seriennummer</th><th>Status</th><th>Kategorie</th><th>Standort</th><th>Fahrzeug</th></tr></thead><tbody>",
                html_rows,
                "</tbody></table>",
                "</body></html>",
            ]
        )

    def export_products_as_pdf(self, filepath: Path) -> None:
        rows = self.list_products()
        pdf = canvas.Canvas(str(filepath), pagesize=A4)
        width, height = A4
        margin = 40
        y = height - margin

        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(margin, y, "Produktliste")
        y -= 24
        pdf.setFont("Helvetica", 9)

        headers = ["ID", "Name", "Seriennummer", "Status", "Kategorie", "Standort", "Fahrzeug"]
        col_widths = [40, 140, 110, 80, 100, 120, 100]

        def draw_row(values: List[str], bold: bool = False) -> None:
            nonlocal y
            if y < margin + 40:
                pdf.showPage()
                y = height - margin
                pdf.setFont("Helvetica-Bold", 16)
                pdf.drawString(margin, y, "Produktliste (Fortsetzung)")
                y -= 24
                pdf.setFont("Helvetica", 9)
                draw_row(headers, bold=True)
            pdf.setFont("Helvetica-Bold" if bold else "Helvetica", 9)
            x = margin
            for value, width_part in zip(values, col_widths):
                pdf.drawString(x, y, value[:60])
                x += width_part
            y -= 14

        draw_row(headers, bold=True)
        for row in rows:
            draw_row(
                [
                    str(row["id"]),
                    (row["name"] or "")[:60],
                    row["seriennummer"] or "",
                    STATUS_LABELS.get(row["status"], row["status"]),
                    row["kategorie_name"] or "",
                    self.location_label_from_product(row)[:60],
                    (row["fahrzeug_name"] or "")[:60],
                ]
            )

        pdf.save()

    def export_maintenance_ics(self) -> str:
        rows = self.connection.execute(
            """
            SELECT w.id, w.geplanter_termin, w.wartungstyp, w.beschreibung, p.name AS produkt_name
            FROM wartungen AS w
            JOIN produkte AS p ON p.id = w.produkt_id
            WHERE w.geplanter_termin IS NOT NULL
            ORDER BY w.geplanter_termin
            """
        ).fetchall()
        now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Ployl//Medizinprodukte//DE"]
        for row in rows:
            start = datetime.strptime(row["geplanter_termin"], "%Y-%m-%d").strftime("%Y%m%d")
            summary = f"{row['produkt_name']} - {row['wartungstyp']}"
            description = (row["beschreibung"] or "").replace("\n", "\\n")
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:wartung-{row['id']}@ployl",
                    f"DTSTAMP:{now}",
                    f"DTSTART;VALUE=DATE:{start}",
                    f"SUMMARY:{summary}",
                    f"DESCRIPTION:{description}",
                    "END:VEVENT",
                ]
            )

        due_rows = self.connection.execute(
            """
            SELECT id, name, seriennummer, naechste_stk, naechste_mtk
            FROM produkte
            WHERE (stk_aktiv = 1 AND naechste_stk IS NOT NULL)
               OR (mtk_aktiv = 1 AND naechste_mtk IS NOT NULL)
            """
        ).fetchall()
        for row in due_rows:
            if row["naechste_stk"]:
                start = datetime.strptime(row["naechste_stk"], "%Y-%m-%d").strftime("%Y%m%d")
                description = f"Seriennummer: {row['seriennummer']}"
                lines.extend(
                    [
                        "BEGIN:VEVENT",
                        f"UID:stk-{row['id']}@ployl",
                        f"DTSTAMP:{now}",
                        f"DTSTART;VALUE=DATE:{start}",
                        f"SUMMARY:{row['name']} - STK fällig",
                        f"DESCRIPTION:{description}",
                        "END:VEVENT",
                    ]
                )
            if row["naechste_mtk"]:
                start = datetime.strptime(row["naechste_mtk"], "%Y-%m-%d").strftime("%Y%m%d")
                description = f"Seriennummer: {row['seriennummer']}"
                lines.extend(
                    [
                        "BEGIN:VEVENT",
                        f"UID:mtk-{row['id']}@ployl",
                        f"DTSTAMP:{now}",
                        f"DTSTART;VALUE=DATE:{start}",
                        f"SUMMARY:{row['name']} - MTK fällig",
                        f"DESCRIPTION:{description}",
                        "END:VEVENT",
                    ]
                )

        material_rows = self.connection.execute(
            """
            SELECT id, name, verfallsdatum
            FROM verbrauchsmaterial
            WHERE verfallsdatum IS NOT NULL
            """
        ).fetchall()
        for row in material_rows:
            start = datetime.strptime(row["verfallsdatum"], "%Y-%m-%d").strftime("%Y%m%d")
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:verfall-{row['id']}@ployl",
                    f"DTSTAMP:{now}",
                    f"DTSTART;VALUE=DATE:{start}",
                    f"SUMMARY:{row['name']} - Verfallsdatum",
                    "END:VEVENT",
                ]
            )

        lines.append("END:VCALENDAR")
        return "\n".join(lines)

    def create_backup(self, backup_dir: Optional[Path] = None) -> Path:
        self.connection.commit()
        backup_dir = backup_dir or (self.db_path.parent / "backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = backup_dir / f"{self.db_path.stem}-{timestamp}{self.db_path.suffix}"
        shutil.copy2(self.db_path, target)
        return target

    def restore_backup(self, source: Path) -> None:
        """Restore the database from the given backup file."""

        if not source.exists():
            raise FileNotFoundError(source)
        self.connection.close()
        shutil.copy2(source, self.db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.initialize_schema()

    def log_event(
        self,
        *,
        ebene: str,
        nachricht: str,
        benutzer_id: Optional[int] = None,
    ) -> None:
        """Persist an entry in the central log table."""

        with self.connection:
            self.connection.execute(
                """
                INSERT INTO system_log (zeitstempel, ebene, nachricht, benutzer_id, mandant_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(timespec="seconds"),
                    ebene,
                    nachricht,
                    benutzer_id,
                    self._active_mandant_id,
                ),
            )

    def list_system_log(self, limit: int = 500) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT sl.*, b.full_name AS benutzer_name
                FROM system_log AS sl
                LEFT JOIN benutzer AS b ON b.id = sl.benutzer_id
                WHERE sl.mandant_id = ?
                ORDER BY sl.id DESC
                LIMIT ?
                """,
                (self._active_mandant_id, limit),
            )
        )

    def record_audit(
        self,
        *,
        tabelle: str,
        datensatz_id: Optional[int],
        aktion: str,
        vorher: Optional[str],
        nachher: Optional[str],
        benutzer_id: Optional[int],
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO audit_log (
                    tabelle, datensatz_id, aktion, vorher, nachher, zeitstempel, benutzer_id, mandant_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tabelle,
                    datensatz_id,
                    aktion,
                    vorher,
                    nachher,
                    datetime.utcnow().isoformat(timespec="seconds"),
                    benutzer_id,
                    self._active_mandant_id,
                ),
            )

    def list_audit_entries(
        self,
        *,
        limit: int = 200,
        benutzer_id: Optional[int] = None,
    ) -> List[sqlite3.Row]:
        query = (
            "SELECT sa.*, b.full_name AS benutzer_name FROM audit_log AS sa "
            "LEFT JOIN benutzer AS b ON b.id = sa.benutzer_id"
        )
        params: List[Any] = []
        where_clauses = ["sa.mandant_id = ?"]
        params.append(self._active_mandant_id)
        if benutzer_id:
            where_clauses.append("sa.benutzer_id = ?")
            params.append(benutzer_id)
        query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY sa.id DESC LIMIT ?"
        params.append(limit)
        return list(self.connection.execute(query, params))

    def import_ics_events(self, path: Path) -> int:
        """Parse a basic ICS file and persist the contained events."""

        count = 0
        current: Dict[str, str] = {}
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if line == "BEGIN:VEVENT":
                    current = {}
                    continue
                if line == "END:VEVENT":
                    if current:
                        self._store_ics_event(current)
                        count += 1
                    current = {}
                    continue
                if ":" in line:
                    key, value = line.split(":", 1)
                    current[key.upper()] = value
        return count

    def _store_ics_event(self, values: Dict[str, str]) -> None:
        summary = values.get("SUMMARY", "")
        dtstart = values.get("DTSTART", "")
        dtend = values.get("DTEND", "")
        produkt_id = None
        if "PRODID" in values:
            try:
                produkt_id = int(values["PRODID"].split("-")[-1])
            except ValueError:
                produkt_id = None
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO ics_importe (quelle, importiert_am, zusammenfassung, start, ende, produkt_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    values.get("UID", "unbekannt"),
                    datetime.utcnow().isoformat(timespec="seconds"),
                    summary,
                    dtstart,
                    dtend,
                    produkt_id,
                ),
            )

    def archive_logs(self, older_than_years: int = 2) -> Optional[Path]:
        cutoff = datetime.utcnow().replace(year=datetime.utcnow().year - older_than_years)
        rows = self.connection.execute(
            "SELECT * FROM system_log WHERE zeitstempel < ?",
            (cutoff.isoformat(timespec="seconds"),),
        ).fetchall()
        if not rows:
            return None
        archive_dir = self.db_path.parent / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"system_log_{cutoff.year}.txt"
        with archive_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(
                    f"{row['zeitstempel']} [{row['ebene']}] {row['nachricht']}"
                    + (f" (User {row['benutzer_id']})" if row["benutzer_id"] else "")
                    + "\n"
                )
        blob = archive_path.read_bytes()
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO archivierte_logs (log_typ, inhalt, erstellt_am)
                VALUES (?, ?, ?)
                """,
                ("system_log", sqlite3.Binary(blob), datetime.utcnow().isoformat(timespec="seconds")),
            )
            self.connection.execute(
                "DELETE FROM system_log WHERE zeitstempel < ?",
                (cutoff.isoformat(timespec="seconds"),),
            )
        return archive_path

    def create_order(
        self,
        *,
        erstellt_von: int,
        standort_id: Optional[int],
        bemerkung: str,
        positionen: List[Tuple[str, int]],
    ) -> int:
        with self.connection:
            cur = self.connection.execute(
                """
                INSERT INTO bestellungen (
                    erstellt_am, erstellt_von, status, standort_id, bemerkung, mandant_id
                )
                VALUES (?, ?, 'offen', ?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(timespec="seconds"),
                    erstellt_von,
                    standort_id,
                    bemerkung,
                    self._active_mandant_id,
                ),
            )
            bestellung_id = int(cur.lastrowid)
            for beschreibung, menge in positionen:
                self.connection.execute(
                    """
                    INSERT INTO bestellpositionen (
                        bestellung_id, beschreibung, menge, mandant_id
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (bestellung_id, beschreibung, menge, self._active_mandant_id),
                )
        return bestellung_id

    def update_order_status(
        self,
        bestellung_id: int,
        *,
        status: str,
        benutzer_id: Optional[int],
    ) -> None:
        timestamps = {
            "genehmigt": "genehmigt_am",
            "abgeschlossen": "abgeschlossen_am",
        }
        column = timestamps.get(status)
        values: List[Any] = [status]
        set_clause = "status = ?"
        if column:
            set_clause += f", {column} = ?"
            values.append(datetime.utcnow().isoformat(timespec="seconds"))
        values.extend([bestellung_id])
        with self.connection:
            self.connection.execute(
                f"UPDATE bestellungen SET {set_clause} WHERE id = ?",
                values,
            )
        self.record_audit(
            tabelle="bestellungen",
            datensatz_id=bestellung_id,
            aktion=f"status:{status}",
            vorher=None,
            nachher=None,
            benutzer_id=benutzer_id,
        )

    def list_orders(self, status: Optional[str] = None) -> List[sqlite3.Row]:
        query = (
            "SELECT b.*, s.land, s.bereich, s.bezirk, s.bezirksstelle, s.ortsstelle, u.full_name AS benutzer_name "
            "FROM bestellungen AS b "
            "LEFT JOIN standorte AS s ON s.id = b.standort_id "
            "LEFT JOIN benutzer AS u ON u.id = b.erstellt_von"
        )
        params: Tuple[Any, ...] = ()
        if status:
            query += " WHERE b.status = ? AND b.mandant_id = ?"
            params = (status, self._active_mandant_id)
        else:
            query += " WHERE b.mandant_id = ?"
            params = (self._active_mandant_id,)
        query += " ORDER BY b.erstellt_am DESC"
        return list(self.connection.execute(query, params))

    def search_global(self, term: str) -> Dict[str, List[sqlite3.Row]]:
        like = f"%{term}%"
        results: Dict[str, List[sqlite3.Row]] = {}
        queries = {
            "produkte": (
                "SELECT id, name, seriennummer FROM produkte "
                "WHERE (name LIKE ? OR seriennummer LIKE ?) AND mandant_id = ?",
                (like, like, self._active_mandant_id),
            ),
            "fahrzeuge": (
                "SELECT id, name, kennzeichen FROM fahrzeuge "
                "WHERE (name LIKE ? OR kennzeichen LIKE ?) AND mandant_id = ?",
                (like, like, self._active_mandant_id),
            ),
            "material": (
                "SELECT id, name, lagerort FROM verbrauchsmaterial WHERE name LIKE ? AND mandant_id = ?",
                (like, self._active_mandant_id),
            ),
            "kontakte": (
                "SELECT id, name, email FROM kontakte "
                "WHERE (name LIKE ? OR email LIKE ?) AND mandant_id = ?",
                (like, like, self._active_mandant_id),
            ),
        }
        try:
            for key, (query, params) in queries.items():
                results[key] = list(self.connection.execute(query, params))
        except sqlite3.Error as exc:
            self._log_internal_error("search_global failed", exc)
            for key in queries:
                results.setdefault(key, [])
        return results

    # ------------------------------------------------------------------
    # tenant & governance extensions
    # ------------------------------------------------------------------
    def list_mandanten(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM mandanten ORDER BY name"
            )
        )

    def save_mandant(
        self,
        *,
        mandant_id: Optional[int],
        name: str,
        aktiv: bool,
        kontakt_email: str,
        notizen: str,
    ) -> int:
        with self.connection:
            if mandant_id:
                self.connection.execute(
                    """
                    UPDATE mandanten
                    SET name = ?, aktiv = ?, kontakt_email = ?, notizen = ?
                    WHERE id = ?
                    """,
                    (name, 1 if aktiv else 0, kontakt_email, notizen, mandant_id),
                )
                return mandant_id
            cur = self.connection.execute(
                """
                INSERT INTO mandanten (name, aktiv, kontakt_email, notizen)
                VALUES (?, ?, ?, ?)
                """,
                (name, 1 if aktiv else 0, kontakt_email, notizen),
            )
            return int(cur.lastrowid)

    def create_product_approval(
        self,
        *,
        produkt_id: int,
        schritt: str,
        kommentar: str,
        benutzer_id: Optional[int],
    ) -> int:
        with self.connection:
            cur = self.connection.execute(
                """
                INSERT INTO produkt_freigaben (
                    produkt_id, schritt, status, kommentar, erstellt_am, angelegt_von, mandant_id
                )
                VALUES (?, ?, 'offen', ?, ?, ?, ?)
                """,
                (
                    produkt_id,
                    schritt,
                    kommentar,
                    datetime.utcnow().isoformat(timespec="seconds"),
                    benutzer_id,
                    self._active_mandant_id,
                ),
            )
            return int(cur.lastrowid)

    def list_product_approvals(self, status: Optional[str] = None) -> List[sqlite3.Row]:
        query = (
            "SELECT pf.*, p.name AS produkt_name, p.seriennummer, u.full_name AS anleger, "
            "gv.full_name AS genehmiger "
            "FROM produkt_freigaben AS pf "
            "LEFT JOIN produkte AS p ON p.id = pf.produkt_id "
            "LEFT JOIN benutzer AS u ON u.id = pf.angelegt_von "
            "LEFT JOIN benutzer AS gv ON gv.id = pf.genehmigt_von "
            "WHERE pf.mandant_id = ?"
        )
        params: List[Any] = [self._active_mandant_id]
        if status:
            query += " AND pf.status = ?"
            params.append(status)
        query += " ORDER BY pf.erstellt_am DESC"
        return list(self.connection.execute(query, params))

    def update_product_approval_status(
        self,
        approval_id: int,
        *,
        status: str,
        benutzer_id: Optional[int],
        kommentar: str = "",
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE produkt_freigaben
                SET status = ?, genehmigt_von = ?, genehmigt_am = ?, kommentar = COALESCE(?, kommentar)
                WHERE id = ? AND mandant_id = ?
                """,
                (
                    status,
                    benutzer_id,
                    datetime.utcnow().isoformat(timespec="seconds"),
                    kommentar,
                    approval_id,
                    self._active_mandant_id,
                ),
            )

    def create_capa_action(
        self,
        *,
        produkt_id: Optional[int],
        beschreibung: str,
        faellig_am: Optional[date],
        verantwortlicher_id: Optional[int],
    ) -> int:
        with self.connection:
            cur = self.connection.execute(
                """
                INSERT INTO capa_massnahmen (
                    produkt_id, beschreibung, status, faellig_am, verantwortlicher_id, erstellt_am, mandant_id
                )
                VALUES (?, ?, 'offen', ?, ?, ?, ?)
                """,
                (
                    produkt_id,
                    beschreibung,
                    self._format_date(faellig_am),
                    verantwortlicher_id,
                    datetime.utcnow().isoformat(timespec="seconds"),
                    self._active_mandant_id,
                ),
            )
            return int(cur.lastrowid)

    def list_capa_actions(self, status: Optional[str] = None) -> List[sqlite3.Row]:
        query = (
            "SELECT cm.*, p.name AS produkt_name, p.seriennummer, b.full_name AS verantwortlicher "
            "FROM capa_massnahmen AS cm "
            "LEFT JOIN produkte AS p ON p.id = cm.produkt_id "
            "LEFT JOIN benutzer AS b ON b.id = cm.verantwortlicher_id "
            "WHERE cm.mandant_id = ?"
        )
        params: List[Any] = [self._active_mandant_id]
        if status:
            query += " AND cm.status = ?"
            params.append(status)
        query += " ORDER BY cm.faellig_am IS NULL, cm.faellig_am"
        return list(self.connection.execute(query, params))

    def update_capa_status(
        self,
        massnahme_id: int,
        *,
        status: str,
        benutzer_id: Optional[int] = None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE capa_massnahmen
                SET status = ?, verantwortlicher_id = COALESCE(?, verantwortlicher_id)
                WHERE id = ? AND mandant_id = ?
                """,
                (status, benutzer_id, massnahme_id, self._active_mandant_id),
            )

    def list_regelwerke(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM regelwerke WHERE mandant_id = ? ORDER BY name",
                (self._active_mandant_id,),
            )
        )

    def save_regelwerk(
        self,
        *,
        regelwerk_id: Optional[int],
        name: str,
        beschreibung: str,
        intervall_monate: Optional[int],
    ) -> int:
        with self.connection:
            if regelwerk_id:
                self.connection.execute(
                    """
                    UPDATE regelwerke
                    SET name = ?, beschreibung = ?, intervall_monate = ?
                    WHERE id = ? AND mandant_id = ?
                    """,
                    (name, beschreibung, intervall_monate, regelwerk_id, self._active_mandant_id),
                )
                return regelwerk_id
            cur = self.connection.execute(
                """
                INSERT INTO regelwerke (name, beschreibung, intervall_monate, mandant_id)
                VALUES (?, ?, ?, ?)
                """,
                (name, beschreibung, intervall_monate, self._active_mandant_id),
            )
            return int(cur.lastrowid)

    def assign_regelwerk_to_product(
        self,
        *,
        produkt_id: int,
        regelwerk_id: int,
        letzter_abgleich: Optional[date],
        naechster_abgleich: Optional[date],
    ) -> int:
        with self.connection:
            cur = self.connection.execute(
                """
                INSERT INTO produkt_regelwerke (
                    produkt_id, regelwerk_id, letzter_abgleich, naechster_abgleich, mandant_id
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(produkt_id, regelwerk_id) DO UPDATE SET
                    letzter_abgleich = excluded.letzter_abgleich,
                    naechster_abgleich = excluded.naechster_abgleich
                """,
                (
                    produkt_id,
                    regelwerk_id,
                    self._format_date(letzter_abgleich),
                    self._format_date(naechster_abgleich),
                    self._active_mandant_id,
                ),
            )
            return int(cur.lastrowid or 0)

    def list_regelwerk_assignments(self, produkt_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT pr.*, r.name AS regelwerk_name, r.intervall_monate
                FROM produkt_regelwerke AS pr
                LEFT JOIN regelwerke AS r ON r.id = pr.regelwerk_id
                WHERE pr.produkt_id = ? AND pr.mandant_id = ?
                ORDER BY r.name
                """,
                (produkt_id, self._active_mandant_id),
            )
        )

    def list_verfahren(self) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM verfahren WHERE mandant_id = ? ORDER BY titel",
                (self._active_mandant_id,),
            )
        )

    def save_verfahren(
        self,
        *,
        verfahren_id: Optional[int],
        titel: str,
        version: str,
        beschreibung: str,
        dokument: str,
    ) -> int:
        with self.connection:
            if verfahren_id:
                self.connection.execute(
                    """
                    UPDATE verfahren
                    SET titel = ?, version = ?, beschreibung = ?, dokument = ?
                    WHERE id = ? AND mandant_id = ?
                    """,
                    (titel, version, beschreibung, dokument, verfahren_id, self._active_mandant_id),
                )
                return verfahren_id
            cur = self.connection.execute(
                """
                INSERT INTO verfahren (titel, version, beschreibung, dokument, mandant_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (titel, version, beschreibung, dokument, self._active_mandant_id),
            )
            return int(cur.lastrowid)

    def confirm_training(
        self,
        *,
        benutzer_id: int,
        verfahren_id: int,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO schulungsnachweise (benutzer_id, verfahren_id, bestaetigt_am, mandant_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(benutzer_id, verfahren_id) DO UPDATE SET
                    bestaetigt_am = excluded.bestaetigt_am
                """,
                (
                    benutzer_id,
                    verfahren_id,
                    datetime.utcnow().isoformat(timespec="seconds"),
                    self._active_mandant_id,
                ),
            )

    def list_user_trainings(self, benutzer_id: int) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT sn.*, v.titel, v.version
                FROM schulungsnachweise AS sn
                LEFT JOIN verfahren AS v ON v.id = sn.verfahren_id
                WHERE sn.benutzer_id = ? AND sn.mandant_id = ?
                ORDER BY sn.bestaetigt_am DESC
                """,
                (benutzer_id, self._active_mandant_id),
            )
        )

    def save_dashboard_layout(self, benutzer_id: int, layout: Dict[str, Any]) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO dashboard_layouts (benutzer_id, layout, erstellt_am, mandant_id)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(benutzer_id) DO UPDATE SET
                    layout = excluded.layout,
                    erstellt_am = excluded.erstellt_am
                """,
                (
                    benutzer_id,
                    json.dumps(layout),
                    datetime.utcnow().isoformat(timespec="seconds"),
                    self._active_mandant_id,
                ),
            )

    def load_dashboard_layout(self, benutzer_id: int) -> Optional[Dict[str, Any]]:
        row = self.connection.execute(
            "SELECT layout FROM dashboard_layouts WHERE benutzer_id = ? AND mandant_id = ?",
            (benutzer_id, self._active_mandant_id),
        ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["layout"])
        except json.JSONDecodeError:
            return None

    def save_filter_set(
        self,
        *,
        benutzer_id: int,
        bereich: str,
        name: str,
        daten: Dict[str, Any],
    ) -> int:
        with self.connection:
            cur = self.connection.execute(
                """
                INSERT INTO gespeicherte_filter (benutzer_id, bereich, name, daten, erstellt_am, mandant_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    benutzer_id,
                    bereich,
                    name,
                    json.dumps(daten),
                    datetime.utcnow().isoformat(timespec="seconds"),
                    self._active_mandant_id,
                ),
            )
            return int(cur.lastrowid)

    def list_filter_sets(self, benutzer_id: int, bereich: str) -> List[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT * FROM gespeicherte_filter
                WHERE benutzer_id = ? AND bereich = ? AND mandant_id = ?
                ORDER BY erstellt_am DESC
                """,
                (benutzer_id, bereich, self._active_mandant_id),
            )
        )

    def list_help_articles(self, bereich: Optional[str] = None) -> List[sqlite3.Row]:
        query = "SELECT * FROM hilfe_artikel WHERE mandant_id = ?"
        params: List[Any] = [self._active_mandant_id]
        if bereich:
            query += " AND bereich = ?"
            params.append(bereich)
        query += " ORDER BY titel"
        return list(self.connection.execute(query, params))

    def record_cockpit_snapshot(self, daten: Dict[str, Any]) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO cockpit_snapshots (erstellt_am, daten, mandant_id)
                VALUES (?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(timespec="seconds"),
                    json.dumps(daten),
                    self._active_mandant_id,
                ),
            )

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.connection.close()
