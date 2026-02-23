"""
CRUD de cache de presupuestos (tabla presupuesto).
"""

import sqlite3
from typing import Dict, List, Optional, Tuple

from src.core import database
from src.core.repositories._common import _mensaje_integridad


def _row_to_presupuesto_cache(r) -> Dict:
    """Convierte una fila de la tabla presupuesto a dict."""
    return {
        "id": r[0],
        "numero_proyecto": r[1] or "",
        "nombre_proyecto": r[2] or "",
        "ruta_excel": r[3] or "",
        "ruta_carpeta": r[4] or "",
        "estado": r[5] or "",
        "cliente": r[6] or "",
        "localidad": r[7] or "",
        "tipo_obra": r[8] or "",
        "fecha": r[9] or "",
        "total": r[10],
        "subtotal": r[11],
        "iva": r[12],
        "obra_descripcion": r[13] or "",
        "cif_admin": r[14] or "",
        "email_admin": r[15] or "",
        "telefono_admin": r[16] or "",
        "codigo_postal": r[17] or "",
        "comunidad_id": r[18],
        "administracion_id": r[19],
        "fecha_modificacion_excel": r[20] or "",
        "fecha_cache": r[21] or "",
        "datos_completos": bool(r[22]),
    }


_PRESUPUESTO_COLS = (
    "id, numero_proyecto, nombre_proyecto, ruta_excel, ruta_carpeta, "
    "estado, cliente, localidad, tipo_obra, fecha, total, subtotal, iva, "
    "obra_descripcion, cif_admin, email_admin, telefono_admin, codigo_postal, "
    "comunidad_id, administracion_id, fecha_modificacion_excel, fecha_cache, "
    "datos_completos"
)


def get_presupuesto_por_ruta(ruta_excel: str) -> Optional[Dict]:
    """Busca un presupuesto en la cache por su ruta_excel.

    Args:
        ruta_excel: Ruta normalizada al fichero .xlsx.

    Returns:
        Dict con los datos cacheados, o None si no existe.
    """
    ruta = (ruta_excel or "").strip()
    if not ruta:
        return None
    with database.get_connection() as conn:
        cur = conn.execute(
            f"SELECT {_PRESUPUESTO_COLS} FROM presupuesto WHERE ruta_excel = ?",
            (ruta,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return _row_to_presupuesto_cache(r)


def get_presupuestos_por_estado(estado: str) -> List[Dict]:
    """Lista todos los presupuestos cacheados de un estado dado.

    Args:
        estado: Nombre de la carpeta de estado (ej: 'PRESUPUESTADO').

    Returns:
        Lista de dicts con los datos cacheados.
    """
    with database.get_connection() as conn:
        cur = conn.execute(
            f"SELECT {_PRESUPUESTO_COLS} FROM presupuesto WHERE estado = ? ORDER BY numero_proyecto",
            (estado,),
        )
        return [_row_to_presupuesto_cache(r) for r in cur.fetchall()]


def upsert_presupuesto(datos: Dict) -> Tuple[Optional[int], Optional[str]]:
    """Inserta o actualiza un presupuesto en la cache (ON CONFLICT ruta_excel).

    Args:
        datos: Dict con los campos del presupuesto. Claves esperadas:
            numero_proyecto, nombre_proyecto (obligatorio), ruta_excel (obligatorio),
            ruta_carpeta, estado, cliente, localidad, tipo_obra, fecha, total,
            subtotal, iva, obra_descripcion, cif_admin, email_admin,
            telefono_admin, codigo_postal, comunidad_id, administracion_id,
            fecha_modificacion_excel (obligatorio), datos_completos.

    Returns:
        (id, None) si ok, (None, mensaje_error) si falla.
    """
    from datetime import datetime

    nombre = (datos.get("nombre_proyecto") or "").strip()
    ruta = (datos.get("ruta_excel") or "").strip()
    fecha_mod = (datos.get("fecha_modificacion_excel") or "").strip()
    if not nombre or not ruta or not fecha_mod:
        return (None, "nombre_proyecto, ruta_excel y fecha_modificacion_excel son obligatorios.")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with database.get_connection() as conn:
        try:
            conn.execute(
                """INSERT INTO presupuesto
                   (numero_proyecto, nombre_proyecto, ruta_excel, ruta_carpeta,
                    estado, cliente, localidad, tipo_obra, fecha, total,
                    subtotal, iva, obra_descripcion, cif_admin, email_admin,
                    telefono_admin, codigo_postal, comunidad_id, administracion_id,
                    fecha_modificacion_excel, fecha_cache, datos_completos)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(ruta_excel) DO UPDATE SET
                       numero_proyecto  = excluded.numero_proyecto,
                       nombre_proyecto  = excluded.nombre_proyecto,
                       ruta_carpeta     = excluded.ruta_carpeta,
                       estado           = excluded.estado,
                       cliente          = excluded.cliente,
                       localidad        = excluded.localidad,
                       tipo_obra        = excluded.tipo_obra,
                       fecha            = excluded.fecha,
                       total            = excluded.total,
                       subtotal         = excluded.subtotal,
                       iva              = excluded.iva,
                       obra_descripcion = excluded.obra_descripcion,
                       cif_admin        = excluded.cif_admin,
                       email_admin      = excluded.email_admin,
                       telefono_admin   = excluded.telefono_admin,
                       codigo_postal    = excluded.codigo_postal,
                       comunidad_id     = excluded.comunidad_id,
                       administracion_id = excluded.administracion_id,
                       fecha_modificacion_excel = excluded.fecha_modificacion_excel,
                       fecha_cache      = excluded.fecha_cache,
                       datos_completos  = excluded.datos_completos
                """,
                (
                    (datos.get("numero_proyecto") or "").strip() or None,
                    nombre,
                    ruta,
                    (datos.get("ruta_carpeta") or "").strip() or None,
                    (datos.get("estado") or "").strip() or None,
                    (datos.get("cliente") or "").strip() or None,
                    (datos.get("localidad") or "").strip() or None,
                    (datos.get("tipo_obra") or "").strip() or None,
                    (datos.get("fecha") or "").strip() or None,
                    datos.get("total"),
                    datos.get("subtotal"),
                    datos.get("iva"),
                    (datos.get("obra_descripcion") or "").strip() or None,
                    (datos.get("cif_admin") or "").strip() or None,
                    (datos.get("email_admin") or "").strip() or None,
                    (datos.get("telefono_admin") or "").strip() or None,
                    (datos.get("codigo_postal") or "").strip() or None,
                    datos.get("comunidad_id"),
                    datos.get("administracion_id"),
                    fecha_mod,
                    now,
                    1 if datos.get("datos_completos") else 0,
                ),
            )
            conn.commit()
            cur = conn.execute(
                "SELECT id FROM presupuesto WHERE ruta_excel = ?", (ruta,)
            )
            row = cur.fetchone()
            return (row[0] if row else None, None)
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return (None, _mensaje_integridad(e))
        except sqlite3.OperationalError as e:
            conn.rollback()
            return (None, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}.")


def actualizar_estado_presupuesto(ruta_excel: str, estado: str) -> Optional[str]:
    """Actualiza solo el campo estado de un presupuesto cacheado.

    Útil cuando se mueve un proyecto de carpeta sin que cambie el Excel.

    Returns:
        None si ok, mensaje de error si falla.
    """
    with database.get_connection() as conn:
        try:
            conn.execute(
                "UPDATE presupuesto SET estado = ? WHERE ruta_excel = ?",
                (estado, ruta_excel),
            )
            conn.commit()
            return None
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def limpiar_presupuestos_huerfanos(rutas_vigentes: List[str]) -> int:
    """Elimina de la cache presupuestos cuya ruta_excel ya no está en disco.

    Args:
        rutas_vigentes: Lista de rutas de Excel actualmente presentes en las carpetas.

    Returns:
        Número de registros eliminados.
    """
    with database.get_connection() as conn:
        cur = conn.execute("SELECT id, ruta_excel FROM presupuesto")
        all_cached = cur.fetchall()
        vigentes_set = set(rutas_vigentes)
        ids_to_delete = [
            r[0] for r in all_cached
            if r[1] and r[1] not in vigentes_set
        ]
        if ids_to_delete:
            placeholders = ",".join("?" for _ in ids_to_delete)
            conn.execute(
                f"DELETE FROM presupuesto WHERE id IN ({placeholders})",
                ids_to_delete,
            )
            conn.commit()
        return len(ids_to_delete)


def get_all_presupuestos_cache() -> List[Dict]:
    """Devuelve todos los presupuestos de la cache.

    Returns:
        Lista de dicts con todos los campos.
    """
    with database.get_connection() as conn:
        cur = conn.execute(
            f"SELECT {_PRESUPUESTO_COLS} FROM presupuesto ORDER BY estado, numero_proyecto"
        )
        return [_row_to_presupuesto_cache(r) for r in cur.fetchall()]
