"""Diálogo de la biblioteca de partidas: buscar en el histórico y elegir partidas.

No escribe en el Excel ni en la BD: devuelve candidatas para la revisión.
"""

from typing import Dict, List, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.core.partida_library import (
    STATUS_LABELS, LibraryLine, PartidaLibrary, SearchResult, to_candidate,
)
from src.utils.helpers import run_in_background

_STATUS_COLORS = {"approved": "#2e7d32", "unreviewed": "#b26a00", "ineligible": "#9e9e9e"}
_GROUP_HEADERS = ["Concepto", "Unidad", "Módulo", "Precio propuesto", "Rango", "Obras", "Estado", "Fecha"]
_LINE_HEADERS = ["Obra", "Fecha", "Precio", "Estado", "Texto"]
_STATUS_COLUMN = 6


def _size_columns(table: QTableWidget, fixed: Dict[int, int], stretch: Optional[int] = None) -> None:
    """Anchos de columna: `fixed` {columna: px} ajustables a mano, `stretch` ocupa
    el espacio libre y el resto se ajusta a su contenido."""
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    for column, width in fixed.items():
        header.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(column, width)
    if stretch is not None:
        header.setSectionResizeMode(stretch, QHeaderView.ResizeMode.Stretch)
    table.setWordWrap(False)


def _money(value: float) -> str:
    """1234.5 -> '1.234,50 €' (formato español)."""
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


class PartidaLibraryDialog(QDialog):
    def __init__(self, parent=None, library: Optional[PartidaLibrary] = None):
        super().__init__(parent)
        self.setWindowTitle("Biblioteca de partidas")
        self.resize(1200, 720)
        self._library: Optional[PartidaLibrary] = library
        self._result = SearchResult([], 0)
        self._basket: List[Dict] = []
        self._accepted = False
        self._build_ui()
        if library is None:
            self._status.setText("Cargando partidas del histórico…")
            run_in_background(PartidaLibrary.load, self._on_loaded)
        else:
            self._on_loaded(True, library)

    # ── Construcción ────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)

        filtros = QHBoxLayout()
        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Buscar partida (p. ej. «bajante pvc», «imperm cubierta»)")
        # Espera 300 ms tras la última tecla antes de buscar.
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._run_search)
        self._search.textChanged.connect(lambda _t: self._timer.start())
        filtros.addWidget(self._search, 3)
        self._module = QComboBox(self)
        self._module.addItem("Todos los módulos", "")
        self._unit = QComboBox(self)
        self._unit.addItem("Todas las unidades", "")
        for u in ("p.a.", "ud", "m2", "m", "m3", "kg", "día", "?"):
            self._unit.addItem(u, u)
        self._estado = QComboBox(self)
        self._estado.addItem("Todas", "all")
        self._estado.addItem("Solo aprobadas", "approved")
        self._estado.addItem("Sin las no aptas", "no_ineligible")
        for combo in (self._module, self._unit, self._estado):
            combo.currentIndexChanged.connect(lambda _i: self._run_search())
            filtros.addWidget(combo, 1)
        lay.addLayout(filtros)

        self._status = QLabel("", self)
        lay.addWidget(self._status)

        split = QSplitter(Qt.Orientation.Vertical, self)
        self._groups = QTableWidget(0, len(_GROUP_HEADERS), split)
        self._groups.setHorizontalHeaderLabels(_GROUP_HEADERS)
        self._groups.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._groups.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        _size_columns(self._groups, fixed={0: 440})  # el concepto, ancho y ajustable
        self._groups.currentCellChanged.connect(lambda r, *_: self._show_detail(r))
        self._groups.cellDoubleClicked.connect(lambda r, _c: self.add_group_to_basket(r))

        detalle = QWidget(split)
        dlay = QVBoxLayout(detalle)
        self._warnings = QLabel("", detalle)
        self._warnings.setWordWrap(True)
        dlay.addWidget(self._warnings)
        self._lines = QTableWidget(0, len(_LINE_HEADERS), detalle)
        self._lines.setHorizontalHeaderLabels(_LINE_HEADERS)
        self._lines.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._lines.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        _size_columns(self._lines, fixed={0: 260}, stretch=len(_LINE_HEADERS) - 1)  # obra; texto completo
        dlay.addWidget(self._lines)
        botones_detalle = QHBoxLayout()
        btn_grupo = QPushButton("Añadir a la selección", detalle)
        btn_grupo.clicked.connect(lambda: self.add_group_to_basket(self._groups.currentRow()))
        btn_obra = QPushButton("Usar el precio de esta obra", detalle)
        btn_obra.clicked.connect(self._add_selected_line)
        botones_detalle.addWidget(btn_grupo)
        botones_detalle.addWidget(btn_obra)
        botones_detalle.addStretch(1)
        dlay.addLayout(botones_detalle)
        lay.addWidget(split, 1)

        cesta = QHBoxLayout()
        self._basket_list = QListWidget(self)
        self._basket_list.setMaximumHeight(110)
        cesta.addWidget(self._basket_list, 3)
        col = QVBoxLayout()
        btn_quitar = QPushButton("Quitar", self)
        btn_quitar.clicked.connect(self._remove_from_basket)
        self._basket_total = QLabel("", self)
        col.addWidget(btn_quitar)
        col.addWidget(self._basket_total)
        col.addStretch(1)
        cesta.addLayout(col, 1)
        lay.addLayout(cesta)

        acciones = QHBoxLayout()
        acciones.addStretch(1)
        btn_cancel = QPushButton("Cancelar", self)
        btn_cancel.clicked.connect(self.reject)
        self._btn_ok = QPushButton("Continuar a la revisión (0)", self)
        self._btn_ok.setProperty("class", "primary")
        self._btn_ok.setEnabled(False)
        self._btn_ok.clicked.connect(self.accept)
        acciones.addWidget(btn_cancel)
        acciones.addWidget(self._btn_ok)
        lay.addLayout(acciones)

    # ── Carga y búsqueda ────────────────────────────────────────────────

    def _on_loaded(self, ok, payload):
        try:
            self._status.text()
        except RuntimeError:  # el diálogo se cerró mientras cargaba
            return
        if not ok:
            self._library = PartidaLibrary([])
            self._status.setText(f"No se pudo cargar el histórico: {payload}")
            return
        self._library = payload
        for m in sorted({l.module for l in payload.lines if l.module}):
            self._module.addItem(m, m)
        aviso = f" ({payload.ignored} líneas ignoradas por datos incompletos)" if payload.ignored else ""
        self._status.setText(f"{len(payload.lines)} partidas con precio cargadas{aviso}. Escribe para buscar.")
        if self._search.text().strip():
            self._run_search()

    def set_query(self, text: str) -> None:
        """Busca `text` inmediatamente, sin esperar al temporizador."""
        self._search.blockSignals(True)
        self._search.setText(text)
        self._search.blockSignals(False)
        self._run_search()

    def _run_search(self):
        if self._library is None:
            return
        self._result = self._library.search(
            self._search.text(),
            module=self._module.currentData() or "",
            unit=self._unit.currentData() or "",
            status_filter=self._estado.currentData() or "all",
        )
        self._fill_groups()
        if self._result.truncated:
            self._status.setText(
                f"Se muestran {len(self._result.groups)} de {self._result.total_groups} grupos: afina la búsqueda."
            )
        elif not self._result.groups and (self._search.text().strip() or self._module.currentData()):
            self._status.setText("Sin resultados. Prueba con menos palabras o quitando filtros.")
        else:
            self._status.setText(f"{len(self._result.groups)} grupos.")

    def _fill_groups(self):
        self._groups.setRowCount(len(self._result.groups))
        for i, g in enumerate(self._result.groups):
            if g.price_min == g.price_max:
                rango = _money(g.price_min)
            else:
                rango = f"{_money(g.price_min)} – {_money(g.price_max)}"
            valores = [
                g.representative.concepto.split("\n")[0], g.unidad_canon, g.module,
                _money(g.proposed_price), rango, str(g.n_budgets), STATUS_LABELS[g.status],
                g.fecha.strftime("%d/%m/%Y") if g.fecha else "",
            ]
            for c, v in enumerate(valores):
                item = QTableWidgetItem(v)
                if c == _STATUS_COLUMN:
                    item.setForeground(QColor(_STATUS_COLORS[g.status]))
                self._groups.setItem(i, c, item)
        self._lines.setRowCount(0)
        self._warnings.setText("")

    def _show_detail(self, row: int):
        if not (0 <= row < len(self._result.groups)):
            return
        g = self._result.groups[row]
        self._warnings.setText(" · ".join(g.warnings))
        self._lines.setRowCount(len(g.lines))
        for i, l in enumerate(g.lines):
            valores = [
                l.proyecto, l.fecha.strftime("%d/%m/%Y") if l.fecha else "", _money(l.precio),
                STATUS_LABELS[l.status], l.concepto.replace("\n", " "),
            ]
            for c, v in enumerate(valores):
                self._lines.setItem(i, c, QTableWidgetItem(v))

    # ── Cesta ───────────────────────────────────────────────────────────

    def add_group_to_basket(self, row: int, line: Optional[LibraryLine] = None) -> None:
        """Añade el grupo `row` (con su precio propuesto o el de `line`) a la cesta."""
        if not (0 <= row < len(self._result.groups)):
            return
        candidata = to_candidate(self._result.groups[row], line)
        self._basket.append(candidata)
        self._basket_list.addItem(
            f"{candidata['titulo'] or candidata['concepto']} — "
            f"{_money(candidata['precio_unitario'])} / {candidata['unidad']}"
        )
        self._refresh_basket()

    def _add_selected_line(self):
        row, line_row = self._groups.currentRow(), self._lines.currentRow()
        if 0 <= row < len(self._result.groups) and 0 <= line_row < len(self._result.groups[row].lines):
            self.add_group_to_basket(row, self._result.groups[row].lines[line_row])

    def _remove_from_basket(self):
        i = self._basket_list.currentRow()
        if 0 <= i < len(self._basket):
            self._basket.pop(i)
            self._basket_list.takeItem(i)
            self._refresh_basket()

    def _refresh_basket(self):
        total = sum(c["precio_unitario"] for c in self._basket)
        self._basket_total.setText(f"{len(self._basket)} partidas · {_money(total)} (cantidad 1)")
        self._btn_ok.setText(f"Continuar a la revisión ({len(self._basket)})")
        self._btn_ok.setEnabled(bool(self._basket))

    # ── Resultado ───────────────────────────────────────────────────────

    def accept(self):
        self._accepted = True
        super().accept()

    def get_candidates(self) -> List[Dict]:
        """Partidas elegidas; vacío si el diálogo no se aceptó."""
        return list(self._basket) if self._accepted else []
