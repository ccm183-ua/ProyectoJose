"""
Catalogo de precios de referencia (H5): precio con origen, fecha, vigencia y
estado explicito, separado de `budget_line.precio`.

Invariante: `approve_price_reference`/`reject_price_reference` son la unica
forma de sacar una fila de `proposed`. Nada en `canonical_budget_repository`
las invoca automaticamente - aceptar una partida en un presupuesto no
aprueba su precio para reutilizacion futura.
"""

import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.core import database
from src.core.repositories._common import _mensaje_integridad

_VALID_ORIGENES = {"historical", "manual"}
_VIGENCIA_DIAS = 365


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _row_to_price_reference(r) -> Dict:
    return {
        "id": r[0], "uuid": r[1], "concepto": r[2], "unidad": r[3], "importe": r[4],
        "moneda": r[5], "impuestos_incluidos": bool(r[6]), "zona": r[7], "origen": r[8],
        "evidence_id": r[9], "estado": r[10], "fecha": r[11], "vigente_hasta": r[12],
        "created_at": r[13], "updated_at": r[14],
    }


_SELECT_COLUMNS = (
    "id, uuid, concepto, unidad, importe, moneda, impuestos_incluidos, zona, origen, "
    "evidence_id, estado, fecha, vigente_hasta, created_at, updated_at"
)


def create_price_reference(
    concepto: str,
    unidad: str,
    importe: float,
    origen: str,
    fecha: str,
    evidence_id: Optional[int] = None,
    zona: Optional[str] = None,
    impuestos_incluidos: bool = False,
    moneda: str = "EUR",
    estado: str = "proposed",
) -> Tuple[Optional[int], Optional[str]]:
    if not (concepto or "").strip():
        return None, "El concepto es obligatorio."
    if not (unidad or "").strip():
        return None, "La unidad es obligatoria."
    if importe is None or importe <= 0:
        return None, "El importe debe ser mayor que cero."
    if origen not in _VALID_ORIGENES:
        return None, f"origen no valido: {origen}."
    if not (fecha or "").strip():
        return None, "La fecha es obligatoria."
    if estado not in ("proposed", "approved", "rejected", "expired"):
        return None, f"estado no valido: {estado}."

    vigente_hasta = (
        datetime.strptime(fecha.strip()[:10], "%Y-%m-%d") + timedelta(days=_VIGENCIA_DIAS)
    ).strftime("%Y-%m-%d")
    now = _now_str()
    with database.get_connection() as conn:
        try:
            cur = conn.execute(
                f"""INSERT INTO price_reference
                    (uuid, concepto, unidad, importe, moneda, impuestos_incluidos, zona,
                     origen, evidence_id, estado, fecha, vigente_hasta, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()), concepto.strip(), unidad.strip(), importe,
                    (moneda or "EUR").strip() or "EUR", int(bool(impuestos_incluidos)),
                    (zona or "").strip() or None, origen, evidence_id, estado,
                    fecha.strip(), vigente_hasta, now, now,
                ),
            )
            conn.commit()
            return cur.lastrowid, None
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return None, _mensaje_integridad(e)
        except sqlite3.OperationalError as e:
            conn.rollback()
            return None, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def get_price_reference(price_reference_id: int) -> Optional[Dict]:
    with database.get_connection() as conn:
        row = conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM price_reference WHERE id=?", (price_reference_id,)
        ).fetchone()
    return _row_to_price_reference(row) if row else None


def list_price_references(
    concepto: Optional[str] = None, unidad: Optional[str] = None, estado: Optional[str] = None,
) -> List[Dict]:
    clauses, params = [], []
    if concepto:
        clauses.append("concepto = ?")
        params.append(concepto)
    if unidad:
        clauses.append("unidad = ?")
        params.append(unidad)
    if estado:
        clauses.append("estado = ?")
        params.append(estado)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with database.get_connection() as conn:
        rows = conn.execute(
            f"SELECT {_SELECT_COLUMNS} FROM price_reference {where} ORDER BY id ASC", params
        ).fetchall()
    return [_row_to_price_reference(r) for r in rows]


def _transition_estado(
    price_reference_id: int, nuevo_estado: str,
) -> Tuple[bool, Optional[str]]:
    now = _now_str()
    with database.get_connection() as conn:
        try:
            row = conn.execute(
                "SELECT estado FROM price_reference WHERE id=?", (price_reference_id,)
            ).fetchone()
            if not row:
                return False, "No se encontro el price_reference indicado."
            estado_actual = row[0]
            if estado_actual != "proposed":
                return False, (
                    "Solo se puede cambiar el estado de un precio en 'proposed' "
                    f"(estado actual: {estado_actual})."
                )
            conn.execute(
                "UPDATE price_reference SET estado=?, updated_at=? WHERE id=?",
                (nuevo_estado, now, price_reference_id),
            )
            conn.commit()
            return True, None
        except sqlite3.OperationalError as e:
            conn.rollback()
            return False, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def approve_price_reference(price_reference_id: int) -> Tuple[bool, Optional[str]]:
    return _transition_estado(price_reference_id, "approved")


def reject_price_reference(price_reference_id: int) -> Tuple[bool, Optional[str]]:
    return _transition_estado(price_reference_id, "rejected")


def refresh_expired_price_references() -> int:
    """Marca 'expired' las filas en proposed/approved cuya vigencia ya paso.
    Se llama a demanda (sin scheduler): antes de leer el catalogo, o desde un
    script manual periodico."""
    today = datetime.now().strftime("%Y-%m-%d")
    with database.get_connection() as conn:
        cur = conn.execute(
            """UPDATE price_reference SET estado='expired', updated_at=?
               WHERE estado IN ('proposed','approved') AND vigente_hasta < ?""",
            (_now_str(), today),
        )
        conn.commit()
        return cur.rowcount
