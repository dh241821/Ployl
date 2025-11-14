"""Medizinprodukte-Management System GUI."""

from __future__ import annotations

import calendar
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import shutil
import sqlite3

import ttkbootstrap as ttkb
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, W
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.widgets.tableview import Tableview

from app.database import DatabaseManager, User

import tkinter as tk
from tkinter import filedialog, font as tkfont

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


DATE_FORMAT = "%d.%m.%Y"
REPAIR_STORAGE = Path("storage/reparaturen")
REPAIR_STORAGE.mkdir(parents=True, exist_ok=True)


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
        self.dark_mode = False

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
        frame = ttkb.Frame(master, style="KpiCard.TFrame")
        frame.configure(padding=18)
        ttkb.Label(frame, text=title, style="KpiTitle.TLabel").pack(anchor=W)
        value_label = ttkb.Label(frame, text="0", style="KpiValue.TLabel")
        value_label.pack(anchor=W, pady=(6, 0))
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

    def update_palette(self, dark_mode: bool) -> None:
        self.dark_mode = dark_mode
        background = "#111827" if dark_mode else "#f8f9fa"
        foreground = "#e2e8f0" if dark_mode else "#1f2937"
        self.figure.patch.set_facecolor(background)
        self.ax.set_facecolor(background)
        self.ax.tick_params(colors=foreground)
        self.ax.yaxis.label.set_color(foreground)
        self.ax.xaxis.label.set_color(foreground)
        self.ax.title.set_color(foreground)
        for spine in self.ax.spines.values():
            spine.set_color(foreground)
        self.canvas.draw_idle()


class ProductsView(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)

        ttkb.Button(toolbar, text="Neu", command=self.create_product, bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_product, bootstyle="secondary").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Ausscheiden", command=self.retire_product, bootstyle="danger").pack(side=LEFT)
        ttkb.Button(toolbar, text="Komponenten", command=self.open_components, bootstyle="info").pack(
            side=LEFT, padx=5
        )
        ttkb.Button(toolbar, text="Wartungen", command=self.open_maintenance, bootstyle="info").pack(
            side=LEFT
        )
        ttkb.Button(toolbar, text="Reparaturen", command=self.open_repairs, bootstyle="info").pack(
            side=LEFT, padx=5
        )
        ttkb.Button(toolbar, text="Export CSV", command=self.export_products, bootstyle="info").pack(side=LEFT, padx=5)
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

        self.hide_retired = ttkb.BooleanVar(value=True)
        ttkb.Checkbutton(
            toolbar,
            text="Ausgeschiedene ausblenden",
            variable=self.hide_retired,
            command=self.refresh,
            bootstyle="round-toggle",
        ).pack(side=LEFT, padx=(20, 0))

        columns = [
            {"text": "ID"},
            {"text": "Name"},
            {"text": "Typ"},
            {"text": "Modell"},
            {"text": "Seriennummer"},
            {"text": "Status"},
            {"text": "Standort"},
            {"text": "Fahrzeug"},
            {"text": "Lagerort"},
            {"text": "Interne Kennung"},
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
        hide_retired = self.hide_retired.get()
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
                        row["lagerort"],
                        row["interne_kennung"],
                    ],
                )
            ).lower()
            if query and query not in haystack:
                continue
            if status_filter and row["status"] != status_filter:
                continue
            if hide_retired and row["status"] == "ausgeschieden":
                continue
            self.table.insert_row(
                values=(
                    row["id"],
                    row["name"],
                    row["produkt_typ_name"] or row["typ"] or "",
                    row["produkt_modell_name"] or "",
                    row["seriennummer"],
                    row["status"],
                    row["standort_name"] or "",
                    row["fahrzeug_name"] or "",
                    row["lagerort"] or "",
                    row["interne_kennung"] or "",
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

    def open_components(self) -> None:
        self._open_product_tab("components")

    def open_maintenance(self) -> None:
        self._open_product_tab("maintenance")

    def open_repairs(self) -> None:
        self._open_product_tab("repairs")

    def _open_product_tab(self, tab_name: str) -> None:
        product_id = self.selected_product_id()
        if not product_id:
            return
        editor = ProductEditor(self, self.db, produkt_id=product_id, initial_tab=tab_name)
        self.wait_window(editor)
        if editor.saved:
            self.refresh()

    def retire_product(self) -> None:
        product_id = self.selected_product_id()
        if not product_id:
            return
        dialog = RetireProductDialog(self)
        self.wait_window(dialog)
        if not dialog.result:
            return
        datum, grund = dialog.result
        try:
            parsed_date = parse_date(datum)
        except ValueError:
            Messagebox.show_error("Ungültiges Datum für Ausscheidung", "Fehler")
            return
        if not parsed_date:
            parsed_date = date.today()
        self.db.mark_product_retired(product_id, parsed_date, grund)
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

    def export_lifecycle(self) -> None:
        product_id = self.selected_product_id()
        if not product_id:
            return
        product = self.db.get_product(product_id)
        default_name = None
        if product:
            today = date.today().isoformat()
            produkt_typ = (product["produkt_typ_name"] or product["typ"] or "Unbekannt").replace(" ", "-")
            modell = (product["produkt_modell_name"] or product["typ"] or "").replace(" ", "-")
            kennung = (product["interne_kennung"] or "").replace(" ", "-")
            parts = [today]
            if produkt_typ:
                parts.append(produkt_typ)
            if modell:
                parts.append(modell)
            if kennung:
                parts.append(kennung)
            default_name = "_".join(filter(None, parts)) + ".html"

        filepath = filedialog.asksaveasfilename(
            title="Produkt-Lebenslauf speichern",
            defaultextension=".html",
            filetypes=[("HTML", "*.html")],
            initialfile=default_name,
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
        self.locations = self.db.list_locations()
        self.vehicle_models = self.db.list_vehicle_models()
        self.vehicle_categories = self.db.list_vehicle_categories()

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Neu", command=self.create_vehicle, bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_vehicle, bootstyle="secondary").pack(side=LEFT, padx=5)

        filter_frame = ttkb.Frame(self)
        filter_frame.pack(fill=tk.X, padx=10)

        ttkb.Label(filter_frame, text="Standort").pack(side=LEFT)
        self.location_filter = ttkb.StringVar()
        location_values = ["Alle"] + [self._format_location(row) for row in self.locations]
        self.location_box = ttkb.Combobox(
            filter_frame,
            textvariable=self.location_filter,
            values=location_values,
            state="readonly",
            width=35,
        )
        self.location_box.pack(side=LEFT, padx=(5, 20))
        self.location_filter.set("Alle")

        ttkb.Label(filter_frame, text="Typ").pack(side=LEFT)
        self.type_filter = ttkb.StringVar()
        type_values = ["Alle"] + sorted({row["name"] for row in self.vehicle_models})
        self.type_box = ttkb.Combobox(
            filter_frame,
            textvariable=self.type_filter,
            values=type_values,
            state="readonly",
            width=25,
        )
        self.type_box.pack(side=LEFT, padx=(5, 20))
        self.type_filter.set("Alle")

        ttkb.Label(filter_frame, text="Kategorie").pack(side=LEFT)
        self.category_filter = ttkb.StringVar()
        category_values = ["Alle"] + [row["name"] for row in self.vehicle_categories]
        self.category_box = ttkb.Combobox(
            filter_frame,
            textvariable=self.category_filter,
            values=category_values,
            state="readonly",
            width=20,
        )
        self.category_box.pack(side=LEFT)
        self.category_filter.set("Alle")

        for variable in (self.location_filter, self.type_filter, self.category_filter):
            variable.trace_add("write", lambda *_: self.refresh())

        columns = [
            {"text": "ID"},
            {"text": "Funkkennung"},
            {"text": "Typ"},
            {"text": "Kategorie"},
            {"text": "Standort"},
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
        self.locations = self.db.list_locations()
        self.vehicle_models = self.db.list_vehicle_models()
        self.vehicle_categories = self.db.list_vehicle_categories()
        current_location = self.location_filter.get()
        current_type = self.type_filter.get()
        current_category = self.category_filter.get()
        location_values = ["Alle"] + [self._format_location_from_row(row) for row in self.locations]
        type_values = ["Alle"] + sorted({row["name"] for row in self.vehicle_models})
        category_values = ["Alle"] + [row["name"] for row in self.vehicle_categories]
        self.location_box.configure(values=location_values)
        self.type_box.configure(values=type_values)
        self.category_box.configure(values=category_values)
        if current_location not in location_values:
            self.location_filter.set("Alle")
        if current_type not in type_values:
            self.type_filter.set("Alle")
        if current_category not in category_values:
            self.category_filter.set("Alle")
        self.table.delete_rows()
        location_filter = self.location_filter.get()
        type_filter = self.type_filter.get()
        category_filter = self.category_filter.get()
        for row in self.db.list_vehicles():
            location_label = self._format_location(row)
            if location_filter != "Alle" and location_label != location_filter:
                continue
            vehicle_type = row["fahrzeug_typ_name"] or row["typ"] or ""
            if type_filter != "Alle" and vehicle_type != type_filter:
                continue
            vehicle_category = row["fahrzeug_kategorie_name"] or row["kategorie"] or ""
            if category_filter != "Alle" and vehicle_category != category_filter:
                continue
            self.table.insert_row(
                values=(
                    row["id"],
                    row["name"],
                    vehicle_type,
                    vehicle_category,
                    location_label,
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

    def _format_location(self, row: sqlite3.Row) -> str:
        if "standort_name" in row.keys() and row["standort_name"]:
            return row["standort_name"]
        standort_id = row["standort_id"] if "standort_id" in row.keys() else None
        if standort_id:
            for loc in self.locations:
                if loc["id"] == standort_id:
                    parts = [loc["bezirksstelle"], loc["ortsstelle"]]
                    label = " - ".join(filter(None, parts))
                    return label or f"Standort #{standort_id}"
        return ""


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
            {"text": "Bezeichnung"},
            {"text": "Kategorie"},
            {"text": "Lagerort"},
            {"text": "Ist"},
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
            lagerort = row["lagerort"] or ""
            category = row["kategorie_name"] if "kategorie_name" in row.keys() else ""
            self.table.insert_row(
                values=(
                    row["id"],
                    row["name"],
                    category,
                    lagerort,
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

        self.product_types_frame = ProductTypesFrame(notebook, db)
        notebook.add(self.product_types_frame, text="Produkttypen")

        self.product_models_frame = ProductModelsFrame(notebook, db)
        notebook.add(self.product_models_frame, text="Produktmodelle")

        self.component_types_frame = ComponentTypesFrame(notebook, db)
        notebook.add(self.component_types_frame, text="Komponententypen")

        self.repair_types_frame = RepairTypesFrame(notebook, db)
        notebook.add(self.repair_types_frame, text="Reparaturarten")

        self.upload_categories_frame = UploadCategoriesFrame(notebook, db)
        notebook.add(self.upload_categories_frame, text="Upload-Kategorien")

        self.material_names_frame = MaterialNamesFrame(notebook, db)
        notebook.add(self.material_names_frame, text="Materialbezeichnungen")

        self.vehicle_brands_frame = VehicleBrandsFrame(notebook, db)
        notebook.add(self.vehicle_brands_frame, text="Fahrzeugmarken")

        self.vehicle_models_frame = VehicleModelsFrame(notebook, db)
        notebook.add(self.vehicle_models_frame, text="Fahrzeugtypen")

        self.vehicle_categories_frame = VehicleCategoriesFrame(notebook, db)
        notebook.add(self.vehicle_categories_frame, text="Fahrzeugkategorien")

        self.users_frame = UsersFrame(notebook, db)
        notebook.add(self.users_frame, text="Benutzer")

    def refresh(self) -> None:
        self.categories_frame.refresh()
        self.locations_frame.refresh()
        self.contacts_frame.refresh()
        self.product_types_frame.refresh()
        self.product_models_frame.refresh()
        self.component_types_frame.refresh()
        self.repair_types_frame.refresh()
        self.upload_categories_frame.refresh()
        self.material_names_frame.refresh()
        self.vehicle_brands_frame.refresh()
        self.vehicle_models_frame.refresh()
        self.vehicle_categories_frame.refresh()
        self.users_frame.refresh()


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
        ttkb.Button(toolbar, text="Neuer Standort", command=self.add_location, bootstyle="success").pack(
            side=LEFT
        )
        ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_location, bootstyle="secondary").pack(
            side=LEFT, padx=5
        )
        ttkb.Button(toolbar, text="Löschen", command=self.delete_location, bootstyle="danger").pack(side=LEFT)

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

    def edit_location(self) -> None:
        location_id = self._selected_location_id()
        if not location_id:
            return
        row = self.db.get_location(location_id)
        if not row:
            Messagebox.show_error("Standort nicht gefunden", "Fehler")
            return
        fields = ["Land", "Bereich", "Bezirk", "Bezirksstelle", "Ortsstelle", "Beschreibung"]
        initial = [
            row["land"] or "",
            row["bereich"] or "",
            row["bezirk"] or "",
            row["bezirksstelle"] or "",
            row["ortsstelle"] or "",
            row["beschreibung"] or "",
        ]
        dialog = SimpleEntryDialog(self, "Standort bearbeiten", fields, initial)
        self.wait_window(dialog)
        if not dialog.result:
            return
        land, bereich, bezirk, bezirksstelle, ortsstelle, beschreibung = dialog.result
        self.db.update_location(
            location_id,
            land,
            bereich,
            bezirk,
            bezirksstelle,
            ortsstelle,
            beschreibung,
        )
        self.refresh()

    def delete_location(self) -> None:
        location_id = self._selected_location_id()
        if not location_id:
            return
        confirm = Messagebox.okcancel("Standort wirklich löschen?", "Bestätigung", alert=True)
        if confirm != "OK":
            return
        try:
            self.db.delete_location(location_id)
        except sqlite3.IntegrityError:
            Messagebox.show_error(
                "Standort wird noch verwendet und kann nicht gelöscht werden.",
                "Fehler",
            )
            return
        self.refresh()

    def _selected_location_id(self) -> Optional[int]:
        if not self.table.view.focus():
            Messagebox.show_info("Bitte Standort auswählen", "Hinweis")
            return None
        rows = self.table.get_rows("selected")
        if not rows:
            Messagebox.show_info("Bitte Standort auswählen", "Hinweis")
            return None
        return int(rows[0].values[0])


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


class SimpleLookupFrame(ttkb.Frame):
    def __init__(
        self,
        master: tk.Misc,
        db: DatabaseManager,
        *,
        fetch_fn: Callable[[], List[sqlite3.Row]],
        add_fn: Callable[[str], int],
        delete_fn: Callable[[int], None],
        title: str,
        column_key: str = "name",
        label: str = "Name",
    ) -> None:
        super().__init__(master)
        self.db = db
        self.fetch_fn = fetch_fn
        self.add_fn = add_fn
        self.delete_fn = delete_fn
        self.column_key = column_key
        self.label = label

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text=f"Neu", command=self.add_entry, bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Löschen", command=self.delete_entry, bootstyle="danger").pack(side=LEFT, padx=5)

        columns = [
            {"text": "ID"},
            {"text": label},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=20)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.fetch_fn():
            value = row[self.column_key] if self.column_key in row.keys() else ""
            self.table.insert_row(values=(row["id"], value))

    def selected_id(self) -> Optional[int]:
        rows = self.table.get_rows("selected")
        if not rows:
            Messagebox.show_info("Bitte einen Eintrag auswählen", "Hinweis")
            return None
        return int(rows[0].values[0])

    def add_entry(self) -> None:
        dialog = SimpleEntryDialog(self, f"Neuer Eintrag", [self.label])
        self.wait_window(dialog)
        if not dialog.result:
            return
        name = dialog.result[0].strip()
        if not name:
            Messagebox.show_warning(f"{self.label} darf nicht leer sein", "Hinweis")
            return
        try:
            self.add_fn(name)
        except sqlite3.IntegrityError as exc:
            Messagebox.show_error(str(exc), "Fehler")
            return
        self.refresh()

    def delete_entry(self) -> None:
        entry_id = self.selected_id()
        if not entry_id:
            return
        if Messagebox.okcancel("Soll der Eintrag wirklich gelöscht werden?", "Bestätigung"):
            try:
                self.delete_fn(entry_id)
            except sqlite3.IntegrityError as exc:
                Messagebox.show_error(str(exc), "Fehler")
                return
            self.refresh()


class ProductTypesFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_product_types,
            add_fn=db.add_product_type,
            delete_fn=db.delete_product_type,
            title="Produkttypen",
            column_key="name",
            label="Produkttyp",
        )


class ComponentTypesFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_component_types,
            add_fn=db.add_component_type,
            delete_fn=db.delete_component_type,
            title="Komponententypen",
            column_key="name",
            label="Komponententyp",
        )


class RepairTypesFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_repair_types,
            add_fn=db.add_repair_type,
            delete_fn=db.delete_repair_type,
            title="Reparaturarten",
            column_key="name",
            label="Reparaturart",
        )


class UploadCategoriesFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_upload_categories,
            add_fn=db.add_upload_category,
            delete_fn=db.delete_upload_category,
            title="Upload-Kategorien",
            column_key="name",
            label="Kategorie",
        )


class MaterialNamesFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_material_names,
            add_fn=db.add_material_name,
            delete_fn=db.delete_material_name,
            title="Materialbezeichnungen",
            column_key="name",
            label="Bezeichnung",
        )


class VehicleBrandsFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_vehicle_brands,
            add_fn=db.add_vehicle_brand,
            delete_fn=db.delete_vehicle_brand,
            title="Fahrzeugmarken",
            column_key="name",
            label="Marke",
        )


class VehicleCategoriesFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_vehicle_categories,
            add_fn=db.add_vehicle_category,
            delete_fn=db.delete_vehicle_category,
            title="Fahrzeugkategorien",
            column_key="name",
            label="Kategorie",
        )


class ProductModelsFrame(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db
        self.product_types: List[sqlite3.Row] = []

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Neu", command=self.add_model, bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Löschen", command=self.delete_model, bootstyle="danger").pack(side=LEFT, padx=5)

        columns = [
            {"text": "ID"},
            {"text": "Produkttyp"},
            {"text": "Modell"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=20)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def refresh(self) -> None:
        self.product_types = self.db.list_product_types()
        self.table.delete_rows()
        for row in self.db.list_product_models():
            type_name = row["typ_name"] or ""
            self.table.insert_row(values=(row["id"], type_name, row["name"]))

    def selected_id(self) -> Optional[int]:
        rows = self.table.get_rows("selected")
        if not rows:
            Messagebox.show_info("Bitte ein Modell auswählen", "Hinweis")
            return None
        return int(rows[0].values[0])

    def add_model(self) -> None:
        dialog = ProductModelDialog(self, self.product_types)
        self.wait_window(dialog)
        if not dialog.result:
            return
        typ_id, name = dialog.result
        try:
            self.db.add_product_model(typ_id, name)
        except sqlite3.IntegrityError as exc:
            Messagebox.show_error(str(exc), "Fehler")
            return
        self.refresh()

    def delete_model(self) -> None:
        model_id = self.selected_id()
        if not model_id:
            return
        if Messagebox.okcancel("Modell wirklich löschen?", "Bestätigung"):
            self.db.delete_product_model(model_id)
            self.refresh()


class VehicleModelsFrame(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db
        self.brands: List[sqlite3.Row] = []

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Neu", command=self.add_model, bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Löschen", command=self.delete_model, bootstyle="danger").pack(side=LEFT, padx=5)

        columns = [
            {"text": "ID"},
            {"text": "Marke"},
            {"text": "Modell"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=20)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def refresh(self) -> None:
        self.brands = self.db.list_vehicle_brands()
        self.table.delete_rows()
        for row in self.db.list_vehicle_models():
            brand = row["marke_name"] or ""
            self.table.insert_row(values=(row["id"], brand, row["name"]))

    def selected_id(self) -> Optional[int]:
        rows = self.table.get_rows("selected")
        if not rows:
            Messagebox.show_info("Bitte ein Modell auswählen", "Hinweis")
            return None
        return int(rows[0].values[0])

    def add_model(self) -> None:
        dialog = VehicleModelDialog(self, self.brands)
        self.wait_window(dialog)
        if not dialog.result:
            return
        brand_id, name = dialog.result
        try:
            self.db.add_vehicle_model(brand_id, name)
        except sqlite3.IntegrityError as exc:
            Messagebox.show_error(str(exc), "Fehler")
            return
        self.refresh()

    def delete_model(self) -> None:
        model_id = self.selected_id()
        if not model_id:
            return
        if Messagebox.okcancel("Modell wirklich löschen?", "Bestätigung"):
            self.db.delete_vehicle_model(model_id)
            self.refresh()


class UsersFrame(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Neu", command=self.add_user, bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_user, bootstyle="secondary").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Passwort setzen", command=self.reset_password, bootstyle="info").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Löschen", command=self.delete_user, bootstyle="danger").pack(side=LEFT, padx=5)

        columns = [
            {"text": "ID"},
            {"text": "Vorname"},
            {"text": "Nachname"},
            {"text": "Dienstnummer"},
            {"text": "Rolle"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=20)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_users():
            self.table.insert_row(
                values=(
                    row["id"],
                    row["vorname"] or "",
                    row["nachname"] or "",
                    row["dienstnummer"] or "",
                    row["role"],
                )
            )

    def selected_user(self) -> Optional[sqlite3.Row]:
        rows = self.table.get_rows("selected")
        if not rows:
            Messagebox.show_info("Bitte einen Benutzer auswählen", "Hinweis")
            return None
        user_id = int(rows[0].values[0])
        for row in self.db.list_users():
            if row["id"] == user_id:
                return row
        return None

    def add_user(self) -> None:
        dialog = UserDialog(self)
        self.wait_window(dialog)
        if not dialog.result:
            return
        vorname, nachname, dienstnummer, rolle = dialog.result
        try:
            self.db.add_or_update_user(
                benutzer_id=None,
                vorname=vorname,
                nachname=nachname,
                dienstnummer=dienstnummer,
                rolle=rolle,
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            Messagebox.show_error(str(exc), "Fehler")
            return
        Messagebox.show_info("Benutzer angelegt. Initiales Passwort entspricht der Dienstnummer.", "Hinweis")
        self.refresh()

    def edit_user(self) -> None:
        row = self.selected_user()
        if not row:
            return
        dialog = UserDialog(
            self,
            vorname=row["vorname"] or "",
            nachname=row["nachname"] or "",
            dienstnummer=row["dienstnummer"] or "",
            rolle=row["role"],
        )
        self.wait_window(dialog)
        if not dialog.result:
            return
        vorname, nachname, dienstnummer, rolle = dialog.result
        try:
            self.db.add_or_update_user(
                benutzer_id=row["id"],
                vorname=vorname,
                nachname=nachname,
                dienstnummer=dienstnummer,
                rolle=rolle,
            )
        except (ValueError, sqlite3.IntegrityError) as exc:
            Messagebox.show_error(str(exc), "Fehler")
            return
        self.refresh()

    def reset_password(self) -> None:
        row = self.selected_user()
        if not row:
            return
        dialog = SimpleEntryDialog(self, "Passwort setzen", ["Neues Passwort"])
        self.wait_window(dialog)
        if not dialog.result:
            return
        password = dialog.result[0].strip()
        if not password:
            Messagebox.show_warning("Passwort darf nicht leer sein", "Hinweis")
            return
        self.db.set_user_password(row["id"], password)
        Messagebox.show_info("Passwort aktualisiert", "Erfolg")

    def delete_user(self) -> None:
        row = self.selected_user()
        if not row:
            return
        if Messagebox.okcancel("Benutzer wirklich löschen?", "Bestätigung"):
            self.db.delete_user(row["id"])
            self.refresh()


class SimpleEntryDialog(ttkb.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        title: str,
        fields: List[str],
        initial: Optional[List[str]] = None,
    ) -> None:
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.result: Optional[List[str]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        self.variables: List[ttkb.StringVar] = []
        for index, label in enumerate(fields):
            ttkb.Label(container, text=label).grid(row=index, column=0, sticky=W, pady=5)
            initial_value = ""
            if initial and index < len(initial):
                initial_value = initial[index]
            var = ttkb.StringVar(value=initial_value)
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


class ProductModelDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, product_types: List[sqlite3.Row]) -> None:
        super().__init__(master)
        self.title("Produktmodell")
        self.resizable(False, False)
        self.result: Optional[Tuple[int, str]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text="Produkttyp").grid(row=0, column=0, sticky=W, pady=5)
        self.type_var = ttkb.StringVar()
        self.types = product_types
        ttkb.Combobox(
            container,
            textvariable=self.type_var,
            values=[row["name"] for row in product_types],
            state="readonly",
            width=30,
        ).grid(row=0, column=1, sticky=W)

        ttkb.Label(container, text="Modellname").grid(row=1, column=0, sticky=W, pady=5)
        self.name_var = ttkb.StringVar()
        ttkb.Entry(container, textvariable=self.name_var, width=32).grid(row=1, column=1, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.grab_set()

    def on_save(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            Messagebox.show_warning("Bitte Modellname eintragen", "Hinweis")
            return
        selected_type = self.type_var.get()
        typ_id = None
        for row in self.types:
            if row["name"] == selected_type:
                typ_id = row["id"]
                break
        if typ_id is None:
            Messagebox.show_warning("Bitte einen Produkttyp auswählen", "Hinweis")
            return
        self.result = (typ_id, name)
        self.destroy()


class VehicleModelDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, brands: List[sqlite3.Row]) -> None:
        super().__init__(master)
        self.title("Fahrzeugmodell")
        self.resizable(False, False)
        self.result: Optional[Tuple[Optional[int], str]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text="Marke").grid(row=0, column=0, sticky=W, pady=5)
        self.brand_var = ttkb.StringVar()
        self.brands = brands
        values = ["Keine"] + [row["name"] for row in brands]
        ttkb.Combobox(
            container,
            textvariable=self.brand_var,
            values=values,
            state="readonly",
            width=30,
        ).grid(row=0, column=1, sticky=W)
        self.brand_var.set(values[0])

        ttkb.Label(container, text="Modellname").grid(row=1, column=0, sticky=W, pady=5)
        self.name_var = ttkb.StringVar()
        ttkb.Entry(container, textvariable=self.name_var, width=32).grid(row=1, column=1, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.grab_set()

    def on_save(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            Messagebox.show_warning("Bitte Modellname eintragen", "Hinweis")
            return
        brand_value = self.brand_var.get()
        brand_id: Optional[int] = None
        if brand_value != "Keine":
            for row in self.brands:
                if row["name"] == brand_value:
                    brand_id = row["id"]
                    break
        self.result = (brand_id, name)
        self.destroy()


class UserDialog(ttkb.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        vorname: str = "",
        nachname: str = "",
        dienstnummer: str = "",
        rolle: str = "benutzer",
    ) -> None:
        super().__init__(master)
        self.title("Benutzer")
        self.resizable(False, False)
        self.result: Optional[Tuple[str, str, str, str]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text="Vorname").grid(row=0, column=0, sticky=W, pady=5)
        self.vorname_var = ttkb.StringVar(value=vorname)
        ttkb.Entry(container, textvariable=self.vorname_var, width=30).grid(row=0, column=1, sticky=W)

        ttkb.Label(container, text="Nachname").grid(row=1, column=0, sticky=W, pady=5)
        self.nachname_var = ttkb.StringVar(value=nachname)
        ttkb.Entry(container, textvariable=self.nachname_var, width=30).grid(row=1, column=1, sticky=W)

        ttkb.Label(container, text="Dienstnummer").grid(row=2, column=0, sticky=W, pady=5)
        self.dienstnummer_var = ttkb.StringVar(value=dienstnummer)
        ttkb.Entry(container, textvariable=self.dienstnummer_var, width=30).grid(row=2, column=1, sticky=W)

        ttkb.Label(container, text="Rolle").grid(row=3, column=0, sticky=W, pady=5)
        self.rolle_var = ttkb.StringVar(value=rolle)
        ttkb.Combobox(
            container,
            textvariable=self.rolle_var,
            values=["admin", "benutzer"],
            state="readonly",
            width=28,
        ).grid(row=3, column=1, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=4, column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.grab_set()

    def on_save(self) -> None:
        vorname = self.vorname_var.get().strip()
        nachname = self.nachname_var.get().strip()
        dienstnummer = self.dienstnummer_var.get().strip()
        if not vorname or not nachname or not dienstnummer:
            Messagebox.show_warning("Bitte alle Felder ausfüllen", "Hinweis")
            return
        rolle = self.rolle_var.get() or "benutzer"
        self.result = (vorname, nachname, dienstnummer, rolle)
        self.destroy()


class RetireProductDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title("Produkt ausscheiden")
        self.resizable(False, False)
        self.result: Optional[Tuple[str, str]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text="Datum (TT.MM.JJJJ)").grid(row=0, column=0, sticky=W, pady=5)
        self.date_var = ttkb.StringVar(value=date.today().strftime(DATE_FORMAT))
        ttkb.Entry(container, textvariable=self.date_var, width=25).grid(row=0, column=1, sticky=W)

        ttkb.Label(container, text="Grund").grid(row=1, column=0, sticky=W, pady=5)
        self.reason_var = ttkb.StringVar()
        ttkb.Entry(container, textvariable=self.reason_var, width=40).grid(row=1, column=1, sticky=W)

        ttkb.Button(container, text="Speichern", command=self.on_save, bootstyle="success").grid(
            row=2, column=0, pady=(20, 0)
        )
        ttkb.Button(container, text="Abbrechen", command=self.destroy, bootstyle="secondary").grid(
            row=2, column=1, pady=(20, 0), padx=5, sticky=W
        )

        self.grab_set()

    def on_save(self) -> None:
        grund = self.reason_var.get().strip()
        if not grund:
            Messagebox.show_warning("Bitte einen Grund angeben", "Hinweis")
            return
        self.result = (self.date_var.get(), grund)
        self.destroy()


class PersonalizationDialog(ttkb.Toplevel):
    def __init__(
        self,
        master: MedizinprodukteApp,
        *,
        current_theme: str,
        font_scale: float,
        show_welcome: bool,
    ) -> None:
        super().__init__(master)
        self.title("Personalisierung")
        self.resizable(False, False)
        self.result: Optional[Tuple[str, float, bool]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        available_themes = [
            theme
            for theme in ["flatly", "cosmo", "minty", "darkly", "cyborg", "solar"]
            if theme in master.style.theme_names()
        ]
        if current_theme not in available_themes:
            available_themes.insert(0, current_theme)

        ttkb.Label(container, text="Design-Thema").grid(row=0, column=0, sticky=W, pady=5)
        self.theme_var = ttkb.StringVar(value=current_theme)
        ttkb.Combobox(
            container,
            textvariable=self.theme_var,
            values=available_themes,
            state="readonly",
            width=25,
        ).grid(row=0, column=1, sticky=W)

        ttkb.Label(container, text="Schriftgröße").grid(row=1, column=0, sticky=W, pady=5)
        self.scale_var = ttkb.DoubleVar(value=font_scale)
        ttkb.Spinbox(
            container,
            textvariable=self.scale_var,
            from_=1.0,
            to=3.0,
            increment=0.1,
            width=10,
        ).grid(row=1, column=1, sticky=W)
        ttkb.Label(
            container,
            text="(1.0 = Standardgröße, 2.0 = extra groß)",
            bootstyle="secondary",
        ).grid(row=2, column=0, columnspan=2, sticky=W)

        self.info_var = ttkb.BooleanVar(value=show_welcome)
        ttkb.Checkbutton(
            container,
            text="Willkommensnachricht anzeigen",
            variable=self.info_var,
            bootstyle="round-toggle",
        ).grid(row=3, column=0, columnspan=2, sticky=W, pady=(10, 0))

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=4, column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.grab_set()

    def on_save(self) -> None:
        try:
            scale = float(self.scale_var.get())
        except (tk.TclError, ValueError):
            Messagebox.show_error("Ungültiger Skalierungswert", "Fehler")
            return
        theme = self.theme_var.get()
        self.result = (theme, scale, self.info_var.get())
        self.destroy()


class ProductEditor(ttkb.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        db: DatabaseManager,
        produkt_id: Optional[int] = None,
        *,
        initial_tab: str = "details",
    ) -> None:
        super().__init__(master)
        self.db = db
        self.produkt_id = produkt_id
        self.saved = False
        self.initial_tab = initial_tab
        self.title("Produkt bearbeiten" if produkt_id else "Neues Produkt")
        self.geometry("720x650")

        self.categories = db.list_categories("produkt")
        self.product_types = db.list_product_types()
        self.product_models = db.list_product_models()
        self.locations = db.list_locations()
        self.vehicles = db.list_vehicles()
        self.component_types = db.list_component_types()
        self.repair_types = db.list_repair_types()
        self.upload_categories = db.list_upload_categories()

        self.model_index: Dict[int, List[Tuple[int, str]]] = {}
        for model in self.product_models:
            self.model_index.setdefault(model["typ_id"], []).append((model["id"], model["name"]))

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        self.notebook = ttkb.Notebook(container)
        self.notebook.pack(fill=BOTH, expand=True)

        self.details_frame = ttkb.Frame(self.notebook)
        self.notebook.add(self.details_frame, text="Produkt")

        self._build_details(self.details_frame)

        self.components_tab = ComponentsTab(
            self.notebook, self.db, self.produkt_id, self.component_types
        )
        self.notebook.add(self.components_tab, text="Komponenten")

        self.maintenance_tab = MaintenanceTab(self.notebook, self.db, self.produkt_id)
        self.notebook.add(self.maintenance_tab, text="Wartungen")

        self.repairs_tab = RepairsTab(
            self.notebook,
            self.db,
            self.produkt_id,
            self.repair_types,
            self.upload_categories,
        )
        self.notebook.add(self.repairs_tab, text="Reparaturen")

        self._tabs = {
            "details": self.details_frame,
            "components": self.components_tab,
            "maintenance": self.maintenance_tab,
            "repairs": self.repairs_tab,
        }
        self._select_initial_tab()

        button_frame = ttkb.Frame(container)
        button_frame.pack(fill=tk.X, pady=(12, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.save, bootstyle="success").pack(
            side=LEFT, padx=5
        )
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(
            side=LEFT, padx=5
        )

        if produkt_id:
            self.load_data()

        self.grab_set()

    def _select_initial_tab(self) -> None:
        target = self._tabs.get(self.initial_tab, self.details_frame)
        self.notebook.select(target)

    def _build_details(self, parent: ttkb.Frame) -> None:
        self.name_var = ttkb.StringVar()
        self.typ_var = ttkb.StringVar()
        self.modell_var = ttkb.StringVar()
        self.seriennummer_var = ttkb.StringVar()
        self.hersteller_var = ttkb.StringVar()
        self.anschaffungsdatum_var = ttkb.StringVar()
        self.kategorie_var = ttkb.StringVar()
        self.standort_var = ttkb.StringVar()
        self.fahrzeug_var = ttkb.StringVar()
        self.lagerort_var = ttkb.StringVar()
        self.status_var = ttkb.StringVar(value="im_dienst")
        self.interne_kennung_var = ttkb.StringVar()
        self.information_var = ttkb.StringVar()

        self.stk_active = ttkb.BooleanVar(value=True)
        self.stk_interval_var = ttkb.StringVar(value="12")
        self.stk_last_var = ttkb.StringVar()
        self.stk_next_var = ttkb.StringVar()

        self.mtk_active = ttkb.BooleanVar(value=True)
        self.mtk_interval_var = ttkb.StringVar(value="24")
        self.mtk_last_var = ttkb.StringVar()
        self.mtk_next_var = ttkb.StringVar()

        info_frame = ttkb.Labelframe(parent, text="Produktspezifisch")
        info_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)

        ttkb.Label(info_frame, text="Bezeichnung*").grid(row=0, column=0, sticky=W, pady=4)
        ttkb.Entry(info_frame, textvariable=self.name_var, width=40).grid(row=0, column=1, sticky=W)

        ttkb.Label(info_frame, text="Produkttyp").grid(row=1, column=0, sticky=W, pady=4)
        self.typ_box = ttkb.Combobox(
            info_frame,
            textvariable=self.typ_var,
            values=[row["name"] for row in self.product_types],
            width=37,
            state="readonly",
        )
        self.typ_box.grid(row=1, column=1, sticky=W)
        self.typ_box.bind("<<ComboboxSelected>>", lambda _event: self._update_model_choices())

        ttkb.Label(info_frame, text="Modell").grid(row=2, column=0, sticky=W, pady=4)
        self.modell_box = ttkb.Combobox(info_frame, textvariable=self.modell_var, width=37, state="readonly")
        self.modell_box.grid(row=2, column=1, sticky=W)

        ttkb.Label(info_frame, text="Hersteller").grid(row=3, column=0, sticky=W, pady=4)
        ttkb.Entry(info_frame, textvariable=self.hersteller_var, width=40).grid(row=3, column=1, sticky=W)

        ttkb.Label(info_frame, text="Anschaffungsdatum (TT.MM.JJJJ)").grid(row=4, column=0, sticky=W, pady=4)
        ttkb.Entry(info_frame, textvariable=self.anschaffungsdatum_var, width=40).grid(
            row=4, column=1, sticky=W
        )

        ttkb.Label(info_frame, text="Kategorie").grid(row=5, column=0, sticky=W, pady=4)
        self.kategorie_box = ttkb.Combobox(
            info_frame,
            textvariable=self.kategorie_var,
            values=[row["name"] for row in self.categories],
            width=37,
            state="readonly",
        )
        self.kategorie_box.grid(row=5, column=1, sticky=W)

        compliance_frame = ttkb.Labelframe(parent, text="Kontrollen")
        compliance_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)

        stk_frame = ttkb.Frame(compliance_frame)
        stk_frame.pack(fill=tk.X, padx=5, pady=5)
        ttkb.Checkbutton(
            stk_frame,
            text="STK erforderlich",
            variable=self.stk_active,
            command=self._update_stk_state,
            bootstyle="round-toggle",
        ).grid(row=0, column=0, sticky=W)
        ttkb.Label(stk_frame, text="Intervall (Monate)").grid(row=1, column=0, sticky=W, pady=2)
        self.stk_interval_entry = ttkb.Entry(stk_frame, textvariable=self.stk_interval_var, width=10)
        self.stk_interval_entry.grid(row=1, column=1, sticky=W)
        ttkb.Label(stk_frame, text="Letzte STK").grid(row=0, column=1, padx=(20, 5), sticky=W)
        self.stk_last_entry = ttkb.Entry(stk_frame, textvariable=self.stk_last_var, width=18)
        self.stk_last_entry.grid(row=0, column=2, sticky=W)
        ttkb.Label(stk_frame, text="Nächste STK").grid(row=0, column=3, padx=(20, 5), sticky=W)
        self.stk_next_entry = ttkb.Entry(stk_frame, textvariable=self.stk_next_var, width=18)
        self.stk_next_entry.grid(row=0, column=4, sticky=W)
        ttkb.Button(
            stk_frame,
            text="Berechnen",
            command=lambda: self._calculate_next_due(
                self.stk_last_var, self.stk_interval_var, self.stk_next_var
            ),
            bootstyle="secondary",
        ).grid(row=1, column=4, padx=(10, 0), sticky=W)

        mtk_frame = ttkb.Frame(compliance_frame)
        mtk_frame.pack(fill=tk.X, padx=5, pady=5)
        ttkb.Checkbutton(
            mtk_frame,
            text="MTK erforderlich",
            variable=self.mtk_active,
            command=self._update_mtk_state,
            bootstyle="round-toggle",
        ).grid(row=0, column=0, sticky=W)
        ttkb.Label(mtk_frame, text="Intervall (Monate)").grid(row=1, column=0, sticky=W, pady=2)
        self.mtk_interval_entry = ttkb.Entry(mtk_frame, textvariable=self.mtk_interval_var, width=10)
        self.mtk_interval_entry.grid(row=1, column=1, sticky=W)
        ttkb.Label(mtk_frame, text="Letzte MTK").grid(row=0, column=1, padx=(20, 5), sticky=W)
        self.mtk_last_entry = ttkb.Entry(mtk_frame, textvariable=self.mtk_last_var, width=18)
        self.mtk_last_entry.grid(row=0, column=2, sticky=W)
        ttkb.Label(mtk_frame, text="Nächste MTK").grid(row=0, column=3, padx=(20, 5), sticky=W)
        self.mtk_next_entry = ttkb.Entry(mtk_frame, textvariable=self.mtk_next_var, width=18)
        self.mtk_next_entry.grid(row=0, column=4, sticky=W)
        ttkb.Button(
            mtk_frame,
            text="Berechnen",
            command=lambda: self._calculate_next_due(
                self.mtk_last_var, self.mtk_interval_var, self.mtk_next_var
            ),
            bootstyle="secondary",
        ).grid(row=1, column=4, padx=(10, 0), sticky=W)

        assignment_frame = ttkb.Labelframe(parent, text="Zuordnung & Hinweise")
        assignment_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)

        ttkb.Label(assignment_frame, text="Standort*").grid(row=0, column=0, sticky=W, pady=4)
        self.standort_box = ttkb.Combobox(
            assignment_frame,
            textvariable=self.standort_var,
            values=[self._format_location(row) for row in self.locations],
            width=45,
            state="readonly",
        )
        self.standort_box.grid(row=0, column=1, sticky=W)

        ttkb.Label(assignment_frame, text="Fahrzeug (Funkkennung)").grid(row=1, column=0, sticky=W, pady=4)
        self.fahrzeug_box = ttkb.Combobox(
            assignment_frame,
            textvariable=self.fahrzeug_var,
            values=[self._format_vehicle(row) for row in self.vehicles],
            width=45,
            state="readonly",
        )
        self.fahrzeug_box.grid(row=1, column=1, sticky=W)

        ttkb.Label(assignment_frame, text="Lagerort").grid(row=2, column=0, sticky=W, pady=4)
        ttkb.Entry(assignment_frame, textvariable=self.lagerort_var, width=48).grid(
            row=2, column=1, sticky=W
        )

        ttkb.Label(assignment_frame, text="Status").grid(row=3, column=0, sticky=W, pady=4)
        self.status_box = ttkb.Combobox(
            assignment_frame,
            textvariable=self.status_var,
            values=["im_dienst", "in_reparatur", "ausgeschieden"],
            width=20,
            state="readonly",
        )
        self.status_box.grid(row=3, column=1, sticky=W)

        ttkb.Label(assignment_frame, text="Interne Kennung").grid(row=4, column=0, sticky=W, pady=4)
        ttkb.Entry(assignment_frame, textvariable=self.interne_kennung_var, width=48).grid(
            row=4, column=1, sticky=W
        )

        ttkb.Label(assignment_frame, text="Informationstext").grid(row=5, column=0, sticky=ttkb.NW, pady=4)
        self.info_text = tk.Text(assignment_frame, height=4, width=45, wrap="word")
        self.info_text.grid(row=5, column=1, sticky=W)

        self._update_model_choices()
        self._update_stk_state()
        self._update_mtk_state()

    def _format_location(self, row: sqlite3.Row) -> str:
        parts = [row["bezirksstelle"], row["ortsstelle"]]
        label = " - ".join(filter(None, parts)) or f"Standort #{row['id']}"
        return f"{label} (#{row['id']})"

    def _format_vehicle(self, row: sqlite3.Row) -> str:
        if not row:
            return ""
        label = row["name"]
        if row.get("kennzeichen"):
            label += f" [{row['kennzeichen']}]"
        return f"{label} (#{row['id']})"

    def _update_model_choices(self) -> None:
        selected_type = self.typ_var.get()
        typ_id = None
        for row in self.product_types:
            if row["name"] == selected_type:
                typ_id = row["id"]
                break
        options = self.model_index.get(typ_id or -1, [])
        self.modell_box.configure(values=[label for _, label in options])
        if options:
            if self.modell_var.get() not in [label for _, label in options]:
                self.modell_var.set(options[0][1])
        else:
            self.modell_var.set("")

    def _update_stk_state(self) -> None:
        state = tk.NORMAL if self.stk_active.get() else tk.DISABLED
        for widget in [self.stk_interval_entry, self.stk_last_entry, self.stk_next_entry]:
            widget.configure(state=state)

    def _update_mtk_state(self) -> None:
        state = tk.NORMAL if self.mtk_active.get() else tk.DISABLED
        for widget in [self.mtk_interval_entry, self.mtk_last_entry, self.mtk_next_entry]:
            widget.configure(state=state)

    def _calculate_next_due(
        self,
        last_var: ttkb.StringVar,
        interval_var: ttkb.StringVar,
        target_var: ttkb.StringVar,
    ) -> None:
        try:
            last_date = parse_date(last_var.get()) if last_var.get().strip() else date.today()
        except ValueError:
            Messagebox.show_error("Ungültiges Datum", "Fehler")
            return
        try:
            interval = int(interval_var.get())
        except ValueError:
            Messagebox.show_error("Intervall muss eine Zahl sein", "Fehler")
            return
        if interval <= 0:
            Messagebox.show_error("Intervall muss größer 0 sein", "Fehler")
            return
        month = last_date.month - 1 + interval
        year = last_date.year + month // 12
        month = month % 12 + 1
        day = min(last_date.day, calendar.monthrange(year, month)[1])
        target_var.set(date(year, month, day).strftime(DATE_FORMAT))

    def _resolve_option(self, value: str, options: Iterable[Tuple[int, str]]) -> Optional[int]:
        for option_id, label in options:
            if label == value:
                return option_id
        return None

    def _resolve_location(self, value: str) -> Optional[int]:
        for row in self.locations:
            if self._format_location(row) == value:
                return row["id"]
        return None

    def _resolve_vehicle(self, value: str) -> Optional[int]:
        for row in self.vehicles:
            if self._format_vehicle(row) == value:
                return row["id"]
        return None

    def load_data(self) -> None:
        if self.produkt_id is None:
            return
        product = self.db.get_product(self.produkt_id)
        if not product:
            Messagebox.show_error("Produkt nicht gefunden", "Fehler")
            self.destroy()
            return
        self.name_var.set(product["name"] or "")
        self.typ_var.set(product["produkt_typ_name"] or product["typ"] or "")
        self._update_model_choices()
        if product["produkt_modell_name"]:
            self.modell_var.set(product["produkt_modell_name"])
        self.seriennummer_var.set(product["seriennummer"] or "")
        self.hersteller_var.set(product["hersteller"] or "")
        self.anschaffungsdatum_var.set(format_date(product["anschaffungsdatum"]))
        if product["kategorie_name"]:
            self.kategorie_var.set(product["kategorie_name"])
        if product["standort_id"]:
            for row in self.locations:
                if row["id"] == product["standort_id"]:
                    self.standort_var.set(self._format_location(row))
                    break
        if product["fahrzeug_id"]:
            for row in self.vehicles:
                if row["id"] == product["fahrzeug_id"]:
                    self.fahrzeug_var.set(self._format_vehicle(row))
                    break
        self.lagerort_var.set(product["lagerort"] or "")
        self.status_var.set(product["status"] or "im_dienst")
        self.interne_kennung_var.set(product["interne_kennung"] or "")
        self.info_text.delete("1.0", tk.END)
        self.info_text.insert(tk.END, product["informationstext"] or "")

        self.stk_active.set(bool(product["stk_aktiv"]))
        self.stk_interval_var.set(str(product["stk_intervall"] or ""))
        self.stk_last_var.set(format_date(product["letzte_stk"]))
        self.stk_next_var.set(format_date(product["naechste_stk"]))
        self.mtk_active.set(bool(product["mtk_aktiv"]))
        self.mtk_interval_var.set(str(product["mtk_intervall"] or ""))
        self.mtk_last_var.set(format_date(product["letzte_mtk"]))
        self.mtk_next_var.set(format_date(product["naechste_mtk"]))

        self._update_stk_state()
        self._update_mtk_state()

        self.components_tab.set_product_id(self.produkt_id)
        self.maintenance_tab.set_product_id(self.produkt_id)
        self.repairs_tab.set_product_id(self.produkt_id)

    def save(self) -> None:
        if not self.name_var.get().strip():
            Messagebox.show_error("Bezeichnung ist erforderlich", "Fehler")
            return
        if not self.seriennummer_var.get().strip():
            Messagebox.show_error("Seriennummer ist erforderlich", "Fehler")
            return

        try:
            anschaffungsdatum = parse_date(self.anschaffungsdatum_var.get())
        except ValueError:
            Messagebox.show_error("Ungültiges Anschaffungsdatum", "Fehler")
            return

        try:
            stk_intervall = int(self.stk_interval_var.get() or 0)
        except ValueError:
            Messagebox.show_error("STK-Intervall muss eine Zahl sein", "Fehler")
            return
        try:
            mtk_intervall = int(self.mtk_interval_var.get() or 0)
        except ValueError:
            Messagebox.show_error("MTK-Intervall muss eine Zahl sein", "Fehler")
            return

        standort_id = self._resolve_location(self.standort_var.get())
        if not standort_id:
            Messagebox.show_error("Bitte einen Standort auswählen", "Fehler")
            return

        fahrzeug_id = self._resolve_vehicle(self.fahrzeug_var.get())
        lagerort = self.lagerort_var.get().strip()
        if not fahrzeug_id and not lagerort:
            Messagebox.show_error(
                "Produkt muss einem Fahrzeug oder einem Lagerort zugeordnet sein", "Fehler"
            )
            return

        try:
            letzte_stk = parse_date(self.stk_last_var.get()) if self.stk_last_var.get().strip() else None
        except ValueError:
            Messagebox.show_error("Ungültiges Datum für letzte STK", "Fehler")
            return
        try:
            naechste_stk = (
                parse_date(self.stk_next_var.get()) if self.stk_next_var.get().strip() else None
            )
        except ValueError:
            Messagebox.show_error("Ungültiges Datum für nächste STK", "Fehler")
            return

        try:
            letzte_mtk = parse_date(self.mtk_last_var.get()) if self.mtk_last_var.get().strip() else None
        except ValueError:
            Messagebox.show_error("Ungültiges Datum für letzte MTK", "Fehler")
            return
        try:
            naechste_mtk = (
                parse_date(self.mtk_next_var.get()) if self.mtk_next_var.get().strip() else None
            )
        except ValueError:
            Messagebox.show_error("Ungültiges Datum für nächste MTK", "Fehler")
            return

        if self.stk_active.get() and not naechste_stk and letzte_stk and stk_intervall > 0:
            self._calculate_next_due(self.stk_last_var, self.stk_interval_var, self.stk_next_var)
            naechste_stk = parse_date(self.stk_next_var.get())
        if self.mtk_active.get() and not naechste_mtk and letzte_mtk and mtk_intervall > 0:
            self._calculate_next_due(self.mtk_last_var, self.mtk_interval_var, self.mtk_next_var)
            naechste_mtk = parse_date(self.mtk_next_var.get())

        kategorie_id = None
        for row in self.categories:
            if row["name"] == self.kategorie_var.get():
                kategorie_id = row["id"]
                break

        produkt_typ_id = None
        for row in self.product_types:
            if row["name"] == self.typ_var.get():
                produkt_typ_id = row["id"]
                break

        produkt_modell_id = None
        if produkt_typ_id:
            for model_id, label in self.model_index.get(produkt_typ_id, []):
                if label == self.modell_var.get():
                    produkt_modell_id = model_id
                    break

        informationstext = self.info_text.get("1.0", tk.END).strip()

        try:
            produkt_id = self.db.add_or_update_product(
                produkt_id=self.produkt_id,
                name=self.name_var.get(),
                typ=self.typ_var.get(),
                seriennummer=self.seriennummer_var.get(),
                hersteller=self.hersteller_var.get(),
                anschaffungsdatum=anschaffungsdatum,
                kategorie_id=kategorie_id,
                standort_id=standort_id,
                fahrzeug_id=fahrzeug_id,
                status=self.status_var.get() or "im_dienst",
                interne_kennung=self.interne_kennung_var.get(),
                stk_intervall=stk_intervall,
                mtk_intervall=mtk_intervall,
                stk_aktiv=self.stk_active.get(),
                mtk_aktiv=self.mtk_active.get(),
                letzte_stk=letzte_stk,
                letzte_mtk=letzte_mtk,
                naechste_stk=naechste_stk,
                naechste_mtk=naechste_mtk,
                lagerort=lagerort,
                produkt_typ_id=produkt_typ_id,
                produkt_modell_id=produkt_modell_id,
                informationstext=informationstext,
            )
        except Exception as exc:  # pragma: no cover
            Messagebox.show_error(str(exc), "Fehler")
            return

        self.produkt_id = produkt_id
        self.saved = True
        Messagebox.show_info("Produkt gespeichert", "Erfolg")
        self.components_tab.set_product_id(self.produkt_id)
        self.maintenance_tab.set_product_id(self.produkt_id)
        self.repairs_tab.set_product_id(self.produkt_id)
        self.destroy()


class ComponentsTab(ttkb.Frame):
    def __init__(
        self,
        master: tk.Misc,
        db: DatabaseManager,
        produkt_id: Optional[int],
        component_types: List[sqlite3.Row],
    ) -> None:
        super().__init__(master)
        self.db = db
        self.produkt_id = produkt_id
        self.component_types = component_types
        self.component_cache: Dict[int, sqlite3.Row] = {}

        self.toolbar = ttkb.Frame(self)
        self.toolbar.pack(fill=tk.X, padx=10, pady=10)

        self.add_btn = ttkb.Button(
            self.toolbar, text="Komponente hinzufügen", command=self.add_component, bootstyle="success"
        )
        self.add_btn.pack(side=LEFT)
        self.edit_btn = ttkb.Button(
            self.toolbar, text="Bearbeiten", command=self.edit_component, bootstyle="secondary"
        )
        self.edit_btn.pack(side=LEFT, padx=5)
        self.delete_btn = ttkb.Button(
            self.toolbar, text="Entfernen", command=self.delete_component, bootstyle="danger"
        )
        self.delete_btn.pack(side=LEFT)

        columns = [
            {"text": "ID"},
            {"text": "Bezeichnung"},
            {"text": "Typ"},
            {"text": "Seriennummer"},
            {"text": "Bemerkung"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=12)
        self.table.bind("<Double-1>", lambda _event: self.edit_component())

        self.placeholder = ttkb.Label(
            self,
            text="Bitte Produkt speichern, um Komponenten zu verwalten.",
            bootstyle="secondary",
        )

        self.set_product_id(produkt_id)

    def set_product_id(self, produkt_id: Optional[int]) -> None:
        self.produkt_id = produkt_id
        self._update_state()

    def _update_state(self) -> None:
        enabled = bool(self.produkt_id)
        state = tk.NORMAL if enabled else tk.DISABLED
        for button in (self.add_btn, self.edit_btn, self.delete_btn):
            button.configure(state=state)
        if enabled:
            self.placeholder.pack_forget()
            self.table.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
            self.refresh()
        else:
            self.table.pack_forget()
            self.placeholder.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def refresh(self) -> None:
        if not self.produkt_id:
            return
        self.table.delete_rows()
        self.component_cache = {}
        for row in self.db.list_components(self.produkt_id):
            self.component_cache[int(row["id"])] = row
            self.table.insert_row(
                values=(
                    row["id"],
                    row["name"],
                    row["komponententyp_name"] or "",
                    row["seriennummer"] or "",
                    row["bemerkung"] or "",
                )
            )

    def selected_component_id(self) -> Optional[int]:
        rows = self.table.get_rows("selected")
        if not rows:
            Messagebox.show_info("Bitte Komponente auswählen", "Hinweis")
            return None
        return int(rows[0].values[0])

    def add_component(self) -> None:
        if not self.produkt_id:
            return
        dialog = ComponentFormDialog(self, "Komponente hinzufügen", self.component_types)
        self.wait_window(dialog)
        if not dialog.result:
            return
        data = dialog.result
        self.db.add_or_update_component(
            komponent_id=None,
            produkt_id=self.produkt_id,
            name=data["name"],
            hersteller=data["hersteller"],
            seriennummer=data["seriennummer"],
            anschaffungsdatum=data["anschaffungsdatum"],
            bemerkung=data["bemerkung"],
            komponententyp_id=data["komponententyp_id"],
        )
        self.refresh()

    def edit_component(self) -> None:
        component_id = self.selected_component_id()
        if not component_id:
            return
        row = self.component_cache.get(component_id)
        if not row:
            return
        dialog = ComponentFormDialog(self, "Komponente bearbeiten", self.component_types, row)
        self.wait_window(dialog)
        if not dialog.result:
            return
        data = dialog.result
        self.db.add_or_update_component(
            komponent_id=component_id,
            produkt_id=row["produkt_id"],
            name=data["name"],
            hersteller=data["hersteller"],
            seriennummer=data["seriennummer"],
            anschaffungsdatum=data["anschaffungsdatum"],
            bemerkung=data["bemerkung"],
            komponententyp_id=data["komponententyp_id"],
        )
        self.refresh()

    def delete_component(self) -> None:
        component_id = self.selected_component_id()
        if not component_id:
            return
        if Messagebox.okcancel("Komponente wirklich entfernen?", "Bestätigung", alert=True) != "OK":
            return
        self.db.delete_component(component_id)
        self.refresh()


class ComponentFormDialog(ttkb.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        title: str,
        component_types: List[sqlite3.Row],
        data: Optional[sqlite3.Row] = None,
    ) -> None:
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.component_types = component_types
        self.result: Optional[Dict[str, Any]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        self.name_var = ttkb.StringVar(value=(data["name"] if data else ""))
        self.hersteller_var = ttkb.StringVar(value=(data["hersteller"] if data else ""))
        self.seriennummer_var = ttkb.StringVar(value=(data["seriennummer"] if data else ""))
        self.anschaffungsdatum_var = ttkb.StringVar(value=format_date(data["anschaffungsdatum"]) if data else "")
        self.bemerkung_var = ttkb.StringVar(value=(data["bemerkung"] if data else ""))
        initial_type = ""
        if data and data["komponententyp_id"]:
            for row in component_types:
                if row["id"] == data["komponententyp_id"]:
                    initial_type = row["name"]
                    break
        self.type_var = ttkb.StringVar(value=initial_type)

        ttkb.Label(container, text="Bezeichnung*").grid(row=0, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.name_var, width=40).grid(row=0, column=1, sticky=W)

        ttkb.Label(container, text="Typ").grid(row=1, column=0, sticky=W, pady=5)
        self.type_box = ttkb.Combobox(
            container,
            textvariable=self.type_var,
            values=[row["name"] for row in component_types],
            state="readonly",
            width=37,
        )
        self.type_box.grid(row=1, column=1, sticky=W)

        ttkb.Label(container, text="Hersteller").grid(row=2, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.hersteller_var, width=40).grid(row=2, column=1, sticky=W)

        ttkb.Label(container, text="Seriennummer").grid(row=3, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.seriennummer_var, width=40).grid(row=3, column=1, sticky=W)

        ttkb.Label(container, text="Anschaffungsdatum (TT.MM.JJJJ)").grid(row=4, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.anschaffungsdatum_var, width=40).grid(
            row=4, column=1, sticky=W
        )

        ttkb.Label(container, text="Bemerkung").grid(row=5, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.bemerkung_var, width=40).grid(row=5, column=1, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=6, column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(
            side=LEFT, padx=5
        )
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(
            side=LEFT, padx=5
        )

        self.grab_set()

    def on_save(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            Messagebox.show_warning("Bitte Bezeichnung angeben", "Hinweis")
            return
        try:
            anschaffungsdatum = (
                parse_date(self.anschaffungsdatum_var.get())
                if self.anschaffungsdatum_var.get().strip()
                else None
            )
        except ValueError:
            Messagebox.show_error("Ungültiges Datum", "Fehler")
            return
        komponententyp_id = None
        selected = self.type_var.get()
        for row in self.component_types:
            if row["name"] == selected:
                komponententyp_id = row["id"]
                break
        self.result = {
            "name": name,
            "hersteller": self.hersteller_var.get().strip(),
            "seriennummer": self.seriennummer_var.get().strip(),
            "anschaffungsdatum": anschaffungsdatum,
            "bemerkung": self.bemerkung_var.get().strip(),
            "komponententyp_id": komponententyp_id,
        }
        self.destroy()


class MaintenanceTab(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager, produkt_id: Optional[int]) -> None:
        super().__init__(master)
        self.db = db
        self.produkt_id = produkt_id
        self.maintenance_cache: Dict[int, sqlite3.Row] = {}

        self.toolbar = ttkb.Frame(self)
        self.toolbar.pack(fill=tk.X, padx=10, pady=10)

        self.add_btn = ttkb.Button(
            self.toolbar, text="Wartung planen", command=self.add_maintenance, bootstyle="success"
        )
        self.add_btn.pack(side=LEFT)
        self.edit_btn = ttkb.Button(
            self.toolbar, text="Bearbeiten", command=self.edit_maintenance, bootstyle="secondary"
        )
        self.edit_btn.pack(side=LEFT, padx=5)
        self.delete_btn = ttkb.Button(
            self.toolbar, text="Löschen", command=self.delete_maintenance, bootstyle="danger"
        )
        self.delete_btn.pack(side=LEFT)

        columns = [
            {"text": "ID"},
            {"text": "Geplanter Termin"},
            {"text": "Typ"},
            {"text": "Durchgeführt"},
            {"text": "Beschreibung"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=12)
        self.table.bind("<Double-1>", lambda _event: self.edit_maintenance())

        self.placeholder = ttkb.Label(
            self,
            text="Bitte Produkt speichern, um Wartungen zu verwalten.",
            bootstyle="secondary",
        )

        self.set_product_id(produkt_id)

    def set_product_id(self, produkt_id: Optional[int]) -> None:
        self.produkt_id = produkt_id
        self._update_state()

    def _update_state(self) -> None:
        enabled = bool(self.produkt_id)
        state = tk.NORMAL if enabled else tk.DISABLED
        for button in (self.add_btn, self.edit_btn, self.delete_btn):
            button.configure(state=state)
        if enabled:
            self.placeholder.pack_forget()
            self.table.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
            self.refresh()
        else:
            self.table.pack_forget()
            self.placeholder.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def refresh(self) -> None:
        if not self.produkt_id:
            return
        self.table.delete_rows()
        self.maintenance_cache = {}
        for row in self.db.list_maintenance(self.produkt_id):
            self.maintenance_cache[int(row["id"])] = row
            self.table.insert_row(
                values=(
                    row["id"],
                    format_date(row["geplanter_termin"]),
                    row["wartungstyp"],
                    format_date(row["durchgefuehrt_am"]),
                    row["beschreibung"] or "",
                )
            )

    def selected_maintenance_id(self) -> Optional[int]:
        rows = self.table.get_rows("selected")
        if not rows:
            Messagebox.show_info("Bitte Wartung auswählen", "Hinweis")
            return None
        return int(rows[0].values[0])

    def add_maintenance(self) -> None:
        if not self.produkt_id:
            return
        dialog = MaintenanceFormDialog(self, "Wartung planen")
        self.wait_window(dialog)
        if not dialog.result:
            return
        data = dialog.result
        self.db.add_or_update_maintenance(
            wartung_id=None,
            produkt_id=self.produkt_id,
            geplanter_termin=data["geplanter_termin"],
            wartungstyp=data["wartungstyp"],
            beschreibung=data["beschreibung"],
            durchgefuehrt_am=data["durchgefuehrt_am"],
            durchgefuehrt_von=data["durchgefuehrt_von"],
            bemerkung=data["bemerkung"],
        )
        self.refresh()

    def edit_maintenance(self) -> None:
        wartung_id = self.selected_maintenance_id()
        if not wartung_id:
            return
        row = self.maintenance_cache.get(wartung_id)
        if not row:
            return
        dialog = MaintenanceFormDialog(self, "Wartung bearbeiten", row)
        self.wait_window(dialog)
        if not dialog.result:
            return
        data = dialog.result
        self.db.add_or_update_maintenance(
            wartung_id=wartung_id,
            produkt_id=row["produkt_id"],
            geplanter_termin=data["geplanter_termin"],
            wartungstyp=data["wartungstyp"],
            beschreibung=data["beschreibung"],
            durchgefuehrt_am=data["durchgefuehrt_am"],
            durchgefuehrt_von=data["durchgefuehrt_von"],
            bemerkung=data["bemerkung"],
        )
        self.refresh()

    def delete_maintenance(self) -> None:
        wartung_id = self.selected_maintenance_id()
        if not wartung_id:
            return
        if Messagebox.okcancel("Wartung wirklich löschen?", "Bestätigung", alert=True) != "OK":
            return
        self.db.delete_maintenance(wartung_id)
        self.refresh()


class MaintenanceFormDialog(ttkb.Toplevel):
    def __init__(
        self, master: tk.Misc, title: str, data: Optional[sqlite3.Row] = None
    ) -> None:
        super().__init__(master)
        self.title(title)
        self.resizable(False, False)
        self.result: Optional[Dict[str, Any]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        self.geplant_var = ttkb.StringVar(value=format_date(data["geplanter_termin"]) if data else "")
        self.typ_var = ttkb.StringVar(value=(data["wartungstyp"] if data else ""))
        self.beschreibung_var = ttkb.StringVar(value=(data["beschreibung"] if data else ""))
        self.durchgefuehrt_var = ttkb.StringVar(value=format_date(data["durchgefuehrt_am"]) if data else "")
        self.von_var = ttkb.StringVar(value=(data["durchgefuehrt_von"] if data else ""))
        self.bemerkung_var = ttkb.StringVar(value=(data["bemerkung"] if data else ""))

        ttkb.Label(container, text="Geplanter Termin (TT.MM.JJJJ)*").grid(row=0, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.geplant_var, width=35).grid(row=0, column=1, sticky=W)

        ttkb.Label(container, text="Typ*").grid(row=1, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.typ_var, width=35).grid(row=1, column=1, sticky=W)

        ttkb.Label(container, text="Beschreibung").grid(row=2, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.beschreibung_var, width=35).grid(row=2, column=1, sticky=W)

        ttkb.Label(container, text="Durchgeführt am (TT.MM.JJJJ)").grid(row=3, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.durchgefuehrt_var, width=35).grid(row=3, column=1, sticky=W)

        ttkb.Label(container, text="Durchgeführt von").grid(row=4, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.von_var, width=35).grid(row=4, column=1, sticky=W)

        ttkb.Label(container, text="Bemerkung").grid(row=5, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.bemerkung_var, width=35).grid(row=5, column=1, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=6, column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(
            side=LEFT, padx=5
        )
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(
            side=LEFT, padx=5
        )

        self.grab_set()

    def on_save(self) -> None:
        try:
            geplanter_termin = parse_date(self.geplant_var.get())
        except ValueError:
            Messagebox.show_error("Ungültiges Datum", "Fehler")
            return
        if not geplanter_termin:
            Messagebox.show_error("Geplanter Termin erforderlich", "Fehler")
            return
        if not self.typ_var.get().strip():
            Messagebox.show_error("Bitte Wartungstyp angeben", "Fehler")
            return
        try:
            durchgefuehrt_am = (
                parse_date(self.durchgefuehrt_var.get())
                if self.durchgefuehrt_var.get().strip()
                else None
            )
        except ValueError:
            Messagebox.show_error("Ungültiges Datum", "Fehler")
            return
        self.result = {
            "geplanter_termin": geplanter_termin,
            "wartungstyp": self.typ_var.get().strip(),
            "beschreibung": self.beschreibung_var.get().strip(),
            "durchgefuehrt_am": durchgefuehrt_am,
            "durchgefuehrt_von": self.von_var.get().strip(),
            "bemerkung": self.bemerkung_var.get().strip(),
        }
        self.destroy()


class RepairsTab(ttkb.Frame):
    def __init__(
        self,
        master: tk.Misc,
        db: DatabaseManager,
        produkt_id: Optional[int],
        repair_types: List[sqlite3.Row],
        upload_categories: List[sqlite3.Row],
    ) -> None:
        super().__init__(master)
        self.db = db
        self.produkt_id = produkt_id
        self.repair_types = repair_types
        self.upload_categories = upload_categories
        self.contacts = db.list_contacts()
        self.repair_cache: Dict[int, sqlite3.Row] = {}

        self.toolbar = ttkb.Frame(self)
        self.toolbar.pack(fill=tk.X, padx=10, pady=10)

        self.add_btn = ttkb.Button(
            self.toolbar, text="Reparatur melden", command=self.add_repair, bootstyle="success"
        )
        self.add_btn.pack(side=LEFT)
        self.attach_btn = ttkb.Button(
            self.toolbar,
            text="Anhänge anzeigen",
            command=self.show_attachments,
            bootstyle="secondary",
        )
        self.attach_btn.pack(side=LEFT, padx=5)

        columns = [
            {"text": "ID"},
            {"text": "Datum"},
            {"text": "Typ"},
            {"text": "Kontakt"},
            {"text": "Kosten"},
            {"text": "Beschreibung"},
            {"text": "Anhänge"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=12)

        self.placeholder = ttkb.Label(
            self,
            text="Bitte Produkt speichern, um Reparaturen zu verwalten.",
            bootstyle="secondary",
        )

        self.set_product_id(produkt_id)

    def set_product_id(self, produkt_id: Optional[int]) -> None:
        self.produkt_id = produkt_id
        self._update_state()

    def _update_state(self) -> None:
        enabled = bool(self.produkt_id)
        state = tk.NORMAL if enabled else tk.DISABLED
        for button in (self.add_btn, self.attach_btn):
            button.configure(state=state)
        if enabled:
            self.placeholder.pack_forget()
            self.table.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))
            self.refresh()
        else:
            self.table.pack_forget()
            self.placeholder.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def refresh(self) -> None:
        if not self.produkt_id:
            return
        self.table.delete_rows()
        self.repair_cache = {}
        for row in self.db.list_repairs(self.produkt_id):
            attachments = self.db.list_repair_attachments(row["id"])
            self.repair_cache[int(row["id"])] = row
            self.table.insert_row(
                values=(
                    row["id"],
                    format_date(row["datum"]),
                    row["reparatur_art_name"] or "",
                    row["kontakt_name"] or "",
                    f"{row['kosten']:.2f}" if row["kosten"] is not None else "",
                    row["beschreibung"] or "",
                    str(len(attachments)),
                )
            )

    def selected_repair_id(self) -> Optional[int]:
        rows = self.table.get_rows("selected")
        if not rows:
            Messagebox.show_info("Bitte Reparatur auswählen", "Hinweis")
            return None
        return int(rows[0].values[0])

    def add_repair(self) -> None:
        if not self.produkt_id:
            return
        dialog = RepairFormDialog(
            self,
            repair_types=self.repair_types,
            upload_categories=self.upload_categories,
            contacts=self.contacts,
        )
        self.wait_window(dialog)
        if not dialog.result:
            return
        data = dialog.result
        repair_id = self.db.add_repair(
            produkt_id=self.produkt_id,
            datum=data["datum"],
            kosten=data["kosten"],
            kontakt_id=data["kontakt_id"],
            beschreibung=data["beschreibung"],
            reparatur_art_id=data["reparatur_art_id"],
        )
        for attachment in data["attachments"]:
            target_name = f"{repair_id}_{Path(attachment['quelle']).name}"
            target_path = REPAIR_STORAGE / target_name
            try:
                shutil.copy2(attachment["quelle"], target_path)
            except OSError as exc:
                Messagebox.show_warning(f"Anhang konnte nicht kopiert werden: {exc}", "Hinweis")
                continue
            self.db.add_repair_attachment(
                reparatur_id=repair_id,
                dateiname=Path(attachment["quelle"]).name,
                speicherpfad=str(target_path),
                upload_kategorie_id=attachment["upload_kategorie_id"],
            )
        self.refresh()

    def show_attachments(self) -> None:
        repair_id = self.selected_repair_id()
        if not repair_id:
            return
        attachments = self.db.list_repair_attachments(repair_id)
        if not attachments:
            Messagebox.show_info("Keine Anhänge vorhanden", "Information")
            return
        lines = []
        for entry in attachments:
            label = entry["upload_kategorie_name"] or "Anhang"
            lines.append(f"{label}: {entry['dateiname']}\n{entry['speicherpfad']}")
        Messagebox.show_info("\n\n".join(lines), "Anhänge")


class RepairFormDialog(ttkb.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        *,
        repair_types: List[sqlite3.Row],
        upload_categories: List[sqlite3.Row],
        contacts: List[sqlite3.Row],
    ) -> None:
        super().__init__(master)
        self.title("Reparatur melden")
        self.resizable(False, False)
        self.repair_types = repair_types
        self.upload_categories = upload_categories
        self.contacts = contacts
        self.result: Optional[Dict[str, Any]] = None
        self.attachments: List[Dict[str, Any]] = []

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        self.datum_var = ttkb.StringVar(value=date.today().strftime(DATE_FORMAT))
        self.kosten_var = ttkb.StringVar()
        self.repair_type_var = ttkb.StringVar()
        self.kontakt_var = ttkb.StringVar()
        self.beschreibung_text = tk.Text(container, height=4, width=40, wrap="word")

        ttkb.Label(container, text="Datum (TT.MM.JJJJ)").grid(row=0, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.datum_var, width=35).grid(row=0, column=1, sticky=W)

        ttkb.Label(container, text="Kosten").grid(row=1, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.kosten_var, width=35).grid(row=1, column=1, sticky=W)

        ttkb.Label(container, text="Reparaturtyp").grid(row=2, column=0, sticky=W, pady=5)
        ttkb.Combobox(
            container,
            textvariable=self.repair_type_var,
            values=[row["name"] for row in self.repair_types],
            state="readonly",
            width=32,
        ).grid(row=2, column=1, sticky=W)

        ttkb.Label(container, text="Kontakt").grid(row=3, column=0, sticky=W, pady=5)
        ttkb.Combobox(
            container,
            textvariable=self.kontakt_var,
            values=[row["name"] for row in self.contacts],
            state="readonly",
            width=32,
        ).grid(row=3, column=1, sticky=W)

        ttkb.Label(container, text="Beschreibung").grid(row=4, column=0, sticky=ttkb.NW, pady=5)
        self.beschreibung_text.grid(row=4, column=1, sticky=W)

        attachments_frame = ttkb.Labelframe(container, text="Anhänge")
        attachments_frame.grid(row=5, column=0, columnspan=2, pady=10, sticky=ttkb.EW)

        self.attachment_list = tk.Listbox(attachments_frame, width=55, height=4)
        self.attachment_list.pack(side=LEFT, padx=5, pady=5)
        button_column = ttkb.Frame(attachments_frame)
        button_column.pack(side=LEFT, padx=5)
        ttkb.Button(button_column, text="Datei hinzufügen", command=self.add_attachment, bootstyle="secondary").pack(
            fill=tk.X, pady=2
        )
        ttkb.Button(button_column, text="Entfernen", command=self.remove_attachment, bootstyle="danger").pack(
            fill=tk.X, pady=2
        )

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=6, column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(
            side=LEFT, padx=5
        )
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(
            side=LEFT, padx=5
        )

        self.grab_set()

    def add_attachment(self) -> None:
        file_path = filedialog.askopenfilename(title="Anhang auswählen")
        if not file_path:
            return
        dialog = AttachmentCategoryDialog(self, self.upload_categories)
        self.wait_window(dialog)
        if dialog.result is None:
            return
        category_id, category_label = dialog.result
        entry = {
            "quelle": file_path,
            "upload_kategorie_id": category_id,
            "label": category_label,
        }
        self.attachments.append(entry)
        self.attachment_list.insert(tk.END, f"{category_label}: {Path(file_path).name}")

    def remove_attachment(self) -> None:
        selection = self.attachment_list.curselection()
        if not selection:
            return
        index = selection[0]
        self.attachment_list.delete(index)
        del self.attachments[index]

    def on_save(self) -> None:
        try:
            datum = parse_date(self.datum_var.get()) or date.today()
        except ValueError:
            Messagebox.show_error("Ungültiges Datum", "Fehler")
            return
        try:
            kosten = float(self.kosten_var.get().replace(",", ".")) if self.kosten_var.get() else 0.0
        except ValueError:
            Messagebox.show_error("Kosten ungültig", "Fehler")
            return
        kontakt_id = None
        for row in self.contacts:
            if row["name"] == self.kontakt_var.get():
                kontakt_id = row["id"]
                break
        reparatur_art_id = None
        for row in self.repair_types:
            if row["name"] == self.repair_type_var.get():
                reparatur_art_id = row["id"]
                break
        beschreibung = self.beschreibung_text.get("1.0", tk.END).strip()
        self.result = {
            "datum": datum or date.today(),
            "kosten": kosten,
            "kontakt_id": kontakt_id,
            "beschreibung": beschreibung,
            "reparatur_art_id": reparatur_art_id,
            "attachments": self.attachments,
        }
        self.destroy()


class AttachmentCategoryDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, categories: List[sqlite3.Row]) -> None:
        super().__init__(master)
        self.title("Kategorie wählen")
        self.resizable(False, False)
        self.result: Optional[Tuple[Optional[int], str]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        self.category_var = ttkb.StringVar()
        ttkb.Label(container, text="Kategorie").grid(row=0, column=0, sticky=W, pady=5)
        ttkb.Combobox(
            container,
            textvariable=self.category_var,
            values=[row["name"] for row in categories],
            state="readonly",
            width=30,
        ).grid(row=0, column=1, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=1, column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Auswählen", command=lambda: self.on_select(categories)).pack(
            side=LEFT, padx=5
        )
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(
            side=LEFT, padx=5
        )

        self.grab_set()

    def on_select(self, categories: List[sqlite3.Row]) -> None:
        label = self.category_var.get()
        category_id = None
        for row in categories:
            if row["name"] == label:
                category_id = row["id"]
                break
        self.result = (category_id, label or "Unkategorisiert")
        self.destroy()


class VehicleEditor(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, db: DatabaseManager, fahrzeug_id: Optional[int] = None) -> None:
        super().__init__(master)
        self.db = db
        self.fahrzeug_id = fahrzeug_id
        self.saved = False
        self.title("Fahrzeug bearbeiten" if fahrzeug_id else "Neues Fahrzeug")
        self.geometry("560x520")

        self.brands = db.list_vehicle_brands()
        self.models = db.list_vehicle_models()
        self.categories = db.list_vehicle_categories()
        self.locations = db.list_locations()

        self.model_index: Dict[Optional[int], List[Tuple[int, str]]] = {}
        for row in self.models:
            self.model_index.setdefault(row["marke_id"], []).append((row["id"], row["name"]))

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        self.name_var = ttkb.StringVar()
        self.kennzeichen_var = ttkb.StringVar()
        self.brand_var = ttkb.StringVar()
        self.model_var = ttkb.StringVar()
        self.category_var = ttkb.StringVar()
        self.inbetriebnahme_var = ttkb.StringVar()
        self.standort_var = ttkb.StringVar()
        self.kilometer_var = ttkb.StringVar()
        self.status_var = ttkb.StringVar(value="im_dienst")
        self.decommission_var = ttkb.BooleanVar(value=False)
        self.decommission_date_var = ttkb.StringVar()

        form = ttkb.Labelframe(container, text="Fahrzeugdetails")
        form.pack(fill=BOTH, expand=True)

        ttkb.Label(form, text="Bezeichnung / Funkkennung*").grid(row=0, column=0, sticky=W, pady=5)
        ttkb.Entry(form, textvariable=self.name_var, width=40).grid(row=0, column=1, sticky=W)

        ttkb.Label(form, text="Kennzeichen / Info").grid(row=1, column=0, sticky=W, pady=5)
        ttkb.Entry(form, textvariable=self.kennzeichen_var, width=40).grid(row=1, column=1, sticky=W)

        ttkb.Label(form, text="Marke").grid(row=2, column=0, sticky=W, pady=5)
        self.brand_box = ttkb.Combobox(
            form,
            textvariable=self.brand_var,
            values=[row["name"] for row in self.brands],
            state="readonly",
            width=37,
        )
        self.brand_box.grid(row=2, column=1, sticky=W)
        self.brand_box.bind("<<ComboboxSelected>>", lambda _event: self._update_model_choices())

        ttkb.Label(form, text="Modell").grid(row=3, column=0, sticky=W, pady=5)
        self.model_box = ttkb.Combobox(form, textvariable=self.model_var, width=37, state="readonly")
        self.model_box.grid(row=3, column=1, sticky=W)

        ttkb.Label(form, text="Kategorie").grid(row=4, column=0, sticky=W, pady=5)
        self.category_box = ttkb.Combobox(
            form,
            textvariable=self.category_var,
            values=[row["name"] for row in self.categories],
            state="readonly",
            width=37,
        )
        self.category_box.grid(row=4, column=1, sticky=W)

        ttkb.Label(form, text="Inbetriebnahme (TT.MM.JJJJ)").grid(row=5, column=0, sticky=W, pady=5)
        ttkb.Entry(form, textvariable=self.inbetriebnahme_var, width=40).grid(row=5, column=1, sticky=W)

        ttkb.Label(form, text="Standort").grid(row=6, column=0, sticky=W, pady=5)
        self.standort_box = ttkb.Combobox(
            form,
            textvariable=self.standort_var,
            values=[self._format_location(row) for row in self.locations],
            state="readonly",
            width=40,
        )
        self.standort_box.grid(row=6, column=1, sticky=W)

        ttkb.Label(form, text="Kilometerstand").grid(row=7, column=0, sticky=W, pady=5)
        ttkb.Entry(form, textvariable=self.kilometer_var, width=20).grid(row=7, column=1, sticky=W)

        ttkb.Label(form, text="Status").grid(row=8, column=0, sticky=W, pady=5)
        ttkb.Combobox(
            form,
            textvariable=self.status_var,
            values=["im_dienst", "in_reparatur", "ausgeschieden"],
            state="readonly",
            width=20,
        ).grid(row=8, column=1, sticky=W)

        decommission_frame = ttkb.Labelframe(container, text="Außerbetriebnahme")
        decommission_frame.pack(fill=BOTH, expand=True, pady=(10, 0))
        ttkb.Checkbutton(
            decommission_frame,
            text="Außer Betrieb",
            variable=self.decommission_var,
            command=self._update_decommission_state,
            bootstyle="round-toggle",
        ).grid(row=0, column=0, sticky=W, pady=5)
        ttkb.Label(decommission_frame, text="Datum (TT.MM.JJJJ)").grid(row=0, column=1, sticky=W, pady=5)
        self.decommission_entry = ttkb.Entry(
            decommission_frame, textvariable=self.decommission_date_var, width=20
        )
        self.decommission_entry.grid(row=0, column=2, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.pack(fill=tk.X, pady=(15, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.save, bootstyle="success").pack(
            side=LEFT, padx=5
        )
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(
            side=LEFT, padx=5
        )

        self._update_model_choices()
        self._update_decommission_state()

        if fahrzeug_id:
            self.load_data()

        self.grab_set()

    def _format_location(self, row: sqlite3.Row) -> str:
        parts = [row["bezirksstelle"], row["ortsstelle"]]
        label = " - ".join(filter(None, parts)) or f"Standort #{row['id']}"
        return f"{label} (#{row['id']})"

    def _update_model_choices(self) -> None:
        selected_brand = None
        for row in self.brands:
            if row["name"] == self.brand_var.get():
                selected_brand = row["id"]
                break
        options = self.model_index.get(selected_brand, [])
        self.model_box.configure(values=[label for _, label in options])
        if self.model_var.get() not in [label for _, label in options]:
            self.model_var.set(options[0][1] if options else "")

    def _update_decommission_state(self) -> None:
        state = tk.NORMAL if self.decommission_var.get() else tk.DISABLED
        self.decommission_entry.configure(state=state)
        if state == tk.DISABLED:
            self.decommission_date_var.set("")

    def load_data(self) -> None:
        vehicle = next((row for row in self.db.list_vehicles() if row["id"] == self.fahrzeug_id), None)
        if not vehicle:
            Messagebox.show_error("Fahrzeug nicht gefunden", "Fehler")
            self.destroy()
            return
        self.name_var.set(vehicle["name"] or "")
        self.kennzeichen_var.set(vehicle["kennzeichen"] or "")
        if vehicle["marke_name"]:
            self.brand_var.set(vehicle["marke_name"])
        else:
            self.brand_var.set(vehicle["marke"] or "")
        self._update_model_choices()
        if vehicle["fahrzeug_typ_name"]:
            self.model_var.set(vehicle["fahrzeug_typ_name"])
        else:
            self.model_var.set(vehicle["typ"] or "")
        if vehicle["fahrzeug_kategorie_name"]:
            self.category_var.set(vehicle["fahrzeug_kategorie_name"])
        else:
            self.category_var.set(vehicle["kategorie"] or "")
        self.inbetriebnahme_var.set(format_date(vehicle["inbetriebnahme"]))
        if vehicle["standort_id"]:
            for row in self.locations:
                if row["id"] == vehicle["standort_id"]:
                    self.standort_var.set(self._format_location(row))
                    break
        self.kilometer_var.set(str(vehicle["kilometerstand"] or 0))
        self.status_var.set(vehicle["status"] or "im_dienst")
        self.decommission_var.set(bool(vehicle["ausserbetrieb"]))
        self.decommission_date_var.set(format_date(vehicle["ausserbetriebnahme_datum"]))
        self._update_decommission_state()

    def save(self) -> None:
        if not self.name_var.get().strip():
            Messagebox.show_error("Bezeichnung ist erforderlich", "Fehler")
            return
        try:
            kilometer = int(self.kilometer_var.get() or 0)
        except ValueError:
            Messagebox.show_error("Kilometerstand muss Zahl sein", "Fehler")
            return
        try:
            inbetriebnahme = parse_date(self.inbetriebnahme_var.get())
        except ValueError:
            Messagebox.show_error("Ungültiges Datum", "Fehler")
            return
        try:
            decommission_date = (
                parse_date(self.decommission_date_var.get())
                if self.decommission_date_var.get().strip()
                else None
            )
        except ValueError:
            Messagebox.show_error("Ungültiges Außerbetriebnahmedatum", "Fehler")
            return

        standort_id = None
        for row in self.locations:
            if self._format_location(row) == self.standort_var.get():
                standort_id = row["id"]
                break

        brand_id = None
        for row in self.brands:
            if row["name"] == self.brand_var.get():
                brand_id = row["id"]
                break

        model_id = None
        if brand_id in self.model_index:
            for mid, label in self.model_index[brand_id]:
                if label == self.model_var.get():
                    model_id = mid
                    break

        category_id = None
        for row in self.categories:
            if row["name"] == self.category_var.get():
                category_id = row["id"]
                break

        self.db.add_or_update_vehicle(
            fahrzeug_id=self.fahrzeug_id,
            name=self.name_var.get(),
            kennzeichen=self.kennzeichen_var.get(),
            marke=self.brand_var.get(),
            typ=self.model_var.get(),
            kategorie=self.category_var.get(),
            inbetriebnahme=inbetriebnahme,
            standort_id=standort_id,
            kilometerstand=kilometer,
            status=self.status_var.get() or "im_dienst",
            marke_id=brand_id,
            fahrzeugtyp_id=model_id,
            fahrzeugkategorie_id=category_id,
            ausserbetrieb=self.decommission_var.get(),
            ausserbetriebnahme=decommission_date,
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
        self.geometry("520x420")

        self.categories = db.list_categories("material")
        self.material_names = [row["name"] for row in db.list_material_names()]
        self.vehicles = db.list_vehicles()
        self.locations = db.list_locations()

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        form = ttkb.Labelframe(container, text="Material")
        form.pack(fill=BOTH, expand=True)

        self.name_var = ttkb.StringVar()
        ttkb.Label(form, text="Bezeichnung*").grid(row=0, column=0, sticky=W, pady=5)
        self.name_box = ttkb.Combobox(
            form,
            textvariable=self.name_var,
            values=self.material_names,
            width=42,
        )
        self.name_box.grid(row=0, column=1, sticky=W)

        self.category_var = ttkb.StringVar()
        ttkb.Label(form, text="Kategorie").grid(row=1, column=0, sticky=W, pady=5)
        self.category_box = ttkb.Combobox(
            form,
            textvariable=self.category_var,
            values=[row["name"] for row in self.categories],
            width=42,
            state="readonly",
        )
        self.category_box.grid(row=1, column=1, sticky=W)

        self.lagerort_var = ttkb.StringVar()
        ttkb.Label(form, text="Lagerort").grid(row=2, column=0, sticky=W, pady=5)
        self.lagerort_box = ttkb.Combobox(
            form,
            textvariable=self.lagerort_var,
            values=self._build_lagerort_options(),
            width=42,
        )
        self.lagerort_box.grid(row=2, column=1, sticky=W)

        self.soll_var = ttkb.StringVar()
        ttkb.Label(form, text="Soll-Bestand").grid(row=3, column=0, sticky=W, pady=5)
        ttkb.Entry(form, textvariable=self.soll_var, width=20).grid(row=3, column=1, sticky=W)

        self.ist_var = ttkb.StringVar()
        ttkb.Label(form, text="Ist-Bestand").grid(row=4, column=0, sticky=W, pady=5)
        ttkb.Entry(form, textvariable=self.ist_var, width=20).grid(row=4, column=1, sticky=W)

        self.expiry_active = ttkb.BooleanVar(value=True)
        self.expiry_var = ttkb.StringVar()
        ttkb.Label(form, text="Verfallsdatum (TT.MM.JJJJ)").grid(row=5, column=0, sticky=W, pady=5)
        self.expiry_entry = ttkb.Entry(form, textvariable=self.expiry_var, width=20)
        self.expiry_entry.grid(row=5, column=1, sticky=W)
        ttkb.Checkbutton(
            form,
            text="Verfallsdatum aktiv",
            variable=self.expiry_active,
            command=self._toggle_expiry,
            bootstyle="round-toggle",
        ).grid(row=5, column=2, padx=10, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        if material_id:
            self.load_data()
        else:
            self._toggle_expiry()

        self.grab_set()

    def _build_lagerort_options(self) -> List[str]:
        options: List[str] = []
        for row in self.vehicles:
            label = row["name"]
            if row["kennzeichen"]:
                label += f" [{row['kennzeichen']}]"
            options.append(label)
        for row in self.locations:
            parts = [row["bezirksstelle"], row["ortsstelle"]]
            label = " - ".join(filter(None, parts))
            if label:
                options.append(label)
        return sorted(set(filter(None, options)))

    def _toggle_expiry(self) -> None:
        state = tk.NORMAL if self.expiry_active.get() else tk.DISABLED
        if not self.expiry_active.get():
            self.expiry_var.set("")
        self.expiry_entry.configure(state=state)

    def load_data(self) -> None:
        material = next((row for row in self.db.list_materials() if row["id"] == self.material_id), None)
        if not material:
            Messagebox.show_error("Material nicht gefunden", "Fehler")
            self.destroy()
            return
        self.name_var.set(material["name"] or "")
        if material["kategorie_id"]:
            for row in self.categories:
                if row["id"] == material["kategorie_id"]:
                    self.category_var.set(row["name"])
                    break
        self.lagerort_var.set(material["lagerort"] or "")
        self.soll_var.set(str(material["soll_bestand"]))
        self.ist_var.set(str(material["ist_bestand"]))
        expiry = format_date(material["verfallsdatum"])
        if expiry:
            self.expiry_var.set(expiry)
            self.expiry_active.set(True)
        else:
            self.expiry_active.set(False)
        self._toggle_expiry()

    def save(self) -> None:
        if not self.name_var.get().strip():
            Messagebox.show_error("Bezeichnung ist erforderlich", "Fehler")
            return

        try:
            soll = int(self.soll_var.get() or 0)
            ist = int(self.ist_var.get() or 0)
        except ValueError:
            Messagebox.show_error("Bestand muss Zahl sein", "Fehler")
            return

        verfallsdatum: Optional[date] = None
        if self.expiry_active.get():
            try:
                verfallsdatum = parse_date(self.expiry_var.get()) if self.expiry_var.get().strip() else None
            except ValueError:
                Messagebox.show_error("Ungültiges Datum", "Fehler")
                return

        kategorie_id = None
        for row in self.categories:
            if row["name"] == self.category_var.get():
                kategorie_id = row["id"]
                break

        self.db.add_or_update_material(
            material_id=self.material_id,
            name=self.name_var.get(),
            kategorie_id=kategorie_id,
            lagerort=self.lagerort_var.get().strip(),
            soll_bestand=soll,
            ist_bestand=ist,
            verfallsdatum=verfallsdatum,
        )
        self.saved = True
        Messagebox.show_info("Material gespeichert", "Erfolg")
        self.destroy()





class MedizinprodukteApp(ttkb.Window):
    def __init__(self) -> None:
        super().__init__(themename="flatly")
        self.title("Medizinprodukte-Management System")
        self.geometry("1100x750")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.db = DatabaseManager()
        self.user: Optional[User] = None
        self.preferences: Dict[str, str] = {}
        self.current_theme = "flatly"
        self.font_scale = 1.0
        self.show_welcome_info = True

        login = LoginDialog(self, self.db)
        self.wait_window(login)
        if not login.user:
            self.destroy()
            return
        self.user = login.user
        self.preferences = self.db.get_user_preferences(self.user.id)
        self.current_theme = self.preferences.get("theme", "flatly") or "flatly"
        try:
            self.font_scale = float(self.preferences.get("font_scale", "1.0"))
        except ValueError:
            self.font_scale = 1.0
        if self.font_scale < 1.0:
            self.font_scale = 1.0
        self.show_welcome_info = self.preferences.get("show_welcome", "1") != "0"
        self._configure_base_fonts()
        self._apply_theme(self.current_theme, persist=False)
        self._apply_font_scale(self.font_scale, persist=False)

        self.create_widgets()
        self.refresh_all()

    def create_widgets(self) -> None:
        self.header_frame = ttkb.Frame(self)
        self.header_frame.pack(fill=tk.X, pady=10, padx=10)

        self.welcome_label = ttkb.Label(
            self.header_frame,
            text=f"Willkommen {self.user.full_name} ({self.user.role})",
            font=("Helvetica", 12),
        )

        self.personalize_button = ttkb.Button(
            self.header_frame,
            text="Personalisieren",
            command=self.open_personalization,
            bootstyle="info",
        )
        self.personalize_button.pack(side=RIGHT)

        self.theme_button = ttkb.Button(
            self.header_frame,
            text=self._theme_button_text(),
            command=self.toggle_theme,
            bootstyle="secondary",
        )
        self.theme_button.pack(side=RIGHT, padx=(0, 10))

        self._update_welcome_visibility()

        self.notebook = ttkb.Notebook(self)
        self.notebook.pack(fill=BOTH, expand=True)

        self.dashboard_view = DashboardView(self.notebook, self.db)
        self.notebook.add(self.dashboard_view, text="Dashboard")
        self.dashboard_view.update_palette(self.current_theme in self._dark_themes())

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

    def _apply_theme(self, theme: str, persist: bool = True) -> None:
        available = set(self.style.theme_names())
        selected = theme if theme in available else "flatly"
        self.style.theme_use(selected)
        self.current_theme = selected
        self._setup_styles()
        if hasattr(self, "dashboard_view"):
            self.dashboard_view.update_palette(self.current_theme in self._dark_themes())
        if hasattr(self, "theme_button"):
            self.theme_button.configure(text=self._theme_button_text())
        if persist and self.user:
            self.db.set_user_preference(self.user.id, "theme", self.current_theme)

    def _setup_styles(self) -> None:
        card_fg = "#f8fafc" if self.current_theme in self._dark_themes() else "#1f2937"
        accent = "#6366f1" if self.current_theme in self._dark_themes() else "#2563eb"
        self.style.configure("KpiCard.TFrame", borderwidth=1, relief="ridge")
        self.style.configure("KpiTitle.TLabel", foreground=accent, font=("Inter", 11, "bold"))
        self.style.configure("KpiValue.TLabel", foreground=card_fg, font=("Inter", 26, "bold"))

    def _configure_base_fonts(self) -> None:
        base_size = 16
        for font_name in [
            "TkDefaultFont",
            "TkTextFont",
            "TkHeadingFont",
            "TkMenuFont",
            "TkTooltipFont",
            "TkFixedFont",
        ]:
            try:
                tkfont.nametofont(font_name).configure(size=base_size)
            except tk.TclError:
                continue

    def _apply_font_scale(self, scale: float, persist: bool = True) -> None:
        if scale < 1.0:
            scale = 1.0
        self.tk.call("tk", "scaling", scale)
        self.font_scale = scale
        if persist and self.user:
            self.db.set_user_preference(self.user.id, "font_scale", f"{scale:.2f}")

    def _update_welcome_visibility(self) -> None:
        if self.show_welcome_info:
            if not self.welcome_label.winfo_ismapped():
                self.welcome_label.pack(side=LEFT)
        else:
            if self.welcome_label.winfo_ismapped():
                self.welcome_label.pack_forget()
        if self.user:
            self.db.set_user_preference(self.user.id, "show_welcome", "1" if self.show_welcome_info else "0")

    def toggle_theme(self) -> None:
        next_theme = "darkly" if self.current_theme not in self._dark_themes() else "flatly"
        self._apply_theme(next_theme)

    def open_personalization(self) -> None:
        dialog = PersonalizationDialog(
            self,
            current_theme=self.current_theme,
            font_scale=self.font_scale,
            show_welcome=self.show_welcome_info,
        )
        self.wait_window(dialog)
        if not dialog.result:
            return
        theme, scale, show_info = dialog.result
        self.show_welcome_info = show_info
        self._apply_theme(theme)
        self._apply_font_scale(scale)
        self._update_welcome_visibility()

    @staticmethod
    def _dark_themes() -> set[str]:
        return {"darkly", "cyborg", "superhero", "solar"}

    def _theme_button_text(self) -> str:
        return "Dunkelmodus" if self.current_theme not in self._dark_themes() else "Hellmodus"


if __name__ == "__main__":
    app = MedizinprodukteApp()
    app.mainloop()
