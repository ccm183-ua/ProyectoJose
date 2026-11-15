"""Aviso interno «la planificación ha cambiado» entre dashboard y calendario.

- `planning_changed(numeros, emisor)`: se guardaron fechas de esas obras; quien
  la recibe relee solo su planificación (sin escanear carpetas).
- `obras_reloaded(emisor)`: el dashboard terminó una recarga completa (pudo
  mover obras de fase); el calendario se recarga entero.

Cada ventana ignora lo que emitió ella misma.
"""

from __future__ import annotations

from typing import Iterable, Optional

from PySide6.QtCore import QObject, Signal


class _PlanningEvents(QObject):
    planning_changed = Signal(object, object)
    obras_reloaded = Signal(object)


_instance: Optional[_PlanningEvents] = None


def planning_events() -> _PlanningEvents:
    global _instance
    if _instance is None:
        _instance = _PlanningEvents()
    return _instance


def notify_planning_changed(numeros: Iterable[str], source=None) -> None:
    planning_events().planning_changed.emit(list(numeros), source)


def notify_obras_reloaded(source=None) -> None:
    planning_events().obras_reloaded.emit(source)
