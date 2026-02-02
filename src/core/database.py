"""
Gestión de la base de datos SQLite.

- El fichero solo se crea si no existe (no se crea en cada arranque).
- No se borra nunca desde la aplicación.
- Puedes editar el .db por fuera (DB Browser, etc.) y reemplazar el fichero
  cuando quieras; la app abrirá lo que haya en la ruta configurada.

Ruta por defecto: Documents/cubiApp/datos.db
Para usar otra ruta: variable de entorno CUBIAPP_DB_PATH (ruta absoluta al .db).
"""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def get_db_path() -> Path:
    """
    Ruta del fichero de base de datos.

    Orden de decisión:
    1. Variable de entorno CUBIAPP_DB_PATH (ruta absoluta al .db).
    2. Por defecto: ~/Documents/cubiApp/datos.db

    Returns:
        Path absoluto al fichero .db
    """
    env_path = os.environ.get("CUBIAPP_DB_PATH")
    if env_path and os.path.isabs(env_path):
        return Path(env_path)
    home = Path.home()
    return home / "Documents" / "cubiApp" / "datos.db"


def ensure_db_directory(path: Path) -> None:
    """Crea el directorio del fichero .db si no existe. No crea el fichero."""
    path.parent.mkdir(parents=True, exist_ok=True)


def connect(read_only: bool = False) -> sqlite3.Connection:
    """
    Abre una conexión a la base de datos.

    - Si el fichero no existe: se crea el directorio (si hace falta) y SQLite
      crea el fichero al conectar. Luego se crean las tablas si no existen.
    - Si el fichero existe: se abre tal cual (puede estar vacío o haber sido
      editado/reemplazado por fuera).

    Args:
        read_only: Si True, abre en solo lectura (uri=True con mode=ro).
                   Útil para no bloquear el fichero al consultar desde fuera.

    Returns:
        Conexión abierta. El llamador debe cerrarla o usar como context manager.
    """
    path = get_db_path()
    ensure_db_directory(path)

    if read_only:
        # Solo lectura: no crea el fichero si no existe
        uri = f"file:{path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA foreign_keys = ON")
        # Crear tablas solo si no existen (no pisa datos existentes)
        init_schema(conn)

    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """
    Crea las tablas si no existen. No modifica tablas ya existentes.

    Si el fichero fue reemplazado por otro .db que ya tiene estas tablas,
    no hace nada. Si fue reemplazado por un .db vacío, crea las tablas.
    """
    conn.executescript(_SCHEMA_SQL)
    conn.commit()


# ---------------------------------------------------------------------------
# Esquema según especificación:
# - Contacto: id, nombre NOT NULL, telefono NOT NULL (c.alt), telefono2, email, notas (resto nullable)
# - Comunidad: id, nombre NOT NULL UNIQUE (identificador), direccion, email, telefono, administracion_id
# - Administración: id, email (c.alt), telefono, direccion (todo nullable; sin riesgo integridad)
# Relaciones: Administración N:M Contacto, Comunidad N:M Contacto,
#             Comunidad N:1 Administración (comunidad obligada a tener una)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
-- Administración (sin FKs; todo nullable)
CREATE TABLE IF NOT EXISTS administracion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    telefono TEXT,
    direccion TEXT
);

-- Comunidad (FK a administración obligatoria; nombre identifica)
CREATE TABLE IF NOT EXISTS comunidad (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    direccion TEXT,
    email TEXT,
    telefono TEXT,
    administracion_id INTEGER NOT NULL REFERENCES administracion(id) ON DELETE RESTRICT
);

-- Contacto (nombre y telefono obligatorios; resto nullable)
CREATE TABLE IF NOT EXISTS contacto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    telefono TEXT NOT NULL UNIQUE,
    telefono2 TEXT,
    email TEXT,
    notas TEXT
);

-- N:M Administración <-> Contacto (0..N contactos por administración, 0..N administraciones por contacto)
CREATE TABLE IF NOT EXISTS administracion_contacto (
    administracion_id INTEGER NOT NULL REFERENCES administracion(id) ON DELETE CASCADE,
    contacto_id INTEGER NOT NULL REFERENCES contacto(id) ON DELETE CASCADE,
    PRIMARY KEY (administracion_id, contacto_id)
);

-- N:M Comunidad <-> Contacto (0..N contactos por comunidad, 0..N comunidades por contacto)
CREATE TABLE IF NOT EXISTS comunidad_contacto (
    comunidad_id INTEGER NOT NULL REFERENCES comunidad(id) ON DELETE CASCADE,
    contacto_id INTEGER NOT NULL REFERENCES contacto(id) ON DELETE CASCADE,
    PRIMARY KEY (comunidad_id, contacto_id)
);

CREATE INDEX IF NOT EXISTS idx_comunidad_administracion ON comunidad(administracion_id);
CREATE INDEX IF NOT EXISTS idx_administracion_contacto_admin ON administracion_contacto(administracion_id);
CREATE INDEX IF NOT EXISTS idx_administracion_contacto_contacto ON administracion_contacto(contacto_id);
CREATE INDEX IF NOT EXISTS idx_comunidad_contacto_comunidad ON comunidad_contacto(comunidad_id);
CREATE INDEX IF NOT EXISTS idx_comunidad_contacto_contacto ON comunidad_contacto(contacto_id);
"""


def get_db_path_as_string() -> str:
    """Ruta del .db como string, para mostrar en la UI o en documentación."""
    return str(get_db_path())


def open_db_folder() -> bool:
    """
    Crea el fichero de la base de datos si no existe (y las tablas), luego abre
    la carpeta donde está en el explorador del sistema. Así puedes localizar
    datos.db y abrirlo con un editor SQLite (p. ej. DB Browser for SQLite).

    Returns:
        True si se lanzó el comando correctamente, False en caso contrario.
    """
    path = get_db_path()
    ensure_db_directory(path)
    # Crear el .db y las tablas si no existen (conectar y cerrar)
    conn = connect()
    conn.close()
    folder = path.parent
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", str(folder)], check=True)
        elif sys.platform == "win32":
            subprocess.run(["explorer", str(folder)], check=True)
        else:
            subprocess.run(["xdg-open", str(folder)], check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return False
