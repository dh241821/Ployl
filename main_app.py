"""Medizinprodukte-Management System GUI."""

from __future__ import annotations

import calendar
import calendar
import json
import textwrap
import webbrowser
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import shutil
import sqlite3

import ttkbootstrap as ttkb
from ttkbootstrap.constants import BOTH, LEFT, RIGHT, W, Y
from ttkbootstrap.dialogs import Messagebox
from ttkbootstrap.widgets import DateEntry
from ttkbootstrap.widgets.tableview import Tableview

from app.database import (
    AUSSCHEIDUNGSGRUND_VORSCHLAEGE,
    BEZIRKSSTELLEN_DATEN,
    BEZIRKSSTELLEN_VORSCHLAEGE,
    BEZIRKSSTELLE_TO_BEZIRK,
    BEZIRK_TO_BEREICH,
    BEREICH_VORSCHLAEGE,
    BEZIRK_VORSCHLAEGE,
    DatabaseManager,
    FAHRZEUG_KATEGORIEN,
    HERSTELLER_VORSCHLAEGE,
    KOMPONENTEN_VORSCHLAEGE,
    LAND_VORSCHLAEGE,
    MATERIAL_VORSCHLAEGE,
    PERMISSION_COLUMNS,
    PERMISSION_DEFAULTS,
    PERMISSION_MODULES,
    PRODUKT_VORSCHLAEGE,
    REPARATUR_DATEI_KATEGORIEN,
    TYP_MODELL_VORSCHLAEGE,
    User,
)

import tkinter as tk
from tkinter import filedialog, font as tkfont, scrolledtext

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


DATE_FORMAT = "%d.%m.%Y"
REPAIR_STORAGE = Path("storage/reparaturen")
REPAIR_STORAGE.mkdir(parents=True, exist_ok=True)

STATUS_OPTIONS: List[Tuple[str, str]] = [
    ("Im Dienst", "im_dienst"),
    ("In Reparatur", "in_reparatur"),
    ("Ausgeschieden", "ausgeschieden"),
]
STATUS_LABEL_TO_VALUE = {label: value for label, value in STATUS_OPTIONS}
STATUS_VALUE_TO_LABEL = {value: label for label, value in STATUS_OPTIONS}

BEZIRKSSTELLEN_INFO: Dict[str, Dict[str, str]] = {
    entry["name"]: entry for entry in BEZIRKSSTELLEN_DATEN
}


def parse_date(value: str) -> Optional[date]:
    value = value.strip()
    if not value:
        return None
    return datetime.strptime(value, DATE_FORMAT).date()


def format_date(value: Optional[str]) -> str:
    if not value:
        return ""
    return datetime.strptime(value, "%Y-%m-%d").strftime(DATE_FORMAT)


def add_months(start: date, months: int) -> date:
    month = start.month - 1 + months
    year = start.year + month // 12
    month = month % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def display_status(value: Optional[str]) -> str:
    if not value:
        return ""
    return STATUS_VALUE_TO_LABEL.get(value, value)


def bind_date_entry(widget: DateEntry, variable: ttkb.StringVar) -> None:
    """Attach a StringVar to a DateEntry's embedded Entry widget."""

    widget.entry.configure(textvariable=variable)
    current = variable.get()
    widget.entry.delete(0, tk.END)
    if current:
        widget.entry.insert(0, current)


class IdentifierCombobox(ttkb.Combobox):
    """Lightweight autocomplete combobox for service number selection."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        values: Optional[Iterable[str]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, values=list(values or ()), **kwargs)
        self._all_values: List[str] = list(values or ())
        self.bind("<KeyRelease>", self._on_key_release, add="+")

    def set_completion_list(self, values: Iterable[str]) -> None:
        """Update the internal value cache and displayed value list."""

        self._all_values = list(values)
        self.configure(values=self._all_values)

    def _on_key_release(self, event: tk.Event) -> None:  # type: ignore[override]
        if event.keysym in {"BackSpace", "Left", "Right", "Up", "Down", "Home", "End", "Return", "Tab", "Escape"}:
            return

        typed = self.get()
        if not typed:
            self.configure(values=self._all_values)
            return

        matches = [value for value in self._all_values if value.lower().startswith(typed.lower())]
        if not matches:
            self.configure(values=self._all_values)
            return

        self.configure(values=matches)
        suggestion = matches[0]
        self.set(suggestion)
        self.icursor(len(typed))
        self.select_range(len(typed), tk.END)


class SearchableCombobox(ttkb.Combobox):
    """Combobox that filters its value list while the user types."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        values: Optional[Iterable[str]] = None,
        match_mode: str = "contains",
        **kwargs: Any,
    ) -> None:
        super().__init__(master, values=list(values or ()), **kwargs)
        self._base_values: List[str] = list(values or ())
        self.match_mode = match_mode
        self.bind("<KeyRelease>", self._on_key_release, add="+")

    def set_completion_list(self, values: Iterable[str]) -> None:
        self._base_values = list(values or ())
        self.configure(values=self._base_values)

    def _matches(self, item: str, typed: str) -> bool:
        haystack = item.lower()
        needle = typed.lower()
        if self.match_mode == "prefix":
            return haystack.startswith(needle)
        return needle in haystack

    def _on_key_release(self, event: tk.Event) -> None:  # type: ignore[override]
        if event.keysym in {
            "BackSpace",
            "Left",
            "Right",
            "Up",
            "Down",
            "Home",
            "End",
            "Return",
            "Tab",
            "Escape",
        }:
            return

        typed = self.get()
        if not typed:
            self.configure(values=self._base_values)
            return
        matches = [value for value in self._base_values if self._matches(value, typed)]
        self.configure(values=matches or self._base_values)


class NavigationSidebar(ttkb.Frame):
    """Scrollable navigation sidebar with selectable buttons."""

    def __init__(self, master: tk.Misc, *, on_select: Callable[[str], None]) -> None:
        super().__init__(master, padding=(14, 18), style="Sidebar.TFrame")
        self.on_select = on_select
        self._commands: Dict[str, Callable[[], None]] = {}
        self._buttons: Dict[str, ttkb.Button] = {}
        self._selected: Optional[str] = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        style = ttkb.Style()
        sidebar_bg = style.lookup("Sidebar.TFrame", "background") or "#f1f5f9"

        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, background=sidebar_bg)
        self.canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.scrollbar = ttkb.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar.grid(row=0, column=1, sticky=tk.NS, padx=(8, 0))
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.inner = ttkb.Frame(self.canvas, padding=(0, 4), style="SidebarInner.TFrame")
        self.inner.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")

        self.inner.columnconfigure(0, weight=1)

    def add_heading(self, text: str) -> None:
        ttkb.Label(
            self.inner,
            text=text.upper(),
            style="SidebarHeading.TLabel",
            padding=(6, 12, 6, 4),
        ).grid(sticky=tk.W, pady=(10, 0))

    def add_item(self, key: str, label: str, command: Callable[[], None]) -> None:
        self._commands[key] = command

        def handle_select(k: str = key) -> None:
            self.select(k)
            cmd = self._commands.get(k)
            if cmd:
                cmd()

        button = ttkb.Button(
            self.inner,
            text=label,
            command=handle_select,
            width=22,
            bootstyle="secondary",
        )
        button.grid(sticky=tk.EW, pady=4)
        self._buttons[key] = button

    def select(self, key: str) -> None:
        if self._selected == key:
            return
        for name, button in self._buttons.items():
            button.configure(bootstyle="secondary" if name != key else "primary")
        self._selected = key


class LargeDialog(ttkb.Toplevel):
    """Toplevel window with a sensible default geometry."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        min_width: int = 900,
        min_height: int = 620,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, **kwargs)
        self._min_width = min_width
        self._min_height = min_height
        self.after(40, self._apply_default_size)

    def configure_size(self, *, width: Optional[int] = None, height: Optional[int] = None) -> None:
        if width:
            self._min_width = width
        if height:
            self._min_height = height
        self._apply_default_size()

    def _apply_default_size(self) -> None:
        try:
            self.update_idletasks()
        except tk.TclError:
            return
        width = max(self._min_width, self.winfo_width() or self._min_width)
        height = max(self._min_height, self.winfo_height() or self._min_height)
        self.minsize(self._min_width, self._min_height)
        self.geometry(f"{width}x{height}")

class LoginDialog(ttkb.Toplevel):
    """Simple login dialog that blocks the root window until closed."""

    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.title("Anmeldung")
        self.resizable(False, False)
        self.db = db
        self.user: Optional[User] = None
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        self.update_idletasks()
        self.lift()
        self.attributes("-topmost", True)
        self.after(150, lambda: self.attributes("-topmost", False))
        self.focus_force()

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        self.login_choices = self.db.list_user_identifiers()
        identifiers = [choice["identifier"] for choice in self.login_choices if choice["identifier"]]
        self.identifier_var = ttkb.StringVar()

        ttkb.Label(container, text="Dienstnummer").grid(row=0, column=0, sticky=W, pady=(0, 5))
        try:
            from ttkbootstrap.widgets import AutocompleteCombobox  # type: ignore

            self.identifier_box = AutocompleteCombobox(
                container,
                textvariable=self.identifier_var,
                width=30,
                completevalues=identifiers,
            )
        except Exception:
            self.identifier_box = IdentifierCombobox(
                container,
                textvariable=self.identifier_var,
                width=30,
                values=identifiers,
            )
            self.identifier_box.set_completion_list(identifiers)
        self.identifier_box.grid(row=1, column=0, sticky=W)
        if identifiers:
            self.identifier_var.set(identifiers[0])

        ttkb.Label(container, text="Passwort").grid(row=2, column=0, sticky=W, pady=(10, 5))
        self.password_var = ttkb.StringVar()
        ttkb.Entry(container, textvariable=self.password_var, show="*", width=30).grid(row=3, column=0, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=4, column=0, pady=(20, 0), sticky=W)
        ttkb.Button(button_frame, text="Anmelden", command=self.on_login, bootstyle="success").pack(side=LEFT)
        ttkb.Button(button_frame, text="Abbrechen", command=self.on_cancel, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.bind("<Return>", lambda _event: self.on_login())
        self.identifier_box.focus_set()

    def _resolve_username(self, identifier: str) -> str:
        for choice in self.login_choices:
            if choice["identifier"] == identifier:
                return choice["username"]
        return identifier

    def on_login(self) -> None:
        identifier = self.identifier_var.get().strip()
        password = self.password_var.get()
        if not identifier or not password:
            Messagebox.show_error("Bitte Dienstnummer und Passwort eingeben", "Anmeldung fehlgeschlagen")
            return
        username = self._resolve_username(identifier)
        user = self.db.authenticate(username, password, identifier=identifier)
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

        fill(
            self.due_table,
            ((row["name"], display_status(row["status"]), row["seriennummer"]) for row in due),
        )
        fill(
            self.repair_table,
            ((row["name"], display_status(row["status"]), row["seriennummer"]) for row in repairs),
        )
        fill(self.expired_table, ((row["name"], format_date(row["verfallsdatum"]), row["lagerort"]) for row in expired))
        fill(self.low_table, ((row["name"], f"{row['ist_bestand']}/{row['soll_bestand']}", row["lagerort"]) for row in low))

        self.ax.clear()
        statuses = list(status_counts.keys())
        values = list(status_counts.values())
        if not statuses:
            statuses = ["im_dienst"]
            values = [0]
        color_map = {
            "im_dienst": "#198754",
            "in_reparatur": "#FFC107",
            "ausgeschieden": "#6c757d",
        }
        labels = [display_status(status) for status in statuses]
        colors = [color_map.get(status, "#0d6efd") for status in statuses]
        self.ax.bar(labels, values, color=colors)
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
    def __init__(
        self,
        master: tk.Misc,
        db: DatabaseManager,
        user: Optional[User] = None,
    ) -> None:
        super().__init__(master)
        self.db = db
        self.write_allowed = True
        self.user = user
        self._location_filter_map: Dict[str, Optional[int]] = {"Alle": None}
        self._vehicle_filter_map: Dict[str, Optional[int]] = {"Alle": None}
        self._category_filter_values: List[str] = ["Alle"]

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)

        self.new_button = ttkb.Button(toolbar, text="Neu", command=self.create_product, bootstyle="success")
        self.new_button.pack(side=LEFT)
        self.edit_button = ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_product, bootstyle="secondary")
        self.edit_button.pack(side=LEFT, padx=5)
        self.retire_button = ttkb.Button(toolbar, text="Ausscheiden", command=self.retire_product, bootstyle="danger")
        self.retire_button.pack(side=LEFT)
        self.components_button = ttkb.Button(
            toolbar,
            text="Komponenten",
            command=self.open_components,
            bootstyle="info",
        )
        self.components_button.pack(side=LEFT, padx=5)
        self.maintenance_button = ttkb.Button(
            toolbar,
            text="Wartungen",
            command=self.open_maintenance,
            bootstyle="info",
        )
        self.maintenance_button.pack(side=LEFT)
        self.repairs_button = ttkb.Button(
            toolbar,
            text="Reparaturen",
            command=self.open_repairs,
            bootstyle="info",
        )
        self.repairs_button.pack(side=LEFT, padx=5)
        self.mass_upload_button = ttkb.Button(
            toolbar,
            text="Massenupload",
            command=self.mass_upload,
            bootstyle="warning",
        )
        self.mass_upload_button.pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Export CSV", command=self.export_products, bootstyle="info").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Lebenslauf", command=self.export_lifecycle, bootstyle="info").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Liste HTML", command=self.export_html, bootstyle="primary").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Liste PDF", command=self.export_pdf, bootstyle="primary").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="ICS Export", command=self.export_ics, bootstyle="secondary").pack(side=LEFT, padx=5)

        self._write_buttons = [
            self.new_button,
            self.edit_button,
            self.retire_button,
            self.components_button,
            self.maintenance_button,
            self.repairs_button,
            self.mass_upload_button,
        ]

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
            values=[""] + [label for label, _ in STATUS_OPTIONS],
            width=18,
            state="readonly",
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

        filter_frame = ttkb.Frame(self)
        filter_frame.pack(fill=tk.X, padx=10)

        ttkb.Label(filter_frame, text="Standort:").grid(row=0, column=0, sticky=W, pady=5)
        self.location_filter_var = ttkb.StringVar(value="Alle")
        self.location_filter_box = SearchableCombobox(
            filter_frame,
            textvariable=self.location_filter_var,
            width=30,
            values=list(self._location_filter_map.keys()),
        )
        self.location_filter_box.grid(row=0, column=1, sticky=W, padx=(0, 15))
        self.location_filter_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        self.location_filter_box.set_completion_list(list(self._location_filter_map.keys()))

        ttkb.Label(filter_frame, text="Kategorie:").grid(row=0, column=2, sticky=W, pady=5)
        self.category_filter_var = ttkb.StringVar(value="Alle")
        self.category_filter_box = ttkb.Combobox(
            filter_frame,
            textvariable=self.category_filter_var,
            state="readonly",
            width=25,
            values=self._category_filter_values,
        )
        self.category_filter_box.grid(row=0, column=3, sticky=W, padx=(0, 15))
        self.category_filter_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh())

        ttkb.Label(filter_frame, text="Fahrzeug:").grid(row=0, column=4, sticky=W, pady=5)
        self.vehicle_filter_var = ttkb.StringVar(value="Alle")
        self.vehicle_filter_box = ttkb.Combobox(
            filter_frame,
            textvariable=self.vehicle_filter_var,
            state="readonly",
            width=25,
            values=list(self._vehicle_filter_map.keys()),
        )
        self.vehicle_filter_box.grid(row=0, column=5, sticky=W)
        self.vehicle_filter_box.bind("<<ComboboxSelected>>", lambda _event: self.refresh())

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

    def set_user(self, user: Optional[User]) -> None:
        self.user = user
        self.refresh()

    def set_write_permissions(self, allowed: bool) -> None:
        """Enable or disable write interactions for the product view."""

        self.write_allowed = allowed
        state = tk.NORMAL if allowed else tk.DISABLED
        for widget in self._write_buttons:
            widget.configure(state=state)

    def _require_write(self) -> bool:
        if self.write_allowed:
            return True
        Messagebox.show_info("Sie haben keine Schreibrechte für Produkte.", "Keine Berechtigung")
        return False

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
        rows = self.db.list_products()
        accessible_rows: List[sqlite3.Row] = []
        for row in rows:
            standort_id = row["standort_id"] if "standort_id" in row.keys() else None
            if self.user and not self.user.can_read_location(standort_id):
                continue
            accessible_rows.append(row)

        self._update_filter_values(accessible_rows)

        query = self.search_var.get().strip().lower()
        status_label = self.status_var.get().strip()
        status_filter = STATUS_LABEL_TO_VALUE.get(status_label, "") if status_label else ""
        hide_retired = self.hide_retired.get()

        location_selection = self.location_filter_var.get()
        location_filter = self._location_filter_map.get(location_selection)
        vehicle_selection = self.vehicle_filter_var.get()
        vehicle_filter = self._vehicle_filter_map.get(vehicle_selection)
        category_selection = self.category_filter_var.get()
        expect_no_category = category_selection == "Ohne Kategorie"
        category_filter = None
        if category_selection not in ("", "Alle", "Ohne Kategorie"):
            category_filter = category_selection

        for row in accessible_rows:
            haystack = " ".join(
                filter(
                    None,
                    [
                        row["name"],
                        row["seriennummer"],
                        row["hersteller"],
                        row.get("produkt_hersteller_name", ""),
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

            standort_id = row["standort_id"] if "standort_id" in row.keys() else None
            if location_filter is not None:
                if location_filter == -1:
                    if standort_id is not None:
                        continue
                elif standort_id != location_filter:
                    continue

            fahrzeug_id = row["fahrzeug_id"] if "fahrzeug_id" in row.keys() else None
            if vehicle_filter is not None:
                if vehicle_filter == -1:
                    if fahrzeug_id is not None:
                        continue
                elif fahrzeug_id != vehicle_filter:
                    continue

            kategorie_name = row["kategorie_name"] or ""
            if expect_no_category and kategorie_name:
                continue
            if category_filter and kategorie_name != category_filter:
                continue

            status_label_value = display_status(row["status"])
            location_label = self.db.location_label_from_product(row)
            self.table.insert_row(
                values=(
                    row["id"],
                    row["name"],
                    row["produkt_typ_name"] or row["typ"] or "",
                    row["produkt_modell_name"] or "",
                    row["seriennummer"],
                    status_label_value,
                    location_label,
                    row["fahrzeug_name"] or "",
                    row["lagerort"] or "",
                    row["interne_kennung"] or "",
                )
            )

    def _update_filter_values(self, rows: List[sqlite3.Row]) -> None:
        location_map: Dict[str, Optional[int]] = {"Alle": None}
        vehicle_map: Dict[str, Optional[int]] = {"Alle": None}
        category_markers: List[str] = []
        has_location_none = False
        has_vehicle_none = False

        for row in rows:
            standort_id = row["standort_id"] if "standort_id" in row.keys() else None
            if standort_id is None:
                has_location_none = True
            else:
                label = self.db.location_label_from_product(row) or f"Standort #{standort_id}"
                if label in location_map:
                    label = f"{label} (ID {standort_id})"
                location_map[label] = int(standort_id)

            fahrzeug_id = row["fahrzeug_id"] if "fahrzeug_id" in row.keys() else None
            if fahrzeug_id is None:
                has_vehicle_none = True
            else:
                vehicle_label = row["fahrzeug_name"] or f"Fahrzeug #{fahrzeug_id}"
                if vehicle_label in vehicle_map:
                    vehicle_label = f"{vehicle_label} (ID {fahrzeug_id})"
                vehicle_map[vehicle_label] = int(fahrzeug_id)

            category_markers.append(row["kategorie_name"] or "__NONE__")

        if has_location_none:
            location_map["Ohne Standort"] = -1
        if has_vehicle_none:
            vehicle_map["Ohne Fahrzeug"] = -1

        previous_location = self.location_filter_var.get()
        self._location_filter_map = location_map
        self.location_filter_box.configure(values=list(location_map.keys()))
        self.location_filter_box.set_completion_list(list(location_map.keys()))
        if previous_location in location_map:
            self.location_filter_var.set(previous_location)
        else:
            self.location_filter_var.set("Alle")

        previous_vehicle = self.vehicle_filter_var.get()
        self._vehicle_filter_map = vehicle_map
        self.vehicle_filter_box.configure(values=list(vehicle_map.keys()))
        if previous_vehicle in vehicle_map:
            self.vehicle_filter_var.set(previous_vehicle)
        else:
            self.vehicle_filter_var.set("Alle")

        categories = sorted({marker for marker in category_markers if marker not in {"", "__NONE__"}})
        values: List[str] = ["Alle"]
        if "__NONE__" in category_markers:
            values.append("Ohne Kategorie")
        values.extend(categories)
        previous_category = self.category_filter_var.get()
        self._category_filter_values = values
        self.category_filter_box.configure(values=values)
        if previous_category in values:
            self.category_filter_var.set(previous_category)
        else:
            self.category_filter_var.set("Alle")

    def _ensure_write_for_product(self, produkt_id: Optional[int]) -> bool:
        if not self.user or not self.user.location_permissions or produkt_id is None:
            return True
        product = self.db.get_product(produkt_id)
        if not product:
            Messagebox.show_error("Produkt nicht gefunden", "Fehler")
            return False
        standort_id = product["standort_id"] if "standort_id" in product.keys() else None
        if self.user.can_write_location(standort_id):
            return True
        Messagebox.show_info(
            "Sie haben keine Schreibrechte für den Standort dieses Produkts.",
            "Keine Berechtigung",
        )
        return False

    def create_product(self) -> None:
        if not self._require_write():
            return
        if self.user and self.user.location_permissions:
            if not any(perm.schreiben for perm in self.user.location_permissions.values()):
                Messagebox.show_info(
                    "Sie haben keine Standorte mit Schreibrechten.",
                    "Keine Berechtigung",
                )
                return
        editor = ProductEditor(self, self.db, user=self.user)
        self.wait_window(editor)
        if editor.saved:
            self.refresh()

    def edit_product(self) -> None:
        if not self._require_write():
            return
        product_id = self.selected_product_id()
        if not product_id:
            return
        if not self._ensure_write_for_product(product_id):
            return
        editor = ProductEditor(self, self.db, produkt_id=product_id, user=self.user)
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
        if not self._require_write():
            return
        product_id = self.selected_product_id()
        if not product_id:
            return
        if not self._ensure_write_for_product(product_id):
            return
        editor = ProductEditor(
            self,
            self.db,
            produkt_id=product_id,
            initial_tab=tab_name,
            user=self.user,
        )
        self.wait_window(editor)
        if editor.saved:
            self.refresh()

    def retire_product(self) -> None:
        if not self._require_write():
            return
        product_id = self.selected_product_id()
        if not product_id:
            return
        if not self._ensure_write_for_product(product_id):
            return
        reasons = [row["name"] for row in self.db.list_retirement_reasons()]
        dialog = RetireProductDialog(self, reasons)
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
        self.db.mark_product_retired(
            product_id,
            parsed_date,
            grund,
            user_id=self.user.id if self.user else None,
        )
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

    def export_pdf(self) -> None:
        filepath = filedialog.asksaveasfilename(
            title="PDF exportieren",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not filepath:
            return
        self.db.export_products_as_pdf(Path(filepath))
        Messagebox.show_info("PDF erstellt", "Export")

    def mass_upload(self) -> None:
        if not self._require_write():
            return
        dialog = MassUploadDialog(self, self.db, user=self.user)
        self.wait_window(dialog)
        created = getattr(dialog, "created", 0)
        errors: List[str] = getattr(dialog, "errors", [])
        if created:
            Messagebox.show_info(f"{created} Produkte angelegt.", "Massenupload")
        if errors:
            Messagebox.show_warning("\n".join(errors), "Massenupload Hinweise")
        if created or errors:
            self.refresh()

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
        self.user: Optional[User] = None
        self.locations = self.db.list_locations()
        self.vehicle_models = self.db.list_vehicle_models()
        self.vehicle_categories = self.db.list_vehicle_categories()
        self.write_allowed = True

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        self.new_button = ttkb.Button(toolbar, text="Neu", command=self.create_vehicle, bootstyle="success")
        self.new_button.pack(side=LEFT)
        self.edit_button = ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_vehicle, bootstyle="secondary")
        self.edit_button.pack(side=LEFT, padx=5)
        self.lifecycle_button = ttkb.Button(
            toolbar,
            text="Lebenslauf",
            command=self.export_lifecycle,
            bootstyle="info",
        )
        self.lifecycle_button.pack(side=LEFT, padx=5)
        self.transfer_button = ttkb.Button(
            toolbar,
            text="Produkte umhängen",
            command=self.transfer_products,
            bootstyle="warning",
        )
        self.transfer_button.pack(side=LEFT, padx=5)

        self._write_buttons = [self.new_button, self.edit_button, self.transfer_button]

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

    def set_write_permissions(self, allowed: bool) -> None:
        self.write_allowed = allowed
        state = tk.NORMAL if allowed else tk.DISABLED
        for widget in self._write_buttons:
            widget.configure(state=state)

    def set_user(self, user: Optional[User]) -> None:
        self.user = user

    def _require_write(self) -> bool:
        if self.write_allowed:
            return True
        Messagebox.show_info("Sie haben keine Schreibrechte für Fahrzeuge.", "Keine Berechtigung")
        return False

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
        location_values = [
            "Alle"
        ] + [
            self.db.location_label(row["id"]) or f"Standort #{row['id']}"
            for row in self.locations
        ]
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
            status_label = display_status(row["status"])
            self.table.insert_row(
                values=(
                    row["id"],
                    row["name"],
                    vehicle_type,
                    vehicle_category,
                    location_label,
                    row["kennzeichen"] or "",
                    status_label,
                    row["kilometerstand"],
                )
            )

    def create_vehicle(self) -> None:
        if not self._require_write():
            return
        editor = VehicleEditor(self, self.db, user=self.user)
        self.wait_window(editor)
        if editor.saved:
            self.refresh()

    def edit_vehicle(self) -> None:
        if not self._require_write():
            return
        vehicle_id = self.selected_vehicle_id()
        if not vehicle_id:
            return
        editor = VehicleEditor(self, self.db, fahrzeug_id=vehicle_id, user=self.user)
        self.wait_window(editor)
        if editor.saved:
            self.refresh()

    def export_lifecycle(self) -> None:
        vehicle_id = self.selected_vehicle_id()
        if not vehicle_id:
            return
        filepath = filedialog.asksaveasfilename(
            title="Fahrzeug-Lebenslauf speichern",
            defaultextension=".html",
            filetypes=[("HTML", "*.html")],
        )
        if not filepath:
            return
        try:
            html = self.db.vehicle_lifecycle_report(vehicle_id)
        except ValueError as exc:
            Messagebox.show_error(str(exc), "Fehler")
            return
        Path(filepath).write_text(html, encoding="utf-8")
        Messagebox.show_info("Bericht erstellt", "Erfolg")

    def transfer_products(self) -> None:
        if not self._require_write():
            return
        dialog = VehicleTransferDialog(self, self.db, user=self.user)
        self.wait_window(dialog)
        moved = getattr(dialog, "moved", 0)
        if moved:
            Messagebox.show_info(f"{moved} Produkte übertragen.", "Fahrzeugtausch")
        elif moved == 0:
            errors = getattr(dialog, "error", "")
            if errors:
                Messagebox.show_warning(errors, "Fahrzeugtausch")
        if moved or getattr(dialog, "error", ""):
            self.refresh()

    def _format_location(self, row: sqlite3.Row) -> str:
        if "standort_id" in row.keys() and row["standort_id"]:
            label = self.db.location_label(int(row["standort_id"]))
            if label:
                return label
        if "standort_name" in row.keys() and row["standort_name"]:
            return row["standort_name"]
        return ""


class MaterialsView(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db
        self.user: Optional[User] = None
        self.write_allowed = True

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        self.new_button = ttkb.Button(toolbar, text="Neu", command=self.create_material, bootstyle="success")
        self.new_button.pack(side=LEFT)
        self.edit_button = ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_material, bootstyle="secondary")
        self.edit_button.pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Statistik", command=self.show_statistics, bootstyle="info").pack(
            side=LEFT, padx=5
        )

        self._write_buttons = [self.new_button, self.edit_button]

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

    def set_write_permissions(self, allowed: bool) -> None:
        self.write_allowed = allowed
        state = tk.NORMAL if allowed else tk.DISABLED
        for widget in self._write_buttons:
            widget.configure(state=state)

    def set_user(self, user: Optional[User]) -> None:
        self.user = user

    def _require_write(self) -> bool:
        if self.write_allowed:
            return True
        Messagebox.show_info("Sie haben keine Schreibrechte für Material.", "Keine Berechtigung")
        return False

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
        if not self._require_write():
            return
        editor = MaterialEditor(self, self.db)
        self.wait_window(editor)
        if editor.saved:
            self.refresh()

    def edit_material(self) -> None:
        if not self._require_write():
            return
        material_id = self.selected_material_id()
        if not material_id:
            return
        editor = MaterialEditor(self, self.db, material_id=material_id)
        self.wait_window(editor)
        if editor.saved:
            self.refresh()

    def show_statistics(self) -> None:
        stats = self.db.material_statistics()
        MaterialStatisticsDialog(self, stats)


class MaterialStatisticsDialog(LargeDialog):
    def __init__(self, master: tk.Misc, stats: Dict[str, Any]) -> None:
        super().__init__(master, min_width=520, min_height=420)
        self.title("Materialstatistik")

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(
            container,
            text=f"Materialien gesamt: {stats['total_items']}",
            font=("Inter", 12, "bold"),
        ).pack(anchor=W)
        ttkb.Label(
            container,
            text=f"Gesamtbestand: {stats['total_bestand']}",
            font=("Inter", 12, "bold"),
        ).pack(anchor=W, pady=(4, 0))
        ttkb.Label(
            container,
            text=f"Mit Verfallsdatum: {stats['expiring']}",
            font=("Inter", 11),
        ).pack(anchor=W, pady=(0, 10))

        table = Tableview(
            container,
            coldata=[{"text": "Kategorie"}, {"text": "Anzahl"}, {"text": "Bestand"}],
            rowdata=[],
            pagesize=8,
        )
        table.pack(fill=BOTH, expand=True)
        for name, count, stock in stats["categories"]:
            table.insert_row(values=(name, count, stock))

        ttkb.Button(container, text="Schließen", command=self.destroy, bootstyle="secondary").pack(
            pady=10
        )

        self.grab_set()


class AnalyticsView(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db
        self.vehicles: List[sqlite3.Row] = []
        self.locations: List[sqlite3.Row] = []
        self.vehicle_options: Dict[str, int] = {}

        summary_frame = ttkb.Frame(self)
        summary_frame.pack(fill=tk.X, padx=20, pady=15)
        self.total_label = ttkb.Label(summary_frame, text="Reparaturkosten gesamt: 0,00 €", font=("Inter", 14, "bold"))
        self.total_label.pack(anchor=W)

        tables_frame = ttkb.Frame(self)
        tables_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)

        status_frame = ttkb.Labelframe(tables_frame, text="Statusübersicht")
        status_frame.pack(fill=BOTH, expand=True, side=LEFT, padx=10, pady=10)
        self.status_table = Tableview(
            status_frame,
            coldata=[{"text": "Status"}, {"text": "Anzahl"}],
            rowdata=[],
            pagesize=10,
        )
        self.status_table.pack(fill=BOTH, expand=True)

        category_frame = ttkb.Labelframe(tables_frame, text="Reparaturkosten je Kategorie")
        category_frame.pack(fill=BOTH, expand=True, side=LEFT, padx=10, pady=10)
        self.category_table = Tableview(
            category_frame,
            coldata=[{"text": "Kategorie"}, {"text": "Summe"}],
            rowdata=[],
            pagesize=10,
        )
        self.category_table.pack(fill=BOTH, expand=True)

        vehicle_frame = ttkb.Labelframe(tables_frame, text="Reparaturkosten je Fahrzeug")
        vehicle_frame.pack(fill=BOTH, expand=True, side=LEFT, padx=10, pady=10)
        self.vehicle_table = Tableview(
            vehicle_frame,
            coldata=[{"text": "Fahrzeug"}, {"text": "Summe"}],
            rowdata=[],
            pagesize=10,
        )
        self.vehicle_table.pack(fill=BOTH, expand=True)

        export_frame = ttkb.Labelframe(self, text="Produktlisten drucken")
        export_frame.pack(fill=BOTH, expand=False, padx=20, pady=(5, 20))

        vehicle_export = ttkb.Frame(export_frame)
        vehicle_export.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Label(vehicle_export, text="Fahrzeug").pack(side=LEFT)
        self.vehicle_var = ttkb.StringVar()
        self.vehicle_combo = ttkb.Combobox(vehicle_export, textvariable=self.vehicle_var, state="readonly", width=40)
        self.vehicle_combo.pack(side=LEFT, padx=5)
        ttkb.Button(vehicle_export, text="Produkte drucken", command=self.export_vehicle_products, bootstyle="primary").pack(side=LEFT, padx=5)

        location_export = ttkb.Frame(export_frame)
        location_export.pack(fill=tk.X, padx=10, pady=(10, 5))

        self.land_var = ttkb.StringVar()
        self.bereich_var = ttkb.StringVar()
        self.bezirk_var = ttkb.StringVar()
        self.bezirksstelle_var = ttkb.StringVar()
        self.ortsstelle_var = ttkb.StringVar()

        ttkb.Label(location_export, text="Land").grid(row=0, column=0, sticky=W, padx=2, pady=2)
        self.land_combo = ttkb.Combobox(location_export, textvariable=self.land_var, state="readonly", width=22)
        self.land_combo.grid(row=0, column=1, sticky=W, padx=2)

        ttkb.Label(location_export, text="Bereich").grid(row=0, column=2, sticky=W, padx=2)
        self.bereich_combo = ttkb.Combobox(location_export, textvariable=self.bereich_var, state="readonly", width=22)
        self.bereich_combo.grid(row=0, column=3, sticky=W, padx=2)

        ttkb.Label(location_export, text="Bezirk").grid(row=1, column=0, sticky=W, padx=2, pady=2)
        self.bezirk_combo = ttkb.Combobox(location_export, textvariable=self.bezirk_var, state="readonly", width=22)
        self.bezirk_combo.grid(row=1, column=1, sticky=W, padx=2)

        ttkb.Label(location_export, text="Bezirksstelle").grid(row=1, column=2, sticky=W, padx=2)
        self.bezirksstelle_combo = ttkb.Combobox(location_export, textvariable=self.bezirksstelle_var, state="readonly", width=22)
        self.bezirksstelle_combo.grid(row=1, column=3, sticky=W, padx=2)

        ttkb.Label(location_export, text="Ortsstelle").grid(row=2, column=0, sticky=W, padx=2, pady=2)
        self.ortsstelle_combo = ttkb.Combobox(location_export, textvariable=self.ortsstelle_var, state="readonly", width=22)
        self.ortsstelle_combo.grid(row=2, column=1, sticky=W, padx=2)

        ttkb.Button(location_export, text="Standort drucken", command=self.export_location_products, bootstyle="primary").grid(row=2, column=3, sticky=W, padx=2, pady=5)

        for var in (
            self.land_var,
            self.bereich_var,
            self.bezirk_var,
            self.bezirksstelle_var,
        ):
            var.trace_add("write", self._update_location_options)

    @staticmethod
    def _format_currency(value: float) -> str:
        formatted = f"{value:,.2f}".replace(",", " ")
        return formatted.replace(".", ",") + " €"

    def refresh(self) -> None:
        total = self.db.repair_cost_total()
        self.total_label.configure(text=f"Reparaturkosten gesamt: {self._format_currency(total)}")

        for table in (self.status_table, self.category_table, self.vehicle_table):
            table.delete_rows()

        for status, count in self.db.product_status_counts().items():
            self.status_table.insert_row(values=(display_status(status), count))

        for kategorie, summe in self.db.repair_costs_by_category():
            self.category_table.insert_row(values=(kategorie, self._format_currency(summe)))

        for fahrzeug, summe in self.db.repair_costs_by_vehicle():
            self.vehicle_table.insert_row(values=(fahrzeug, self._format_currency(summe)))

        self.vehicles = self.db.list_vehicles()
        self.vehicle_options = {}
        vehicle_labels: List[str] = [""]
        for row in self.vehicles:
            label = row["name"]
            if row["kennzeichen"]:
                label += f" ({row['kennzeichen']})"
            vehicle_labels.append(label)
            self.vehicle_options[label] = row["id"]
        current_vehicle = self.vehicle_var.get()
        self.vehicle_combo.configure(values=vehicle_labels)
        if current_vehicle not in vehicle_labels:
            self.vehicle_var.set("")

        self.locations = self.db.list_locations()
        self._update_location_options()

    def _update_location_options(self, *_: object) -> None:
        land = self.land_var.get().strip()
        bereich = self.bereich_var.get().strip()
        bezirk = self.bezirk_var.get().strip()
        bezirksstelle = self.bezirksstelle_var.get().strip()

        land_values = sorted({row["land"] for row in self.locations if row["land"]})
        bereich_values = sorted(
            {
                row["bereich"]
                for row in self.locations
                if row["bereich"] and (not land or row["land"] == land)
            }
        )
        bezirk_values = sorted(
            {
                row["bezirk"]
                for row in self.locations
                if row["bezirk"]
                and (not land or row["land"] == land)
                and (not bereich or row["bereich"] == bereich)
            }
        )
        bezirksstelle_values = sorted(
            {
                row["bezirksstelle"]
                for row in self.locations
                if row["bezirksstelle"]
                and (not land or row["land"] == land)
                and (not bereich or row["bereich"] == bereich)
                and (not bezirk or row["bezirk"] == bezirk)
            }
        )
        ortsstelle_values = sorted(
            {
                row["ortsstelle"]
                for row in self.locations
                if row["ortsstelle"]
                and (not land or row["land"] == land)
                and (not bereich or row["bereich"] == bereich)
                and (not bezirk or row["bezirk"] == bezirk)
                and (not bezirksstelle or row["bezirksstelle"] == bezirksstelle)
            }
        )

        self.land_combo.configure(values=[""] + land_values)
        self.bereich_combo.configure(values=[""] + bereich_values)
        self.bezirk_combo.configure(values=[""] + bezirk_values)
        self.bezirksstelle_combo.configure(values=[""] + bezirksstelle_values)
        self.ortsstelle_combo.configure(values=[""] + ortsstelle_values)

        if land not in self.land_combo.cget("values"):
            self.land_var.set("")
        if bereich not in self.bereich_combo.cget("values"):
            self.bereich_var.set("")
        if bezirk not in self.bezirk_combo.cget("values"):
            self.bezirk_var.set("")
        if bezirksstelle not in self.bezirksstelle_combo.cget("values"):
            self.bezirksstelle_var.set("")
        if self.ortsstelle_var.get() not in self.ortsstelle_combo.cget("values"):
            self.ortsstelle_var.set("")

    def export_vehicle_products(self) -> None:
        label = self.vehicle_var.get().strip()
        if not label or label not in self.vehicle_options:
            Messagebox.show_info("Bitte ein Fahrzeug auswählen", "Hinweis")
            return
        fahrzeug_id = self.vehicle_options[label]
        filepath = filedialog.asksaveasfilename(
            title="Produkte nach Fahrzeug drucken",
            defaultextension=".html",
            filetypes=[("HTML", "*.html")],
        )
        if not filepath:
            return
        html = self.db.export_products_filtered_html(
            fahrzeug_id=fahrzeug_id,
            title=f"Produkte für {label}",
        )
        Path(filepath).write_text(html, encoding="utf-8")
        Messagebox.show_info("Export abgeschlossen", "Erfolg")

    def export_location_products(self) -> None:
        land = self.land_var.get().strip() or None
        bereich = self.bereich_var.get().strip() or None
        bezirk = self.bezirk_var.get().strip() or None
        bezirksstelle = self.bezirksstelle_var.get().strip() or None
        ortsstelle = self.ortsstelle_var.get().strip() or None

        if not any([land, bereich, bezirk, bezirksstelle, ortsstelle]):
            Messagebox.show_info("Bitte mindestens eine Ebene auswählen", "Hinweis")
            return

        filepath = filedialog.asksaveasfilename(
            title="Produkte nach Standort drucken",
            defaultextension=".html",
            filetypes=[("HTML", "*.html")],
        )
        if not filepath:
            return

        html = self.db.export_products_filtered_html(
            land=land,
            bereich=bereich,
            bezirk=bezirk,
            bezirksstelle=bezirksstelle,
            ortsstelle=ortsstelle,
            title="Produkte nach Standort",
        )
        Path(filepath).write_text(html, encoding="utf-8")
        Messagebox.show_info("Export abgeschlossen", "Erfolg")

class MasterDataView(ttkb.Frame):
    def __init__(
        self,
        master: tk.Misc,
        db: DatabaseManager,
        *,
        show_locations: bool = True,
        allow_edit_locations: bool = True,
    ) -> None:
        super().__init__(master)
        self.db = db

        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        nav_container = ttkb.Frame(self, padding=(10, 10, 0, 10))
        nav_container.grid(row=0, column=0, sticky=tk.NS)
        nav_container.rowconfigure(0, weight=1)

        self.nav = ttkb.Treeview(nav_container, show="tree", selectmode="browse", height=18)
        self.nav.grid(row=0, column=0, sticky=tk.NS)
        nav_scroll = ttkb.Scrollbar(nav_container, orient=tk.VERTICAL, command=self.nav.yview)
        nav_scroll.grid(row=0, column=1, sticky=tk.NS, padx=(4, 0))
        self.nav.configure(yscrollcommand=nav_scroll.set)

        self.content = ttkb.Frame(self, padding=(10, 10, 10, 10))
        self.content.grid(row=0, column=1, sticky=tk.NSEW)
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.frames: Dict[str, ttkb.Frame] = {}

        general = self.nav.insert("", "end", "general", text="Allgemein")
        product_group = self.nav.insert("", "end", "products", text="Produkte")
        vehicle_group = self.nav.insert("", "end", "vehicles", text="Fahrzeuge")
        support_group = self.nav.insert("", "end", "support", text="Support")
        if show_locations:
            locations_group = self.nav.insert("", "end", "locations", text="Standorte")
        else:
            locations_group = None

        for group in (general, product_group, vehicle_group, support_group):
            self.nav.item(group, open=True)
        if locations_group:
            self.nav.item(locations_group, open=True)

        self.categories_frame = CategoriesFrame(self.content, db)
        self._register_section("categories", general, "Kategorien", self.categories_frame)

        self.locations_frame: Optional[LocationsFrame] = None
        if show_locations:
            self.locations_frame = LocationsFrame(self.content, db)
            self.locations_frame.set_write_permissions(allow_edit_locations)
            self._register_section(
                "locations_section",
                locations_group or general,
                "Standortverwaltung",
                self.locations_frame,
            )

        self.contacts_frame = ContactsFrame(self.content, db)
        self._register_section("contacts", support_group, "Kontakte", self.contacts_frame)

        self.product_types_frame = ProductTypesFrame(self.content, db)
        self._register_section("product_types", product_group, "Produkttypen", self.product_types_frame)

        self.product_models_frame = ProductModelsFrame(self.content, db)
        self._register_section("product_models", product_group, "Produktmodelle", self.product_models_frame)

        self.product_manufacturers_frame = ProductManufacturersFrame(self.content, db)
        self._register_section("product_manufacturers", product_group, "Hersteller", self.product_manufacturers_frame)

        self.component_types_frame = ComponentTypesFrame(self.content, db)
        self._register_section("component_types", product_group, "Komponententypen", self.component_types_frame)

        self.maintenance_types_frame = MaintenanceTypesFrame(self.content, db)
        self._register_section("maintenance_types", product_group, "Wartungstypen", self.maintenance_types_frame)

        self.repair_types_frame = RepairTypesFrame(self.content, db)
        self._register_section("repair_types", product_group, "Reparaturarten", self.repair_types_frame)

        self.upload_categories_frame = UploadCategoriesFrame(self.content, db)
        self._register_section("upload_categories", support_group, "Upload-Kategorien", self.upload_categories_frame)

        self.retirement_reasons_frame = RetirementReasonsFrame(self.content, db)
        self._register_section(
            "retirement_reasons", product_group, "Ausscheidungsgründe", self.retirement_reasons_frame
        )

        self.material_names_frame = MaterialNamesFrame(self.content, db)
        self._register_section("material_names", general, "Materialbezeichnungen", self.material_names_frame)

        self.vehicle_brands_frame = VehicleBrandsFrame(self.content, db)
        self._register_section("vehicle_brands", vehicle_group, "Fahrzeugmarken", self.vehicle_brands_frame)

        self.vehicle_models_frame = VehicleModelsFrame(self.content, db)
        self._register_section("vehicle_models", vehicle_group, "Fahrzeugtypen", self.vehicle_models_frame)

        self.vehicle_categories_frame = VehicleCategoriesFrame(self.content, db)
        self._register_section("vehicle_categories", vehicle_group, "Fahrzeugkategorien", self.vehicle_categories_frame)

        self.users_frame = UsersFrame(self.content, db)
        self._register_section("users", support_group, "Benutzer", self.users_frame)

        self.nav.bind("<<TreeviewSelect>>", self._on_nav_select)

        self._initial_selection()

    def refresh(self) -> None:
        for frame in self.frames.values():
            if hasattr(frame, "refresh"):
                frame.refresh()  # type: ignore[call-arg]

    def _register_section(
        self,
        key: str,
        parent: Optional[str],
        label: str,
        frame: ttkb.Frame,
    ) -> None:
        frame.grid(row=0, column=0, sticky=tk.NSEW)
        frame.grid_remove()
        self.frames[key] = frame
        parent_id = parent if parent is not None else ""
        self.nav.insert(parent_id, "end", key, text=label)

    def _on_nav_select(self, _event: tk.Event) -> None:  # type: ignore[override]
        selection = self.nav.selection()
        if not selection:
            return
        item = selection[0]
        if item in self.frames:
            self._show_frame(item)
            return
        children = self.nav.get_children(item)
        if children:
            self.nav.selection_set(children[0])
            self._show_frame(children[0])

    def _show_frame(self, key: str) -> None:
        for frame_key, frame in self.frames.items():
            if frame_key == key:
                frame.grid()
            else:
                frame.grid_remove()

    def _initial_selection(self) -> None:
        # Choose the first available frame for display
        if self.frames:
            first_key = next(iter(self.frames))
            self.nav.selection_set(first_key)
            self._show_frame(first_key)



class CategoriesFrame(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Neue Kategorie", command=self.add_category, bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_category, bootstyle="secondary").pack(
            side=LEFT, padx=5
        )
        ttkb.Button(toolbar, text="Löschen", command=self.delete_category, bootstyle="danger").pack(side=LEFT)

        columns = [
            {"text": "ID"},
            {"text": "Name"},
            {"text": "Typ"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=20)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.table.bind("<Double-1>", lambda _event: self.edit_category())

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

    def selected_category(self) -> Optional[Tuple[int, str, str]]:
        rows = self.table.get_rows("selected")
        if not rows:
            Messagebox.show_info("Bitte eine Kategorie auswählen", "Hinweis")
            return None
        values = rows[0].values
        return int(values[0]), str(values[1]), str(values[2])

    def edit_category(self) -> None:
        selected = self.selected_category()
        if not selected:
            return
        category_id, name, typ = selected
        dialog = SimpleEntryDialog(self, "Kategorie bearbeiten", ["Name", "Typ (produkt/material)"], [name, typ])
        self.wait_window(dialog)
        if not dialog.result:
            return
        new_name, new_typ = dialog.result
        new_typ = new_typ.strip()
        if new_typ not in {"produkt", "material"}:
            Messagebox.show_error("Typ muss 'produkt' oder 'material' sein", "Fehler")
            return
        self.db.update_category(category_id, new_name.strip(), new_typ)
        self.refresh()

    def delete_category(self) -> None:
        selected = self.selected_category()
        if not selected:
            return
        category_id, _, _ = selected
        if Messagebox.okcancel("Kategorie wirklich löschen?", "Bestätigung", alert=True) != "OK":
            return
        try:
            self.db.delete_category(category_id)
        except sqlite3.IntegrityError as exc:
            Messagebox.show_error(str(exc), "Fehler")
            return
        self.refresh()


class LocationsFrame(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db
        self.write_allowed = True

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=(10, 0))
        self.add_button = ttkb.Button(toolbar, text="Neuer Standort", command=self.add_location, bootstyle="success")
        self.add_button.pack(side=LEFT)
        self.edit_button = ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_location, bootstyle="secondary")
        self.edit_button.pack(side=LEFT, padx=5)
        self.delete_button = ttkb.Button(toolbar, text="Löschen", command=self.delete_location, bootstyle="danger")
        self.delete_button.pack(side=LEFT)

        self._write_buttons = [self.add_button, self.edit_button, self.delete_button]

        filter_frame = ttkb.Labelframe(self, text="Filter")
        filter_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        self._all_locations: List[Dict[str, Any]] = []
        self._filter_vars: Dict[str, ttkb.StringVar] = {}
        filter_config = [
            ("Land", "land"),
            ("Bereich", "bereich"),
            ("Bezirk", "bezirk"),
            ("Bezirksstelle", "bezirksstelle"),
            ("Ortsstelle", "ortsstelle"),
            ("Funkkennung", "funkkennung"),
        ]
        for column, (label_text, data_key) in enumerate(filter_config):
            ttkb.Label(filter_frame, text=label_text).grid(row=0, column=column, sticky=W, padx=5, pady=(5, 2))
            var = ttkb.StringVar()
            entry = ttkb.Entry(filter_frame, textvariable=var, width=22)
            entry.grid(row=1, column=column, sticky=W, padx=5, pady=(0, 8))
            var.trace_add("write", self._on_filter_change)
            self._filter_vars[data_key] = var
            filter_frame.columnconfigure(column, weight=1)

        columns = [
            {"text": "ID"},
            {"text": "Land"},
            {"text": "Bereich"},
            {"text": "Bezirk"},
            {"text": "Bezirksstelle"},
            {"text": "Ortsstelle"},
            {"text": "Funkkennung"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=20)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)

    def set_write_permissions(self, allowed: bool) -> None:
        self.write_allowed = allowed
        state = tk.NORMAL if allowed else tk.DISABLED
        for widget in self._write_buttons:
            widget.configure(state=state)

    def _require_write(self) -> bool:
        if self.write_allowed:
            return True
        Messagebox.show_info("Sie haben keine Schreibrechte für Standorte.", "Keine Berechtigung")
        return False

    def refresh(self) -> None:
        self._all_locations = [
            {
                "id": row["id"],
                "land": row["land"],
                "bereich": row["bereich"],
                "bezirk": row["bezirk"],
                "bezirksstelle": row["bezirksstelle"],
                "ortsstelle": row["ortsstelle"],
                "funkkennung": row["funkkennung"],
            }
            for row in self.db.list_locations()
        ]
        self._apply_filter()

    def _on_filter_change(self, *_args: Any) -> None:
        self.after_idle(self._apply_filter)

    def _apply_filter(self) -> None:
        self.table.delete_rows()
        active_filters = {
            key: var.get().strip().lower()
            for key, var in self._filter_vars.items()
            if var.get().strip()
        }
        for row in self._all_locations:
            if not active_filters:
                matches = True
            else:
                matches = True
                for key, needle in active_filters.items():
                    haystack = (row.get(key) or "").lower()
                    if needle not in haystack:
                        matches = False
                        break
            if not matches:
                continue
            self.table.insert_row(
                values=(
                    row["id"],
                    row["land"] or "",
                    row["bereich"] or "",
                    row["bezirk"] or "",
                    row["bezirksstelle"] or "",
                    row["ortsstelle"] or "",
                    row.get("funkkennung") or "",
                )
            )

    def add_location(self) -> None:
        if not self._require_write():
            return
        templates = [dict(row) for row in self.db.list_locations()]
        dialog = LocationDialog(self, templates=templates)
        self.wait_window(dialog)
        if dialog.result:
            data = dialog.result
            self.db.add_location(
                data["land"],
                data["bereich"],
                data["bezirk"],
                data["bezirksstelle"],
                data["ortsstelle"],
                data["beschreibung"],
                funkkennung=data["funkkennung"],
            )
            self.refresh()

    def edit_location(self) -> None:
        if not self._require_write():
            return
        location_id = self._selected_location_id()
        if not location_id:
            return
        row = self.db.get_location(location_id)
        if not row:
            Messagebox.show_error("Standort nicht gefunden", "Fehler")
            return
        templates = [dict(entry) for entry in self.db.list_locations()]
        dialog = LocationDialog(self, data=row, templates=templates)
        self.wait_window(dialog)
        if not dialog.result:
            return
        data = dialog.result
        self.db.update_location(
            location_id,
            data["land"],
            data["bereich"],
            data["bezirk"],
            data["bezirksstelle"],
            data["ortsstelle"],
            data["beschreibung"],
            ist_fahrzeug=bool(row["ist_fahrzeug"]) if "ist_fahrzeug" in row.keys() else False,
            funkkennung=data["funkkennung"],
        )
        self.refresh()

    def delete_location(self) -> None:
        if not self._require_write():
            return
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
        ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_contact, bootstyle="secondary").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Löschen", command=self.delete_contact, bootstyle="danger").pack(side=LEFT)

        columns = [
            {"text": "ID"},
            {"text": "Name"},
            {"text": "Unternehmen"},
            {"text": "Telefon"},
            {"text": "E-Mail"},
            {"text": "Website"},
            {"text": "Kontaktperson"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=20)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.table.bind("<Double-1>", lambda _event: self.edit_contact())

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_contacts():
            self.table.insert_row(
                values=(
                    row["id"],
                    row["name"],
                    row["unternehmen"] or "",
                    row["telefon"] or "",
                    row["email"] or "",
                    row["website"] or "",
                    row["kontaktperson"] or "",
                )
            )

    def add_contact(self) -> None:
        dialog = ContactDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            data = dialog.result
            self.db.add_or_update_contact(
                kontakt_id=None,
                name=data["name"],
                adresse=data["adresse"],
                telefon=data["telefon"],
                email=data["email"],
                kontaktperson=data["kontaktperson"],
                unternehmen=data["unternehmen"],
                website=data["website"],
                info=data["info"],
            )
            self.refresh()

    def edit_contact(self) -> None:
        kontakt_id = self._selected_contact_id()
        if not kontakt_id:
            return
        contact = next((row for row in self.db.list_contacts() if row["id"] == kontakt_id), None)
        if not contact:
            Messagebox.show_error("Kontakt nicht gefunden", "Fehler")
            return
        dialog = ContactDialog(self, contact)
        self.wait_window(dialog)
        if not dialog.result:
            return
        data = dialog.result
        self.db.add_or_update_contact(
            kontakt_id=kontakt_id,
            name=data["name"],
            adresse=data["adresse"],
            telefon=data["telefon"],
            email=data["email"],
            kontaktperson=data["kontaktperson"],
            unternehmen=data["unternehmen"],
            website=data["website"],
            info=data["info"],
        )
        self.refresh()

    def delete_contact(self) -> None:
        kontakt_id = self._selected_contact_id()
        if not kontakt_id:
            return
        if Messagebox.okcancel("Kontakt wirklich löschen?", "Bestätigung", alert=True) != "OK":
            return
        self.db.delete_contact(kontakt_id)
        self.refresh()

    def _selected_contact_id(self) -> Optional[int]:
        rows = self.table.get_rows("selected")
        if not rows:
            Messagebox.show_info("Bitte einen Kontakt auswählen", "Hinweis")
            return None
        return int(rows[0].values[0])


class SimpleLookupFrame(ttkb.Frame):
    def __init__(
        self,
        master: tk.Misc,
        db: DatabaseManager,
        *,
        fetch_fn: Callable[[], List[sqlite3.Row]],
        add_fn: Callable[[str], int],
        delete_fn: Callable[[int], None],
        update_fn: Optional[Callable[[int, str], None]] = None,
        title: str,
        column_key: str = "name",
        label: str = "Name",
        suggestions: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(master)
        self.db = db
        self.fetch_fn = fetch_fn
        self.add_fn = add_fn
        self.delete_fn = delete_fn
        self.update_fn = update_fn
        self.column_key = column_key
        self.label = label
        self._suggestions: List[str] = list(dict.fromkeys(suggestions or []))

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Neu", command=self.add_entry, bootstyle="success").pack(side=LEFT)
        if self.update_fn:
            ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_entry, bootstyle="secondary").pack(
                side=LEFT, padx=5
            )
        ttkb.Button(toolbar, text="Löschen", command=self.delete_entry, bootstyle="danger").pack(side=LEFT, padx=5)

        if self._suggestions:
            suggestion_frame = ttkb.Frame(self)
            suggestion_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
            ttkb.Label(suggestion_frame, text=f"{label}-Vorschläge").pack(side=LEFT)
            self.suggestion_var = ttkb.StringVar()
            self.suggestion_box = SearchableCombobox(
                suggestion_frame,
                textvariable=self.suggestion_var,
                values=self._suggestions,
                width=40,
            )
            self.suggestion_box.pack(side=LEFT, padx=(8, 8))
            self.suggestion_box.set_completion_list(self._suggestions)
            ttkb.Button(
                suggestion_frame,
                text="Übernehmen",
                command=self.add_selected_suggestion,
                bootstyle="primary",
            ).pack(side=LEFT)

        columns = [
            {"text": "ID"},
            {"text": label},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=20)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)
        if self.update_fn:
            self.table.bind("<Double-1>", lambda _event: self.edit_entry())

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.fetch_fn():
            value = row[self.column_key] if self.column_key in row.keys() else ""
            self.table.insert_row(values=(row["id"], value))

    def add_selected_suggestion(self) -> None:
        value = getattr(self, "suggestion_var", ttkb.StringVar()).get().strip()
        if not value:
            Messagebox.show_warning(f"Bitte einen {self.label} auswählen", "Hinweis")
            return
        try:
            self.add_fn(value)
        except sqlite3.IntegrityError as exc:
            Messagebox.show_error(str(exc), "Fehler")
            return
        self.refresh()
        if hasattr(self, "suggestion_var"):
            self.suggestion_var.set("")

    def selected_id(self) -> Optional[int]:
        rows = self.table.get_rows("selected")
        if not rows:
            Messagebox.show_info("Bitte einen Eintrag auswählen", "Hinweis")
            return None
        return int(rows[0].values[0])

    def add_entry(self) -> None:
        dialog = SimpleEntryDialog(self, "Neuer Eintrag", [self.label])
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

    def edit_entry(self) -> None:
        if not self.update_fn:
            return
        entry_id = self.selected_id()
        if not entry_id:
            return
        rows = self.table.get_rows("selected")
        current_value = rows[0].values[1] if rows else ""
        dialog = SimpleEntryDialog(self, "Eintrag bearbeiten", [self.label], [current_value])
        self.wait_window(dialog)
        if not dialog.result:
            return
        new_value = dialog.result[0].strip()
        if not new_value:
            Messagebox.show_warning(f"{self.label} darf nicht leer sein", "Hinweis")
            return
        try:
            self.update_fn(entry_id, new_value)
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
            update_fn=db.update_product_type,
            title="Produkttypen",
            column_key="name",
            label="Produkttyp",
            suggestions=PRODUKT_VORSCHLAEGE,
        )


class ComponentTypesFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_component_types,
            add_fn=db.add_component_type,
            delete_fn=db.delete_component_type,
            update_fn=db.update_component_type,
            title="Komponententypen",
            column_key="name",
            label="Komponententyp",
            suggestions=KOMPONENTEN_VORSCHLAEGE,
        )


class MaintenanceTypesFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_maintenance_types,
            add_fn=db.add_maintenance_type,
            delete_fn=db.delete_maintenance_type,
            update_fn=db.update_maintenance_type,
            title="Wartungstypen",
            column_key="name",
            label="Wartungstyp",
        )


class RepairTypesFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_repair_types,
            add_fn=db.add_repair_type,
            delete_fn=db.delete_repair_type,
            update_fn=db.update_repair_type,
            title="Reparaturarten",
            column_key="name",
            label="Reparaturart",
        )


class RetirementReasonsFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_retirement_reasons,
            add_fn=db.add_retirement_reason,
            delete_fn=db.delete_retirement_reason,
            update_fn=db.update_retirement_reason,
            title="Ausscheidungsgründe",
            column_key="name",
            label="Grund",
            suggestions=AUSSCHEIDUNGSGRUND_VORSCHLAEGE,
        )


class UploadCategoriesFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_upload_categories,
            add_fn=db.add_upload_category,
            delete_fn=db.delete_upload_category,
            update_fn=db.update_upload_category,
            title="Upload-Kategorien",
            column_key="name",
            label="Kategorie",
            suggestions=REPARATUR_DATEI_KATEGORIEN,
        )


class MaterialNamesFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_material_names,
            add_fn=db.add_material_name,
            delete_fn=db.delete_material_name,
            update_fn=db.update_material_name,
            title="Materialbezeichnungen",
            column_key="name",
            label="Bezeichnung",
            suggestions=MATERIAL_VORSCHLAEGE,
        )


class VehicleBrandsFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_vehicle_brands,
            add_fn=db.add_vehicle_brand,
            delete_fn=db.delete_vehicle_brand,
            update_fn=db.update_vehicle_brand,
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
            update_fn=db.update_vehicle_category,
            title="Fahrzeugkategorien",
            column_key="name",
            label="Kategorie",
            suggestions=FAHRZEUG_KATEGORIEN,
        )


class ProductModelsFrame(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db
        self.product_types: List[sqlite3.Row] = []

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Neu", command=self.add_model, bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_model, bootstyle="secondary").pack(
            side=LEFT, padx=5
        )
        ttkb.Button(toolbar, text="Löschen", command=self.delete_model, bootstyle="danger").pack(side=LEFT, padx=5)

        columns = [
            {"text": "ID"},
            {"text": "Produkttyp"},
            {"text": "Modell"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=20)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.table.bind("<Double-1>", lambda _event: self.edit_model())

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

    def edit_model(self) -> None:
        model_id = self.selected_id()
        if not model_id:
            return
        model = next((row for row in self.db.list_product_models() if row["id"] == model_id), None)
        if not model:
            Messagebox.show_error("Modell nicht gefunden", "Fehler")
            return
        dialog = ProductModelDialog(self, self.product_types, existing=model)
        self.wait_window(dialog)
        if not dialog.result:
            return
        typ_id, name = dialog.result
        try:
            self.db.update_product_model(model_id, typ_id, name)
        except sqlite3.IntegrityError as exc:
            Messagebox.show_error(str(exc), "Fehler")
            return
        self.refresh()


class ProductManufacturersFrame(SimpleLookupFrame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(
            master,
            db,
            fetch_fn=db.list_product_manufacturers,
            add_fn=db.add_product_manufacturer,
            delete_fn=db.delete_product_manufacturer,
            update_fn=db.update_product_manufacturer,
            title="Hersteller",
            column_key="name",
            label="Hersteller",
            suggestions=HERSTELLER_VORSCHLAEGE,
        )


class VehicleModelsFrame(ttkb.Frame):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.db = db
        self.brands: List[sqlite3.Row] = []

        toolbar = ttkb.Frame(self)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        ttkb.Button(toolbar, text="Neu", command=self.add_model, bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Bearbeiten", command=self.edit_model, bootstyle="secondary").pack(
            side=LEFT, padx=5
        )
        ttkb.Button(toolbar, text="Löschen", command=self.delete_model, bootstyle="danger").pack(side=LEFT, padx=5)

        columns = [
            {"text": "ID"},
            {"text": "Marke"},
            {"text": "Modell"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=20)
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.table.bind("<Double-1>", lambda _event: self.edit_model())

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

    def edit_model(self) -> None:
        model_id = self.selected_id()
        if not model_id:
            return
        model = next((row for row in self.db.list_vehicle_models() if row["id"] == model_id), None)
        if not model:
            Messagebox.show_error("Modell nicht gefunden", "Fehler")
            return
        dialog = VehicleModelDialog(self, self.brands, existing=model)
        self.wait_window(dialog)
        if not dialog.result:
            return
        brand_id, name = dialog.result
        try:
            self.db.update_vehicle_model(model_id, brand_id, name)
        except sqlite3.IntegrityError as exc:
            Messagebox.show_error(str(exc), "Fehler")
            return
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
        dialog = UserDialog(self, self.db)
        self.wait_window(dialog)
        if not dialog.result:
            return
        vorname, nachname, dienstnummer, rolle, email = dialog.result
        try:
            self.db.add_or_update_user(
                benutzer_id=None,
                vorname=vorname,
                nachname=nachname,
                dienstnummer=dienstnummer,
                rolle=rolle,
                email=email,
                permissions=dialog.permissions,
                location_permissions=dialog.location_permissions,
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
        assigned_locations = self.db.list_user_location_permissions(row["id"])
        dialog = UserDialog(
            self,
            self.db,
            vorname=row["vorname"] or "",
            nachname=row["nachname"] or "",
            dienstnummer=row["dienstnummer"] or "",
            email=row["email"] or "",
            rolle=row["role"],
            permissions={column: bool(row[column]) for column in PERMISSION_COLUMNS},
            assigned_locations=assigned_locations,
        )
        self.wait_window(dialog)
        if not dialog.result:
            return
        vorname, nachname, dienstnummer, rolle, email = dialog.result
        try:
            self.db.add_or_update_user(
                benutzer_id=row["id"],
                vorname=vorname,
                nachname=nachname,
                dienstnummer=dienstnummer,
                rolle=rolle,
                email=email,
                permissions=dialog.permissions,
                location_permissions=dialog.location_permissions,
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


class LocationDialog(ttkb.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        data: Optional[sqlite3.Row] = None,
        *,
        templates: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(master)
        self.title("Standort")
        self.resizable(False, False)
        self.result: Optional[Dict[str, Any]] = None
        self._template_map: Dict[str, Dict[str, Any]] = {}

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        default_land = data["land"] if data and data["land"] else LAND_VORSCHLAEGE[0]
        self.land_var = ttkb.StringVar(value=default_land)
        self.bereich_var = ttkb.StringVar(value=(data["bereich"] if data else ""))
        self.bezirk_var = ttkb.StringVar(value=(data["bezirk"] if data else ""))
        self.bezirksstelle_var = ttkb.StringVar(value=(data["bezirksstelle"] if data else ""))
        self.ortsstelle_var = ttkb.StringVar(value=(data["ortsstelle"] if data else ""))
        self.funkkennung_var = ttkb.StringVar(value=(data["funkkennung"] if data else ""))
        self._initial_is_vehicle = bool(data["ist_fahrzeug"]) if data and "ist_fahrzeug" in data.keys() else False

        templates = templates or []
        if templates:
            template_labels: List[str] = []
            for entry in templates:
                label = self._format_template(entry)
                if label:
                    template_labels.append(label)
                    self._template_map[label] = entry
            if template_labels:
                ttkb.Label(container, text="Bekannter Standort").grid(row=0, column=0, sticky=W, pady=5)
                self.template_var = ttkb.StringVar()
                self.template_box = SearchableCombobox(
                    container,
                    textvariable=self.template_var,
                    values=template_labels,
                    width=32,
                    match_mode="contains",
                )
                self.template_box.grid(row=0, column=1, sticky=W)
                self.template_box.set_completion_list(template_labels)
                self.template_box.bind("<<ComboboxSelected>>", self._on_template_selected)

        base_row = 1 if templates else 0

        ttkb.Label(container, text="Land").grid(row=base_row, column=0, sticky=W, pady=5)
        self.land_box = SearchableCombobox(
            container,
            textvariable=self.land_var,
            values=LAND_VORSCHLAEGE,
            width=32,
            match_mode="prefix",
        )
        self.land_box.grid(row=base_row, column=1, sticky=W)
        self.land_box.set_completion_list(LAND_VORSCHLAEGE)

        ttkb.Label(container, text="Bereich").grid(row=base_row + 1, column=0, sticky=W, pady=5)
        self.bereich_box = SearchableCombobox(
            container,
            textvariable=self.bereich_var,
            values=BEREICH_VORSCHLAEGE,
            width=32,
            match_mode="prefix",
        )
        self.bereich_box.grid(row=base_row + 1, column=1, sticky=W)
        self.bereich_box.set_completion_list(BEREICH_VORSCHLAEGE)
        self.bereich_var.trace_add("write", lambda *_: self._refresh_bezirk_choices())

        ttkb.Label(container, text="Bezirk").grid(row=base_row + 2, column=0, sticky=W, pady=5)
        self.bezirk_box = SearchableCombobox(
            container,
            textvariable=self.bezirk_var,
            values=self._bezirk_choices(self.bereich_var.get()),
            width=32,
        )
        self.bezirk_box.grid(row=base_row + 2, column=1, sticky=W)
        self.bezirk_box.set_completion_list(self._bezirk_choices(self.bereich_var.get()))

        ttkb.Label(container, text="Bezirksstelle").grid(row=base_row + 3, column=0, sticky=W, pady=5)
        self.bezirksstelle_box = SearchableCombobox(
            container,
            textvariable=self.bezirksstelle_var,
            values=BEZIRKSSTELLEN_VORSCHLAEGE,
            width=32,
        )
        self.bezirksstelle_box.grid(row=base_row + 3, column=1, sticky=W)
        self.bezirksstelle_box.set_completion_list(BEZIRKSSTELLEN_VORSCHLAEGE)
        self.bezirksstelle_box.bind("<<ComboboxSelected>>", self._on_bezirksstelle_selected)

        ttkb.Label(container, text="Ortsstelle").grid(row=base_row + 4, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.ortsstelle_var, width=34).grid(
            row=base_row + 4, column=1, sticky=W
        )

        ttkb.Label(container, text="Beschreibung").grid(row=base_row + 5, column=0, sticky=W, pady=5)
        self.description_text = tk.Text(container, width=32, height=4, wrap="word")
        self.description_text.grid(row=base_row + 5, column=1, sticky=W)
        if data and data["beschreibung"]:
            self.description_text.insert(tk.END, data["beschreibung"])

        ttkb.Label(container, text="Funkkennung").grid(row=base_row + 6, column=0, sticky=W, pady=5)
        self.funkkennung_entry = ttkb.Entry(container, textvariable=self.funkkennung_var, width=28)
        self.funkkennung_entry.grid(row=base_row + 6, column=1, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=base_row + 7, column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self._on_save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.grab_set()

    def _bezirk_choices(self, bereich: str) -> List[str]:
        if not bereich:
            return BEZIRK_VORSCHLAEGE
        return [bezirk for bezirk, area in BEZIRK_TO_BEREICH.items() if area == bereich]

    def _refresh_bezirk_choices(self) -> None:
        options = self._bezirk_choices(self.bereich_var.get().strip())
        self.bezirk_box.set_completion_list(options)
        if self.bezirk_var.get() and self.bezirk_var.get() not in options:
            self.bezirk_var.set(options[0] if options else "")

    def _format_template(self, entry: Dict[str, Any]) -> str:
        parts = [
            entry.get("land") or "",
            entry.get("bereich") or "",
            entry.get("bezirk") or "",
            entry.get("bezirksstelle") or "",
            entry.get("ortsstelle") or "",
        ]
        label = " / ".join([part for part in parts if part])
        if entry.get("funkkennung"):
            label = f"{label} ({entry['funkkennung']})" if label else entry["funkkennung"]
        return label

    def _on_template_selected(self, _event: tk.Event) -> None:  # type: ignore[override]
        label = getattr(self, "template_var", ttkb.StringVar()).get()
        template = self._template_map.get(label)
        if not template:
            return
        self._apply_template(template)

    def _apply_template(self, template: Dict[str, Any]) -> None:
        self.land_var.set(template.get("land", LAND_VORSCHLAEGE[0]))
        self.bereich_var.set(template.get("bereich", ""))
        self._refresh_bezirk_choices()
        self.bezirk_var.set(template.get("bezirk", ""))
        self.bezirksstelle_var.set(template.get("bezirksstelle", ""))
        self.ortsstelle_var.set(template.get("ortsstelle", ""))
        self.description_text.delete("1.0", tk.END)
        if template.get("beschreibung"):
            self.description_text.insert(tk.END, template.get("beschreibung", ""))
        if "ist_fahrzeug" in template:
            self._initial_is_vehicle = bool(template.get("ist_fahrzeug"))
        if template.get("funkkennung"):
            self.funkkennung_var.set(template.get("funkkennung", ""))

    def _on_bezirksstelle_selected(self, _event: tk.Event) -> None:  # type: ignore[override]
        name = self.bezirksstelle_var.get().strip()
        if not name:
            return
        info = BEZIRKSSTELLEN_INFO.get(name)
        if info:
            bezirk = BEZIRKSSTELLE_TO_BEZIRK.get(name, "")
            bereich = BEZIRK_TO_BEREICH.get(bezirk, "")
            if bereich:
                self.bereich_var.set(bereich)
            if bezirk:
                self.bezirk_var.set(bezirk)
            self._refresh_bezirk_choices()
            self.description_text.delete("1.0", tk.END)
            self.description_text.insert(tk.END, info.get("beschreibung", ""))

    def _on_save(self) -> None:
        land = self.land_var.get().strip() or LAND_VORSCHLAEGE[0]
        bereich = self.bereich_var.get().strip()
        bezirk = self.bezirk_var.get().strip()
        bezirksstelle = self.bezirksstelle_var.get().strip()
        ortsstelle = self.ortsstelle_var.get().strip()
        beschreibung = self.description_text.get("1.0", tk.END).strip()
        funkkennung = self.funkkennung_var.get().strip()

        self.result = {
            "land": land,
            "bereich": bereich,
            "bezirk": bezirk,
            "bezirksstelle": bezirksstelle,
            "ortsstelle": ortsstelle,
            "beschreibung": beschreibung,
            "ist_fahrzeug": self._initial_is_vehicle,
            "funkkennung": funkkennung,
        }
        self.destroy()

class ContactDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, data: Optional[sqlite3.Row] = None) -> None:
        super().__init__(master)
        self.title("Kontakt")
        self.resizable(False, False)
        self.result: Optional[Dict[str, str]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        self.name_var = ttkb.StringVar(value=(data["name"] if data else ""))
        self.company_var = ttkb.StringVar(value=(data["unternehmen"] if data else ""))
        self.address_var = ttkb.StringVar(value=(data["adresse"] if data else ""))
        self.phone_var = ttkb.StringVar(value=(data["telefon"] if data else ""))
        self.mail_var = ttkb.StringVar(value=(data["email"] if data else ""))
        self.website_var = ttkb.StringVar(value=(data["website"] if data else ""))
        self.contact_person_var = ttkb.StringVar(value=(data["kontaktperson"] if data else ""))

        ttkb.Label(container, text="Name*").grid(row=0, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.name_var, width=40).grid(row=0, column=1, sticky=W)

        ttkb.Label(container, text="Unternehmen").grid(row=1, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.company_var, width=40).grid(row=1, column=1, sticky=W)

        ttkb.Label(container, text="Adresse").grid(row=2, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.address_var, width=40).grid(row=2, column=1, sticky=W)

        ttkb.Label(container, text="Telefon").grid(row=3, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.phone_var, width=40).grid(row=3, column=1, sticky=W)

        ttkb.Label(container, text="E-Mail").grid(row=4, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.mail_var, width=40).grid(row=4, column=1, sticky=W)

        ttkb.Label(container, text="Website").grid(row=5, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.website_var, width=40).grid(row=5, column=1, sticky=W)

        ttkb.Label(container, text="Kontaktperson").grid(row=6, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.contact_person_var, width=40).grid(row=6, column=1, sticky=W)

        ttkb.Label(container, text="Info").grid(row=7, column=0, sticky=W, pady=5)
        self.info_text = tk.Text(container, height=4, width=38, wrap="word")
        self.info_text.grid(row=7, column=1, sticky=W)
        if data and data["info"]:
            self.info_text.insert(tk.END, data["info"])

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=8, column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.grab_set()

    def on_save(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            Messagebox.show_warning("Bitte einen Namen angeben", "Hinweis")
            return
        self.result = {
            "name": name,
            "unternehmen": self.company_var.get().strip(),
            "adresse": self.address_var.get().strip(),
            "telefon": self.phone_var.get().strip(),
            "email": self.mail_var.get().strip(),
            "website": self.website_var.get().strip(),
            "kontaktperson": self.contact_person_var.get().strip(),
            "info": self.info_text.get("1.0", tk.END).strip(),
        }
        self.destroy()

class ProductModelDialog(ttkb.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        product_types: List[sqlite3.Row],
        existing: Optional[sqlite3.Row] = None,
    ) -> None:
        super().__init__(master)
        self.title("Produktmodell")
        self.resizable(False, False)
        self.result: Optional[Tuple[int, str]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text="Produkttyp").grid(row=0, column=0, sticky=W, pady=5)
        self.type_var = ttkb.StringVar()
        self.types = product_types
        type_box = ttkb.Combobox(
            container,
            textvariable=self.type_var,
            values=[row["name"] for row in product_types],
            state="readonly",
            width=30,
        )
        type_box.grid(row=0, column=1, sticky=W)
        if product_types and not self.type_var.get():
            self.type_var.set(product_types[0]["name"])

        ttkb.Label(container, text="Modellname").grid(row=1, column=0, sticky=W, pady=5)
        self.name_var = ttkb.StringVar()
        self.name_box = SearchableCombobox(
            container,
            textvariable=self.name_var,
            values=TYP_MODELL_VORSCHLAEGE,
            width=34,
        )
        self.name_box.grid(row=1, column=1, sticky=W)
        self.name_box.set_completion_list(TYP_MODELL_VORSCHLAEGE)

        if existing:
            keys = set(existing.keys())
            type_name = ""
            if "typ_name" in keys:
                type_name = existing["typ_name"] or ""
            elif "typ" in keys:
                type_name = existing["typ"] or ""
            if type_name:
                self.type_var.set(type_name)
            if "name" in keys:
                self.name_var.set(existing["name"] or "")

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
    def __init__(
        self,
        master: tk.Misc,
        brands: List[sqlite3.Row],
        existing: Optional[sqlite3.Row] = None,
    ) -> None:
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
        brand_box = ttkb.Combobox(
            container,
            textvariable=self.brand_var,
            values=values,
            state="readonly",
            width=30,
        )
        brand_box.grid(row=0, column=1, sticky=W)
        self.brand_var.set(values[0])

        ttkb.Label(container, text="Modellname").grid(row=1, column=0, sticky=W, pady=5)
        self.name_var = ttkb.StringVar()
        ttkb.Entry(container, textvariable=self.name_var, width=32).grid(row=1, column=1, sticky=W)

        if existing:
            keys = set(existing.keys())
            brand_name = ""
            if "marke_name" in keys:
                brand_name = existing["marke_name"] or ""
            elif "marke" in keys:
                brand_name = existing["marke"] or ""
            if brand_name and brand_name in values:
                self.brand_var.set(brand_name)
            if "name" in keys:
                self.name_var.set(existing["name"] or "")

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
        db: DatabaseManager,
        *,
        vorname: str = "",
        nachname: str = "",
        dienstnummer: str = "",
        email: str = "",
        rolle: str = "benutzer",
        permissions: Optional[Dict[str, bool]] = None,
        assigned_locations: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(master)
        self.title("Benutzer")
        self.resizable(False, False)
        self.result: Optional[Tuple[str, str, str, str, str]] = None
        self.permissions: Dict[str, bool] = {}
        self.db = db
        self.locations = db.list_locations()
        self._location_labels: Dict[int, str] = {
            row["id"]: self._format_location(row) for row in self.locations
        }
        self.location_permissions: Dict[int, Dict[str, bool]] = {}
        if assigned_locations:
            for entry in assigned_locations:
                standort_id = entry["standort_id"]
                self.location_permissions[standort_id] = {
                    "lesen": bool(entry["lesen"]),
                    "schreiben": bool(entry["schreiben"]),
                }
                if standort_id not in self._location_labels:
                    self._location_labels[standort_id] = entry.get("label") or f"Standort #{standort_id}"

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

        ttkb.Label(container, text="E-Mail").grid(row=3, column=0, sticky=W, pady=5)
        self.email_var = ttkb.StringVar(value=email)
        ttkb.Entry(container, textvariable=self.email_var, width=30).grid(row=3, column=1, sticky=W)

        ttkb.Label(container, text="Rolle").grid(row=4, column=0, sticky=W, pady=5)
        self.rolle_var = ttkb.StringVar(value=rolle)
        ttkb.Combobox(
            container,
            textvariable=self.rolle_var,
            values=["admin", "benutzer"],
            state="readonly",
            width=28,
        ).grid(row=4, column=1, sticky=W)

        permission_values = PERMISSION_DEFAULTS.copy()
        if permissions:
            for key, value in permissions.items():
                if key in permission_values:
                    permission_values[key] = bool(value)

        self.permission_vars: Dict[str, Tuple[ttkb.BooleanVar, ttkb.BooleanVar]] = {}
        permissions_frame = ttkb.Labelframe(container, text="Modul-Berechtigungen")
        permissions_frame.grid(row=5, column=0, columnspan=2, sticky=W + tk.E, pady=(15, 0))

        for index, (module, label) in enumerate(PERMISSION_MODULES):
            read_var = ttkb.BooleanVar(value=permission_values[f"{module}_lesen"])
            write_var = ttkb.BooleanVar(value=permission_values[f"{module}_schreiben"])
            self.permission_vars[module] = (read_var, write_var)
            ttkb.Checkbutton(
                permissions_frame,
                text=f"{label} lesen",
                variable=read_var,
                bootstyle="round-toggle",
            ).grid(row=index, column=0, sticky=W, padx=5, pady=3)
            ttkb.Checkbutton(
                permissions_frame,
                text=f"{label} schreiben",
                variable=write_var,
                bootstyle="round-toggle",
            ).grid(row=index, column=1, sticky=W, padx=5, pady=3)
            write_var.trace_add(
                "write",
                lambda *_args, r_var=read_var, w_var=write_var: self._on_write_toggle(r_var, w_var),
            )

        location_frame = ttkb.Labelframe(container, text="Standort-Berechtigungen")
        location_frame.grid(row=6, column=0, columnspan=2, sticky=W + tk.E, pady=(15, 0))

        self.location_tree = ttkb.Treeview(
            location_frame,
            columns=("standort", "lesen", "schreiben"),
            show="headings",
            height=6,
        )
        self.location_tree.heading("standort", text="Standort")
        self.location_tree.heading("lesen", text="Lesen")
        self.location_tree.heading("schreiben", text="Schreiben")
        self.location_tree.column("standort", width=280)
        self.location_tree.column("lesen", width=100, anchor=tk.CENTER)
        self.location_tree.column("schreiben", width=120, anchor=tk.CENTER)
        self.location_tree.pack(fill=BOTH, expand=True, padx=5, pady=5)

        location_buttons = ttkb.Frame(location_frame)
        location_buttons.pack(fill=tk.X, padx=5, pady=(0, 5))
        ttkb.Button(
            location_buttons,
            text="Hinzufügen",
            command=self.add_location_permission,
            bootstyle="success",
        ).pack(side=LEFT, padx=2)
        ttkb.Button(
            location_buttons,
            text="Bearbeiten",
            command=self.edit_location_permission,
            bootstyle="secondary",
        ).pack(side=LEFT, padx=2)
        ttkb.Button(
            location_buttons,
            text="Entfernen",
            command=self.remove_location_permission,
            bootstyle="danger",
        ).pack(side=LEFT, padx=2)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=7, column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        self._refresh_location_table()
        self.grab_set()

    def _format_location(self, row: sqlite3.Row) -> str:
        parts = [
            row["land"],
            row["bereich"],
            row["bezirk"],
            row["bezirksstelle"],
            row["ortsstelle"],
        ]
        label = " / ".join([part for part in parts if part])
        if not label:
            label = f"Standort #{row['id']}"
        return label

    def _refresh_location_table(self) -> None:
        for item in self.location_tree.get_children():
            self.location_tree.delete(item)
        for standort_id, flags in sorted(self.location_permissions.items(), key=lambda item: self._location_labels.get(item[0], "")):
            label = self._location_labels.get(standort_id, f"Standort #{standort_id}")
            lesen_text = "Ja" if flags.get("lesen") else "Nein"
            schreiben_text = "Ja" if flags.get("schreiben") else "Nein"
            self.location_tree.insert(
                "",
                tk.END,
                iid=str(standort_id),
                values=(label, lesen_text, schreiben_text),
            )

    def _available_location_choices(self) -> List[Tuple[int, str]]:
        choices: List[Tuple[int, str]] = []
        for row in self.locations:
            label = self._location_labels.get(row["id"], self._format_location(row))
            if row["id"] not in self.location_permissions:
                choices.append((row["id"], label))
        choices.sort(key=lambda item: item[1])
        return choices

    def _selected_location_id(self) -> Optional[int]:
        selection = self.location_tree.selection()
        if not selection:
            Messagebox.show_info("Bitte einen Standort auswählen", "Hinweis")
            return None
        return int(selection[0])

    def add_location_permission(self) -> None:
        choices = self._available_location_choices()
        if not choices:
            Messagebox.show_info("Alle Standorte sind bereits zugewiesen.", "Hinweis")
            return
        dialog = LocationPermissionDialog(self, choices)
        self.wait_window(dialog)
        if not dialog.result:
            return
        standort_id, lesen, schreiben = dialog.result
        self.location_permissions[standort_id] = {"lesen": lesen, "schreiben": schreiben}
        self._refresh_location_table()

    def edit_location_permission(self) -> None:
        standort_id = self._selected_location_id()
        if standort_id is None:
            return
        current = self.location_permissions.get(standort_id, {"lesen": True, "schreiben": False})
        label = self._location_labels.get(standort_id, f"Standort #{standort_id}")
        dialog = LocationPermissionDialog(
            self,
            [(standort_id, label)],
            selected_id=standort_id,
            lesen=current.get("lesen", True),
            schreiben=current.get("schreiben", False),
            allow_location_change=False,
        )
        self.wait_window(dialog)
        if not dialog.result:
            return
        _standort_id, lesen, schreiben = dialog.result
        self.location_permissions[standort_id] = {"lesen": lesen, "schreiben": schreiben}
        self._refresh_location_table()

    def remove_location_permission(self) -> None:
        standort_id = self._selected_location_id()
        if standort_id is None:
            return
        self.location_permissions.pop(standort_id, None)
        self._refresh_location_table()

    def on_save(self) -> None:
        vorname = self.vorname_var.get().strip()
        nachname = self.nachname_var.get().strip()
        dienstnummer = self.dienstnummer_var.get().strip()
        if not vorname or not nachname or not dienstnummer:
            Messagebox.show_warning("Bitte alle Felder ausfüllen", "Hinweis")
            return
        rolle = self.rolle_var.get() or "benutzer"
        email = self.email_var.get().strip()
        permission_map: Dict[str, bool] = {}
        for module, (read_var, write_var) in self.permission_vars.items():
            permission_map[f"{module}_lesen"] = bool(read_var.get())
            permission_map[f"{module}_schreiben"] = bool(write_var.get())
        self.permissions = permission_map
        self.result = (vorname, nachname, dienstnummer, rolle, email)
        self.destroy()

    @staticmethod
    def _on_write_toggle(read_var: ttkb.BooleanVar, write_var: ttkb.BooleanVar) -> None:
        if write_var.get() and not read_var.get():
            read_var.set(True)


class LocationPermissionDialog(ttkb.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        choices: List[Tuple[int, str]],
        *,
        selected_id: Optional[int] = None,
        lesen: bool = True,
        schreiben: bool = False,
        allow_location_change: bool = True,
    ) -> None:
        super().__init__(master)
        self.title("Standortberechtigung")
        self.resizable(False, False)
        self.result: Optional[Tuple[int, bool, bool]] = None
        self._choices = choices
        self._allow_location_change = allow_location_change
        self._selected_location: Optional[int] = selected_id

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text="Standort").grid(row=0, column=0, sticky=W, pady=5)
        if allow_location_change:
            self.location_var = ttkb.StringVar()
            self._choice_map = {}
            values: List[str] = []
            for standort_id, label in choices:
                display = label or f"Standort #{standort_id}"
                self._choice_map[display] = standort_id
                values.append(display)
                if selected_id == standort_id:
                    self.location_var.set(display)
            if not self.location_var.get() and values:
                self.location_var.set(values[0])
            ttkb.Combobox(
                container,
                textvariable=self.location_var,
                values=values,
                state="readonly",
                width=35,
            ).grid(row=0, column=1, sticky=W)
        else:
            label = next((label for standort_id, label in choices if standort_id == selected_id), "")
            self.location_var = ttkb.StringVar(value=label)
            ttkb.Entry(container, textvariable=self.location_var, width=35, state="readonly").grid(
                row=0, column=1, sticky=W
            )

        ttkb.Label(container, text="Lesen").grid(row=1, column=0, sticky=W, pady=5)
        self.read_var = ttkb.BooleanVar(value=lesen)
        ttkb.Checkbutton(container, variable=self.read_var, bootstyle="round-toggle").grid(
            row=1, column=1, sticky=W
        )

        ttkb.Label(container, text="Schreiben").grid(row=2, column=0, sticky=W, pady=5)
        self.write_var = ttkb.BooleanVar(value=schreiben)
        write_box = ttkb.Checkbutton(container, variable=self.write_var, bootstyle="round-toggle")
        write_box.grid(row=2, column=1, sticky=W)
        self.write_var.trace_add("write", lambda *_args: self._ensure_write_implies_read())

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.grab_set()

    def _ensure_write_implies_read(self) -> None:
        if self.write_var.get() and not self.read_var.get():
            self.read_var.set(True)

    def on_save(self) -> None:
        if self._allow_location_change:
            label = self.location_var.get()
            standort_id = self._choice_map.get(label)
            if standort_id is None:
                Messagebox.show_warning("Bitte einen Standort auswählen", "Hinweis")
                return
        else:
            standort_id = self._selected_location
        if standort_id is None:
            Messagebox.show_warning("Kein Standort ausgewählt", "Hinweis")
            return
        lesen = bool(self.read_var.get())
        schreiben = bool(self.write_var.get())
        if schreiben and not lesen:
            lesen = True
        self.result = (standort_id, lesen, schreiben)
        self.destroy()

class RetireProductDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, reasons: Sequence[str]) -> None:
        super().__init__(master)
        self.title("Produkt ausscheiden")
        self.resizable(False, False)
        self.result: Optional[Tuple[str, str]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text="Datum (TT.MM.JJJJ)").grid(row=0, column=0, sticky=W, pady=5)
        self.date_var = ttkb.StringVar(value=date.today().strftime(DATE_FORMAT))
        self.date_entry = DateEntry(
            container,
            dateformat=DATE_FORMAT,
            width=18,
        )
        self.date_entry.grid(row=0, column=1, sticky=W)
        bind_date_entry(self.date_entry, self.date_var)

        ttkb.Label(container, text="Grund").grid(row=1, column=0, sticky=W, pady=5)
        self.reason_var = ttkb.StringVar()
        self.reasons = list(reasons)
        self.reason_box = SearchableCombobox(
            container,
            textvariable=self.reason_var,
            values=self.reasons,
            width=38,
            match_mode="contains",
        )
        self.reason_box.grid(row=1, column=1, sticky=W)
        self.reason_box.set_completion_list(self.reasons)

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


class PasswordChangeDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.title("Passwort ändern")
        self.resizable(False, False)
        self.result: Optional[Tuple[str, str]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text="Aktuelles Passwort").grid(row=0, column=0, sticky=W, pady=5)
        self.old_var = ttkb.StringVar()
        ttkb.Entry(container, textvariable=self.old_var, show="*", width=30).grid(row=0, column=1, sticky=W)

        ttkb.Label(container, text="Neues Passwort").grid(row=1, column=0, sticky=W, pady=5)
        self.new_var = ttkb.StringVar()
        ttkb.Entry(container, textvariable=self.new_var, show="*", width=30).grid(row=1, column=1, sticky=W)

        ttkb.Label(container, text="Bestätigung").grid(row=2, column=0, sticky=W, pady=5)
        self.confirm_var = ttkb.StringVar()
        ttkb.Entry(container, textvariable=self.confirm_var, show="*", width=30).grid(row=2, column=1, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(15, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.grab_set()

    def on_save(self) -> None:
        old = self.old_var.get()
        new = self.new_var.get()
        confirm = self.confirm_var.get()
        if not old or not new:
            Messagebox.show_warning("Bitte alle Felder ausfüllen", "Hinweis")
            return
        if new != confirm:
            Messagebox.show_warning("Neue Passwörter stimmen nicht überein", "Hinweis")
            return
        self.result = (old, new)
        self.destroy()


class AccountDialog(ttkb.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        db: DatabaseManager,
        *,
        user_id: int,
        vorname: str,
        nachname: str,
        email: str,
        language: str,
        theme: str,
    ) -> None:
        super().__init__(master)
        self.title("Mein Konto")
        self.resizable(False, False)
        self.result: Optional[Tuple[str, str, str, str, str]] = None
        self.db = db
        self.user_id = user_id

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text="Vorname").grid(row=0, column=0, sticky=W, pady=5)
        self.vorname_var = ttkb.StringVar(value=vorname)
        ttkb.Entry(container, textvariable=self.vorname_var, width=30).grid(row=0, column=1, sticky=W)

        ttkb.Label(container, text="Nachname").grid(row=1, column=0, sticky=W, pady=5)
        self.nachname_var = ttkb.StringVar(value=nachname)
        ttkb.Entry(container, textvariable=self.nachname_var, width=30).grid(row=1, column=1, sticky=W)

        ttkb.Label(container, text="E-Mail").grid(row=2, column=0, sticky=W, pady=5)
        self.email_var = ttkb.StringVar(value=email)
        ttkb.Entry(container, textvariable=self.email_var, width=30).grid(row=2, column=1, sticky=W)

        ttkb.Label(container, text="Sprache").grid(row=3, column=0, sticky=W, pady=5)
        self.language_var = ttkb.StringVar(value=language)
        ttkb.Combobox(
            container,
            textvariable=self.language_var,
            values=["de", "en"],
            width=28,
            state="readonly",
        ).grid(row=3, column=1, sticky=W)

        ttkb.Label(container, text="Theme").grid(row=4, column=0, sticky=W, pady=5)
        self.theme_var = ttkb.StringVar(value=theme)
        ttkb.Combobox(
            container,
            textvariable=self.theme_var,
            values=sorted(master.style.theme_names()),
            width=28,
            state="readonly",
        ).grid(row=4, column=1, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=5, column=0, columnspan=2, pady=(15, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.grab_set()

    def on_save(self) -> None:
        vorname = self.vorname_var.get().strip()
        nachname = self.nachname_var.get().strip()
        if not vorname or not nachname:
            Messagebox.show_warning("Vor- und Nachname sind erforderlich", "Hinweis")
            return
        email = self.email_var.get().strip()
        language = self.language_var.get() or "de"
        theme = self.theme_var.get() or "flatly"
        self.result = (vorname, nachname, email, language, theme)
        self.destroy()


class GlobalSearchDialog(LargeDialog):
    def __init__(
        self,
        master: tk.Misc,
        db: DatabaseManager,
        user: Optional[User],
    ) -> None:
        super().__init__(master, min_width=780, min_height=520)
        self.title("Globale Suche")
        self.db = db
        self.user = user

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        self.query_var = ttkb.StringVar()
        search_row = ttkb.Frame(container)
        search_row.pack(fill=tk.X, pady=(0, 10))
        ttkb.Entry(search_row, textvariable=self.query_var).pack(side=LEFT, fill=tk.X, expand=True)
        ttkb.Button(search_row, text="Suchen", command=self.perform_search, bootstyle="primary").pack(side=LEFT, padx=(10, 0))

        columns = [
            {"text": "Bereich"},
            {"text": "Bezeichnung"},
            {"text": "Details"},
        ]
        self.table = Tableview(
            container,
            coldata=columns,
            rowdata=[],
            pagesize=15,
        )
        self.table.pack(fill=BOTH, expand=True)

        self.bind("<Return>", lambda _event: self.perform_search())
        self.grab_set()

    def perform_search(self) -> None:
        term = self.query_var.get().strip()
        self.table.delete_rows()
        if not term:
            return
        results = self.db.search_global(term)
        for section, rows in results.items():
            for row in rows:
                details = []
                if "seriennummer" in row.keys():
                    details.append(f"SN: {row['seriennummer']}")
                if "kennzeichen" in row.keys() and row["kennzeichen"]:
                    details.append(f"Kennzeichen: {row['kennzeichen']}")
                if "lagerort" in row.keys() and row["lagerort"]:
                    details.append(f"Ort: {row['lagerort']}")
                if "email" in row.keys() and row["email"]:
                    details.append(f"E-Mail: {row['email']}")
                self.table.insert_row(
                    values=(
                        section.capitalize(),
                        row.get("name") or row.get("full_name") or row.get("kennzeichen") or "",
                        ", ".join(details),
                    )
                )


class LogViewerDialog(LargeDialog):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master, min_width=780, min_height=520)
        self.title("System-Log")
        self.db = db

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        columns = [
            {"text": "Zeit"},
            {"text": "Ebene"},
            {"text": "Nachricht"},
            {"text": "Benutzer"},
        ]
        self.table = Tableview(container, coldata=columns, rowdata=[], pagesize=20)
        self.table.pack(fill=BOTH, expand=True)

        self.refresh()
        self.grab_set()

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_system_log():
            self.table.insert_row(
                values=(
                    row["zeitstempel"],
                    row["ebene"],
                    row["nachricht"],
                    row["benutzer_name"] or "",
                )
            )


class ConfigurationDialog(LargeDialog):
    def __init__(self, master: tk.Misc, *, backup_dir: str, reminder_days: int) -> None:
        super().__init__(master, min_width=520, min_height=260)
        self.title("Konfiguration")
        self.result: Optional[Tuple[str, int]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text="Backup-Verzeichnis").grid(row=0, column=0, sticky=W, pady=5)
        self.backup_var = ttkb.StringVar(value=backup_dir)
        entry = ttkb.Entry(container, textvariable=self.backup_var, width=32)
        entry.grid(row=0, column=1, sticky=W)
        ttkb.Button(container, text="Auswählen", command=self.choose_directory).grid(row=0, column=2, padx=(8, 0))

        ttkb.Label(container, text="Erinnerungstage").grid(row=1, column=0, sticky=W, pady=5)
        self.reminder_var = ttkb.IntVar(value=reminder_days)
        ttkb.Spinbox(container, textvariable=self.reminder_var, from_=1, to=60, width=5).grid(row=1, column=1, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=2, column=0, columnspan=3, pady=(15, 0))
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.grab_set()

    def choose_directory(self) -> None:
        path = filedialog.askdirectory(title="Backup-Verzeichnis")
        if path:
            self.backup_var.set(path)

    def on_save(self) -> None:
        backup_dir = self.backup_var.get().strip()
        reminder_days = int(self.reminder_var.get())
        if reminder_days <= 0:
            Messagebox.show_warning("Erinnerungstage müssen größer 0 sein", "Hinweis")
            return
        self.result = (backup_dir, reminder_days)
        self.destroy()


class OrderCenterDialog(LargeDialog):
    def __init__(self, master: tk.Misc, db: DatabaseManager, user: Optional[User]) -> None:
        super().__init__(master, min_width=900, min_height=560)
        self.title("Bestellwesen")
        self.db = db
        self.user = user

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        toolbar = ttkb.Frame(container)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttkb.Button(toolbar, text="Neue Bestellung", command=self.new_order, bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Genehmigen", command=lambda: self.change_status("genehmigt"), bootstyle="info").pack(side=LEFT, padx=5)
        ttkb.Button(toolbar, text="Abschließen", command=lambda: self.change_status("abgeschlossen"), bootstyle="secondary").pack(side=LEFT, padx=5)

        columns = [
            {"text": "ID"},
            {"text": "Status"},
            {"text": "Erstellt"},
            {"text": "Standort"},
            {"text": "Benutzer"},
        ]
        self.table = Tableview(container, coldata=columns, rowdata=[], pagesize=18)
        self.table.pack(fill=BOTH, expand=True)

        self.refresh()
        self.grab_set()

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_orders():
            location = " / ".join(
                filter(
                    None,
                    [row["land"], row["bereich"], row["bezirk"], row["bezirksstelle"], row["ortsstelle"]],
                )
            )
            self.table.insert_row(
                values=(
                    row["id"],
                    row["status"],
                    row["erstellt_am"],
                    location,
                    row["benutzer_name"] or "",
                )
            )

    def selected_order(self) -> Optional[int]:
        rows = self.table.get_rows("selected")
        if not rows:
            Messagebox.show_info("Bitte Bestellung wählen", "Hinweis")
            return None
        return int(rows[0].values[0])

    def change_status(self, status: str) -> None:
        order_id = self.selected_order()
        if order_id is None:
            return
        try:
            self.db.update_order_status(order_id, status=status, benutzer_id=self.user.id if self.user else None)
        except Exception as exc:  # pragma: no cover - UI feedback
            Messagebox.show_error(str(exc), "Statusänderung fehlgeschlagen")
            return
        self.refresh()

    def new_order(self) -> None:
        dialog = NewOrderDialog(self, self.db)
        self.wait_window(dialog)
        if not dialog.result:
            return
        standort_id, bemerkung, positionen = dialog.result
        try:
            self.db.create_order(
                erstellt_von=self.user.id if self.user else 0,
                standort_id=standort_id,
                bemerkung=bemerkung,
                positionen=positionen,
            )
        except Exception as exc:  # pragma: no cover - UI feedback
            Messagebox.show_error(str(exc), "Bestellung konnte nicht angelegt werden")
            return
        self.refresh()


class NewOrderDialog(LargeDialog):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master, min_width=640, min_height=420)
        self.title("Bestellung anlegen")
        self.result: Optional[Tuple[Optional[int], str, List[Tuple[str, int]]]] = None
        self.db = db

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text="Standort").grid(row=0, column=0, sticky=W, pady=5)
        locations = db.list_locations()
        self.location_map = {db.location_label(row["id"]): row["id"] for row in locations}
        self.location_var = ttkb.StringVar()
        ttkb.Combobox(
            container,
            textvariable=self.location_var,
            values=list(self.location_map.keys()),
            width=40,
        ).grid(row=0, column=1, sticky=W)

        ttkb.Label(container, text="Bemerkung").grid(row=1, column=0, sticky=W, pady=5)
        self.note_var = ttkb.StringVar()
        ttkb.Entry(container, textvariable=self.note_var, width=42).grid(row=1, column=1, sticky=W)

        ttkb.Label(container, text="Positionen (eine pro Zeile, Format: Menge x Beschreibung)").grid(row=2, column=0, columnspan=2, sticky=W, pady=5)
        self.positions = scrolledtext.ScrolledText(container, width=60, height=6)
        self.positions.grid(row=3, column=0, columnspan=2, pady=(0, 10))

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=4, column=0, columnspan=2)
        ttkb.Button(button_frame, text="Speichern", command=self.on_save, bootstyle="success").pack(side=LEFT, padx=5)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.grab_set()

    def on_save(self) -> None:
        selected = self.location_var.get()
        standort_id = self.location_map.get(selected)
        bemerkung = self.note_var.get().strip()
        raw_lines = [line.strip() for line in self.positions.get("1.0", tk.END).splitlines() if line.strip()]
        if not raw_lines:
            Messagebox.show_warning("Bitte mindestens eine Position erfassen", "Hinweis")
            return
        parsed: List[Tuple[str, int]] = []
        for line in raw_lines:
            if " " in line:
                amount_part, description = line.split(" ", 1)
            elif "x" in line:
                amount_part, description = line.split("x", 1)
            else:
                amount_part, description = "1", line
            try:
                amount = int(amount_part.replace("x", "").strip())
            except ValueError:
                amount = 1
            parsed.append((description.strip(), amount))
        self.result = (standort_id, bemerkung, parsed)
        self.destroy()


class HelpDialog(LargeDialog):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, min_width=760, min_height=560)
        self.title("Hilfe")

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        intro = textwrap.dedent(
            """
            Willkommen in der Hilfeansicht. Links finden Sie eine Kurzfassung der wichtigsten Arbeitsabläufe.
            Öffnen Sie die vollständige Dokumentation über den Link unten.
            """
        ).strip()

        ttkb.Label(container, text=intro, wraplength=640, justify=tk.LEFT).pack(fill=tk.X, pady=(0, 10))

        self.text = scrolledtext.ScrolledText(container, wrap=tk.WORD)
        self.text.pack(fill=BOTH, expand=True)
        self.text.insert(tk.END, self._load_help_content())
        self.text.configure(state=tk.DISABLED)

        ttkb.Button(container, text="Dokumentation öffnen", command=self.open_docs, bootstyle="link").pack(pady=(10, 0))

        self.grab_set()

    @staticmethod
    def _load_help_content() -> str:
        docs = [Path("docs/benutzerhandbuch.md"), Path("docs/medizinprodukte_management_system.md")]
        for doc in docs:
            if doc.exists():
                return doc.read_text(encoding="utf-8")
        return "Dokumentation nicht gefunden."

    def open_docs(self) -> None:
        docs = Path("docs/medizinprodukte_management_system.html")
        if docs.exists():
            webbrowser.open(docs.resolve().as_uri())
        else:
            Messagebox.show_info("HTML-Dokumentation nicht gefunden.", "Hinweis")

class PersonalizationDialog(LargeDialog):
    def __init__(
        self,
        master: MedizinprodukteApp,
        *,
        current_theme: str,
        font_scale: float,
        show_welcome: bool,
    ) -> None:
        super().__init__(master, min_width=480, min_height=320)
        self.title("Personalisierung")
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


class ProductEditor(LargeDialog):
    def __init__(
        self,
        master: tk.Misc,
        db: DatabaseManager,
        produkt_id: Optional[int] = None,
        *,
        initial_tab: str = "details",
        user: Optional[User] = None,
    ) -> None:
        super().__init__(master, min_width=980, min_height=760)
        self.db = db
        self.produkt_id = produkt_id
        self.saved = False
        self.initial_tab = initial_tab
        self.title("Produkt bearbeiten" if produkt_id else "Neues Produkt")
        self.user = user

        self.categories = db.list_categories("produkt")
        self.product_types = db.list_product_types()
        self.product_models = db.list_product_models()
        self.product_manufacturers = db.list_product_manufacturers()
        all_locations = db.list_locations()
        if user and user.location_permissions:
            allowed_ids = {loc_id for loc_id, perm in user.location_permissions.items() if perm.schreiben}
            self.locations = [row for row in all_locations if row["id"] in allowed_ids]
        else:
            self.locations = all_locations
        if user and user.location_permissions and not self.locations:
            Messagebox.show_error(
                "Es sind keine Standorte mit Schreibrechten verfügbar.",
                "Keine Berechtigung",
            )
            self.destroy()
            return
        self.vehicles = db.list_vehicles()
        self.component_types = db.list_component_types()
        self.maintenance_types = db.list_maintenance_types()
        self.repair_types = db.list_repair_types()
        self.upload_categories = db.list_upload_categories()

        self.location_label_map: Dict[str, int] = {
            self._format_location(row): int(row["id"]) for row in self.locations
        }
        self.location_labels: List[str] = list(self.location_label_map.keys())

        self.vehicle_label_map: Dict[str, int] = {
            self._format_vehicle(row): int(row["id"])
            for row in self.vehicles
            if self._format_vehicle(row)
        }
        self.vehicle_labels: List[str] = [""] + list(self.vehicle_label_map.keys())

        self.model_index: Dict[int, List[Tuple[int, str]]] = {}
        for model in self.product_models:
            self.model_index.setdefault(model["typ_id"], []).append((model["id"], model["name"]))

        self.manufacturer_index: Dict[str, int] = {
            row["name"]: int(row["id"]) for row in self.product_manufacturers
        }

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

        self.maintenance_tab = MaintenanceTab(
            self.notebook, self.db, self.produkt_id, maintenance_types=self.maintenance_types
        )
        self.notebook.add(self.maintenance_tab, text="Wartungen")

        self.repairs_tab = RepairsTab(
            self.notebook,
            self.db,
            self.produkt_id,
            self.repair_types,
            self.upload_categories,
            user=self.user,
        )
        self.notebook.add(self.repairs_tab, text="Reparaturen")

        self._tabs = {
            "details": self.details_frame,
            "components": self.components_tab,
            "maintenance": self.maintenance_tab,
            "repairs": self.repairs_tab,
        }
        self._select_initial_tab()

        button_frame = ttkb.Frame(self, padding=(15, 12))
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(
            side=RIGHT, padx=5
        )
        ttkb.Button(button_frame, text="Speichern", command=self.save, bootstyle="success").pack(
            side=RIGHT, padx=5
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
        default_status_label = STATUS_VALUE_TO_LABEL.get("im_dienst", STATUS_OPTIONS[0][0])
        self.status_var = ttkb.StringVar(value=default_status_label)
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

        ttkb.Label(info_frame, text="Bezeichnung").grid(row=0, column=0, sticky=W, pady=4)
        self.name_entry = ttkb.Entry(info_frame, textvariable=self.name_var, width=40, state="readonly")
        self.name_entry.grid(row=0, column=1, sticky=W)

        ttkb.Label(info_frame, text="Produkttyp").grid(row=1, column=0, sticky=W, pady=4)
        self.typ_box = ttkb.Combobox(
            info_frame,
            textvariable=self.typ_var,
            values=[row["name"] for row in self.product_types],
            width=37,
            state="readonly",
        )
        self.typ_box.grid(row=1, column=1, sticky=W)
        self.typ_box.bind("<<ComboboxSelected>>", self._on_type_selected)

        ttkb.Label(info_frame, text="Modell").grid(row=2, column=0, sticky=W, pady=4)
        self.modell_box = ttkb.Combobox(info_frame, textvariable=self.modell_var, width=37, state="readonly")
        self.modell_box.grid(row=2, column=1, sticky=W)
        self.modell_box.bind("<<ComboboxSelected>>", lambda _event: self._update_name_from_type_model())

        ttkb.Label(info_frame, text="Seriennummer*").grid(row=3, column=0, sticky=W, pady=4)
        ttkb.Entry(info_frame, textvariable=self.seriennummer_var, width=40).grid(row=3, column=1, sticky=W)

        ttkb.Label(info_frame, text="Hersteller").grid(row=4, column=0, sticky=W, pady=4)
        self.hersteller_box = ttkb.Combobox(
            info_frame,
            textvariable=self.hersteller_var,
            width=37,
        )
        self.hersteller_box.grid(row=4, column=1, sticky=W)
        self._refresh_manufacturer_choices()

        ttkb.Label(info_frame, text="Anschaffungsdatum (TT.MM.JJJJ)").grid(row=5, column=0, sticky=W, pady=4)
        self.anschaffungsdatum_entry = DateEntry(
            info_frame,
            dateformat=DATE_FORMAT,
            width=18,
        )
        self.anschaffungsdatum_entry.grid(row=5, column=1, sticky=W)
        bind_date_entry(self.anschaffungsdatum_entry, self.anschaffungsdatum_var)

        ttkb.Label(info_frame, text="Kategorie").grid(row=6, column=0, sticky=W, pady=4)
        self.kategorie_box = ttkb.Combobox(
            info_frame,
            textvariable=self.kategorie_var,
            values=[row["name"] for row in self.categories],
            width=37,
            state="readonly",
        )
        self.kategorie_box.grid(row=6, column=1, sticky=W)

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
        self.stk_last_entry = DateEntry(
            stk_frame,
            dateformat=DATE_FORMAT,
            width=16,
        )
        self.stk_last_entry.grid(row=0, column=2, sticky=W)
        bind_date_entry(self.stk_last_entry, self.stk_last_var)
        ttkb.Label(stk_frame, text="Nächste STK").grid(row=0, column=3, padx=(20, 5), sticky=W)
        self.stk_next_entry = DateEntry(
            stk_frame,
            dateformat=DATE_FORMAT,
            width=16,
        )
        self.stk_next_entry.grid(row=0, column=4, sticky=W)
        bind_date_entry(self.stk_next_entry, self.stk_next_var)
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
        self.mtk_last_entry = DateEntry(
            mtk_frame,
            dateformat=DATE_FORMAT,
            width=16,
        )
        self.mtk_last_entry.grid(row=0, column=2, sticky=W)
        bind_date_entry(self.mtk_last_entry, self.mtk_last_var)
        ttkb.Label(mtk_frame, text="Nächste MTK").grid(row=0, column=3, padx=(20, 5), sticky=W)
        self.mtk_next_entry = DateEntry(
            mtk_frame,
            dateformat=DATE_FORMAT,
            width=16,
        )
        self.mtk_next_entry.grid(row=0, column=4, sticky=W)
        bind_date_entry(self.mtk_next_entry, self.mtk_next_var)
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
        assignment_frame.columnconfigure(1, weight=1)

        ttkb.Label(assignment_frame, text="Standort*").grid(row=0, column=0, sticky=W, pady=4)
        self.standort_box = SearchableCombobox(
            assignment_frame,
            textvariable=self.standort_var,
            values=self.location_labels,
            width=45,
            match_mode="contains",
        )
        self.standort_box.grid(row=0, column=1, sticky=tk.EW)
        self.standort_box.set_completion_list(self.location_labels)

        ttkb.Label(assignment_frame, text="Fahrzeug (Funkkennung)").grid(row=1, column=0, sticky=W, pady=4)
        self.fahrzeug_box = SearchableCombobox(
            assignment_frame,
            textvariable=self.fahrzeug_var,
            values=self.vehicle_labels,
            width=45,
            match_mode="contains",
        )
        self.fahrzeug_box.grid(row=1, column=1, sticky=tk.EW)
        self.fahrzeug_box.set_completion_list(self.vehicle_labels)

        ttkb.Label(assignment_frame, text="Lagerort").grid(row=2, column=0, sticky=W, pady=4)
        ttkb.Entry(assignment_frame, textvariable=self.lagerort_var, width=48).grid(
            row=2, column=1, sticky=tk.EW
        )

        ttkb.Label(assignment_frame, text="Status").grid(row=3, column=0, sticky=W, pady=4)
        self.status_box = ttkb.Combobox(
            assignment_frame,
            textvariable=self.status_var,
            values=[label for label, _ in STATUS_OPTIONS],
            width=20,
            state="readonly",
        )
        self.status_box.grid(row=3, column=1, sticky=W)

        ttkb.Label(assignment_frame, text="Interne Kennung").grid(row=4, column=0, sticky=W, pady=4)
        ttkb.Entry(assignment_frame, textvariable=self.interne_kennung_var, width=48).grid(
            row=4, column=1, sticky=W
        )

        ttkb.Label(assignment_frame, text="Informationstext").grid(row=5, column=0, sticky=tk.NW, pady=4)
        self.info_text = tk.Text(assignment_frame, height=4, width=45, wrap="word")
        self.info_text.grid(row=5, column=1, sticky=W)

        self._update_model_choices()
        self._update_stk_state()
        self._update_mtk_state()

    def _format_location(self, row: sqlite3.Row) -> str:
        label = self.db.location_label(row["id"])
        if not label:
            label = f"Standort #{row['id']}"
        return f"{label} (#{row['id']})"

    def _format_vehicle(self, row: sqlite3.Row) -> str:
        if not row:
            return ""
        label = row["name"] if "name" in row.keys() else ""
        if "kennzeichen" in row.keys() and row["kennzeichen"]:
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
        self._update_name_from_type_model()

    def _on_type_selected(self, _event: Optional[tk.Event] = None) -> None:  # type: ignore[override]
        self._update_model_choices()

    def _update_name_from_type_model(self) -> None:
        typ = self.typ_var.get().strip()
        modell = self.modell_var.get().strip()
        parts = [value for value in (typ, modell) if value]
        self.name_var.set(" ".join(parts))

    def _refresh_manufacturer_choices(self) -> None:
        if hasattr(self, "hersteller_box"):
            values = sorted(self.manufacturer_index.keys())
            self.hersteller_box.configure(values=values)

    def _update_stk_state(self) -> None:
        state = tk.NORMAL if self.stk_active.get() else tk.DISABLED
        for widget in [self.stk_interval_entry, self.stk_last_entry, self.stk_next_entry]:
            widget.configure(state=state)
            if hasattr(widget, "entry"):
                widget.entry.configure(state=state)

    def _update_mtk_state(self) -> None:
        state = tk.NORMAL if self.mtk_active.get() else tk.DISABLED
        for widget in [self.mtk_interval_entry, self.mtk_last_entry, self.mtk_next_entry]:
            widget.configure(state=state)
            if hasattr(widget, "entry"):
                widget.entry.configure(state=state)

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
        return self.location_label_map.get(value.strip())

    def _resolve_vehicle(self, value: str) -> Optional[int]:
        value = value.strip()
        if not value:
            return None
        return self.vehicle_label_map.get(value)

    def load_data(self) -> None:
        if self.produkt_id is None:
            return
        product = self.db.get_product(self.produkt_id)
        if not product:
            Messagebox.show_error("Produkt nicht gefunden", "Fehler")
            self.destroy()
            return
        existing_name = product["name"] or ""
        self.name_var.set(existing_name)
        self.typ_var.set(product["produkt_typ_name"] or product["typ"] or "")
        self._update_model_choices()
        if product["produkt_modell_name"]:
            self.modell_var.set(product["produkt_modell_name"])
        if existing_name:
            self.name_var.set(existing_name)
        self.seriennummer_var.set(product["seriennummer"] or "")
        self.hersteller_var.set(
            product["produkt_hersteller_name"]
            or product["hersteller"]
            or ""
        )
        self.anschaffungsdatum_var.set(format_date(product["anschaffungsdatum"]))
        if not self.anschaffungsdatum_var.get():
            self.anschaffungsdatum_entry.entry.delete(0, tk.END)
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
        status_value = product["status"] or "im_dienst"
        self.status_var.set(display_status(status_value))
        self.interne_kennung_var.set(product["interne_kennung"] or "")
        self.info_text.delete("1.0", tk.END)
        self.info_text.insert(tk.END, product["informationstext"] or "")

        self.stk_active.set(bool(product["stk_aktiv"]))
        self.stk_interval_var.set(str(product["stk_intervall"] or ""))
        self.stk_last_var.set(format_date(product["letzte_stk"]))
        if not self.stk_last_var.get():
            self.stk_last_entry.entry.delete(0, tk.END)
        self.stk_next_var.set(format_date(product["naechste_stk"]))
        if not self.stk_next_var.get():
            self.stk_next_entry.entry.delete(0, tk.END)
        self.mtk_active.set(bool(product["mtk_aktiv"]))
        self.mtk_interval_var.set(str(product["mtk_intervall"] or ""))
        self.mtk_last_var.set(format_date(product["letzte_mtk"]))
        if not self.mtk_last_var.get():
            self.mtk_last_entry.entry.delete(0, tk.END)
        self.mtk_next_var.set(format_date(product["naechste_mtk"]))
        if not self.mtk_next_var.get():
            self.mtk_next_entry.entry.delete(0, tk.END)

        self._update_stk_state()
        self._update_mtk_state()

        self.components_tab.set_product_id(self.produkt_id)
        self.maintenance_tab.set_product_id(self.produkt_id)
        self.repairs_tab.set_product_id(self.produkt_id)

    def save(self) -> None:
        seriennummer = self.seriennummer_var.get().strip()
        if not seriennummer:
            Messagebox.show_error("Seriennummer ist erforderlich", "Fehler")
            return

        try:
            anschaffungsdatum = (
                parse_date(self.anschaffungsdatum_var.get())
                if self.anschaffungsdatum_var.get().strip()
                else None
            )
        except ValueError:
            Messagebox.show_error("Ungültiges Anschaffungsdatum", "Fehler")
            return

        try:
            stk_intervall = int(self.stk_interval_var.get() or 0)
            mtk_intervall = int(self.mtk_interval_var.get() or 0)
        except ValueError:
            Messagebox.show_error("Kontrollintervalle müssen numerisch sein", "Fehler")
            return

        standort_id = self._resolve_location(self.standort_var.get())
        if not standort_id:
            Messagebox.show_warning("Bitte einen Standort auswählen", "Hinweis")
            return
        if self.user and not self.user.can_write_location(standort_id):
            Messagebox.show_info(
                "Sie haben keine Schreibrechte für den ausgewählten Standort.",
                "Keine Berechtigung",
            )
            return

        fahrzeug_id = self._resolve_vehicle(self.fahrzeug_var.get())
        lagerort = self.lagerort_var.get().strip()
        if not fahrzeug_id and not lagerort:
            Messagebox.show_warning(
                "Ein Produkt benötigt entweder ein Fahrzeug oder einen Lagerort.",
                "Hinweis",
            )
            return

        try:
            letzte_stk = (
                parse_date(self.stk_last_var.get())
                if self.stk_last_var.get().strip()
                else None
            )
            naechste_stk = (
                parse_date(self.stk_next_var.get())
                if self.stk_next_var.get().strip()
                else None
            )
            letzte_mtk = (
                parse_date(self.mtk_last_var.get())
                if self.mtk_last_var.get().strip()
                else None
            )
            naechste_mtk = (
                parse_date(self.mtk_next_var.get())
                if self.mtk_next_var.get().strip()
                else None
            )
        except ValueError:
            Messagebox.show_error("Ungültige Datumsangaben", "Fehler")
            return

        if self.db.serial_exists(seriennummer, exclude_id=self.produkt_id):
            Messagebox.show_error("Seriennummer ist bereits vorhanden", "Fehler")
            return

        if self.stk_active.get() and not naechste_stk and letzte_stk and stk_intervall > 0:
            self._calculate_next_due(self.stk_last_var, self.stk_interval_var, self.stk_next_var)
            naechste_stk = parse_date(self.stk_next_var.get())
        if self.mtk_active.get() and not naechste_mtk and letzte_mtk and mtk_intervall > 0:
            self._calculate_next_due(self.mtk_last_var, self.mtk_interval_var, self.mtk_next_var)
            naechste_mtk = parse_date(self.mtk_next_var.get())

        if anschaffungsdatum and letzte_stk and letzte_stk < anschaffungsdatum:
            Messagebox.show_error("Letzte STK darf nicht vor Anschaffung liegen", "Fehler")
            return
        if anschaffungsdatum and letzte_mtk and letzte_mtk < anschaffungsdatum:
            Messagebox.show_error("Letzte MTK darf nicht vor Anschaffung liegen", "Fehler")
            return
        if letzte_stk and naechste_stk and naechste_stk < letzte_stk:
            Messagebox.show_error("Nächste STK liegt vor der letzten STK", "Fehler")
            return
        if letzte_mtk and naechste_mtk and naechste_mtk < letzte_mtk:
            Messagebox.show_error("Nächste MTK liegt vor der letzten MTK", "Fehler")
            return
        if anschaffungsdatum:
            if naechste_stk and naechste_stk < anschaffungsdatum:
                Messagebox.show_error("Nächste STK darf nicht vor Anschaffung liegen", "Fehler")
                return
            if naechste_mtk and naechste_mtk < anschaffungsdatum:
                Messagebox.show_error("Nächste MTK darf nicht vor Anschaffung liegen", "Fehler")
                return

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
        status_value = STATUS_LABEL_TO_VALUE.get(self.status_var.get(), "im_dienst")

        hersteller_name = self.hersteller_var.get().strip()
        produkt_hersteller_id: Optional[int] = None
        if hersteller_name:
            produkt_hersteller_id = self.manufacturer_index.get(hersteller_name)
            if not produkt_hersteller_id:
                try:
                    produkt_hersteller_id = self.db.add_product_manufacturer(hersteller_name)
                except sqlite3.IntegrityError:
                    row = next(
                        (row for row in self.db.list_product_manufacturers() if row["name"] == hersteller_name),
                        None,
                    )
                    if row:
                        produkt_hersteller_id = int(row["id"])
                self.product_manufacturers = self.db.list_product_manufacturers()
                self.manufacturer_index = {
                    row["name"]: int(row["id"]) for row in self.product_manufacturers
                }
                self._refresh_manufacturer_choices()

        was_new = self.produkt_id is None
        name_value = self._resolved_name()
        before = self.db.get_product(self.produkt_id) if self.produkt_id else None

        try:
            produkt_id = self.db.add_or_update_product(
                produkt_id=self.produkt_id,
                name=name_value,
                typ=self.typ_var.get(),
                seriennummer=seriennummer,
                hersteller=self.hersteller_var.get(),
                anschaffungsdatum=anschaffungsdatum,
                kategorie_id=kategorie_id,
                standort_id=standort_id,
                fahrzeug_id=fahrzeug_id,
                status=status_value,
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
                produkt_hersteller_id=produkt_hersteller_id,
                informationstext=informationstext,
                user_id=self.user.id if self.user else None,
            )
        except Exception as exc:  # pragma: no cover
            Messagebox.show_error(str(exc), "Fehler")
            return

        after = self.db.get_product(produkt_id)
        try:
            self.db.record_audit(
                tabelle="produkte",
                datensatz_id=produkt_id,
                aktion="create" if was_new else "update",
                vorher=json.dumps(dict(before)) if before else None,
                nachher=json.dumps(dict(after)) if after else None,
                benutzer_id=self.user.id if self.user else None,
            )
            self.db.log_event(
                ebene="INFO",
                nachricht=f"Produkt {name_value} gespeichert",
                benutzer_id=self.user.id if self.user else None,
            )
        except Exception:
            pass

        self.produkt_id = produkt_id
        if was_new:
            self.components_tab.persist_pending(produkt_id)
            self.maintenance_tab.persist_pending(produkt_id)
        self.saved = True
        Messagebox.show_info("Produkt gespeichert", "Erfolg")
        self.components_tab.set_product_id(self.produkt_id)
        self.maintenance_tab.set_product_id(self.produkt_id)
        self.repairs_tab.set_product_id(self.produkt_id)
        self.destroy()

    def _resolved_name(self) -> str:
        entered = self.name_var.get().strip()
        if entered:
            return entered
        derived = self._derived_name()
        if derived:
            return derived
        return self.seriennummer_var.get().strip()

    def _derived_name(self) -> str:
        typ = self.typ_var.get().strip()
        modell = self.modell_var.get().strip()
        parts = [part for part in (typ, modell) if part]
        return " ".join(parts)


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
        self.pending_components: List[Dict[str, Any]] = []
        self.pending_cache: Dict[str, Dict[str, Any]] = {}

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
            {"text": "Kennung"},
            {"text": "Bezeichnung"},
            {"text": "Typ"},
            {"text": "Seriennummer"},
            {"text": "Bemerkung"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=12)
        self.table.bind("<Double-1>", lambda _event: self.edit_component())
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        self.info_label = ttkb.Label(self, text="", bootstyle="secondary", anchor=W)
        self.info_label.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.set_product_id(produkt_id)

    def set_product_id(self, produkt_id: Optional[int]) -> None:
        self.produkt_id = produkt_id
        self._update_state()

    def _update_state(self) -> None:
        for button in (self.add_btn, self.edit_btn, self.delete_btn):
            button.configure(state=tk.NORMAL)
        if self.produkt_id:
            self.info_label.configure(text="")
            self.refresh()
        else:
            self.info_label.configure(
                text="Komponenten werden nach dem Speichern automatisch mit dem Produkt verknüpft."
            )
            self.refresh_pending()

    def refresh(self) -> None:
        if not self.produkt_id:
            return
        self.table.delete_rows()
        self.component_cache = {}
        for row in self.db.list_components(self.produkt_id):
            self.component_cache[int(row["id"])] = row
            self.table.insert_row(
                values=(
                    str(row["id"]),
                    row["name"],
                    row["komponententyp_name"] or "",
                    row["seriennummer"] or "",
                    row["bemerkung"] or "",
                )
            )

    def refresh_pending(self) -> None:
        self.table.delete_rows()
        self.pending_cache = {}
        for index, record in enumerate(self.pending_components, start=1):
            key = f"neu-{index}"
            self.pending_cache[key] = {"index": index - 1, "data": record}
            self.table.insert_row(
                values=(
                    key,
                    record.get("name", ""),
                    record.get("komponententyp_name", ""),
                    record.get("seriennummer", ""),
                    record.get("bemerkung", ""),
                )
            )

    def selected_component_key(self) -> Optional[str]:
        rows = self.table.get_rows("selected")
        if not rows:
            Messagebox.show_info("Bitte Komponente auswählen", "Hinweis")
            return None
        return str(rows[0].values[0])

    def _resolve_component_type_name(self, type_id: Optional[int]) -> str:
        if not type_id:
            return ""
        for row in self.component_types:
            if row["id"] == type_id:
                return row["name"]
        return ""

    def add_component(self) -> None:
        dialog = ComponentFormDialog(self, "Komponente hinzufügen", self.component_types)
        self.wait_window(dialog)
        if not dialog.result:
            return
        data = dialog.result
        type_name = self._resolve_component_type_name(data["komponententyp_id"])
        if self.produkt_id:
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
        else:
            record = dict(data)
            record["komponententyp_name"] = type_name
            anschaffung = record.get("anschaffungsdatum")
            record["anschaffungsdatum"] = anschaffung.isoformat() if anschaffung else None
            self.pending_components.append(record)
            self.refresh_pending()

    def edit_component(self) -> None:
        key = self.selected_component_key()
        if not key:
            return
        if key.startswith("neu-"):
            pending = self.pending_cache.get(key)
            if not pending:
                return
            record = dict(pending["data"])
            dialog = ComponentFormDialog(self, "Komponente bearbeiten", self.component_types, record)
            self.wait_window(dialog)
            if not dialog.result:
                return
            data = dialog.result
            type_name = self._resolve_component_type_name(data["komponententyp_id"])
            updated = dict(data)
            updated["komponententyp_name"] = type_name
            anschaffung = updated.get("anschaffungsdatum")
            updated["anschaffungsdatum"] = anschaffung.isoformat() if anschaffung else None
            self.pending_components[pending["index"]] = updated
            self.refresh_pending()
            return

        component_id = int(key)
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
            produkt_id=self.produkt_id,
            name=data["name"],
            hersteller=data["hersteller"],
            seriennummer=data["seriennummer"],
            anschaffungsdatum=data["anschaffungsdatum"],
            bemerkung=data["bemerkung"],
            komponententyp_id=data["komponententyp_id"],
        )
        self.refresh()

    def delete_component(self) -> None:
        key = self.selected_component_key()
        if not key:
            return
        if key.startswith("neu-"):
            pending = self.pending_cache.get(key)
            if not pending:
                return
            if Messagebox.okcancel("Komponente wirklich entfernen?", "Bestätigung") != "OK":
                return
            del self.pending_components[pending["index"]]
            self.refresh_pending()
            return

        component_id = int(key)
        if Messagebox.okcancel("Komponente wirklich entfernen?", "Bestätigung", alert=True) != "OK":
            return
        self.db.delete_component(component_id)
        self.refresh()

    def persist_pending(self, produkt_id: int) -> None:
        if not self.pending_components:
            return
        for record in self.pending_components:
            anschaffungsdatum = (
                datetime.strptime(record["anschaffungsdatum"], "%Y-%m-%d").date()
                if record.get("anschaffungsdatum")
                else None
            )
            self.db.add_or_update_component(
                komponent_id=None,
                produkt_id=produkt_id,
                name=record.get("name", ""),
                hersteller=record.get("hersteller", ""),
                seriennummer=record.get("seriennummer", ""),
                anschaffungsdatum=anschaffungsdatum,
                bemerkung=record.get("bemerkung", ""),
                komponententyp_id=record.get("komponententyp_id"),
            )
        self.pending_components.clear()
        self.pending_cache = {}


class ComponentFormDialog(LargeDialog):
    def __init__(
        self,
        master: tk.Misc,
        title: str,
        component_types: List[sqlite3.Row],
        data: Optional[sqlite3.Row] = None,
    ) -> None:
        super().__init__(master, min_width=520, min_height=360)
        self.title(title)
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
        self.anschaffungsdatum_entry = DateEntry(
            container,
            dateformat=DATE_FORMAT,
            width=18,
        )
        self.anschaffungsdatum_entry.grid(row=4, column=1, sticky=W)
        bind_date_entry(self.anschaffungsdatum_entry, self.anschaffungsdatum_var)

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
    def __init__(
        self,
        master: tk.Misc,
        db: DatabaseManager,
        produkt_id: Optional[int],
        *,
        maintenance_types: Optional[Sequence[Any]] = None,
    ) -> None:
        super().__init__(master)
        self.db = db
        self.produkt_id = produkt_id
        self.maintenance_cache: Dict[int, sqlite3.Row] = {}
        self.pending_maintenances: List[Dict[str, Any]] = []
        self.pending_cache: Dict[str, Dict[str, Any]] = {}
        self.maintenance_types: List[str] = self._normalize_types(maintenance_types)

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
            {"text": "Kennung"},
            {"text": "Geplanter Termin"},
            {"text": "Typ"},
            {"text": "Durchgeführt"},
            {"text": "Beschreibung"},
        ]
        self.table = Tableview(self, coldata=columns, rowdata=[], pagesize=12)
        self.table.bind("<Double-1>", lambda _event: self.edit_maintenance())
        self.table.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        self.info_label = ttkb.Label(self, text="", bootstyle="secondary", anchor=W)
        self.info_label.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.set_product_id(produkt_id)

    def set_product_id(self, produkt_id: Optional[int]) -> None:
        self.produkt_id = produkt_id
        self._update_state()

    def _update_state(self) -> None:
        for button in (self.add_btn, self.edit_btn, self.delete_btn):
            button.configure(state=tk.NORMAL)
        if self.produkt_id:
            self.info_label.configure(text="")
            self.refresh()
        else:
            self.info_label.configure(
                text="Wartungen werden nach dem Speichern automatisch zum Produkt hinzugefügt."
            )
            self.refresh_pending()

    def refresh(self) -> None:
        if not self.produkt_id:
            return
        self.table.delete_rows()
        self.maintenance_cache = {}
        for row in self.db.list_maintenance(self.produkt_id):
            self._register_type(row["wartungstyp"])
            self.maintenance_cache[int(row["id"])] = row
            self.table.insert_row(
                values=(
                    str(row["id"]),
                    format_date(row["geplanter_termin"]),
                    row["wartungstyp"],
                    format_date(row["durchgefuehrt_am"]),
                    row["beschreibung"] or "",
                )
            )

    def refresh_pending(self) -> None:
        self.table.delete_rows()
        self.pending_cache = {}
        for index, record in enumerate(self.pending_maintenances, start=1):
            key = f"neu-{index}"
            self.pending_cache[key] = {"index": index - 1, "data": record}
            self._register_type(record.get("wartungstyp", ""))
            self.table.insert_row(
                values=(
                    key,
                    self._format_iso(record.get("geplanter_termin")),
                    record.get("wartungstyp", ""),
                    self._format_iso(record.get("durchgefuehrt_am")),
                    record.get("beschreibung", ""),
                )
            )

    @staticmethod
    def _format_iso(value: Optional[str]) -> str:
        if not value:
            return ""
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime(DATE_FORMAT)
        except ValueError:
            return value

    def selected_maintenance_key(self) -> Optional[str]:
        rows = self.table.get_rows("selected")
        if not rows:
            Messagebox.show_info("Bitte Wartung auswählen", "Hinweis")
            return None
        return str(rows[0].values[0])

    def add_maintenance(self) -> None:
        dialog = MaintenanceFormDialog(
            self,
            "Wartung planen",
            maintenance_types=self.maintenance_types,
        )
        self.wait_window(dialog)
        if not dialog.result:
            return
        data = dialog.result
        self._register_type(data["wartungstyp"])
        if self.produkt_id:
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
        else:
            record = {
                "geplanter_termin": data["geplanter_termin"].isoformat(),
                "wartungstyp": data["wartungstyp"],
                "beschreibung": data["beschreibung"],
                "durchgefuehrt_am": data["durchgefuehrt_am"].isoformat()
                if data["durchgefuehrt_am"]
                else None,
                "durchgefuehrt_von": data["durchgefuehrt_von"],
                "bemerkung": data["bemerkung"],
            }
            self.pending_maintenances.append(record)
            self.refresh_pending()

    def edit_maintenance(self) -> None:
        key = self.selected_maintenance_key()
        if not key:
            return
        if key.startswith("neu-"):
            pending = self.pending_cache.get(key)
            if not pending:
                return
            record = dict(pending["data"])
            dialog = MaintenanceFormDialog(
                self,
                "Wartung bearbeiten",
                data=record,
                maintenance_types=self.maintenance_types,
            )
            self.wait_window(dialog)
            if not dialog.result:
                return
            data = dialog.result
            self._register_type(data["wartungstyp"])
            updated = {
                "geplanter_termin": data["geplanter_termin"].isoformat(),
                "wartungstyp": data["wartungstyp"],
                "beschreibung": data["beschreibung"],
                "durchgefuehrt_am": data["durchgefuehrt_am"].isoformat()
                if data["durchgefuehrt_am"]
                else None,
                "durchgefuehrt_von": data["durchgefuehrt_von"],
                "bemerkung": data["bemerkung"],
            }
            self.pending_maintenances[pending["index"]] = updated
            self.refresh_pending()
            return

        wartung_id = int(key)
        row = self.maintenance_cache.get(wartung_id)
        if not row:
            return
        dialog = MaintenanceFormDialog(
            self,
            "Wartung bearbeiten",
            data=row,
            maintenance_types=self.maintenance_types,
        )
        self.wait_window(dialog)
        if not dialog.result:
            return
        data = dialog.result
        self._register_type(data["wartungstyp"])
        self.db.add_or_update_maintenance(
            wartung_id=wartung_id,
            produkt_id=self.produkt_id,
            geplanter_termin=data["geplanter_termin"],
            wartungstyp=data["wartungstyp"],
            beschreibung=data["beschreibung"],
            durchgefuehrt_am=data["durchgefuehrt_am"],
            durchgefuehrt_von=data["durchgefuehrt_von"],
            bemerkung=data["bemerkung"],
        )
        self.refresh()

    def delete_maintenance(self) -> None:
        key = self.selected_maintenance_key()
        if not key:
            return
        if key.startswith("neu-"):
            pending = self.pending_cache.get(key)
            if not pending:
                return
            if Messagebox.okcancel("Wartung wirklich entfernen?", "Bestätigung") != "OK":
                return
            del self.pending_maintenances[pending["index"]]
            self.refresh_pending()
            return

        wartung_id = int(key)
        if Messagebox.okcancel("Wartung wirklich löschen?", "Bestätigung", alert=True) != "OK":
            return
        self.db.delete_maintenance(wartung_id)
        self.refresh()

    def persist_pending(self, produkt_id: int) -> None:
        if not self.pending_maintenances:
            return
        for record in self.pending_maintenances:
            geplanter = datetime.strptime(record["geplanter_termin"], "%Y-%m-%d").date()
            durchgefuehrt = (
                datetime.strptime(record["durchgefuehrt_am"], "%Y-%m-%d").date()
                if record.get("durchgefuehrt_am")
                else None
            )
            self._register_type(record.get("wartungstyp", ""))
            self.db.add_or_update_maintenance(
                wartung_id=None,
                produkt_id=produkt_id,
                geplanter_termin=geplanter,
                wartungstyp=record.get("wartungstyp", ""),
                beschreibung=record.get("beschreibung", ""),
                durchgefuehrt_am=durchgefuehrt,
                durchgefuehrt_von=record.get("durchgefuehrt_von", ""),
                bemerkung=record.get("bemerkung", ""),
            )
        self.pending_maintenances.clear()
        self.pending_cache = {}

    def set_maintenance_types(self, maintenance_types: Sequence[Any]) -> None:
        self.maintenance_types = self._normalize_types(maintenance_types)

    @staticmethod
    def _normalize_types(values: Optional[Sequence[Any]]) -> List[str]:
        names: List[str] = []
        if not values:
            return names
        for value in values:
            if isinstance(value, sqlite3.Row):
                name = value["name"] if "name" in value.keys() else str(value)
            else:
                name = str(value)
            name = name.strip()
            if name:
                names.append(name)
        return sorted(set(names))

    def _register_type(self, name: str) -> None:
        cleaned = name.strip()
        if cleaned and cleaned not in self.maintenance_types:
            self.maintenance_types.append(cleaned)
            self.maintenance_types.sort()
class MaintenanceFormDialog(LargeDialog):
    def __init__(
        self,
        master: tk.Misc,
        title: str,
        *,
        data: Optional[sqlite3.Row] = None,
        maintenance_types: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(master, min_width=540, min_height=400)
        self.title(title)
        self.result: Optional[Dict[str, Any]] = None

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        self.geplant_var = ttkb.StringVar(value=format_date(data["geplanter_termin"]) if data else "")
        initial_type = ""
        if data:
            initial_type = data["wartungstyp"] or ""
        initial_type = str(initial_type).strip()
        self.typ_var = ttkb.StringVar(value=initial_type)
        self.beschreibung_var = ttkb.StringVar(value=(data["beschreibung"] if data else ""))
        self.durchgefuehrt_var = ttkb.StringVar(value=format_date(data["durchgefuehrt_am"]) if data else "")
        self.von_var = ttkb.StringVar(value=(data["durchgefuehrt_von"] if data else ""))
        self.bemerkung_var = ttkb.StringVar(value=(data["bemerkung"] if data else ""))

        ttkb.Label(container, text="Geplanter Termin (TT.MM.JJJJ)*").grid(row=0, column=0, sticky=W, pady=5)
        self.geplant_entry = DateEntry(
            container,
            dateformat=DATE_FORMAT,
            width=18,
        )
        self.geplant_entry.grid(row=0, column=1, sticky=W)
        bind_date_entry(self.geplant_entry, self.geplant_var)

        ttkb.Label(container, text="Typ*").grid(row=1, column=0, sticky=W, pady=5)
        type_values = sorted({str(value).strip() for value in (maintenance_types or []) if str(value).strip()})
        existing_type = initial_type
        if existing_type and existing_type not in type_values:
            type_values.append(existing_type)
            type_values.sort()
        self.type_box = ttkb.Combobox(
            container,
            textvariable=self.typ_var,
            values=type_values,
            width=35,
        )
        self.type_box.grid(row=1, column=1, sticky=W)

        ttkb.Label(container, text="Beschreibung").grid(row=2, column=0, sticky=W, pady=5)
        ttkb.Entry(container, textvariable=self.beschreibung_var, width=35).grid(row=2, column=1, sticky=W)

        ttkb.Label(container, text="Durchgeführt am (TT.MM.JJJJ)").grid(row=3, column=0, sticky=W, pady=5)
        self.durchgefuehrt_entry = DateEntry(
            container,
            dateformat=DATE_FORMAT,
            width=18,
        )
        self.durchgefuehrt_entry.grid(row=3, column=1, sticky=W)
        bind_date_entry(self.durchgefuehrt_entry, self.durchgefuehrt_var)

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
        user: Optional[User] = None,
    ) -> None:
        super().__init__(master)
        self.db = db
        self.produkt_id = produkt_id
        self.repair_types = repair_types
        self.upload_categories = upload_categories
        self.contacts = db.list_contacts()
        self.user = user
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
            user_id=self.user.id if self.user else None,
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


class RepairFormDialog(LargeDialog):
    def __init__(
        self,
        master: tk.Misc,
        *,
        repair_types: List[sqlite3.Row],
        upload_categories: List[sqlite3.Row],
        contacts: List[sqlite3.Row],
    ) -> None:
        super().__init__(master, min_width=680, min_height=520)
        self.title("Reparatur melden")
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
        self.datum_entry = DateEntry(
            container,
            dateformat=DATE_FORMAT,
            width=18,
        )
        self.datum_entry.grid(row=0, column=1, sticky=W)
        bind_date_entry(self.datum_entry, self.datum_var)

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

        ttkb.Label(container, text="Beschreibung").grid(row=4, column=0, sticky=tk.NW, pady=5)
        self.beschreibung_text.grid(row=4, column=1, sticky=W)

        attachments_frame = ttkb.Labelframe(container, text="Anhänge")
        attachments_frame.grid(row=5, column=0, columnspan=2, pady=10, sticky=tk.EW)

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


class AttachmentCategoryDialog(LargeDialog):
    def __init__(self, master: tk.Misc, categories: List[sqlite3.Row]) -> None:
        super().__init__(master, min_width=420, min_height=240)
        self.title("Kategorie wählen")
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


class MassUploadDialog(LargeDialog):
    def __init__(
        self,
        master: tk.Misc,
        db: DatabaseManager,
        *,
        user: Optional[User] = None,
    ) -> None:
        super().__init__(master, min_width=900, min_height=680)
        self.db = db
        self.user = user
        self.created = 0
        self.errors: List[str] = []
        self.title("Massenupload Produkte")

        self.categories = db.list_categories("produkt")
        self.product_types = db.list_product_types()
        self.product_models = db.list_product_models()
        self.product_manufacturers = db.list_product_manufacturers()
        self.vehicles = db.list_vehicles()
        all_locations = db.list_locations()
        if user and user.location_permissions:
            allowed_ids = {loc_id for loc_id, perm in user.location_permissions.items() if perm.schreiben}
            self.locations = [row for row in all_locations if row["id"] in allowed_ids]
            if not self.locations:
                Messagebox.show_info(
                    "Es sind keine Standorte mit Schreibrechten verfügbar.",
                    "Massenupload",
                )
                self.destroy()
                return
        else:
            self.locations = all_locations

        self.model_index: Dict[int, List[Tuple[int, str]]] = {}
        for model in self.product_models:
            self.model_index.setdefault(model["typ_id"], []).append((model["id"], model["name"]))

        self.manufacturer_index: Dict[str, int] = {
            row["name"]: int(row["id"]) for row in self.product_manufacturers
        }

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        form = ttkb.Labelframe(container, text="Gemeinsame Angaben")
        form.pack(fill=tk.X, expand=False)

        self.typ_var = ttkb.StringVar()
        self.modell_var = ttkb.StringVar()
        self.kategorie_var = ttkb.StringVar()
        self.hersteller_var = ttkb.StringVar()
        self.anschaffungsdatum_var = ttkb.StringVar()
        self.standort_var = ttkb.StringVar()
        self.fahrzeug_var = ttkb.StringVar()
        self.lagerort_var = ttkb.StringVar()
        self.status_var = ttkb.StringVar(value=STATUS_OPTIONS[0][0])
        self.interne_prefix_var = ttkb.StringVar()
        self.stk_interval_var = ttkb.StringVar(value="12")
        self.mtk_interval_var = ttkb.StringVar(value="24")
        self.stk_active = ttkb.BooleanVar(value=True)
        self.mtk_active = ttkb.BooleanVar(value=True)

        ttkb.Label(form, text="Typ").grid(row=0, column=0, sticky=W, pady=5)
        self.typ_box = ttkb.Combobox(
            form,
            textvariable=self.typ_var,
            values=[row["name"] for row in self.product_types],
            state="readonly",
            width=32,
        )
        self.typ_box.grid(row=0, column=1, sticky=W)
        self.typ_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_model_choices())
        if self.product_types:
            self.typ_var.set(self.product_types[0]["name"])

        ttkb.Label(form, text="Modell").grid(row=1, column=0, sticky=W, pady=5)
        self.model_box = ttkb.Combobox(form, textvariable=self.modell_var, width=32, state="readonly")
        self.model_box.grid(row=1, column=1, sticky=W)

        ttkb.Label(form, text="Kategorie").grid(row=2, column=0, sticky=W, pady=5)
        self.category_box = ttkb.Combobox(
            form,
            textvariable=self.kategorie_var,
            values=[row["name"] for row in self.categories],
            state="readonly",
            width=32,
        )
        self.category_box.grid(row=2, column=1, sticky=W)

        ttkb.Label(form, text="Hersteller").grid(row=3, column=0, sticky=W, pady=5)
        ttkb.Entry(form, textvariable=self.hersteller_var, width=34).grid(row=3, column=1, sticky=W)

        ttkb.Label(form, text="Anschaffungsdatum").grid(row=4, column=0, sticky=W, pady=5)
        self.anschaffungsdatum_entry = DateEntry(form, dateformat=DATE_FORMAT, width=18)
        self.anschaffungsdatum_entry.grid(row=4, column=1, sticky=W)
        bind_date_entry(self.anschaffungsdatum_entry, self.anschaffungsdatum_var)

        ttkb.Label(form, text="Standort").grid(row=0, column=2, sticky=W, padx=(25, 5), pady=5)
        self.location_options: Dict[str, int] = {}
        location_values: List[str] = []
        for row in self.locations:
            label = self.db.location_label(row["id"]) or f"Standort #{row['id']}"
            label = f"{label} (#{row['id']})"
            self.location_options[label] = row["id"]
            location_values.append(label)
        self.location_box = ttkb.Combobox(
            form,
            textvariable=self.standort_var,
            values=location_values,
            state="readonly",
            width=38,
        )
        self.location_box.grid(row=0, column=3, sticky=W)
        if location_values:
            self.standort_var.set(location_values[0])

        ttkb.Label(form, text="Fahrzeug").grid(row=1, column=2, sticky=W, padx=(25, 5), pady=5)
        self.vehicle_options: Dict[str, int] = {
            self._format_vehicle(row): int(row["id"]) for row in self.vehicles
        }
        vehicle_values = ["Kein Fahrzeug"] + list(self.vehicle_options.keys())
        self.vehicle_box = ttkb.Combobox(
            form,
            textvariable=self.fahrzeug_var,
            values=vehicle_values,
            state="readonly",
            width=38,
        )
        self.vehicle_box.grid(row=1, column=3, sticky=W)
        self.vehicle_box.set("Kein Fahrzeug")

        ttkb.Label(form, text="Lagerort").grid(row=2, column=2, sticky=W, padx=(25, 5), pady=5)
        ttkb.Entry(form, textvariable=self.lagerort_var, width=40).grid(row=2, column=3, sticky=W)

        ttkb.Label(form, text="Status").grid(row=3, column=2, sticky=W, padx=(25, 5), pady=5)
        ttkb.Combobox(
            form,
            textvariable=self.status_var,
            values=[label for label, _ in STATUS_OPTIONS],
            state="readonly",
            width=20,
        ).grid(row=3, column=3, sticky=W)

        ttkb.Label(form, text="Interne Kennung Präfix").grid(row=4, column=2, sticky=W, padx=(25, 5), pady=5)
        ttkb.Entry(form, textvariable=self.interne_prefix_var, width=30).grid(row=4, column=3, sticky=W)

        interval_frame = ttkb.Frame(form)
        interval_frame.grid(row=5, column=0, columnspan=4, sticky=W, pady=(10, 0))
        ttkb.Checkbutton(
            interval_frame,
            text="STK aktiv",
            variable=self.stk_active,
            bootstyle="round-toggle",
        ).grid(row=0, column=0, sticky=W)
        ttkb.Label(interval_frame, text="Intervall (Monate)").grid(row=0, column=1, sticky=W, padx=5)
        ttkb.Entry(interval_frame, textvariable=self.stk_interval_var, width=6).grid(row=0, column=2, sticky=W)
        ttkb.Checkbutton(
            interval_frame,
            text="MTK aktiv",
            variable=self.mtk_active,
            bootstyle="round-toggle",
        ).grid(row=0, column=3, sticky=W, padx=(20, 0))
        ttkb.Label(interval_frame, text="Intervall (Monate)").grid(row=0, column=4, sticky=W, padx=5)
        ttkb.Entry(interval_frame, textvariable=self.mtk_interval_var, width=6).grid(row=0, column=5, sticky=W)

        serial_frame = ttkb.Labelframe(container, text="Seriennummern (eine pro Zeile)")
        serial_frame.pack(fill=BOTH, expand=True, pady=(15, 5))
        self.serial_text = tk.Text(serial_frame, height=10)
        self.serial_text.pack(fill=BOTH, expand=True)

        info_frame = ttkb.Labelframe(container, text="Informationstext")
        info_frame.pack(fill=BOTH, expand=True, pady=(5, 10))
        self.info_text = tk.Text(info_frame, height=4)
        self.info_text.pack(fill=BOTH, expand=True)

        button_frame = ttkb.Frame(container)
        button_frame.pack(fill=tk.X)
        ttkb.Button(button_frame, text="Speichern", command=self.save, bootstyle="success").pack(
            side=LEFT, padx=5
        )
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(
            side=LEFT, padx=5
        )

        self._refresh_model_choices()
        self.grab_set()

    def _refresh_model_choices(self) -> None:
        selected_type = None
        for row in self.product_types:
            if row["name"] == self.typ_var.get():
                selected_type = row["id"]
                break
        options = self.model_index.get(selected_type or -1, [])
        labels = [label for _, label in options]
        self.model_box.configure(values=labels)
        if labels:
            if self.modell_var.get() not in labels:
                self.modell_var.set(labels[0])
        else:
            self.modell_var.set("")

    def _format_vehicle(self, row: sqlite3.Row) -> str:
        label = row["name"] or ""
        if row["kennzeichen"]:
            label += f" [{row['kennzeichen']}]"
        return label

    def save(self) -> None:
        serials = [line.strip() for line in self.serial_text.get("1.0", tk.END).splitlines()]
        serials = [serial for serial in serials if serial]
        if not serials:
            Messagebox.show_error("Bitte geben Sie mindestens eine Seriennummer ein.", "Massenupload")
            return

        try:
            anschaffungsdatum = parse_date(self.anschaffungsdatum_var.get())
        except ValueError:
            Messagebox.show_error("Ungültiges Anschaffungsdatum", "Fehler")
            return

        try:
            stk_interval = int(self.stk_interval_var.get() or 0)
            mtk_interval = int(self.mtk_interval_var.get() or 0)
        except ValueError:
            Messagebox.show_error("Intervalle müssen Zahlen sein", "Fehler")
            return

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

        standort_id = self.location_options.get(self.standort_var.get())
        vehicle_label = self.fahrzeug_var.get()
        fahrzeug_id = None
        if vehicle_label and vehicle_label != "Kein Fahrzeug":
            fahrzeug_id = self.vehicle_options.get(vehicle_label)

        hersteller_name = self.hersteller_var.get().strip()
        produkt_hersteller_id: Optional[int] = None
        if hersteller_name:
            produkt_hersteller_id = self.manufacturer_index.get(hersteller_name)
            if not produkt_hersteller_id:
                try:
                    produkt_hersteller_id = self.db.add_product_manufacturer(hersteller_name)
                except sqlite3.IntegrityError:
                    row = next(
                        (row for row in self.db.list_product_manufacturers() if row["name"] == hersteller_name),
                        None,
                    )
                    if row:
                        produkt_hersteller_id = int(row["id"])
                self.product_manufacturers = self.db.list_product_manufacturers()
                self.manufacturer_index = {
                    row["name"]: int(row["id"]) for row in self.product_manufacturers
                }

        naechste_stk = None
        if anschaffungsdatum and self.stk_active.get() and stk_interval > 0:
            naechste_stk = add_months(anschaffungsdatum, stk_interval)
        naechste_mtk = None
        if anschaffungsdatum and self.mtk_active.get() and mtk_interval > 0:
            naechste_mtk = add_months(anschaffungsdatum, mtk_interval)

        status_value = STATUS_LABEL_TO_VALUE.get(self.status_var.get(), "im_dienst")
        informationstext = self.info_text.get("1.0", tk.END).strip()

        if standort_id is None and fahrzeug_id is None and not self.lagerort_var.get().strip():
            Messagebox.show_error(
                "Bitte Standort, Fahrzeug oder Lagerort angeben.",
                "Massenupload",
            )
            return

        created, errors = self.db.bulk_add_products(
            serials,
            name=self._derived_name(),
            typ=self.typ_var.get(),
            hersteller=self.hersteller_var.get(),
            anschaffungsdatum=anschaffungsdatum,
            kategorie_id=kategorie_id,
            standort_id=standort_id,
            fahrzeug_id=fahrzeug_id,
            status=status_value,
            interne_kennung_prefix=self.interne_prefix_var.get(),
            stk_intervall=stk_interval,
            mtk_intervall=mtk_interval,
            stk_aktiv=self.stk_active.get(),
            mtk_aktiv=self.mtk_active.get(),
            letzte_stk=None,
            letzte_mtk=None,
            naechste_stk=naechste_stk,
            naechste_mtk=naechste_mtk,
            lagerort=self.lagerort_var.get().strip(),
            produkt_typ_id=produkt_typ_id,
            produkt_modell_id=produkt_modell_id,
            produkt_hersteller_id=produkt_hersteller_id,
            informationstext=informationstext,
            user_id=self.user.id if self.user else None,
        )
        self.created = created
        self.errors = errors
        if created == 0 and not errors:
            self.errors = ["Es konnten keine Produkte angelegt werden."]
        self.destroy()

    def _derived_name(self) -> str:
        typ = self.typ_var.get().strip()
        modell = self.modell_var.get().strip()
        parts = [part for part in (typ, modell) if part]
        return " ".join(parts)
class VehicleEditor(LargeDialog):
    def __init__(
        self,
        master: tk.Misc,
        db: DatabaseManager,
        fahrzeug_id: Optional[int] = None,
        *,
        user: Optional[User] = None,
    ) -> None:
        super().__init__(master, min_width=820, min_height=640)
        self.db = db
        self.fahrzeug_id = fahrzeug_id
        self.saved = False
        self.title("Fahrzeug bearbeiten" if fahrzeug_id else "Neues Fahrzeug")
        self.user = user

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
        self.fahrgestell_var = ttkb.StringVar()
        default_vehicle_status = STATUS_VALUE_TO_LABEL.get("im_dienst", STATUS_OPTIONS[0][0])
        self.status_var = ttkb.StringVar(value=default_vehicle_status)
        self.decommission_var = ttkb.BooleanVar(value=False)
        self.decommission_date_var = ttkb.StringVar()

        form = ttkb.Labelframe(container, text="Fahrzeugdetails")
        form.pack(fill=BOTH, expand=True)
        form.columnconfigure(1, weight=1)

        ttkb.Label(form, text="Bezeichnung / Funkkennung*").grid(row=0, column=0, sticky=W, pady=5)
        ttkb.Entry(form, textvariable=self.name_var, width=40).grid(row=0, column=1, sticky=tk.EW)

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
        self.brand_box.grid(row=2, column=1, sticky=tk.EW)
        self.brand_box.bind("<<ComboboxSelected>>", lambda _event: self._update_model_choices())

        ttkb.Label(form, text="Modell").grid(row=3, column=0, sticky=W, pady=5)
        self.model_box = ttkb.Combobox(form, textvariable=self.model_var, width=37, state="readonly")
        self.model_box.grid(row=3, column=1, sticky=tk.EW)

        ttkb.Label(form, text="Kategorie").grid(row=4, column=0, sticky=W, pady=5)
        self.category_box = ttkb.Combobox(
            form,
            textvariable=self.category_var,
            values=[row["name"] for row in self.categories],
            state="readonly",
            width=37,
        )
        self.category_box.grid(row=4, column=1, sticky=tk.EW)

        ttkb.Label(form, text="Inbetriebnahme (TT.MM.JJJJ)").grid(row=5, column=0, sticky=W, pady=5)
        self.inbetriebnahme_entry = DateEntry(
            form,
            dateformat=DATE_FORMAT,
            width=18,
        )
        self.inbetriebnahme_entry.grid(row=5, column=1, sticky=W)
        bind_date_entry(self.inbetriebnahme_entry, self.inbetriebnahme_var)

        ttkb.Label(form, text="Standort").grid(row=6, column=0, sticky=W, pady=5)
        self.standort_box = ttkb.Combobox(
            form,
            textvariable=self.standort_var,
            values=[self._format_location(row) for row in self.locations],
            state="readonly",
            width=40,
        )
        self.standort_box.grid(row=6, column=1, sticky=tk.EW)

        ttkb.Label(form, text="Kilometerstand").grid(row=7, column=0, sticky=W, pady=5)
        ttkb.Entry(form, textvariable=self.kilometer_var, width=20).grid(row=7, column=1, sticky=W)

        ttkb.Label(form, text="Fahrgestellnummer").grid(row=8, column=0, sticky=W, pady=5)
        ttkb.Entry(form, textvariable=self.fahrgestell_var, width=30).grid(row=8, column=1, sticky=W)

        ttkb.Label(form, text="Status").grid(row=9, column=0, sticky=W, pady=5)
        ttkb.Combobox(
            form,
            textvariable=self.status_var,
            values=[label for label, _ in STATUS_OPTIONS],
            state="readonly",
            width=20,
        ).grid(row=9, column=1, sticky=W)

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
        self.decommission_entry = DateEntry(
            decommission_frame,
            dateformat=DATE_FORMAT,
            width=18,
        )
        self.decommission_entry.grid(row=0, column=2, sticky=W)
        bind_date_entry(self.decommission_entry, self.decommission_date_var)

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
        label = self.db.location_label(row["id"])
        if not label:
            label = f"Standort #{row['id']}"
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
        if hasattr(self.decommission_entry, "entry"):
            self.decommission_entry.entry.configure(state=state)
        if state == tk.DISABLED:
            if hasattr(self.decommission_entry, "entry"):
                self.decommission_entry.entry.delete(0, tk.END)
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
        if not self.inbetriebnahme_var.get():
            self.inbetriebnahme_entry.entry.delete(0, tk.END)
        if vehicle["standort_id"]:
            for row in self.locations:
                if row["id"] == vehicle["standort_id"]:
                    self.standort_var.set(self._format_location(row))
                    break
        self.kilometer_var.set(str(vehicle["kilometerstand"] or 0))
        self.fahrgestell_var.set(vehicle["fahrgestellnummer"] or "")
        status_value = vehicle["status"] or "im_dienst"
        self.status_var.set(display_status(status_value))
        self.decommission_var.set(bool(vehicle["ausserbetrieb"]))
        self.decommission_date_var.set(format_date(vehicle["ausserbetriebnahme_datum"]))
        if not self.decommission_date_var.get():
            self.decommission_entry.entry.delete(0, tk.END)
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
        fahrgestell = self.fahrgestell_var.get().strip()
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

        status_value = STATUS_LABEL_TO_VALUE.get(self.status_var.get(), "im_dienst")
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
            status=status_value,
            marke_id=brand_id,
            fahrzeugtyp_id=model_id,
            fahrzeugkategorie_id=category_id,
            ausserbetrieb=self.decommission_var.get(),
            ausserbetriebnahme=decommission_date,
            fahrgestellnummer=fahrgestell,
            user_id=self.user.id if self.user else None,
        )
        self.saved = True
        Messagebox.show_info("Fahrzeug gespeichert", "Erfolg")
        self.destroy()


class VehicleTransferDialog(ttkb.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        db: DatabaseManager,
        *,
        user: Optional[User] = None,
    ) -> None:
        super().__init__(master)
        self.db = db
        self.user = user
        self.moved = 0
        self.error = ""
        self.title("Produkte umhängen")
        self.geometry("420x220")
        self.resizable(False, False)

        vehicles = db.list_vehicles()
        if user and user.location_permissions:
            vehicles = [
                row
                for row in vehicles
                if user.can_write_location(row["standort_id"])
            ]
        self.vehicles = vehicles
        self.vehicle_labels: Dict[str, int] = {
            self._vehicle_label(row): int(row["id"]) for row in self.vehicles
        }

        if not self.vehicle_labels:
            Messagebox.show_info("Keine Fahrzeuge verfügbar.", "Fahrzeugtausch")
            self.destroy()
            return

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text="Quelle").grid(row=0, column=0, sticky=W, pady=5)
        self.source_var = ttkb.StringVar()
        ttkb.Combobox(
            container,
            textvariable=self.source_var,
            values=list(self.vehicle_labels.keys()),
            state="readonly",
            width=35,
        ).grid(row=0, column=1, sticky=W)

        ttkb.Label(container, text="Ziel").grid(row=1, column=0, sticky=W, pady=5)
        self.target_var = ttkb.StringVar(value="Kein Fahrzeug")
        target_values = ["Kein Fahrzeug"] + list(self.vehicle_labels.keys())
        ttkb.Combobox(
            container,
            textvariable=self.target_var,
            values=target_values,
            state="readonly",
            width=35,
        ).grid(row=1, column=1, sticky=W)

        button_frame = ttkb.Frame(container)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(20, 0))
        ttkb.Button(button_frame, text="Übertragen", command=self._on_transfer, bootstyle="success").pack(
            side=LEFT, padx=5
        )
        ttkb.Button(button_frame, text="Abbrechen", command=self.destroy, bootstyle="secondary").pack(
            side=LEFT, padx=5
        )

        self.grab_set()

    def _vehicle_label(self, row: sqlite3.Row) -> str:
        label = row["name"] or ""
        if row["kennzeichen"]:
            label += f" [{row['kennzeichen']}]"
        return label

    def _on_transfer(self) -> None:
        source_label = self.source_var.get()
        if not source_label:
            Messagebox.show_error("Bitte Quellfahrzeug auswählen", "Fahrzeugtausch")
            return
        source_id = self.vehicle_labels.get(source_label)
        if source_id is None:
            Messagebox.show_error("Ungültiges Quellfahrzeug", "Fahrzeugtausch")
            return
        target_label = self.target_var.get()
        target_id = None if target_label == "Kein Fahrzeug" else self.vehicle_labels.get(target_label)
        if target_id == source_id:
            Messagebox.show_error("Quell- und Zielfahrzeug dürfen nicht identisch sein.", "Fahrzeugtausch")
            return
        moved = self.db.transfer_vehicle_products(
            source_id,
            target_id,
            user_id=self.user.id if self.user else None,
        )
        self.moved = moved
        if moved == 0:
            self.error = "Es wurden keine Produkte übertragen."
        self.destroy()


class MaterialEditor(LargeDialog):
    def __init__(self, master: tk.Misc, db: DatabaseManager, material_id: Optional[int] = None) -> None:
        super().__init__(master, min_width=720, min_height=520)
        self.db = db
        self.material_id = material_id
        self.saved = False
        self.title("Material bearbeiten" if material_id else "Neues Material")

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
        self.expiry_entry = DateEntry(
            form,
            dateformat=DATE_FORMAT,
            width=18,
        )
        self.expiry_entry.grid(row=5, column=1, sticky=W)
        bind_date_entry(self.expiry_entry, self.expiry_var)
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
            label = self.db.location_label(row["id"])
            if label:
                options.append(label)
        return sorted(set(filter(None, options)))

    def _toggle_expiry(self) -> None:
        state = tk.NORMAL if self.expiry_active.get() else tk.DISABLED
        if not self.expiry_active.get():
            self.expiry_var.set("")
        self.expiry_entry.configure(state=state)
        if hasattr(self.expiry_entry, "entry"):
            self.expiry_entry.entry.configure(state=state)
            if state == tk.DISABLED:
                self.expiry_entry.entry.delete(0, tk.END)

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
        self.products_view: Optional[ProductsView] = None
        self.vehicles_view: Optional[VehiclesView] = None
        self.materials_view: Optional[MaterialsView] = None
        self.views: List[ttkb.Frame] = []

        login = LoginDialog(self, self.db)
        self.wait_window(login)
        if not login.user:
            self.destroy()
            return
        self.user = login.user
        self.db.set_active_mandant(self.user.mandant_id)
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
        self._build_menubar()
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

        layout = ttkb.Frame(self)
        layout.pack(fill=BOTH, expand=True, padx=10, pady=(0, 12))

        self.sidebar = NavigationSidebar(layout, on_select=self._on_sidebar_select)
        self.sidebar.pack(side=LEFT, fill=tk.Y, padx=(0, 16))
        self.sidebar.add_heading("Arbeitsbereiche")

        content = ttkb.Frame(layout)
        content.pack(side=LEFT, fill=BOTH, expand=True)

        self.view_container = ttkb.Frame(content)
        self.view_container.pack(fill=BOTH, expand=True)
        self.view_container.columnconfigure(0, weight=1)
        self.view_container.rowconfigure(0, weight=1)

        self.views = []
        self._view_map: Dict[str, ttkb.Frame] = {}
        self._nav_order: List[str] = []
        self._current_view: Optional[str] = None

        self.dashboard_view = DashboardView(self.view_container, self.db)
        self.dashboard_view.update_palette(self.current_theme in self._dark_themes())
        self._register_view("dashboard", "Dashboard", "🏠  Dashboard", self.dashboard_view)

        if self.user and self.user.can_read("produkte"):
            self.products_view = ProductsView(self.view_container, self.db, user=self.user)
            self.products_view.set_write_permissions(self.user.can_write("produkte"))
            self.products_view.set_user(self.user)
            self._register_view("products", "Produkte", "🗂️  Produkte", self.products_view)
        else:
            self.products_view = None

        if self.user and self.user.can_read("fahrzeuge"):
            self.vehicles_view = VehiclesView(self.view_container, self.db)
            self.vehicles_view.set_write_permissions(self.user.can_write("fahrzeuge"))
            self.vehicles_view.set_user(self.user)
            self._register_view("vehicles", "Fahrzeuge", "🚑  Fahrzeuge", self.vehicles_view)
        else:
            self.vehicles_view = None

        if self.user and self.user.can_read("material"):
            self.materials_view = MaterialsView(self.view_container, self.db)
            self.materials_view.set_write_permissions(self.user.can_write("material"))
            self.materials_view.set_user(self.user)
            self._register_view("materials", "Material", "📦  Material", self.materials_view)
        else:
            self.materials_view = None

        self.analytics_view = AnalyticsView(self.view_container, self.db)
        self._register_view("analytics", "Auswertung", "📊  Auswertung", self.analytics_view)

        show_locations = self.user.can_read("standorte") if self.user else True
        allow_edit_locations = self.user.can_write("standorte") if self.user else True
        self.master_view = MasterDataView(
            self.view_container,
            self.db,
            show_locations=show_locations,
            allow_edit_locations=allow_edit_locations,
        )
        self._register_view("masterdata", "Stammdaten", "🧱  Stammdaten", self.master_view)

        if self._nav_order:
            self._show_view(self._nav_order[0])

        self.after(500, self._notify_upcoming_items)

    def _register_view(
        self,
        key: str,
        tab_label: str,
        nav_label: str,
        view: ttkb.Frame,
    ) -> None:
        view.grid(row=0, column=0, sticky=tk.NSEW)
        view.grid_remove()
        self.views.append(view)
        self._view_map[key] = view
        self._nav_order.append(key)
        self.sidebar.add_item(key, nav_label, lambda k=key: self._on_sidebar_select(k))
        if self._current_view is None:
            self._show_view(key)

    def _on_sidebar_select(self, key: str) -> None:
        self._show_view(key)

    def _show_view(self, key: str) -> None:
        if key not in self._view_map:
            return
        if self._current_view and self._current_view in self._view_map:
            self._view_map[self._current_view].grid_remove()
        view = self._view_map[key]
        view.grid()
        self._current_view = key
        self.sidebar.select(key)
        if hasattr(view, "refresh"):
            view.refresh()  # type: ignore[call-arg]

    def _build_menubar(self) -> None:
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Backup wiederherstellen", command=self.restore_backup_dialog)
        file_menu.add_command(label="Archivieren", command=self.archive_logs)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.on_closing)
        menubar.add_cascade(label="Datei", menu=file_menu)

        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Globale Suche", command=self.open_global_search)
        tools_menu.add_command(label="ICS importieren", command=self.import_ics_dialog)
        tools_menu.add_command(label="Logbuch", command=self.show_log_viewer)
        tools_menu.add_command(label="Konfiguration", command=self.open_configuration)
        tools_menu.add_command(label="Bestellungen", command=self.open_order_center)
        menubar.add_cascade(label="Werkzeuge", menu=tools_menu)

        governance_menu = tk.Menu(menubar, tearoff=0)
        governance_menu.add_command(label="Freigabecenter", command=self.open_approval_center)
        governance_menu.add_command(label="CAPA-Board", command=self.open_capa_board)
        governance_menu.add_command(label="Compliance-Assistent", command=self.open_compliance_assistant)
        governance_menu.add_command(label="Schulungsnachweise", command=self.open_training_center)
        governance_menu.add_command(label="Operations-Cockpit", command=self.open_operations_cockpit)
        governance_menu.add_separator()
        governance_menu.add_command(label="Dashboard gestalten", command=self.open_dashboard_designer)
        governance_menu.add_command(label="Filter-Bibliothek", command=self.open_filter_library)
        menubar.add_cascade(label="Governance", menu=governance_menu)

        account_menu = tk.Menu(menubar, tearoff=0)
        account_menu.add_command(label="Mein Konto", command=self.open_account_dialog)
        account_menu.add_command(label="Passwort ändern", command=self.open_password_dialog)
        menubar.add_cascade(label="Konto", menu=account_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Hilfe", command=self.open_help)
        help_menu.add_command(label="Systemstatus", command=self.show_migration_status)
        menubar.add_cascade(label="Hilfe", menu=help_menu)

        self.config(menu=menubar)

    def refresh_current(self) -> None:
        if self._current_view:
            view = self._view_map.get(self._current_view)
            if view and hasattr(view, "refresh"):
                view.refresh()  # type: ignore[call-arg]

    def refresh_all(self) -> None:
        for view in self.views:
            if hasattr(view, "refresh"):
                view.refresh()  # type: ignore[call-arg]

    def on_closing(self) -> None:
        try:
            self.db.create_backup()
        except Exception:
            pass
        self.db.close()
        self.destroy()

    def restore_backup_dialog(self) -> None:
        filename = filedialog.askopenfilename(
            title="Backup auswählen",
            filetypes=[("SQLite", "*.db"), ("Alle Dateien", "*.*")],
        )
        if not filename:
            return
        try:
            self.db.restore_backup(Path(filename))
        except Exception as exc:  # pragma: no cover - UI feedback
            Messagebox.show_error(str(exc), "Fehler beim Wiederherstellen")
            return
        Messagebox.show_info(
            "Backup wurde eingespielt. Bitte Anwendung neu starten, um mit den Daten zu arbeiten.",
            "Backup wiederhergestellt",
        )

    def archive_logs(self) -> None:
        try:
            archive_path = self.db.archive_logs()
        except Exception as exc:  # pragma: no cover - UI feedback
            Messagebox.show_error(str(exc), "Archivierung fehlgeschlagen")
            return
        if archive_path:
            Messagebox.show_info(
                f"Systemlog wurde nach {archive_path} archiviert.",
                "Archiv erstellt",
            )
        else:
            Messagebox.show_info("Es gab keine veralteten Logeinträge.", "Keine Aktion erforderlich")

    def open_global_search(self) -> None:
        dialog = GlobalSearchDialog(self, self.db, self.user)
        self.wait_window(dialog)

    def import_ics_dialog(self) -> None:
        filename = filedialog.askopenfilename(
            title="ICS-Datei importieren",
            filetypes=[("Kalender", "*.ics"), ("Alle Dateien", "*.*")],
        )
        if not filename:
            return
        try:
            count = self.db.import_ics_events(Path(filename))
        except Exception as exc:  # pragma: no cover - UI feedback
            Messagebox.show_error(str(exc), "Import fehlgeschlagen")
            return
        Messagebox.show_info(f"{count} Termine importiert.", "ICS Import")

    def show_log_viewer(self) -> None:
        dialog = LogViewerDialog(self, self.db)
        self.wait_window(dialog)

    def open_configuration(self) -> None:
        dialog = ConfigurationDialog(
            self,
            backup_dir=self.preferences.get("backup_dir", ""),
            reminder_days=int(self.preferences.get("reminder_days", "7")),
        )
        self.wait_window(dialog)
        if not dialog.result:
            return
        backup_dir, reminder_days = dialog.result
        if self.user:
            self.db.set_user_preference(self.user.id, "backup_dir", backup_dir)
            self.db.set_user_preference(self.user.id, "reminder_days", str(reminder_days))
            self.preferences["backup_dir"] = backup_dir
            self.preferences["reminder_days"] = str(reminder_days)

    def open_order_center(self) -> None:
        dialog = OrderCenterDialog(self, self.db, self.user)
        self.wait_window(dialog)

    def open_approval_center(self) -> None:
        dialog = ApprovalCenterDialog(self, self.db, self.user)
        self.wait_window(dialog)
        self.refresh_all()

    def open_capa_board(self) -> None:
        dialog = CapaBoardDialog(self, self.db)
        self.wait_window(dialog)

    def open_compliance_assistant(self) -> None:
        dialog = ComplianceAssistantDialog(self, self.db)
        self.wait_window(dialog)

    def open_training_center(self) -> None:
        if not self.user:
            return
        dialog = TrainingCenterDialog(self, self.db, self.user)
        self.wait_window(dialog)

    def open_operations_cockpit(self) -> None:
        dialog = OperationsCockpitDialog(self, self.db)
        self.wait_window(dialog)

    def open_dashboard_designer(self) -> None:
        if not self.user:
            return
        dialog = DashboardDesignerDialog(self, self.db, self.user)
        self.wait_window(dialog)

    def open_filter_library(self) -> None:
        if not self.user:
            return
        dialog = FilterLibraryDialog(self, self.db, self.user)
        self.wait_window(dialog)

    def open_account_dialog(self) -> None:
        if not self.user:
            return
        row = self.db.get_user(self.user.id)
        if not row:
            Messagebox.show_error("Benutzer konnte nicht geladen werden", "Fehler")
            return
        dialog = AccountDialog(
            self,
            self.db,
            user_id=self.user.id,
            vorname=row["vorname"] or "",
            nachname=row["nachname"] or "",
            email=row["email"] or "",
            language=self.preferences.get("language", "de"),
            theme=self.current_theme,
        )
        self.wait_window(dialog)
        if not dialog.result:
            return
        vorname, nachname, email, language, theme = dialog.result
        self.db.update_user_profile(
            benutzer_id=self.user.id,
            vorname=vorname,
            nachname=nachname,
            email=email,
        )
        self.db.set_user_preference(self.user.id, "language", language)
        self.preferences["language"] = language
        self.user.full_name = f"{vorname} {nachname}".strip()
        self.user.email = email
        self.welcome_label.configure(
            text=f"Willkommen {self.user.full_name} ({self.user.role})"
        )
        if theme != self.current_theme:
            self._apply_theme(theme)

    def open_password_dialog(self) -> None:
        if not self.user:
            return
        dialog = PasswordChangeDialog(self)
        self.wait_window(dialog)
        if not dialog.result:
            return
        old_password, new_password = dialog.result
        authenticated = self.db.authenticate(
            self.user.username,
            old_password,
            identifier=self.user.username,
        )
        if not authenticated:
            Messagebox.show_error("Aktuelles Passwort ist falsch", "Fehler")
            return
        self.db.set_user_password(self.user.id, new_password)
        Messagebox.show_info("Passwort wurde aktualisiert", "Erfolg")

    def open_help(self) -> None:
        dialog = HelpDialog(self)
        self.wait_window(dialog)

    def show_migration_status(self) -> None:
        Messagebox.show_info(
            "Datenbank-Schema ist aktuell. Neue Tabellen und Spalten werden automatisch angelegt.",
            "Schema-Status",
        )

    def _notify_upcoming_items(self) -> None:
        try:
            due_products = self.db.due_products()
            expired = self.db.expired_materials()
            low_stock = self.db.low_stock_materials()
        except Exception:
            return
        reminder_days = int(self.preferences.get("reminder_days", "7"))
        messages = []
        if due_products:
            messages.append(f"{len(due_products)} Produkte benötigen Wartung.")
        if expired:
            messages.append(f"{len(expired)} Materialien sind abgelaufen.")
        if low_stock:
            messages.append(f"{len(low_stock)} Materialien unterschreiten den Soll-Bestand.")
        if not messages:
            return
        Messagebox.show_info(
            "\n".join(messages) + f"\n\nErinnerungszeitraum: {reminder_days} Tage.",
            "Anstehende Aufgaben",
        )

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
        sidebar_bg = "#0f172a" if self.current_theme in self._dark_themes() else "#f1f5f9"
        sidebar_fg = "#f8fafc" if self.current_theme in self._dark_themes() else "#0f172a"
        self.style.configure("KpiCard.TFrame", borderwidth=1, relief="ridge")
        self.style.configure("KpiTitle.TLabel", foreground=accent, font=("Inter", 11, "bold"))
        self.style.configure("KpiValue.TLabel", foreground=card_fg, font=("Inter", 26, "bold"))
        self.style.configure("Sidebar.TFrame", background=sidebar_bg)
        self.style.configure("SidebarInner.TFrame", background=sidebar_bg)
        self.style.configure(
            "SidebarHeading.TLabel",
            background=sidebar_bg,
            foreground=sidebar_fg,
            font=("Inter", 11, "bold"),
        )

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


class ApprovalCenterDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, db: DatabaseManager, user: Optional[User]) -> None:
        super().__init__(master)
        self.title("Freigabecenter")
        self.geometry("720x440")
        self.db = db
        self.user = user

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        toolbar = ttkb.Frame(container)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttkb.Button(toolbar, text="Freigeben", command=lambda: self._update_status("genehmigt"), bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Ablehnen", command=lambda: self._update_status("abgelehnt"), bootstyle="danger").pack(side=LEFT, padx=8)

        columns = [
            {"text": "ID"},
            {"text": "Produkt"},
            {"text": "Schritt"},
            {"text": "Status"},
            {"text": "Kommentar"},
        ]
        self.table = Tableview(container, coldata=columns, rowdata=[], pagesize=18)
        self.table.pack(fill=BOTH, expand=True)
        self.refresh()
        self.grab_set()

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_product_approvals():
            self.table.insert_row(
                rowkey=row["id"],
                values=(
                    row["id"],
                    f"{row['produkt_name']} ({row['seriennummer']})" if row["produkt_name"] else row["seriennummer"],
                    row["schritt"],
                    row["status"],
                    row["kommentar"] or "",
                ),
            )

    def _update_status(self, status: str) -> None:
        selected = self.table.get_selected_row()
        if not selected:
            Messagebox.show_warning("Bitte Eintrag auswählen", "Hinweis")
            return
        dialog = SimpleEntryDialog(self, "Kommentar", ["Kommentar"])
        self.wait_window(dialog)
        kommentar = dialog.result[0] if dialog and dialog.result else ""
        self.db.update_product_approval_status(
            int(selected.key),
            status=status,
            benutzer_id=self.user.id if self.user else None,
            kommentar=kommentar,
        )
        self.refresh()


class CapaBoardDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.title("CAPA-Board")
        self.geometry("700x440")
        self.db = db

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        toolbar = ttkb.Frame(container)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttkb.Button(toolbar, text="Neue Maßnahme", command=self.create_action, bootstyle="success").pack(side=LEFT)
        ttkb.Button(toolbar, text="Erledigt", command=lambda: self._change_status("erledigt"), bootstyle="secondary").pack(side=LEFT, padx=8)

        columns = [
            {"text": "ID"},
            {"text": "Beschreibung"},
            {"text": "Produkt"},
            {"text": "Fällig"},
            {"text": "Status"},
        ]
        self.table = Tableview(container, coldata=columns, rowdata=[], pagesize=18)
        self.table.pack(fill=BOTH, expand=True)
        self.refresh()
        self.grab_set()

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_capa_actions():
            self.table.insert_row(
                rowkey=row["id"],
                values=(
                    row["id"],
                    row["beschreibung"],
                    row["produkt_name"] or "",
                    row["faellig_am"] or "",
                    row["status"],
                ),
            )

    def create_action(self) -> None:
        dialog = SimpleEntryDialog(self, "Neue Maßnahme", ["Beschreibung", "Produkt-ID", "Fälligkeitsdatum (YYYY-MM-DD)"])
        self.wait_window(dialog)
        if not dialog.result:
            return
        beschreibung, produkt_id, faellig_text = dialog.result
        produkt_ref = int(produkt_id) if produkt_id.strip() else None
        faellig = None
        if faellig_text.strip():
            try:
                faellig = datetime.strptime(faellig_text.strip(), "%Y-%m-%d").date()
            except ValueError:
                Messagebox.show_warning("Datum konnte nicht interpretiert werden", "Hinweis")
                return
        self.db.create_capa_action(
            produkt_id=produkt_ref,
            beschreibung=beschreibung,
            faellig_am=faellig,
            verantwortlicher_id=None,
        )
        self.refresh()

    def _change_status(self, status: str) -> None:
        selected = self.table.get_selected_row()
        if not selected:
            Messagebox.show_warning("Bitte Eintrag auswählen", "Hinweis")
            return
        self.db.update_capa_status(int(selected.key), status=status)
        self.refresh()


class ComplianceAssistantDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.title("Compliance-Assistent")
        self.geometry("640x420")
        self.db = db

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        toolbar = ttkb.Frame(container)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttkb.Button(toolbar, text="Regelwerk hinzufügen", command=self.add_regelwerk, bootstyle="success").pack(side=LEFT)

        columns = [
            {"text": "Name"},
            {"text": "Beschreibung"},
            {"text": "Intervall"},
        ]
        self.table = Tableview(container, coldata=columns, rowdata=[], pagesize=16)
        self.table.pack(fill=BOTH, expand=True)
        self.refresh()
        self.grab_set()

    def refresh(self) -> None:
        self.table.delete_rows()
        for row in self.db.list_regelwerke():
            self.table.insert_row(
                rowkey=row["id"],
                values=(row["name"], row["beschreibung"] or "", row["intervall_monate"] or "-"),
            )

    def add_regelwerk(self) -> None:
        dialog = SimpleEntryDialog(self, "Regelwerk", ["Name", "Beschreibung", "Intervall (Monate)"])
        self.wait_window(dialog)
        if not dialog.result:
            return
        name, beschreibung, intervall = dialog.result
        months = int(intervall) if intervall.strip() else None
        self.db.save_regelwerk(
            regelwerk_id=None,
            name=name,
            beschreibung=beschreibung,
            intervall_monate=months,
        )
        self.refresh()


class TrainingCenterDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, db: DatabaseManager, user: User) -> None:
        super().__init__(master)
        self.title("Schulungsnachweise")
        self.geometry("640x420")
        self.db = db
        self.user = user

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text=f"Nachweise für {user.full_name}", font=("Helvetica", 12, "bold")).pack(pady=(0, 10))

        columns = [
            {"text": "Titel"},
            {"text": "Version"},
            {"text": "Bestätigt"},
        ]
        self.table = Tableview(container, coldata=columns, rowdata=[], pagesize=14)
        self.table.pack(fill=BOTH, expand=True)

        ttkb.Button(container, text="Schulung bestätigen", command=self.confirm_selected, bootstyle="success").pack(pady=10)
        self.refresh()
        self.grab_set()

    def refresh(self) -> None:
        self.table.delete_rows()
        confirmations = {row["verfahren_id"]: row for row in self.db.list_user_trainings(self.user.id)}
        for row in self.db.list_verfahren():
            bestaetigt = confirmations.get(row["id"])
            self.table.insert_row(
                rowkey=row["id"],
                values=(row["titel"], row["version"], bestaetigt["bestaetigt_am"] if bestaetigt else ""),
            )

    def confirm_selected(self) -> None:
        selected = self.table.get_selected_row()
        if not selected:
            Messagebox.show_warning("Bitte Schulung auswählen", "Hinweis")
            return
        self.db.confirm_training(benutzer_id=self.user.id, verfahren_id=int(selected.key))
        self.refresh()


class OperationsCockpitDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, db: DatabaseManager) -> None:
        super().__init__(master)
        self.title("Operations-Cockpit")
        self.geometry("520x320")
        self.db = db

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        self.stats_label = ttkb.Label(container, text="", justify=tk.LEFT, font=("Helvetica", 11))
        self.stats_label.pack(fill=BOTH, expand=True)

        ttkb.Button(container, text="Snapshot speichern", command=self.save_snapshot, bootstyle="info").pack(pady=12)
        self.refresh()
        self.grab_set()

    def refresh(self) -> None:
        material = self.db.material_statistics()
        stats = [
            f"Produkte gesamt: {len(self.db.list_products())}",
            f"Materialpositionen: {material['total_items']}",
            f"Materialbestand: {material['total_bestand']}",
            f"Offene Freigaben: {len(self.db.list_product_approvals(status='offen'))}",
        ]
        self.stats_label.configure(text="\n".join(stats))

    def save_snapshot(self) -> None:
        daten = {
            "zeitpunkt": datetime.utcnow().isoformat(timespec="seconds"),
            "produkte": len(self.db.list_products()),
            "material": self.db.material_statistics(),
        }
        self.db.record_cockpit_snapshot(daten)
        Messagebox.show_info("Snapshot gespeichert", "Erfolg")


class DashboardDesignerDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, db: DatabaseManager, user: User) -> None:
        super().__init__(master)
        self.title("Dashboard gestalten")
        self.geometry("420x260")
        self.db = db
        self.user = user

        container = ttkb.Frame(self, padding=20)
        container.pack(fill=BOTH, expand=True)

        ttkb.Label(container, text="Widgets auswählen", font=("Helvetica", 12, "bold")).pack(pady=(0, 10))
        self.widgets: Dict[str, ttkb.BooleanVar] = {
            "kpi": ttkb.BooleanVar(value=True),
            "diagramm": ttkb.BooleanVar(value=True),
            "warnungen": ttkb.BooleanVar(value=True),
        }
        for key, var in self.widgets.items():
            ttkb.Checkbutton(
                container,
                text=key.capitalize(),
                variable=var,
                bootstyle="round-toggle",
            ).pack(anchor=tk.W)

        ttkb.Button(container, text="Speichern", command=self.save, bootstyle="success").pack(pady=15)
        self.grab_set()

    def save(self) -> None:
        layout = {key: var.get() for key, var in self.widgets.items()}
        self.db.save_dashboard_layout(self.user.id, layout)
        Messagebox.show_info("Dashboard-Einstellungen gespeichert", "Erfolg")
        self.destroy()


class FilterLibraryDialog(ttkb.Toplevel):
    def __init__(self, master: tk.Misc, db: DatabaseManager, user: User) -> None:
        super().__init__(master)
        self.title("Filter-Bibliothek")
        self.geometry("540x360")
        self.db = db
        self.user = user

        container = ttkb.Frame(self, padding=15)
        container.pack(fill=BOTH, expand=True)

        toolbar = ttkb.Frame(container)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ttkb.Button(toolbar, text="Filter speichern", command=self.save_filter, bootstyle="success").pack(side=LEFT)

        columns = [
            {"text": "Bereich"},
            {"text": "Name"},
            {"text": "Erstellt"},
        ]
        self.table = Tableview(container, coldata=columns, rowdata=[], pagesize=16)
        self.table.pack(fill=BOTH, expand=True)
        self.refresh()
        self.grab_set()

    def refresh(self) -> None:
        self.table.delete_rows()
        for bereich in ["produkte", "fahrzeuge", "material", "standorte"]:
            for row in self.db.list_filter_sets(self.user.id, bereich):
                self.table.insert_row(
                    values=(bereich.capitalize(), row["name"], row["erstellt_am"]),
                )

    def save_filter(self) -> None:
        dialog = SimpleEntryDialog(
            self,
            "Filter speichern",
            ["Bereich (produkte/fahrzeuge/material/standorte)", "Bezeichnung"],
        )
        self.wait_window(dialog)
        if not dialog.result:
            return
        area, name = dialog.result
        area = area.strip().lower() or "produkte"
        if area not in {"produkte", "fahrzeuge", "material", "standorte"}:
            Messagebox.show_warning("Bereich wird nicht unterstützt", "Hinweis")
            return
        self.db.save_filter_set(
            benutzer_id=self.user.id,
            bereich=area,
            name=name,
            daten={},
        )
        self.refresh()


if __name__ == "__main__":
    app = MedizinprodukteApp()
    app.mainloop()
