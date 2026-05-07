"""
Diálogo auditable de resultados del análisis histórico.
"""

import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from src.core.historical_analysis_status import AnalysisStatus
from src.core.historical_budget_analyzer import HistoricalBudgetAnalyzer
from src.core.repositories import (
    get_historical_learning_metrics,
    get_historical_budget_issues,
    get_historical_budget_partidas,
    list_historical_budgets_by_run,
    replace_budget_issues,
    set_historical_budget_manual_status,
)
from src.gui import theme


class HistoricalAnalysisResultsDialog(QDialog):
    def __init__(self, parent=None, run_id: int | None = None):
        super().__init__(parent)
        self.setWindowTitle("Resultados análisis histórico")
        self._run_id = run_id
        self._rows = list_historical_budgets_by_run(run_id) if run_id else []
        self._metrics = get_historical_learning_metrics(run_id)
        self._analyzer = HistoricalBudgetAnalyzer()
        self._build_ui()
        self._populate_table()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        layout.addWidget(theme.create_title(self, "Auditoría de archivos analizados", "xl"))
        subtitle = theme.create_text(
            self,
            f"Run ID: {self._run_id or '-'} · Archivos: {len(self._rows)}",
        )
        layout.addWidget(subtitle)

        kpi = QHBoxLayout()
        self._kpi_budgets = QLabel(self)
        self._kpi_partidas = QLabel(self)
        self._kpi_patterns = QLabel(self)
        for lbl in (self._kpi_budgets, self._kpi_partidas, self._kpi_patterns):
            lbl.setFont(theme.font_sm())
            lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; background: transparent;")
            kpi.addWidget(lbl)
            kpi.addSpacing(theme.SPACE_MD)
        kpi.addStretch()
        layout.addLayout(kpi)
        self._refresh_kpis()

        filter_row = QHBoxLayout()
        self._status_filter = QComboBox(self)
        self._status_filter.addItems(
            [
                "Todos",
                AnalysisStatus.VALID,
                AnalysisStatus.VALID_WITH_WARNINGS,
                AnalysisStatus.EXCLUDED_INCOMPLETE_DATA,
                AnalysisStatus.NOT_COMPATIBLE,
                AnalysisStatus.READ_ERROR,
                AnalysisStatus.SKIPPED_UNCHANGED,
                AnalysisStatus.MANUALLY_EXCLUDED,
            ]
        )
        self._status_filter.currentIndexChanged.connect(self._populate_table)
        filter_row.addWidget(self._status_filter)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Buscar por archivo...")
        self._search.textChanged.connect(self._populate_table)
        filter_row.addWidget(self._search, 1)
        layout.addLayout(filter_row)

        self._table = QTableWidget(self)
        self._table.setColumnCount(11)
        self._table.setHorizontalHeaderLabels(
            ["Estado", "Archivo", "Nº esperado", "Nº detectado", "Hoja", "Score", "Partidas", "Total", "Warnings", "Aprende", "Acciones"]
        )
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 180)
        self._table.setColumnWidth(2, 110)
        self._table.setColumnWidth(3, 110)
        self._table.setColumnWidth(4, 130)
        self._table.setColumnWidth(5, 80)
        self._table.setColumnWidth(6, 80)
        self._table.setColumnWidth(7, 100)
        self._table.setColumnWidth(8, 80)
        self._table.setColumnWidth(9, 90)
        self._table.setColumnWidth(10, 110)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._show_detail_selected)
        layout.addWidget(self._table, 1)

        actions = QHBoxLayout()
        self._stats_lbl = QLabel("", self)
        self._stats_lbl.setFont(theme.font_sm())
        self._stats_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; background: transparent;")
        actions.addWidget(self._stats_lbl)
        actions.addStretch()

        btn_detail = QPushButton("Ver detalle", self)
        btn_detail.clicked.connect(self._show_detail_selected)
        actions.addWidget(btn_detail)

        btn_close = QPushButton("Cerrar", self)
        btn_close.clicked.connect(self.accept)
        actions.addWidget(btn_close)
        layout.addLayout(actions)
        theme.fit_dialog(self, 1180, 620)

    def _populate_table(self):
        status = self._status_filter.currentText()
        search = self._search.text().strip().lower()
        filtered = []
        for row in self._rows:
            if status != "Todos" and row.get("analysis_status") != status:
                continue
            path = row.get("ruta_excel", "")
            if search and search not in path.lower() and search not in os.path.basename(path).lower():
                continue
            filtered.append(row)

        self._table.setRowCount(len(filtered))
        for i, row in enumerate(filtered):
            status_value = row.get("analysis_status", "")
            state_item = QTableWidgetItem(self._status_label(status_value))
            state_item.setForeground(self._status_color(status_value))
            self._table.setItem(i, 0, state_item)
            self._table.setItem(i, 1, QTableWidgetItem(row.get("ruta_excel", "")))
            self._table.setItem(i, 2, QTableWidgetItem(row.get("expected_numero", "")))
            self._table.setItem(i, 3, QTableWidgetItem(row.get("detected_numero", "")))
            self._table.setItem(i, 4, QTableWidgetItem(row.get("selected_sheet", "")))

            score_item = QTableWidgetItem(str(row.get("compatible_score", 0)))
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 5, score_item)

            partidas = QTableWidgetItem(str(row.get("num_partidas", 0)))
            partidas.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 6, partidas)

            total = QTableWidgetItem(f"{float(row.get('total', 0.0)):.2f} €")
            total.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 7, total)

            warnings = QTableWidgetItem(str(row.get("warning_count", 0)))
            warnings.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 8, warnings)

            self._table.setItem(i, 9, QTableWidgetItem("Sí" if row.get("usable_for_learning") else "No"))
            self._table.item(i, 0).setData(Qt.ItemDataRole.UserRole, row)
            btn_detail_row = QPushButton("Ver detalle", self._table)
            btn_detail_row.setFont(theme.font_sm())
            btn_detail_row.clicked.connect(lambda _checked=False, data=row: self._show_detail_for_data(data))
            self._table.setCellWidget(i, 10, btn_detail_row)

        self._stats_lbl.setText(f"Mostrando {len(filtered)} de {len(self._rows)} archivos")

    @staticmethod
    def _status_label(status: str) -> str:
        return {
            AnalysisStatus.VALID: "✅ VALID",
            AnalysisStatus.VALID_WITH_WARNINGS: "🟡 VALID_WITH_WARNINGS",
            AnalysisStatus.EXCLUDED_INCOMPLETE_DATA: "🚫 EXCLUDED_INCOMPLETE_DATA",
            AnalysisStatus.NOT_COMPATIBLE: "📄 NOT_COMPATIBLE",
            AnalysisStatus.SKIPPED_UNCHANGED: "⏭ SKIPPED_UNCHANGED",
            AnalysisStatus.READ_ERROR: "❌ READ_ERROR",
            AnalysisStatus.MANUALLY_EXCLUDED: "🛑 MANUALLY_EXCLUDED",
        }.get(status, status or "-")

    @staticmethod
    def _status_color(status: str):
        color_map = {
            AnalysisStatus.VALID: theme.qcolor(theme.SUCCESS),
            AnalysisStatus.VALID_WITH_WARNINGS: theme.qcolor(theme.WARNING),
            AnalysisStatus.EXCLUDED_INCOMPLETE_DATA: theme.qcolor(theme.ERROR),
            AnalysisStatus.NOT_COMPATIBLE: theme.qcolor(theme.TEXT_SECONDARY),
            AnalysisStatus.SKIPPED_UNCHANGED: theme.qcolor(theme.TEXT_TERTIARY),
            AnalysisStatus.READ_ERROR: theme.qcolor(theme.ERROR),
            AnalysisStatus.MANUALLY_EXCLUDED: theme.qcolor(theme.ERROR),
        }
        return color_map.get(status, theme.qcolor(theme.TEXT_PRIMARY))

    def _show_detail_selected(self):
        row_index = self._table.currentRow()
        if row_index < 0:
            QMessageBox.information(self, "Detalle", "Selecciona un archivo para ver el detalle.")
            return
        item = self._table.item(row_index, 0)
        data = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not data:
            return
        self._show_detail_for_data(data)

    def _show_detail_for_data(self, data: dict):
        if not data:
            return

        issues = get_historical_budget_issues(int(data.get("id") or 0))
        partidas = get_historical_budget_partidas(int(data.get("id") or 0), limit=150)

        detail = QTextEdit(self)
        detail.setReadOnly(True)
        lines = [
            f"Archivo: {data.get('ruta_excel', '')}",
            f"Estado: {data.get('analysis_status', '')}",
            f"Motivo: {self._status_explanation(data.get('analysis_status', ''))}",
            f"Hoja usada: {data.get('selected_sheet', '')}",
            f"Número esperado: {data.get('expected_numero', '')}",
            f"Número detectado: {data.get('detected_numero', '')}",
            f"Score compatibilidad: {int(data.get('compatible_score', 0))}",
            f"Partidas detectadas: {data.get('num_partidas', 0)}",
            f"Total detectado: {float(data.get('total', 0.0)):.2f} €",
            "",
            "Issues:",
        ]
        if issues:
            lines.extend([f"- {i.get('severity', '')} {i.get('code', '')}: {i.get('message', '')}" for i in issues])
        else:
            lines.append("- Sin issues registrados.")

        lines.append("")
        lines.append("Partidas extraídas:")
        if partidas:
            for p in partidas:
                lines.append(
                    f"- {p.get('codigo', '')} {p.get('concepto_original', '')} | "
                    f"{p.get('unidad', '')} | cant {p.get('cantidad', 0):.2f} | precio {p.get('precio_unitario', 0):.2f}"
                )
        else:
            lines.append("- Sin partidas persistidas.")

        detail.setPlainText("\n".join(lines))

        dlg = QDialog(self)
        dlg.setWindowTitle("Detalle de archivo analizado")
        lay = QVBoxLayout(dlg)
        lay.addWidget(detail)
        actions = QHBoxLayout()
        btn_include = QPushButton("Marcar como apto manualmente", dlg)
        btn_include.clicked.connect(lambda: self._include_selected(data, dlg))
        actions.addWidget(btn_include)

        btn_exclude = QPushButton("Excluir del aprendizaje", dlg)
        btn_exclude.clicked.connect(lambda: self._exclude_selected(data, dlg))
        actions.addWidget(btn_exclude)

        btn_reanalyze = QPushButton("Reanalizar este archivo", dlg)
        btn_reanalyze.clicked.connect(lambda: self._reanalyze_selected(data, dlg))
        actions.addWidget(btn_reanalyze)

        btn_open = QPushButton("Abrir Excel", dlg)
        btn_open.clicked.connect(lambda: self._open_excel(data))
        actions.addWidget(btn_open)
        actions.addStretch()

        btn_close = QPushButton("Cerrar", dlg)
        btn_close.clicked.connect(dlg.accept)
        actions.addWidget(btn_close)
        lay.addLayout(actions)
        theme.fit_dialog(dlg, 900, 540)
        dlg.exec()

    @staticmethod
    def _status_explanation(status: str) -> str:
        return {
            AnalysisStatus.VALID: "Archivo apto para aprendizaje.",
            AnalysisStatus.VALID_WITH_WARNINGS: "Apto para aprendizaje, con avisos menores.",
            AnalysisStatus.EXCLUDED_INCOMPLETE_DATA: "Compatible, pero excluido por calidad económica incompleta.",
            AnalysisStatus.NOT_COMPATIBLE: "No se detectó estructura compatible de presupuesto cubiApp.",
            AnalysisStatus.SKIPPED_UNCHANGED: "Sin cambios desde el último análisis.",
            AnalysisStatus.READ_ERROR: "Error técnico durante lectura/análisis del Excel.",
            AnalysisStatus.MANUALLY_EXCLUDED: "Excluido manualmente por decisión del usuario.",
        }.get(status, "Estado no especificado.")

    def _reload_rows(self):
        self._rows = list_historical_budgets_by_run(self._run_id) if self._run_id else []
        self._metrics = get_historical_learning_metrics(self._run_id)
        self._refresh_kpis()
        self._populate_table()

    def _refresh_kpis(self):
        self._kpi_budgets.setText(f"Presupuestos usados: {int(self._metrics.get('presupuestos_usados', 0))}")
        self._kpi_partidas.setText(f"Partidas útiles: {int(self._metrics.get('partidas_utiles', 0))}")
        self._kpi_patterns.setText(f"Patrones generados: {int(self._metrics.get('patrones_generados', 0))}")

    def _exclude_selected(self, data: dict, parent_dialog: QDialog):
        budget_id = int(data.get("id") or 0)
        if budget_id <= 0:
            return
        err = set_historical_budget_manual_status(
            budget_id,
            AnalysisStatus.MANUALLY_EXCLUDED,
            False,
        )
        if err:
            QMessageBox.warning(self, "Excluir", err)
            return
        replace_budget_issues(
            budget_id,
            [
                {
                    "severity": "WARN",
                    "code": "MANUALLY_EXCLUDED",
                    "message": "Excluido manualmente por usuario.",
                }
            ],
        )
        self._rebuild_patterns()
        QMessageBox.information(self, "Excluir", "Archivo excluido del aprendizaje.")
        parent_dialog.accept()
        self._reload_rows()

    def _include_selected(self, data: dict, parent_dialog: QDialog):
        budget_id = int(data.get("id") or 0)
        if budget_id <= 0:
            return
        partidas = get_historical_budget_partidas(budget_id, limit=500)
        if not partidas:
            QMessageBox.warning(
                self,
                "Marcar como apto",
                "No se puede marcar como apto: el archivo no tiene partidas extraídas.",
            )
            return
        has_positive_price = any(float(p.get("precio_unitario", 0.0)) > 0 for p in partidas)
        if not has_positive_price:
            QMessageBox.warning(
                self,
                "Marcar como apto",
                "No se puede marcar como apto: no hay partidas con precio unitario > 0.",
            )
            return
        err = set_historical_budget_manual_status(
            budget_id,
            AnalysisStatus.VALID_WITH_WARNINGS,
            True,
        )
        if err:
            QMessageBox.warning(self, "Marcar como apto", err)
            return
        replace_budget_issues(
            budget_id,
            [
                {
                    "severity": "WARN",
                    "code": "MANUALLY_INCLUDED",
                    "message": "Marcado manualmente como apto para aprendizaje.",
                }
            ],
        )
        reclass_result = self._analyzer.reclassify_budget_modules(budget_id)
        if not reclass_result.get("ok"):
            QMessageBox.warning(
                self,
                "Marcar como apto",
                f"Marcado como apto, pero falló la reclasificación: {reclass_result.get('error', 'desconocido')}",
            )
        self._rebuild_patterns()
        QMessageBox.information(self, "Marcar como apto", "Archivo marcado como apto para aprendizaje.")
        parent_dialog.accept()
        self._reload_rows()

    def _reanalyze_selected(self, data: dict, parent_dialog: QDialog):
        excel_path = data.get("ruta_excel", "")
        if not excel_path:
            return
        result = self._analyzer.analyze_budget(
            excel_path,
            metadata={"analysis_run_id": self._run_id},
            force_reanalyze=True,
        )
        if result.get("status") == "error":
            QMessageBox.warning(self, "Reanalizar", result.get("error", "Error desconocido"))
            return
        self._rebuild_patterns()
        QMessageBox.information(self, "Reanalizar", "Archivo reanalizado correctamente.")
        parent_dialog.accept()
        self._reload_rows()

    @staticmethod
    def _open_excel(data: dict):
        excel_path = data.get("ruta_excel", "")
        if not excel_path or not os.path.exists(excel_path):
            return
        try:
            if sys.platform == "win32":
                os.startfile(excel_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", excel_path], check=False)
            else:
                subprocess.run(["xdg-open", excel_path], check=False)
        except (OSError, ValueError):
            pass

    @staticmethod
    def _rebuild_patterns():
        from src.core.historical_pattern_builder import HistoricalPatternBuilder

        HistoricalPatternBuilder().rebuild_patterns()
