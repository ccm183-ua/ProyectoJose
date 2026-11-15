"""Datos del calendario de obras (sin Qt): caché del dashboard + planificación.

No escanea carpetas: usa lo que dejó la última recarga del dashboard. Para
detectar obras movidas fuera de la app hay que actualizar el dashboard.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Iterable, List

from src.core.obra_calendar import FASES
from src.core.obra_planning import date_from_folder_name
from src.core.obra_planning_service import enrich_with_planning, folder_name, planning_key

logger = logging.getLogger(__name__)

ERROR_LECTURA = "No se pudo leer la planificación: las obras se muestran sin fechas."


@dataclass
class CalendarData:
    filas_por_estado: Dict[str, List[Dict]] = field(default_factory=dict)
    repetidas: int = 0
    error: str = ""
    vacia: bool = False


def load_calendar_data(hoy: date) -> CalendarData:
    from src.core.repositories import presupuesto_cache_repository as cache_repo

    data: Dict[str, List[Dict]] = {}
    for cached in cache_repo.get_all_presupuestos_cache():
        estado = (cached.get("estado") or "").strip().upper()
        if not estado:
            continue
        row = dict(cached)
        row.setdefault("numero", row.get("numero_proyecto", ""))
        data.setdefault(estado, []).append(row)

    error = ""
    try:
        # Todas las fases cuentan para detectar números repetidos, como en el dashboard.
        enrich_with_planning(data, hoy, reconcile=False)
    except Exception:
        logger.exception("No se pudo leer la planificación para el calendario")
        error = ERROR_LECTURA
        for fase in FASES:
            for row in data.get(fase, []):
                row["planificacion"] = {}
                row["planificacion_duplicado"] = False
                row["planificacion_propuesta"] = None

    filas = {fase: data.get(fase, []) for fase in FASES}
    repetidas = sum(1 for rows in filas.values() for r in rows if r.get("planificacion_duplicado"))
    return CalendarData(filas, repetidas, error, vacia=not any(filas.values()))


def refresh_planning(filas_por_estado: Dict[str, List[Dict]], numeros: Iterable[str]) -> None:
    """Relee el plan de `numeros` y recalcula su propuesta (tras guardar o deshacer)."""
    from src.core.repositories.obra_planificacion_repository import get_planes

    wanted = {n for n in numeros if n}
    if not wanted:
        return
    planes = get_planes(wanted)
    for fase, rows in filas_por_estado.items():
        for row in rows:
            numero = planning_key(row)
            if row.get("planificacion_duplicado") or numero not in wanted:
                continue
            row["planificacion"] = planes.get(numero, {})
            propuesta = None
            if fase == "EJECUTAR" and not row["planificacion"].get("inicio_previsto"):
                propuesta = date_from_folder_name(folder_name(row))
            row["planificacion_propuesta"] = propuesta
