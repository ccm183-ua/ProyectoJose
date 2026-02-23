"""
CRUD de Comunidad.
"""

import sqlite3
from difflib import SequenceMatcher
from typing import Optional, List, Dict, Tuple

from src.core import database
from src.core.repositories._common import (
    FUZZY_MATCH_THRESHOLD,
    _ejecutar,
    _mensaje_integridad,
    _normalize_for_match,
)


def _row_to_comunidad(r) -> Dict:
    return {
        "id": r[0], "nombre": r[1] or "",
        "cif": r[2] or "", "direccion": r[3] or "",
        "email": r[4] or "", "telefono": r[5] or "",
        "administracion_id": r[6],
    }


def get_comunidades() -> List[Dict]:
    """Lista todas las comunidades con id, nombre, cif, direccion, email, telefono, administracion_id y nombre_administracion."""
    with database.get_connection() as conn:
        cur = conn.execute("""
            SELECT c.id, c.nombre, c.cif, c.direccion, c.email, c.telefono, c.administracion_id,
                   COALESCE(a.nombre, a.email) AS admin_nombre
            FROM comunidad c
            LEFT JOIN administracion a ON a.id = c.administracion_id
            ORDER BY c.nombre
        """)
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "nombre": r[1] or "",
                "cif": r[2] or "",
                "direccion": r[3] or "",
                "email": r[4] or "",
                "telefono": r[5] or "",
                "administracion_id": r[6],
                "nombre_administracion": r[7] or "(sin asignar)",
            }
            for r in rows
        ]


def create_comunidad(
    nombre: str,
    administracion_id: int,
    cif: str = "",
    direccion: str = "",
    email: str = "",
    telefono: str = "",
) -> Tuple[Optional[int], Optional[str]]:
    """Crea una comunidad. nombre y administracion_id obligatorios. Devuelve (id, None) o (None, mensaje_error)."""
    nombre = nombre.strip()
    if not nombre:
        return (None, "El nombre de la comunidad es obligatorio.")
    with database.get_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO comunidad (nombre, cif, direccion, email, telefono, administracion_id) VALUES (?, ?, ?, ?, ?, ?)",
                (nombre, cif.strip() or None, direccion.strip() or None, email.strip() or None, telefono.strip() or None, administracion_id),
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


def update_comunidad(
    id_: int,
    nombre: str,
    administracion_id: int,
    cif: str = "",
    direccion: str = "",
    email: str = "",
    telefono: str = "",
) -> Optional[str]:
    """Actualiza una comunidad. Devuelve None si ok, o mensaje de error."""
    nombre = nombre.strip()
    if not nombre:
        return "El nombre de la comunidad es obligatorio."
    with database.get_connection() as conn:
        err = _ejecutar(
            conn,
            "UPDATE comunidad SET nombre=?, cif=?, direccion=?, email=?, telefono=?, administracion_id=? WHERE id=?",
            (nombre, cif.strip() or None, direccion.strip() or None, email.strip() or None, telefono.strip() or None, administracion_id, id_),
        )
        return err


def delete_comunidad(id_: int) -> Optional[str]:
    """Elimina una comunidad. Devuelve None si ok, o mensaje de error."""
    with database.get_connection() as conn:
        err = _ejecutar(conn, "DELETE FROM comunidad WHERE id=?", (id_,))
        return err


def get_comunidades_para_tabla() -> List[Dict]:
    """Lista comunidades con cif, administracion_id, nombre_administracion y contactos (para tabla y clics)."""
    with database.get_connection() as conn:
        cur = conn.execute("""
            SELECT c.id, c.nombre, c.cif, c.direccion, c.email, c.telefono, c.administracion_id,
                   COALESCE(a.nombre, a.email, '(sin asignar)') AS nombre_administracion,
                   COALESCE(GROUP_CONCAT(ct.nombre), '') AS contactos
            FROM comunidad c
            LEFT JOIN administracion a ON a.id = c.administracion_id
            LEFT JOIN comunidad_contacto cc ON cc.comunidad_id = c.id
            LEFT JOIN contacto ct ON ct.id = cc.contacto_id
            GROUP BY c.id
            ORDER BY c.nombre
        """)
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "nombre": r[1] or "",
                "cif": r[2] or "",
                "direccion": r[3] or "",
                "email": r[4] or "",
                "telefono": r[5] or "",
                "administracion_id": r[6],
                "nombre_administracion": r[7] or "—",
                "contactos": (r[8] or "").strip() or "—",
            }
            for r in rows
        ]


def get_comunidad_por_id(id_: int) -> Optional[Dict]:
    """Devuelve una comunidad por id, o None si no existe."""
    with database.get_connection() as conn:
        cur = conn.execute(
            "SELECT id, nombre, cif, direccion, email, telefono, administracion_id FROM comunidad WHERE id=?",
            (id_,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            "id": r[0],
            "nombre": r[1] or "",
            "cif": r[2] or "",
            "direccion": r[3] or "",
            "email": r[4] or "",
            "telefono": r[5] or "",
            "administracion_id": r[6],
        }


def buscar_comunidad_por_nombre(nombre: str) -> Optional[Dict]:
    """Busca una comunidad por nombre exacto (case-insensitive).

    Primero intenta coincidencia directa. Si no encuentra, repite la
    búsqueda normalizando ambos lados (eliminando «C.P.» y variantes)
    para evitar que el prefijo de «Comunidad de Propietarios» impida
    el match cuando una parte lo tiene y la otra no.

    Args:
        nombre: Nombre a buscar.

    Returns:
        Dict con los datos de la comunidad o None si no se encuentra.
    """
    nombre = nombre.strip()
    if not nombre:
        return None
    with database.get_connection() as conn:
        cur = conn.execute(
            "SELECT id, nombre, cif, direccion, email, telefono, administracion_id "
            "FROM comunidad WHERE LOWER(TRIM(nombre)) = LOWER(?)",
            (nombre,),
        )
        r = cur.fetchone()
        if r:
            return _row_to_comunidad(r)

        nombre_norm = _normalize_for_match(nombre).lower()
        if not nombre_norm:
            return None
        cur = conn.execute(
            "SELECT id, nombre, cif, direccion, email, telefono, administracion_id "
            "FROM comunidad ORDER BY nombre"
        )
        for r in cur.fetchall():
            db_norm = _normalize_for_match(r[1] or "").lower()
            if db_norm == nombre_norm:
                return _row_to_comunidad(r)
        return None


def buscar_comunidades_fuzzy(nombre: str, umbral: float = FUZZY_MATCH_THRESHOLD) -> List[Dict]:
    """Busca comunidades cuyo nombre sea similar al dado (fuzzy matching).

    Usa difflib.SequenceMatcher para calcular la similitud. Antes de
    comparar, normaliza ambos nombres eliminando «C.P.» y variantes
    (Comunidad de Propietarios) para evitar falsos positivos por ese
    prefijo tan común.

    Args:
        nombre: Nombre aproximado a buscar.
        umbral: Ratio mínimo de similitud (0-1). Por defecto 0.55.

    Returns:
        Lista de dicts con los datos de las comunidades encontradas,
        cada uno con un campo extra 'similitud' (float 0-1).
    """
    nombre = nombre.strip()
    if not nombre:
        return []
    with database.get_connection() as conn:
        cur = conn.execute(
            "SELECT id, nombre, cif, direccion, email, telefono, administracion_id "
            "FROM comunidad ORDER BY nombre"
        )
        rows = cur.fetchall()
        nombre_norm = _normalize_for_match(nombre).lower()
        if not nombre_norm:
            return []
        resultados = []
        for r in rows:
            db_norm = _normalize_for_match(r[1] or "").lower()
            ratio = SequenceMatcher(None, nombre_norm, db_norm).ratio()
            if ratio >= umbral:
                resultados.append({
                    **_row_to_comunidad(r),
                    "similitud": round(ratio, 3),
                })
        resultados.sort(key=lambda x: x["similitud"], reverse=True)
        return resultados
