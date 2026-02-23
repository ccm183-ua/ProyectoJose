"""
Helpers y constantes compartidos por los repositorios.
"""

import re
import sqlite3

_CP_RE = re.compile(
    r"\b[Cc]\.?\s*[Pp]\.?\s*",
)

# Umbral de similitud para búsqueda fuzzy (0.0 – 1.0)
FUZZY_MATCH_THRESHOLD = 0.55

# Límite de registros en consultas de historial
HISTORIAL_DEFAULT_LIMIT = 50


def _normalize_for_match(name: str) -> str:
    """Elimina prefijos 'C.P.', 'C.P', 'C. P.', etc. y normaliza espacios.

    Estos prefijos son abreviaturas de "Comunidad de Propietarios" y están
    presentes en la gran mayoría de nombres de comunidad y proyecto, lo que
    distorsiona el matching fuzzy produciendo falsos positivos.
    """
    result = _CP_RE.sub("", name)
    return " ".join(result.split()).strip()


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
