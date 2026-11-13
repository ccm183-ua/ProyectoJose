"""Persistencia de la planificación de obras (tabla obra_planificacion, esquema v6).

Clave: número de proyecto ("114-26"), estable al mover la carpeta de estado.
Ninguna fecha real se inventa: el primer escaneo solo anota el estado y los
cambios detectados fuera de la app se guardan como aproximados.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional

from src.core import database

STATE_INICIO = "EJECUTANDO"
STATE_FIN = "TERMINADO"

_DATE_FIELDS = ("inicio_previsto", "fin_previsto", "inicio_real", "fin_real", "avisado_en")
_BOOL_FIELDS = ("inicio_real_aproximado", "fin_real_aproximado")
_OTHER_FIELDS = ("margen_aviso_dias", "notas", "estado_conocido")
_EDITABLE = set(_DATE_FIELDS) | set(_BOOL_FIELDS) | set(_OTHER_FIELDS)
_COLUMNS = ("numero_proyecto",) + _DATE_FIELDS + _BOOL_FIELDS + _OTHER_FIELDS + ("actualizado_en",)


def _to_db(field: str, value):
    if field in _DATE_FIELDS:
        return value.isoformat() if isinstance(value, date) else (value or None)
    if field in _BOOL_FIELDS:
        return 1 if value else 0
    return value


def _parse_date(raw) -> Optional[date]:
    try:
        return date.fromisoformat(str(raw)[:10]) if raw else None
    except ValueError:
        return None


def _row_to_plan(row) -> Dict:
    plan = dict(zip(_COLUMNS, row))
    for f in _DATE_FIELDS:
        plan[f] = _parse_date(plan[f])
    for f in _BOOL_FIELDS:
        plan[f] = bool(plan[f])
    return plan


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


_CHUNK = 500  # por debajo del límite de parámetros de SQLite


def _fetch_many(conn: sqlite3.Connection, numeros: List[str]) -> Dict[str, Dict]:
    """Planes de muchos números con una consulta por bloque (no una por obra)."""
    out: Dict[str, Dict] = {}
    for i in range(0, len(numeros), _CHUNK):
        chunk = numeros[i:i + _CHUNK]
        placeholders = ",".join("?" for _ in chunk)
        rows = conn.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM obra_planificacion WHERE numero_proyecto IN ({placeholders})",
            chunk,
        ).fetchall()
        out.update({row[0]: _row_to_plan(row) for row in rows})
    return out


def get_planes(numeros: Iterable[str]) -> Dict[str, Dict]:
    """Planes existentes de los números dados (los que no tienen fila no aparecen)."""
    wanted = sorted(n for n in {str(n or "").strip() for n in numeros} if n)
    if not wanted:
        return {}
    with database.get_connection(read_only=True) as conn:
        return _fetch_many(conn, wanted)


def _upsert(conn: sqlite3.Connection, numero: str, fields: Dict) -> None:
    conn.execute(
        "INSERT INTO obra_planificacion (numero_proyecto, actualizado_en) VALUES (?, ?) "
        "ON CONFLICT(numero_proyecto) DO NOTHING",
        (numero, _now()),
    )
    if fields:
        sets = ", ".join(f"{f} = ?" for f in fields)
        conn.execute(
            f"UPDATE obra_planificacion SET {sets}, actualizado_en = ? WHERE numero_proyecto = ?",
            [_to_db(f, v) for f, v in fields.items()] + [_now(), numero],
        )


def upsert_plan(numero: str, **fields) -> Optional[str]:
    """Crea o actualiza el plan de `numero`; solo toca los campos pasados.

    Pasar `None` en una fecha la quita. Devuelve un mensaje de error o None.
    """
    numero = (numero or "").strip()
    if not numero:
        return "Falta el número de proyecto."
    unknown = set(fields) - _EDITABLE
    if unknown:
        return f"Campos no válidos: {', '.join(sorted(unknown))}"
    with database.get_connection() as conn:
        try:
            _upsert(conn, numero, fields)
            conn.commit()
            return None
        except sqlite3.Error as e:
            conn.rollback()
            return e.args[0] if e.args else "Error de base de datos."


def _state_change_fields(current: Optional[Dict], to_state: str, when: date, aproximada: bool) -> Dict:
    fields: Dict = {"estado_conocido": to_state}
    if to_state == STATE_INICIO and not (current or {}).get("inicio_real"):
        fields.update(inicio_real=when, inicio_real_aproximado=aproximada)
    if to_state == STATE_FIN and not (current or {}).get("fin_real"):
        fields.update(fin_real=when, fin_real_aproximado=aproximada)
    return fields


def _get_one(conn: sqlite3.Connection, numero: str) -> Optional[Dict]:
    row = conn.execute(
        f"SELECT {', '.join(_COLUMNS)} FROM obra_planificacion WHERE numero_proyecto = ?", (numero,)
    ).fetchone()
    return _row_to_plan(row) if row else None


def record_state_change(numero: str, to_state: str, when: date, aproximada: bool = False) -> Optional[str]:
    """La obra pasa a `to_state`: fecha real de inicio/fin si aún no la tenía.

    Volver a un estado anterior no borra fechas.
    """
    numero = (numero or "").strip()
    if not numero:
        return "Falta el número de proyecto."
    with database.get_connection() as conn:
        try:
            current = _get_one(conn, numero)
            _upsert(conn, numero, _state_change_fields(current, to_state, when, aproximada))
            conn.commit()
            return None
        except sqlite3.Error as e:
            conn.rollback()
            return e.args[0] if e.args else "Error de base de datos."


def reconcile_scan(numeros_por_estado: Dict[str, List[str]], hoy: date) -> Optional[str]:
    """Detecta obras que cambiaron de estado fuera de la app desde el último escaneo.

    - Números vacíos o repetidos (en cualquier estado) se ignoran.
    - Sin fila o sin estado conocido: solo se anota el estado (no se inventan fechas).
    - Estado distinto del conocido: transición con la fecha del escaneo, aproximada.
    """
    conteo = Counter(n.strip() for ns in numeros_por_estado.values() for n in ns if n and n.strip())
    unicos = sorted(n for n, c in conteo.items() if c == 1)
    with database.get_connection() as conn:
        try:
            existentes = _fetch_many(conn, unicos)
            for estado, numeros in numeros_por_estado.items():
                for numero in {n.strip() for n in numeros if n and n.strip()}:
                    if conteo[numero] != 1:
                        continue
                    current = existentes.get(numero)
                    known = (current or {}).get("estado_conocido")
                    if not known:
                        _upsert(conn, numero, {"estado_conocido": estado})
                    elif known != estado:
                        _upsert(conn, numero, _state_change_fields(current, estado, hoy, True))
            conn.commit()
            return None
        except sqlite3.Error as e:
            conn.rollback()
            return e.args[0] if e.args else "Error de base de datos."
