"""Barra de filtros de una pestaña de «Presupuestos existentes».

Fila 1: buscador (leading) · botón «Filtros (N)» · resumen.
Fila 2: etiquetas de los filtros activos (× para quitar) · «Limpiar filtros».
Fila 3 (plegable): cliente, administración, fechas e importes.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QCompleter, QDateEdit, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from src.core.budget_filters import BudgetFilters, filter_chips, summary_text, without
from src.gui import theme


def _norm(text: str) -> str:
    return " ".join((text or "").split()).casefold()


def _parse_amount(text: str) -> Optional[float]:
    raw = (text or "").strip().replace("€", "").replace(" ", "")
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


class BudgetFilterBar(QWidget):
    filters_changed = Signal(object)
    expanded_changed = Signal(bool)

    def __init__(self, parent=None, leading: Optional[QWidget] = None):
        super().__init__(parent)
        self._options = {"cliente": set(), "admin": set()}
        self._chip_buttons: List[QPushButton] = []
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(theme.SPACE_XS)

        top = QHBoxLayout()
        if leading is not None:
            top.addWidget(leading, 1)
        self._toggle = QPushButton("Filtros", self)
        self._toggle.setCheckable(True)
        self._toggle.setFont(theme.font_base())
        self._toggle.setToolTip("Filtrar por cliente, administración, fecha o importe")
        self._toggle.toggled.connect(self._on_toggled)
        top.addWidget(self._toggle)
        self._summary = theme.create_text(self, "", muted=True)
        top.addWidget(self._summary)
        root.addLayout(top)

        self._chips_row = QWidget(self)
        self._chips_layout = QHBoxLayout(self._chips_row)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.addStretch()
        self._clear_btn = QPushButton("Limpiar filtros", self._chips_row)
        self._clear_btn.setFlat(True)
        self._clear_btn.clicked.connect(self.clear)
        self._chips_layout.addWidget(self._clear_btn)
        self._chips_row.setVisible(False)
        root.addWidget(self._chips_row)

        self._panel = QWidget(self)
        panel = QHBoxLayout(self._panel)
        panel.setContentsMargins(0, 0, 0, 0)
        self._cliente = self._make_combo("Todos los clientes")
        self._admin = self._make_combo("Todas las administraciones")
        panel.addWidget(QLabel("Cliente", self._panel))
        panel.addWidget(self._cliente, 2)
        panel.addWidget(QLabel("Administración", self._panel))
        panel.addWidget(self._admin, 2)
        self._desde_chk, self._desde = self._make_date("Desde")
        self._hasta_chk, self._hasta = self._make_date("Hasta")
        for w in (self._desde_chk, self._desde, self._hasta_chk, self._hasta):
            panel.addWidget(w)
        panel.addWidget(QLabel("Importe", self._panel))
        self._min = self._make_amount("mín. €")
        self._max = self._make_amount("máx. €")
        panel.addWidget(self._min)
        panel.addWidget(QLabel("–", self._panel))
        panel.addWidget(self._max)
        self._panel.setVisible(False)
        root.addWidget(self._panel)

        self._refresh_admin_enabled()

    # ── construcción ────────────────────────────────────────────────
    def _make_combo(self, placeholder: str) -> QComboBox:
        combo = QComboBox(self._panel)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.lineEdit().setPlaceholderText(placeholder)
        combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        combo.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        combo.currentTextChanged.connect(self._on_combo_text)
        return combo

    def _make_date(self, label: str):
        chk = QCheckBox(label, self._panel)
        edit = QDateEdit(self._panel)
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("dd/MM/yy")
        edit.setDate(QDate.currentDate())
        edit.setEnabled(False)
        chk.toggled.connect(edit.setEnabled)
        chk.toggled.connect(lambda _=False: self._emit())
        edit.dateChanged.connect(lambda _=None, c=chk: c.isChecked() and self._emit())
        return chk, edit

    def _make_amount(self, placeholder: str) -> QLineEdit:
        edit = QLineEdit(self._panel)
        edit.setPlaceholderText(placeholder)
        edit.setMaximumWidth(110)
        edit.editingFinished.connect(self._emit)
        return edit

    # ── API ─────────────────────────────────────────────────────────
    def toggle_button(self) -> QPushButton:
        return self._toggle

    def is_expanded(self) -> bool:
        return self._toggle.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self._toggle.setChecked(bool(expanded))

    def summary(self) -> str:
        return self._summary.text()

    def set_summary(self, count: int, total: float) -> None:
        self._summary.setText(summary_text(count, total))

    def chip_labels(self) -> List[str]:
        return [b.property("chip_label") for b in self._chip_buttons]

    def filters(self) -> BudgetFilters:
        def _date(chk, edit) -> Optional[date]:
            return edit.date().toPython() if chk.isChecked() else None

        return BudgetFilters(
            cliente=self._cliente.currentText().strip(),
            administracion=self._admin.currentText().strip(),
            fecha_desde=_date(self._desde_chk, self._desde),
            fecha_hasta=_date(self._hasta_chk, self._hasta),
            importe_min=_parse_amount(self._min.text()),
            importe_max=_parse_amount(self._max.text()),
        )

    def set_filters(self, f: BudgetFilters) -> None:
        self._loading = True
        try:
            self._cliente.setCurrentText(f.cliente)
            self._admin.setCurrentText(f.administracion)
            for chk, edit, value in ((self._desde_chk, self._desde, f.fecha_desde),
                                     (self._hasta_chk, self._hasta, f.fecha_hasta)):
                chk.setChecked(value is not None)
                if value is not None:
                    edit.setDate(QDate(value.year, value.month, value.day))
            self._min.setText("" if f.importe_min is None else f"{f.importe_min:g}")
            self._max.setText("" if f.importe_max is None else f"{f.importe_max:g}")
        finally:
            self._loading = False
        self._refresh_chips(f)
        self._refresh_admin_enabled()

    def set_options(self, clientes: List[str], administraciones: List[str]) -> None:
        self._loading = True
        try:
            for combo, key, values in ((self._cliente, "cliente", clientes),
                                       (self._admin, "admin", administraciones)):
                current = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(list(values))
                combo.setCurrentText(current)
                combo.blockSignals(False)
                self._options[key] = {_norm(v) for v in values}
        finally:
            self._loading = False
        self._refresh_admin_enabled()

    def remove_chip(self, field: str) -> None:
        self.set_filters(without(self.filters(), field))
        self._emit()

    def clear(self) -> None:
        self.set_filters(BudgetFilters())
        self._emit()

    # ── internos ────────────────────────────────────────────────────
    def _on_toggled(self, checked: bool) -> None:
        self._panel.setVisible(checked)
        self.expanded_changed.emit(checked)

    def _on_combo_text(self, text: str) -> None:
        if self._loading:
            return
        key = "cliente" if self.sender() is self._cliente else "admin"
        # Mientras se teclea un nombre a medias no se filtra (dejaría la tabla vacía).
        if not text.strip() or _norm(text) in self._options[key]:
            self._emit()

    def _emit(self) -> None:
        if self._loading:
            return
        f = self.filters()
        self._refresh_chips(f)
        self.filters_changed.emit(f)

    def _refresh_admin_enabled(self) -> None:
        has = bool(self._options["admin"]) or bool(self._admin.currentText().strip())
        self._admin.setEnabled(has)
        self._admin.setToolTip("" if has else "No hay administraciones en estos presupuestos")

    def _refresh_chips(self, f: BudgetFilters) -> None:
        for btn in self._chip_buttons:
            self._chips_layout.removeWidget(btn)
            btn.deleteLater()
        self._chip_buttons = []
        for i, (field, label) in enumerate(filter_chips(f)):
            btn = QPushButton(f"{label}  ×", self._chips_row)
            btn.setProperty("chip_label", label)
            btn.setToolTip("Quitar este filtro")
            btn.clicked.connect(lambda _=False, fl=field: self.remove_chip(fl))
            self._chips_layout.insertWidget(i, btn)
            self._chip_buttons.append(btn)
        count = f.active_count()
        self._toggle.setText(f"Filtros ({count})" if count else "Filtros")
        self._chips_row.setVisible(count > 0)
