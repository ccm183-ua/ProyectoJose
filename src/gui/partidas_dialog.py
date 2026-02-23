"""
Diálogo de revisión de partidas sugeridas por la IA.

Muestra las partidas generadas en una tabla donde el usuario puede:
- Seleccionar/deseleccionar partidas con doble clic
- Aplicar las seleccionadas al presupuesto
- Cancelar sin añadir partidas
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.gui import theme


class SuggestedPartidasDialog(QDialog):
    """Diálogo para revisar y seleccionar partidas sugeridas."""

    def __init__(self, parent, result):
        super().__init__(parent)
        self.setWindowTitle("Partidas Sugeridas")

        self._partidas = result.get('partidas', [])
        self._source = result.get('source', 'ia')
        self._selected_partidas = []
        self._selected = [True] * len(self._partidas)

        self._build_ui()
        self._populate_list()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        title = theme.create_title(panel, "Partidas Sugeridas", "xl")
        layout.addWidget(title)

        source_layout = QHBoxLayout()
        if self._source == 'ia':
            source_label = "Generado con IA"
            source_color = theme.SUCCESS
        else:
            source_label = "Desde plantilla offline"
            source_color = theme.WARNING

        source_text = QLabel(source_label, panel)
        source_text.setFont(theme.font_sm())
        source_text.setStyleSheet(f"color: {source_color}; background: transparent;")
        source_layout.addWidget(source_text)
        source_layout.addSpacing(theme.SPACE_LG)

        count_text = QLabel(f"{len(self._partidas)} partidas generadas", panel)
        count_text.setFont(theme.font_sm())
        count_text.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; background: transparent;")
        source_layout.addWidget(count_text)
        source_layout.addStretch()
        layout.addLayout(source_layout)

        warning_layout = QHBoxLayout()
        warning_icon = QLabel("ℹ", panel)
        warning_icon.setFont(theme.font_lg())
        warning_icon.setStyleSheet(f"color: {theme.ACCENT_PRIMARY}; background: transparent;")
        warning_layout.addWidget(warning_icon)

        warning_text = theme.create_text(
            panel, "Los precios son orientativos. Revise y ajuste antes de enviar al cliente.",
        )
        warning_layout.addWidget(warning_text, 1)
        layout.addSpacing(theme.SPACE_SM)
        layout.addLayout(warning_layout)
        layout.addSpacing(theme.SPACE_MD)

        self._table = QTableWidget(panel)
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["", "Concepto", "Cantidad", "Unidad", "Precio Unit.", "Importe"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 30)
        self._table.setColumnWidth(2, 80)
        self._table.setColumnWidth(3, 70)
        self._table.setColumnWidth(4, 100)
        self._table.setColumnWidth(5, 100)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_item_toggle)
        layout.addWidget(self._table, 1)

        sel_layout = QHBoxLayout()
        for text, handler in [
            ("Seleccionar todas", self._on_select_all),
            ("Deseleccionar todas", self._on_deselect_all),
            ("Invertir selección", self._on_toggle_selection),
        ]:
            btn = QPushButton(text, panel)
            btn.setFont(theme.font_sm())
            btn.setFixedHeight(34)
            btn.clicked.connect(handler)
            sel_layout.addWidget(btn)
        sel_layout.addStretch()
        layout.addSpacing(theme.SPACE_SM)
        layout.addLayout(sel_layout)

        layout.addSpacing(theme.SPACE_MD)
        layout.addWidget(theme.create_divider(panel))
        layout.addSpacing(theme.SPACE_MD)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancelar", panel)
        btn_cancel.setFont(theme.font_base())
        btn_cancel.setFixedSize(120, 44)
        btn_cancel.setToolTip("Crear presupuesto sin partidas")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addSpacing(theme.SPACE_MD)

        btn_apply = QPushButton("Aplicar seleccionadas", panel)
        btn_apply.setFont(theme.get_font_medium())
        btn_apply.setFixedSize(200, 44)
        btn_apply.setProperty("class", "primary")
        btn_apply.setDefault(True)
        btn_apply.clicked.connect(self._on_apply)
        btn_layout.addWidget(btn_apply)

        layout.addLayout(btn_layout)

        main_layout.addWidget(panel)

        self.setMinimumSize(780, 520)
        self.resize(820, 600)

    def _populate_list(self):
        self._table.setRowCount(len(self._partidas))
        for i, partida in enumerate(self._partidas):
            cantidad = partida.get('cantidad', 1)
            precio = partida.get('precio_unitario', 0)
            importe = cantidad * precio

            titulo = partida.get('titulo', '')
            descripcion = partida.get('descripcion', '')
            if titulo and descripcion:
                display_text = f"{titulo} - {descripcion}"
            elif titulo:
                display_text = titulo
            else:
                display_text = str(partida.get('concepto', ''))

            check_item = QTableWidgetItem("✓")
            check_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 0, check_item)
            self._table.setItem(i, 1, QTableWidgetItem(display_text))
            self._table.setItem(i, 2, QTableWidgetItem(str(cantidad)))
            self._table.setItem(i, 3, QTableWidgetItem(str(partida.get('unidad', 'ud'))))

            price_item = QTableWidgetItem(f"{precio:.2f} €")
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 4, price_item)

            total_item = QTableWidgetItem(f"{importe:.2f} €")
            total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 5, total_item)

    def _on_item_toggle(self, index):
        idx = index.row()
        if 0 <= idx < len(self._selected):
            self._selected[idx] = not self._selected[idx]
            self._update_check_mark(idx)

    def _update_check_mark(self, idx):
        mark = "✓" if self._selected[idx] else ""
        item = self._table.item(idx, 0)
        if item:
            item.setText(mark)

    def _on_select_all(self):
        for i in range(len(self._selected)):
            self._selected[i] = True
            self._update_check_mark(i)

    def _on_deselect_all(self):
        for i in range(len(self._selected)):
            self._selected[i] = False
            self._update_check_mark(i)

    def _on_toggle_selection(self):
        for i in range(len(self._selected)):
            self._selected[i] = not self._selected[i]
            self._update_check_mark(i)

    def _on_apply(self):
        self._selected_partidas = []
        for i, partida in enumerate(self._partidas):
            if i < len(self._selected) and self._selected[i]:
                self._selected_partidas.append(partida)

        if not self._selected_partidas:
            resp = QMessageBox.question(
                self, "Sin selección",
                "No hay partidas seleccionadas. ¿Desea continuar sin partidas?",
            )
            if resp != QMessageBox.StandardButton.Yes:
                return

        self.accept()

    def get_selected_partidas(self):
        return self._selected_partidas
