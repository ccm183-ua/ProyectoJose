"""
Diálogo final para revisar partidas históricas + IA complementaria.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
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
from src.gui.partida_provenance_model import row_for_partida


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

    def _is_partial(self) -> bool:
        return bool(
            self._cobertura.get("modulos_pendientes")
            or self._cobertura.get("error_ia")
        )

    def _coverage_summary_text(self) -> str:
        """Resume la cobertura del orquestador en uno de cuatro estados.

        No usa "precios reales" como sinónimo de histórico: una referencia
        histórica es un precio de una obra anterior, no una vigencia garantizada.
        """
        n_hist = int(self._cobertura.get("partidas_historicas", 0) or 0)
        n_ia = int(self._cobertura.get("partidas_ia", 0) or 0)
        if n_hist and n_ia:
            base = (
                f"Mezcla: {n_hist} de referencias históricas + {n_ia} estimadas por IA. "
                "Revisa las estimadas antes de aceptar."
            )
        elif n_hist:
            base = f"Todas las partidas ({n_hist}) provienen de referencias históricas."
        elif n_ia:
            base = f"Todas las partidas ({n_ia}) son estimaciones de IA. Revísalas antes de aceptar."
        else:
            failure_reason = self._cobertura.get("failure_reason", "")
            sufijo = f" ({failure_reason})" if failure_reason and failure_reason != "OK" else ""
            base = f"Resultado incompleto: no se ha generado cobertura.{sufijo}"

        if self._is_partial():
            pendientes = ", ".join(
                str(m).replace("_", " ").strip()
                for m in (self._cobertura.get("modulos_pendientes") or [])
            )
            motivo = self._cobertura.get("error_ia") or "sin detalle"
            return (
                f"Resultado parcial: quedan módulos sin resolver ({pendientes or '—'}). "
                f"Motivo: {motivo}. Se conservan las partidas ya obtenidas. {base}"
            )
        return base

    def _build_rows(self):
        # Fixes histórico evidenciado, Tarea 6: conserva el source real
        # ('historical_exact'/'historical_comparable', Tarea 5) en vez de
        # colapsarlo a 'historical' genérico, y guarda el dict crudo (con
        # evidence_level/evidence_price_*/evidence_differences) aparte del
        # normalizado para Excel, que no conserva esos campos.
        for partida in self._historical_partidas:
            raw = dict(partida or {})
            raw.setdefault("source", "historical")
            self._rows.append(
                {"origin": "Histórica", "raw": raw, "partida": normalize_partida_for_excel(raw)}
            )
        for partida in self._ai_partidas:
            raw = dict(partida or {})
            raw.setdefault("source", "ai_completion")
            self._rows.append(
                {"origin": "IA complementaria", "raw": raw, "partida": normalize_partida_for_excel(raw)}
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
            color = theme.WARNING if self._is_partial() else theme.TEXT_TERTIARY
            cobertura_lbl.setStyleSheet(f"color: {color}; background: transparent;")
            lay.addWidget(cobertura_lbl)
        if self._merge_duplicates_note:
            dup = QLabel(self._merge_duplicates_note, panel)
            dup.setWordWrap(True)
            dup.setStyleSheet(f"color: {theme.TEXT_TERTIARY}; background: transparent;")
            lay.addWidget(dup)

        self._table = QTableWidget(panel)
        self._table.setColumnCount(9)
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
                "Motivo/Fuente",
            ]
        )
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for col, width in (
            (0, 46),   # Usar
            (1, 90),   # Origen
            (4, 48),   # Ud
            (5, 70),   # Cantidad
            (6, 80),   # Precio
            (7, 86),   # Total
            (8, 150),  # Motivo/Fuente
        ):
            self._table.setColumnWidth(col, width)
        # Título (2) y Descripción (3) absorben el ancho restante: con el
        # mínimo de 900 px no aparece scroll horizontal.
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
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
        btn_provenance = QPushButton("Ver procedencia", panel)
        btn_provenance.clicked.connect(self._show_provenance_detail)
        btns.addWidget(btn_provenance)
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

    @staticmethod
    def _table_item(text: str, *, editable: bool, tooltip: str = "") -> QTableWidgetItem:
        item = QTableWidgetItem(str(text))
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        item.setFlags(flags)
        if tooltip:
            item.setToolTip(tooltip)
        return item

    def _populate(self):
        # Inserción masiva: itemChanged no debe dispararse mientras la fila
        # está a medias (leería celdas que aún no existen), ni recalcular
        # totales que se escriben explícitamente más abajo.
        self._table.blockSignals(True)
        try:
            self._table.setRowCount(len(self._rows))
            for i, row in enumerate(self._rows):
                partida = row["partida"]
                origin = row["origin"]
                concepto = str(partida.get("titulo") or partida.get("concepto") or "").strip()
                descripcion = str(partida.get("descripcion", "")).strip()
                unidad = str(partida.get("unidad", "ud")).strip()
                cantidad = float(partida.get("cantidad", 1) or 1)
                precio = float(partida.get("precio_unitario", 0) or 0)
                motivo = partida.get("reason") or partida.get("source") or partida.get("module") or ""
                total = cantidad * precio

                tooltip = (
                    f"Título: {concepto or '-'}\n"
                    f"Descripción: {descripcion or '-'}\n"
                    f"Origen: {origin}\n"
                    f"Usa «Ver procedencia» para el detalle."
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

                self._table.setItem(i, 1, self._table_item(origin, editable=False, tooltip=tooltip))
                self._table.setItem(i, 2, self._table_item(concepto, editable=True, tooltip=tooltip))
                self._table.setItem(i, 3, self._table_item(descripcion, editable=True, tooltip=tooltip))
                self._table.setItem(i, 4, self._table_item(unidad, editable=True, tooltip=tooltip))
                self._table.setItem(i, 5, self._table_item(str(cantidad), editable=True))
                self._table.setItem(i, 6, self._table_item(str(precio), editable=True))
                self._table.setItem(i, 7, self._table_item(f"{total:.2f}", editable=False))
                self._table.setItem(i, 8, self._table_item(str(motivo), editable=False))
        finally:
            self._table.blockSignals(False)

    def _toggle_current_row(self, index=None):
        if index is not None and index.column() != 0:
            return
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
            # Fixes histórico evidenciado, Tarea 6: reusar el source ya
            # resuelto en _build_rows (historical_exact/historical_comparable/
            # ai_completion), no volver a colapsarlo por origen genérico.
            selected.append(normalize_partida_for_excel(partida))

        self._selected_partidas = selected
        self.accept()

    def get_selected_partidas(self):
        return self._selected_partidas

    def _provenance_details(self, row_index: int) -> dict:
        """Procedencia completa de una fila, sin depender de que sea columna."""
        row = self._rows[row_index]
        raw = row.get("raw") or {}
        provenance = row_for_partida(raw)
        confidence = raw.get("confidence", "")
        return {
            "Origen": str(row.get("origin", "")),
            "Fuente": provenance["Fuente"],
            "Nivel": provenance["Nivel"],
            "Rango histórico": provenance["Rango histórico"],
            "Diferencias": provenance["Diferencias"],
            "Confianza": str(confidence) if confidence not in (None, "") else "—",
        }

    def _build_provenance_dialog(self, row_index: int) -> QDialog:
        dlg = QDialog(self)
        dlg.setWindowTitle("Detalle de procedencia")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        lay.setSpacing(theme.SPACE_SM)
        concepto = self._table.item(row_index, 2).text()
        lay.addWidget(theme.create_title(dlg, f"Procedencia de: {concepto}", "lg"))
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        for label, value in self._provenance_details(row_index).items():
            value_lbl = QLabel(value, dlg)
            value_lbl.setWordWrap(True)
            form.addRow(QLabel(f"{label}:", dlg), value_lbl)
        lay.addLayout(form)
        actions = QHBoxLayout()
        actions.addStretch()
        close_btn = QPushButton("Cerrar", dlg)
        close_btn.clicked.connect(dlg.accept)
        actions.addWidget(close_btn)
        lay.addLayout(actions)
        theme.fit_dialog(dlg, 520, 320)
        return dlg

    def _show_provenance_detail(self):
        row_index = self._table.currentRow()
        if row_index < 0:
            QMessageBox.information(
                self, "Procedencia", "Selecciona una partida para ver su procedencia."
            )
            return
        self._build_provenance_dialog(row_index).exec()

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
