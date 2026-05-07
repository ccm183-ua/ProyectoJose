"""
Diálogo para analizar presupuestos históricos desde una carpeta.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from src.core.historical_budget_analyzer import HistoricalBudgetAnalyzer
from src.gui import theme
from src.utils.helpers import run_in_background


class HistoricalAnalysisDialog(QDialog):
    """Permite ejecutar análisis histórico sobre una carpeta de presupuestos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Analizar presupuestos terminados")
        self._analyzer = HistoricalBudgetAnalyzer()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        title = theme.create_title(self, "Analizar presupuestos terminados", "xl")
        layout.addWidget(title)

        text = theme.create_text(
            self,
            "La aplicación extraerá partidas de los presupuestos seleccionados y las guardará\n"
            "en una base histórica reutilizable. Los presupuestos ya analizados no se volverán\n"
            "a procesar salvo que el Excel haya cambiado.",
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        layout.addSpacing(theme.SPACE_SM)

        folder_label = theme.create_form_label(self, "Carpeta de presupuestos:")
        layout.addWidget(folder_label)

        row = QHBoxLayout()
        self._folder_input = QLineEdit(self)
        self._folder_input.setReadOnly(True)
        self._folder_input.setMinimumHeight(32)
        self._folder_input.setFont(theme.font_base())
        row.addWidget(self._folder_input, 1)

        btn_browse = QPushButton("Seleccionar...", self)
        btn_browse.setFont(theme.font_base())
        btn_browse.setFixedHeight(32)
        btn_browse.clicked.connect(self._on_browse)
        row.addWidget(btn_browse)
        layout.addLayout(row)

        self._recursive_check = QCheckBox("Incluir subcarpetas", self)
        self._recursive_check.setChecked(True)
        self._recursive_check.setFont(theme.font_base())
        layout.addWidget(self._recursive_check)

        self._status_label = QLabel("Pendiente", self)
        self._status_label.setFont(theme.font_sm())
        self._status_label.setStyleSheet(f"color: {theme.TEXT_MUTED}; background: transparent;")
        layout.addWidget(self._status_label)

        self._summary = QTextEdit(self)
        self._summary.setReadOnly(True)
        self._summary.setMinimumHeight(120)
        self._summary.setFont(theme.font_base())
        layout.addWidget(self._summary, 1)

        layout.addWidget(theme.create_divider(self))
        actions = QHBoxLayout()
        actions.addStretch()

        self._cancel_btn = QPushButton("Cerrar", self)
        self._cancel_btn.setFont(theme.font_base())
        self._cancel_btn.setFixedHeight(32)
        self._cancel_btn.clicked.connect(self.reject)
        actions.addWidget(self._cancel_btn)
        actions.addSpacing(8)

        self._run_btn = QPushButton("Analizar", self)
        self._run_btn.setFont(theme.get_font_medium())
        self._run_btn.setFixedHeight(32)
        self._run_btn.setProperty("class", "primary")
        self._run_btn.clicked.connect(self._on_run)
        actions.addWidget(self._run_btn)

        layout.addLayout(actions)
        theme.fit_dialog(self, 700, 460)

    def _on_browse(self):
        path = QFileDialog.getExistingDirectory(self, "Selecciona una carpeta")
        if path:
            self._folder_input.setText(path)

    def _on_run(self):
        folder = self._folder_input.text().strip()
        if not folder:
            QMessageBox.information(self, "Carpeta requerida", "Selecciona una carpeta para analizar.")
            return

        self._run_btn.setEnabled(False)
        self._status_label.setText("Analizando...")
        self._summary.setPlainText("Procesando archivos, por favor espera...")

        recursive = self._recursive_check.isChecked()

        def _work():
            return self._analyzer.analyze_folder(folder, recursive=recursive)

        def _done(ok: bool, payload):
            self._run_btn.setEnabled(True)
            if not ok:
                self._status_label.setText("Error en análisis")
                self._summary.setPlainText(str(payload))
                return

            summary = payload or {}
            self._status_label.setText("Análisis completado")
            self._summary.setPlainText(
                f"Run ID: {summary.get('run_id', '-')}\n"
                f"Total archivos: {summary.get('total_archivos', 0)}\n"
                f"Procesados: {summary.get('procesados', 0)}\n"
                f"Omitidos: {summary.get('omitidos', 0)}\n"
                f"Errores: {summary.get('errores', 0)}"
            )

        run_in_background(_work, _done)
