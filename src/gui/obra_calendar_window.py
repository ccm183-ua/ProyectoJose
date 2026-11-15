"""Ventana «Calendario de obras» (pieza C).

Mes en cuadrícula con las etiquetas de inicio y fin de cada obra, la lista
«Sin fecha» y una franja de resumen. Las fechas previstas se ponen y se
mueven arrastrando, sin preguntar y con Deshacer. Diseño:
docs/superpowers/specs/2026-11-15-calendario-obras-design.md.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import date
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QMimeData, Qt, QTimer
from PySide6.QtGui import QDrag, QFontMetrics, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QTextBrowser,
    QToolButton, QVBoxLayout, QWidget,
)

from src.core import obra_calendar as oc
from src.core.obra_calendar_service import CalendarData, load_calendar_data, refresh_planning
from src.core.obra_planning_service import planning_key
from src.gui import planning_events, theme
from src.gui.widgets.toast import show_toast
from src.utils.helpers import run_in_background

logger = logging.getLogger(__name__)

MIME_OBRA = "application/x-cubiapp-obra"
_TITULO = "Calendario de obras"
_DIAS = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
_AVISO_VACIA = "No hay obras cargadas. Abre «Presupuestos existentes» una vez para cargarlas."

# Franja de color a la izquierda de cada etiqueta: la fase de la obra.
FASE_COLOR = {
    "EJECUTAR": theme.INFO,
    "EJECUTANDO": theme.SUCCESS,
    "TERMINADO": theme.TEXT_TERTIARY,
}
_COLOR_TEXTO = {"warning": "#92400e", "late": "#b91c1c"}
_COLOR_BORDE = {"warning": theme.WARNING, "late": theme.ERROR}
_FONDO_AVISO = {"warning": theme.WARNING_BG, "late": theme.ERROR_BG}

HELP_HTML = f"""
<h3 style="margin-top:0">Cómo usar el calendario</h3>
<p><b>Poner una fecha.</b> Arrastra una obra de la lista «Sin fecha» a un día:
ese día pasa a ser su inicio previsto. Si la carpeta ya lleva una fecha en el
nombre («EJECUTAR EL 13-07-26»), el botón «Poner esta fecha» la guarda.</p>
<p><b>Mover una fecha.</b> Arrastra la etiqueta ▶ (inicio previsto) o ■ (fin
previsto) a otro día. Al mover el inicio, el fin previsto se desplaza los mismos
días.</p>
<p><b>Quitar la fecha.</b> Arrastra la etiqueta ▶ de vuelta a «Sin fecha», o clic
derecho → «Quitar fechas previstas».</p>
<p><b>Deshacer.</b> Cada cambio muestra un aviso abajo con el botón «Deshacer».</p>
<p><b>Fechas reales.</b> Las etiquetas con relleno son fechas que ya pasaron de
verdad (la obra empezó o terminó). No se arrastran; se corrigen con doble clic.</p>
<p><b>Doble clic</b> en una etiqueta: ventana de planificación (fechas, margen de
aviso y notas). <b>Clic derecho</b>: abrir el Excel o la carpeta de la obra.</p>
<h4>Qué significa cada cosa</h4>
<ul>
<li>▶ inicio · ■ fin previsto · ✓ obra terminada · ≈ fecha aproximada</li>
<li>Borde discontinuo: fecha prevista · relleno: fecha real</li>
<li>Franja de la izquierda: <span style="color:{theme.INFO}"><b>azul</b></span> EJECUTAR,
<span style="color:{theme.SUCCESS}"><b>verde</b></span> EJECUTANDO,
<span style="color:{theme.TEXT_TERTIARY}"><b>gris</b></span> TERMINADO</li>
<li><span style="color:#92400e"><b>Ámbar</b></span>: empieza dentro del margen de aviso ·
<span style="color:#b91c1c"><b>rojo</b></span>: el inicio ya pasó y sigue en EJECUTAR, o va con retraso</li>
</ul>
<h4>Teclado</h4>
<p>RePág / AvPág: mes anterior / siguiente · Inicio: volver a hoy ·
F5: volver a leer las obras · F1: esta ayuda.</p>
<p style="color:{theme.TEXT_SECONDARY}">Las obras salen de la última carga de
«Presupuestos existentes». Si has movido carpetas fuera de la app, pulsa allí
«⟳ Actualizar» y el calendario se pondrá al día solo.</p>
"""


def _encode(numero: str, fase: str, tipo: str) -> bytes:
    return f"{numero}|{fase}|{tipo}".encode("utf-8")


def _decode(raw) -> Optional[Tuple[str, str, str]]:
    partes = bytes(raw).decode("utf-8", errors="replace").split("|")
    return (partes[0], partes[1], partes[2]) if len(partes) == 3 else None


def _margen_general() -> int:
    try:
        from src.core.settings import Settings

        return Settings().get_obra_margen_aviso_dias()
    except Exception:
        return 7


def _chip_style(ev: oc.CalendarEvent) -> str:
    franja = FASE_COLOR.get(ev.fase, theme.TEXT_TERTIARY)
    if ev.real:
        return (f"QLabel{{background:{theme.BG_SECONDARY};color:{theme.TEXT_PRIMARY};"
                f"border:1px solid {theme.BORDER_DEFAULT};border-left:4px solid {franja};"
                "border-radius:4px;padding:1px 4px;font-size:12px;}")
    borde = _COLOR_BORDE.get(ev.color, theme.BORDER_DEFAULT)
    texto = _COLOR_TEXTO.get(ev.color, theme.TEXT_PRIMARY)
    fondo = _FONDO_AVISO.get(ev.color, theme.BG_CARD)
    return (f"QLabel{{background:{fondo};color:{texto};border:1px dashed {borde};"
            f"border-left:4px solid {franja};border-radius:4px;padding:1px 4px;font-size:12px;}}")


def _caption(text: str, parent=None) -> QLabel:
    label = QLabel(text, parent)
    label.setWordWrap(True)
    label.setStyleSheet(f"color:{theme.TEXT_SECONDARY};background:transparent;font-size:12px;")
    return label


class _DragSource:
    """Mezcla: arrastra `_payload` (número, fase, tipo) al mover con el botón pulsado."""

    _payload: Optional[Tuple[str, str, str]] = None
    _press_pos = None

    def _drag_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()

    def _drag_move(self, event) -> bool:
        if not self._payload or self._press_pos is None:
            return False
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return False
        if (event.position().toPoint() - self._press_pos).manhattanLength() < QApplication.startDragDistance():
            return False
        mime = QMimeData()
        mime.setData(MIME_OBRA, _encode(*self._payload))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        self._press_pos = None
        drag.exec(Qt.DropAction.MoveAction)
        return True


class _EventChip(QLabel, _DragSource):
    """Etiqueta de una obra en un día. El texto se recorta con «…» según el ancho."""

    def __init__(self, window: "ObraCalendarWindow", event: oc.CalendarEvent, parent=None):
        super().__init__(event.texto, parent)
        self._window = window
        self.calendar_event = event  # no `self.event`: taparía QWidget.event() y la app se cierra de golpe
        self._full_text = event.texto
        self._payload = (event.numero, event.fase, event.tipo) if event.arrastrable else None
        self.setToolTip(event.ayuda)
        self.setStyleSheet(_chip_style(event))
        # Que el texto largo no ensanche la columna: se recorta en resizeEvent.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(20)
        self.setCursor(Qt.CursorShape.OpenHandCursor if event.arrastrable else Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: window.build_menu(event.numero).exec(self.mapToGlobal(pos))
        )

    def full_text(self) -> str:
        return self._full_text

    def resizeEvent(self, e):
        super().resizeEvent(e)
        disponible = max(0, self.contentsRect().width() - 2)
        self.setText(self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight, disponible))

    def mousePressEvent(self, e):
        self._drag_press(e)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not self._drag_move(e):
            super().mouseMoveEvent(e)

    def mouseDoubleClickEvent(self, e):
        self._window.edit_planning(self.calendar_event.numero)


class _DayCell(QFrame):
    def __init__(self, window: "ObraCalendarWindow", dia: date, en_mes: bool, es_hoy: bool,
                 eventos: List[oc.CalendarEvent], parent=None):
        super().__init__(parent)
        self._window = window
        self.dia = dia
        self.en_mes = en_mes
        self.es_hoy = es_hoy
        self.highlighted = False
        self.setObjectName("dayCell")
        self.setAcceptDrops(en_mes)
        self.setMinimumSize(110, 96)
        self._apply_style()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(5, 3, 5, 3)
        lay.setSpacing(2)
        numero = QLabel(str(dia.day), self)
        if es_hoy:
            numero.setStyleSheet(
                f"color:{theme.TEXT_INVERSE};background:{theme.ACCENT_PRIMARY};border-radius:9px;"
                "font-weight:bold;padding:0 5px;"
            )
            numero.setToolTip("Hoy")
        else:
            color = theme.TEXT_PRIMARY if en_mes else theme.BORDER_DEFAULT
            numero.setStyleSheet(f"color:{color};background:transparent;font-weight:600;")
        fila = QHBoxLayout()
        fila.setContentsMargins(0, 0, 0, 0)
        fila.addWidget(numero)
        fila.addStretch(1)
        lay.addLayout(fila)
        self.chips: List[_EventChip] = []
        self.more_button: Optional[QToolButton] = None
        if en_mes:
            for ev in eventos[: oc.MAX_ETIQUETAS_DIA]:
                chip = _EventChip(window, ev, self)
                lay.addWidget(chip)
                self.chips.append(chip)
            if len(eventos) > oc.MAX_ETIQUETAS_DIA:
                btn = QToolButton(self)
                btn.setText(f"+{len(eventos) - oc.MAX_ETIQUETAS_DIA} más")
                btn.setToolTip("Ver todas las obras de este día")
                btn.setAutoRaise(True)
                btn.setStyleSheet(f"color:{theme.ACCENT_DARK};font-size:12px;")
                btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                btn.setMenu(window.build_day_menu(eventos, btn))
                lay.addWidget(btn)
                self.more_button = btn
        lay.addStretch(1)

    def _apply_style(self) -> None:
        if not self.en_mes:
            fondo, borde, ancho = theme.BG_PRIMARY, theme.BORDER_LIGHT, 1
        elif self.dia.weekday() >= 5:
            fondo, borde, ancho = theme.BG_SECONDARY, theme.BORDER_LIGHT, 1
        else:
            fondo, borde, ancho = theme.BG_CARD, theme.BORDER_LIGHT, 1
        if self.es_hoy:
            borde, ancho = theme.ACCENT_PRIMARY, 2
        if self.highlighted:
            fondo, borde, ancho = theme.ACCENT_LIGHT, theme.ACCENT_PRIMARY, 2
        self.setStyleSheet(f"#dayCell{{background:{fondo};border:{ancho}px solid {borde};border-radius:6px;}}")

    def _set_highlight(self, on: bool) -> None:
        if self.highlighted != on:
            self.highlighted = on
            self._apply_style()

    def dragEnterEvent(self, e):
        if self.en_mes and e.mimeData().hasFormat(MIME_OBRA):
            e.acceptProposedAction()
            self._set_highlight(True)
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if self.en_mes and e.mimeData().hasFormat(MIME_OBRA):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self._set_highlight(False)

    def dropEvent(self, e):
        self._set_highlight(False)
        payload = _decode(e.mimeData().data(MIME_OBRA).data())
        if not payload:
            e.ignore()
            return
        e.acceptProposedAction()
        dia, window = self.dia, self._window
        # Después de que termine el arrastre: guardar repinta y borra esta celda.
        QTimer.singleShot(0, lambda: window.drop_on_day(*payload, dia))


class _UnscheduledRow(QFrame, _DragSource):
    """Obra sin fecha: número en negrita y el nombre completo debajo (en varias líneas)."""

    def __init__(self, window: "ObraCalendarWindow", item: Dict, parent=None):
        super().__init__(parent)
        self._window = window
        self.numero = item["numero"]
        self.search_text = f"{item['numero']} {item.get('nombre', '')}".lower()
        self._payload = (item["numero"], "EJECUTAR", "inicio")
        self.setObjectName("sinFechaRow")
        self.setStyleSheet(
            f"#sinFechaRow{{background:{theme.BG_CARD};border:1px solid {theme.BORDER_LIGHT};"
            f"border-left:4px solid {FASE_COLOR['EJECUTAR']};border-radius:6px;}}"
            f"#sinFechaRow:hover{{border-color:{theme.ACCENT_PRIMARY};}}"
        )
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(f"{item['ayuda']}\nArrastra a un día para poner el inicio previsto · doble clic para editar")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 5, 8, 6)
        lay.setSpacing(2)
        titulo = QLabel(item["numero"], self)
        titulo.setStyleSheet(f"font-weight:bold;color:{theme.TEXT_PRIMARY};background:transparent;")
        lay.addWidget(titulo)
        nombre = QLabel(item.get("nombre") or item["texto"], self)
        nombre.setWordWrap(True)
        nombre.setStyleSheet(f"color:{theme.TEXT_PRIMARY};background:transparent;font-size:12px;")
        lay.addWidget(nombre)
        self.proposal_button: Optional[QPushButton] = None
        if item["propuesta"]:
            propuesta = QLabel(item["propuesta_texto"], self)
            propuesta.setStyleSheet(f"font-style:italic;color:{theme.TEXT_SECONDARY};background:transparent;font-size:12px;")
            lay.addWidget(propuesta)
            btn = QPushButton("Poner esta fecha", self)
            btn.setToolTip("Guarda la fecha del nombre de la carpeta como inicio previsto")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            numero = self.numero
            btn.clicked.connect(lambda: window.put_proposal(numero))
            fila = QHBoxLayout()
            fila.setContentsMargins(0, 2, 0, 0)
            fila.addWidget(btn)
            fila.addStretch(1)
            lay.addLayout(fila)
            self.proposal_button = btn
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: window.build_menu(self.numero).exec(self.mapToGlobal(pos))
        )

    def mousePressEvent(self, e):
        self._drag_press(e)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not self._drag_move(e):
            super().mouseMoveEvent(e)

    def mouseDoubleClickEvent(self, e):
        self._window.edit_planning(self.numero)


class _UnscheduledPanel(QFrame):
    def __init__(self, window: "ObraCalendarWindow", parent=None):
        super().__init__(parent)
        self._window = window
        self.highlighted = False
        self.setObjectName("sinFechaPanel")
        self.setAcceptDrops(True)
        self.setFixedWidth(330)
        self._apply_style()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(6)
        self.title = QLabel("Sin fecha (0)", self)
        self.title.setStyleSheet(f"font-weight:bold;font-size:14px;color:{theme.TEXT_PRIMARY};background:transparent;")
        lay.addWidget(self.title)
        lay.addWidget(_caption("Arrastra una obra a un día para ponerle fecha, o una etiqueta ▶ aquí para quitarla.", self))
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Buscar obra…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_filter)
        lay.addWidget(self.search)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("sinFechaLista")
        inner.setStyleSheet("#sinFechaLista{background:transparent;}")
        self._list = QVBoxLayout(inner)
        self._list.setContentsMargins(0, 0, 4, 0)
        self._list.setSpacing(6)
        self._list.addStretch(1)
        scroll.setWidget(inner)
        scroll.viewport().setStyleSheet("background:transparent;")
        self._inner = inner
        lay.addWidget(scroll, 1)
        self.empty_label = _caption("", self)
        self.empty_label.hide()
        lay.addWidget(self.empty_label)
        self.rows: List[_UnscheduledRow] = []

    def _apply_style(self) -> None:
        fondo = theme.ACCENT_LIGHT if self.highlighted else theme.BG_PRIMARY
        borde = theme.ACCENT_PRIMARY if self.highlighted else theme.BORDER_LIGHT
        self.setStyleSheet(f"#sinFechaPanel{{background:{fondo};border:1px solid {borde};border-radius:8px;}}")

    def _set_highlight(self, on: bool) -> None:
        if self.highlighted != on:
            self.highlighted = on
            self._apply_style()

    def set_items(self, items: List[Dict]) -> None:
        for row in self.rows:
            self._list.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.rows = []
        for i, item in enumerate(items):
            row = _UnscheduledRow(self._window, item, self._inner)
            self._list.insertWidget(i, row)
            self.rows.append(row)
        self.title.setText(f"Sin fecha ({len(items)})")
        self._apply_filter()

    def visible_numeros(self) -> List[str]:
        return [r.numero for r in self.rows if not r.isHidden()]

    def _apply_filter(self) -> None:
        texto = self.search.text().strip().lower()
        visibles = 0
        for row in self.rows:
            mostrar = not texto or texto in row.search_text
            row.setVisible(mostrar)
            visibles += mostrar
        if not self.rows:
            mensaje = "Todas las obras de EJECUTAR tienen fecha."
        elif not visibles:
            mensaje = "Ninguna obra coincide con la búsqueda."
        else:
            mensaje = ""
        self.empty_label.setText(mensaje)
        self.empty_label.setVisible(bool(mensaje))

    def _accepts(self, e) -> bool:
        if not e.mimeData().hasFormat(MIME_OBRA):
            return False
        payload = _decode(e.mimeData().data(MIME_OBRA).data())
        return bool(payload and payload[1] == "EJECUTAR" and payload[2] == "inicio")

    def dragEnterEvent(self, e):
        if self._accepts(e):
            e.acceptProposedAction()
            self._set_highlight(True)
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if self._accepts(e):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragLeaveEvent(self, e):
        self._set_highlight(False)

    def dropEvent(self, e):
        self._set_highlight(False)
        payload = _decode(e.mimeData().data(MIME_OBRA).data())
        if not payload:
            e.ignore()
            return
        e.acceptProposedAction()
        window = self._window
        QTimer.singleShot(0, lambda: window.drop_on_unscheduled(*payload))


class _HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{_TITULO} · Ayuda")
        self.resize(560, 560)
        lay = QVBoxLayout(self)
        texto = QTextBrowser(self)
        texto.setHtml(HELP_HTML)
        texto.setOpenLinks(False)
        lay.addWidget(texto)
        botones = QDialogButtonBox(self)
        cerrar = botones.addButton("Cerrar", QDialogButtonBox.ButtonRole.RejectRole)
        cerrar.setDefault(True)
        botones.rejected.connect(self.reject)
        lay.addWidget(botones)


def _legend(parent=None) -> QWidget:
    """Leyenda fija bajo el calendario."""
    host = QWidget(parent)
    lay = QHBoxLayout(host)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)

    def muestra(texto: str, estilo: str, ayuda: str) -> None:
        label = QLabel(texto, host)
        label.setStyleSheet(f"QLabel{{{estilo}border-radius:4px;padding:1px 6px;font-size:12px;}}")
        label.setToolTip(ayuda)
        lay.addWidget(label)

    prevista = f"background:{theme.BG_CARD};color:{theme.TEXT_PRIMARY};border:1px dashed {theme.BORDER_DEFAULT};"
    real = f"background:{theme.BG_SECONDARY};color:{theme.TEXT_PRIMARY};border:1px solid {theme.BORDER_DEFAULT};"
    muestra("▶ inicio · ■ fin previsto", prevista + f"border-left:4px solid {theme.INFO};",
            "Fecha prevista (borde discontinuo): se puede arrastrar")
    muestra("✓ terminada", real + f"border-left:4px solid {theme.TEXT_TERTIARY};",
            "Fecha real (relleno): no se arrastra; se corrige con doble clic")
    for fase, color in FASE_COLOR.items():
        muestra(fase.capitalize(), f"background:transparent;color:{theme.TEXT_SECONDARY};"
                f"border:none;border-left:4px solid {color};", f"Franja de color: obra en {fase}")
    muestra("Empieza pronto", f"background:{theme.WARNING_BG};color:{_COLOR_TEXTO['warning']};"
            f"border:1px dashed {theme.WARNING};", "Empieza dentro del margen de aviso")
    muestra("Pasada / con retraso", f"background:{theme.ERROR_BG};color:{_COLOR_TEXTO['late']};"
            f"border:1px dashed {theme.ERROR};", "El inicio ya pasó y sigue en EJECUTAR, o el fin previsto ya pasó")
    lay.addStretch(1)
    return host


class ObraCalendarWindow(QWidget):
    def __init__(self, parent=None, hoy: Optional[date] = None, autoload: bool = True):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(_TITULO)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(1200, 760)
        self._hoy = hoy or date.today()
        self._year, self._month = self._hoy.year, self._hoy.month
        self._data = CalendarData()
        self._eventos: List[oc.CalendarEvent] = []
        self._rows_by_numero: Dict[str, Tuple[str, Dict]] = {}
        self._cells: List[_DayCell] = []
        self._margen = _margen_general()
        self._loading = False
        self._build_ui()
        self._build_shortcuts()
        eventos = planning_events.planning_events()
        eventos.planning_changed.connect(self._on_planning_changed)
        eventos.obras_reloaded.connect(self._on_obras_reloaded)
        self._render()
        if autoload:
            self.reload()

    # ── Interfaz ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setObjectName("obraCalendar")
        self.setStyleSheet(f"#obraCalendar{{background:{theme.BG_PRIMARY};}}")
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 10)
        root.setSpacing(8)

        cabecera = QHBoxLayout()
        cabecera.setSpacing(6)
        self._btn_prev = QToolButton(self)
        self._btn_prev.setText("◀")
        self._btn_prev.setToolTip("Mes anterior (RePág)")
        self._btn_prev.clicked.connect(self.go_prev)
        self.month_label = QLabel(self)
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.month_label.setFont(theme.get_font_bold(16))
        self.month_label.setStyleSheet(f"color:{theme.TEXT_PRIMARY};background:transparent;")
        # Ancho fijo (el del mes más largo): las flechas no se mueven al cambiar de mes.
        metricas = QFontMetrics(self.month_label.font())
        ancho = max(metricas.horizontalAdvance(oc.month_title(2000, m)) for m in range(1, 13))
        self.month_label.setFixedWidth(ancho + 24)
        self._btn_next = QToolButton(self)
        self._btn_next.setText("▶")
        self._btn_next.setToolTip("Mes siguiente (AvPág)")
        self._btn_next.clicked.connect(self.go_next)
        for btn in (self._btn_prev, self._btn_next):
            btn.setFixedSize(34, 30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_today = QPushButton("Hoy", self)
        self._btn_today.setToolTip("Volver al mes actual (Inicio)")
        self._btn_today.clicked.connect(self.go_today)
        self._btn_help = QPushButton("? Ayuda", self)
        self._btn_help.setToolTip("Cómo se ponen y se mueven las fechas (F1)")
        self._btn_help.clicked.connect(self.show_help)
        self._btn_reload = QPushButton("⟳ Volver a leer", self)
        self._btn_reload.setToolTip(
            "Vuelve a leer las obras y su planificación (F5).\n"
            "Para detectar carpetas movidas fuera de la app, actualiza «Presupuestos existentes»."
        )
        self._btn_reload.clicked.connect(self.reload)
        for w in (self._btn_prev, self.month_label, self._btn_next):
            cabecera.addWidget(w)
        cabecera.addSpacing(6)
        cabecera.addWidget(self._btn_today)
        cabecera.addStretch(1)
        cabecera.addWidget(self._btn_reload)
        cabecera.addWidget(self._btn_help)
        root.addLayout(cabecera)

        # Resumen del mes en tarjetas.
        self._summary_host = QWidget(self)
        self._summary_layout = QHBoxLayout(self._summary_host)
        self._summary_layout.setContentsMargins(0, 0, 0, 0)
        self._summary_layout.setSpacing(6)
        self.summary_cards: List[QLabel] = []
        root.addWidget(self._summary_host)

        self.message_label = QLabel("", self)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(
            f"color:#92400e;background:{theme.WARNING_BG};border:1px solid {theme.WARNING};"
            "border-radius:6px;padding:6px 10px;"
        )
        self.message_label.hide()
        root.addWidget(self.message_label)

        cuerpo = QHBoxLayout()
        cuerpo.setSpacing(12)
        izquierda = QVBoxLayout()
        izquierda.setSpacing(6)
        grid_host = QWidget(self)
        self._grid = QGridLayout(grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(4)
        for c, nombre in enumerate(_DIAS):
            cab = QLabel(nombre, grid_host)
            cab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            color = theme.TEXT_TERTIARY if c >= 5 else theme.TEXT_SECONDARY
            cab.setStyleSheet(f"color:{color};background:transparent;font-weight:600;padding:2px;")
            self._grid.addWidget(cab, 0, c)
            self._grid.setColumnStretch(c, 1)
        izquierda.addWidget(grid_host, 1)
        izquierda.addWidget(_legend(self))
        cuerpo.addLayout(izquierda, 1)
        self.unscheduled_panel = _UnscheduledPanel(self, self)
        cuerpo.addWidget(self.unscheduled_panel)
        root.addLayout(cuerpo, 1)

        self.footer_label = _caption("", self)
        root.addWidget(self.footer_label)

    def _build_shortcuts(self) -> None:
        atajos = (
            (Qt.Key.Key_PageUp, self.go_prev),
            (Qt.Key.Key_PageDown, self.go_next),
            (Qt.Key.Key_Home, self.go_today),
            (Qt.Key.Key_F5, self.reload),
            (Qt.Key.Key_F1, self.show_help),
        )
        self._shortcuts = []
        for tecla, accion in atajos:
            atajo = QShortcut(QKeySequence(tecla), self)
            atajo.activated.connect(accion)
            self._shortcuts.append(atajo)

    def show_help(self) -> None:
        _HelpDialog(self).exec()

    def _render_summary(self) -> None:
        while self._summary_layout.count():  # tarjetas y el hueco final de la vez anterior
            item = self._summary_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().deleteLater()
        self.summary_cards = []
        resumen = oc.month_summary(self._eventos, self._year, self._month)
        for texto, tono in oc.summary_parts(resumen):
            card = QLabel(texto[:1].upper() + texto[1:], self._summary_host)
            if tono == "late":
                estilo = f"color:{_COLOR_TEXTO['late']};background:{theme.ERROR_BG};border:1px solid #fecaca;"
            elif tono == "muted":
                estilo = f"color:{theme.TEXT_TERTIARY};background:{theme.BG_CARD};border:1px solid {theme.BORDER_LIGHT};"
            else:
                estilo = f"color:{theme.TEXT_PRIMARY};background:{theme.BG_CARD};border:1px solid {theme.BORDER_LIGHT};"
            card.setStyleSheet(f"QLabel{{{estilo}border-radius:10px;padding:3px 10px;font-size:12px;}}")
            self._summary_layout.addWidget(card)
            self.summary_cards.append(card)
        self._summary_layout.addStretch(1)
        self._summary_host.setToolTip(oc.summary_text(resumen) + "\n(Retrasos: a día de hoy, en cualquier mes.)")

    def _render(self) -> None:
        self.month_label.setText(oc.month_title(self._year, self._month))
        self._btn_today.setEnabled((self._year, self._month) != (self._hoy.year, self._hoy.month))
        self._render_summary()
        mensaje = self._data.error or (_AVISO_VACIA if self._data.vacia else "")
        self.message_label.setText(mensaje)
        self.message_label.setVisible(bool(mensaje))

        for cell in self._cells:
            self._grid.removeWidget(cell)
            cell.hide()  # deleteLater no es inmediato: que no se vea la casilla vieja
            cell.deleteLater()
        self._cells = []
        por_dia = oc.events_by_day(self._eventos)
        host = self._grid.parentWidget()
        semanas = oc.month_weeks(self._year, self._month)
        for r, semana in enumerate(semanas, start=1):
            self._grid.setRowStretch(r, 1)
            for c, dia in enumerate(semana):
                cell = _DayCell(self, dia, dia.month == self._month, dia == self._hoy, por_dia.get(dia, []), host)
                self._grid.addWidget(cell, r, c)
                self._cells.append(cell)
        for r in range(len(semanas) + 1, 7):
            self._grid.setRowStretch(r, 0)

        self.unscheduled_panel.set_items(oc.unscheduled(self._data.filas_por_estado.get("EJECUTAR", [])))
        n = self._data.repetidas
        if n == 1:
            self.footer_label.setText("1 obra con número repetido, no se puede planificar")
        elif n > 1:
            self.footer_label.setText(f"{n} obras con número repetido, no se pueden planificar")
        else:
            self.footer_label.setText("")

    # ── Datos ────────────────────────────────────────────────────────────

    def reload(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._btn_reload.setEnabled(False)
        hoy = self._hoy

        def _done(ok, payload):
            self._loading = False
            try:
                self._btn_reload.setEnabled(True)
            except RuntimeError:
                return  # la ventana se cerró mientras cargaba
            if not ok:
                logger.error("No se pudieron cargar las obras del calendario: %s", payload)
                self.set_data(CalendarData(error=f"No se pudieron cargar las obras: {payload}"))
                return
            self.set_data(payload)

        run_in_background(lambda: load_calendar_data(hoy), _done)

    def set_data(self, data: CalendarData) -> None:
        self._data = data
        self._index()
        self._render()

    def _index(self) -> None:
        self._rows_by_numero = {}
        for fase, rows in self._data.filas_por_estado.items():
            for row in rows:
                numero = planning_key(row)
                if numero and not row.get("planificacion_duplicado"):
                    self._rows_by_numero[numero] = (fase, row)
        self._eventos = oc.build_events(self._data.filas_por_estado, self._hoy, self._margen)

    def _row(self, numero: str) -> Tuple[Optional[str], Optional[Dict]]:
        return self._rows_by_numero.get(numero, (None, None))

    def _plan(self, numero: str) -> Dict:
        return (self._row(numero)[1] or {}).get("planificacion") or {}

    # ── Navegación y consultas (también para los tests) ───────────────────

    def go_prev(self) -> None:
        self._year, self._month = (self._year - 1, 12) if self._month == 1 else (self._year, self._month - 1)
        self._render()

    def go_next(self) -> None:
        self._year, self._month = (self._year + 1, 1) if self._month == 12 else (self._year, self._month + 1)
        self._render()

    def go_today(self) -> None:
        self._year, self._month = self._hoy.year, self._hoy.month
        self._render()

    def cell_for(self, dia: date) -> Optional[_DayCell]:
        return next((c for c in self._cells if c.dia == dia), None)

    def unscheduled_numeros(self) -> List[str]:
        return [r.numero for r in self.unscheduled_panel.rows]

    # ── Acciones ─────────────────────────────────────────────────────────

    def drop_on_day(self, numero: str, fase: str, tipo: str, dia: date) -> None:
        fase_actual, row = self._row(numero)
        if row is None:
            return
        plan = self._plan(numero)
        campos, motivo = oc.drop_fields(plan, fase_actual, tipo, dia)
        if campos is None:
            if motivo:
                show_toast(self, motivo)
            return
        if tipo == "inicio":
            verbo = "movido al" if plan.get("inicio_previsto") else "el"
            mensaje = f"{numero}: inicio previsto {verbo} {dia:%d/%m}"
        else:
            mensaje = f"{numero}: fin previsto el {dia:%d/%m}"
        self._save(numero, campos, mensaje)

    def drop_on_unscheduled(self, numero: str, fase: str, tipo: str) -> None:
        fase_actual, row = self._row(numero)
        if row is None or fase_actual != "EJECUTAR" or tipo != "inicio":
            return
        if not self._plan(numero).get("inicio_previsto"):
            return
        self.clear_planned(numero)

    def clear_planned(self, numero: str) -> None:
        campos = oc.clear_fields(self._plan(numero))
        if campos:
            self._save(numero, campos, f"{numero}: fechas previstas quitadas")

    def put_proposal(self, numero: str) -> None:
        propuesta = (self._row(numero)[1] or {}).get("planificacion_propuesta")
        if not propuesta:
            return
        self._save(numero, oc.proposal_fields(self._plan(numero), propuesta),
                   f"{numero}: inicio previsto el {propuesta[0]:%d/%m}")

    def edit_planning(self, numero: str) -> None:
        from src.gui import obra_planning_dialog

        fase, row = self._row(numero)
        if row is None:
            return
        dlg = obra_planning_dialog.ObraPlanningDialog(
            self, titulo=oc.folder_name(row) or numero, plan=self._plan(numero),
            margen_general=self._margen, propuesta=row.get("planificacion_propuesta"),
        )
        if dlg.exec() != 1 or dlg.get_changes() is None:
            return
        self._save(numero, dlg.get_changes(), f"{numero}: planificación guardada")

    def _save(self, numero: str, campos: Dict, mensaje: str) -> None:
        from src.core.repositories import obra_planificacion_repository as repo

        try:
            snapshot = repo.get_planes([numero]).get(numero)
        except Exception as exc:
            QMessageBox.critical(self, _TITULO, f"No se pudo leer la planificación de {numero}:\n{exc}")
            return
        err = repo.upsert_plan(numero, **campos)
        if err:
            QMessageBox.critical(self, _TITULO, f"No se pudo guardar {numero}:\n{err}")
            self._render()
            return
        self._after_change([numero])
        show_toast(self, mensaje, [("Deshacer", lambda: self._undo(numero, snapshot))])

    def _undo(self, numero: str, snapshot: Optional[Dict]) -> None:
        from src.core.repositories import obra_planificacion_repository as repo

        err = repo.restore_plan_snapshot(numero, snapshot)
        if err:
            QMessageBox.critical(self, _TITULO, f"No se pudo deshacer {numero}:\n{err}")
            return
        self._after_change([numero])
        show_toast(self, f"{numero}: cambio deshecho")

    def _after_change(self, numeros: List[str]) -> None:
        try:
            refresh_planning(self._data.filas_por_estado, numeros)
        except Exception:
            logger.exception("No se pudo releer la planificación de %s", numeros)
        self._index()
        self._render()
        planning_events.notify_planning_changed(numeros, source=self)

    # ── Menús y abrir ficheros ───────────────────────────────────────────

    def build_menu(self, numero: str, parent=None) -> QMenu:
        menu = QMenu(parent or self)
        row = self._row(numero)[1] or {}
        menu.addAction("Planificación…").triggered.connect(lambda: self.edit_planning(numero))
        menu.addAction("Abrir Excel").triggered.connect(
            lambda: self._open_path(row.get("ruta_excel", ""), "El archivo Excel ya no existe."))
        menu.addAction("Abrir carpeta").triggered.connect(
            lambda: self._open_path(row.get("ruta_carpeta", ""), "La carpeta ya no existe."))
        menu.addSeparator()
        quitar = menu.addAction("Quitar fechas previstas")
        quitar.triggered.connect(lambda: self.clear_planned(numero))
        quitar.setEnabled(oc.clear_fields(self._plan(numero)) is not None)
        return menu

    def build_day_menu(self, eventos: List[oc.CalendarEvent], parent) -> QMenu:
        menu = QMenu(parent)
        for ev in eventos:
            sub = self.build_menu(ev.numero, menu)
            sub.setTitle(ev.texto)
            menu.addMenu(sub)
        return menu

    def _open_path(self, path: str, missing: str) -> None:
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, _TITULO, missing)
            return
        path = os.path.normpath(path)
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=True)
            else:
                subprocess.run(["xdg-open", path], check=True)
        except Exception as exc:
            QMessageBox.critical(self, _TITULO, f"No se pudo abrir:\n{path}\n\nError: {exc}")

    # ── Avisos de otras ventanas ─────────────────────────────────────────

    def _on_planning_changed(self, numeros, source) -> None:
        if source is self:
            return
        try:
            refresh_planning(self._data.filas_por_estado, numeros)
        except Exception:
            logger.exception("No se pudo releer la planificación de %s", numeros)
            return
        self._index()
        self._render()

    def _on_obras_reloaded(self, source) -> None:
        if source is not self:
            self.reload()

    def closeEvent(self, event):
        eventos = planning_events.planning_events()
        for senal, slot in ((eventos.planning_changed, self._on_planning_changed),
                            (eventos.obras_reloaded, self._on_obras_reloaded)):
            try:
                senal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        super().closeEvent(event)
