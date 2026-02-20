"""
Diálogos PySide6 para cubiApp.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from src.core.project_parser import ProjectParser
from src.core import db_repository
from src.utils.project_name_generator import ProjectNameGenerator
from src.gui import theme


# ---------------------------------------------------------------------------
# Diálogos de confirmación / selección de comunidad (flujo presupuesto)
# ---------------------------------------------------------------------------

def crear_comunidad_con_formulario(parent, nombre_prefill: str = "") -> dict | None:
    from src.gui.db_manager_wx import ComunidadFormDialog

    initial = {"nombre": nombre_prefill} if nombre_prefill else {}
    dlg = ComunidadFormDialog(parent, "Nueva Comunidad", initial=initial)
    result = None
    if dlg.exec() == 1:
        vals = dlg.get_values()
        nombre = vals.get("nombre", "").strip()
        admin_id = vals.get("administracion_id")
        new_id, err = db_repository.create_comunidad(
            nombre, admin_id,
            cif=vals.get("cif", ""),
            direccion=vals.get("direccion", ""),
            email=vals.get("email", ""),
            telefono=vals.get("telefono", ""),
        )
        if err:
            QMessageBox.critical(parent, "Error", f"Error al crear la comunidad:\n{err}")
        else:
            ct_ids = vals.get("contacto_ids", [])
            if ct_ids:
                db_repository.set_contactos_para_comunidad(new_id, ct_ids)
            result = {
                "id": new_id, "nombre": nombre,
                "cif": vals.get("cif", ""),
                "direccion": vals.get("direccion", ""),
                "email": vals.get("email", ""),
                "telefono": vals.get("telefono", ""),
                "administracion_id": admin_id,
            }
    return result


class ComunidadConfirmDialog(QDialog):
    """Diálogo que muestra los datos de una comunidad encontrada y pide confirmación."""

    def __init__(self, parent, comunidad_data: dict, nombre_buscado: str):
        super().__init__(parent)
        self.setWindowTitle("Comunidad encontrada")
        self._comunidad = comunidad_data
        self._nombre_buscado = nombre_buscado
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        title = theme.create_title(self, "Comunidad encontrada", "xl")
        layout.addWidget(title)

        msg = theme.create_text(
            self,
            f'Se ha encontrado una comunidad con el nombre "{self._nombre_buscado}".\n'
            "¿Desea rellenar automáticamente los datos del presupuesto con esta información?",
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)
        layout.addSpacing(theme.SPACE_MD)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)

        campos = [
            ("Nombre:", self._comunidad.get("nombre", "")),
            ("CIF:", self._comunidad.get("cif", "") or "(vacío)"),
            ("Correo:", self._comunidad.get("email", "") or "(vacío)"),
            ("Teléfono:", self._comunidad.get("telefono", "") or "(vacío)"),
            ("Dirección:", self._comunidad.get("direccion", "") or "(vacío)"),
        ]
        for row, (label_text, value_text) in enumerate(campos):
            lbl = QLabel(label_text, self)
            lbl.setFont(theme.get_font_medium())
            lbl.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(lbl, row, 0)

            val = QLabel(value_text, self)
            val.setFont(theme.font_base())
            val.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
            grid.addWidget(val, row, 1)

        layout.addLayout(grid)
        layout.addWidget(theme.create_divider(self))

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_no = QPushButton("No, continuar sin datos", self)
        btn_no.setFont(theme.font_base())
        btn_no.setFixedHeight(32)
        btn_no.clicked.connect(self.reject)
        btn_layout.addWidget(btn_no)
        btn_layout.addSpacing(8)

        btn_yes = QPushButton("Sí, rellenar datos", self)
        btn_yes.setFont(theme.get_font_medium())
        btn_yes.setFixedHeight(32)
        btn_yes.setProperty("class", "primary")
        btn_yes.setDefault(True)
        btn_yes.clicked.connect(self.accept)
        btn_layout.addWidget(btn_yes)

        layout.addLayout(btn_layout)
        theme.fit_dialog(self, 520, 400)

    def get_comunidad_data(self) -> dict:
        return self._comunidad


class ComunidadFuzzySelectDialog(QDialog):
    """Diálogo que muestra coincidencias fuzzy y permite al usuario elegir una comunidad."""

    def __init__(self, parent, resultados: list, nombre_buscado: str):
        super().__init__(parent)
        self.setWindowTitle("Coincidencias aproximadas")
        self._resultados = resultados
        self._nombre_buscado = nombre_buscado
        self._selected_comunidad = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        title = theme.create_title(self, "Coincidencias aproximadas", "xl")
        layout.addWidget(title)

        msg = theme.create_text(
            self,
            f'No se encontró una comunidad exacta con "{self._nombre_buscado}", '
            "pero se encontraron las siguientes coincidencias.\n"
            "Seleccione una para rellenar los datos del presupuesto:",
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)
        layout.addSpacing(theme.SPACE_SM)

        self._table = QTableWidget(self)
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Nombre", "CIF", "Correo", "Similitud"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(1, 100)
        self._table.setColumnWidth(2, 160)
        self._table.setColumnWidth(3, 80)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)

        self._table.setRowCount(len(self._resultados))
        for idx, com in enumerate(self._resultados):
            self._table.setItem(idx, 0, QTableWidgetItem(com.get("nombre", "")))
            self._table.setItem(idx, 1, QTableWidgetItem(com.get("cif", "") or ""))
            self._table.setItem(idx, 2, QTableWidgetItem(com.get("email", "") or ""))
            similitud_pct = f"{com.get('similitud', 0) * 100:.0f}%"
            self._table.setItem(idx, 3, QTableWidgetItem(similitud_pct))
        if self._resultados:
            self._table.selectRow(0)

        layout.addWidget(self._table, 1)
        layout.addWidget(theme.create_divider(self))

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_skip = QPushButton("Continuar sin datos", self)
        btn_skip.setFont(theme.font_base())
        btn_skip.setFixedHeight(32)
        btn_skip.clicked.connect(self.reject)
        btn_layout.addWidget(btn_skip)
        btn_layout.addSpacing(8)

        btn_new = QPushButton("Añadir nueva", self)
        btn_new.setFont(theme.font_base())
        btn_new.setFixedHeight(32)
        btn_new.clicked.connect(self._on_nueva_comunidad)
        btn_layout.addWidget(btn_new)
        btn_layout.addSpacing(8)

        btn_ok = QPushButton("Usar seleccionada", self)
        btn_ok.setFont(theme.get_font_medium())
        btn_ok.setFixedHeight(32)
        btn_ok.setProperty("class", "primary")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_ok)
        btn_layout.addWidget(btn_ok)

        layout.addLayout(btn_layout)
        theme.fit_dialog(self, 720, 480)

    def _on_ok(self):
        row = self._table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Aviso", "Seleccione una comunidad de la lista.")
            return
        self._selected_comunidad = self._resultados[row]
        self.accept()

    def _on_nueva_comunidad(self):
        result = crear_comunidad_con_formulario(self, nombre_prefill=self._nombre_buscado)
        if result:
            self._selected_comunidad = result
            self.accept()

    def get_comunidad_data(self) -> dict:
        return self._selected_comunidad


class ProjectNameDialogWx(QDialog):
    """Diálogo para pegar una línea del Excel y obtener nombre del proyecto."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo Presupuesto")
        self.parser = ProjectParser()
        self.name_generator = ProjectNameGenerator()
        self.project_data = None
        self.project_name = None
        self._build_ui()
        self._load_from_clipboard()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        title = theme.create_title(self, "Crear Presupuesto", "xl")
        layout.addWidget(title)

        inst = theme.create_text(
            self,
            "Copia una fila completa (columnas A-I) desde tu Excel de presupuestos "
            "y pégalo en el campo de abajo, o haz clic en 'Cargar desde Portapapeles'.",
        )
        inst.setWordWrap(True)
        layout.addWidget(inst)

        lbl_datos = QLabel("Datos del proyecto:", self)
        lbl_datos.setFont(theme.get_font_medium())
        lbl_datos.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(lbl_datos)

        self._data_text = QTextEdit(self)
        self._data_text.setPlaceholderText("Pega aquí los datos del Excel (Ctrl+V)")
        self._data_text.setFont(theme.font_base())
        self._data_text.setMaximumHeight(90)
        self._data_text.textChanged.connect(self._validate_data)
        layout.addWidget(self._data_text)

        btn_load = QPushButton("Cargar desde Portapapeles", self)
        btn_load.setFont(theme.font_base())
        btn_load.setFixedHeight(32)
        btn_load.clicked.connect(self._load_from_clipboard)
        layout.addWidget(btn_load)

        lbl_nombre = theme.create_form_label(self, "Nombre del proyecto:")
        layout.addWidget(lbl_nombre)

        self._name_field = QLineEdit(self)
        self._name_field.setReadOnly(True)
        self._name_field.setFont(theme.font_base())
        layout.addWidget(self._name_field)

        layout.addSpacing(8)
        layout.addWidget(theme.create_divider(self))
        layout.addSpacing(8)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("Cancelar", self)
        btn_cancel.setFont(theme.font_base())
        btn_cancel.setFixedSize(100, 32)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addSpacing(8)

        btn_ok = QPushButton("Crear Presupuesto", self)
        btn_ok.setFont(theme.get_font_medium())
        btn_ok.setFixedHeight(32)
        btn_ok.setProperty("class", "primary")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_validate_ok)
        btn_layout.addWidget(btn_ok)

        layout.addLayout(btn_layout)
        theme.fit_dialog(self, 560, 480)

    def _load_from_clipboard(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self._data_text.setPlainText(text)
            self._validate_data()
        else:
            QMessageBox.information(
                self, "Portapapeles vacío",
                "No hay datos en el portapapeles. Copia una fila desde tu Excel.",
            )

    def _validate_data(self):
        text = self._data_text.toPlainText().strip()
        if not text:
            self._name_field.setText("")
            return
        project_data, error = self.parser.parse_clipboard_data(text)
        if error:
            self._name_field.setText(f"Error: {error}")
            return
        self.project_data = project_data
        self.project_name = self.name_generator.generate_project_name(project_data)
        self._name_field.setText(self.project_name)

    def _on_validate_ok(self):
        text = self._data_text.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Datos vacíos", "Por favor, ingresa los datos del proyecto.")
            return
        project_data, error = self.parser.parse_clipboard_data(text)
        if error:
            QMessageBox.information(self, "Error de validación", error)
            return
        self.project_data = project_data
        self.project_name = self.name_generator.generate_project_name(project_data)
        self.accept()

    def get_project_data(self):
        return self.project_data

    def get_project_name(self):
        return self.project_name


# ---------------------------------------------------------------------------
# Función compartida: obtener datos de proyecto (relación Excel → portapapeles)
# ---------------------------------------------------------------------------

def _find_budget_by_numero(budgets: list, numero: str):
    target = numero.strip()
    if not target:
        return None
    for b in budgets:
        if str(b.get("numero", "")).strip() == target:
            return b
    base = target.split("-")[0].strip() if "-" in target else ""
    if base:
        for b in budgets:
            if str(b.get("numero", "")).strip() == base:
                return b
    return None


def _ask_use_matched_budget(parent, budget: dict) -> str:
    """Devuelve 'yes', 'no' o 'cancel'."""
    num = budget.get("numero", "")
    cliente = budget.get("cliente", "")
    calle = budget.get("calle", "")
    localidad = budget.get("localidad", "")
    tipo = budget.get("tipo", "")
    fecha = budget.get("fecha", "")
    importe = budget.get("importe", "")

    lines = [
        f"Nº: {num}", f"Cliente: {cliente}", f"Calle: {calle}",
        f"Localidad: {localidad}", f"Tipo: {tipo}", f"Fecha: {fecha}",
        f"Importe: {importe}",
    ]
    msg = (
        f"Se ha encontrado el presupuesto Nº {num} en la relación:\n\n"
        + "\n".join(lines)
        + "\n\n¿Desea regenerar los campos con estos datos?"
        "\n\n(Sí = usar estos datos · No = elegir otro · Cancelar = salir)"
    )
    resp = QMessageBox.question(
        parent, "Presupuesto encontrado", msg,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
    )
    if resp == QMessageBox.StandardButton.Yes:
        return "yes"
    if resp == QMessageBox.StandardButton.No:
        return "no"
    return "cancel"


def obtain_project_data(parent, preselect_numero: str = "") -> tuple:
    from src.core.settings import Settings

    settings = Settings()
    relation_path = settings.get_default_path(Settings.PATH_RELATION_FILE)

    if relation_path and os.path.isfile(relation_path):
        try:
            from src.core.excel_relation_reader import ExcelRelationReader
            budgets, err = ExcelRelationReader().read(relation_path)
            if not err and budgets:
                if preselect_numero:
                    match = _find_budget_by_numero(budgets, preselect_numero)
                    if match is not None:
                        result = _ask_use_matched_budget(parent, match)
                        if result == "yes":
                            gen = ProjectNameGenerator()
                            data = {k: v for k, v in match.items() if k != "importe"}
                            name = gen.generate_project_name(data)
                            return data, name
                        if result == "cancel":
                            return None, None

                sel_dlg = BudgetSelectorDialog(parent, budgets)
                ret = sel_dlg.exec()
                if ret == 1:
                    data = sel_dlg.get_project_data()
                    name = sel_dlg.get_project_name()
                    return data, name
                use_clipboard = sel_dlg.used_clipboard_fallback()
                if not use_clipboard:
                    return None, None
            elif err:
                QMessageBox.warning(
                    parent, "Aviso",
                    f"No se pudo leer el Excel de relación:\n{err}\n\n"
                    "Se usará el portapapeles como alternativa.",
                )
        except Exception as exc:
            QMessageBox.warning(
                parent, "Aviso",
                f"Error leyendo el Excel de relación:\n{exc}\n\n"
                "Se usará el portapapeles como alternativa.",
            )

    dlg = ProjectNameDialogWx(parent)
    if dlg.exec() != 1:
        return None, None
    project_data = dlg.get_project_data()
    project_name = dlg.get_project_name()
    return project_data, project_name


# ---------------------------------------------------------------------------
# Selector de presupuesto desde Excel de relación
# ---------------------------------------------------------------------------

class BudgetSelectorDialog(QDialog):
    """Muestra los presupuestos leídos del Excel de relación y permite elegir uno."""

    def __init__(self, parent, budgets: list, preselect_numero: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Presupuesto")
        self._budgets = budgets
        self._filtered: list = list(budgets)
        self._preselect_numero = preselect_numero.strip()
        self.project_data = None
        self.project_name = None
        self._use_clipboard = False
        self.name_generator = ProjectNameGenerator()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        title = theme.create_title(self, "Crear Presupuesto desde Relación", "xl")
        layout.addWidget(title)

        inst = theme.create_text(
            self, "Selecciona un presupuesto de la lista o utiliza el portapapeles como alternativa.",
        )
        inst.setWordWrap(True)
        layout.addWidget(inst)

        search_layout = QHBoxLayout()
        lbl_search = QLabel("Buscar:", self)
        lbl_search.setFont(theme.get_font_medium())
        lbl_search.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
        search_layout.addWidget(lbl_search)
        self._search = QLineEdit(self)
        self._search.setFont(theme.font_base())
        self._search.setPlaceholderText("Buscar por cualquier campo...")
        self._search.textChanged.connect(self._on_filter)
        search_layout.addWidget(self._search, 1)
        layout.addLayout(search_layout)

        self._table = QTableWidget(self)
        cols = [("Nº", 50), ("Fecha", 85), ("Cliente", 200), ("Calle", 200),
                ("Localidad", 100), ("Tipo", 160), ("Importe", 80)]
        self._table.setColumnCount(len(cols))
        self._table.setHorizontalHeaderLabels([c[0] for c in cols])
        for i, (_, w) in enumerate(cols):
            self._table.setColumnWidth(i, w)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(lambda: self._on_ok())
        self._populate_table(self._budgets)
        layout.addWidget(self._table, 1)

        layout.addWidget(theme.create_divider(self))

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("Cancelar", self)
        btn_cancel.setFont(theme.font_base())
        btn_cancel.setFixedHeight(32)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addSpacing(8)

        btn_clipboard = QPushButton("Pegar desde portapapeles", self)
        btn_clipboard.setFont(theme.font_base())
        btn_clipboard.setFixedHeight(32)
        btn_clipboard.clicked.connect(self._on_clipboard)
        btn_layout.addWidget(btn_clipboard)
        btn_layout.addSpacing(8)

        btn_ok = QPushButton("Crear presupuesto", self)
        btn_ok.setFont(theme.get_font_medium())
        btn_ok.setFixedHeight(32)
        btn_ok.setProperty("class", "primary")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_ok)
        btn_layout.addWidget(btn_ok)

        layout.addLayout(btn_layout)
        theme.fit_dialog(self, 920, 520)

    def _populate_table(self, items: list):
        self._table.setRowCount(len(items))
        select_row = -1
        for i, b in enumerate(items):
            self._table.setItem(i, 0, QTableWidgetItem(str(b.get("numero", ""))))
            self._table.setItem(i, 1, QTableWidgetItem(b.get("fecha", "")))
            self._table.setItem(i, 2, QTableWidgetItem(b.get("cliente", "")))
            self._table.setItem(i, 3, QTableWidgetItem(b.get("calle", "")))
            self._table.setItem(i, 4, QTableWidgetItem(b.get("localidad", "")))
            self._table.setItem(i, 5, QTableWidgetItem(b.get("tipo", "")))
            self._table.setItem(i, 6, QTableWidgetItem(b.get("importe", "")))
            if (self._preselect_numero
                    and str(b.get("numero", "")).strip() == self._preselect_numero):
                select_row = i
        if select_row >= 0:
            self._table.selectRow(select_row)
            self._table.scrollToItem(self._table.item(select_row, 0))

    def _on_filter(self):
        query = self._search.text().strip().lower()
        if not query:
            self._filtered = list(self._budgets)
        else:
            self._filtered = [
                b for b in self._budgets
                if query in " ".join(str(v) for v in b.values()).lower()
            ]
        self._populate_table(self._filtered)

    def _on_ok(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._filtered):
            QMessageBox.information(self, "Aviso", "Selecciona un presupuesto de la lista.")
            return
        budget = self._filtered[row]
        self.project_data = {k: v for k, v in budget.items() if k != "importe"}
        self.project_name = self.name_generator.generate_project_name(self.project_data)
        self.accept()

    def _on_clipboard(self):
        self._use_clipboard = True
        self.reject()

    def used_clipboard_fallback(self) -> bool:
        return self._use_clipboard

    def get_project_data(self):
        return self.project_data

    def get_project_name(self):
        return self.project_name


# ---------------------------------------------------------------------------
# Diálogo de configuración de rutas por defecto
# ---------------------------------------------------------------------------

class DefaultPathsDialog(QDialog):
    """Permite al usuario configurar las 3 rutas por defecto de la aplicación."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rutas por defecto")
        from src.core.settings import Settings
        self._settings = Settings()
        self._fields: dict = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        title = theme.create_title(self, "Rutas por defecto", "xl")
        layout.addWidget(title)

        inst = theme.create_text(
            self,
            "Configura las carpetas y archivos por defecto que se usarán "
            "al abrir y guardar presupuestos.",
        )
        inst.setWordWrap(True)
        layout.addWidget(inst)
        layout.addSpacing(theme.SPACE_MD)

        from src.core.settings import Settings
        descriptions = [
            (Settings.PATH_SAVE_BUDGETS, "Carpeta para guardar presupuestos nuevos:", "dir"),
            (Settings.PATH_OPEN_BUDGETS, "Carpeta para abrir presupuestos existentes:", "dir"),
            (Settings.PATH_RELATION_FILE, "Archivo Excel de relación de presupuestos:", "file"),
        ]

        for key, label_text, mode in descriptions:
            lbl = QLabel(label_text, self)
            lbl.setFont(theme.get_font_medium())
            lbl.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
            layout.addWidget(lbl)

            row = QHBoxLayout()
            tc = QLineEdit(self)
            tc.setReadOnly(True)
            tc.setFont(theme.font_base())
            tc.setMinimumHeight(32)
            current = self._settings.get_default_path(key) or ""
            tc.setText(current)
            row.addWidget(tc, 1)

            btn_browse = QPushButton("Examinar...", self)
            btn_browse.setFont(theme.font_sm())
            btn_browse.setFixedHeight(28)
            btn_browse.clicked.connect(lambda checked, k=key, t=tc, m=mode: self._browse(k, t, m))
            row.addWidget(btn_browse)

            btn_clear = QPushButton("Limpiar", self)
            btn_clear.setFont(theme.font_sm())
            btn_clear.setFixedHeight(28)
            btn_clear.clicked.connect(lambda checked, t=tc: t.setText(""))
            row.addWidget(btn_clear)

            layout.addLayout(row)
            self._fields[key] = tc

        layout.addStretch()
        layout.addWidget(theme.create_divider(self))
        layout.addSpacing(8)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("Cancelar", self)
        btn_cancel.setFont(theme.font_base())
        btn_cancel.setFixedSize(90, 30)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addSpacing(8)

        btn_save = QPushButton("Guardar", self)
        btn_save.setFont(theme.get_font_medium())
        btn_save.setFixedSize(90, 30)
        btn_save.setProperty("class", "primary")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)
        theme.fit_dialog(self, 600, 420)

    def _browse(self, key: str, textctrl: QLineEdit, mode: str):
        if mode == "dir":
            path = QFileDialog.getExistingDirectory(
                self, "Selecciona una carpeta", textctrl.text(),
            )
        else:
            default_dir = os.path.dirname(textctrl.text()) if textctrl.text() else ""
            path, _ = QFileDialog.getOpenFileName(
                self, "Selecciona el archivo Excel", default_dir,
                "Archivos Excel (*.xlsx)",
            )
        if path:
            textctrl.setText(path)

    def _on_save(self):
        from src.core.settings import Settings

        warnings = []
        for key, tc in self._fields.items():
            path = tc.text().strip()
            if not path:
                continue
            if key == Settings.PATH_RELATION_FILE:
                if not os.path.isfile(path):
                    warnings.append(f"El archivo no existe: {path}")
            else:
                if not os.path.isdir(path):
                    warnings.append(f"La carpeta no existe: {path}")

        if warnings:
            msg = "Se detectaron rutas que no existen:\n\n" + "\n".join(warnings) + "\n\n¿Guardar de todas formas?"
            resp = QMessageBox.warning(
                self, "Rutas no válidas", msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resp != QMessageBox.StandardButton.Yes:
                return

        for key, tc in self._fields.items():
            self._settings.set_default_path(key, tc.text())
        self.accept()
