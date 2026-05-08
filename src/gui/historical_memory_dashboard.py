"""
Panel global de memoria historica.
"""

import json
import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
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
from src.core.historical_integrity_diagnostics import diagnose_historical_integrity
from src.core.historical_issue_catalog import historical_issue_label
from src.core.historical_pattern_builder import HistoricalPatternBuilder
from src.core.database import get_db_path_as_string, open_db_folder
from src.core.repositories import (
    append_budget_issue,
    get_historical_budget_issues,
    get_historical_budget_partidas,
    get_historical_memory_dashboard_metrics,
    list_historical_memory_dashboard_budgets,
    set_historical_budget_learning_status,
)
from src.gui import theme


class HistoricalMemoryDashboard(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Panel de memoria historica")
        self._rows: list[dict] = []
        self._has_any_budgets = False
        self._analyzer = HistoricalBudgetAnalyzer()
        self._build_ui()
        self._reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        layout.addWidget(theme.create_title(self, "Memoria historica", "xl"))
        subtitle = theme.create_text(
            self,
            "Vista global de presupuestos escaneados, calidad de datos, uso en memoria y patrones.",
        )
        layout.addWidget(subtitle)
        self._db_path_label = theme.create_text(
            self,
            f"Base de datos: {get_db_path_as_string()}",
            muted=True,
        )
        self._db_path_label.setWordWrap(True)
        layout.addWidget(self._db_path_label)

        self._kpi_grid = QGridLayout()
        self._kpi_grid.setHorizontalSpacing(theme.SPACE_LG)
        self._kpi_grid.setVerticalSpacing(theme.SPACE_XS)
        self._kpi_labels: dict[str, QLabel] = {}
        kpis = [
            ("total_budgets", "Escaneados"),
            ("valid", "Validos"),
            ("valid_with_warnings", "Con avisos"),
            ("invalid", "Invalidos"),
            ("not_compatible", "No compatibles"),
            ("read_error", "Errores lectura"),
            ("included", "Incluidos"),
            ("pending_review", "Pendientes"),
            ("excluded", "Excluidos"),
            ("not_eligible", "No aptos"),
            ("historical_partidas", "Partidas"),
            ("active_patterns", "Patrones"),
            ("patterns_with_sources", "Patrones con fuentes"),
            ("integrity_errors", "Errores integridad"),
        ]
        for idx, (key, title) in enumerate(kpis):
            label = QLabel(self)
            label.setFont(theme.font_sm())
            label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; background: transparent;")
            self._kpi_labels[key] = label
            self._kpi_grid.addWidget(label, idx // 7, idx % 7)
        layout.addLayout(self._kpi_grid)

        filter_row = QHBoxLayout()
        self._status_filter = QComboBox(self)
        self._status_filter.addItem("Estado técnico: todos", "")
        self._status_filter.addItem("Válido", AnalysisStatus.VALID)
        self._status_filter.addItem("Revisar", AnalysisStatus.VALID_WITH_WARNINGS)
        self._status_filter.addItem("Inválido", AnalysisStatus.EXCLUDED_INCOMPLETE_DATA)
        self._status_filter.addItem("No compatible", AnalysisStatus.NOT_COMPATIBLE)
        self._status_filter.addItem("Error de lectura", AnalysisStatus.READ_ERROR)
        self._status_filter.currentIndexChanged.connect(self._reload)
        filter_row.addWidget(self._status_filter)

        self._learning_filter = QComboBox(self)
        self._learning_filter.addItem("Memoria: todos", "")
        self._learning_filter.addItem("Incluidos", "INCLUDED")
        self._learning_filter.addItem("Pendientes", "PENDING_REVIEW")
        self._learning_filter.addItem("Excluidos", "EXCLUDED")
        self._learning_filter.addItem("No aptos", "NOT_ELIGIBLE")
        self._learning_filter.currentIndexChanged.connect(self._reload)
        filter_row.addWidget(self._learning_filter)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Buscar por archivo, obra, numero o cliente")
        self._search.textChanged.connect(self._reload)
        filter_row.addWidget(self._search, 1)

        self._only_problems = QCheckBox("Solo problemas", self)
        self._only_problems.stateChanged.connect(self._reload)
        filter_row.addWidget(self._only_problems)
        self._with_warnings = QCheckBox("Con avisos", self)
        self._with_warnings.stateChanged.connect(self._reload)
        filter_row.addWidget(self._with_warnings)
        self._no_modules = QCheckBox("Sin módulos", self)
        self._no_modules.stateChanged.connect(self._reload)
        filter_row.addWidget(self._no_modules)
        self._no_partidas = QCheckBox("Sin partidas", self)
        self._no_partidas.stateChanged.connect(self._reload)
        filter_row.addWidget(self._no_partidas)
        self._no_related_patterns = QCheckBox("Sin patrones", self)
        self._no_related_patterns.stateChanged.connect(self._reload)
        filter_row.addWidget(self._no_related_patterns)

        btn_refresh = QPushButton("Actualizar", self)
        btn_refresh.clicked.connect(self._reload)
        filter_row.addWidget(btn_refresh)
        layout.addLayout(filter_row)

        self._table = QTableWidget(self)
        self._table.setColumnCount(11)
        self._table.setHorizontalHeaderLabels(
            [
                "Archivo / obra",
                "Nº presupuesto",
                "Cliente",
                "Total",
                "Estado técnico",
                "Uso en memoria",
                "Avisos",
                "Partidas",
                "Módulos",
                "Patrones relacionados",
                "Último análisis",
            ]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        for col, width in {
            1: 110,
            2: 140,
            3: 100,
            4: 125,
            5: 125,
            6: 70,
            7: 80,
            9: 80,
            10: 140,
        }.items():
            self._table.setColumnWidth(col, width)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._show_detail_selected)
        self._table.itemSelectionChanged.connect(self._update_action_states)
        layout.addWidget(self._table, 1)

        actions = QHBoxLayout()
        self._stats_lbl = QLabel("", self)
        self._stats_lbl.setFont(theme.font_sm())
        self._stats_lbl.setStyleSheet(f"color: {theme.TEXT_MUTED}; background: transparent;")
        actions.addWidget(self._stats_lbl)
        actions.addStretch()

        self._btn_detail = QPushButton("Ver detalle", self)
        self._btn_detail.clicked.connect(self._show_detail_selected)
        actions.addWidget(self._btn_detail)
        self._btn_open_excel = QPushButton("Abrir Excel", self)
        self._btn_open_excel.clicked.connect(self._open_excel_selected)
        actions.addWidget(self._btn_open_excel)
        self._btn_open_db = QPushButton("Abrir carpeta BD", self)
        self._btn_open_db.clicked.connect(self._open_db_folder)
        actions.addWidget(self._btn_open_db)
        self._btn_include = QPushButton("Incluir en memoria", self)
        self._btn_include.clicked.connect(self._include_selected)
        actions.addWidget(self._btn_include)
        self._btn_exclude = QPushButton("Excluir de memoria", self)
        self._btn_exclude.clicked.connect(self._exclude_selected)
        actions.addWidget(self._btn_exclude)
        self._btn_reanalyze = QPushButton("Reanalizar", self)
        self._btn_reanalyze.clicked.connect(self._reanalyze_selected)
        actions.addWidget(self._btn_reanalyze)
        self._btn_diagnostics = QPushButton("Diagnóstico", self)
        self._btn_diagnostics.clicked.connect(self._run_diagnostics)
        actions.addWidget(self._btn_diagnostics)
        self._btn_rebuild_patterns = QPushButton("Reconstruir patrones", self)
        self._btn_rebuild_patterns.clicked.connect(self._rebuild_patterns)
        actions.addWidget(self._btn_rebuild_patterns)

        btn_close = QPushButton("Cerrar", self)
        btn_close.clicked.connect(self.accept)
        actions.addWidget(btn_close)
        layout.addLayout(actions)
        self._update_action_states()
        theme.fit_dialog(self, 1380, 760)

    def _filters(self) -> dict:
        return {
            "analysis_status": self._status_filter.currentData() or "",
            "learning_status": self._learning_filter.currentData() or "",
            "search": self._search.text().strip(),
            "only_problems": self._only_problems.isChecked(),
            "with_warnings": self._with_warnings.isChecked(),
            "no_modules": self._no_modules.isChecked(),
            "no_partidas": self._no_partidas.isChecked(),
            "no_related_patterns": self._no_related_patterns.isChecked(),
        }

    def _reload(self):
        self._refresh_kpis()
        self._rows = list_historical_memory_dashboard_budgets(self._filters())
        self._populate_table()
        self._update_action_states()

    def _refresh_kpis(self):
        metrics = get_historical_memory_dashboard_metrics()
        try:
            report = diagnose_historical_integrity()
            metrics["integrity_errors"] = len(
                [f for f in report.get("findings", []) if f.get("severity") == "ERROR"]
            )
        except Exception:
            metrics["integrity_errors"] = 0
        titles = {
            "total_budgets": "Escaneados",
            "valid": "Validos",
            "valid_with_warnings": "Con avisos",
            "invalid": "Invalidos",
            "not_compatible": "No compatibles",
            "read_error": "Errores lectura",
            "included": "Incluidos",
            "pending_review": "Pendientes",
            "excluded": "Excluidos",
            "not_eligible": "No aptos",
            "historical_partidas": "Partidas",
            "active_patterns": "Patrones",
            "patterns_with_sources": "Patrones con fuentes",
            "integrity_errors": "Errores integridad",
        }
        for key, label in self._kpi_labels.items():
            label.setText(f"{titles[key]}: {int(metrics.get(key, 0))}")
        total_budgets = int(metrics.get("total_budgets", 0))
        self._has_any_budgets = total_budgets > 0
        if total_budgets == 0:
            self._stats_lbl.setText(
                "No hay presupuestos históricos en esta base de datos.\n"
                f"Base de datos activa: {get_db_path_as_string()}\n"
                "Sugerencia: escanea presupuestos históricos desde 'Herramientas > Analizar presupuestos terminados'.\n"
                "Si esperabas datos, revisa la variable CUBIAPP_DB_PATH."
            )

    def _populate_table(self):
        self._table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            values = [
                self._file_or_project(row),
                row.get("numero_proyecto", ""),
                row.get("cliente", ""),
                f"{float(row.get('total', 0.0)):.2f} EUR",
                self._status_label(row.get("analysis_status", "")),
                self._memory_label(row),
                str(int(row.get("warning_count", 0))),
                str(int(row.get("num_partidas", 0))),
                ", ".join(row.get("modules", [])),
                str(int(row.get("related_patterns", 0))),
                row.get("fecha_analisis", ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (3, 6, 7, 9):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col == 4:
                    item.setForeground(self._status_color(row.get("analysis_status", "")))
                    item.setData(Qt.ItemDataRole.UserRole, row)
                if col == 5:
                    item.setForeground(self._memory_color(row))
                self._table.setItem(i, col, item)
        if self._has_any_budgets:
            self._stats_lbl.setText(f"Mostrando {len(self._rows)} presupuestos")

    def _open_db_folder(self):
        ok = open_db_folder()
        if not ok:
            QMessageBox.warning(
                self,
                "Base de datos",
                "No se pudo abrir la carpeta de la base de datos activa.",
            )

    def _selected_rows_data(self) -> list[dict]:
        rows = sorted({idx.row() for idx in self._table.selectionModel().selectedRows()})
        data = []
        for row_idx in rows:
            item = self._table.item(row_idx, 4)
            row = item.data(Qt.ItemDataRole.UserRole) if item else None
            if row:
                data.append(row)
        return data

    def _selected_row_data(self) -> dict | None:
        rows = self._selected_rows_data()
        if not rows:
            QMessageBox.information(self, "Memoria historica", "Selecciona un presupuesto.")
            return None
        return rows[0]

    def _update_action_states(self):
        rows = self._selected_rows_data()
        has_rows = bool(rows)
        single = len(rows) == 1
        self._btn_detail.setEnabled(single)
        can_include = has_rows and all(self._can_be_included_in_memory(row) for row in rows)
        self._btn_include.setEnabled(can_include)
        can_exclude = has_rows and any(self._can_be_excluded_in_memory(row) for row in rows)
        self._btn_exclude.setEnabled(can_exclude)
        excel_ok = single and bool(rows[0].get("ruta_excel")) and os.path.exists(rows[0].get("ruta_excel", ""))
        self._btn_open_excel.setEnabled(excel_ok)
        self._btn_reanalyze.setEnabled(excel_ok)

    def _show_detail_selected(self):
        data = self._selected_row_data()
        if not data:
            return
        budget_id = int(data.get("id") or 0)
        issues = get_historical_budget_issues(budget_id)
        partidas = get_historical_budget_partidas(budget_id, limit=250)
        probe_summary = self._probe_summary(data.get("probe_diagnostics_json", ""))

        dlg = QDialog(self)
        dlg.setWindowTitle("Detalle de memoria historica")
        lay = QVBoxLayout(dlg)
        lay.addWidget(theme.create_title(dlg, os.path.basename(data.get("ruta_excel", "")) or "Presupuesto", "lg"))
        lay.addWidget(theme.create_text(dlg, data.get("ruta_excel", ""), muted=True))

        box = QGroupBox("Datos generales", dlg)
        grid = QGridLayout(box)
        fields = [
            ("Estado técnico", self._status_label(data.get("analysis_status", ""))),
            ("Uso en memoria", self._memory_label(data)),
            ("Nº presupuesto", data.get("numero_proyecto", "")),
            ("Cliente", data.get("cliente", "")),
            ("Total", f"{float(data.get('total', 0.0)):.2f} EUR"),
            ("Partidas", str(int(data.get("num_partidas", 0)))),
            ("Módulos", ", ".join(data.get("modules", [])) or "-"),
            ("Patrones relacionados", str(int(data.get("related_patterns", 0)))),
            ("Hoja", data.get("selected_sheet", "") or "-"),
            ("Score compatibilidad", str(int(data.get("compatible_score", 0)))),
            ("Resumen diagnóstico técnico", probe_summary),
            ("Último análisis", data.get("fecha_analisis", "") or "-"),
        ]
        for idx, (name, value) in enumerate(fields):
            grid.addWidget(QLabel(name, box), idx // 2, (idx % 2) * 2)
            value_lbl = QLabel(value, box)
            value_lbl.setWordWrap(True)
            grid.addWidget(value_lbl, idx // 2, (idx % 2) * 2 + 1)
        lay.addWidget(box)

        issues_box = QGroupBox("Avisos del análisis", dlg)
        issues_lay = QVBoxLayout(issues_box)
        issues_table = QTableWidget(issues_box)
        issues_table.setColumnCount(3)
        issues_table.setHorizontalHeaderLabels(["Nivel", "Motivo", "Codigo"])
        issues_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        issues_table.setRowCount(len(issues))
        for i, issue in enumerate(issues):
            issues_table.setItem(i, 0, QTableWidgetItem(self._severity_label(issue.get("severity", ""))))
            issues_table.setItem(i, 1, QTableWidgetItem(historical_issue_label(issue.get("code", ""))))
            issues_table.setItem(i, 2, QTableWidgetItem(issue.get("code", "")))
        issues_lay.addWidget(issues_table)
        lay.addWidget(issues_box)

        partidas_box = QGroupBox("Partidas extraídas", dlg)
        partidas_lay = QVBoxLayout(partidas_box)
        partidas_table = QTableWidget(partidas_box)
        partidas_table.setColumnCount(6)
        partidas_table.setHorizontalHeaderLabels(["Orden", "Codigo", "Concepto", "Unidad", "Cantidad", "Precio"])
        partidas_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        partidas_table.setRowCount(len(partidas))
        for i, partida in enumerate(partidas):
            partidas_table.setItem(i, 0, QTableWidgetItem(str(partida.get("orden", ""))))
            partidas_table.setItem(i, 1, QTableWidgetItem(partida.get("codigo", "")))
            partidas_table.setItem(i, 2, QTableWidgetItem(partida.get("concepto_original", "")))
            partidas_table.setItem(i, 3, QTableWidgetItem(partida.get("unidad", "")))
            partidas_table.setItem(i, 4, QTableWidgetItem(f"{float(partida.get('cantidad', 0.0)):.2f}"))
            partidas_table.setItem(i, 5, QTableWidgetItem(f"{float(partida.get('precio_unitario', 0.0)):.2f}"))
        partidas_lay.addWidget(partidas_table)
        lay.addWidget(partidas_box, 1)

        buttons = QHBoxLayout()
        btn_probe = QPushButton("Ver diagnóstico técnico", dlg)
        btn_probe.clicked.connect(lambda: self._show_probe_diagnostics(data))
        buttons.addWidget(btn_probe)
        buttons.addStretch()
        close = QPushButton("Cerrar", dlg)
        close.clicked.connect(dlg.accept)
        buttons.addWidget(close)
        lay.addLayout(buttons)
        theme.fit_dialog(dlg, 1100, 760)
        dlg.exec()

    def _open_excel_selected(self):
        data = self._selected_row_data()
        if data:
            self._open_excel(data)

    def _include_selected(self):
        changed = 0
        for data in self._selected_rows_data():
            if not self._can_be_included_in_memory(data):
                continue
            budget_id = int(data.get("id") or 0)
            err = set_historical_budget_learning_status(
                budget_id,
                "INCLUDED",
                True,
                decision_source="MANUAL",
                decision_reason="Incluido manualmente desde panel de memoria.",
            )
            if err:
                QMessageBox.warning(self, "Incluir en memoria", err)
                continue
            append_budget_issue(
                budget_id,
                {
                    "severity": "WARN",
                    "code": "MANUALLY_INCLUDED",
                    "message": "Marcado manualmente como apto para aprendizaje desde panel de memoria.",
                },
            )
            self._analyzer.reclassify_budget_modules(budget_id)
            changed += 1
        if changed:
            self._rebuild_patterns(silent=True)
            self._reload()
            QMessageBox.information(self, "Incluir en memoria", f"Presupuestos incluidos: {changed}")
        else:
            QMessageBox.information(self, "Incluir en memoria", "No hay presupuestos seleccionados aptos para incluir.")

    def _exclude_selected(self):
        changed = 0
        for data in self._selected_rows_data():
            if not self._can_be_excluded_in_memory(data):
                continue
            budget_id = int(data.get("id") or 0)
            err = set_historical_budget_learning_status(
                budget_id,
                "EXCLUDED",
                False,
                decision_source="MANUAL",
                decision_reason="Excluido manualmente desde panel de memoria.",
            )
            if err:
                QMessageBox.warning(self, "Excluir de memoria", err)
                continue
            append_budget_issue(
                budget_id,
                {
                    "severity": "WARN",
                    "code": "MANUALLY_EXCLUDED",
                    "message": "Excluido manualmente por usuario desde panel de memoria.",
                },
            )
            changed += 1
        if changed:
            self._rebuild_patterns(silent=True)
            self._reload()
            QMessageBox.information(self, "Excluir de memoria", f"Presupuestos excluidos: {changed}")
        else:
            QMessageBox.information(self, "Excluir de memoria", "No hay presupuestos seleccionados válidos para excluir.")

    def _reanalyze_selected(self):
        data = self._selected_row_data()
        if not data:
            return
        excel_path = data.get("ruta_excel", "")
        if not excel_path or not os.path.exists(excel_path):
            QMessageBox.warning(self, "Reanalizar", "No se encuentra el fichero Excel en la ruta registrada.")
            return
        result = self._analyzer.analyze_budget(excel_path, force_reanalyze=True)
        if result.get("status") == "error":
            QMessageBox.warning(self, "Reanalizar", result.get("error", "Error desconocido"))
            return
        self._rebuild_patterns(silent=True)
        self._reload()
        QMessageBox.information(self, "Reanalizar", "Presupuesto reanalizado correctamente.")

    def _run_diagnostics(self):
        report = diagnose_historical_integrity()
        findings = report.get("findings", [])
        by_severity = {"ERROR": 0, "WARN": 0, "INFO": 0}
        for finding in findings:
            sev = (finding.get("severity") or "INFO").upper()
            by_severity[sev] = by_severity.get(sev, 0) + 1
        if not findings:
            preview = "No se han detectado problemas de integridad."
        else:
            lines = []
            for finding in findings[:20]:
                sev = (finding.get("severity") or "INFO").upper()
                check = finding.get("check") or "-"
                message = finding.get("message") or "-"
                row_id = finding.get("row_id")
                entity = f" | entidad: {row_id}" if row_id is not None else ""
                lines.append(f"- [{sev}] {check}: {message}{entity}")
            preview = "\n".join(lines)
        QMessageBox.information(
            self,
            "Diagnóstico de integridad",
            (
                f"Errores: {by_severity.get('ERROR', 0)}\n"
                f"Avisos: {by_severity.get('WARN', 0)}\n"
                f"Info: {by_severity.get('INFO', 0)}\n\n{preview}"
            ),
        )
        self._refresh_kpis()

    def _rebuild_patterns(self, silent: bool = False):
        if not silent:
            confirm = QMessageBox.question(
                self,
                "Reconstruir patrones",
                "Se reconstruiran los patrones historicos con los presupuestos incluidos en memoria.",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
        result = HistoricalPatternBuilder().rebuild_patterns()
        if not silent:
            QMessageBox.information(
                self,
                "Reconstruir patrones",
                f"Patrones reconstruidos: {int(result.get('patterns_inserted', 0))}",
            )
        self._refresh_kpis()

    @staticmethod
    def _file_or_project(data: dict) -> str:
        project = (data.get("nombre_proyecto") or "").strip()
        path = data.get("ruta_excel", "")
        file_name = os.path.basename(path)
        if project and project != file_name:
            return f"{project} - {file_name}"
        return file_name or path

    @staticmethod
    def _can_be_included_in_memory(data: dict) -> bool:
        return data.get("analysis_status") in (
            AnalysisStatus.VALID,
            AnalysisStatus.VALID_WITH_WARNINGS,
        )

    @staticmethod
    def _can_be_excluded_in_memory(data: dict) -> bool:
        status = (data.get("learning_status") or "").strip().upper()
        return status in ("INCLUDED", "PENDING_REVIEW")

    @staticmethod
    def _status_label(status: str) -> str:
        return {
            AnalysisStatus.VALID: "Válido",
            AnalysisStatus.VALID_WITH_WARNINGS: "Revisar",
            AnalysisStatus.EXCLUDED_INCOMPLETE_DATA: "Inválido",
            AnalysisStatus.NOT_COMPATIBLE: "No compatible",
            AnalysisStatus.READ_ERROR: "Error de lectura",
            AnalysisStatus.SKIPPED_UNCHANGED: "Sin cambios",
            AnalysisStatus.MANUALLY_EXCLUDED: "Excluido",
        }.get(status, status or "-")

    @staticmethod
    def _status_color(status: str):
        if status == AnalysisStatus.VALID:
            return theme.qcolor(theme.SUCCESS)
        if status == AnalysisStatus.VALID_WITH_WARNINGS:
            return theme.qcolor(theme.WARNING)
        if status in (
            AnalysisStatus.EXCLUDED_INCOMPLETE_DATA,
            AnalysisStatus.NOT_COMPATIBLE,
            AnalysisStatus.READ_ERROR,
        ):
            return theme.qcolor(theme.ERROR)
        return theme.qcolor(theme.TEXT_SECONDARY)

    @staticmethod
    def _memory_label(data: dict) -> str:
        status = (data.get("learning_status") or "").strip().upper()
        if status == "INCLUDED" or data.get("usable_for_learning"):
            return "Incluido"
        if status == "PENDING_REVIEW":
            return "Pendiente"
        if status == "EXCLUDED":
            return "Excluido"
        if status == "NOT_ELIGIBLE":
            return "No apto"
        return "Sin decidir"

    @staticmethod
    def _memory_color(data: dict):
        status = (data.get("learning_status") or "").strip().upper()
        if status == "INCLUDED" or data.get("usable_for_learning"):
            return theme.qcolor(theme.SUCCESS)
        if status == "PENDING_REVIEW":
            return theme.qcolor(theme.WARNING)
        if status in ("EXCLUDED", "NOT_ELIGIBLE"):
            return theme.qcolor(theme.ERROR)
        return theme.qcolor(theme.TEXT_SECONDARY)

    @staticmethod
    def _severity_label(severity: str) -> str:
        return {
            "INFO": "Info",
            "WARN": "Aviso",
            "SEVERE": "Grave",
            "ERROR": "Error",
        }.get((severity or "").strip().upper(), severity or "-")

    @staticmethod
    def _probe_summary(probe_diagnostics_json: str) -> str:
        raw = (probe_diagnostics_json or "").strip()
        if not raw:
            return "Sin diagnóstico técnico guardado."
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return "Diagnóstico técnico no legible."
        selected = data.get("selected_candidate") or {}
        candidates = data.get("candidates") or []
        score = int(selected.get("score") or data.get("score") or 0)
        sheet = selected.get("sheet_name") or data.get("selected_sheet") or "-"
        partidas = selected.get("partidas_detected") or data.get("partidas_detected")
        if partidas is None:
            partidas = data.get("num_partidas")
        return f"Candidatos: {len(candidates)} | Hoja: {sheet} | Score: {score} | Partidas detectadas: {int(partidas or 0)}"

    def _show_probe_diagnostics(self, data: dict):
        raw = (data.get("probe_diagnostics_json") or "").strip()
        if not raw:
            QMessageBox.information(self, "Diagnóstico técnico", "No hay diagnóstico técnico guardado.")
            return
        try:
            pretty = json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            pretty = raw
        QMessageBox.information(self, "Diagnóstico técnico", pretty[:12000])

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
