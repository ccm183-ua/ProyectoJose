"""
Diálogo de siguiente paso tras seleccionar partidas históricas.
"""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui import theme


class HistoricalSelectionNextStepDialog(QDialog):
    CREATE_ONLY = "CREATE_ONLY"
    COMPLETE_WITH_AI = "COMPLETE_WITH_AI"
    CANCEL = "CANCEL"

    def __init__(self, parent=None, selected_count: int = 0):
        super().__init__(parent)
        self.setWindowTitle("Partidas históricas seleccionadas")
        self._selected_count = selected_count
        self._result = self.CANCEL
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        layout.addWidget(theme.create_title(panel, "Partidas históricas seleccionadas", "lg"))
        info = QLabel(
            f"Has seleccionado {self._selected_count} partidas históricas para este presupuesto.",
            panel,
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        explanation = QLabel(
            "Puedes crear el presupuesto solo con estas partidas o pedir a la IA que proponga "
            "partidas complementarias antes de generar el Excel.",
            panel,
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        layout.addWidget(theme.create_divider(panel))
        layout.addLayout(
            self._build_option(
                panel,
                "Crear solo con históricas",
                "Usa únicamente las partidas seleccionadas.",
                self.CREATE_ONLY,
                primary=True,
            )
        )
        layout.addLayout(
            self._build_option(
                panel,
                "Completar con IA",
                "La IA propondrá partidas adicionales sin sustituir las históricas.",
                self.COMPLETE_WITH_AI,
            )
        )
        layout.addLayout(
            self._build_option(
                panel,
                "Volver",
                "Regresa a la selección anterior.",
                self.CANCEL,
            )
        )

        main_layout.addWidget(panel)
        self.resize(720, 420)

    def _build_option(self, panel, button_text, description, value, primary=False):
        row = QVBoxLayout()
        button_row = QHBoxLayout()
        btn = QPushButton(button_text, panel)
        btn.setMinimumHeight(42)
        if primary:
            btn.setProperty("class", "primary")
        btn.clicked.connect(lambda: self._select(value))
        button_row.addWidget(btn)
        row.addLayout(button_row)
        desc = QLabel(description, panel)
        desc.setWordWrap(True)
        row.addWidget(desc)
        return row

    def _select(self, value: str):
        self._result = value
        self.accept()

    def get_result(self) -> str:
        return self._result
