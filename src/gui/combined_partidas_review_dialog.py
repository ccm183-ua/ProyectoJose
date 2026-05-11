"""
Diálogo final para revisar partidas históricas + IA complementaria.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from src.gui import theme


class CombinedPartidasReviewDialog(QDialog):
    def __init__(self, parent, historical_partidas=None, ai_partidas=None):
        super().__init__(parent)
        self.setWindowTitle("Revisión final de partidas")
        self._historical_partidas = historical_partidas or []
        self._ai_partidas = ai_partidas or []
        self._rows = []
        self._selected_partidas = []
        self._updating_totals = False
        self._build_rows()
        self._build_ui()
        self._populate()

    def _build_rows(self):
        for partida in self._historical_partidas:
            self._rows.append({"origin": "Histórica", "partida": dict(partida or {})})
        for partida in self._ai_partidas:
            self._rows.append({"origin": "IA complementaria", "partida": dict(partida or {})})
        self._selected = [True] * len(self._rows)

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

        self._table = QTableWidget(panel)
        self._table.setColumnCount(10)
        self._table.setHorizontalHeaderLabels(
            [
                "Usar",
                "Origen",
                "Título/Concepto",
                "Descripción",
                "Unidad",
                "Cantidad",
                "Precio",
                "Total",
                "Confianza",
                "Motivo/Fuente",
            ]
        )
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(False)
        self._table.verticalHeader().setVisible(False)
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
        self.resize(1180, 660)

    def _populate(self):
        self._table.setRowCount(len(self._rows))
        for i, row in enumerate(self._rows):
            partida = row["partida"]
            origin = row["origin"]
            concepto = str(partida.get("concepto") or partida.get("titulo") or "").strip()
            descripcion = str(partida.get("descripcion", "")).strip()
            unidad = str(partida.get("unidad", "ud")).strip()
            cantidad = float(partida.get("cantidad", 1) or 1)
            precio = float(partida.get("precio_unitario", 0) or 0)
            confianza = partida.get("confidence", "")
            motivo = partida.get("reason") or partida.get("source") or partida.get("module") or ""
            total = cantidad * precio

            self._table.setItem(i, 0, QTableWidgetItem("✓"))
            self._table.item(i, 0).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 1, QTableWidgetItem(origin))
            self._table.setItem(i, 2, QTableWidgetItem(concepto))
            self._table.setItem(i, 3, QTableWidgetItem(descripcion))
            self._table.setItem(i, 4, QTableWidgetItem(unidad))
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
        if row < 0 or row >= len(self._selected):
            return
        self._selected[row] = not self._selected[row]
        self._table.item(row, 0).setText("✓" if self._selected[row] else "")

    def _select_all(self):
        for i in range(len(self._selected)):
            self._selected[i] = True
            self._table.item(i, 0).setText("✓")

    def _select_none(self):
        for i in range(len(self._selected)):
            self._selected[i] = False
            self._table.item(i, 0).setText("")

    def _on_apply(self):
        selected = []
        for row, data in enumerate(self._rows):
            if not self._selected[row]:
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

            partida["concepto"] = concepto
            partida["titulo"] = str(partida.get("titulo") or partida["concepto"]).strip()
            partida["descripcion"] = str(self._table.item(row, 3).text() or "").strip()
            partida["unidad"] = unidad
            partida["cantidad"] = cantidad
            partida["precio_unitario"] = precio
            selected.append(partida)

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
