"""
CRUD del dominio canonico de presupuestos (H3): budget, budget_version,
budget_line, evidence, field_evidence, document, approval.

Invariantes garantizadas aqui, no por cada llamador:
- Un budget nunca existe sin version activa (create_budget_with_first_version
  es la unica forma de crear uno).
- Como maximo una version no-'superseded' por budget: start_new_version hace
  crear+supersede+repuntar en una sola transaccion.
- budget_line es inmutable: no hay update_line, solo lineas nuevas en una
  version nueva.
"""

import sqlite3
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.core import database
from src.core.budget_math import IVA_RATE, calcular_importe_linea, calcular_totales
from src.core.repositories._common import _mensaje_integridad

_VALID_EVIDENCE_TIPOS = {"historical", "catalog", "ai_estimate", "web", "manual", "legacy_excel"}
_VALID_FIELD_EVIDENCE_CAMPOS = {"precio", "cantidad", "concepto"}
_VALID_DOCUMENT_TIPOS = {"excel_import", "excel_export", "pdf_export"}


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _row_to_budget(r) -> Dict:
    return {
        "id": r[0],
        "uuid": r[1],
        "nombre_proyecto": r[2] or "",
        "numero_proyecto": r[3] or "",
        "presupuesto_legacy_id": r[4],
        "estado": r[5] or "",
        "active_version_id": r[6],
        "created_at": r[7] or "",
        "updated_at": r[8] or "",
    }


_BUDGET_SELECT = (
    "SELECT id, uuid, nombre_proyecto, numero_proyecto, presupuesto_legacy_id, "
    "estado, active_version_id, created_at, updated_at FROM budget"
)


def _row_to_version(r) -> Dict:
    return {
        "id": r[0],
        "budget_id": r[1],
        "numero_version": r[2],
        "estado": r[3] or "",
        "origen": r[4] or "",
        "subtotal": r[5],
        "iva": r[6],
        "iva_rate": r[7],
        "total": r[8],
        "superseded_by_version_id": r[9],
        "reconciliation_warnings_json": r[10] or "",
        "created_at": r[11] or "",
        "approved_at": r[12] or "",
        "superseded_at": r[13] or "",
    }


_VERSION_SELECT = (
    "SELECT id, budget_id, numero_version, estado, origen, subtotal, iva, iva_rate, total, "
    "superseded_by_version_id, reconciliation_warnings_json, created_at, approved_at, superseded_at "
    "FROM budget_version"
)


def _row_to_line(r) -> Dict:
    return {
        "id": r[0],
        "budget_version_id": r[1],
        "line_uid": r[2],
        "orden": r[3],
        "numero": r[4] or "",
        "concepto": r[5] or "",
        "unidad": r[6] or "",
        "cantidad": r[7],
        "precio": r[8],
        "importe": r[9],
        "source": r[10] or "",
        "created_at": r[11] or "",
    }


def _insert_version_and_lines(
    conn: sqlite3.Connection,
    budget_id: int,
    numero_version: int,
    lines: List[Dict],
    origen: str,
    iva_rate: float,
    estado: str,
    now: str,
    reconciliation_warnings_json: Optional[str] = None,
) -> int:
    """Inserta budget_version + sus budget_line en la conexion/transaccion actual.

    No hace commit ni maneja excepciones: lo hace el llamador, que envuelve
    la operacion completa (crear budget, o supersede+nueva version).
    """
    computed = []
    for line in lines or []:
        cantidad = float(line.get("cantidad") or 0)
        precio = float(line.get("precio") or 0)
        computed.append({
            "orden": line.get("orden"),
            "numero": line.get("numero"),
            "concepto": (line.get("concepto") or "").strip(),
            "unidad": line.get("unidad"),
            "cantidad": cantidad,
            "precio": precio,
            "importe": calcular_importe_linea(cantidad, precio),
            "source": (line.get("source") or "unknown").strip() or "unknown",
        })

    totales = calcular_totales((l["importe"] for l in computed), iva_rate=iva_rate)

    cur = conn.execute(
        """INSERT INTO budget_version
           (budget_id, numero_version, estado, origen, subtotal, iva, iva_rate, total,
            reconciliation_warnings_json, created_at, approved_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            budget_id, numero_version, estado, origen,
            totales["subtotal"], totales["iva"], iva_rate, totales["total"],
            reconciliation_warnings_json, now, now if estado == "approved" else None,
        ),
    )
    version_id = cur.lastrowid

    for idx, line in enumerate(computed):
        orden = line["orden"]
        if orden is None:
            orden = idx + 1
        conn.execute(
            """INSERT INTO budget_line
               (budget_version_id, line_uid, orden, numero, concepto, unidad,
                cantidad, precio, importe, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                version_id, str(uuid.uuid4()), orden,
                (line["numero"] or None), line["concepto"], (line["unidad"] or None),
                line["cantidad"], line["precio"], line["importe"], line["source"], now,
            ),
        )
    return version_id


def create_budget_with_first_version(
    nombre_proyecto: str,
    lines: List[Dict],
    numero_proyecto: str = "",
    presupuesto_legacy_id: Optional[int] = None,
    iva_rate: float = IVA_RATE,
    estado_inicial: str = "draft",
    reconciliation_warnings_json: Optional[str] = None,
) -> Tuple[Optional[int], Optional[str]]:
    """Crea un budget y su primera version (numero_version=1) en una unica
    transaccion. Unica forma de crear un budget: nunca queda con
    active_version_id sin resolver."""
    if not (nombre_proyecto or "").strip():
        return None, "El nombre del proyecto es obligatorio."
    if estado_inicial not in ("draft", "approved"):
        return None, f"Estado inicial no valido: {estado_inicial}."

    now = _now_str()
    with database.get_connection() as conn:
        try:
            budget_uuid = str(uuid.uuid4())
            cur = conn.execute(
                """INSERT INTO budget
                   (uuid, nombre_proyecto, numero_proyecto, presupuesto_legacy_id,
                    estado, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    budget_uuid, nombre_proyecto.strip(),
                    (numero_proyecto or "").strip() or None,
                    presupuesto_legacy_id, estado_inicial, now, now,
                ),
            )
            budget_id = cur.lastrowid

            version_id = _insert_version_and_lines(
                conn, budget_id, 1, lines, "import", iva_rate, estado_inicial, now,
                reconciliation_warnings_json,
            )
            conn.execute(
                "UPDATE budget SET active_version_id=? WHERE id=?", (version_id, budget_id)
            )
            conn.commit()
            return budget_id, None
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return None, _mensaje_integridad(e)
        except sqlite3.OperationalError as e:
            conn.rollback()
            return None, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def start_new_version(
    budget_id: int,
    lines: List[Dict],
    origen: str = "manual_edit",
    iva_rate: Optional[float] = None,
) -> Tuple[Optional[int], Optional[str]]:
    """Crea una version nueva (siempre 'draft') que reemplaza la activa:
    marca la anterior 'superseded' y repunta active_version_id, en una
    unica transaccion."""
    if origen not in ("import", "manual_edit", "ai_edit"):
        return None, f"origen no valido: {origen}."

    now = _now_str()
    with database.get_connection() as conn:
        try:
            row = conn.execute(
                "SELECT active_version_id FROM budget WHERE id=?", (budget_id,)
            ).fetchone()
            if not row:
                return None, "No se encontro el budget indicado."
            active_version_id = row[0]

            effective_iva_rate = iva_rate
            if effective_iva_rate is None:
                effective_iva_rate = IVA_RATE
                if active_version_id:
                    prev = conn.execute(
                        "SELECT iva_rate FROM budget_version WHERE id=?", (active_version_id,)
                    ).fetchone()
                    if prev and prev[0] is not None:
                        effective_iva_rate = prev[0]

            max_row = conn.execute(
                "SELECT COALESCE(MAX(numero_version), 0) FROM budget_version WHERE budget_id=?",
                (budget_id,),
            ).fetchone()
            numero_version = int((max_row[0] if max_row else 0) or 0) + 1

            version_id = _insert_version_and_lines(
                conn, budget_id, numero_version, lines, origen, effective_iva_rate, "draft", now,
            )

            if active_version_id:
                conn.execute(
                    """UPDATE budget_version
                       SET estado='superseded', superseded_at=?, superseded_by_version_id=?
                       WHERE id=?""",
                    (now, version_id, active_version_id),
                )
            conn.execute(
                "UPDATE budget SET active_version_id=?, estado='draft', updated_at=? WHERE id=?",
                (version_id, now, budget_id),
            )
            conn.commit()
            return version_id, None
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return None, _mensaje_integridad(e)
        except sqlite3.OperationalError as e:
            conn.rollback()
            return None, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def approve_active_version(
    budget_id: int, aprobado_por: str, nota: str = "",
) -> Tuple[bool, Optional[str]]:
    """Transiciona draft -> approved y crea la fila de approval. Rechaza con
    un mensaje de negocio (no una excepcion de integridad confusa) si la
    version activa ya no esta en draft."""
    if not (aprobado_por or "").strip():
        return False, "aprobado_por es obligatorio."

    now = _now_str()
    with database.get_connection() as conn:
        try:
            row = conn.execute(
                "SELECT active_version_id FROM budget WHERE id=?", (budget_id,)
            ).fetchone()
            if not row:
                return False, "No se encontro el budget indicado."
            version_id = row[0]
            if not version_id:
                return False, "El budget no tiene version activa."

            version_row = conn.execute(
                "SELECT estado FROM budget_version WHERE id=?", (version_id,)
            ).fetchone()
            estado_actual = version_row[0] if version_row else None
            if estado_actual != "draft":
                return False, (
                    "Solo se puede aprobar una version en borrador "
                    f"(estado actual: {estado_actual or 'desconocido'})."
                )

            conn.execute(
                "UPDATE budget_version SET estado='approved', approved_at=? WHERE id=?",
                (now, version_id),
            )
            conn.execute(
                "UPDATE budget SET estado='approved', updated_at=? WHERE id=?",
                (now, budget_id),
            )
            conn.execute(
                """INSERT INTO approval (budget_version_id, aprobado_por, aprobado_at, nota)
                   VALUES (?, ?, ?, ?)""",
                (version_id, aprobado_por.strip(), now, (nota or "").strip() or None),
            )
            conn.commit()
            return True, None
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return False, _mensaje_integridad(e)
        except sqlite3.OperationalError as e:
            conn.rollback()
            return False, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def get_budget(budget_id: int) -> Optional[Dict]:
    with database.get_connection() as conn:
        row = conn.execute(f"{_BUDGET_SELECT} WHERE id=?", (budget_id,)).fetchone()
    return _row_to_budget(row) if row else None


def get_budget_by_legacy_id(presupuesto_legacy_id: int) -> Optional[Dict]:
    with database.get_connection() as conn:
        row = conn.execute(
            f"{_BUDGET_SELECT} WHERE presupuesto_legacy_id=?", (presupuesto_legacy_id,)
        ).fetchone()
    return _row_to_budget(row) if row else None


def get_active_version(budget_id: int) -> Optional[Dict]:
    with database.get_connection() as conn:
        row = conn.execute(
            """SELECT bv.id, bv.budget_id, bv.numero_version, bv.estado, bv.origen, bv.subtotal,
                      bv.iva, bv.iva_rate, bv.total, bv.superseded_by_version_id,
                      bv.reconciliation_warnings_json, bv.created_at, bv.approved_at, bv.superseded_at
               FROM budget_version bv
               JOIN budget b ON b.active_version_id = bv.id
               WHERE b.id=?""",
            (budget_id,),
        ).fetchone()
    return _row_to_version(row) if row else None


def list_versions(budget_id: int) -> List[Dict]:
    with database.get_connection() as conn:
        rows = conn.execute(
            f"{_VERSION_SELECT} WHERE budget_id=? ORDER BY numero_version ASC", (budget_id,)
        ).fetchall()
    return [_row_to_version(r) for r in rows]


def get_lines(budget_version_id: int) -> List[Dict]:
    with database.get_connection() as conn:
        rows = conn.execute(
            """SELECT id, budget_version_id, line_uid, orden, numero, concepto, unidad,
                      cantidad, precio, importe, source, created_at
               FROM budget_line WHERE budget_version_id=? ORDER BY orden ASC""",
            (budget_version_id,),
        ).fetchall()
    return [_row_to_line(r) for r in rows]


def record_evidence(
    tipo_fuente: str, referencia: str = "", modelo_herramienta: str = "", resumen: str = "",
) -> Tuple[Optional[int], Optional[str]]:
    if tipo_fuente not in _VALID_EVIDENCE_TIPOS:
        return None, f"tipo_fuente no valido: {tipo_fuente}."
    now = _now_str()
    with database.get_connection() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO evidence
                   (uuid, tipo_fuente, referencia, fecha_consulta, modelo_herramienta, resumen, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()), tipo_fuente, (referencia or "").strip() or None, now,
                    (modelo_herramienta or "").strip() or None, (resumen or "").strip() or None, now,
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


def link_field_evidence(budget_line_id: int, campo: str, evidence_id: int) -> Optional[str]:
    if campo not in _VALID_FIELD_EVIDENCE_CAMPOS:
        return f"campo no valido: {campo}."
    now = _now_str()
    with database.get_connection() as conn:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO field_evidence (budget_line_id, campo, evidence_id, created_at)
                   VALUES (?, ?, ?, ?)""",
                (budget_line_id, campo, evidence_id, now),
            )
            conn.commit()
            return None
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return _mensaje_integridad(e)
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def register_document(
    budget_version_id: int,
    tipo: str,
    ruta: str,
    hash_sha256: Optional[str] = None,
    tamano_bytes: Optional[int] = None,
) -> Tuple[Optional[int], Optional[str]]:
    if tipo not in _VALID_DOCUMENT_TIPOS:
        return None, f"tipo de documento no valido: {tipo}."
    if not (ruta or "").strip():
        return None, "La ruta del documento es obligatoria."
    now = _now_str()
    with database.get_connection() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO document (budget_version_id, tipo, ruta, hash_sha256, tamano_bytes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (budget_version_id, tipo, ruta.strip(), hash_sha256, tamano_bytes, now),
            )
            conn.commit()
            return cur.lastrowid, None
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return None, _mensaje_integridad(e)
        except sqlite3.OperationalError as e:
            conn.rollback()
            return None, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."
