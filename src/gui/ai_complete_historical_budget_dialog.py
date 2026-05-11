"""
Diálogo específico para completar partidas históricas con IA.
"""

import threading

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QVBoxLayout,
    QWidget,
)

from src.core.budget_generator import BudgetGenerator
from src.core.settings import AI_PROVIDER_DEEPSEEK, Settings
from src.gui import theme


class AICompleteHistoricalBudgetDialog(QDialog):
    _generation_done = Signal(dict)

    def __init__(
        self,
        parent=None,
        project_data=None,
        confirmed_context="",
        selected_historical_partidas=None,
        historical_result=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Completar presupuesto con IA")
        self._generation_done.connect(self._on_generation_complete)

        self._settings = Settings()
        self._project_data = project_data or {}
        self._confirmed_context = confirmed_context or ""
        self._selected_historical_partidas = selected_historical_partidas or []
        self._historical_result = historical_result or {}

        self._action = "cancel"
        self._result = None
        self._pending_instructions = ""
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        layout.addWidget(theme.create_title(panel, "Completar presupuesto con IA", "xl"))
        context_label = theme.create_text(
            panel,
            "La IA propondrá solo partidas complementarias a la selección histórica actual.",
        )
        context_label.setWordWrap(True)
        layout.addWidget(context_label)

        provider = self._settings.get_ai_provider()
        model = (
            self._settings.get_deepseek_model()
            if provider == AI_PROVIDER_DEEPSEEK
            else self._settings.get_gemini_model()
        )
        layout.addWidget(
            QLabel(
                f"Proveedor IA activo: {provider}\nModelo IA activo: {model}",
                panel,
            )
        )

        selected_count = len(self._selected_historical_partidas)
        layout.addWidget(QLabel(f"Partidas históricas seleccionadas: {selected_count}", panel))
        layout.addWidget(QLabel("Resumen del contexto confirmado:", panel))
        self._context_preview = QPlainTextEdit(panel)
        self._context_preview.setReadOnly(True)
        self._context_preview.setPlainText(self._confirmed_context or "(sin contexto adicional)")
        self._context_preview.setMinimumHeight(120)
        self._context_preview.setMaximumHeight(160)
        layout.addWidget(self._context_preview)

        layout.addWidget(QLabel("Partidas históricas seleccionadas (resumen):", panel))
        self._selected_table = QTableWidget(panel)
        self._selected_table.setColumnCount(5)
        self._selected_table.setHorizontalHeaderLabels(["Código", "Título/Concepto", "Ud", "Cantidad", "Precio"])
        self._selected_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._selected_table.setColumnWidth(0, 90)
        self._selected_table.setColumnWidth(2, 70)
        self._selected_table.setColumnWidth(3, 90)
        self._selected_table.setColumnWidth(4, 100)
        self._selected_table.setMinimumHeight(180)
        self._selected_table.setMaximumHeight(220)
        self._selected_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._populate_selected_table()
        layout.addWidget(self._selected_table)

        lbl_extra = QLabel("Instrucciones adicionales para completar (opcional):", panel)
        lbl_extra.setFont(theme.get_font_medium())
        layout.addWidget(lbl_extra)

        self._instructions = QPlainTextEdit(panel)
        self._instructions.setPlaceholderText(
            "Ej.: Añade solo partidas de remates, limpieza o medios auxiliares si faltan."
        )
        self._instructions.setMinimumHeight(90)
        self._instructions.setMaximumHeight(120)
        layout.addWidget(self._instructions)

        scroll.setWidget(panel)
        main_layout.addWidget(scroll)
        main_layout.addWidget(theme.create_divider(self))
        buttons = QHBoxLayout()
        buttons.addStretch()

        btn_cancel = QPushButton("Cancelar", panel)
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)

        btn_only_historical = QPushButton("Continuar solo con históricas", panel)
        btn_only_historical.clicked.connect(self._on_continue_historical)
        buttons.addWidget(btn_only_historical)

        self._btn_generate = QPushButton("Buscar partidas complementarias", panel)
        self._btn_generate.setProperty("class", "primary")
        self._btn_generate.clicked.connect(self._on_generate)
        buttons.addWidget(self._btn_generate)
        main_layout.addLayout(buttons)
        self.resize(760, 620)
        self.setMinimumSize(640, 480)

    def _populate_selected_table(self):
        self._selected_table.setRowCount(len(self._selected_historical_partidas))
        for row, partida in enumerate(self._selected_historical_partidas):
            codigo = str(partida.get("codigo", "") or "").strip()
            concepto = str(partida.get("titulo") or partida.get("concepto") or "-").strip()
            unidad = str(partida.get("unidad", "ud"))
            cantidad = str(partida.get("cantidad", 0))
            precio = str(partida.get("precio_unitario", partida.get("precio", 0)))
            self._selected_table.setItem(row, 0, QTableWidgetItem(codigo))
            self._selected_table.setItem(row, 1, QTableWidgetItem(concepto))
            self._selected_table.setItem(row, 2, QTableWidgetItem(unidad))
            self._selected_table.setItem(row, 3, QTableWidgetItem(cantidad))
            self._selected_table.setItem(row, 4, QTableWidgetItem(precio))

    def _on_continue_historical(self):
        self._action = "historical_only"
        self._result = {"partidas": [], "source": "historical_only"}
        self.accept()

    def _on_generate(self):
        self._pending_instructions = self._instructions.toPlainText().strip()
        self._btn_generate.setEnabled(False)
        self._btn_generate.setText("Buscando...")
        thread = threading.Thread(target=self._run_generation, daemon=True)
        thread.start()

    def _run_generation(self):
        try:
            generator = BudgetGenerator(settings=self._settings)
            result = generator.generate_complementary_partidas(
                project_data=self._project_data,
                confirmed_context=self._confirmed_context,
                selected_historical_partidas=self._selected_historical_partidas,
                historical_result=self._historical_result,
                user_instructions=self._pending_instructions,
            )
            self._generation_done.emit(result)
        except Exception as exc:
            self._generation_done.emit(
                {"partidas": [], "source": "error", "error": f"Error inesperado: {exc}"}
            )

    def _on_generation_complete(self, result):
        self._btn_generate.setEnabled(True)
        self._btn_generate.setText("Buscar partidas complementarias")
        if result.get("error") and not result.get("partidas"):
            QMessageBox.warning(
                self,
                "Error de generación",
                f"No se pudieron generar partidas complementarias:\n\n{result.get('error', '')}",
            )
            return
        self._action = "ai_completion"
        self._result = result
        self.accept()

    def get_action(self) -> str:
        return self._action

    def get_result(self) -> dict:
        return self._result or {"partidas": []}
