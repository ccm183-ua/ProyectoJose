"""
Diálogo final para revisar partidas históricas + IA complementaria.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.partida_normalizer import normalize_partida_for_excel
from src.gui import theme


class CombinedPartidasReviewDialog(QDialog):
    def __init__(
        self,
        parent,
        historical_partidas=None,
        ai_partidas=None,
        merge_duplicates_note: str = "",
        cobertura=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Revisión final de partidas")
        self._historical_partidas = historical_partidas or []
        self._ai_partidas = ai_partidas or []
        self._merge_duplicates_note = (merge_duplicates_note or "").strip()
        self._cobertura = cobertura or {}
        self._rows = []
        self._selected_partidas = []
        self._updating_totals = False
        self._build_rows()
        self._build_ui()
        self._populate()

    def _coverage_summary_text(self) -> str:
        """Resume la cobertura del orquestador en uno de cuatro estados.

        No usa "precios reales" como sinónimo de histórico: una referencia
        histórica es un precio de una obra anterior, no una vigencia garantizada.
        """
        n_hist = int(self._cobertura.get("partidas_historicas", 0) or 0)
        n_ia = int(self._cobertura.get("partidas_ia", 0) or 0)
        if n_hist and n_ia:
            return (
                f"Mezcla: {n_hist} de referencias históricas + {n_ia} estimadas por IA. "
                "Revisa las estimadas antes de aceptar."
            )
        if n_hist:
            return f"Todas las partidas ({n_hist}) provienen de referencias históricas."
        if n_ia:
            return f"Todas las partidas ({n_ia}) son estimaciones de IA. Revísalas antes de aceptar."
        failure_reason = self._cobertura.get("failure_reason", "")
        sufijo = f" ({failure_reason})" if failure_reason and failure_reason != "OK" else ""
        return f"Resultado incompleto: no se ha generado cobertura.{sufijo}"

    def _build_rows(self):
        for partida in self._historical_partidas:
            self._rows.append(
                {
                    "origin": "Histórica",
                    "partida": normalize_partida_for_excel(dict(partida or {}), source="historical"),
                }
            )
        for partida in self._ai_partidas:
            self._rows.append(
                {
                    "origin": "IA complementaria",
                    "partida": normalize_partida_for_excel(dict(partida or {}), source="ai_completion"),
                }
            )
    def _build_ui(self):
        main = QVBoxLayout(self)
        panel = QWidget(self)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        lay.setSpacing(theme.SPACE_SM)

        lay.addWidget(theme.create_title(panel, "Revisión final combinada", "xl"))
        lay.addWidget(
            QLabel(
                f"Históricas: {len(self._historical_partidas)} | IA complementaria: {len(self._ai_partidas)}",
                panel,
            )
        )
        if self._cobertura:
            cobertura_lbl = QLabel(self._coverage_summary_text(), panel)
            cobertura_lbl.setWordWrap(True)
            cobertura_lbl.setStyleSheet(f"color: {theme.TEXT_TERTIARY}; background: transparent;")
            lay.addWidget(cobertura_lbl)
        if self._merge_duplicates_note:
            dup = QLabel(self._merge_duplicates_note, panel)
            dup.setWordWrap(True)
            dup.setStyleSheet(f"color: {theme.TEXT_TERTIARY}; background: transparent;")
            lay.addWidget(dup)

        self._table = QTableWidget(panel)
        self._table.setColumnCount(10)
        self._table.setHorizontalHeaderLabels(
            [
                "Usar",
                "Origen",
                "Título",
                "Descripción",
                "Ud",
                "Cantidad",
                "Precio",
                "Total",
                "Confianza",
                "Motivo/Fuente",
            ]
        )
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.setColumnWidth(0, 55)
        self._table.setColumnWidth(1, 110)
        self._table.setColumnWidth(2, 260)
        self._table.setColumnWidth(3, 420)
        self._table.setColumnWidth(4, 70)
        self._table.setColumnWidth(5, 90)
        self._table.setColumnWidth(6, 90)
        self._table.setColumnWidth(7, 90)
        self._table.setColumnWidth(8, 90)
        self._table.setColumnWidth(9, 260)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(False)
        self._table.setWordWrap(False)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self._table.doubleClicked.connect(self._toggle_current_row)
        self._table.itemChanged.connect(self._on_item_changed)
        lay.addWidget(self._table, 1)

        btns = QHBoxLayout()
        for text, fn in (
            ("Seleccionar todas", self._select_all),
            ("Deseleccionar todas", self._select_none),
        ):
            btn = QPushButton(text, panel)
            btn.clicked.connect(fn)
            btns.addWidget(btn)
        btns.addStretch()
        lay.addLayout(btns)

        lay.addWidget(theme.create_divider(panel))
        actions = QHBoxLayout()
        actions.addStretch()
        btn_cancel = QPushButton("Cancelar", panel)
        btn_cancel.clicked.connect(self.reject)
        actions.addWidget(btn_cancel)
        btn_apply = QPushButton("Confirmar", panel)
        btn_apply.setProperty("class", "primary")
        btn_apply.clicked.connect(self._on_apply)
        actions.addWidget(btn_apply)
        lay.addLayout(actions)

        main.addWidget(panel)
        self.resize(1100, 650)
        self.setMinimumSize(900, 520)

    def _populate(self):
        self._table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            partida = row["partida"]
            origin = row["origin"]
            concepto = str(partida.get("titulo") or partida.get("concepto") or "").strip()
            descripcion = str(partida.get("descripcion", "")).strip()
            unidad = str(partida.get("unidad", "ud")).strip()
            cantidad = float(partida.get("cantidad", 1) or 1)
            precio = float(partida.get("precio_unitario", 0) or 0)
            confianza = partida.get("confidence", "")
            motivo = partida.get("reason") or partida.get("source") or partida.get("module") or ""
            total = cantidad * precio

            tooltip = (
                f"Título: {concepto or '-'}\n"
                f"Descripción: {descripcion or '-'}\n"
                f"Origen: {origin}"
            )

            use_item = QTableWidgetItem()
            use_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
            use_item.setCheckState(Qt.CheckState.Checked)
            use_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            use_item.setToolTip(tooltip)
            self._table.setItem(i, 0, use_item)

            origin_item = QTableWidgetItem(origin)
            origin_item.setToolTip(tooltip)
            self._table.setItem(i, 1, origin_item)

            title_item = QTableWidgetItem(concepto)
            title_item.setToolTip(tooltip)
            self._table.setItem(i, 2, title_item)

            desc_item = QTableWidgetItem(descripcion)
            desc_item.setToolTip(tooltip)
            self._table.setItem(i, 3, desc_item)

            unit_item = QTableWidgetItem(unidad)
            unit_item.setToolTip(tooltip)
            self._table.setItem(i, 4, unit_item)
            self._table.setItem(i, 5, QTableWidgetItem(str(cantidad)))
            self._table.setItem(i, 6, QTableWidgetItem(str(precio)))
            self._table.setItem(i, 7, QTableWidgetItem(f"{total:.2f}"))
            self._table.setItem(i, 8, QTableWidgetItem(str(confianza)))
            self._table.setItem(i, 9, QTableWidgetItem(str(motivo)))

            for col in (2, 3, 5, 6):
                item = self._table.item(i, col)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

    def _toggle_current_row(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._rows):
            return
        it = self._table.item(row, 0)
        if it is None:
            return
        it.setCheckState(
            Qt.CheckState.Unchecked
            if it.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )

    def _select_all(self):
        self._table.blockSignals(True)
        for i in range(self._table.rowCount()):
            it = self._table.item(i, 0)
            if it is not None:
                it.setCheckState(Qt.CheckState.Checked)
        self._table.blockSignals(False)

    def _select_none(self):
        self._table.blockSignals(True)
        for i in range(self._table.rowCount()):
            it = self._table.item(i, 0)
            if it is not None:
                it.setCheckState(Qt.CheckState.Unchecked)
        self._table.blockSignals(False)

    def _on_apply(self):
        selected = []
        for row, data in enumerate(self._rows):
            use_it = self._table.item(row, 0)
            if use_it is None or use_it.checkState() != Qt.CheckState.Checked:
                continue
            try:
                cantidad = float((self._table.item(row, 5).text() or "1").replace(",", "."))
                precio = float((self._table.item(row, 6).text() or "0").replace(",", "."))
            except ValueError:
                QMessageBox.warning(self, "Valor inválido", "Cantidad y precio deben ser numéricos.")
                return

            partida = dict(data["partida"])
            concepto = str(self._table.item(row, 2).text() or "").strip()
            unidad = str(self._table.item(row, 4).text() or "").strip()
            if not concepto:
                QMessageBox.warning(
                    self,
                    "Fila inválida",
                    f"La fila {row + 1} tiene el concepto vacío. Debe indicar título/concepto.",
                )
                return
            if not unidad:
                QMessageBox.warning(
                    self,
                    "Fila inválida",
                    f"La fila {row + 1} tiene la unidad vacía. Debe indicar una unidad.",
                )
                return
            if cantidad <= 0:
                QMessageBox.warning(
                    self,
                    "Fila inválida",
                    f"La fila {row + 1} tiene cantidad <= 0. Debe ser mayor que 0.",
                )
                return
            if precio < 0:
                QMessageBox.warning(
                    self,
                    "Fila inválida",
                    f"La fila {row + 1} tiene precio negativo. Debe ser >= 0.",
                )
                return

            partida["titulo"] = concepto
            partida["concepto"] = concepto
            partida["descripcion"] = str(self._table.item(row, 3).text() or "").strip()
            partida["unidad"] = unidad
            partida["cantidad"] = cantidad
            partida["precio_unitario"] = precio
            normalized_source = "historical" if data["origin"] == "Histórica" else "ai_completion"
            selected.append(normalize_partida_for_excel(partida, source=normalized_source))

        self._selected_partidas = selected
        self.accept()

    def get_selected_partidas(self):
        return self._selected_partidas

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._updating_totals or item is None:
            return
        if item.column() not in (5, 6):
            return
        row = item.row()
        try:
            cantidad = float((self._table.item(row, 5).text() or "0").replace(",", "."))
            precio = float((self._table.item(row, 6).text() or "0").replace(",", "."))
        except ValueError:
            return

        self._updating_totals = True
        total_item = self._table.item(row, 7)
        if total_item is None:
            total_item = QTableWidgetItem()
            self._table.setItem(row, 7, total_item)
        total_item.setText(f"{(cantidad * precio):.2f}")
        self._updating_totals = False
