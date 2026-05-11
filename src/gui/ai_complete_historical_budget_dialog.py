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
    QPushButton,
    QTextEdit,
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
        panel = QWidget(self)
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
        layout.addWidget(
            QLabel(
                "Resumen del contexto confirmado:\n"
                f"{self._confirmed_context or '(sin contexto adicional)'}",
                panel,
            )
        )

        resumen = []
        for p in self._selected_historical_partidas[:12]:
            concepto = p.get("concepto") or p.get("titulo") or "-"
            unidad = p.get("unidad", "ud")
            cantidad = p.get("cantidad", 0)
            resumen.append(f"- {concepto} ({cantidad} {unidad})")
        if len(self._selected_historical_partidas) > 12:
            resumen.append(f"... y {len(self._selected_historical_partidas) - 12} más")
        resumen_text = "\n".join(resumen) if resumen else "-"
        resumen_label = QLabel(f"Listado resumido:\n{resumen_text}", panel)
        resumen_label.setWordWrap(True)
        layout.addWidget(resumen_label)

        lbl_extra = QLabel("Instrucciones adicionales para completar (opcional):", panel)
        lbl_extra.setFont(theme.get_font_medium())
        layout.addWidget(lbl_extra)

        self._instructions = QTextEdit(panel)
        self._instructions.setPlaceholderText(
            "Opcional: prioridades, límites de alcance, exclusiones, etc."
        )
        self._instructions.setMaximumHeight(100)
        layout.addWidget(self._instructions)

        layout.addWidget(theme.create_divider(panel))
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
        layout.addLayout(buttons)

        main_layout.addWidget(panel)
        self.resize(900, 680)

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
