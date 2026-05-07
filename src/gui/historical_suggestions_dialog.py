"""
Diálogo para revisar sugerencias históricas de partidas.
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


class HistoricalSuggestionsDialog(QDialog):
    """Permite activar partidas históricas y ajustar cantidad/precio."""

    def __init__(self, parent, suggestion_result: dict):
        super().__init__(parent)
        self.setWindowTitle("Sugerencias históricas")
        self._result = suggestion_result or {}
        self._modules = self._result.get("detected_modules", [])
        self._partidas = self._result.get("partidas", [])
        self._selected = [
            (
                float(p.get("confidence", 0.0)) >= 0.7
                and int(p.get("historical_frequency", 0)) >= 3
            )
            for p in self._partidas
        ]
        self._selected_partidas = []
        self._build_ui()
        self._populate()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        title = theme.create_title(panel, "Sugerencias históricas", "xl")
        layout.addWidget(title)

        stats = self._result.get("stats", {})
        msg = theme.create_text(
            panel,
            f"Basado en {stats.get('partidas_base', 0)} partidas históricas asociadas a los módulos detectados.",
        )
        msg.setWordWrap(True)
        layout.addWidget(msg)

        modules_text = ", ".join(
            f"{m.get('label', m.get('name', ''))} ({int((m.get('confidence', 0) or 0) * 100)}%)"
            for m in self._modules[:6]
        )
        if modules_text:
            modules_lbl = QLabel(f"Módulos detectados: {modules_text}", panel)
            modules_lbl.setFont(theme.font_sm())
            modules_lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; background: transparent;")
            modules_lbl.setWordWrap(True)
            layout.addWidget(modules_lbl)

        self._table = QTableWidget(panel)
        self._table.setColumnCount(9)
        self._table.setHorizontalHeaderLabels(
            ["", "Módulo", "Concepto", "Cantidad", "Unidad", "Precio Unit.", "Rango €", "Frecuencia", "Conf."]
        )
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 32)
        self._table.setColumnWidth(1, 140)
        self._table.setColumnWidth(3, 85)
        self._table.setColumnWidth(4, 70)
        self._table.setColumnWidth(5, 95)
        self._table.setColumnWidth(6, 110)
        self._table.setColumnWidth(7, 80)
        self._table.setColumnWidth(8, 70)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._toggle_current_row)
        layout.addWidget(self._table, 1)

        actions = QHBoxLayout()
        btn_all = QPushButton("Seleccionar todas", panel)
        btn_all.setFont(theme.font_sm())
        btn_all.clicked.connect(self._select_all)
        actions.addWidget(btn_all)
        btn_none = QPushButton("Deseleccionar todas", panel)
        btn_none.setFont(theme.font_sm())
        btn_none.clicked.connect(self._select_none)
        actions.addWidget(btn_none)
        actions.addStretch()
        layout.addLayout(actions)

        layout.addWidget(theme.create_divider(panel))
        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_cancel = QPushButton("Saltar", panel)
        btn_cancel.setFont(theme.font_base())
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        buttons.addSpacing(8)
        btn_apply = QPushButton("Insertar seleccionadas", panel)
        btn_apply.setFont(theme.get_font_medium())
        btn_apply.setProperty("class", "primary")
        btn_apply.clicked.connect(self._on_apply)
        buttons.addWidget(btn_apply)
        layout.addLayout(buttons)

        main_layout.addWidget(panel)
        self.resize(980, 600)

    def _populate(self):
        self._table.setRowCount(len(self._partidas))
        for i, partida in enumerate(self._partidas):
            self._table.setItem(i, 0, QTableWidgetItem("✓" if self._selected[i] else ""))
            self._table.item(i, 0).setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 1, QTableWidgetItem(str(partida.get("module", ""))))
            self._table.setItem(i, 2, QTableWidgetItem(str(partida.get("concepto", ""))))

            qty_item = QTableWidgetItem(str(partida.get("cantidad", 1)))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 3, qty_item)

            self._table.setItem(i, 4, QTableWidgetItem(str(partida.get("unidad", "ud"))))

            price_item = QTableWidgetItem(str(partida.get("precio_unitario", 0.0)))
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 5, price_item)

            rango_min = float(partida.get("precio_min", 0.0))
            rango_max = float(partida.get("precio_max", 0.0))
            rango_item = QTableWidgetItem(f"{rango_min:.2f}-{rango_max:.2f}")
            rango_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 6, rango_item)

            freq_item = QTableWidgetItem(str(partida.get("historical_frequency", 0)))
            freq_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 7, freq_item)

            conf = float(partida.get("confidence", 0.0))
            conf_item = QTableWidgetItem(f"{int(conf * 100)}%")
            conf_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 8, conf_item)

        # Solo cantidad y precio son editables
        for row in range(self._table.rowCount()):
            for col in (3, 5):
                item = self._table.item(row, col)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

    def _toggle_current_row(self):
        row = self._table.currentRow()
        if row < 0:
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
        for row, partida in enumerate(self._partidas):
            if not self._selected[row]:
                continue
            try:
                cantidad = float((self._table.item(row, 3).text() or "1").replace(",", "."))
                precio = float((self._table.item(row, 5).text() or "0").replace(",", "."))
            except ValueError:
                QMessageBox.warning(
                    self, "Valor inválido", "Cantidad y precio deben ser numéricos."
                )
                return

            concepto = str(partida.get("concepto", "")).strip()
            titulo = str(partida.get("titulo", "")).strip() or concepto.upper()
            descripcion = str(partida.get("descripcion", "")).strip()
            selected.append(
                {
                    "titulo": titulo,
                    "descripcion": descripcion,
                    "concepto": concepto,
                    "cantidad": cantidad,
                    "unidad": str(partida.get("unidad", "ud")),
                    "precio_unitario": precio,
                }
            )
        self._selected_partidas = selected
        self.accept()

    def get_selected_partidas(self):
        return self._selected_partidas
