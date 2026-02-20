"""
Diálogo para gestionar plantillas de presupuesto personalizadas.

Permite al usuario:
- Ver la lista de plantillas (predefinidas y personalizadas)
- Añadir nuevas plantillas importando partidas desde un Excel existente
- Eliminar plantillas personalizadas (no las predefinidas)
- Ver las partidas de una plantilla seleccionada
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QListWidget, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from src.core.work_type_catalog import WorkTypeCatalog
from src.core.excel_partidas_extractor import ExcelPartidasExtractor
from src.gui import theme
from src.utils.helpers import run_in_background


class TemplateManagerDialog(QDialog):
    """Diálogo para gestionar plantillas de presupuesto."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestionar Plantillas de Presupuesto")

        self._catalog = WorkTypeCatalog()
        self._extractor = ExcelPartidasExtractor()

        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        title = theme.create_title(panel, "Gestionar Plantillas", "xl")
        layout.addWidget(title)

        subtitle = theme.create_text(
            panel,
            "Gestiona tu biblioteca de plantillas de presupuesto. "
            "Las plantillas personalizadas se crean importando las partidas "
            "desde un presupuesto Excel ya existente.",
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)
        layout.addSpacing(theme.SPACE_MD)

        content_layout = QHBoxLayout()

        # Panel izquierdo
        left_layout = QVBoxLayout()
        lbl_list = QLabel("Plantillas disponibles:", panel)
        lbl_list.setFont(theme.get_font_medium())
        lbl_list.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
        left_layout.addWidget(lbl_list)

        self._template_list = QListWidget(panel)
        self._template_list.setFont(theme.font_base())
        self._template_list.setMinimumWidth(280)
        self._template_list.currentRowChanged.connect(self._on_select)
        left_layout.addWidget(self._template_list, 1)

        btn_list_layout = QHBoxLayout()
        btn_add = QPushButton("+ Añadir desde Excel", panel)
        btn_add.setFont(theme.get_font_medium())
        btn_add.setFixedHeight(38)
        btn_add.setProperty("class", "primary")
        btn_add.clicked.connect(self._on_add)
        btn_list_layout.addWidget(btn_add)

        self._btn_delete = QPushButton("Eliminar", panel)
        self._btn_delete.setFont(theme.font_base())
        self._btn_delete.setFixedHeight(38)
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._on_delete)
        btn_list_layout.addWidget(self._btn_delete)

        left_layout.addLayout(btn_list_layout)
        content_layout.addLayout(left_layout)
        content_layout.addSpacing(theme.SPACE_LG)

        # Panel derecho
        right_layout = QVBoxLayout()
        lbl_detail = QLabel("Partidas de la plantilla:", panel)
        lbl_detail.setFont(theme.get_font_medium())
        lbl_detail.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
        right_layout.addWidget(lbl_detail)

        self._detail_table = QTableWidget(panel)
        self._detail_table.setColumnCount(3)
        self._detail_table.setHorizontalHeaderLabels(["Concepto", "Ud.", "Precio ref."])
        self._detail_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._detail_table.setColumnWidth(1, 50)
        self._detail_table.setColumnWidth(2, 90)
        self._detail_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._detail_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._detail_table.setAlternatingRowColors(True)
        self._detail_table.verticalHeader().setVisible(False)
        self._detail_table.setFont(theme.font_sm())
        self._detail_table.setMinimumWidth(320)
        right_layout.addWidget(self._detail_table, 1)

        self._lbl_count = theme.create_text(panel, "", muted=True)
        right_layout.addWidget(self._lbl_count)

        content_layout.addLayout(right_layout, 1)
        layout.addLayout(content_layout, 1)

        layout.addSpacing(theme.SPACE_MD)
        layout.addWidget(theme.create_divider(panel))
        layout.addSpacing(theme.SPACE_MD)

        btn_close = QPushButton("Cerrar", panel)
        btn_close.setFont(theme.font_base())
        btn_close.setFixedSize(100, 40)
        btn_close.clicked.connect(self.accept)
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_layout.addWidget(btn_close)
        layout.addLayout(close_layout)

        main_layout.addWidget(panel)

        self.setMinimumSize(700, 520)
        self.resize(740, 560)

    def _refresh_list(self):
        self._template_list.clear()
        self._detail_table.setRowCount(0)
        self._lbl_count.setText("")
        self._btn_delete.setEnabled(False)

        predefined = self._catalog.get_predefined_names()
        custom = self._catalog.get_custom_names()

        for name in predefined:
            self._template_list.addItem(f"  {name}")
        for name in custom:
            self._template_list.addItem(f"* {name}")

    def _on_select(self, row):
        if row < 0:
            self._detail_table.setRowCount(0)
            self._lbl_count.setText("")
            self._btn_delete.setEnabled(False)
            return

        display_name = self._template_list.item(row).text()
        nombre = display_name[2:]
        is_custom = display_name.startswith("* ")

        self._btn_delete.setEnabled(is_custom)

        plantilla = self._catalog.get_by_name(nombre)
        self._detail_table.setRowCount(0)

        if not plantilla:
            self._lbl_count.setText("")
            return

        partidas = plantilla.get('partidas_base', [])
        self._detail_table.setRowCount(len(partidas))
        for i, p in enumerate(partidas):
            self._detail_table.setItem(i, 0, QTableWidgetItem(p.get('concepto', '')))
            self._detail_table.setItem(i, 1, QTableWidgetItem(p.get('unidad', 'ud')))
            precio = p.get('precio_ref', 0)
            price_item = QTableWidgetItem(f"{precio:.2f} €")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._detail_table.setItem(i, 2, price_item)

        self._lbl_count.setText(f"{len(partidas)} partidas")

    def _on_add(self):
        nombre, ok = QInputDialog.getText(
            self,
            "Nueva plantilla personalizada",
            "Nombre para la nueva plantilla:\n\n"
            "Ejemplo: Reforma cocina completa, Sustitución ascensor, etc.",
        )
        if not ok or not nombre:
            return
        nombre = nombre.strip()
        if not nombre:
            QMessageBox.warning(self, "Error", "El nombre no puede estar vacío.")
            return

        existing = self._catalog.get_by_name(nombre)
        if existing and not existing.get('personalizada'):
            QMessageBox.warning(
                self, "Nombre duplicado",
                f"Ya existe una plantilla predefinida con ese nombre:\n'{nombre}'.\n\n"
                "Elige un nombre diferente.",
            )
            return

        if existing and existing.get('personalizada'):
            confirm = QMessageBox.question(
                self, "Reemplazar plantilla",
                f"Ya existe una plantilla personalizada con ese nombre:\n'{nombre}'.\n\n"
                "¿Deseas reemplazarla?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        excel_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecciona el presupuesto Excel para importar partidas",
            "", "Archivos Excel (*.xlsx)",
        )
        if not excel_path:
            return

        self._btn_delete.setEnabled(False)

        def _on_extract_done(ok_flag, payload):
            self._btn_delete.setEnabled(True)
            if not ok_flag or not payload:
                QMessageBox.warning(
                    self, "Sin partidas",
                    f"No se encontraron partidas en el archivo:\n{os.path.basename(excel_path)}\n\n"
                    "Asegúrate de que el Excel tiene partidas con el formato de la plantilla "
                    "(número en col A, unidad en col B, descripción en col C, "
                    "cantidad en col G, precio en col H).",
                )
                return

            partidas = payload
            resumen = f"Se encontraron {len(partidas)} partidas en el Excel:\n\n"
            for i, p in enumerate(partidas[:8]):
                resumen += f"  {i+1}. {p['concepto'][:50]} ({p['unidad']}, {p['precio_ref']:.2f}€)\n"
            if len(partidas) > 8:
                resumen += f"  ... y {len(partidas) - 8} más\n"
            resumen += f"\n¿Guardar como plantilla '{nombre}'?"

            confirm = QMessageBox.question(
                self, "Confirmar importación", resumen,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

            plantilla = {
                'nombre': nombre,
                'categoria': 'personalizada',
                'descripcion': f"Plantilla importada desde {os.path.basename(excel_path)}",
                'contexto_ia': (
                    f"Presupuesto de tipo '{nombre}'. "
                    f"Partidas de referencia importadas de un presupuesto real. "
                    f"Usar como base para generar partidas similares adaptadas al caso concreto."
                ),
                'partidas_base': partidas,
            }

            if self._catalog.add_custom(plantilla):
                QMessageBox.information(
                    self, "Plantilla creada",
                    f"Plantilla '{nombre}' guardada con {len(partidas)} partidas.",
                )
                self._refresh_list()

                custom_names = self._catalog.get_custom_names()
                predefined_count = len(self._catalog.get_predefined_names())
                if nombre in custom_names:
                    idx = predefined_count + custom_names.index(nombre)
                    self._template_list.setCurrentRow(idx)
            else:
                QMessageBox.critical(self, "Error", "Error al guardar la plantilla.")

        run_in_background(lambda: self._extractor.extract(excel_path), _on_extract_done)

    def _on_delete(self):
        row = self._template_list.currentRow()
        if row < 0:
            return

        display_name = self._template_list.item(row).text()
        if not display_name.startswith("* "):
            QMessageBox.warning(
                self, "No permitido",
                "Solo se pueden eliminar plantillas personalizadas.",
            )
            return

        nombre = display_name[2:]

        confirm = QMessageBox.warning(
            self, "Confirmar eliminación",
            f"¿Eliminar la plantilla personalizada '{nombre}'?\n\n"
            "Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        if self._catalog.remove_custom(nombre):
            QMessageBox.information(self, "Eliminada", f"Plantilla '{nombre}' eliminada.")
            self._refresh_list()
        else:
            QMessageBox.critical(self, "Error", "Error al eliminar la plantilla.")
