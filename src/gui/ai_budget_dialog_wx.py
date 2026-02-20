"""
Diálogo para configurar la generación de partidas con IA.

Permite al usuario:
- Escribir el tipo de obra (texto libre)
- Añadir una descripción adicional para dar contexto a la IA
- Opcionalmente seleccionar una plantilla predefinida como referencia
- Generar partidas con IA o saltar el paso
"""

import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from src.core.work_type_catalog import WorkTypeCatalog
from src.core.budget_generator import BudgetGenerator
from src.core.settings import Settings
from src.gui import theme


class AIBudgetDialog(QDialog):
    """Diálogo para configurar y lanzar la generación de partidas con IA."""

    _generation_done = Signal(dict)

    def __init__(self, parent=None, datos_proyecto=None, context_extra=""):
        super().__init__(parent)
        self.setWindowTitle("Generar Partidas con IA")
        self._generation_done.connect(self._on_generation_complete)

        self._datos_proyecto = datos_proyecto or {}
        self._context_extra = context_extra or ""
        self._catalog = WorkTypeCatalog()
        self._settings = Settings()
        self._selected_plantilla = None
        self._result = None

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        title = theme.create_title(panel, "Generar Partidas con IA", "xl")
        layout.addWidget(title)

        subtitle = theme.create_text(
            panel,
            "Describe el tipo de obra y la IA generará las partidas del presupuesto "
            "con precios orientativos. Opcionalmente selecciona una plantilla de referencia.",
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(theme.SPACE_SM)

        lbl_tipo = QLabel("Tipo de obra:", panel)
        lbl_tipo.setFont(theme.get_font_medium())
        lbl_tipo.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(lbl_tipo)

        self._tipo_text = QLineEdit(panel)
        self._tipo_text.setPlaceholderText("Ej: Reparación de bajante comunitaria, Reforma integral cocina...")
        self._tipo_text.setFont(theme.font_base())
        self._tipo_text.setMinimumHeight(32)
        layout.addWidget(self._tipo_text)

        layout.addSpacing(theme.SPACE_XS)

        lbl_desc = QLabel("Descripción adicional (contexto para la IA):", panel)
        lbl_desc.setFont(theme.get_font_medium())
        lbl_desc.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(lbl_desc)

        self._desc_text = QTextEdit(panel)
        self._desc_text.setPlaceholderText(
            "Ej: Bajante de PVC en patio interior, edificio 4 plantas, "
            "acceso difícil por estrechez del patio..."
        )
        self._desc_text.setFont(theme.font_base())
        self._desc_text.setMaximumHeight(64)
        layout.addWidget(self._desc_text)

        layout.addSpacing(theme.SPACE_XS)

        lbl_plantilla = QLabel("Plantilla de referencia (opcional):", panel)
        lbl_plantilla.setFont(theme.get_font_medium())
        lbl_plantilla.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(lbl_plantilla)

        plantilla_hint = theme.create_text(
            panel,
            "Si seleccionas una, la IA la usará como base para generar partidas más precisas.",
            muted=True,
        )
        layout.addWidget(plantilla_hint)

        names = self._catalog.get_all_names()
        self._plantilla_list = QListWidget(panel)
        self._plantilla_list.addItem("(Ninguna - generar desde cero)")
        self._plantilla_list.addItems(names)
        self._plantilla_list.setCurrentRow(0)
        self._plantilla_list.setFont(theme.font_base())
        self._plantilla_list.setMaximumHeight(100)
        layout.addWidget(self._plantilla_list)

        if not self._settings.has_api_key():
            warning_layout = QHBoxLayout()
            warning_icon = QLabel("⚠", panel)
            warning_icon.setStyleSheet(f"color: {theme.WARNING}; background: transparent;")
            warning_icon.setFont(theme.font_lg())
            warning_layout.addWidget(warning_icon)

            warning_text = theme.create_text(
                panel, "No hay API key configurada. Solo se podrán usar plantillas offline.",
            )
            warning_text.setStyleSheet(f"color: {theme.WARNING}; background: transparent;")
            warning_layout.addWidget(warning_text, 1)
            layout.addSpacing(theme.SPACE_SM)
            layout.addLayout(warning_layout)

        layout.addSpacing(theme.SPACE_MD)
        layout.addWidget(theme.create_divider(panel))
        layout.addSpacing(theme.SPACE_MD)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_skip = QPushButton("Saltar", panel)
        btn_skip.setFont(theme.font_base())
        btn_skip.setFixedSize(120, 44)
        btn_skip.setToolTip("Crear presupuesto vacío sin partidas IA")
        btn_skip.clicked.connect(self.reject)
        btn_layout.addWidget(btn_skip)
        btn_layout.addSpacing(theme.SPACE_MD)

        self._btn_generate = QPushButton("Generar partidas con IA", panel)
        self._btn_generate.setFont(theme.get_font_medium())
        self._btn_generate.setFixedSize(220, 44)
        self._btn_generate.setProperty("class", "primary")
        self._btn_generate.setDefault(True)
        self._btn_generate.clicked.connect(self._on_generate)
        btn_layout.addWidget(self._btn_generate)

        layout.addLayout(btn_layout)

        main_layout.addWidget(panel)

        self.setMinimumSize(650, 500)
        self.resize(650, 580)

    def _on_generate(self):
        tipo = self._tipo_text.text().strip()
        if not tipo:
            QMessageBox.warning(self, "Campo obligatorio", "Por favor, escribe el tipo de obra.")
            return

        descripcion = self._desc_text.toPlainText().strip()

        sel_idx = self._plantilla_list.currentRow()
        if sel_idx > 0:
            nombre = self._plantilla_list.item(sel_idx).text()
            self._selected_plantilla = self._catalog.get_by_name(nombre)
        else:
            self._selected_plantilla = None

        self._btn_generate.setEnabled(False)
        self._btn_generate.setText("Generando...")

        thread = threading.Thread(
            target=self._run_generation,
            args=(tipo, descripcion),
            daemon=True,
        )
        thread.start()

    def _run_generation(self, tipo, descripcion):
        try:
            api_key = self._settings.get_api_key()
            generator = BudgetGenerator(api_key=api_key)

            full_desc = descripcion
            if self._context_extra:
                full_desc = f"{descripcion}\n{self._context_extra}" if descripcion else self._context_extra

            result = generator.generate(
                tipo_obra=tipo,
                descripcion=full_desc,
                plantilla=self._selected_plantilla,
                datos_proyecto=self._datos_proyecto,
            )

            self._generation_done.emit(result)
        except Exception as exc:
            self._generation_done.emit({
                'partidas': [],
                'source': 'error',
                'error': f"Error inesperado en la generación: {exc}",
            })

    def _on_generation_complete(self, result):
        self._result = result
        self._btn_generate.setEnabled(True)
        self._btn_generate.setText("Generar partidas con IA")

        source = result.get('source', 'error')

        if source == 'error' or (result.get('error') and not result.get('partidas')):
            QMessageBox.warning(
                self, "Error de generación",
                f"No se pudieron generar partidas:\n\n{result.get('error', '')}",
            )
            return

        if source == 'offline':
            confirm = QMessageBox.question(
                self,
                "Modo offline - Partidas de plantilla",
                "La IA no está disponible en este momento (cuota agotada o sin conexión).\n\n"
                "Se han cargado las partidas base de la plantilla seleccionada "
                "como punto de partida. Estas partidas NO han sido adaptadas por la IA "
                "a tu descripción específica.\n\n"
                "¿Quieres usar estas partidas base como referencia?\n"
                "(Podrás editarlas manualmente en el siguiente paso)",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                self._result = None
                return
            self.accept()
            return

        self.accept()

    def get_result(self):
        return self._result
