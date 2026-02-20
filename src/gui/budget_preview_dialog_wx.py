"""
Diálogo de previsualización de presupuesto (PySide6).

Muestra un resumen completo del presupuesto: datos de cabecera,
listado de partidas con importes y totales (subtotal, IVA, total).
"""

import os
import re
import subprocess
import sys

from PySide6.QtCore import Qt

_RE_OBRA_PREFIX = re.compile(r"^Obra:\s*", re.IGNORECASE)


def _clean_obra(value: str) -> str:
    cleaned = _RE_OBRA_PREFIX.sub("", value).strip()
    return cleaned.rstrip(".")
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from src.core.budget_reader import BudgetReader
from src.gui import theme
from src.utils.helpers import run_in_background


class BudgetPreviewDialog(QDialog):
    """Previsualización de un presupuesto .xlsx."""

    def __init__(self, parent, file_path):
        super().__init__(parent)
        self.setWindowTitle("Previsualización del Presupuesto")
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._file_path = file_path
        self._data = None
        self._build_ui()
        self._load_data()
        theme.fit_dialog(self, min_w=720, min_h=560)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(self._scroll_content)
        self._scroll_layout.setContentsMargins(theme.SPACE_LG, theme.SPACE_LG, theme.SPACE_LG, theme.SPACE_LG)
        self._scroll_layout.setSpacing(theme.SPACE_MD)
        self._scroll.setWidget(self._scroll_content)

        main_layout.addWidget(self._scroll, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_pdf = QPushButton("Exportar PDF", self)
        btn_pdf.setFont(theme.font_base())
        btn_pdf.clicked.connect(self._on_export_pdf)
        self._btn_pdf = btn_pdf
        btn_layout.addWidget(btn_pdf)
        btn_layout.addSpacing(theme.SPACE_SM)

        btn_open = QPushButton("Abrir Excel", self)
        btn_open.setFont(theme.font_base())
        btn_open.setProperty("class", "primary")
        btn_open.clicked.connect(self._on_open_excel)
        btn_layout.addWidget(btn_open)
        btn_layout.addSpacing(theme.SPACE_SM)

        btn_close = QPushButton("Cerrar", self)
        btn_close.setFont(theme.font_base())
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        main_layout.addLayout(btn_layout)
        main_layout.setContentsMargins(theme.SPACE_MD, 0, theme.SPACE_MD, theme.SPACE_MD)

    def _clear_scroll(self):
        while self._scroll_layout.count():
            child = self._scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _load_data(self):
        lbl_loading = theme.create_text(self._scroll_content, "Cargando presupuesto\u2026", muted=True)
        self._scroll_layout.addWidget(lbl_loading)

        def _read():
            return BudgetReader().read(self._file_path)

        def _on_done(ok, payload):
            self._clear_scroll()
            if not ok or not payload:
                lbl = theme.create_text(self._scroll_content, "No se pudo leer el presupuesto.", muted=True)
                self._scroll_layout.addWidget(lbl)
                return
            self._data = payload
            self._render_header()
            self._render_partidas()
            self._render_totals()
            self._scroll_layout.addStretch()

        run_in_background(_read, _on_done)

    @staticmethod
    def _fmt_euro(value):
        try:
            val = float(value)
        except (TypeError, ValueError):
            return "0,00 \u20AC"
        txt = f"{val:,.2f}"
        txt = txt.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{txt} \u20AC"

    @staticmethod
    def _fmt_qty(value):
        try:
            val = float(value)
        except (TypeError, ValueError):
            return "0"
        if val == int(val):
            return str(int(val))
        return f"{val:.2f}".replace(".", ",")

    def _render_header(self):
        cab = self._data["cabecera"]
        card = theme.Card(self._scroll_content, padding=theme.SPACE_MD)
        card_layout = card.get_inner_layout()

        title = theme.create_title(card, "Datos del Proyecto", "lg")
        card_layout.addWidget(title)
        card_layout.addWidget(theme.create_divider(card))

        fields = [
            ("Proyecto", cab.get("numero", "")),
            ("Fecha", cab.get("fecha", "")),
            ("Cliente", cab.get("cliente", "")),
            ("Dirección", cab.get("direccion", "")),
            ("Código Postal", cab.get("codigo_postal", "")),
            ("Obra", _clean_obra(cab.get("obra", ""))),
            ("CIF Admin.", cab.get("cif_admin", "")),
            ("Email Admin.", cab.get("email_admin", "")),
            ("Teléfono Admin.", cab.get("telefono_admin", "")),
        ]
        visible = [(l, v) for l, v in fields if v]

        for label_text, value in visible:
            row = QHBoxLayout()
            lbl = QLabel(f"{label_text}:", card)
            lbl.setFont(theme.create_font(10, theme.QFont.Weight.Medium))
            lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; background: transparent;")
            lbl.setFixedWidth(90)
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(lbl)
            row.addSpacing(8)

            val = QLabel(value, card)
            val.setFont(theme.font_base())
            val.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
            row.addWidget(val)
            row.addStretch()
            card_layout.addLayout(row)
        self._scroll_layout.addWidget(card)

    def _render_partidas(self):
        partidas = self._data["partidas"]
        if not partidas:
            return

        card = theme.Card(self._scroll_content, padding=theme.SPACE_MD)
        card_layout = card.get_inner_layout()

        title = theme.create_title(card, f"Partidas ({len(partidas)})", "lg")
        card_layout.addWidget(title)
        card_layout.addWidget(theme.create_divider(card))

        table = QTableWidget(card)
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["Num", "Concepto", "Ud", "Cant.", "Precio", "Importe"])
        table.setColumnWidth(0, 50)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(2, 45)
        table.setColumnWidth(3, 60)
        table.setColumnWidth(4, 85)
        table.setColumnWidth(5, 95)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)

        table.setRowCount(len(partidas))
        for i, p in enumerate(partidas):
            table.setItem(i, 0, QTableWidgetItem(p.get("numero", "")))
            concepto = p.get("concepto", "").replace("\n", " ").replace("&#10;", " ")
            table.setItem(i, 1, QTableWidgetItem(concepto[:100]))
            table.setItem(i, 2, QTableWidgetItem(p.get("unidad", "")))

            for col, val_str in [(3, self._fmt_qty(p.get("cantidad", 0))),
                                 (4, self._fmt_euro(p.get("precio", 0))),
                                 (5, self._fmt_euro(p.get("importe", 0)))]:
                item = QTableWidgetItem(val_str)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(i, col, item)

        list_height = min(len(partidas) * 28 + 32, 360)
        table.setFixedHeight(list_height)
        card_layout.addWidget(table)
        self._scroll_layout.addWidget(card)

    def _render_totals(self):
        card = theme.Card(self._scroll_content, padding=theme.SPACE_MD)
        card_layout = card.get_inner_layout()

        entries = [
            ("Subtotal", self._fmt_euro(self._data.get("subtotal", 0))),
            ("IVA (10%)", self._fmt_euro(self._data.get("iva", 0))),
        ]

        for label_text, value in entries:
            row = QHBoxLayout()
            lbl = QLabel(label_text, card)
            lbl.setFont(theme.font_base())
            lbl.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; background: transparent;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(lbl, 1)
            val = QLabel(value, card)
            val.setFont(theme.font_base())
            val.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(val)
            card_layout.addLayout(row)

        card_layout.addWidget(theme.create_divider(card))

        total_row = QHBoxLayout()
        lbl = QLabel("TOTAL", card)
        lbl.setFont(theme.create_font(14, theme.QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        total_row.addWidget(lbl, 1)
        val = QLabel(self._fmt_euro(self._data.get("total", 0)), card)
        val.setFont(theme.create_font(14, theme.QFont.Weight.Bold))
        val.setStyleSheet(f"color: {theme.ACCENT_PRIMARY}; background: transparent;")
        val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        total_row.addWidget(val)
        card_layout.addLayout(total_row)

        self._scroll_layout.addWidget(card)

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _on_export_pdf(self):
        from src.core.pdf_exporter import PDFExporter
        exporter = PDFExporter()
        if not exporter.is_available():
            QMessageBox.warning(
                self, "Exportar PDF",
                "Microsoft Excel no est\u00e1 disponible.\n"
                "Para exportar a PDF se necesita Excel instalado.",
            )
            return

        self._btn_pdf.setEnabled(False)
        self._btn_pdf.setText("Exportando\u2026")

        def _on_done(ok_outer, payload):
            self._btn_pdf.setEnabled(True)
            self._btn_pdf.setText("Exportar PDF")
            if not ok_outer:
                QMessageBox.critical(self, "Error", f"Error al exportar PDF:\n{payload}")
                return
            ok, result = payload
            if ok:
                resp = QMessageBox.question(
                    self, "PDF exportado",
                    f"PDF generado:\n{result}\n\n\u00bfDesea abrirlo?",
                )
                if resp == QMessageBox.StandardButton.Yes:
                    self._open_file(result)
            else:
                QMessageBox.critical(self, "Error", f"Error al exportar PDF:\n{result}")

        run_in_background(lambda: exporter.export(self._file_path), _on_done)

    def _on_open_excel(self):
        self._open_file(self._file_path)

    @staticmethod
    def _open_file(path):
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", path], check=True)
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.run(["xdg-open", path], check=True)
        except Exception as exc:
            QMessageBox.critical(
                None, "Error al abrir",
                f"No se pudo abrir:\n{path}\n\nError: {exc}",
            )
