"""
Dashboard de presupuestos existentes (PySide6).

Muestra los presupuestos organizados por carpetas de estado (pestañas
dinámicas) a partir de la ruta configurada en PATH_OPEN_BUDGETS.
"""

import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
)

from src.core import folder_scanner
from src.core.project_data_resolver import build_relation_index, resolve_projects
from src.core.settings import Settings
from src.gui import theme
from src.utils.helpers import run_in_background

_COLUMNS = [
    ("Proyecto", 220),
    ("Cliente", 160),
    ("Localidad", 120),
    ("Tipo obra", 120),
    ("Fecha", 90),
    ("Total", 100),
]

_SEARCH_KEYS = ("nombre_proyecto", "cliente", "localidad", "tipo_obra", "numero")


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

        btn_refresh = QPushButton("\u27F3 Actualizar", header)
        btn_refresh.setFont(theme.font_base())
        btn_refresh.setFixedHeight(36)
        btn_refresh.setToolTip("Recargar presupuestos desde las carpetas")
        btn_refresh.clicked.connect(self._load_data)
        top_row.addWidget(btn_refresh)

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
        self._btn_pdf = self._tb_button(toolbar, "Exportar PDF", self._on_export_pdf)
        self._btn_open = self._tb_button(toolbar, "Abrir Excel", self._on_open_excel, primary=True)
        self._btn_folder = self._tb_button(toolbar, "Abrir carpeta", self._on_open_folder)

        for btn in (self._btn_preview, self._btn_edit, self._btn_pdf,
                    self._btn_open, self._btn_folder):
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
            self._rebuild_tabs(states, root_path)

        run_in_background(_scan, _on_done)

    def _set_toolbar_enabled(self, enabled):
        for btn in (self._btn_preview, self._btn_edit, self._btn_pdf,
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
            scanned = folder_scanner.scan_projects(state_dir)
            resolved = resolve_projects(scanned, self._relation_index)
            self._tab_data[state_name] = resolved

            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            tab_layout.setContentsMargins(theme.SPACE_MD, theme.SPACE_MD, theme.SPACE_MD, theme.SPACE_SM)

            search_widget, search_ctrl = self._create_search_box(tab_widget, state_name)
            tab_layout.addWidget(search_widget)
            self._tab_searches[state_name] = search_ctrl

            table = QTableWidget(tab_widget)
            table.setColumnCount(len(_COLUMNS))
            table.setHorizontalHeaderLabels([c[0] for c in _COLUMNS])
            for i, (_, w) in enumerate(_COLUMNS):
                table.setColumnWidth(i, w)
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            table.doubleClicked.connect(self._on_item_dblclick)
            table.itemSelectionChanged.connect(self._update_buttons)
            tab_layout.addWidget(table, 1)

            self._tab_tables[state_name] = table
            self._notebook.addTab(tab_widget, f"  {state_name}  ")

        self._notebook.blockSignals(False)

        for state_name in states:
            self._populate_table(state_name)
        self._update_buttons()

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
        search.setPlaceholderText("Proyecto, cliente, localidad...")
        search.setMinimumHeight(32)
        search.textChanged.connect(lambda: self._on_search(state_name))
        sz.addWidget(search, 1)

        return search_widget, search

    def _on_search(self, state_name):
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

    # ------------------------------------------------------------------
    # Poblar tabla
    # ------------------------------------------------------------------

    def _populate_table(self, state_name):
        table = self._tab_tables.get(state_name)
        if table is None:
            return
        rows = self._tab_data.get(state_name, [])
        search_ctrl = self._tab_searches.get(state_name)
        query = search_ctrl.text() if search_ctrl else ""
        filtered = self._filter_rows(rows, query)

        table.setRowCount(len(filtered))
        for i, proj in enumerate(filtered):
            has_excel = bool(proj.get("ruta_excel")) and os.path.exists(proj.get("ruta_excel", ""))
            nombre = proj.get("nombre_proyecto", "")
            if not has_excel:
                nombre = f"\u26A0 {nombre}"

            table.setItem(i, 0, QTableWidgetItem(nombre))
            table.setItem(i, 1, QTableWidgetItem(proj.get("cliente", "")))
            table.setItem(i, 2, QTableWidgetItem(proj.get("localidad", "")))
            table.setItem(i, 3, QTableWidgetItem(proj.get("tipo_obra", "")))

            fecha_raw = proj.get("fecha", "")
            table.setItem(i, 4, QTableWidgetItem(fecha_raw))

            total = proj.get("total")
            total_text = ""
            if total is not None:
                try:
                    t = f"{float(total):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    total_text = f"{t} \u20AC"
                except (ValueError, TypeError):
                    pass
            total_item = QTableWidgetItem(total_text)
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            total_item.setFont(theme.get_font_bold(9))
            table.setItem(i, 5, total_item)

            if not has_excel:
                for col in range(table.columnCount()):
                    item = table.item(i, col)
                    if item:
                        item.setForeground(QColor(theme.TEXT_TERTIARY))

        self._update_buttons()

    # ------------------------------------------------------------------
    # Selección y helpers
    # ------------------------------------------------------------------

    def _current_state(self):
        page = self._notebook.currentIndex()
        if page < 0 or page >= len(self._state_names):
            return None
        return self._state_names[page]

    def _get_selected(self):
        state = self._current_state()
        if state is None:
            return None
        table = self._tab_tables.get(state)
        if table is None:
            return None
        row = table.currentRow()
        if row < 0:
            return None

        search_ctrl = self._tab_searches.get(state)
        query = search_ctrl.text() if search_ctrl else ""
        visible = self._filter_rows(self._tab_data.get(state, []), query)
        if row >= len(visible):
            return None
        return visible[row]

    def _on_tab_changed(self, _index):
        self._update_buttons()

    def _update_buttons(self):
        selected = self._get_selected()
        has_sel = selected is not None
        file_ok = has_sel and os.path.exists(selected.get("ruta_excel", ""))
        for btn in (self._btn_preview, self._btn_edit, self._btn_pdf,
                    self._btn_open, self._btn_folder):
            btn.setEnabled(has_sel)
        if has_sel and not file_ok:
            self._btn_preview.setEnabled(False)
            self._btn_edit.setEnabled(False)
            self._btn_pdf.setEnabled(False)
            self._btn_open.setEnabled(False)

    def _on_item_dblclick(self):
        self._on_preview()

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _on_preview(self):
        selected = self._get_selected()
        if not selected:
            return
        ruta = os.path.normpath(selected.get("ruta_excel", ""))
        if not os.path.exists(ruta):
            QMessageBox.warning(self, "Error", f"El archivo ya no existe:\n{ruta}")
            return
        from src.gui.budget_preview_dialog_wx import BudgetPreviewDialog
        dlg = BudgetPreviewDialog(self, ruta)
        dlg.show()

    def _on_edit_menu(self):
        selected = self._get_selected()
        if not selected:
            return
        ruta = os.path.normpath(selected.get("ruta_excel", ""))
        if not os.path.exists(ruta):
            QMessageBox.warning(self, "Error", f"El archivo ya no existe:\n{ruta}")
            return

        menu = QMenu(self)
        act_regen = menu.addAction("Regenerar todas las partidas (IA)")
        act_add = menu.addAction("A\u00f1adir m\u00e1s partidas (IA)")
        menu.addSeparator()
        act_header = menu.addAction("Regenerar campos del presupuesto")

        act_regen.triggered.connect(lambda: self._edit_regen_all(ruta))
        act_add.triggered.connect(lambda: self._edit_add_partidas(ruta))
        numero = selected.get("numero", "")
        act_header.triggered.connect(lambda: self._edit_regen_header(ruta, numero))

        menu.exec(self._btn_edit.mapToGlobal(self._btn_edit.rect().bottomLeft()))

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
        selected = self._get_selected()
        if not selected:
            return
        ruta = os.path.normpath(selected.get("ruta_excel", ""))
        if not os.path.exists(ruta):
            QMessageBox.warning(self, "Error", f"El archivo ya no existe:\n{ruta}")
            return
        self._open_file(ruta)

    def _on_open_folder(self):
        selected = self._get_selected()
        if not selected:
            return
        folder = selected.get("ruta_carpeta", "")
        if not folder or not os.path.isdir(folder):
            ruta = selected.get("ruta_excel", "")
            folder = os.path.dirname(ruta) if ruta else ""
        if folder and os.path.isdir(folder):
            self._open_file(folder)
        else:
            QMessageBox.warning(self, "Error", "No se encontr\u00f3 la carpeta.")

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

        from src.gui.ai_budget_dialog_wx import AIBudgetDialog
        from src.gui.partidas_dialog_wx import SuggestedPartidasDialog
        from src.core.excel_manager import ExcelManager

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

        em = ExcelManager()
        if em.insert_partidas_via_xml(ruta, selected_partidas):
            QMessageBox.information(self, "\u00c9xito", f"Partidas regeneradas ({len(selected_partidas)}).")
            self._load_data()
        else:
            QMessageBox.critical(self, "Error", "Error al insertar partidas.")

    def _edit_add_partidas(self, ruta):
        from src.core.budget_reader import BudgetReader
        from src.gui.ai_budget_dialog_wx import AIBudgetDialog
        from src.gui.partidas_dialog_wx import SuggestedPartidasDialog
        from src.core.excel_manager import ExcelManager

        reader = BudgetReader()
        existing = reader.read(ruta)
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

        em = ExcelManager()
        if em.append_partidas_via_xml(ruta, selected_partidas):
            QMessageBox.information(self, "\u00c9xito", f"{len(selected_partidas)} partidas a\u00f1adidas.")
            self._load_data()
        else:
            QMessageBox.critical(self, "Error", "Error al a\u00f1adir partidas.")

    def _edit_regen_header(self, ruta, numero_proyecto=""):
        confirm = QMessageBox.warning(
            self, "Regenerar campos",
            "Esta acción sobrescribirá los campos de cabecera del presupuesto "
            "(cliente, dirección, fecha, etc.).\n\n¿Desea continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        from src.core.excel_manager import ExcelManager

        project_data, project_name = self._obtain_project_data(preselect_numero=numero_proyecto)
        if not project_data:
            return

        comunidad_data = None
        if hasattr(self._parent, "_buscar_comunidad_para_presupuesto"):
            comunidad_data = self._parent._buscar_comunidad_para_presupuesto(
                project_data.get("cliente", "")
            )

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
            "admin_email": comunidad_data.get("email", "") if comunidad_data else "",
            "admin_telefono": comunidad_data.get("telefono", "") if comunidad_data else "",
        }

        em = ExcelManager()
        if em.update_header_fields(ruta, excel_data):
            QMessageBox.information(self, "\u00c9xito", "Campos actualizados.")
            self._load_data()
        else:
            QMessageBox.critical(self, "Error", "Error al actualizar campos.")

    def _obtain_project_data(self, preselect_numero=""):
        from src.gui.dialogs_wx import obtain_project_data
        return obtain_project_data(self, preselect_numero=preselect_numero)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _open_file(path):
        path = os.path.normpath(path)
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", path], check=True)
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.run(["xdg-open", path], check=True)
        except Exception as exc:
            QMessageBox.critical(
                None, "Error al abrir",
                f"No se pudo abrir:\n{path}\n\nError: {exc}",
            )
