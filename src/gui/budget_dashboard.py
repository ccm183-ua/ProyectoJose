"""
Dashboard de presupuestos existentes (PySide6).

Muestra los presupuestos organizados por carpetas de estado (pestañas
dinámicas) a partir de la ruta configurada en PATH_OPEN_BUDGETS.

Funcionalidades:
- Columnas redimensionables (arrastrar bordes de cabecera).
- Ordenación por cualquier columna (clic en cabecera).
- Menú contextual para mover proyectos entre carpetas de estado.
- Toggle entre vista Excel y vista explorador de archivos.
- Orden personalizado de pestañas.
"""

import os
import re
import shutil
import subprocess
import sys
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
)

from src.core import folder_scanner
from src.core.budget_cache import cleanup_orphaned_cache
from src.core.project_data_resolver import build_relation_index, resolve_projects
from src.core.settings import Settings
from src.gui import theme
from src.utils.budget_utils import RE_PROJECT_NUM, normalize_date
from src.utils.helpers import run_in_background

# ── Columnas del modo presupuestos ────────────────────────────────────

_COLUMNS = [
    ("Nº", 70),
    ("Proyecto", 220),
    ("Cliente", 160),
    ("Administración", 180),
    ("Dirección", 220),
    ("Tipo obra", 120),
    ("Fecha", 90),
    ("Bruto", 100),
    ("IVA", 90),
    ("Total+IVA", 110),
    ("Origen", 90),
    ("Finalizado", 90),
    ("Calidad", 80),
]

# ── Columnas del modo explorador ──────────────────────────────────────

_EXPLORER_COLUMNS = [
    ("Nombre", 320),
    ("Extensión", 80),
    ("Tamaño", 90),
    ("Fecha modificación", 140),
]

_SEARCH_KEYS = (
    "nombre_proyecto", "cliente", "administracion_nombre", "direccion", "localidad", "tipo_obra", "numero",
    "fuente_datos",
)

# Rol de datos para almacenar la referencia al dict de datos original en los ítems
_DATA_REF_ROLE = Qt.ItemDataRole.UserRole + 1

# ── Orden personalizado de pestañas ───────────────────────────────────

_TAB_ORDER = [
    "PTE. PRESUPUESTAR",
    "PRESUPUESTADO",
    "EJECUTAR",
    "EJECUTANDO",
    "TERMINADO",
    "ANULADOS",
    "MODELO INFORME",
    "MODELOS DE PRESUPUESTOS",
]

# Carpetas que son estados de proyecto (para menú "Mover a...")
_STATE_FOLDERS = [
    "PTE. PRESUPUESTAR",
    "PRESUPUESTADO",
    "EJECUTAR",
    "EJECUTANDO",
    "TERMINADO",
    "ANULADOS",
]

_CENTER_BUDGET_COLS = {0, 6, 7, 8, 9}


def _sort_tabs(states: list[str]) -> list[str]:
    """Ordena las pestañas según ``_TAB_ORDER``; las no listadas van al final."""
    order_map = {name.upper(): i for i, name in enumerate(_TAB_ORDER)}
    return sorted(states, key=lambda s: order_map.get(s.upper(), 999))


# ── Parseo de número de proyecto para ordenación numérica ─────────────


def _project_sort_key(numero: str) -> float:
    """Convierte un número de proyecto como '71-26' en un valor numérico
    para ordenación correcta.  Resultado: ``año * 10000 + número``.

    Ejemplos:
        '71-26' → 260071   (año 26, proyecto 71)
        '9-26'  → 260009
        '8-26'  → 260008
    Si no se puede parsear, devuelve -1 para que quede al final.
    """
    m = RE_PROJECT_NUM.search(numero)
    if m:
        num = int(m.group(1))
        year = int(m.group(2))
        return year * 10000 + num
    return -1.0


# ── QTableWidgetItem con ordenación inteligente ───────────────────────

class _SortableItem(QTableWidgetItem):
    """Item de tabla que permite ordenar correctamente por valor subyacente.

    Almacena el valor real (float, str) en ``Qt.UserRole`` y lo usa
    para la comparación ``<`` en lugar del texto visible.
    """

    def __init__(self, display_text: str, sort_value=None):
        super().__init__(display_text)
        self.setData(Qt.ItemDataRole.UserRole, sort_value if sort_value is not None else display_text)

    def __lt__(self, other: QTableWidgetItem):
        my_val = self.data(Qt.ItemDataRole.UserRole)
        other_val = other.data(Qt.ItemDataRole.UserRole) if other else None

        # Ambos numéricos → comparar como float
        if isinstance(my_val, (int, float)) and isinstance(other_val, (int, float)):
            return my_val < other_val

        # Ambos str → comparar como str case-insensitive
        return str(my_val or "").lower() < str(other_val or "").lower()


class BudgetDashboardFrame(QMainWindow):
    """Ventana principal del dashboard de presupuestos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Presupuestos existentes")
        self.resize(1060, 650)
        self._parent = parent
        self._settings = Settings()

        self._tab_data: dict[str, list[dict]] = {}
        self._tab_tables: dict[str, QTableWidget] = {}
        self._tab_searches: dict[str, QLineEdit] = {}
        self._state_names: list[str] = []
        self._relation_index: dict = {}
        self._root_path: str = ""
        self._explorer_mode: bool = False
        self._show_extra_columns: bool = True

        self._build_ui()
        self._center()
        self._load_data()

    def _center(self):
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Header ---
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, 0)

        top_row = QHBoxLayout()
        title = theme.create_title(header, "Presupuestos", "2xl")
        top_row.addWidget(title, 1)

        # Botón toggle explorador / Excel
        self._btn_toggle_mode = QPushButton("Explorador", header)
        self._btn_toggle_mode.setFont(theme.font_base())
        self._btn_toggle_mode.setFixedHeight(36)
        self._btn_toggle_mode.setCheckable(True)
        self._btn_toggle_mode.setToolTip(
            "Alternar entre vista de presupuestos Excel y explorador de archivos"
        )
        self._btn_toggle_mode.clicked.connect(self._on_toggle_mode)
        top_row.addWidget(self._btn_toggle_mode)

        btn_refresh = QPushButton("\u27F3 Actualizar", header)
        btn_refresh.setFont(theme.font_base())
        btn_refresh.setFixedHeight(36)
        btn_refresh.setToolTip("Recargar presupuestos desde las carpetas")
        btn_refresh.clicked.connect(self._load_data)
        top_row.addWidget(btn_refresh)

        self._btn_toggle_extra = QPushButton("Ocultar datos extra", header)
        self._btn_toggle_extra.setFont(theme.font_base())
        self._btn_toggle_extra.setFixedHeight(36)
        self._btn_toggle_extra.setCheckable(True)
        self._btn_toggle_extra.setChecked(True)
        self._btn_toggle_extra.setToolTip("Mostrar/ocultar Origen, Finalizado y Calidad")
        self._btn_toggle_extra.clicked.connect(self._on_toggle_extra_columns)
        top_row.addWidget(self._btn_toggle_extra)

        self._btn_reset_columns = QPushButton("Restaurar columnas", header)
        self._btn_reset_columns.setFont(theme.font_base())
        self._btn_reset_columns.setFixedHeight(36)
        self._btn_reset_columns.setToolTip("Mostrar todas las columnas del dashboard")
        self._btn_reset_columns.clicked.connect(self._on_reset_columns)
        top_row.addWidget(self._btn_reset_columns)

        header_layout.addLayout(top_row)

        root_path = self._settings.get_default_path(Settings.PATH_OPEN_BUDGETS) or ""
        hint = root_path if root_path else "Ruta no configurada"
        self._subtitle = theme.create_text(header, hint, muted=True)
        header_layout.addWidget(self._subtitle)
        header_layout.addSpacing(theme.SPACE_MD)

        main_layout.addWidget(header)

        # --- Notebook ---
        self._notebook = QTabWidget(central)
        self._notebook.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self._notebook, 1)

        # --- Toolbar ---
        toolbar = QWidget()
        toolbar.setProperty("class", "toolbar")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(theme.SPACE_LG, theme.SPACE_SM, theme.SPACE_LG, theme.SPACE_SM)

        self._btn_preview = self._tb_button(toolbar, "Previsualizar", self._on_preview)
        self._btn_edit = self._tb_button(toolbar, "Editar \u25BC", self._on_edit_menu)
        self._btn_complete = self._tb_button(toolbar, "Completar datos", self._on_complete_data)
        self._btn_refresh_selected = self._tb_button(
            toolbar, "Actualizar seleccionados", self._on_refresh_selected
        )
        self._btn_pdf = self._tb_button(toolbar, "Exportar PDF", self._on_export_pdf)
        self._btn_open = self._tb_button(toolbar, "Abrir Excel", self._on_open_excel, primary=True)
        self._btn_folder = self._tb_button(toolbar, "Abrir carpeta", self._on_open_folder)

        for btn in (self._btn_preview, self._btn_edit, self._btn_complete, self._btn_refresh_selected,
                    self._btn_pdf, self._btn_open, self._btn_folder):
            tb_layout.addWidget(btn)
        tb_layout.addStretch()

        main_layout.addWidget(toolbar)
        self.setCentralWidget(central)
        self._update_buttons()

    @staticmethod
    def _tb_button(parent, label, handler, primary=False):
        btn = QPushButton(label, parent)
        btn.setFont(theme.font_base())
        if primary:
            btn.setProperty("class", "primary")
        btn.clicked.connect(handler)
        return btn

    # ------------------------------------------------------------------
    # Toggle modo explorador / Excel
    # ------------------------------------------------------------------

    def _on_toggle_mode(self):
        self._explorer_mode = self._btn_toggle_mode.isChecked()
        if self._explorer_mode:
            self._btn_toggle_mode.setText("Solo Excel")
            self._btn_toggle_mode.setToolTip("Volver a la vista de presupuestos Excel")
            self._btn_toggle_extra.setEnabled(False)
            self._btn_reset_columns.setEnabled(False)
        else:
            self._btn_toggle_mode.setText("Explorador")
            self._btn_toggle_mode.setToolTip(
                "Alternar entre vista de presupuestos Excel y explorador de archivos"
            )
            self._btn_toggle_extra.setEnabled(True)
            self._btn_reset_columns.setEnabled(True)
        # Reconstruir pestañas manteniendo estado
        if self._state_names and self._root_path:
            current_tab = self._notebook.currentIndex()
            self._rebuild_tabs(self._state_names, self._root_path)
            if 0 <= current_tab < self._notebook.count():
                self._notebook.setCurrentIndex(current_tab)

    def _on_toggle_extra_columns(self):
        self._show_extra_columns = self._btn_toggle_extra.isChecked()
        if self._show_extra_columns:
            self._btn_toggle_extra.setText("Ocultar datos extra")
        else:
            self._btn_toggle_extra.setText("Mostrar datos extra")
        for state_name, table in self._tab_tables.items():
            if not self._explorer_mode and state_name in self._state_names:
                self._apply_extra_columns_visibility(table)

    def _apply_extra_columns_visibility(self, table: QTableWidget):
        # Columnas extra: Origen (10), Finalizado (11), Calidad (12)
        visible = self._show_extra_columns
        for col_idx in (10, 11, 12):
            if col_idx < table.columnCount():
                table.setColumnHidden(col_idx, not visible)
        self._resize_budget_columns(table)

    def _on_reset_columns(self):
        """Restaura columnas visibles del dashboard en todas las pestañas."""
        self._show_extra_columns = True
        self._btn_toggle_extra.setChecked(True)
        self._btn_toggle_extra.setText("Ocultar datos extra")
        for state_name, table in self._tab_tables.items():
            if self._explorer_mode or state_name not in self._state_names:
                continue
            for idx in range(table.columnCount()):
                table.setColumnHidden(idx, False)
            self._apply_extra_columns_visibility(table)

    def _resize_budget_columns(self, table: QTableWidget):
        """Ajusta anchos al mostrar/ocultar columnas extra."""
        if self._show_extra_columns:
            widths = [70, 220, 160, 180, 220, 120, 90, 100, 90, 110, 90, 90, 80]
        else:
            widths = [80, 280, 180, 220, 320, 170, 110, 120, 100, 140]
        for idx, width in enumerate(widths):
            if idx < table.columnCount():
                table.setColumnWidth(idx, width)

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------

    def _load_data(self):
        root_path = self._settings.get_default_path(Settings.PATH_OPEN_BUDGETS)
        if not root_path or not os.path.isdir(root_path):
            self._show_empty_state(
                "La ruta de presupuestos existentes no est\u00e1 configurada.\n\n"
                "Configura la ruta en Configuraci\u00f3n \u2192 Rutas por defecto."
            )
            return

        self._root_path = root_path
        self._subtitle.setText(root_path)
        self._show_empty_state("Cargando presupuestos\u2026")
        self._set_toolbar_enabled(False)

        def _scan():
            rel_index = build_relation_index()
            states = folder_scanner.scan_root(root_path)
            return rel_index, states

        def _on_done(ok, payload):
            self._set_toolbar_enabled(True)
            if not ok:
                self._show_empty_state(f"Error al cargar: {payload}")
                return
            rel_index, states = payload
            self._relation_index = rel_index
            if not states:
                self._show_empty_state("No se encontraron subcarpetas en:\n" + root_path)
                return
            # Ordenar según _TAB_ORDER
            states = _sort_tabs(states)
            self._rebuild_tabs(states, root_path)

        run_in_background(_scan, _on_done)

    def _set_toolbar_enabled(self, enabled):
        for btn in (self._btn_preview, self._btn_edit, self._btn_complete, self._btn_refresh_selected,
                    self._btn_pdf,
                    self._btn_open, self._btn_folder):
            btn.setEnabled(enabled)

    def _rebuild_tabs(self, states, root_path):
        self._notebook.blockSignals(True)
        self._notebook.clear()
        self._tab_data.clear()
        self._tab_tables.clear()
        self._tab_searches.clear()
        self._state_names = states

        for state_name in states:
            state_dir = os.path.join(root_path, state_name)

            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            tab_layout.setContentsMargins(
                theme.SPACE_MD, theme.SPACE_MD, theme.SPACE_MD, theme.SPACE_SM
            )

            search_widget, search_ctrl = self._create_search_box(tab_widget, state_name)
            tab_layout.addWidget(search_widget)
            self._tab_searches[state_name] = search_ctrl

            if self._explorer_mode:
                explorer_data = folder_scanner.scan_explorer(state_dir)
                self._tab_data[state_name] = explorer_data
                table = self._create_base_table(
                    tab_widget, _EXPLORER_COLUMNS,
                    self._on_explorer_dblclick,
                    self._on_explorer_context_menu, state_name,
                )
            else:
                scanned = folder_scanner.scan_projects(state_dir)
                resolved = resolve_projects(scanned, self._relation_index, state_name)
                self._tab_data[state_name] = resolved
                table = self._create_base_table(
                    tab_widget, _COLUMNS,
                    self._on_item_dblclick,
                    self._on_context_menu, state_name,
                )
                self._apply_extra_columns_visibility(table)

            tab_layout.addWidget(table, 1)
            self._tab_tables[state_name] = table
            self._notebook.addTab(tab_widget, f"  {state_name}  ")

        self._notebook.blockSignals(False)

        for state_name in states:
            if self._explorer_mode:
                self._populate_explorer_table(state_name)
            else:
                self._populate_table(state_name)

        if not self._explorer_mode:
            all_rutas = []
            for state_name in states:
                for proj in self._tab_data.get(state_name, []):
                    ruta = proj.get("ruta_excel", "")
                    if ruta:
                        all_rutas.append(ruta)
            if all_rutas:
                cleanup_orphaned_cache(all_rutas)

        self._update_buttons()

    def _create_base_table(self, parent, columns, dblclick_handler, ctx_menu_handler, state_name):
        """Crea y configura un QTableWidget con las propiedades comunes a ambos modos."""
        table = QTableWidget(parent)
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels([c[0] for c in columns])
        if not self._explorer_mode:
            for i in _CENTER_BUDGET_COLS:
                if i >= len(columns):
                    continue
                h_item = table.horizontalHeaderItem(i)
                if h_item:
                    h_item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                    )
        for i, (_, w) in enumerate(columns):
            table.setColumnWidth(i, w)

        hdr = table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        hdr.setStretchLastSection(True)
        hdr.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        hdr.customContextMenuRequested.connect(
            lambda pos, tbl=table: self._on_header_context_menu(tbl, pos)
        )

        table.setSortingEnabled(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)

        table.doubleClicked.connect(dblclick_handler)
        table.itemSelectionChanged.connect(self._update_buttons)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(
            lambda pos, sn=state_name: ctx_menu_handler(pos, sn)
        )
        return table

    @staticmethod
    def _align_budget_row_items(table: QTableWidget, row: int):
        """Centra solo Nº, Fecha y columnas de precio en una fila de presupuesto."""
        for col in _CENTER_BUDGET_COLS:
            if col >= table.columnCount():
                continue
            item = table.item(row, col)
            if item is not None:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                )

    def _on_header_context_menu(self, table: QTableWidget, pos):
        """Menú contextual en cabecera para ocultar/mostrar columnas."""
        header = table.horizontalHeader()
        col = header.logicalIndexAt(pos)

        menu = QMenu(self)
        act_hide = None
        if col >= 0:
            col_name_item = table.horizontalHeaderItem(col)
            col_name = col_name_item.text() if col_name_item else f"Columna {col + 1}"
            act_hide = menu.addAction(f"Ocultar columna: {col_name}")
        act_show_all = menu.addAction("Mostrar todas las columnas")

        action = menu.exec(header.mapToGlobal(pos))
        if act_hide is not None and action == act_hide:
            table.setColumnHidden(col, True)
        elif action == act_show_all:
            for idx in range(table.columnCount()):
                table.setColumnHidden(idx, False)
            # Reaplicar lógica de columnas extra del dashboard de presupuestos
            if not self._explorer_mode:
                self._apply_extra_columns_visibility(table)

    def _show_empty_state(self, message):
        self._notebook.blockSignals(True)
        self._notebook.clear()
        self._tab_data.clear()
        self._tab_tables.clear()
        self._tab_searches.clear()
        self._state_names = []

        empty_widget = QWidget()
        layout = QVBoxLayout(empty_widget)
        layout.addStretch()
        lbl = QLabel(message, empty_widget)
        lbl.setFont(theme.font_lg())
        lbl.setStyleSheet(f"color: {theme.TEXT_TERTIARY}; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

        self._notebook.addTab(empty_widget, "  Sin datos  ")
        self._notebook.blockSignals(False)
        self._update_buttons()

    # ------------------------------------------------------------------
    # Búsqueda
    # ------------------------------------------------------------------

    def _create_search_box(self, parent, state_name):
        search_widget = QWidget(parent)
        sz = QHBoxLayout(search_widget)
        sz.setContentsMargins(0, 0, 0, 0)

        label = theme.create_text(search_widget, "Buscar:")
        sz.addWidget(label)

        search = QLineEdit(search_widget)
        search.setFont(theme.font_base())
        search.setPlaceholderText("Proyecto, cliente, dirección...")
        search.setMinimumHeight(32)
        search.textChanged.connect(lambda: self._on_search(state_name))
        sz.addWidget(search, 1)

        return search_widget, search

    def _on_search(self, state_name):
        if self._explorer_mode:
            self._populate_explorer_table(state_name)
        else:
            self._populate_table(state_name)

    def _filter_rows(self, rows, query):
        q = (query or "").strip().lower()
        if not q:
            return rows
        out = []
        for r in rows:
            for k in _SEARCH_KEYS:
                v = str(r.get(k, "") or "").lower()
                if q in v:
                    out.append(r)
                    break
        return out

    def _filter_explorer_rows(self, rows, query):
        q = (query or "").strip().lower()
        if not q:
            return rows
        return [r for r in rows if q in r.get("nombre", "").lower()]

    # ------------------------------------------------------------------
    # Poblar tabla (modo presupuestos)
    # ------------------------------------------------------------------

    def _populate_table(self, state_name):
        table = self._tab_tables.get(state_name)
        if table is None:
            return

        # Deshabilitar sort mientras se insertan items
        table.setSortingEnabled(False)

        rows = self._tab_data.get(state_name, [])
        search_ctrl = self._tab_searches.get(state_name)
        query = search_ctrl.text() if search_ctrl else ""
        filtered = self._filter_rows(rows, query)

        table.setRowCount(len(filtered))
        for i, proj in enumerate(filtered):
            has_excel = bool(proj.get("ruta_excel")) and os.path.exists(
                proj.get("ruta_excel", "")
            )
            motivo = (proj.get("motivo_incompleto") or "").strip()
            has_warning = bool(motivo)
            nombre = proj.get("nombre_proyecto", "")
            if not has_excel or has_warning:
                nombre = f"\u26A0 {nombre}"

            numero = proj.get("numero", "")
            sort_key = _project_sort_key(numero)

            # Columna 0: Nº (número de proyecto, sort numérico)
            item_num = _SortableItem(numero, sort_key)
            item_num.setData(_DATA_REF_ROLE, i)
            table.setItem(i, 0, item_num)

            # Columna 1: Proyecto (sin prefijo numérico duplicado)
            nombre_display = re.sub(r"^(\u26A0\s*)?\d+-\d+\s*", r"\1", nombre)
            table.setItem(i, 1, _SortableItem(nombre_display, sort_key))
            item_proyecto = table.item(i, 1)
            if item_proyecto and has_warning:
                item_proyecto.setToolTip(motivo)
                item_proyecto.setForeground(QColor("#CC8B00"))

            # Columna 2: Cliente
            cliente = proj.get("cliente", "")
            table.setItem(i, 2, _SortableItem(cliente, cliente.lower()))

            # Columna 3: Administración
            admin_nombre = proj.get("administracion_nombre", "")
            table.setItem(i, 3, _SortableItem(admin_nombre, admin_nombre.lower()))

            # Columna 4: Dirección
            direccion = proj.get("direccion", "") or proj.get("localidad", "")
            table.setItem(i, 4, _SortableItem(direccion, direccion.lower()))

            # Columna 5: Tipo obra
            tipo = proj.get("tipo_obra", "")
            table.setItem(i, 5, _SortableItem(tipo, tipo.lower()))

            # Columna 6: Fecha
            fecha_raw = normalize_date(proj.get("fecha", ""))
            table.setItem(i, 6, _SortableItem(fecha_raw, fecha_raw))

            # Columnas 7, 8, 9: Bruto, IVA y Total+IVA (sort numérico)
            def _money_item(value, bold=False):
                text = ""
                sort_val = 0.0
                if value is not None:
                    try:
                        v = float(value)
                        sort_val = v
                        f = (
                            f"{v:,.2f}"
                            .replace(",", "X")
                            .replace(".", ",")
                            .replace("X", ".")
                        )
                        text = f"{f} \u20AC"
                    except (ValueError, TypeError):
                        pass
                item = _SortableItem(text, sort_val)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                if bold:
                    item.setFont(theme.get_font_bold(9))
                return item

            bruto_item = _money_item(proj.get("subtotal"))
            iva_item = _money_item(proj.get("iva"))
            total_item = _money_item(proj.get("total"), bold=True)
            table.setItem(i, 7, bruto_item)
            table.setItem(i, 8, iva_item)
            table.setItem(i, 9, total_item)

            # Columna 10: Origen (scan/finalizado)
            fuente = proj.get("fuente_datos", "scan")
            fuente_display = "Finalizado" if str(fuente).lower() == "finalizado" else "Escaneo"
            table.setItem(i, 10, _SortableItem(fuente_display, fuente_display.lower()))
            item_fuente = table.item(i, 10)
            if item_fuente:
                item_fuente.setForeground(
                    QColor("#2E7D32") if fuente_display == "Finalizado" else QColor("#3563A6")
                )

            # Columna 11: Finalizado (sí/no)
            finalizado = bool(proj.get("es_finalizado", False))
            finalizado_display = "Sí" if finalizado else "No"
            table.setItem(i, 11, _SortableItem(finalizado_display, 1 if finalizado else 0))
            item_finalizado = table.item(i, 11)
            if item_finalizado and finalizado:
                item_finalizado.setForeground(QColor("#2E7D32"))

            # Columna 12: Calidad (0-100)
            calidad = int(proj.get("calidad_datos", 0) or 0)
            calidad_text = f"{calidad}%"
            item_calidad = _SortableItem(calidad_text, calidad)
            item_calidad.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            table.setItem(i, 12, item_calidad)
            if calidad >= 80:
                item_calidad.setForeground(QColor("#1B5E20"))  # Verde oscuro
            elif calidad >= 60:
                item_calidad.setForeground(QColor("#66BB6A"))  # Verde claro
            elif calidad >= 40:
                item_calidad.setForeground(QColor("#F9A825"))  # Amarillo
            else:
                item_calidad.setForeground(QColor("#C62828"))  # Rojo

            # Color solo en indicadores de calidad/estado (no fila completa)
            datos_ok = proj.get("datos_completos", True)
            if not has_excel:
                # Resaltar solo el dato de calidad si no existe fichero
                item_calidad.setForeground(QColor(theme.TEXT_TERTIARY))
                item_calidad.setToolTip("El archivo Excel ya no existe en la ruta esperada.")
            elif has_warning:
                # Aviso funcional (no necesariamente error): sin coincidencia de hoja.
                item_calidad.setForeground(QColor("#CC8B00"))
                item_calidad.setToolTip(motivo)
            elif not datos_ok:
                tip = (
                    "No se pudieron obtener los datos completos de este presupuesto. "
                    "El Excel puede estar dañado o tener un formato inesperado."
                )
                if motivo:
                    tip += f"\nDetalle: {motivo}"
                item_calidad.setToolTip(tip)

            self._align_budget_row_items(table, i)

        # Re-habilitar sort y aplicar orden por defecto: Nº descendente (últimos primero)
        table.setSortingEnabled(True)
        table.sortItems(0, Qt.SortOrder.DescendingOrder)

        # Mantener título de pestaña limpio (sin contador de warnings)
        tab_idx = self._state_names.index(state_name) if state_name in self._state_names else -1
        if tab_idx >= 0:
            self._notebook.setTabText(tab_idx, f"  {state_name}  ")

        self._update_buttons()

    # ------------------------------------------------------------------
    # Poblar tabla (modo explorador)
    # ------------------------------------------------------------------

    def _populate_explorer_table(self, state_name):
        table = self._tab_tables.get(state_name)
        if table is None:
            return

        table.setSortingEnabled(False)

        rows = self._tab_data.get(state_name, [])
        search_ctrl = self._tab_searches.get(state_name)
        query = search_ctrl.text() if search_ctrl else ""
        filtered = self._filter_explorer_rows(rows, query)

        table.setRowCount(len(filtered))
        for i, entry in enumerate(filtered):
            nombre = entry.get("nombre", "")
            es_carpeta = entry.get("es_carpeta", False)
            prefix = "\U0001F4C1 " if es_carpeta else "\U0001F4C4 "

            # Nombre
            item_nombre = _SortableItem(prefix + nombre, nombre.lower())
            item_nombre.setData(_DATA_REF_ROLE, i)
            table.setItem(i, 0, item_nombre)

            # Extensión
            ext = entry.get("extension", "") if not es_carpeta else "Carpeta"
            table.setItem(i, 1, _SortableItem(ext, ext.lower()))

            # Tamaño
            tamano = entry.get("tamano", 0)
            if es_carpeta:
                tam_text = ""
                sort_tam = -1
            elif tamano < 1024:
                tam_text = f"{tamano} B"
                sort_tam = tamano
            elif tamano < 1024 * 1024:
                tam_text = f"{tamano / 1024:.1f} KB"
                sort_tam = tamano
            else:
                tam_text = f"{tamano / (1024 * 1024):.1f} MB"
                sort_tam = tamano
            item_tam = _SortableItem(tam_text, sort_tam)
            item_tam.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            table.setItem(i, 2, item_tam)

            # Fecha modificación
            fecha = entry.get("fecha_modificacion", "")
            table.setItem(i, 3, _SortableItem(fecha, fecha))

            # Color para carpetas
            if es_carpeta:
                for col in range(table.columnCount()):
                    item = table.item(i, col)
                    if item:
                        item.setForeground(QColor(theme.ACCENT_PRIMARY))


        table.setSortingEnabled(True)
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self._update_buttons()

    # ------------------------------------------------------------------
    # Menú contextual (modo presupuestos)
    # ------------------------------------------------------------------

    def _on_context_menu(self, pos, state_name):
        table = self._tab_tables.get(state_name)
        if table is None:
            return

        item = table.itemAt(pos)
        if item is None:
            return

        row = item.row()
        table.selectRow(row)

        selected_many = self._get_selected_many()
        if not selected_many:
            return

        menu = QMenu(self)

        # Sub-menú "Mover a..."
        move_menu = menu.addMenu("Mover a...")
        for target_state in _STATE_FOLDERS:
            # Buscar la carpeta real (case-insensitive)
            real_name = self._find_real_folder_name(target_state)
            if real_name and real_name.upper() != state_name.upper():
                act = move_menu.addAction(target_state)
                act.triggered.connect(
                    lambda checked=False, tgt=real_name, projs=selected_many: self._move_project(
                        projs, state_name, tgt
                    )
                )

        if move_menu.isEmpty():
            move_menu.setEnabled(False)

        menu.addSeparator()

        # Abrir carpeta
        act_folder = menu.addAction("Abrir carpeta")
        act_folder.triggered.connect(self._on_open_folder)

        # Abrir excel
        has_excel = any(
            bool(s.get("ruta_excel")) and os.path.exists(s.get("ruta_excel", ""))
            for s in selected_many
        )
        act_excel = menu.addAction("Abrir Excel")
        act_excel.setEnabled(has_excel)
        act_excel.triggered.connect(self._on_open_excel)

        menu.exec(table.viewport().mapToGlobal(pos))

    def _find_real_folder_name(self, target_upper: str) -> str:
        """Busca el nombre real de la carpeta en disco (respetando mayúsculas reales)."""
        if not self._root_path:
            return ""
        try:
            for entry in os.listdir(self._root_path):
                if entry.upper() == target_upper.upper():
                    full = os.path.join(self._root_path, entry)
                    if os.path.isdir(full):
                        return entry
        except OSError:
            pass
        return ""

    def _move_project(self, projects: list[dict], from_state: str, to_state: str):
        """Mueve una selección de proyectos de un estado a otro."""
        if not projects:
            return

        valid_moves = []
        for project in projects:
            src_folder = project.get("ruta_carpeta", "")
            if not src_folder or not os.path.isdir(src_folder):
                continue
            folder_name = os.path.basename(src_folder)
            dest_folder = os.path.join(self._root_path, to_state, folder_name)
            if os.path.exists(dest_folder):
                continue
            valid_moves.append((src_folder, dest_folder, folder_name))

        if not valid_moves:
            QMessageBox.warning(
                self, "Error",
                "No hay proyectos válidos para mover en la selección."
            )
            return

        confirm = QMessageBox.question(
            self, "Mover proyectos",
            f"¿Mover {len(valid_moves)} proyecto(s) de\n  {from_state}\na\n  {to_state}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        moved = 0
        failed = 0
        for src_folder, dest_folder, _folder_name in valid_moves:
            try:
                shutil.move(src_folder, dest_folder)
                moved += 1
            except Exception:
                failed += 1

        QMessageBox.information(
            self, "Mover proyectos",
            f"Movidos: {moved}\nCon error: {failed}"
        )
        self._load_data()

    # ------------------------------------------------------------------
    # Menú contextual (modo explorador)
    # ------------------------------------------------------------------

    def _on_explorer_context_menu(self, pos, state_name):
        table = self._tab_tables.get(state_name)
        if table is None:
            return

        item = table.itemAt(pos)
        if item is None:
            return

        row = item.row()
        table.selectRow(row)

        entry = self._get_row_data(state_name, row)
        if entry is None:
            return

        ruta = entry.get("ruta", "")

        menu = QMenu(self)
        act_open = menu.addAction("Abrir")
        act_open.triggered.connect(lambda: self._open_file(ruta) if ruta else None)

        if not entry.get("es_carpeta"):
            act_folder = menu.addAction("Abrir carpeta contenedora")
            act_folder.triggered.connect(
                lambda: self._open_file(os.path.dirname(ruta)) if ruta else None
            )

        menu.exec(table.viewport().mapToGlobal(pos))

    def _on_explorer_dblclick(self):
        """Doble clic en modo explorador: abrir el archivo o carpeta."""
        state = self._current_state()
        if state is None:
            return
        table = self._tab_tables.get(state)
        if table is None:
            return
        row = table.currentRow()
        if row < 0:
            return

        entry = self._get_row_data(state, row)
        if entry is None:
            return

        ruta = entry.get("ruta", "")
        if ruta and os.path.exists(ruta):
            self._open_file(ruta)

    # ------------------------------------------------------------------
    # Selección y helpers
    # ------------------------------------------------------------------

    def _current_state(self):
        page = self._notebook.currentIndex()
        if page < 0 or page >= len(self._state_names):
            return None
        return self._state_names[page]

    def _get_row_data(self, state_name: str, row: int):
        """Devuelve el dict de datos original para una fila visual de la tabla."""
        table = self._tab_tables.get(state_name)
        if table is None:
            return None
        first_item = table.item(row, 0)
        if first_item is None:
            return None
        data_idx = first_item.data(_DATA_REF_ROLE)

        rows = self._tab_data.get(state_name, [])
        search_ctrl = self._tab_searches.get(state_name)
        query = search_ctrl.text() if search_ctrl else ""

        if self._explorer_mode:
            filtered = self._filter_explorer_rows(rows, query)
        else:
            filtered = self._filter_rows(rows, query)

        if data_idx is None or data_idx >= len(filtered):
            return None
        return filtered[data_idx]

    def _get_selected(self):
        selected_many = self._get_selected_many()
        return selected_many[0] if selected_many else None

    def _get_selected_many(self):
        state = self._current_state()
        if state is None:
            return []
        table = self._tab_tables.get(state)
        if table is None:
            return []

        selected_rows = sorted({idx.row() for idx in table.selectionModel().selectedRows()})
        if not selected_rows:
            row = table.currentRow()
            if row >= 0:
                selected_rows = [row]

        entries = []
        for row in selected_rows:
            entry = self._get_row_data(state, row)
            if entry is None:
                continue
            if self._explorer_mode:
                entries.append({
                    "nombre_proyecto": entry.get("nombre", ""),
                    "ruta_excel": entry.get("ruta", "") if not entry.get("es_carpeta") else "",
                    "ruta_carpeta": entry.get("ruta", "") if entry.get("es_carpeta") else os.path.dirname(entry.get("ruta", "")),
                    "numero": "",
                })
            else:
                entries.append(entry)
        return entries

    def _on_tab_changed(self, _index):
        self._update_buttons()

    def _update_buttons(self):
        selected_many = self._get_selected_many()
        selected = selected_many[0] if selected_many else None
        has_sel = len(selected_many) > 0
        file_ok = has_sel and selected is not None and os.path.exists(selected.get("ruta_excel", ""))
        for btn in (self._btn_preview, self._btn_edit, self._btn_complete, self._btn_pdf,
                    self._btn_open, self._btn_folder):
            btn.setEnabled(has_sel)
        self._btn_refresh_selected.setEnabled(has_sel and not self._explorer_mode)
        if has_sel and not file_ok:
            self._btn_preview.setEnabled(False)
            self._btn_edit.setEnabled(False)
            self._btn_complete.setEnabled(False)
            self._btn_pdf.setEnabled(False)
            self._btn_open.setEnabled(False)
        # "Completar datos" solo en modo Excel y con datos incompletos
        if has_sel and file_ok and not self._explorer_mode:
            self._btn_complete.setEnabled(not bool(selected.get("datos_completos", True)))
        else:
            self._btn_complete.setEnabled(False)

    def _on_item_dblclick(self):
        self._on_preview()

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _on_preview(self):
        selected_many = self._get_selected_many()
        if not selected_many:
            return

        rutas = []
        for sel in selected_many:
            ruta = os.path.normpath(sel.get("ruta_excel", ""))
            if ruta and os.path.exists(ruta):
                rutas.append(ruta)
        if not rutas:
            QMessageBox.warning(self, "Error", "No hay archivos Excel válidos en la selección.")
            return
        from src.gui.budget_preview_dialog import BudgetPreviewDialog
        for ruta in rutas[:5]:
            dlg = BudgetPreviewDialog(self, ruta)
            dlg.show()
        if len(rutas) > 5:
            QMessageBox.information(
                self, "Previsualización",
                f"Se abrieron 5 previsualizaciones de {len(rutas)} seleccionados.",
            )

    def _on_edit_menu(self):
        selected_many = self._get_selected_many()
        if not selected_many:
            return
        selected = selected_many[0]
        ruta = os.path.normpath(selected.get("ruta_excel", ""))
        if not os.path.exists(ruta):
            QMessageBox.warning(self, "Error", f"El archivo ya no existe:\n{ruta}")
            return

        menu = QMenu(self)
        act_regen = menu.addAction("Regenerar todas las partidas (IA)")
        act_add = menu.addAction("A\u00f1adir m\u00e1s partidas (IA)")
        menu.addSeparator()
        if len(selected_many) > 1:
            act_header = menu.addAction(
                f"Regenerar campos en seleccionados ({len(selected_many)})"
            )
        else:
            act_header = menu.addAction("Regenerar campos del presupuesto")

        act_regen.triggered.connect(lambda: self._edit_regen_all(ruta))
        act_add.triggered.connect(lambda: self._edit_add_partidas(ruta))
        if len(selected_many) > 1:
            act_header.triggered.connect(lambda: self._edit_regen_header_selected(selected_many))
        else:
            numero = selected.get("numero", "")
            act_header.triggered.connect(lambda: self._edit_regen_header(ruta, numero))

        menu.exec(self._btn_edit.mapToGlobal(self._btn_edit.rect().bottomLeft()))

    def _on_complete_data(self):
        selected_many = self._get_selected_many()
        if not selected_many:
            return
        selected = selected_many[0]
        ruta = os.path.normpath(selected.get("ruta_excel", ""))
        if not os.path.exists(ruta):
            QMessageBox.warning(self, "Error", f"El archivo ya no existe:\n{ruta}")
            return
        if bool(selected.get("datos_completos", True)):
            QMessageBox.information(
                self,
                "Información",
                "Este presupuesto ya figura como completo.",
            )
            return
        numero = selected.get("numero", "")
        self._edit_regen_header(ruta, numero)

    def _on_refresh_selected(self):
        selected_many = self._get_selected_many()
        if not selected_many:
            return
        if self._explorer_mode:
            QMessageBox.information(
                self, "Actualizar seleccionados",
                "Esta acción está disponible en la vista de presupuestos.",
            )
            return
        from src.core.services import BudgetService
        svc = BudgetService()
        ok_count = 0
        fail_count = 0
        for selected in selected_many:
            ruta = os.path.normpath(selected.get("ruta_excel", ""))
            if not ruta or not os.path.exists(ruta):
                fail_count += 1
                continue
            refreshed = svc.refresh_budget_cache_entry(
                ruta,
                estado=self._current_state() or "",
                expected_numero=selected.get("numero", ""),
            )
            if refreshed:
                ok_count += 1
            else:
                fail_count += 1
        self._load_data()
        QMessageBox.information(
            self,
            "Actualizar seleccionados",
            f"Actualizados: {ok_count}\nCon error: {fail_count}",
        )

    def _on_export_pdf(self):
        selected = self._get_selected()
        if not selected:
            return
        ruta = os.path.normpath(selected.get("ruta_excel", ""))
        if not os.path.exists(ruta):
            QMessageBox.warning(self, "Error", f"El archivo ya no existe:\n{ruta}")
            return
        from src.core.pdf_exporter import PDFExporter
        exporter = PDFExporter()
        if not exporter.is_available():
            QMessageBox.warning(
                self, "Exportar PDF",
                "Microsoft Excel no est\u00e1 disponible.\n"
                "Para exportar a PDF se necesita Excel instalado.",
            )
            return

        self._btn_pdf.setEnabled(False)
        self._btn_pdf.setText("Exportando\u2026")

        def _on_pdf_done(ok_outer, payload):
            self._btn_pdf.setEnabled(True)
            self._btn_pdf.setText("Exportar PDF")
            if not ok_outer:
                QMessageBox.critical(self, "Error", f"Error al exportar PDF:\n{payload}")
                return
            ok, result = payload
            if ok:
                resp = QMessageBox.question(
                    self, "PDF exportado",
                    f"PDF generado:\n{result}\n\n\u00bfDesea abrirlo?",
                )
                if resp == QMessageBox.StandardButton.Yes:
                    self._open_file(result)
            else:
                QMessageBox.critical(self, "Error", f"Error al exportar PDF:\n{result}")

        run_in_background(lambda: exporter.export(ruta), _on_pdf_done)

    def _on_open_excel(self):
        selected_many = self._get_selected_many()
        if not selected_many:
            return
        from src.core.services import BudgetService

        svc = BudgetService()
        refreshed_any = False
        for selected in selected_many:
            ruta = os.path.normpath(selected.get("ruta_excel", ""))
            if not os.path.exists(ruta):
                continue
            # Refresco inmediato al abrir para no depender del mtime de cierre.
            if svc.refresh_budget_cache_entry(
                ruta,
                estado=self._current_state() or "",
                expected_numero=selected.get("numero", ""),
            ):
                refreshed_any = True

            numero = selected.get("numero", "")
            data = svc.read_budget(ruta, expected_numero=numero)
            if not data:
                resp = QMessageBox.question(
                    self,
                    "Lectura incompleta del Excel",
                    "No se pudieron leer bien los datos del presupuesto.\n\n"
                    "¿Deseas abrirlo igualmente y completarlo manualmente después?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if resp != QMessageBox.StandardButton.Yes:
                    continue
            opened = self._open_file(ruta)
            if opened:
                self._watch_excel_changes_and_refresh(
                    ruta_excel=ruta,
                    estado=self._current_state() or "",
                )
        if refreshed_any:
            self._load_data()

    def _watch_excel_changes_and_refresh(self, ruta_excel: str, estado: str):
        """Vigila cambios de mtime tras abrir Excel y refresca ese presupuesto."""
        try:
            baseline = os.path.getmtime(ruta_excel)
        except OSError:
            baseline = None

        def _watch():
            if baseline is None:
                return {"changed": False}
            # Ventana de observación ~6 minutos
            for _ in range(180):
                time.sleep(2)
                try:
                    mtime_now = os.path.getmtime(ruta_excel)
                except OSError:
                    continue
                if mtime_now != baseline:
                    return {"changed": True}
            return {"changed": False}

        def _on_watch_done(ok, payload):
            if not ok or not payload.get("changed"):
                return

            from src.core.services import BudgetService
            svc = BudgetService()
            if svc.finalize_budget(ruta_excel, estado=estado):
                self._load_data()

        run_in_background(_watch, _on_watch_done)

    def _on_open_folder(self):
        selected_many = self._get_selected_many()
        if not selected_many:
            return
        opened = 0
        seen = set()
        for selected in selected_many:
            folder = selected.get("ruta_carpeta", "")
            if not folder or not os.path.isdir(folder):
                ruta = selected.get("ruta_excel", "")
                folder = os.path.dirname(ruta) if ruta else ""
            if folder and os.path.isdir(folder) and folder not in seen:
                seen.add(folder)
                if self._open_file(folder):
                    opened += 1
        if opened == 0:
            QMessageBox.warning(self, "Error", "No se encontr\u00f3 ninguna carpeta válida.")

    # ------------------------------------------------------------------
    # Edición
    # ------------------------------------------------------------------

    def _edit_regen_all(self, ruta):
        confirm = QMessageBox.warning(
            self, "Regenerar partidas",
            "Esta acción reemplazará TODAS las partidas actuales del presupuesto "
            "por las que genere la IA.\n\n¿Desea continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        from src.gui.ai_budget_dialog import AIBudgetDialog
        from src.gui.partidas_dialog import SuggestedPartidasDialog
        from src.core.services import BudgetService

        ai_dlg = AIBudgetDialog(self)
        if ai_dlg.exec() != 1:
            return
        result = ai_dlg.get_result()
        if not result or not result.get("partidas"):
            QMessageBox.information(self, "Aviso", "No se generaron partidas.")
            return

        partidas_dlg = SuggestedPartidasDialog(self, result)
        if partidas_dlg.exec() != 1:
            return
        selected_partidas = partidas_dlg.get_selected_partidas()
        if not selected_partidas:
            return

        svc = BudgetService()
        if svc.insert_partidas(ruta, selected_partidas):
            svc.finalize_budget(ruta, estado=self._current_state() or "")
            QMessageBox.information(
                self, "\u00c9xito", f"Partidas regeneradas ({len(selected_partidas)})."
            )
            self._load_data()
        else:
            QMessageBox.critical(self, "Error", "Error al insertar partidas.")

    def _edit_add_partidas(self, ruta):
        from src.gui.ai_budget_dialog import AIBudgetDialog
        from src.gui.partidas_dialog import SuggestedPartidasDialog
        from src.core.services import BudgetService

        svc = BudgetService()
        existing = svc.read_budget(ruta)
        existing_partidas = existing["partidas"] if existing else []

        context = ""
        if existing_partidas:
            conceptos = [p["concepto"] for p in existing_partidas]
            context = (
                f"Ya existen {len(existing_partidas)} partidas: "
                + ", ".join(conceptos[:10])
                + (". " if len(conceptos) <= 10 else "... ")
                + "Genera partidas ADICIONALES que complementen las existentes."
            )

        ai_dlg = AIBudgetDialog(self, context_extra=context)
        if ai_dlg.exec() != 1:
            return
        result = ai_dlg.get_result()
        if not result or not result.get("partidas"):
            QMessageBox.information(self, "Aviso", "No se generaron partidas.")
            return

        partidas_dlg = SuggestedPartidasDialog(self, result)
        if partidas_dlg.exec() != 1:
            return
        selected_partidas = partidas_dlg.get_selected_partidas()
        if not selected_partidas:
            return

        if svc.append_partidas(ruta, selected_partidas):
            svc.finalize_budget(ruta, estado=self._current_state() or "")
            QMessageBox.information(
                self, "\u00c9xito",
                f"{len(selected_partidas)} partidas a\u00f1adidas."
            )
            self._load_data()
        else:
            QMessageBox.critical(self, "Error", "Error al a\u00f1adir partidas.")

    def _edit_regen_header_selected(self, selected_many: list[dict]):
        if not selected_many:
            return
        confirm = QMessageBox.warning(
            self, "Regenerar campos",
            f"Se regenerarán campos en {len(selected_many)} presupuesto(s).\n\n"
            "¿Desea continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        for sel in selected_many:
            ruta = os.path.normpath(sel.get("ruta_excel", ""))
            if not os.path.exists(ruta):
                continue
            self._edit_regen_header(
                ruta,
                numero_proyecto=sel.get("numero", ""),
                ask_confirmation=False,
            )

    def _edit_regen_header(self, ruta, numero_proyecto="", ask_confirmation=True):
        if ask_confirmation:
            confirm = QMessageBox.warning(
                self, "Regenerar campos",
                "Esta acción sobrescribirá los campos de cabecera del presupuesto "
                "(cliente, dirección, fecha, etc.).\n\n¿Desea continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        from src.core.services import BudgetService, DatabaseService

        project_data, project_name = self._obtain_project_data(
            preselect_numero=numero_proyecto
        )
        if not project_data:
            return

        comunidad_data = None
        if hasattr(self._parent, "_buscar_comunidad_para_presupuesto"):
            partes_dir = [
                p for p in [
                    project_data.get("calle", ""),
                    project_data.get("num_calle", ""),
                    project_data.get("codigo_postal", ""),
                    project_data.get("localidad", ""),
                ] if p
            ]
            direccion_proyecto = ", ".join(partes_dir)
            comunidad_data = self._parent._buscar_comunidad_para_presupuesto(
                project_data.get("cliente", ""), direccion=direccion_proyecto,
            )

        db_svc = DatabaseService()
        admin_data = db_svc.get_admin_para_comunidad(comunidad_data)

        excel_data = {
            "nombre_obra": project_name or "",
            "numero_proyecto": project_data.get("numero", ""),
            "fecha": project_data.get("fecha", ""),
            "cliente": project_data.get("cliente", ""),
            "calle": project_data.get("calle", ""),
            "num_calle": project_data.get("num_calle", ""),
            "codigo_postal": project_data.get("codigo_postal", ""),
            "tipo": project_data.get("tipo", ""),
            "admin_cif": comunidad_data.get("cif", "") if comunidad_data else "",
            "admin_email": admin_data.get("email", "") if admin_data else "",
            "admin_telefono": admin_data.get("telefono", "") if admin_data else "",
        }

        svc = BudgetService()
        if svc.update_header_fields(ruta, excel_data):
            svc.finalize_budget(
                ruta,
                project_data=project_data,
                comunidad_data=comunidad_data,
                admin_data=admin_data,
                estado=self._current_state() or "",
            )
            QMessageBox.information(self, "\u00c9xito", "Campos actualizados.")
            self._load_data()
        else:
            QMessageBox.critical(self, "Error", "Error al actualizar campos.")

    def _obtain_project_data(self, preselect_numero=""):
        from src.gui.dialogs import obtain_project_data
        return obtain_project_data(self, preselect_numero=preselect_numero)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _open_file(path) -> bool:
        path = os.path.normpath(path)
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", path], check=True)
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.run(["xdg-open", path], check=True)
            return True
        except Exception as exc:
            QMessageBox.critical(
                None, "Error al abrir",
                f"No se pudo abrir:\n{path}\n\nError: {exc}",
            )
            return False
