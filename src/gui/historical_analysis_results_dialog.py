"""
Diálogo auditable de resultados del análisis histórico.
"""

import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.core.historical_analysis_status import AnalysisStatus
from src.core.historical_budget_analyzer import HistoricalBudgetAnalyzer
from src.core.repositories import (
    append_budget_issue,
    get_historical_learning_metrics,
    get_historical_budget_issues,
    get_historical_budget_partidas,
    list_historical_budgets_by_run,
    set_historical_budget_learning_status,
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
        self._pending_learning_decisions: dict[int, bool] = {}
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
        self._status_filter.addItem("Todos", None)
        self._status_filter.addItem("✅ Válidos", AnalysisStatus.VALID)
        self._status_filter.addItem("🟡 Revisar", AnalysisStatus.VALID_WITH_WARNINGS)
        self._status_filter.addItem("🚫 Inválidos", AnalysisStatus.EXCLUDED_INCOMPLETE_DATA)
        self._status_filter.addItem("📄 No compatibles", AnalysisStatus.NOT_COMPATIBLE)
        self._status_filter.addItem("❌ Errores", AnalysisStatus.READ_ERROR)
        self._status_filter.addItem("⏭ Sin cambios", AnalysisStatus.SKIPPED_UNCHANGED)
        self._status_filter.addItem("🛑 Excluidos manualmente", AnalysisStatus.MANUALLY_EXCLUDED)
        self._status_filter.currentIndexChanged.connect(self._populate_table)
        filter_row.addWidget(self._status_filter)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Buscar por archivo...")
        self._search.textChanged.connect(self._populate_table)
        filter_row.addWidget(self._search, 1)

        self._only_review = QCheckBox("Solo revisar", self)
        self._only_review.stateChanged.connect(self._populate_table)
        filter_row.addWidget(self._only_review)
        layout.addLayout(filter_row)

        self._table = QTableWidget(self)
        self._table.setColumnCount(10)
        self._table.setHorizontalHeaderLabels(
            [
                "Estado",
                "Archivo",
                "Nº esperado",
                "Nº detectado",
                "Hoja",
                "Score",
                "Partidas",
                "Total",
                "Avisos",
                "Memoria",
            ]
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
        self._table.setColumnWidth(9, 140)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
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

        btn_include_selected = QPushButton("Incluir en memoria", self)
        btn_include_selected.clicked.connect(self._include_selected_memory)
        actions.addWidget(btn_include_selected)

        btn_exclude_selected = QPushButton("Excluir de memoria", self)
        btn_exclude_selected.clicked.connect(self._exclude_selected_memory)
        actions.addWidget(btn_exclude_selected)

        btn_apply = QPushButton("Aplicar cambios", self)
        btn_apply.clicked.connect(self._apply_learning_decisions)
        actions.addWidget(btn_apply)

        btn_close = QPushButton("Cerrar", self)
        btn_close.clicked.connect(self.accept)
        actions.addWidget(btn_close)
        layout.addLayout(actions)
        theme.fit_dialog(self, 1180, 620)

    def _populate_table(self):
        status = self._status_filter.currentData()
        search = self._search.text().strip().lower()
        filtered = []
        for row in self._rows:
            if self._only_review.isChecked() and row.get("analysis_status") != AnalysisStatus.VALID_WITH_WARNINGS:
                continue
            if status and row.get("analysis_status") != status:
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

            memory_item = self._memory_item_for_row(row)
            self._table.setItem(i, 9, memory_item)
            self._table.item(i, 0).setData(Qt.ItemDataRole.UserRole, row)

        self._stats_lbl.setText(f"Mostrando {len(filtered)} de {len(self._rows)} archivos")

    @staticmethod
    def _status_label(status: str) -> str:
        return {
            AnalysisStatus.VALID: "✅ Válido",
            AnalysisStatus.VALID_WITH_WARNINGS: "🟡 Revisar",
            AnalysisStatus.EXCLUDED_INCOMPLETE_DATA: "🚫 Inválido",
            AnalysisStatus.NOT_COMPATIBLE: "📄 No compatible",
            AnalysisStatus.SKIPPED_UNCHANGED: "⏭ Sin cambios",
            AnalysisStatus.READ_ERROR: "❌ Error",
            AnalysisStatus.MANUALLY_EXCLUDED: "🛑 Excluido",
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

    @staticmethod
    def _severity_label(severity: str) -> str:
        return {
            "INFO": "Info",
            "WARN": "Aviso",
            "SEVERE": "Grave",
            "ERROR": "Error",
        }.get((severity or "").strip().upper(), severity or "-")

    @staticmethod
    def _issue_code_label(code: str) -> str:
        key = (code or "").strip().upper()
        return {
            "SEVERE_MANY_ZERO_PRICES": "Más del 50% de las partidas tienen precio unitario igual o menor que 0.",
            "SEVERE_TOTAL_ZERO": "El presupuesto tiene total 0 o no se ha detectado correctamente.",
            "SEVERE_NO_PARTIDAS": "No se han detectado partidas válidas en el presupuesto.",
            "NO_PARTIDA_STRUCTURE": "El archivo no tiene una estructura de partidas compatible.",
            "NO_BUDGET_HEADER": "No se ha detectado la cabecera esperada del presupuesto.",
            "NO_EXPECTED_NUMERO": "No se pudo confirmar el número de presupuesto esperado.",
            "WARN_NO_EXPECTED_NUMERO": "No se pudo confirmar el número de presupuesto esperado.",
            "WARN_NUMERO_MISMATCH": "El número detectado no coincide con el número esperado.",
            "WARN_LOW_PARTIDA_COUNT": "Se detectaron pocas partidas; conviene revisar.",
            "READ_ERROR": "Error técnico durante la lectura del Excel.",
            "MANUALLY_EXCLUDED": "Archivo excluido manualmente del aprendizaje.",
            "MANUALLY_INCLUDED": "Archivo marcado manualmente como apto para aprendizaje.",
            "NO_WORKSHEETS": "No se encontraron hojas de cálculo legibles en el archivo.",
            "NO_PROBE_RESULT": "No se pudo evaluar la compatibilidad del archivo.",
        }.get(key, "Aviso del análisis histórico.")

    def _memory_item_for_row(self, row: dict) -> QTableWidgetItem:
        budget_id = int(row.get("id") or 0)
        status = row.get("analysis_status")
        learning_status = (row.get("learning_status") or "").strip().upper()
        current = bool(row.get("usable_for_learning"))
        if learning_status == "INCLUDED":
            base_label = "Incluido"
            base_color = theme.qcolor(theme.SUCCESS)
        elif learning_status == "PENDING_REVIEW":
            base_label = "Pendiente"
            base_color = theme.qcolor(theme.WARNING)
        elif learning_status == "EXCLUDED":
            base_label = "Excluido"
            base_color = theme.qcolor(theme.TEXT_SECONDARY)
        elif learning_status == "NOT_ELIGIBLE":
            base_label = "No apto"
            base_color = theme.qcolor(theme.ERROR)
        elif status in (AnalysisStatus.EXCLUDED_INCOMPLETE_DATA, AnalysisStatus.NOT_COMPATIBLE, AnalysisStatus.READ_ERROR):
            base_label = "No apto"
            base_color = theme.qcolor(theme.ERROR)
        elif status == AnalysisStatus.VALID_WITH_WARNINGS:
            base_label = "Pendiente"
            base_color = theme.qcolor(theme.WARNING)
        elif current:
            base_label = "Incluido"
            base_color = theme.qcolor(theme.SUCCESS)
        else:
            base_label = "Excluido"
            base_color = theme.qcolor(theme.TEXT_SECONDARY)

        if budget_id in self._pending_learning_decisions:
            pending_decision = bool(self._pending_learning_decisions[budget_id])
            if pending_decision:
                label = "Incluido"
                color = theme.qcolor(theme.SUCCESS)
            else:
                label = "Excluido"
                color = theme.qcolor(theme.TEXT_SECONDARY)
            if pending_decision != current:
                label = f"{label} *"
        else:
            label = base_label
            color = base_color

        item = QTableWidgetItem(label)
        item.setForeground(color)
        return item

    @staticmethod
    def _set_dynamic_table_height(table: QTableWidget, row_count: int, min_rows: int, max_rows: int) -> None:
        visible_rows = min(max(int(row_count or 0), min_rows), max_rows)
        row_height = table.verticalHeader().defaultSectionSize()
        header_height = table.horizontalHeader().height()
        extra = table.frameWidth() * 2 + 8
        table_height = header_height + (visible_rows * row_height) + extra
        table.setMinimumHeight(table_height)
        table.setMaximumHeight(table_height)

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

        dlg = QDialog(self)
        dlg.setWindowTitle("Detalle de archivo analizado")
        dlg.setMinimumSize(1020, 680)
        lay = QVBoxLayout(dlg)

        status_text = self._status_label(data.get("analysis_status", ""))
        memoria_text = self._memory_item_for_row(data).text().replace(" *", "")
        header = QLabel(f"{status_text} — Memoria: {memoria_text}", dlg)
        header.setFont(theme.get_font_medium(13))
        header.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
        lay.addWidget(header)

        details_box = QGroupBox("Datos generales", dlg)
        details_grid = QGridLayout(details_box)
        details_grid.setHorizontalSpacing(theme.SPACE_XL)
        details_grid.setVerticalSpacing(theme.SPACE_XS)

        file_name = os.path.basename(data.get("ruta_excel", "")) or "-"
        file_path = data.get("ruta_excel", "") or "-"
        file_name_lbl = QLabel(file_name, details_box)
        file_name_lbl.setFont(theme.get_font_medium(12))
        file_name_lbl.setWordWrap(True)
        file_path_lbl = QLabel(file_path, details_box)
        file_path_lbl.setWordWrap(True)
        file_path_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; background: transparent;")

        details_grid.addWidget(QLabel("Archivo", details_box), 0, 0)
        details_grid.addWidget(file_name_lbl, 1, 0)
        details_grid.addWidget(file_path_lbl, 2, 0)
        details_grid.addWidget(QLabel(f"Hoja usada: {data.get('selected_sheet', '')}", details_box), 3, 0)
        details_grid.addWidget(QLabel(f"Número esperado: {data.get('expected_numero', '')}", details_box), 4, 0)
        details_grid.addWidget(QLabel(f"Número detectado: {data.get('detected_numero', '')}", details_box), 5, 0)

        details_grid.addWidget(QLabel(f"Score compatibilidad: {int(data.get('compatible_score', 0))}", details_box), 0, 1)
        details_grid.addWidget(QLabel(f"Partidas detectadas: {int(data.get('num_partidas', 0))}", details_box), 1, 1)
        details_grid.addWidget(QLabel(f"Total detectado: {float(data.get('total', 0.0)):.2f} €", details_box), 2, 1)
        details_grid.addWidget(
            QLabel(
                f"Memoria: {memoria_text}",
                details_box,
            ),
            3,
            1,
        )
        details_grid.setColumnStretch(0, 1)
        details_grid.setColumnStretch(1, 1)
        lay.addWidget(details_box)

        diagnosis_box = QGroupBox("Diagnóstico", dlg)
        diagnosis_layout = QVBoxLayout(diagnosis_box)
        diagnosis_label = QLabel(self._status_explanation(data.get("analysis_status", "")), diagnosis_box)
        diagnosis_label.setWordWrap(True)
        diagnosis_layout.addWidget(diagnosis_label)
        lay.addWidget(diagnosis_box)

        issues_box = QGroupBox("Avisos del análisis", dlg)
        issues_layout = QVBoxLayout(issues_box)
        issues_table = QTableWidget(issues_box)
        issues_table.setColumnCount(3)
        issues_table.setHorizontalHeaderLabels(["Nivel", "Motivo", "Código técnico"])
        issues_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        issues_table.setColumnWidth(0, 100)
        issues_table.setColumnWidth(2, 210)
        issues_table.verticalHeader().setVisible(False)
        issues_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        issues_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        if issues:
            issues_table.setRowCount(len(issues))
            for idx, issue in enumerate(issues):
                code = issue.get("code", "")
                issues_table.setItem(idx, 0, QTableWidgetItem(self._severity_label(issue.get("severity", ""))))
                issues_table.setItem(idx, 1, QTableWidgetItem(self._issue_code_label(code)))
                issues_table.setItem(idx, 2, QTableWidgetItem(code))
        else:
            issues_table.setRowCount(1)
            issues_table.setItem(0, 0, QTableWidgetItem("-"))
            issues_table.setItem(0, 1, QTableWidgetItem("Sin avisos registrados."))
            issues_table.setItem(0, 2, QTableWidgetItem("-"))
        self._set_dynamic_table_height(issues_table, issues_table.rowCount(), min_rows=1, max_rows=6)
        issues_layout.addWidget(issues_table)
        lay.addWidget(issues_box)

        partidas_box = QGroupBox("Partidas extraídas", dlg)
        partidas_layout = QVBoxLayout(partidas_box)
        partidas_table = QTableWidget(partidas_box)
        partidas_table.setColumnCount(6)
        partidas_table.setHorizontalHeaderLabels(["Código", "Concepto", "Unidad", "Cantidad", "Precio", "Total"])
        partidas_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        partidas_table.setColumnWidth(0, 90)
        partidas_table.setColumnWidth(2, 90)
        partidas_table.setColumnWidth(3, 90)
        partidas_table.setColumnWidth(4, 90)
        partidas_table.setColumnWidth(5, 100)
        partidas_table.verticalHeader().setVisible(False)
        partidas_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        partidas_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        if partidas:
            partidas_table.setRowCount(len(partidas))
            for idx, partida in enumerate(partidas):
                cantidad = float(partida.get("cantidad", 0.0) or 0.0)
                precio = float(partida.get("precio_unitario", 0.0) or 0.0)
                total = float(partida.get("total_linea") or (cantidad * precio))
                partidas_table.setItem(idx, 0, QTableWidgetItem(partida.get("codigo", "")))
                partidas_table.setItem(idx, 1, QTableWidgetItem(partida.get("concepto_original", "")))
                partidas_table.setItem(idx, 2, QTableWidgetItem(partida.get("unidad", "")))
                partidas_table.setItem(idx, 3, QTableWidgetItem(f"{cantidad:.2f}"))
                partidas_table.setItem(idx, 4, QTableWidgetItem(f"{precio:.2f}"))
                partidas_table.setItem(idx, 5, QTableWidgetItem(f"{total:.2f}"))
        else:
            partidas_table.setRowCount(1)
            partidas_table.setItem(0, 0, QTableWidgetItem("-"))
            partidas_table.setItem(0, 1, QTableWidgetItem("Sin partidas persistidas."))
            partidas_table.setItem(0, 2, QTableWidgetItem("-"))
            partidas_table.setItem(0, 3, QTableWidgetItem("-"))
            partidas_table.setItem(0, 4, QTableWidgetItem("-"))
            partidas_table.setItem(0, 5, QTableWidgetItem("-"))
        self._set_dynamic_table_height(partidas_table, partidas_table.rowCount(), min_rows=3, max_rows=10)
        partidas_layout.addWidget(partidas_table)
        lay.addWidget(partidas_box, 1)

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
        theme.fit_dialog(dlg, 1020, 680)
        dlg.exec()

    @staticmethod
    def _status_explanation(status: str) -> str:
        return {
            AnalysisStatus.VALID: "Archivo apto para aprendizaje.",
            AnalysisStatus.VALID_WITH_WARNINGS: "Archivo técnicamente aprovechable, pero pendiente de revisión manual por avisos.",
            AnalysisStatus.EXCLUDED_INCOMPLETE_DATA: "Compatible, pero excluido por calidad económica incompleta.",
            AnalysisStatus.NOT_COMPATIBLE: "No se detectó estructura compatible de presupuesto cubiApp.",
            AnalysisStatus.SKIPPED_UNCHANGED: "Sin cambios desde el último análisis.",
            AnalysisStatus.READ_ERROR: "Error técnico durante lectura/análisis del Excel.",
            AnalysisStatus.MANUALLY_EXCLUDED: "Excluido manualmente por decisión del usuario.",
        }.get(status, "Estado no especificado.")

    def _reload_rows(self):
        self._rows = list_historical_budgets_by_run(self._run_id) if self._run_id else []
        self._metrics = get_historical_learning_metrics(self._run_id)
        self._pending_learning_decisions = {}
        self._refresh_kpis()
        self._populate_table()

    def _selected_rows_data(self) -> list[dict]:
        selected_data: list[dict] = []
        row_indexes = sorted({item.row() for item in self._table.selectedItems()})
        for row_index in row_indexes:
            item = self._table.item(row_index, 0)
            data = item.data(Qt.ItemDataRole.UserRole) if item else None
            if data:
                selected_data.append(data)
        return selected_data

    def _include_selected_memory(self):
        changed = 0
        for data in self._selected_rows_data():
            status = data.get("analysis_status")
            if status not in (AnalysisStatus.VALID, AnalysisStatus.VALID_WITH_WARNINGS, AnalysisStatus.MANUALLY_EXCLUDED):
                continue
            budget_id = int(data.get("id") or 0)
            if budget_id <= 0:
                continue
            if status == AnalysisStatus.MANUALLY_EXCLUDED:
                partidas = get_historical_budget_partidas(budget_id, limit=500)
                has_positive_price = any(float(p.get("precio_unitario", 0.0) or 0.0) > 0 for p in partidas)
                if not partidas or not has_positive_price:
                    continue
            self._pending_learning_decisions[budget_id] = True
            changed += 1
        if changed:
            self._populate_table()

    def _exclude_selected_memory(self):
        changed = 0
        for data in self._selected_rows_data():
            if data.get("analysis_status") not in (
                AnalysisStatus.VALID,
                AnalysisStatus.VALID_WITH_WARNINGS,
                AnalysisStatus.MANUALLY_EXCLUDED,
            ):
                continue
            budget_id = int(data.get("id") or 0)
            if budget_id > 0:
                self._pending_learning_decisions[budget_id] = False
                changed += 1
        if changed:
            self._populate_table()

    def _apply_learning_decisions(self):
        if not self._pending_learning_decisions:
            QMessageBox.information(self, "Aplicar decisiones", "No hay cambios pendientes.")
            return

        has_changes = False
        for data in self._rows:
            status = data.get("analysis_status")
            if status not in (
                AnalysisStatus.VALID,
                AnalysisStatus.VALID_WITH_WARNINGS,
                AnalysisStatus.MANUALLY_EXCLUDED,
            ):
                continue
            budget_id = int(data.get("id") or 0)
            if budget_id <= 0 or budget_id not in self._pending_learning_decisions:
                continue

            decision = bool(self._pending_learning_decisions[budget_id])
            current = bool(data.get("usable_for_learning"))
            current_learning_status = (data.get("learning_status") or "").strip().upper()
            if not current_learning_status:
                if data.get("analysis_status") in (
                    AnalysisStatus.EXCLUDED_INCOMPLETE_DATA,
                    AnalysisStatus.NOT_COMPATIBLE,
                    AnalysisStatus.READ_ERROR,
                ):
                    current_learning_status = "NOT_ELIGIBLE"
                elif current:
                    current_learning_status = "INCLUDED"
                elif data.get("analysis_status") == AnalysisStatus.VALID_WITH_WARNINGS:
                    current_learning_status = "PENDING_REVIEW"
                else:
                    current_learning_status = "EXCLUDED"

            target_learning_status = "INCLUDED" if decision else "EXCLUDED"
            if decision == current and current_learning_status == target_learning_status:
                continue

            if decision:
                err = set_historical_budget_learning_status(
                    budget_id,
                    "INCLUDED",
                    True,
                    decision_source="MANUAL",
                    decision_reason="Incluido manualmente desde revision de memoria.",
                )
                if err:
                    QMessageBox.warning(self, "Aplicar decisiones", err)
                    continue
                append_budget_issue(
                    budget_id,
                    {
                        "severity": "WARN",
                        "code": "MANUALLY_INCLUDED",
                        "message": "Marcado manualmente como apto para aprendizaje.",
                    },
                )
                self._analyzer.reclassify_budget_modules(budget_id)
                has_changes = True
            else:
                err = set_historical_budget_learning_status(
                    budget_id,
                    "EXCLUDED",
                    False,
                    decision_source="MANUAL",
                    decision_reason="Excluido manualmente desde revision de memoria.",
                )
                if err:
                    QMessageBox.warning(self, "Aplicar decisiones", err)
                    continue
                append_budget_issue(
                    budget_id,
                    {
                        "severity": "WARN",
                        "code": "MANUALLY_EXCLUDED",
                        "message": "Excluido manualmente por usuario.",
                    },
                )
                has_changes = True

        if has_changes:
            self._rebuild_patterns()
            QMessageBox.information(self, "Aplicar decisiones", "Decisiones aplicadas correctamente.")
        else:
            QMessageBox.information(self, "Aplicar decisiones", "No hubo cambios efectivos para aplicar.")
        self._reload_rows()

    def _refresh_kpis(self):
        self._kpi_budgets.setText(f"Presupuestos usados: {int(self._metrics.get('presupuestos_usados', 0))}")
        self._kpi_partidas.setText(f"Partidas útiles: {int(self._metrics.get('partidas_utiles', 0))}")
        self._kpi_patterns.setText(f"Patrones generados: {int(self._metrics.get('patrones_generados', 0))}")

    def _exclude_selected(self, data: dict, parent_dialog: QDialog):
        budget_id = int(data.get("id") or 0)
        if budget_id <= 0:
            return
        err = set_historical_budget_learning_status(
            budget_id,
            "EXCLUDED",
            False,
            decision_source="MANUAL",
            decision_reason="Excluido manualmente por usuario.",
        )
        if err:
            QMessageBox.warning(self, "Excluir", err)
            return
        append_budget_issue(
            budget_id,
            {
                "severity": "WARN",
                "code": "MANUALLY_EXCLUDED",
                "message": "Excluido manualmente por usuario.",
            },
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
        err = set_historical_budget_learning_status(
            budget_id,
            "INCLUDED",
            True,
            decision_source="MANUAL",
            decision_reason="Marcado manualmente como apto para aprendizaje.",
        )
        if err:
            QMessageBox.warning(self, "Marcar como apto", err)
            return
        append_budget_issue(
            budget_id,
            {
                "severity": "WARN",
                "code": "MANUALLY_INCLUDED",
                "message": "Marcado manualmente como apto para aprendizaje.",
            },
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
