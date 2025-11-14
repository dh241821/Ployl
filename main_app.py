"""Medizinprodukte-Management System GUI."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import ttkbootstrap as ttkb
from ttkbootstrap.constants import BOTH, LEFT, W
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.tableview import Tableview

from app.database import DatabaseManager, User

import tkinter as tk
from tkinter import filedialog

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


DATE_FORMAT = "%d.%m.%Y"


def parse_date(value: str) -> Optional[date]:
    value = value.strip()
    if not value:
        return None
    return datetime.strptime(value, DATE_FORMAT).date()


def format_date(value: Optional[str]) -> str:
    if not value:
        return ""
    return datetime.strptime(value, "%Y-%m-%d").strftime(DATE_FORMAT)


class LoginDialog(ttkb.Toplevel):
    """Simple login dialog that blocks the root window until closed."""

    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.title("Anmeldung")
        self.resizable(False, False)
        self.db = db
        self.user: Optional[User] = None
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text="Benutzername").grid(row=0, column=0, sticky=W, pady=(0, 5))
        self.username_var = ttkb.StringVar()
        ttkb.Entry(container, textvariable=self.username_var, width=30).grid(row=1, column=0, sticky=W)

        ttkb.Label(container, text="Passwort").grid(row=2, column=0, sticky=W, pady=(10, 5))
        self.password_var = ttkb.StringVar()
        ttkb.Entry(container, textvariable=self.password_var, show="*", width=30).grid(row=3, column=0, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=4, column=0, pady=(20, 0), sticky=W)
        ttkb.Button(button_frame, text="Anmelden", command=self.on_login, bootstyle="success").pack(side=LEFT)
        ttkb.Button(button_frame, text="Abbrechen", command=self.on_cancel, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.bind("<Return>", lambda _event: self.on_login())
        self.username_var.set("admin")

    def on_login(self) -> None:
        username = self.username_var.get().strip()
        password = self.password_var.get()
        if not username or not password:
            Messagebox.show_error("Bitte Benutzername und Passwort eingeben", "Anmeldung fehlgeschlagen")
            return
        user = self.db.authenticate(username, password)
        if not user:
            Messagebox.show_error("Ungültige Anmeldedaten", "Anmeldung fehlgeschlagen")
            return
        self.user = user
        self.destroy()

    def on_cancel(self) -> None:
        self.user = None
        self.destroy()


class DashboardView(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db

        header = ttkb.Label(self, text="Dashboard", font=("Helvetica", 18, "bold"))
        header.pack(pady=10)

        self.kpi_frame = ttkb.Frame(self)
        self.kpi_frame.pack(fill=BOTH, padx=20)

        self.cards: Dict[str, ttkb.Label] = {}
        for title, bootstyle in [
            ("Fällige Produkte", "danger"),
            ("Produkte in Reparatur", "warning"),
            ("Abgelaufenes Material", "danger"),
            ("Niedriger Bestand", "warning"),
        ]:
            card = self._create_card(self.kpi_frame, title, bootstyle)
            card.pack(side=LEFT, padx=10, pady=10, fill=BOTH, expand=True)
            self.cards[title] = card.value_label  # type: ignore[attr-defined]

        chart_frame = ttkb.Labelframe(self, text="Status-Verteilung")
        chart_frame.pack(fill=BOTH, expand=True, padx=20, pady=(0, 10))
        self.figure = Figure(figsize=(5, 3), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill=BOTH, expand=True)

        self.tables_frame = ttkb.Frame(self)
        self.tables_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)

        self.due_table = self._create_table(self.tables_frame, "Fällige Produkte")
        self.repair_table = self._create_table(self.tables_frame, "Produkte in Reparatur")
        self.expired_table = self._create_table(self.tables_frame, "Abgelaufenes Material")
        self.low_table = self._create_table(self.tables_frame, "Material mit niedrigem Bestand")

    def _create_card(self, master: tk.Misc, title: str, bootstyle: str) -> ttkb.Frame:
        frame = ttkb.Frame(master, bootstyle=bootstyle)
        frame.configure(padding=15)
        ttkb.Label(frame, text=title, font=("Helvetica", 12, "bold"), bootstyle="inverse").pack(anchor=W)
        value_label = ttkb.Label(frame, text="0", font=("Helvetica", 24, "bold"), bootstyle="inverse")
        value_label.pack(anchor=W)
        frame.value_label = value_label  # type: ignore[attr-defined]
        return frame

    def _create_table(self, master: tk.Misc, title: str) -> Tableview:
        frame = ttkb.Labelframe(master, text=title)
        frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        table = Tableview(
            frame,
            coldata=[{"text": "Name"}, {"text": "Status"}, {"text": "Zusatz"}],
            rowdata=[],
            pagesize=10,
        )
        table.pack(fill=BOTH, expand=True)
        return table

    def refresh(self) -> None:
        due = self.db.due_products()
        repairs = self.db.products_in_repair()
        expired = self.db.expired_materials()
        low = self.db.low_stock_materials()
        status_counts = self.db.product_status_counts()

        self.cards["Fällige Produkte"].configure(text=str(len(due)))
        self.cards["Produkte in Reparatur"].configure(text=str(len(repairs)))
        self.cards["Abgelaufenes Material"].configure(text=str(len(expired)))
        self.cards["Niedriger Bestand"].configure(text=str(len(low)))

        def fill(table: Tableview, rows: Iterable[Tuple[str, str, str]]) -> None:
            table.delete_rows()
            for row in rows:
                table.insert_row(values=row)

        fill(self.due_table, ((row["name"], row["status"], row["seriennummer"]) for row in due))
        fill(self.repair_table, ((row["name"], row["status"], row["seriennummer"]) for row in repairs))
        fill(self.expired_table, ((row["name"], format_date(row["verfallsdatum"]), row["lagerort"]) for row in expired))
        fill(self.low_table, ((row["name"], f"{row['ist_bestand']}/{row['soll_bestand']}", row["lagerort"]) for row in low))

        self.ax.clear()
        statuses = list(status_counts.keys())
        values = list(status_counts.values())
        if not statuses:
            statuses = ["Keine Daten"]
            values = [0]
        color_map = {
            "im_dienst": "#198754",
            "in_reparatur": "#FFC107",
            "ausgeschieden": "#6c757d",
        }
        colors = [color_map.get(status, "#0d6efd") for status in statuses]
        self.ax.bar(statuses, values, color=colors)
        self.ax.set_ylabel("Anzahl")
        self.ax.set_title("Status-Verteilung")
        self.canvas.draw()


class ProductsView(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)

        ttkb.Button(toolbar, text="Neu", command=self.create_product, bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_product, bootstyle="secondary").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Löschen", command=self.delete_product, bootstyle="danger").pack(side=LEFT)
        ttkb.Button(toolbar, text="Export CSV", command=self.export_products, bootstyle="info").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Komponenten", command=self.manage_components, bootstyle="primary").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Reparaturen", command=self.manage_repairs, bootstyle="warning").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Wartungen", command=self.manage_maintenance, bootstyle="light").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Lebenslauf", command=self.export_lifecycle, bootstyle="info").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Liste HTML", command=self.export_html, bootstyle="primary").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="ICS Export", command=self.export_ics, bootstyle="secondary").pack(side=LEFT, padx=5)

        ttkb.Label(toolbar, text="Suche:").pack(side=LEFT, padx=(20, 5))
        self.search_var = ttkb.StringVar()
        search_entry = ttkb.Entry(toolbar, textvariable=self.search_var, width=25)
        search_entry.pack(side=LEFT)
        self.search_var.trace_add("write", lambda *_: self.refresh())

        ttkb.Label(toolbar, text="Status:").pack(side=LEFT, padx=(20, 5))
        self.status_var = ttkb.StringVar()
        status_box = ttkb.Combobox(
            toolbar,
            textvariable=self.status_var,
            values=("", "im_dienst", "in_reparatur", "ausgeschieden"),
            width=15,
        )
        status_box.pack(side=LEFT)
        status_box.set("")
        status_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh())

        columns = [
            {"text": "ID"},
            {"text": "Name"},
            {"text": "Seriennummer"},
            {"text": "Status"},
            {"text": "Standort"},
            {"text": "Fahrzeug"},
        ]

        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=15)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.table.bind("<Double-1>", lambda _event: self.edit_product())

    def selected_product_id(self) -> Optional[int]:
        if not self.table.view.focus():
            Messagebox.show_info("Bitte Produkt auswählen", "Hinweis")
            return None
        row = self.table.get_rows("selected")
        if not row:
            Messagebox.show_info("Bitte Produkt auswählen", "Hinweis")
            return None
        return int(row[0].values[0])

    def refresh(self) -> None:
        self.table.delete_rows()
        query = self.search_var.get().strip().lower()
        status_filter = self.status_var.get().strip()
        for row in self.db.list_products():
            haystack = " ".join(
                filter(
                    None,
                    [
                        row["name"],
                        row["seriennummer"],
                        row["hersteller"],
                        row["standort_name"],
                        row["fahrzeug_name"],
                        row["status"],
                    ],
                )
            ).lower()
            if query and query not in haystack:
                continue
            if status_filter and row["status"] != status_filter:
                continue
            self.table.insert_row(
                values=(
                    row["id"],
                    row["name"],
                    row["seriennummer"],
                    row["status"],
                    row["standort_name"] or "",
                    row["fahrzeug_name"] or "",
                )
            )

    def create_product(self) -> None:
        editor = ProductEditor(self, self.db)
        self.wait_window(editor)
        if editor.saved:
            self.refresh()

    def edit_product(self) -> None:
        product_id = self.selected_product_id()
        if not product_id:
            return
        editor = ProductEditor(self, self.db, produkt_id=product_id)
        self.wait_window(editor)
        if editor.saved:
            self.refresh()

    def delete_product(self) -> None:
        product_id = self.selected_product_id()
        if not product_id:
            return
        if Messagebox.okcancel("Produkt wirklich löschen?", "Bestätigung", alert=True) != "OK":
            return
        self.db.delete_product(product_id)
        self.refresh()

    def export_products(self) -> None:
        filepath = filedialog.asksaveasfilename(
            title="CSV exportieren",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not filepath:
            return
        csv_data = self.db.export_products_as_csv()
        Path(filepath).write_text(csv_data, encoding="utf-8")
        Messagebox.show_info("Export abgeschlossen", "Export")

    def manage_components(self) -> None:
        product_id = self.selected_product_id()
        if not product_id:
            return
        dialog = ComponentsDialog(self, self.db, product_id)
        self.wait_window(dialog)

    def manage_repairs(self) -> None:
        product_id = self.selected_product_id()
        if not product_id:
            return
        dialog = RepairsDialog(self, self.db, product_id)
        self.wait_window(dialog)
        self.refresh()

    def manage_maintenance(self) -> None:
        product_id = self.selected_product_id()
        if not product_id:
            return
        dialog = MaintenanceDialog(self, self.db, product_id)
        self.wait_window(dialog)

    def export_lifecycle(self) -> None:
        product_id = self.selected_product_id()
        if not product_id:
            return
        filepath = filedialog.asksaveasfilename(
            title="Produkt-Lebenslauf speichern",
            defaultextension=".html",
            filetypes=[("HTML", "*.html")],
        )
        if not filepath:
            return
        try:
            html = self.db.product_lifecycle_report(product_id)
        except ValueError as exc:
            Messagebox.show_error(str(exc), "Fehler")
            return
        Path(filepath).write_text(html, encoding="utf-8")
        Messagebox.show_info("Bericht erstellt", "Erfolg")

    def export_html(self) -> None:
        filepath = filedialog.asksaveasfilename(
            title="Produktliste speichern",
            defaultextension=".html",
            filetypes=[("HTML", "*.html")],
        )
        if not filepath:
            return
        html = self.db.export_products_as_html()
        Path(filepath).write_text(html, encoding="utf-8")
        Messagebox.show_info("Liste erstellt", "Erfolg")

    def export_ics(self) -> None:
        filepath = filedialog.asksaveasfilename(
            title="Wartungen als ICS exportieren",
            defaultextension=".ics",
            filetypes=[("ICS", "*.ics")],
        )
        if not filepath:
            return
        ics_data = self.db.export_maintenance_ics()
        Path(filepath).write_text(ics_data, encoding="utf-8")
        Messagebox.show_info("ICS Export abgeschlossen", "Erfolg")


class VehiclesView(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Neu", command=self.create_vehicle, bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_vehicle, bootstyle="secondary").pack(side=LEFT, padx=5)

        columns = [
            {"text": "ID"},
            {"text": "Name"},
            {"text": "Kennzeichen"},
            {"text": "Status"},
            {"text": "Kilometer"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=15)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.table.bind("<Double-1>", lambda _event: self.edit_vehicle())

    def selected_vehicle_id(self) -> Optional[int]:
        if not self.table.view.focus():
            Messagebox.show_info("Bitte Fahrzeug auswählen", "Hinweis")
            return None
        row = self.table.get_rows("selected")
        if not row:
            Messagebox.show_info("Bitte Fahrzeug auswählen", "Hinweis")
            return None
        return int(row[0].values[0])

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_vehicles():
            self.table.insert_row(
                values=(
                    row["id"],
                    row["name"],
                    row["kennzeichen"] or "",
                    row["status"],
                    row["kilometerstand"],
                )
            )

    def create_vehicle(self) -> None:
        editor = VehicleEditor(self, self.db)
        self.wait_window(editor)
        if editor.saved:
            self.refresh()

    def edit_vehicle(self) -> None:
        vehicle_id = self.selected_vehicle_id()
        if not vehicle_id:
            return
        editor = VehicleEditor(self, self.db, fahrzeug_id=vehicle_id)
        self.wait_window(editor)
        if editor.saved:
            self.refresh()


class MaterialsView(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Neu", command=self.create_material, bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_material, bootstyle="secondary").pack(side=LEFT, padx=5)

        columns = [
            {"text": "ID"},
            {"text": "Name"},
            {"text": "Bestand"},
            {"text": "Soll"},
            {"text": "Verfallsdatum"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=15)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.table.bind("<Double-1>", lambda _event: self.edit_material())

    def selected_material_id(self) -> Optional[int]:
        if not self.table.view.focus():
            Messagebox.show_info("Bitte Material auswählen", "Hinweis")
            return None
        row = self.table.get_rows("selected")
        if not row:
            Messagebox.show_info("Bitte Material auswählen", "Hinweis")
            return None
        return int(row[0].values[0])

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_materials():
            display_date = format_date(row["verfallsdatum"])
            self.table.insert_row(
                values=(
                    row["id"],
                    row["name"],
                    row["ist_bestand"],
                    row["soll_bestand"],
                    display_date,
                )
            )

    def create_material(self) -> None:
        editor = MaterialEditor(self, self.db)
        self.wait_window(editor)
        if editor.saved:
            self.refresh()

    def edit_material(self) -> None:
        material_id = self.selected_material_id()
        if not material_id:
            return
        editor = MaterialEditor(self, self.db, material_id=material_id)
        self.wait_window(editor)
        if editor.saved:
            self.refresh()


class MasterDataView(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db

        notebook = ttkb.Notebook(self)
        notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self.categories_frame = CategoriesFrame(notebook, db)
        notebook.add(self.categories_frame, text="Kategorien")

        self.locations_frame = LocationsFrame(notebook, db)
        notebook.add(self.locations_frame, text="Standorte")

        self.contacts_frame = ContactsFrame(notebook, db)
        notebook.add(self.contacts_frame, text="Kontakte")

    def refresh(self) -> None:
        self.categories_frame.refresh()
        self.locations_frame.refresh()
        self.contacts_frame.refresh()


class CategoriesFrame(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Neue Kategorie", command=self.add_category, bootstyle="success").pack(side=LEFT)

        columns = [
            {"text": "ID"},
            {"text": "Name"},
            {"text": "Typ"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=20)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_categories():
            self.table.insert_row(values=(row["id"], row["name"], row["typ"]))

    def add_category(self) -> None:
        dialog = SimpleEntryDialog(self, "Neue Kategorie", ["Name", "Typ (produkt/material)"])
        self.wait_window(dialog)
        if dialog.result:
            name, typ = dialog.result
            if typ not in {"produkt", "material"}:
                Messagebox.show_error("Typ muss 'produkt' oder 'material' sein", "Fehler")
                return
            self.db.add_category(name, typ)
            self.refresh()


class LocationsFrame(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Neuer Standort", command=self.add_location, bootstyle="success").pack(side=LEFT)

        columns = [
            {"text": "ID"},
            {"text": "Land"},
            {"text": "Bereich"},
            {"text": "Bezirk"},
            {"text": "Bezirksstelle"},
            {"text": "Ortsstelle"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=20)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_locations():
            self.table.insert_row(
                values=(
                    row["id"],
                    row["land"] or "",
                    row["bereich"] or "",
                    row["bezirk"] or "",
                    row["bezirksstelle"] or "",
                    row["ortsstelle"] or "",
                )
            )

    def add_location(self) -> None:
        fields = ["Land", "Bereich", "Bezirk", "Bezirksstelle", "Ortsstelle", "Beschreibung"]
        dialog = SimpleEntryDialog(self, "Neuer Standort", fields)
        self.wait_window(dialog)
        if dialog.result:
            land, bereich, bezirk, bezirksstelle, ortsstelle, beschreibung = dialog.result
            self.db.add_location(land, bereich, bezirk, bezirksstelle, ortsstelle, beschreibung)
            self.refresh()


class ContactsFrame(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Kontakt hinzufügen", command=self.add_contact, bootstyle="success").pack(side=LEFT)

        columns = [
            {"text": "ID"},
            {"text": "Name"},
            {"text": "Telefon"},
            {"text": "E-Mail"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=20)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_contacts():
            self.table.insert_row(
                values=(row["id"], row["name"], row["telefon"] or "", row["email"] or "")
            )

    def add_contact(self) -> None:
        fields = ["Name", "Adresse", "Telefon", "E-Mail", "Kontaktperson"]
        dialog = SimpleEntryDialog(self, "Neuer Kontakt", fields)
        self.wait_window(dialog)
        if dialog.result:
            name, adresse, telefon, email, kontaktperson = dialog.result
            self.db.add_or_update_contact(
                kontakt_id=None,
                name=name,
                adresse=adresse,
                telefon=telefon,
                email=email,
                kontaktperson=kontaktperson,
            )
            self.refresh()


class SimpleEntryDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, title: str, fields: List[str]) -> None:
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.result: Optional[List[str]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        self.variables: List[ttkb.StringVar] = []
        for index, label in enumerate(fields):
            ttkb.Label(container, text=label).grid(row=index, column=0, sticky=W, pady=5)
            var = ttkb.StringVar()
            ttkb.Entry(container, textvariable=var, width=40).grid(row=index, column=1, sticky=W)
            self.variables.append(var)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=len(fields), column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.grab_set()

    def on_save(self) -> None:
        self.result = [var.get() for var in self.variables]
        self.destroy()


class ProductEditor(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, db: DatabaseManager, produkt_id: Optional[int] = None) -> None:
        super().__init__(master)
        self.db = db
        self.produkt_id = produkt_id
        self.saved = False
        self.title("Produkt bearbeiten" if produkt_id else "Neues Produkt")
        self.geometry("600x500")

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        fields = [
            ("Name", "name"),
            ("Typ/Modell", "typ"),
            ("Seriennummer", "seriennummer"),
            ("Hersteller", "hersteller"),
            ("Anschaffungsdatum (TT.MM.JJJJ)", "anschaffungsdatum"),
            ("Kategorie-ID", "kategorie_id"),
            ("Standort-ID", "standort_id"),
            ("Fahrzeug-ID", "fahrzeug_id"),
            ("Status", "status"),
            ("Interne Kennung", "interne_kennung"),
            ("STK Intervall (Monate)", "stk_intervall"),
            ("MTK Intervall (Monate)", "mtk_intervall"),
        ]

        self.vars: Dict[str, ttkb.StringVar] = {}
        for index, (label, key) in enumerate(fields):
            ttkb.Label(container, text=label).grid(row=index, column=0, sticky=W, pady=5)
            var = ttkb.StringVar()
            ttkb.Entry(container, textvariable=var, width=40).grid(row=index, column=1, sticky=W)
            self.vars[key] = var

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=len(fields), column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        if produkt_id:
            self.load_data()

        self.grab_set()

    def load_data(self) -> None:
        if self.produkt_id is None:
            return
        product = self.db.get_product(self.produkt_id)
        if not product:
            Messagebox.show_error("Produkt nicht gefunden", "Fehler")
            self.destroy()
            return
        self.vars["name"].set(product["name"] or "")
        self.vars["typ"].set(product["typ"] or "")
        self.vars["seriennummer"].set(product["seriennummer"] or "")
        self.vars["hersteller"].set(product["hersteller"] or "")
        self.vars["anschaffungsdatum"].set(format_date(product["anschaffungsdatum"]))
        self.vars["kategorie_id"].set(str(product["kategorie_id"] or ""))
        self.vars["standort_id"].set(str(product["standort_id"] or ""))
        self.vars["fahrzeug_id"].set(str(product["fahrzeug_id"] or ""))
        self.vars["status"].set(product["status"]) 
        self.vars["interne_kennung"].set(product["interne_kennung"] or "")
        self.vars["stk_intervall"].set(str(product["stk_intervall"]))
        self.vars["mtk_intervall"].set(str(product["mtk_intervall"]))

    def save(self) -> None:
        try:
            anschaffungsdatum = parse_date(self.vars["anschaffungsdatum"].get())
        except ValueError:
            Messagebox.show_error("Ungültiges Datum. Format TT.MM.JJJJ", "Fehler")
            return

        if not self.vars["name"].get().strip():
            Messagebox.show_error("Name ist erforderlich", "Fehler")
            return
        if not self.vars["seriennummer"].get().strip():
            Messagebox.show_error("Seriennummer ist erforderlich", "Fehler")
            return

        try:
            stk = int(self.vars["stk_intervall"].get() or 12)
            mtk = int(self.vars["mtk_intervall"].get() or 24)
        except ValueError:
            Messagebox.show_error("Intervall muss Zahl sein", "Fehler")
            return

        try:
            produkt_id = self.db.add_or_update_product(
                produkt_id=self.produkt_id,
                name=self.vars["name"].get(),
                typ=self.vars["typ"].get(),
                seriennummer=self.vars["seriennummer"].get(),
                hersteller=self.vars["hersteller"].get(),
                anschaffungsdatum=anschaffungsdatum,
                kategorie_id=int(self.vars["kategorie_id"].get()) if self.vars["kategorie_id"].get() else None,
                standort_id=int(self.vars["standort_id"].get()) if self.vars["standort_id"].get() else None,
                fahrzeug_id=int(self.vars["fahrzeug_id"].get()) if self.vars["fahrzeug_id"].get() else None,
                status=self.vars["status"].get() or "im_dienst",
                interne_kennung=self.vars["interne_kennung"].get(),
                stk_intervall=stk,
                mtk_intervall=mtk,
            )
        except Exception as exc:  # pragma: no cover - sqlite errors are surfaced to the UI
            Messagebox.show_error(str(exc), "Fehler")
            return

        self.saved = True
        Messagebox.show_info("Produkt gespeichert", "Erfolg")
        self.destroy()


class VehicleEditor(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, db: DatabaseManager, fahrzeug_id: Optional[int] = None) -> None:
        super().__init__(master)
        self.db = db
        self.fahrzeug_id = fahrzeug_id
        self.saved = False
        self.title("Fahrzeug bearbeiten" if fahrzeug_id else "Neues Fahrzeug")
        self.geometry("500x450")

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        fields = [
            ("Name", "name"),
            ("Kennzeichen", "kennzeichen"),
            ("Marke", "marke"),
            ("Typ", "typ"),
            ("Kategorie", "kategorie"),
            ("Inbetriebnahme (TT.MM.JJJJ)", "inbetriebnahme"),
            ("Standort-ID", "standort_id"),
            ("Kilometerstand", "kilometerstand"),
            ("Status", "status"),
        ]

        self.vars: Dict[str, ttkb.StringVar] = {}
        for index, (label, key) in enumerate(fields):
            ttkb.Label(container, text=label).grid(row=index, column=0, sticky=W, pady=5)
            var = ttkb.StringVar()
            ttkb.Entry(container, textvariable=var, width=40).grid(row=index, column=1, sticky=W)
            self.vars[key] = var

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=len(fields), column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        if fahrzeug_id:
            self.load_data()

        self.grab_set()

    def load_data(self) -> None:
        vehicle = next((row for row in self.db.list_vehicles() if row["id"] == self.fahrzeug_id), None)
        if not vehicle:
            Messagebox.show_error("Fahrzeug nicht gefunden", "Fehler")
            self.destroy()
            return
        self.vars["name"].set(vehicle["name"] or "")
        self.vars["kennzeichen"].set(vehicle["kennzeichen"] or "")
        self.vars["marke"].set(vehicle["marke"] or "")
        self.vars["typ"].set(vehicle["typ"] or "")
        self.vars["kategorie"].set(vehicle["kategorie"] or "")
        self.vars["inbetriebnahme"].set(format_date(vehicle["inbetriebnahme"]))
        self.vars["standort_id"].set(str(vehicle["standort_id"] or ""))
        self.vars["kilometerstand"].set(str(vehicle["kilometerstand"] or 0))
        self.vars["status"].set(vehicle["status"] or "im_dienst")

    def save(self) -> None:
        try:
            inbetriebnahme = parse_date(self.vars["inbetriebnahme"].get())
        except ValueError:
            Messagebox.show_error("Ungültiges Datum. Format TT.MM.JJJJ", "Fehler")
            return

        try:
            kilometer = int(self.vars["kilometerstand"].get() or 0)
        except ValueError:
            Messagebox.show_error("Kilometerstand muss Zahl sein", "Fehler")
            return

        if not self.vars["name"].get().strip():
            Messagebox.show_error("Name ist erforderlich", "Fehler")
            return

        self.db.add_or_update_vehicle(
            fahrzeug_id=self.fahrzeug_id,
            name=self.vars["name"].get(),
            kennzeichen=self.vars["kennzeichen"].get(),
            marke=self.vars["marke"].get(),
            typ=self.vars["typ"].get(),
            kategorie=self.vars["kategorie"].get(),
            inbetriebnahme=inbetriebnahme,
            standort_id=int(self.vars["standort_id"].get()) if self.vars["standort_id"].get() else None,
            kilometerstand=kilometer,
            status=self.vars["status"].get() or "im_dienst",
        )
        self.saved = True
        Messagebox.show_info("Fahrzeug gespeichert", "Erfolg")
        self.destroy()


class MaterialEditor(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, db: DatabaseManager, material_id: Optional[int] = None) -> None:
        super().__init__(master)
        self.db = db
        self.material_id = material_id
        self.saved = False
        self.title("Material bearbeiten" if material_id else "Neues Material")
        self.geometry("500x400")

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        fields = [
            ("Name", "name"),
            ("Kategorie-ID", "kategorie_id"),
            ("Lagerort", "lagerort"),
            ("Soll-Bestand", "soll_bestand"),
            ("Ist-Bestand", "ist_bestand"),
            ("Verfallsdatum (TT.MM.JJJJ)", "verfallsdatum"),
        ]

        self.vars: Dict[str, ttkb.StringVar] = {}
        for index, (label, key) in enumerate(fields):
            ttkb.Label(container, text=label).grid(row=index, column=0, sticky=W, pady=5)
            var = ttkb.StringVar()
            ttkb.Entry(container, textvariable=var, width=40).grid(row=index, column=1, sticky=W)
            self.vars[key] = var

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=len(fields), column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        if material_id:
            self.load_data()

        self.grab_set()

    def load_data(self) -> None:
        material = next((row for row in self.db.list_materials() if row["id"] == self.material_id), None)
        if not material:
            Messagebox.show_error("Material nicht gefunden", "Fehler")
            self.destroy()
            return
        self.vars["name"].set(material["name"] or "")
        self.vars["kategorie_id"].set(str(material["kategorie_id"] or ""))
        self.vars["lagerort"].set(material["lagerort"] or "")
        self.vars["soll_bestand"].set(str(material["soll_bestand"]))
        self.vars["ist_bestand"].set(str(material["ist_bestand"]))
        self.vars["verfallsdatum"].set(format_date(material["verfallsdatum"]))

    def save(self) -> None:
        try:
            soll = int(self.vars["soll_bestand"].get() or 0)
            ist = int(self.vars["ist_bestand"].get() or 0)
        except ValueError:
            Messagebox.show_error("Bestand muss Zahl sein", "Fehler")
            return

        try:
            verfallsdatum = parse_date(self.vars["verfallsdatum"].get())
        except ValueError:
            Messagebox.show_error("Ungültiges Datum", "Fehler")
            return

        if not self.vars["name"].get().strip():
            Messagebox.show_error("Name ist erforderlich", "Fehler")
            return

        self.db.add_or_update_material(
            material_id=self.material_id,
            name=self.vars["name"].get(),
            kategorie_id=int(self.vars["kategorie_id"].get()) if self.vars["kategorie_id"].get() else None,
            lagerort=self.vars["lagerort"].get(),
            soll_bestand=soll,
            ist_bestand=ist,
            verfallsdatum=verfallsdatum,
        )
        self.saved = True
        Messagebox.show_info("Material gespeichert", "Erfolg")
        self.destroy()


class ComponentsDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, db: DatabaseManager, produkt_id: int) -> None:
        super().__init__(master)
        self.db = db
        self.produkt_id = produkt_id
        self.title("Komponenten verwalten")
        self.geometry("600x400")

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Hinzufügen", command=self.add_component, bootstyle="success").pack(side=LEFT)

        columns = [
            {"text": "ID"},
            {"text": "Name"},
            {"text": "Seriennummer"},
            {"text": "Bemerkung"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=15)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self.refresh()
        self.grab_set()

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_components(self.produkt_id):
            self.table.insert_row(
                values=(row["id"], row["name"], row["seriennummer"] or "", row["bemerkung"] or "")
            )

    def add_component(self) -> None:
        fields = ["Name", "Hersteller", "Seriennummer", "Anschaffungsdatum (TT.MM.JJJJ)", "Bemerkung"]
        dialog = SimpleEntryDialog(self, "Komponente hinzufügen", fields)
        self.wait_window(dialog)
        if dialog.result:
            name, hersteller, seriennummer, anschaffungsdatum, bemerkung = dialog.result
            try:
                anschaffungs_date = parse_date(anschaffungsdatum)
            except ValueError:
                Messagebox.show_error("Ungültiges Datum", "Fehler")
                return
            self.db.add_or_update_component(
                komponent_id=None,
                produkt_id=self.produkt_id,
                name=name,
                hersteller=hersteller,
                seriennummer=seriennummer,
                anschaffungsdatum=anschaffungs_date,
                bemerkung=bemerkung,
            )
            self.refresh()


class RepairsDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, db: DatabaseManager, produkt_id: int) -> None:
        super().__init__(master)
        self.db = db
        self.produkt_id = produkt_id
        self.title("Reparaturen")
        self.geometry("650x450")

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Reparatur melden", command=self.add_repair, bootstyle="success").pack(side=LEFT)

        columns = [
            {"text": "Datum"},
            {"text": "Kosten"},
            {"text": "Dienstleister"},
            {"text": "Beschreibung"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=15)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self.refresh()
        self.grab_set()

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_repairs(self.produkt_id):
            self.table.insert_row(
                values=(
                    format_date(row["datum"]),
                    f"{row['kosten']:.2f}" if row["kosten"] is not None else "",
                    row["kontakt_name"] or "",
                    row["beschreibung"] or "",
                )
            )

    def add_repair(self) -> None:
        fields = ["Datum (TT.MM.JJJJ)", "Kosten", "Kontakt-ID", "Beschreibung"]
        dialog = SimpleEntryDialog(self, "Reparatur melden", fields)
        self.wait_window(dialog)
        if dialog.result:
            datum_raw, kosten_raw, kontakt_raw, beschreibung = dialog.result
            try:
                datum = parse_date(datum_raw)
            except ValueError:
                Messagebox.show_error("Ungültiges Datum", "Fehler")
                return
            try:
                kosten = float(kosten_raw or 0)
            except ValueError:
                Messagebox.show_error("Kosten ungültig", "Fehler")
                return
            kontakt_id = int(kontakt_raw) if kontakt_raw else None
            self.db.add_repair(
                produkt_id=self.produkt_id,
                datum=datum or date.today(),
                kosten=kosten,
                kontakt_id=kontakt_id,
                beschreibung=beschreibung,
            )
            self.refresh()


class MaintenanceDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, db: DatabaseManager, produkt_id: int) -> None:
        super().__init__(master)
        self.db = db
        self.produkt_id = produkt_id
        self.title("Wartungen")
        self.geometry("650x450")

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Wartung planen", command=self.add_maintenance, bootstyle="success").pack(side=LEFT)

        columns = [
            {"text": "Geplant"},
            {"text": "Typ"},
            {"text": "Durchgeführt"},
            {"text": "Beschreibung"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=15)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self.refresh()
        self.grab_set()

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_maintenance(self.produkt_id):
            self.table.insert_row(
                values=(
                    format_date(row["geplanter_termin"]),
                    row["wartungstyp"],
                    format_date(row["durchgefuehrt_am"]),
                    row["beschreibung"] or "",
                )
            )

    def add_maintenance(self) -> None:
        fields = [
            "Geplantes Datum (TT.MM.JJJJ)",
            "Typ",
            "Beschreibung",
            "Durchgeführt am (TT.MM.JJJJ)",
            "Durchgeführt von",
            "Bemerkung",
        ]
        dialog = SimpleEntryDialog(self, "Wartung", fields)
        self.wait_window(dialog)
        if dialog.result:
            geplanter_raw, typ, beschreibung, durch_raw, durch_von, bemerkung = dialog.result
            try:
                geplanter = parse_date(geplanter_raw)
            except ValueError:
                Messagebox.show_error("Ungültiges Datum", "Fehler")
                return
            try:
                durchgefuehrt = parse_date(durch_raw)
            except ValueError:
                Messagebox.show_error("Ungültiges Datum", "Fehler")
                return
            if not geplanter:
                Messagebox.show_error("Geplantes Datum erforderlich", "Fehler")
                return
            self.db.add_or_update_maintenance(
                wartung_id=None,
                produkt_id=self.produkt_id,
                geplanter_termin=geplanter,
                wartungstyp=typ or "STK",
                beschreibung=beschreibung,
                durchgefuehrt_am=durchgefuehrt,
                durchgefuehrt_von=durch_von,
                bemerkung=bemerkung,
            )
            self.refresh()


class MedizinprodukteApp(ttkb.Window):
    def __init__(self) -> None:
        super().__init__(themename="flatly")
        self.title("Medizinprodukte-Management System")
        self.geometry("1100x750")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.db = DatabaseManager()
        self.user: Optional[User] = None

        login = LoginDialog(self, self.db)
        self.wait_window(login)
        if not login.user:
            self.destroy()
            return
        self.user = login.user

        self.create_widgets()
        self.refresh_all()

    def create_widgets(self) -> None:
        welcome = ttkb.Label(
            self,
            text=f"Willkommen {self.user.full_name} ({self.user.role})",
            font=("Helvetica", 12),
        )
        welcome.pack(pady=10)

        self.notebook = ttkb.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=True)

        self.dashboard_view = DashboardView(self.notebook, self.db)
        self.notebook.add(self.dashboard_view, text="Dashboard")

        self.products_view = ProductsView(self.notebook, self.db)
        self.notebook.add(self.products_view, text="Produkte")

        self.vehicles_view = VehiclesView(self.notebook, self.db)
        self.notebook.add(self.vehicles_view, text="Fahrzeuge")

        self.materials_view = MaterialsView(self.notebook, self.db)
        self.notebook.add(self.materials_view, text="Material")

        self.master_view = MasterDataView(self.notebook, self.db)
        self.notebook.add(self.master_view, text="Stammdaten")

        self.notebook.bind("<<NotebookTabChanged>>", lambda _event: self.refresh_current())

    def refresh_current(self) -> None:
        current = self.notebook.select()
        widget = self.nametowidget(current)
        if hasattr(widget, "refresh"):
            widget.refresh()  # type: ignore[call-arg]

    def refresh_all(self) -> None:
        for view in [
            self.dashboard_view,
            self.products_view,
            self.vehicles_view,
            self.materials_view,
            self.master_view,
        ]:
            if hasattr(view, "refresh"):
                view.refresh()  # type: ignore[call-arg]

    def on_closing(self) -> None:
        self.db.close()
        self.destroy()


if __name__ == "__main__":
    app = MedizinprodukteApp()
    app.mainloop()
