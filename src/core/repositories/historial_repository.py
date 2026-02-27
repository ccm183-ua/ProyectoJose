"""
CRUD de historial de presupuestos.
"""

import sqlite3
from typing import Dict, List, Optional, Tuple

from src.core import database
from src.core.repositories._common import HISTORIAL_DEFAULT_LIMIT, _mensaje_integridad


def registrar_presupuesto(datos: Dict) -> Tuple[Optional[int], Optional[str]]:
    """Registra un presupuesto en el historial (INSERT OR REPLACE por ruta_excel).

    Args:
        datos: Dict con nombre_proyecto, ruta_excel, ruta_carpeta, fecha_creacion,
               cliente, localidad, tipo_obra, numero_proyecto, usa_partidas_ia,
               total_presupuesto.

    Returns:
        (id, None) si ok, (None, mensaje_error) si falla.
    """
    from datetime import datetime

    nombre = (datos.get("nombre_proyecto") or "").strip()
    ruta = (datos.get("ruta_excel") or "").strip()
    if not nombre or not ruta:
        return (None, "nombre_proyecto y ruta_excel son obligatorios.")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with database.get_connection() as conn:
        try:
            conn.execute(
                """INSERT INTO historial_presupuesto
                   (nombre_proyecto, ruta_excel, ruta_carpeta, fecha_creacion,
                    fecha_ultimo_acceso, cliente, localidad, tipo_obra,
                    numero_proyecto, usa_partidas_ia, total_presupuesto)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(ruta_excel) DO UPDATE SET
                       nombre_proyecto=excluded.nombre_proyecto,
                       fecha_ultimo_acceso=excluded.fecha_ultimo_acceso,
                       cliente=COALESCE(excluded.cliente,
                                        historial_presupuesto.cliente),
                       localidad=COALESCE(excluded.localidad,
                                          historial_presupuesto.localidad),
                       tipo_obra=COALESCE(excluded.tipo_obra,
                                          historial_presupuesto.tipo_obra),
                       numero_proyecto=COALESCE(excluded.numero_proyecto,
                                                historial_presupuesto.numero_proyecto),
                       usa_partidas_ia=MAX(excluded.usa_partidas_ia,
                                           historial_presupuesto.usa_partidas_ia),
                       total_presupuesto=COALESCE(excluded.total_presupuesto,
                                                  historial_presupuesto.total_presupuesto)
                """,
                (
                    nombre, ruta,
                    (datos.get("ruta_carpeta") or "").strip() or None,
                    datos.get("fecha_creacion") or now,
                    now,
                    (datos.get("cliente") or "").strip() or None,
                    (datos.get("localidad") or "").strip() or None,
                    (datos.get("tipo_obra") or "").strip() or None,
                    (datos.get("numero_proyecto") or "").strip() or None,
                    1 if datos.get("usa_partidas_ia") else 0,
                    datos.get("total_presupuesto"),
                ),
            )
            conn.commit()
            cur = conn.execute(
                "SELECT id FROM historial_presupuesto WHERE ruta_excel=?", (ruta,)
            )
            row = cur.fetchone()
            return (row[0] if row else None, None)
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return (None, _mensaje_integridad(e))
        except sqlite3.OperationalError as e:
            conn.rollback()
            return (None, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}.")


def get_historial_reciente(limit: int = HISTORIAL_DEFAULT_LIMIT) -> List[Dict]:
    """Lista los presupuestos más recientes del historial.

    Args:
        limit: Número máximo de resultados.

    Returns:
        Lista de dicts ordenada por fecha_ultimo_acceso DESC.
    """
    with database.get_connection() as conn:
        cur = conn.execute(
            """SELECT id, nombre_proyecto, ruta_excel, ruta_carpeta,
                      fecha_creacion, fecha_ultimo_acceso, cliente,
                      localidad, tipo_obra, numero_proyecto,
                      usa_partidas_ia, total_presupuesto
               FROM historial_presupuesto
               ORDER BY fecha_ultimo_acceso DESC
               LIMIT ?""",
            (limit,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "nombre_proyecto": r[1] or "",
                "ruta_excel": r[2] or "",
                "ruta_carpeta": r[3] or "",
                "fecha_creacion": r[4] or "",
                "fecha_ultimo_acceso": r[5] or "",
                "cliente": r[6] or "",
                "localidad": r[7] or "",
                "tipo_obra": r[8] or "",
                "numero_proyecto": r[9] or "",
                "usa_partidas_ia": bool(r[10]),
                "total_presupuesto": r[11],
            }
            for r in rows
        ]


def actualizar_acceso(ruta_excel: str) -> Optional[str]:
    """Actualiza la fecha de último acceso de un presupuesto.

    Returns:
        None si ok, mensaje de error si falla.
    """
    from datetime import datetime

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with database.get_connection() as conn:
        try:
            conn.execute(
                "UPDATE historial_presupuesto SET fecha_ultimo_acceso=? WHERE ruta_excel=?",
                (now, ruta_excel),
            )
            conn.commit()
            return None
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def actualizar_total(ruta_excel: str, total: float) -> Optional[str]:
    """Actualiza el total de un presupuesto en el historial.

    Returns:
        None si ok, mensaje de error si falla.
    """
    with database.get_connection() as conn:
        try:
            conn.execute(
                "UPDATE historial_presupuesto SET total_presupuesto=? WHERE ruta_excel=?",
                (total, ruta_excel),
            )
            conn.commit()
            return None
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def eliminar_historial(id_: int) -> Optional[str]:
    """Elimina una entrada del historial. No borra el archivo Excel.

    Returns:
        None si ok, mensaje de error si falla.
    """
    with database.get_connection() as conn:
        try:
            conn.execute("DELETE FROM historial_presupuesto WHERE id=?", (id_,))
            conn.commit()
            return None
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def buscar_historial(texto: str) -> List[Dict]:
    """Busca presupuestos en el historial por nombre, cliente o localidad.

    Args:
        texto: Texto a buscar (LIKE %texto%).

    Returns:
        Lista de dicts coincidentes, ordenada por fecha_ultimo_acceso DESC.
    """
    texto = texto.strip()
    if not texto:
        return get_historial_reciente()

    like = f"%{texto}%"
    with database.get_connection() as conn:
        cur = conn.execute(
            """SELECT id, nombre_proyecto, ruta_excel, ruta_carpeta,
                      fecha_creacion, fecha_ultimo_acceso, cliente,
                      localidad, tipo_obra, numero_proyecto,
                      usa_partidas_ia, total_presupuesto
               FROM historial_presupuesto
               WHERE nombre_proyecto LIKE ? OR cliente LIKE ? OR localidad LIKE ?
               ORDER BY fecha_ultimo_acceso DESC""",
            (like, like, like),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "nombre_proyecto": r[1] or "",
                "ruta_excel": r[2] or "",
                "ruta_carpeta": r[3] or "",
                "fecha_creacion": r[4] or "",
                "fecha_ultimo_acceso": r[5] or "",
                "cliente": r[6] or "",
                "localidad": r[7] or "",
                "tipo_obra": r[8] or "",
                "numero_proyecto": r[9] or "",
                "usa_partidas_ia": bool(r[10]),
                "total_presupuesto": r[11],
            }
            for r in rows
        ]
