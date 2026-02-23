"""
CRUD de Contacto y relaciones N:M con Administración y Comunidad.
"""

import sqlite3
from typing import Optional, List, Dict, Tuple

from src.core import database
from src.core.repositories._common import _ejecutar, _mensaje_integridad


def get_contactos() -> List[Dict]:
    """Lista todos los contactos con id, nombre, telefono, telefono2, email, notas."""
    with database.get_connection() as conn:
        cur = conn.execute(
            "SELECT id, nombre, telefono, telefono2, email, notas FROM contacto ORDER BY nombre"
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "nombre": r[1] or "",
                "telefono": r[2] or "",
                "telefono2": r[3] or "",
                "email": r[4] or "",
                "notas": r[5] or "",
            }
            for r in rows
        ]


def get_contactos_para_tabla() -> List[Dict]:
    """Lista contactos con columnas 'administraciones' y 'comunidades': entidades asociadas (para la tabla)."""
    with database.get_connection() as conn:
        cur = conn.execute("""
            SELECT co.id, co.nombre, co.telefono, co.telefono2, co.email, co.notas,
                   (SELECT GROUP_CONCAT(COALESCE(a.nombre, a.email)) FROM administracion_contacto ac
                    JOIN administracion a ON a.id = ac.administracion_id WHERE ac.contacto_id = co.id) AS admins,
                   (SELECT GROUP_CONCAT(c.nombre) FROM comunidad_contacto cc
                    JOIN comunidad c ON c.id = cc.comunidad_id WHERE cc.contacto_id = co.id) AS coms
            FROM contacto co
            ORDER BY co.nombre
        """)
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "nombre": r[1] or "",
                "telefono": r[2] or "",
                "telefono2": r[3] or "",
                "email": r[4] or "",
                "notas": r[5] or "",
                "administraciones": (r[6] or "").strip() or "—",
                "comunidades": (r[7] or "").strip() or "—",
            }
            for r in rows
        ]


def create_contacto(
    nombre: str,
    telefono: str,
    telefono2: str = "",
    email: str = "",
    notas: str = "",
) -> Tuple[Optional[int], Optional[str]]:
    """Crea un contacto. nombre y telefono obligatorios. Devuelve (id, None) o (None, mensaje_error)."""
    nombre = nombre.strip()
    telefono = telefono.strip()
    if not nombre:
        return (None, "El nombre del contacto es obligatorio.")
    if not telefono:
        return (None, "El teléfono del contacto es obligatorio.")
    with database.get_connection() as conn:
        try:
            conn.execute(
                "INSERT INTO contacto (nombre, telefono, telefono2, email, notas) VALUES (?, ?, ?, ?, ?)",
                (nombre, telefono, telefono2.strip() or None, email.strip() or None, notas.strip() or None),
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


def update_contacto(
    id_: int,
    nombre: str,
    telefono: str,
    telefono2: str = "",
    email: str = "",
    notas: str = "",
) -> Optional[str]:
    """Actualiza un contacto. Devuelve None si ok, o mensaje de error."""
    nombre = nombre.strip()
    telefono = telefono.strip()
    if not nombre:
        return "El nombre del contacto es obligatorio."
    if not telefono:
        return "El teléfono del contacto es obligatorio."
    with database.get_connection() as conn:
        err = _ejecutar(
            conn,
            "UPDATE contacto SET nombre=?, telefono=?, telefono2=?, email=?, notas=? WHERE id=?",
            (nombre, telefono, telefono2.strip() or None, email.strip() or None, notas.strip() or None, id_),
        )
        return err


def delete_contacto(id_: int) -> Optional[str]:
    """Elimina un contacto. Devuelve None si ok, o mensaje de error."""
    with database.get_connection() as conn:
        err = _ejecutar(conn, "DELETE FROM contacto WHERE id=?", (id_,))
        return err


def get_contactos_por_administracion_id(administracion_id: int) -> List[Dict]:
    """Lista contactos asociados a una administración (id, nombre, telefono, telefono2, email, notas)."""
    with database.get_connection() as conn:
        cur = conn.execute("""
            SELECT c.id, c.nombre, c.telefono, c.telefono2, c.email, c.notas
            FROM contacto c
            JOIN administracion_contacto ac ON ac.contacto_id = c.id
            WHERE ac.administracion_id = ?
            ORDER BY c.nombre
        """, (administracion_id,))
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "nombre": r[1] or "",
                "telefono": r[2] or "",
                "telefono2": r[3] or "",
                "email": r[4] or "",
                "notas": r[5] or "",
            }
            for r in rows
        ]


def get_contactos_por_comunidad_id(comunidad_id: int) -> List[Dict]:
    """Lista contactos asociados a una comunidad (id, nombre, telefono, telefono2, email, notas)."""
    with database.get_connection() as conn:
        cur = conn.execute("""
            SELECT c.id, c.nombre, c.telefono, c.telefono2, c.email, c.notas
            FROM contacto c
            JOIN comunidad_contacto cc ON cc.contacto_id = c.id
            WHERE cc.comunidad_id = ?
            ORDER BY c.nombre
        """, (comunidad_id,))
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "nombre": r[1] or "",
                "telefono": r[2] or "",
                "telefono2": r[3] or "",
                "email": r[4] or "",
                "notas": r[5] or "",
            }
            for r in rows
        ]


def get_administracion_ids_para_contacto(contacto_id: int) -> List[int]:
    """Devuelve los id de administraciones asignadas a este contacto."""
    with database.get_connection() as conn:
        cur = conn.execute(
            "SELECT administracion_id FROM administracion_contacto WHERE contacto_id=?",
            (contacto_id,),
        )
        return [r[0] for r in cur.fetchall()]


def get_comunidad_ids_para_contacto(contacto_id: int) -> List[int]:
    """Devuelve los id de comunidades asignadas a este contacto."""
    with database.get_connection() as conn:
        cur = conn.execute(
            "SELECT comunidad_id FROM comunidad_contacto WHERE contacto_id=?",
            (contacto_id,),
        )
        return [r[0] for r in cur.fetchall()]


def set_administracion_contacto(contacto_id: int, administracion_ids: List[int]) -> Optional[str]:
    """Sustituye las asignaciones contacto-administración por la lista dada."""
    with database.get_connection() as conn:
        try:
            conn.execute("DELETE FROM administracion_contacto WHERE contacto_id=?", (contacto_id,))
            for aid in administracion_ids:
                conn.execute(
                    "INSERT INTO administracion_contacto (administracion_id, contacto_id) VALUES (?, ?)",
                    (aid, contacto_id),
                )
            conn.commit()
            return None
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return _mensaje_integridad(e)


def set_comunidad_contacto(contacto_id: int, comunidad_ids: List[int]) -> Optional[str]:
    """Sustituye las asignaciones contacto-comunidad por la lista dada."""
    with database.get_connection() as conn:
        try:
            conn.execute("DELETE FROM comunidad_contacto WHERE contacto_id=?", (contacto_id,))
            for cid in comunidad_ids:
                conn.execute(
                    "INSERT INTO comunidad_contacto (comunidad_id, contacto_id) VALUES (?, ?)",
                    (cid, contacto_id),
                )
            conn.commit()
            return None
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return _mensaje_integridad(e)


def set_contactos_para_administracion(administracion_id: int, contacto_ids: List[int]) -> Optional[str]:
    """Sustituye los contactos asignados a una administración por la lista dada."""
    with database.get_connection() as conn:
        try:
            conn.execute("DELETE FROM administracion_contacto WHERE administracion_id=?", (administracion_id,))
            for cid in contacto_ids:
                conn.execute(
                    "INSERT INTO administracion_contacto (administracion_id, contacto_id) VALUES (?, ?)",
                    (administracion_id, cid),
                )
            conn.commit()
            return None
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return _mensaje_integridad(e)


def set_contactos_para_comunidad(comunidad_id: int, contacto_ids: List[int]) -> Optional[str]:
    """Sustituye los contactos asignados a una comunidad por la lista dada."""
    with database.get_connection() as conn:
        try:
            conn.execute("DELETE FROM comunidad_contacto WHERE comunidad_id=?", (comunidad_id,))
            for cid in contacto_ids:
                conn.execute(
                    "INSERT INTO comunidad_contacto (comunidad_id, contacto_id) VALUES (?, ?)",
                    (comunidad_id, cid),
                )
            conn.commit()
            return None
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return _mensaje_integridad(e)
