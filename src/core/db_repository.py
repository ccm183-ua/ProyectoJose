"""
Capa de acceso a datos de la base de datos (CRUD).

Devuelve datos o (éxito, mensaje_error) con mensajes en español para el usuario.
Captura sqlite3.IntegrityError y lo convierte en mensajes claros.
"""

import sqlite3
from typing import Optional, List, Dict, Tuple

from src.core import database


def _mensaje_integridad(e: sqlite3.IntegrityError) -> str:
    """Convierte IntegrityError en mensaje amigable en español."""
    texto = (e.args[0] or "").lower()
    if "not null" in texto or "NOT NULL" in str(e):
        if "contacto" in texto or "nombre" in texto:
            return "El nombre y el teléfono del contacto son obligatorios."
        if "comunidad" in texto:
            return "El nombre de la comunidad es obligatorio."
        if "administracion" in texto:
            return "La comunidad debe tener una administración asignada."
        return "Faltan datos obligatorios."
    if "unique" in texto or "UNIQUE" in str(e):
        if "telefono" in texto:
            return "Ya existe un contacto con ese teléfono."
        if "nombre" in texto and "comunidad" in texto:
            return "Ya existe una comunidad con ese nombre."
        if "email" in texto:
            return "Ya existe una administración con ese correo."
        return "Ese valor ya existe y no se puede repetir."
    if "foreign key" in texto or "FOREIGN KEY" in str(e):
        return "No se puede usar ese valor: la referencia no existe o no es válida."
    if "restrict" in texto or "RESTRICT" in str(e):
        return "No se puede eliminar: hay comunidades que usan esta administración. Asigne otra administración a esas comunidades antes."
    return "Error de datos. Compruebe que todos los campos obligatorios estén rellenados y que no repita teléfono, nombre de comunidad o correo de administración."


def _ejecutar(conn, *args, **kwargs):
    """Ejecuta y en caso de IntegrityError devuelve mensaje amigable."""
    try:
        conn.execute(*args, **kwargs)
        conn.commit()
        return None
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return _mensaje_integridad(e)
    except sqlite3.OperationalError as e:
        conn.rollback()
        return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


# ---------------------------------------------------------------------------
# Administración
# ---------------------------------------------------------------------------

def get_administraciones() -> List[Dict]:
    """Lista todas las administraciones. Cada elemento es un dict con id, nombre, cif, email, telefono, direccion."""
    conn = database.connect()
    try:
        cur = conn.execute(
            "SELECT id, nombre, cif, email, telefono, direccion FROM administracion ORDER BY id"
        )
        rows = cur.fetchall()
        return [
            {"id": r[0], "nombre": r[1] or "", "cif": r[2] or "", "email": r[3] or "", "telefono": r[4] or "", "direccion": r[5] or ""}
            for r in rows
        ]
    finally:
        conn.close()


def create_administracion(nombre: str, cif: str = "", email: str = "", telefono: str = "", direccion: str = "") -> Tuple[Optional[int], Optional[str]]:
    """Crea una administración. nombre es obligatorio. Devuelve (id, None) o (None, mensaje_error)."""
    nombre = nombre.strip()
    if not nombre:
        return (None, "El nombre de la administración es obligatorio.")
    conn = database.connect()
    try:
        conn.execute(
            "INSERT INTO administracion (nombre, cif, email, telefono, direccion) VALUES (?, ?, ?, ?, ?)",
            (nombre, cif.strip() or None, email.strip() or None, telefono.strip() or None, direccion.strip() or None),
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
    finally:
        conn.close()


def update_administracion(id_: int, nombre: str, cif: str = "", email: str = "", telefono: str = "", direccion: str = "") -> Optional[str]:
    """Actualiza una administración. nombre es obligatorio. Devuelve None si ok, o mensaje de error."""
    nombre = nombre.strip()
    if not nombre:
        return "El nombre de la administración es obligatorio."
    conn = database.connect()
    try:
        err = _ejecutar(
            conn,
            "UPDATE administracion SET nombre=?, cif=?, email=?, telefono=?, direccion=? WHERE id=?",
            (nombre, cif.strip() or None, email.strip() or None, telefono.strip() or None, direccion.strip() or None, id_),
        )
        return err
    finally:
        conn.close()


def delete_administracion(id_: int) -> Optional[str]:
    """Elimina una administración. Devuelve None si ok, o mensaje de error (p. ej. RESTRICT)."""
    conn = database.connect()
    try:
        err = _ejecutar(conn, "DELETE FROM administracion WHERE id=?", (id_,))
        return err
    finally:
        conn.close()


def get_administraciones_para_tabla() -> List[Dict]:
    """Lista administraciones con columna 'contactos': nombres de contactos asociados (para la tabla)."""
    conn = database.connect()
    try:
        cur = conn.execute("""
            SELECT a.id, a.nombre, a.cif, a.email, a.telefono, a.direccion,
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
                "cif": r[2] or "",
                "email": r[3] or "",
                "telefono": r[4] or "",
                "direccion": r[5] or "",
                "contactos": (r[6] or "").strip() or "—",
            }
            for r in rows
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Comunidad
# ---------------------------------------------------------------------------

def get_comunidades() -> List[Dict]:
    """Lista todas las comunidades con id, nombre, direccion, email, telefono, administracion_id y nombre_administracion."""
    conn = database.connect()
    try:
        cur = conn.execute("""
            SELECT c.id, c.nombre, c.direccion, c.email, c.telefono, c.administracion_id,
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
                "direccion": r[2] or "",
                "email": r[3] or "",
                "telefono": r[4] or "",
                "administracion_id": r[5],
                "nombre_administracion": r[6] or "(sin asignar)",
            }
            for r in rows
        ]
    finally:
        conn.close()


def create_comunidad(
    nombre: str,
    administracion_id: int,
    direccion: str = "",
    email: str = "",
    telefono: str = "",
) -> Tuple[Optional[int], Optional[str]]:
    """Crea una comunidad. nombre y administracion_id obligatorios. Devuelve (id, None) o (None, mensaje_error)."""
    nombre = nombre.strip()
    if not nombre:
        return (None, "El nombre de la comunidad es obligatorio.")
    conn = database.connect()
    try:
        conn.execute(
            "INSERT INTO comunidad (nombre, direccion, email, telefono, administracion_id) VALUES (?, ?, ?, ?, ?)",
            (nombre, direccion.strip() or None, email.strip() or None, telefono.strip() or None, administracion_id),
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
    finally:
        conn.close()


def update_comunidad(
    id_: int,
    nombre: str,
    administracion_id: int,
    direccion: str = "",
    email: str = "",
    telefono: str = "",
) -> Optional[str]:
    """Actualiza una comunidad. Devuelve None si ok, o mensaje de error."""
    nombre = nombre.strip()
    if not nombre:
        return "El nombre de la comunidad es obligatorio."
    conn = database.connect()
    try:
        err = _ejecutar(
            conn,
            "UPDATE comunidad SET nombre=?, direccion=?, email=?, telefono=?, administracion_id=? WHERE id=?",
            (nombre, direccion.strip() or None, email.strip() or None, telefono.strip() or None, administracion_id, id_),
        )
        return err
    finally:
        conn.close()


def delete_comunidad(id_: int) -> Optional[str]:
    """Elimina una comunidad. Devuelve None si ok, o mensaje de error."""
    conn = database.connect()
    try:
        err = _ejecutar(conn, "DELETE FROM comunidad WHERE id=?", (id_,))
        return err
    finally:
        conn.close()


def get_comunidades_para_tabla() -> List[Dict]:
    """Lista comunidades con administracion_id, nombre_administracion y contactos (para tabla y clics)."""
    conn = database.connect()
    try:
        cur = conn.execute("""
            SELECT c.id, c.nombre, c.direccion, c.email, c.telefono, c.administracion_id,
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
                "direccion": r[2] or "",
                "email": r[3] or "",
                "telefono": r[4] or "",
                "administracion_id": r[5],
                "nombre_administracion": r[6] or "—",
                "contactos": (r[7] or "").strip() or "—",
            }
            for r in rows
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Contacto
# ---------------------------------------------------------------------------

def get_contactos() -> List[Dict]:
    """Lista todos los contactos con id, nombre, telefono, telefono2, email, notas."""
    conn = database.connect()
    try:
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
    finally:
        conn.close()


def get_contactos_para_tabla() -> List[Dict]:
    """Lista contactos con columnas 'administraciones' y 'comunidades': entidades asociadas (para la tabla)."""
    conn = database.connect()
    try:
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
    finally:
        conn.close()


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
    conn = database.connect()
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
    finally:
        conn.close()


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
    conn = database.connect()
    try:
        err = _ejecutar(
            conn,
            "UPDATE contacto SET nombre=?, telefono=?, telefono2=?, email=?, notas=? WHERE id=?",
            (nombre, telefono, telefono2.strip() or None, email.strip() or None, notas.strip() or None, id_),
        )
        return err
    finally:
        conn.close()


def delete_contacto(id_: int) -> Optional[str]:
    """Elimina un contacto. Devuelve None si ok, o mensaje de error."""
    conn = database.connect()
    try:
        err = _ejecutar(conn, "DELETE FROM contacto WHERE id=?", (id_,))
        return err
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Relaciones N:M (para asignar contactos a administraciones y comunidades)
# ---------------------------------------------------------------------------

def get_administracion_por_id(id_: int) -> Optional[Dict]:
    """Devuelve una administración por id, o None si no existe."""
    conn = database.connect()
    try:
        cur = conn.execute(
            "SELECT id, nombre, cif, email, telefono, direccion FROM administracion WHERE id=?",
            (id_,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {"id": r[0], "nombre": r[1] or "", "cif": r[2] or "", "email": r[3] or "", "telefono": r[4] or "", "direccion": r[5] or ""}
    finally:
        conn.close()


def get_comunidad_por_id(id_: int) -> Optional[Dict]:
    """Devuelve una comunidad por id, o None si no existe."""
    conn = database.connect()
    try:
        cur = conn.execute(
            "SELECT id, nombre, direccion, email, telefono, administracion_id FROM comunidad WHERE id=?",
            (id_,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            "id": r[0],
            "nombre": r[1] or "",
            "direccion": r[2] or "",
            "email": r[3] or "",
            "telefono": r[4] or "",
            "administracion_id": r[5],
        }
    finally:
        conn.close()


def get_contactos_por_administracion_id(administracion_id: int) -> List[Dict]:
    """Lista contactos asociados a una administración (id, nombre, telefono, telefono2, email, notas)."""
    conn = database.connect()
    try:
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
    finally:
        conn.close()


def get_contactos_por_comunidad_id(comunidad_id: int) -> List[Dict]:
    """Lista contactos asociados a una comunidad (id, nombre, telefono, telefono2, email, notas)."""
    conn = database.connect()
    try:
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
    finally:
        conn.close()


def get_administracion_ids_para_contacto(contacto_id: int) -> List[int]:
    """Devuelve los id de administraciones asignadas a este contacto."""
    conn = database.connect()
    try:
        cur = conn.execute(
            "SELECT administracion_id FROM administracion_contacto WHERE contacto_id=?",
            (contacto_id,),
        )
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def get_comunidad_ids_para_contacto(contacto_id: int) -> List[int]:
    """Devuelve los id de comunidades asignadas a este contacto."""
    conn = database.connect()
    try:
        cur = conn.execute(
            "SELECT comunidad_id FROM comunidad_contacto WHERE contacto_id=?",
            (contacto_id,),
        )
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def set_administracion_contacto(contacto_id: int, administracion_ids: List[int]) -> Optional[str]:
    """Sustituye las asignaciones contacto-administración por la lista dada."""
    conn = database.connect()
    try:
        conn.execute("DELETE FROM administracion_contacto WHERE contacto_id=?", (contacto_id,))
        for aid in administracion_ids:
            err = _ejecutar(
                conn,
                "INSERT INTO administracion_contacto (administracion_id, contacto_id) VALUES (?, ?)",
                (aid, contacto_id),
            )
            if err:
                return err
        conn.commit()
        return None
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return _mensaje_integridad(e)
    finally:
        conn.close()


def set_comunidad_contacto(contacto_id: int, comunidad_ids: List[int]) -> Optional[str]:
    """Sustituye las asignaciones contacto-comunidad por la lista dada."""
    conn = database.connect()
    try:
        conn.execute("DELETE FROM comunidad_contacto WHERE contacto_id=?", (contacto_id,))
        for cid in comunidad_ids:
            err = _ejecutar(
                conn,
                "INSERT INTO comunidad_contacto (comunidad_id, contacto_id) VALUES (?, ?)",
                (cid, contacto_id),
            )
            if err:
                return err
        conn.commit()
        return None
    except sqlite3.IntegrityError as e:
        conn.rollback()
        return _mensaje_integridad(e)
    finally:
        conn.close()
