"""
CRUD de Administración.
"""

import sqlite3
from typing import Optional, List, Dict, Tuple

from difflib import SequenceMatcher

from src.core import database
from src.core.repositories._common import (
    FUZZY_MATCH_THRESHOLD,
    _ejecutar,
    _mensaje_integridad,
)


def get_administraciones() -> List[Dict]:
    """Lista todas las administraciones. Cada elemento es un dict con id, nombre, email, telefono, direccion."""
    with database.get_connection() as conn:
        cur = conn.execute(
            "SELECT id, nombre, email, telefono, direccion FROM administracion ORDER BY id"
        )
        rows = cur.fetchall()
        return [
            {"id": r[0], "nombre": r[1] or "", "email": r[2] or "", "telefono": r[3] or "", "direccion": r[4] or ""}
            for r in rows
        ]


def create_administracion(nombre: str, email: str = "", telefono: str = "", direccion: str = "") -> Tuple[Optional[int], Optional[str]]:
    """Crea una administración. nombre es obligatorio. Devuelve (id, None) o (None, mensaje_error)."""
    nombre = nombre.strip()
    if not nombre:
        return (None, "El nombre de la administración es obligatorio.")
    with database.get_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO administracion (nombre, email, telefono, direccion) VALUES (?, ?, ?, ?)",
                (nombre, email.strip() or None, telefono.strip() or None, direccion.strip() or None),
            )
            conn.commit()
            cur = conn.execute("SELECT last_insert_rowid()")
            return (cur.fetchone()[0], None)
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return (None, _mensaje_integridad(e))
        except sqlite3.OperationalError as e:
            conn.rollback()
            return (None, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}.")


def update_administracion(id_: int, nombre: str, email: str = "", telefono: str = "", direccion: str = "") -> Optional[str]:
    """Actualiza una administración. nombre es obligatorio. Devuelve None si ok, o mensaje de error."""
    nombre = nombre.strip()
    if not nombre:
        return "El nombre de la administración es obligatorio."
    with database.get_connection() as conn:
        err = _ejecutar(
            conn,
            "UPDATE administracion SET nombre=?, email=?, telefono=?, direccion=? WHERE id=?",
            (nombre, email.strip() or None, telefono.strip() or None, direccion.strip() or None, id_),
        )
        return err


def delete_administracion(id_: int) -> Optional[str]:
    """Elimina una administración. Devuelve None si ok, o mensaje de error (p. ej. RESTRICT)."""
    with database.get_connection() as conn:
        err = _ejecutar(conn, "DELETE FROM administracion WHERE id=?", (id_,))
        return err


def get_administraciones_para_tabla() -> List[Dict]:
    """Lista administraciones con columna 'contactos': nombres de contactos asociados (para la tabla)."""
    with database.get_connection() as conn:
        cur = conn.execute("""
            SELECT a.id, a.nombre, a.email, a.telefono, a.direccion,
                   COALESCE(GROUP_CONCAT(c.nombre), '') AS contactos
            FROM administracion a
            LEFT JOIN administracion_contacto ac ON ac.administracion_id = a.id
            LEFT JOIN contacto c ON c.id = ac.contacto_id
            GROUP BY a.id
            ORDER BY a.id
        """)
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "nombre": r[1] or "",
                "email": r[2] or "",
                "telefono": r[3] or "",
                "direccion": r[4] or "",
                "contactos": (r[5] or "").strip() or "—",
            }
            for r in rows
        ]


def get_administracion_por_id(id_: int) -> Optional[Dict]:
    """Devuelve una administración por id, o None si no existe."""
    with database.get_connection() as conn:
        cur = conn.execute(
            "SELECT id, nombre, email, telefono, direccion FROM administracion WHERE id=?",
            (id_,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {"id": r[0], "nombre": r[1] or "", "email": r[2] or "", "telefono": r[3] or "", "direccion": r[4] or ""}


def buscar_administracion_por_nombre(nombre: str) -> Optional[Dict]:
    """Busca una administración por nombre exacto (case-insensitive).

    Args:
        nombre: Nombre a buscar.

    Returns:
        Dict con los datos de la administración o None si no se encuentra.
    """
    nombre = nombre.strip()
    if not nombre:
        return None
    with database.get_connection() as conn:
        cur = conn.execute(
            "SELECT id, nombre, email, telefono, direccion "
            "FROM administracion WHERE LOWER(TRIM(nombre)) = LOWER(?)",
            (nombre,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            "id": r[0], "nombre": r[1] or "",
            "email": r[2] or "", "telefono": r[3] or "", "direccion": r[4] or "",
        }


def buscar_administraciones_fuzzy(nombre: str, umbral: float = FUZZY_MATCH_THRESHOLD) -> List[Dict]:
    """Busca administraciones cuyo nombre sea similar al dado (fuzzy matching).

    Usa difflib.SequenceMatcher para calcular la similitud. Solo devuelve
    resultados cuya ratio >= umbral, ordenados de mayor a menor similitud.

    Args:
        nombre: Nombre aproximado a buscar.
        umbral: Ratio mínimo de similitud (0-1). Por defecto 0.55.

    Returns:
        Lista de dicts con los datos de las administraciones encontradas,
        cada uno con un campo extra 'similitud' (float 0-1).
    """
    nombre = nombre.strip()
    if not nombre:
        return []
    with database.get_connection() as conn:
        cur = conn.execute(
            "SELECT id, nombre, email, telefono, direccion FROM administracion ORDER BY nombre"
        )
        rows = cur.fetchall()
        nombre_lower = nombre.lower()
        resultados = []
        for r in rows:
            nombre_db = (r[1] or "").strip().lower()
            ratio = SequenceMatcher(None, nombre_lower, nombre_db).ratio()
            if ratio >= umbral:
                resultados.append({
                    "id": r[0], "nombre": r[1] or "",
                    "email": r[2] or "", "telefono": r[3] or "", "direccion": r[4] or "",
                    "similitud": round(ratio, 3),
                })
        resultados.sort(key=lambda x: x["similitud"], reverse=True)
        return resultados
