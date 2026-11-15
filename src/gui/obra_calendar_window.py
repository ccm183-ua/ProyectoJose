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
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QMessageBox,
    QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget,
)

from src.core import obra_calendar as oc
from src.core.obra_calendar_service import CalendarData, load_calendar_data, refresh_planning
from src.core.obra_planning_service import planning_key
from src.gui import planning_events
from src.gui.widgets.toast import show_toast
from src.utils.helpers import run_in_background

logger = logging.getLogger(__name__)

MIME_OBRA = "application/x-cubiapp-obra"
_TITULO = "Calendario de obras"
_DIAS = ("L", "M", "X", "J", "V", "S", "D")
_AVISO_VACIA = "No hay obras cargadas. Abre «Presupuestos existentes» una vez para cargarlas."


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
    if ev.real:
        return ("QLabel{background:#e5e7eb;color:#111827;border:1px solid #9ca3af;"
                "border-radius:4px;padding:1px 4px;}")
    borde = {"warning": "#d97706", "late": "#dc2626"}.get(ev.color, "#6b7280")
    texto = {"warning": "#92400e", "late": "#991b1b"}.get(ev.color, "palette(text)")
    return (f"QLabel{{background:transparent;color:{texto};border:1px dashed {borde};"
            "border-radius:4px;padding:1px 4px;}")


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
    def __init__(self, window: "ObraCalendarWindow", event: oc.CalendarEvent, parent=None):
        super().__init__(event.texto, parent)
        self._window = window
        self.calendar_event = event  # no `self.event`: taparía QWidget.event() y la app se cierra de golpe
        self._payload = (event.numero, event.fase, event.tipo) if event.arrastrable else None
        self.setToolTip(event.ayuda)
        self.setStyleSheet(_chip_style(event))
        if event.arrastrable:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: window.build_menu(event.numero).exec(self.mapToGlobal(pos))
        )

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
        self.setObjectName("dayCell")
        self.setAcceptDrops(en_mes)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumSize(110, 90)
        if es_hoy:
            self.setStyleSheet("#dayCell{border:2px solid #2563eb;}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(2)
        numero = QLabel(str(dia.day), self)
        numero.setEnabled(en_mes)
        if es_hoy:
            numero.setStyleSheet("font-weight:bold;color:#2563eb;")
        lay.addWidget(numero)
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
                btn.setAutoRaise(True)
                btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                btn.setMenu(window.build_day_menu(eventos, btn))
                lay.addWidget(btn)
                self.more_button = btn
        lay.addStretch(1)

    def dragEnterEvent(self, e):
        if self.en_mes and e.mimeData().hasFormat(MIME_OBRA):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        self.dragEnterEvent(e)

    def dropEvent(self, e):
        payload = _decode(e.mimeData().data(MIME_OBRA).data())
        if not payload:
            e.ignore()
            return
        e.acceptProposedAction()
        dia, window = self.dia, self._window
        # Después de que termine el arrastre: guardar repinta y borra esta celda.
        QTimer.singleShot(0, lambda: window.drop_on_day(*payload, dia))


class _UnscheduledRow(QFrame, _DragSource):
    def __init__(self, window: "ObraCalendarWindow", item: Dict, parent=None):
        super().__init__(parent)
        self._window = window
        self.numero = item["numero"]
        self._payload = (item["numero"], "EJECUTAR", "inicio")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(f"{item['ayuda']}\nArrastra a un día para poner el inicio previsto · doble clic para editar")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)
        lay.addWidget(QLabel(item["texto"], self))
        self.proposal_button: Optional[QPushButton] = None
        if item["propuesta"]:
            fila = QHBoxLayout()
            propuesta = QLabel(item["propuesta_texto"], self)
            propuesta.setStyleSheet("font-style:italic;color:#6b7280;")
            btn = QPushButton("Poner esta fecha", self)
            numero = self.numero
            btn.clicked.connect(lambda: window.put_proposal(numero))
            fila.addWidget(propuesta, 1)
            fila.addWidget(btn)
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
        self.setAcceptDrops(True)
        self.setFixedWidth(290)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel("Sin fecha (0)", self)
        self.title.setStyleSheet("font-weight:bold;")
        lay.addWidget(self.title)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self._list = QVBoxLayout(inner)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.addStretch(1)
        scroll.setWidget(inner)
        self._inner = inner
        lay.addWidget(scroll, 1)
        pista = QLabel("Arrastra una obra a un día para ponerle fecha, o una etiqueta ▶ aquí para quitarla.", self)
        pista.setWordWrap(True)
        lay.addWidget(pista)
        self.rows: List[_UnscheduledRow] = []

    def set_items(self, items: List[Dict]) -> None:
        for row in self.rows:
            self._list.removeWidget(row)
            row.deleteLater()
        self.rows = []
        for i, item in enumerate(items):
            row = _UnscheduledRow(self._window, item, self._inner)
            self._list.insertWidget(i, row)
            self.rows.append(row)
        self.title.setText(f"Sin fecha ({len(items)})")

    def dragEnterEvent(self, e):
        payload = _decode(e.mimeData().data(MIME_OBRA).data()) if e.mimeData().hasFormat(MIME_OBRA) else None
        if payload and payload[1] == "EJECUTAR" and payload[2] == "inicio":
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        self.dragEnterEvent(e)

    def dropEvent(self, e):
        payload = _decode(e.mimeData().data(MIME_OBRA).data())
        if not payload:
            e.ignore()
            return
        e.acceptProposedAction()
        window = self._window
        QTimer.singleShot(0, lambda: window.drop_on_unscheduled(*payload))


class ObraCalendarWindow(QWidget):
    def __init__(self, parent=None, hoy: Optional[date] = None, autoload: bool = True):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(_TITULO)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(1150, 720)
        self._hoy = hoy or date.today()
        self._year, self._month = self._hoy.year, self._hoy.month
        self._data = CalendarData()
        self._eventos: List[oc.CalendarEvent] = []
        self._rows_by_numero: Dict[str, Tuple[str, Dict]] = {}
        self._cells: List[_DayCell] = []
        self._margen = _margen_general()
        self._loading = False
        self._build_ui()
        eventos = planning_events.planning_events()
        eventos.planning_changed.connect(self._on_planning_changed)
        eventos.obras_reloaded.connect(self._on_obras_reloaded)
        self._render()
        if autoload:
            self.reload()

    # ── Interfaz ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        cabecera = QHBoxLayout()
        self._btn_prev = QPushButton("◀", self)
        self._btn_prev.setToolTip("Mes anterior")
        self._btn_prev.clicked.connect(self.go_prev)
        self.month_label = QLabel(self)
        self.month_label.setStyleSheet("font-size:16px;font-weight:bold;padding:0 8px;")
        self._btn_next = QPushButton("▶", self)
        self._btn_next.setToolTip("Mes siguiente")
        self._btn_next.clicked.connect(self.go_next)
        self._btn_today = QPushButton("Hoy", self)
        self._btn_today.clicked.connect(self.go_today)
        self._btn_reload = QPushButton("⟳", self)
        self._btn_reload.setToolTip(
            "Volver a leer las obras y su planificación.\n"
            "Para detectar carpetas movidas fuera de la app, actualiza «Presupuestos existentes»."
        )
        self._btn_reload.clicked.connect(self.reload)
        for w in (self._btn_prev, self.month_label, self._btn_next, self._btn_today):
            cabecera.addWidget(w)
        cabecera.addStretch(1)
        cabecera.addWidget(self._btn_reload)
        root.addLayout(cabecera)

        self.summary_label = QLabel("", self)
        root.addWidget(self.summary_label)
        self.message_label = QLabel("", self)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("color:#b45309;")
        self.message_label.hide()
        root.addWidget(self.message_label)

        cuerpo = QHBoxLayout()
        grid_host = QWidget(self)
        self._grid = QGridLayout(grid_host)
        self._grid.setSpacing(2)
        for c, nombre in enumerate(_DIAS):
            cab = QLabel(nombre, grid_host)
            cab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(cab, 0, c)
            self._grid.setColumnStretch(c, 1)
        cuerpo.addWidget(grid_host, 1)
        self.unscheduled_panel = _UnscheduledPanel(self, self)
        cuerpo.addWidget(self.unscheduled_panel)
        root.addLayout(cuerpo, 1)

        self.footer_label = QLabel("", self)
        self.footer_label.setStyleSheet("color:#6b7280;")
        root.addWidget(self.footer_label)

    def _render(self) -> None:
        self.month_label.setText(oc.month_title(self._year, self._month))
        self.summary_label.setText(oc.summary_text(oc.month_summary(self._eventos, self._year, self._month)))
        mensaje = self._data.error or (_AVISO_VACIA if self._data.vacia else "")
        self.message_label.setText(mensaje)
        self.message_label.setVisible(bool(mensaje))

        for cell in self._cells:
            self._grid.removeWidget(cell)
            cell.deleteLater()
        self._cells = []
        por_dia = oc.events_by_day(self._eventos)
        host = self._grid.parentWidget()
        for r, semana in enumerate(oc.month_weeks(self._year, self._month), start=1):
            for c, dia in enumerate(semana):
                cell = _DayCell(self, dia, dia.month == self._month, dia == self._hoy, por_dia.get(dia, []), host)
                self._grid.addWidget(cell, r, c)
                self._cells.append(cell)

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
