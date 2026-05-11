"""
Gestión de la base de datos SQLite.

- El fichero solo se crea si no existe (no se crea en cada arranque).
- No se borra nunca desde la aplicación.
- Puedes editar el .db por fuera (DB Browser, etc.) y reemplazar el fichero
  cuando quieras; la app abrirá lo que haya en la ruta configurada.

Prioridad de ruta:
1. Ruta guardada en Settings.
2. Variable CUBIAPP_DB_PATH (ruta absoluta al .db).
3. Ruta estable por defecto: Documents/CubiApp/datos.db.
4. Fallback legacy project_root/datos.db solo si la ruta estable no existe
   o esta vacia y legacy contiene historicos.
"""

import os
import sqlite3
import subprocess
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from src.core.settings import Settings


APP_VERSION = "cubiapp"


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def get_legacy_db_path() -> Path:
    return get_project_root() / "datos.db"


def get_stable_default_db_path() -> Path:
    return Path.home() / "Documents" / "CubiApp" / "datos.db"


def _db_has_historical_data(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            table = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='historical_budget'"
            ).fetchone()
            if not table:
                return False
            count = conn.execute("SELECT COUNT(*) FROM historical_budget").fetchone()[0]
            return int(count or 0) > 0
    except sqlite3.Error:
        return False


def _db_is_truly_empty(path: Path) -> bool:
    return not path.exists() or path.stat().st_size == 0


def get_db_path() -> Path:
    """
    Ruta del fichero de base de datos.

    Orden de decision:
    1. Ruta guardada en Settings, si existe.
    2. Variable de entorno CUBIAPP_DB_PATH, si existe y es absoluta.
    3. Documents/CubiApp/datos.db.
    4. Fallback legacy project_root/datos.db solo si la ruta estable no existe
       o esta vacia y legacy contiene historicos.

    Returns:
        Path absoluto al fichero .db
    """
    settings_path = Settings().get_database_path()
    if settings_path and os.path.isabs(settings_path):
        return Path(settings_path)

    env_path = os.environ.get("CUBIAPP_DB_PATH")
    if env_path and os.path.isabs(env_path):
        return Path(env_path)
    stable_path = get_stable_default_db_path()
    legacy_path = get_legacy_db_path()
    if _db_is_truly_empty(stable_path) and _db_has_historical_data(legacy_path):
        return legacy_path
    return stable_path


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


@contextmanager
def get_connection(read_only: bool = False) -> Iterator[sqlite3.Connection]:
    """Context manager que abre y cierra automáticamente la conexión SQLite.

    Uso::

        with get_connection() as conn:
            conn.execute("SELECT ...")
    """
    conn = connect(read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()


def _migrate_administracion_nombre(conn: sqlite3.Connection) -> None:
    """Añade la columna nombre a administracion si no existe (BDs creadas antes del cambio)."""
    cur = conn.execute("PRAGMA table_info(administracion)")
    columns = [row[1] for row in cur.fetchall()]
    if "nombre" not in columns:
        conn.execute("ALTER TABLE administracion ADD COLUMN nombre TEXT NOT NULL DEFAULT ''")
        conn.commit()


def _migrate_comunidad_cif(conn: sqlite3.Connection) -> None:
    """Añade la columna cif a comunidad si no existe (BDs creadas antes del cambio)."""
    cur = conn.execute("PRAGMA table_info(comunidad)")
    columns = [row[1] for row in cur.fetchall()]
    if "cif" not in columns:
        conn.execute("ALTER TABLE comunidad ADD COLUMN cif TEXT")
        conn.commit()


def _migrate_presupuesto_v2(conn: sqlite3.Connection) -> None:
    """Añade columnas nuevas en presupuesto y crea tabla de partidas si faltan."""
    cur = conn.execute("PRAGMA table_info(presupuesto)")
    columns = {row[1] for row in cur.fetchall()}

    column_defs = {
        "direccion": "TEXT",
        "localizacion": "TEXT",
        "fuente_datos": "TEXT NOT NULL DEFAULT 'scan'",
        "es_finalizado": "INTEGER NOT NULL DEFAULT 0",
        "motivo_incompleto": "TEXT",
        "calidad_datos": "INTEGER NOT NULL DEFAULT 0",
        "comunidad_nombre": "TEXT",
        "administracion_nombre": "TEXT",
        "fecha_finalizacion": "TEXT",
        "total_partidas": "REAL",
        "num_partidas": "INTEGER NOT NULL DEFAULT 0",
        "metodo_resolucion_admin": "TEXT",
        "metodo_resolucion_comunidad": "TEXT",
    }

    changed = False
    for col_name, col_def in column_defs.items():
        if col_name not in columns:
            conn.execute(f"ALTER TABLE presupuesto ADD COLUMN {col_name} {col_def}")
            changed = True

    if changed:
        conn.commit()


def _ensure_presupuesto_v2_indexes(conn: sqlite3.Connection) -> None:
    """Crea índices v2 de presupuesto de forma segura en BDs antiguas."""
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_presupuesto_finalizado ON presupuesto(es_finalizado, estado)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_presupuesto_calidad ON presupuesto(calidad_datos)"
    )
    conn.commit()


def init_schema(conn: sqlite3.Connection) -> None:
    """
    Crea las tablas si no existen. No modifica tablas ya existentes.

    Si el fichero fue reemplazado por otro .db que ya tiene estas tablas,
    no hace nada. Si fue reemplazado por un .db vacío, crea las tablas.
    Ejecuta migraciones para añadir columnas nuevas a tablas existentes.
    """
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_HISTORICAL_SCHEMA_SQL)
    conn.commit()
    _migrate_administracion_nombre(conn)
    _migrate_comunidad_cif(conn)
    _migrate_presupuesto_v2(conn)
    _ensure_presupuesto_v2_indexes(conn)
    _ensure_app_database_identity(conn)


# ---------------------------------------------------------------------------
# Esquema según especificación:
# - Contacto: id, nombre NOT NULL, telefono NOT NULL (c.alt), telefono2, email, notas (resto nullable)
# - Comunidad: id, nombre NOT NULL UNIQUE (identificador), cif, direccion, email, telefono, administracion_id
# - Administración: id, nombre NOT NULL, email (c.alt), telefono, direccion (sin CIF)
# Relaciones: Administración N:M Contacto, Comunidad N:M Contacto,
#             Comunidad N:1 Administración (comunidad obligada a tener una)
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
-- Administración (nombre obligatorio; resto nullable)
CREATE TABLE IF NOT EXISTS administracion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    email TEXT UNIQUE,
    telefono TEXT,
    direccion TEXT
);

-- Comunidad (FK a administración obligatoria; nombre identifica)
CREATE TABLE IF NOT EXISTS comunidad (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    cif TEXT,
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

-- Historial de presupuestos (creados y abiertos desde la app)
CREATE TABLE IF NOT EXISTS historial_presupuesto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_proyecto TEXT NOT NULL,
    ruta_excel TEXT NOT NULL UNIQUE,
    ruta_carpeta TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_ultimo_acceso TEXT NOT NULL,
    cliente TEXT,
    localidad TEXT,
    tipo_obra TEXT,
    numero_proyecto TEXT,
    usa_partidas_ia INTEGER DEFAULT 0,
    total_presupuesto REAL
);
CREATE INDEX IF NOT EXISTS idx_historial_fecha ON historial_presupuesto(fecha_ultimo_acceso);

-- Cache de presupuestos escaneados (evita re-leer Excels si no han cambiado)
CREATE TABLE IF NOT EXISTS presupuesto (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_proyecto          TEXT,
    nombre_proyecto          TEXT NOT NULL,
    ruta_excel               TEXT UNIQUE,
    ruta_carpeta             TEXT,
    estado                   TEXT,
    cliente                  TEXT,
    localidad                TEXT,
    tipo_obra                TEXT,
    fecha                    TEXT,
    total                    REAL,
    subtotal                 REAL,
    iva                      REAL,
    obra_descripcion         TEXT,
    cif_admin                TEXT,
    email_admin              TEXT,
    telefono_admin           TEXT,
    codigo_postal            TEXT,
    direccion                TEXT,
    localizacion             TEXT,
    comunidad_id             INTEGER REFERENCES comunidad(id) ON DELETE SET NULL,
    administracion_id        INTEGER REFERENCES administracion(id) ON DELETE SET NULL,
    comunidad_nombre         TEXT,
    administracion_nombre    TEXT,
    fecha_modificacion_excel TEXT NOT NULL,
    fecha_cache              TEXT NOT NULL,
    datos_completos          INTEGER DEFAULT 0,
    total_partidas           REAL,
    num_partidas             INTEGER NOT NULL DEFAULT 0,
    fuente_datos             TEXT NOT NULL DEFAULT 'scan',
    es_finalizado            INTEGER NOT NULL DEFAULT 0,
    fecha_finalizacion       TEXT,
    calidad_datos            INTEGER NOT NULL DEFAULT 0,
    motivo_incompleto        TEXT,
    metodo_resolucion_admin  TEXT,
    metodo_resolucion_comunidad TEXT
);
CREATE INDEX IF NOT EXISTS idx_presupuesto_numero ON presupuesto(numero_proyecto);
CREATE INDEX IF NOT EXISTS idx_presupuesto_estado ON presupuesto(estado);
CREATE INDEX IF NOT EXISTS idx_presupuesto_ruta ON presupuesto(ruta_excel);

CREATE TABLE IF NOT EXISTS presupuesto_partida (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    presupuesto_id INTEGER NOT NULL REFERENCES presupuesto(id) ON DELETE CASCADE,
    orden INTEGER NOT NULL,
    numero TEXT,
    concepto TEXT NOT NULL,
    unidad TEXT,
    cantidad REAL,
    precio REAL,
    importe REAL
);
CREATE INDEX IF NOT EXISTS idx_presupuesto_partida_presupuesto
    ON presupuesto_partida(presupuesto_id, orden);
CREATE INDEX IF NOT EXISTS idx_presupuesto_partida_numero
    ON presupuesto_partida(numero);
"""

# Memoria histórica, patrones y diagnósticos (repositorio historical_repository y paneles asociados).
_HISTORICAL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS app_database_identity (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    database_uuid TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS historical_analysis_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_inicio TEXT,
    carpeta_origen TEXT,
    estado TEXT,
    fecha_fin TEXT,
    total_archivos INTEGER,
    archivos_procesados INTEGER,
    archivos_omitidos INTEGER,
    archivos_error INTEGER,
    error TEXT
);

CREATE TABLE IF NOT EXISTS historical_pattern_build_run (
    id TEXT PRIMARY KEY,
    started_at TEXT,
    builder_version TEXT,
    finished_at TEXT,
    source_budget_count INTEGER,
    source_partida_count INTEGER,
    patterns_inserted INTEGER,
    error TEXT
);

CREATE TABLE IF NOT EXISTS execution_module (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    categoria TEXT,
    activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS historical_budget (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ruta_excel TEXT NOT NULL UNIQUE,
    ruta_carpeta TEXT,
    numero_proyecto TEXT,
    nombre_proyecto TEXT,
    cliente TEXT,
    localidad TEXT,
    tipo_obra_original TEXT,
    tipo_obra_normalizado TEXT,
    estado TEXT,
    total REAL,
    fecha_presupuesto TEXT,
    fecha_modificacion_excel TEXT NOT NULL,
    fecha_analisis TEXT,
    num_partidas INTEGER NOT NULL DEFAULT 0,
    analysis_run_id INTEGER REFERENCES historical_analysis_run(id) ON DELETE SET NULL,
    analisis_ok INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    warnings TEXT,
    analysis_status TEXT,
    compatible_score INTEGER NOT NULL DEFAULT 0,
    selected_sheet TEXT,
    selected_sheet_index INTEGER,
    expected_numero TEXT,
    detected_numero TEXT,
    numero_matches INTEGER NOT NULL DEFAULT 0,
    usable_for_learning INTEGER NOT NULL DEFAULT 0,
    learning_status TEXT,
    learning_status_source TEXT,
    learning_decision_reason TEXT,
    learning_decision_at TEXT,
    analyzer_version TEXT,
    probe_version TEXT,
    reader_version TEXT,
    quality_rules_version TEXT,
    classifier_version TEXT,
    probe_diagnostics_json TEXT,
    header_score INTEGER NOT NULL DEFAULT 0,
    partida_score INTEGER NOT NULL DEFAULT 0,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_historical_budget_run ON historical_budget(analysis_run_id);
CREATE INDEX IF NOT EXISTS idx_historical_budget_status ON historical_budget(analysis_status);
CREATE INDEX IF NOT EXISTS idx_historical_budget_learning ON historical_budget(learning_status);

CREATE TABLE IF NOT EXISTS historical_partida (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    historical_budget_id INTEGER NOT NULL REFERENCES historical_budget(id) ON DELETE CASCADE,
    orden INTEGER NOT NULL,
    codigo TEXT,
    titulo TEXT,
    descripcion TEXT,
    concepto_original TEXT,
    concepto_normalizado TEXT,
    unidad TEXT,
    cantidad REAL,
    precio_unitario REAL,
    total_linea REAL,
    capitulo TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_historical_partida_budget ON historical_partida(historical_budget_id, orden);

CREATE TABLE IF NOT EXISTS historical_partida_module (
    partida_id INTEGER NOT NULL REFERENCES historical_partida(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES execution_module(id) ON DELETE CASCADE,
    confidence REAL,
    source TEXT,
    PRIMARY KEY (partida_id, module_id)
);

CREATE TABLE IF NOT EXISTS budget_module_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    historical_budget_id INTEGER NOT NULL REFERENCES historical_budget(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES execution_module(id) ON DELETE CASCADE,
    num_partidas INTEGER,
    total_importe REAL,
    porcentaje_presupuesto REAL,
    UNIQUE (historical_budget_id, module_id)
);

CREATE TABLE IF NOT EXISTS historical_budget_issue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    historical_budget_id INTEGER NOT NULL REFERENCES historical_budget(id) ON DELETE CASCADE,
    severity TEXT,
    code TEXT,
    message TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_historical_budget_issue_budget ON historical_budget_issue(historical_budget_id);

CREATE TABLE IF NOT EXISTS historical_budget_enrichment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    historical_budget_id INTEGER NOT NULL REFERENCES historical_budget(id) ON DELETE CASCADE,
    enrichment_type TEXT NOT NULL,
    status TEXT,
    source TEXT,
    model TEXT,
    prompt_version TEXT,
    input_hash TEXT,
    content TEXT,
    confidence REAL,
    warnings TEXT,
    metadata_json TEXT,
    reviewed_at TEXT,
    created_at TEXT,
    updated_at TEXT,
    UNIQUE (historical_budget_id, enrichment_type)
);

CREATE TABLE IF NOT EXISTS suggested_partida_pattern (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id INTEGER NOT NULL REFERENCES execution_module(id) ON DELETE CASCADE,
    concepto_normalizado TEXT NOT NULL,
    titulo_sugerido TEXT,
    descripcion_sugerida TEXT,
    unidad_habitual TEXT,
    precio_unitario_medio REAL,
    precio_unitario_mediana REAL,
    precio_unitario_min REAL,
    precio_unitario_max REAL,
    frecuencia INTEGER,
    confianza REAL,
    pattern_build_run TEXT,
    pattern_source TEXT,
    activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS suggested_partida_pattern_source (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_id INTEGER NOT NULL REFERENCES suggested_partida_pattern(id) ON DELETE CASCADE,
    historical_partida_id INTEGER NOT NULL REFERENCES historical_partida(id) ON DELETE CASCADE,
    historical_budget_id INTEGER NOT NULL REFERENCES historical_budget(id) ON DELETE CASCADE,
    precio_unitario REAL,
    total_linea REAL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS historical_memory_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    message TEXT,
    metadata_json TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS suggestion_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    tipo_obra_normalizado TEXT,
    descripcion TEXT,
    min_confidence REAL,
    num_presupuestos_base INTEGER NOT NULL DEFAULT 0,
    fecha_actualizacion TEXT,
    activo INTEGER NOT NULL DEFAULT 1
);
"""


def _ensure_app_database_identity(conn: sqlite3.Connection) -> None:
    """Una fila fija (id=1) con UUID para distinguir ficheros .db en diagnósticos."""
    cur = conn.execute("SELECT COUNT(*) FROM app_database_identity WHERE id=1")
    n = int((cur.fetchone() or [0])[0] or 0)
    if n == 0:
        conn.execute(
            "INSERT INTO app_database_identity (id, database_uuid) VALUES (1, ?)",
            (str(uuid.uuid4()),),
        )
        conn.commit()


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
