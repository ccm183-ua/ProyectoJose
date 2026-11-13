"""Añade la planificación de obras a las filas del dashboard (núcleo, sin Qt).

Lo llaman tanto la recarga completa (`_load_data`) como el refresco de filas
(`_refresh_rows`), ambos en segundo plano: una consulta en bloque, nunca una
conexión por obra.
"""

from __future__ import annotations

import os
import re
from collections import Counter, defaultdict
from datetime import date
from typing import Dict, Iterable, List, Optional, Set

from src.core.obra_planning import date_from_folder_name
from src.core.repositories.obra_planificacion_repository import get_planes, reconcile_scan

PLANNING_STATES = ("EJECUTAR", "EJECUTANDO", "TERMINADO")
PROPOSAL_STATE = "EJECUTAR"


# Número al principio del nombre de la carpeta, con sufijo de subpresupuesto
# ("160-26-2"): el escáner del dashboard lo recorta a "160-26", pero para
# planificar son obras distintas.
_KEY_RE = re.compile(r"^\s*(\d+-\d+(?:-\d+)?)")


def _folder_name(row: Dict) -> str:
    carpeta = row.get("ruta_carpeta") or ""
    return os.path.basename(os.path.normpath(carpeta)) if carpeta else str(row.get("nombre_proyecto") or "")


def planning_key(row: Dict) -> str:
    """Identidad de la obra para planificar: número con sufijo del nombre de la
    carpeta; si no se puede leer, el número que da el escáner."""
    match = _KEY_RE.match(_folder_name(row))
    if match:
        return match.group(1)
    return str(row.get("numero") or "").strip()


_numero = planning_key


def enrich_with_planning(
    data: Dict[str, List[Dict]],
    hoy: date,
    reconcile: bool,
    known_duplicates: Optional[Iterable[str]] = None,
) -> Set[str]:
    """Rellena en las filas de EJECUTAR/EJECUTANDO/TERMINADO:

    - `planificacion`: el plan guardado ({} si no hay o el número no es único);
    - `planificacion_duplicado`: el número está repetido o vacío;
    - `planificacion_propuesta`: (fecha, aproximada) leída del nombre de la
      carpeta, solo en EJECUTAR y si no hay inicio previsto; si no, None.

    Con `reconcile=True` (recarga completa) antes detecta obras movidas de
    estado fuera de la app. Devuelve el conjunto de números repetidos, para
    pasarlo como `known_duplicates` al refrescar solo algunas filas.
    """
    conteo = Counter(_numero(r) for rows in data.values() for r in rows if _numero(r))
    duplicados = {n for n, c in conteo.items() if c > 1} | set(known_duplicates or ())
    ubicaciones = defaultdict(set)
    for estado, rows in data.items():
        for r in rows:
            if _numero(r) in duplicados:
                ubicaciones[_numero(r)].add(estado)

    if reconcile:
        reconcile_scan({estado: [_numero(r) for r in rows] for estado, rows in data.items()}, hoy)

    numeros = [
        _numero(r) for estado in PLANNING_STATES for r in data.get(estado, [])
        if _numero(r) and _numero(r) not in duplicados
    ]
    planes = get_planes(numeros)

    for estado in PLANNING_STATES:
        for row in data.get(estado, []):
            numero = _numero(row)
            repetido = not numero or numero in duplicados
            plan = {} if repetido else planes.get(numero, {})
            row["planificacion"] = plan
            row["planificacion_duplicado"] = repetido
            row["planificacion_duplicado_en"] = sorted(ubicaciones.get(numero, ())) if repetido else []
            propuesta = None
            if estado == PROPOSAL_STATE and not repetido and not plan.get("inicio_previsto"):
                propuesta = date_from_folder_name(_folder_name(row))
            row["planificacion_propuesta"] = propuesta
    return duplicados
