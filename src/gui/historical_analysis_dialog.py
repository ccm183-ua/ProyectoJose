"""
Diálogo para analizar presupuestos históricos desde una carpeta.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from src.core.historical_budget_analyzer import HistoricalBudgetAnalyzer
from src.core.historical_analysis_status import AnalysisStatus
from src.core.settings import Settings
from src.gui.historical_analysis_results_dialog import HistoricalAnalysisResultsDialog
from src.gui import theme
from src.utils.helpers import run_in_background


class HistoricalAnalysisDialog(QDialog):
    """Permite ejecutar análisis histórico sobre una carpeta de presupuestos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Analizar presupuestos terminados")
        self._analyzer = HistoricalBudgetAnalyzer()
        self._settings = Settings()
        self._build_ui()
        # Precargar la última carpeta analizada para no tener que volver a buscarla.
        last_folder = self._settings.get_default_path(Settings.PATH_HISTORICAL_FOLDER)
        if last_folder:
            self._folder_list.addItem(last_folder)

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

        folder_label = theme.create_form_label(self, "Carpetas de presupuestos:")
        layout.addWidget(folder_label)

        self._folder_list = QListWidget(self)
        self._folder_list.setFont(theme.font_base())
        self._folder_list.setMinimumHeight(120)
        self._folder_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self._folder_list)

        folder_actions = QHBoxLayout()
        btn_add = QPushButton("+ Añadir carpeta...", self)
        btn_add.setFont(theme.font_base())
        btn_add.setFixedHeight(32)
        btn_add.clicked.connect(self._on_add_folder)
        folder_actions.addWidget(btn_add)

        btn_remove = QPushButton("Quitar seleccionadas", self)
        btn_remove.setFont(theme.font_base())
        btn_remove.setFixedHeight(32)
        btn_remove.clicked.connect(self._on_remove_selected_folders)
        folder_actions.addWidget(btn_remove)
        folder_actions.addStretch()
        layout.addLayout(folder_actions)

        self._recursive_check = QCheckBox("Incluir subcarpetas", self)
        self._recursive_check.setChecked(True)
        self._recursive_check.setFont(theme.font_base())
        layout.addWidget(self._recursive_check)

        self._force_check = QCheckBox("Reanalizar todo (ignorar caché por fecha)", self)
        self._force_check.setChecked(False)
        self._force_check.setFont(theme.font_base())
        layout.addWidget(self._force_check)

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
        theme.fit_dialog(self, 700, 540)

    def _on_add_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Selecciona una carpeta")
        if not path:
            return
        existing = {
            self._folder_list.item(i).text() for i in range(self._folder_list.count())
        }
        if path not in existing:
            self._folder_list.addItem(path)

    def _on_remove_selected_folders(self):
        for item in self._folder_list.selectedItems():
            self._folder_list.takeItem(self._folder_list.row(item))

    def _on_run(self):
        folders = [self._folder_list.item(i).text() for i in range(self._folder_list.count())]
        if not folders:
            QMessageBox.information(
                self, "Carpeta requerida", "Añade al menos una carpeta para analizar."
            )
            return

        # Recordar la última carpeta para el auto-análisis en el arranque.
        self._settings.set_default_path(Settings.PATH_HISTORICAL_FOLDER, folders[-1])

        self._run_btn.setEnabled(False)
        self._status_label.setText("Analizando...")
        self._summary.setPlainText("Procesando archivos, por favor espera...")

        recursive = self._recursive_check.isChecked()
        force_reanalyze = self._force_check.isChecked()

        def _work():
            return self._analyzer.analyze_folders(
                folders, recursive=recursive, force_reanalyze=force_reanalyze
            )

        def _done(ok: bool, payload):
            self._run_btn.setEnabled(True)
            if not ok:
                self._status_label.setText("Error en análisis")
                self._summary.setPlainText(str(payload))
                return

            summary = payload or {}
            status_counts = summary.get("status_counts", {})
            self._status_label.setText("Análisis completado")
            self._summary.setPlainText(
                f"Run ID: {summary.get('run_id', '-')}\n"
                f"Archivos encontrados: {summary.get('total_archivos', 0)}\n"
                f"Analizados nuevos: {summary.get('procesados', 0)}\n"
                f"Omitidos sin cambios: {status_counts.get(AnalysisStatus.SKIPPED_UNCHANGED, 0)}\n"
                f"Errores técnicos: {status_counts.get(AnalysisStatus.READ_ERROR, 0)}\n\n"
                f"Aptos para aprendizaje: {status_counts.get(AnalysisStatus.VALID, 0)}\n"
                f"Aptos con warnings menores: {status_counts.get(AnalysisStatus.VALID_WITH_WARNINGS, 0)}\n"
                f"Excluidos por datos incompletos: {status_counts.get(AnalysisStatus.EXCLUDED_INCOMPLETE_DATA, 0)}\n"
                f"No compatibles: {status_counts.get(AnalysisStatus.NOT_COMPATIBLE, 0)}\n"
                f"Excluidos manualmente: {status_counts.get(AnalysisStatus.MANUALLY_EXCLUDED, 0)}\n\n"
                f"Incidencias totales (warnings + severos): {summary.get('warnings', 0)}"
            )
            warnings_detail = summary.get("warnings_detail", [])
            if warnings_detail:
                lines = ["", "Detalle warnings por archivo:"]
                for item in warnings_detail[:40]:
                    lines.append(f"- {item.get('excel_path', '')}")
                    for warning in item.get("warnings", []):
                        lines.append(f"    · {warning}")
                self._summary.append("\n".join(lines))

            run_id = summary.get("run_id")
            if run_id:
                dlg = HistoricalAnalysisResultsDialog(self, run_id=run_id)
                dlg.exec()

        run_in_background(_work, _done)
