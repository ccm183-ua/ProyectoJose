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


def _migrate_execution_module_descripcion(conn: sqlite3.Connection) -> None:
    """Añade la columna descripcion a execution_module si no existe (BDs anteriores al cambio)."""
    cur = conn.execute("PRAGMA table_info(execution_module)")
    columns = [row[1] for row in cur.fetchall()]
    if "descripcion" not in columns:
        conn.execute("ALTER TABLE execution_module ADD COLUMN descripcion TEXT")
        conn.commit()


def _migrate_historical_budget_source_kind(conn: sqlite3.Connection) -> None:
    """Añade procedencia/aprobación explícita a historical_budget (BDs anteriores al cambio).

    ALTER TABLE ADD COLUMN ... DEFAULT aplica el valor por defecto también a las
    filas ya existentes, así que las importaciones previas quedan marcadas como
    'external_excel' sin tocar su learning_status ya decidido.
    """
    cur = conn.execute("PRAGMA table_info(historical_budget)")
    columns = {row[1] for row in cur.fetchall()}
    column_defs = {
        "file_sha256": "TEXT",
        "source_kind": "TEXT NOT NULL DEFAULT 'external_excel'",
        "approved_at": "TEXT",
        "approved_by": "TEXT",
    }
    changed = False
    for col_name, col_def in column_defs.items():
        if col_name not in columns:
            conn.execute(f"ALTER TABLE historical_budget ADD COLUMN {col_name} {col_def}")
            changed = True
    if changed:
        conn.commit()


def _migrate_pattern_evidence_columns(conn: sqlite3.Connection) -> None:
    """Añade estadísticas de evidencia a suggested_partida_pattern (BDs anteriores
    al cambio). Los patrones existentes quedan con estos campos vacíos hasta la
    siguiente reconstrucción (rebuild_patterns), que ahora agrupa solo por
    módulo principal y líneas atómicas aprobadas."""
    cur = conn.execute("PRAGMA table_info(suggested_partida_pattern)")
    columns = {row[1] for row in cur.fetchall()}
    column_defs = {
        "distinct_budget_count": "INTEGER NOT NULL DEFAULT 0",
        "price_spread_ratio": "REAL",
        "latest_source_date": "TEXT",
        "evidence_quality": "TEXT",
    }
    changed = False
    for col_name, col_def in column_defs.items():
        if col_name not in columns:
            conn.execute(f"ALTER TABLE suggested_partida_pattern ADD COLUMN {col_name} {col_def}")
            changed = True
    if changed:
        conn.commit()


def _seed_execution_modules(conn: sqlite3.Connection) -> None:
    """Siembra el catálogo de módulos del clasificador. No reactiva ni sobrescribe
    personalizaciones del usuario: solo crea nombres faltantes y completa
    descripciones vacías conocidas."""
    from src.core.historical_partida_classifier import MODULE_DESCRIPTIONS

    for nombre, descripcion in MODULE_DESCRIPTIONS.items():
        conn.execute(
            "INSERT OR IGNORE INTO execution_module (nombre, descripcion) VALUES (?, ?)",
            (nombre, descripcion),
        )
        conn.execute(
            "UPDATE execution_module SET descripcion=? WHERE nombre=? AND (descripcion IS NULL OR descripcion='')",
            (descripcion, nombre),
        )
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


# Version explicita del esquema. Se incrementa al añadir una migracion nueva
# a _MIGRATIONS; una BDD nueva se crea ya en esta version (las CREATE TABLE
# de _SCHEMA_SQL/_HISTORICAL_SCHEMA_SQL incluyen todas las columnas).
CURRENT_SCHEMA_VERSION = 3

# Migraciones ordenadas e idempotentes (cada una comprueba su propio estado
# antes de tocar nada). Se ejecutan en este orden porque el seed de módulos
# depende de que la columna 'descripcion' ya exista.
_MIGRATIONS = [
    _migrate_administracion_nombre,
    _migrate_comunidad_cif,
    _migrate_presupuesto_v2,
    _ensure_presupuesto_v2_indexes,
    _migrate_execution_module_descripcion,
    _seed_execution_modules,
    _migrate_historical_budget_source_kind,
    _migrate_pattern_evidence_columns,
]


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Version de esquema registrada en la BDD, o 0 si aun no se ha marcado."""
    cur = conn.execute("SELECT version FROM schema_version WHERE id=1")
    row = cur.fetchone()
    return int(row[0]) if row else 0


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    conn.execute(
        """INSERT INTO schema_version (id, version) VALUES (1, ?)
           ON CONFLICT(id) DO UPDATE SET version=excluded.version""",
        (version,),
    )
    conn.commit()


# Guarda de reentrada: create_database_backup() registra un evento mediante
# log_historical_memory_event(), que abre OTRA conexión y por tanto vuelve a
# llamar a init_schema(). Sin esta guarda, esa conexión anidada vería la
# version todavia sin marcar y dispararia otro backup recursivamente.
_MIGRATION_IN_PROGRESS = False


def init_schema(conn: sqlite3.Connection) -> None:
    """
    Crea las tablas si no existen. No modifica tablas ya existentes.

    Si el fichero fue reemplazado por otro .db que ya tiene estas tablas,
    no hace nada. Si fue reemplazado por un .db vacío, crea las tablas.

    Ejecuta las migraciones pendientes hasta CURRENT_SCHEMA_VERSION solo si
    la BDD no está ya en esa versión (evita repetir el escaneo de columnas en
    cada conexión). Antes de migrar, respalda el fichero original: si algo
    falla a mitad de la secuencia, ese backup es la copia recuperable.
    """
    conn.executescript(_SCHEMA_SQL)
    conn.executescript(_HISTORICAL_SCHEMA_SQL)
    conn.executescript(_CANONICAL_SCHEMA_SQL)
    conn.executescript(_AUDIT_SCHEMA_SQL)
    conn.executescript(_PRICE_REFERENCE_SCHEMA_SQL)
    conn.commit()

    global _MIGRATION_IN_PROGRESS
    current_version = get_schema_version(conn)
    if current_version < CURRENT_SCHEMA_VERSION and not _MIGRATION_IN_PROGRESS:
        _MIGRATION_IN_PROGRESS = True
        try:
            try:
                from src.core.database_backup import create_database_backup

                create_database_backup(
                    f"before_migration_v{current_version}_to_v{CURRENT_SCHEMA_VERSION}"
                )
            except Exception:
                # No bloquear el arranque si el backup falla (p.ej. disco lleno);
                # las migraciones son idempotentes y se pueden reintentar.
                pass

            for migration in _MIGRATIONS:
                migration(conn)
            _set_schema_version(conn, CURRENT_SCHEMA_VERSION)
        finally:
            _MIGRATION_IN_PROGRESS = False

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
CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    version INTEGER NOT NULL DEFAULT 0
);

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
    descripcion TEXT,
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
    error TEXT,
    file_sha256 TEXT,
    source_kind TEXT NOT NULL DEFAULT 'external_excel',
    approved_at TEXT,
    approved_by TEXT
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
    activo INTEGER NOT NULL DEFAULT 1,
    distinct_budget_count INTEGER NOT NULL DEFAULT 0,
    price_spread_ratio REAL,
    latest_source_date TEXT,
    evidence_quality TEXT
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

CREATE TABLE IF NOT EXISTS historical_partida_feature (
    partida_id INTEGER PRIMARY KEY REFERENCES historical_partida(id) ON DELETE CASCADE,
    action TEXT,
    element TEXT,
    system TEXT,
    unit TEXT,
    material TEXT,
    dimensions_json TEXT,
    conditions_json TEXT,
    line_kind TEXT,
    primary_module_id TEXT,
    secondary_module_ids_json TEXT,
    confidence REAL,
    reasons_json TEXT,
    classifier_version TEXT,
    created_at TEXT,
    updated_at TEXT
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

# Dominio canónico de presupuestos (H3). Aditivo, no toca presupuesto/
# presupuesto_partida/historical_*. `presupuesto_legacy_id` es un enlace de
# auditoría, nunca una dependencia de escritura: ninguna operación canónica
# exige que la fila `presupuesto` exista.
_CANONICAL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS budget (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid                   TEXT NOT NULL UNIQUE,
    nombre_proyecto        TEXT NOT NULL,
    numero_proyecto        TEXT,
    presupuesto_legacy_id  INTEGER REFERENCES presupuesto(id) ON DELETE SET NULL,
    estado                 TEXT NOT NULL DEFAULT 'draft' CHECK (estado IN ('draft','approved')),
    active_version_id      INTEGER REFERENCES budget_version(id) ON DELETE SET NULL,
    created_at             TEXT NOT NULL,
    updated_at             TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_budget_legacy  ON budget(presupuesto_legacy_id);
CREATE INDEX IF NOT EXISTS idx_budget_numero  ON budget(numero_proyecto);
CREATE INDEX IF NOT EXISTS idx_budget_estado  ON budget(estado);

CREATE TABLE IF NOT EXISTS budget_version (
    id                            INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_id                     INTEGER NOT NULL REFERENCES budget(id) ON DELETE CASCADE,
    numero_version                INTEGER NOT NULL,
    estado                        TEXT NOT NULL DEFAULT 'draft'
                                      CHECK (estado IN ('draft','approved','superseded')),
    origen                        TEXT NOT NULL DEFAULT 'import'
                                      CHECK (origen IN ('import','manual_edit','ai_edit')),
    subtotal                      REAL,
    iva                           REAL,
    iva_rate                      REAL NOT NULL DEFAULT 0.10,
    total                         REAL,
    superseded_by_version_id      INTEGER REFERENCES budget_version(id) ON DELETE SET NULL,
    reconciliation_warnings_json  TEXT,
    created_at                    TEXT NOT NULL,
    approved_at                   TEXT,
    superseded_at                 TEXT,
    UNIQUE (budget_id, numero_version)
);
CREATE INDEX IF NOT EXISTS idx_budget_version_budget ON budget_version(budget_id, numero_version);
CREATE INDEX IF NOT EXISTS idx_budget_version_estado ON budget_version(estado);

CREATE TABLE IF NOT EXISTS budget_line (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_version_id  INTEGER NOT NULL REFERENCES budget_version(id) ON DELETE CASCADE,
    line_uid           TEXT NOT NULL,
    orden              INTEGER NOT NULL,
    numero             TEXT,
    concepto           TEXT NOT NULL,
    unidad             TEXT,
    cantidad           REAL NOT NULL,
    precio             REAL NOT NULL,
    importe            REAL NOT NULL,
    source             TEXT NOT NULL DEFAULT 'unknown',
    created_at         TEXT NOT NULL,
    UNIQUE (budget_version_id, orden)
);
CREATE INDEX IF NOT EXISTS idx_budget_line_version ON budget_line(budget_version_id, orden);
CREATE INDEX IF NOT EXISTS idx_budget_line_uid     ON budget_line(line_uid);

CREATE TABLE IF NOT EXISTS evidence (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid                TEXT NOT NULL UNIQUE,
    tipo_fuente         TEXT NOT NULL
                            CHECK (tipo_fuente IN
                                ('historical','catalog','ai_estimate','web','manual','legacy_excel')),
    referencia          TEXT,
    fecha_consulta      TEXT NOT NULL,
    modelo_herramienta  TEXT,
    resumen             TEXT,
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evidence_tipo ON evidence(tipo_fuente);

CREATE TABLE IF NOT EXISTS field_evidence (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_line_id  INTEGER NOT NULL REFERENCES budget_line(id) ON DELETE CASCADE,
    campo           TEXT NOT NULL CHECK (campo IN ('precio','cantidad','concepto')),
    evidence_id     INTEGER NOT NULL REFERENCES evidence(id) ON DELETE RESTRICT,
    created_at      TEXT NOT NULL,
    UNIQUE (budget_line_id, campo, evidence_id)
);
CREATE INDEX IF NOT EXISTS idx_field_evidence_line     ON field_evidence(budget_line_id);
CREATE INDEX IF NOT EXISTS idx_field_evidence_evidence ON field_evidence(evidence_id);

CREATE TABLE IF NOT EXISTS document (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_version_id  INTEGER NOT NULL REFERENCES budget_version(id) ON DELETE CASCADE,
    tipo               TEXT NOT NULL CHECK (tipo IN ('excel_import','excel_export','pdf_export')),
    ruta               TEXT NOT NULL,
    hash_sha256        TEXT,
    tamano_bytes       INTEGER,
    created_at         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_document_version ON document(budget_version_id, tipo);

CREATE TABLE IF NOT EXISTS approval (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    budget_version_id  INTEGER NOT NULL UNIQUE REFERENCES budget_version(id) ON DELETE CASCADE,
    aprobado_por       TEXT NOT NULL,
    aprobado_at        TEXT NOT NULL,
    nota               TEXT
);
"""

# H4: registro de auditoria del backend privado (aditiva, sin subir CURRENT_SCHEMA_VERSION).
_AUDIT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL CHECK (event_type IN (
                    'login_success','login_failure','logout',
                    'budget_created','version_created','version_approved',
                    'export_excel','export_pdf','error')),
    email       TEXT,
    budget_id   INTEGER REFERENCES budget(id) ON DELETE SET NULL,
    detail      TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_log_event   ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);
"""

# H5: catalogo de precios de referencia (aditiva, sin subir CURRENT_SCHEMA_VERSION).
_PRICE_REFERENCE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS price_reference (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid                  TEXT NOT NULL UNIQUE,
    concepto              TEXT NOT NULL,
    unidad                TEXT NOT NULL,
    importe               REAL NOT NULL,
    moneda                TEXT NOT NULL DEFAULT 'EUR',
    impuestos_incluidos   INTEGER NOT NULL DEFAULT 0 CHECK (impuestos_incluidos IN (0,1)),
    zona                  TEXT,
    origen                TEXT NOT NULL CHECK (origen IN ('historical','manual')),
    evidence_id           INTEGER REFERENCES evidence(id) ON DELETE SET NULL,
    estado                TEXT NOT NULL DEFAULT 'proposed'
                              CHECK (estado IN ('proposed','approved','rejected','expired')),
    fecha                 TEXT NOT NULL,
    vigente_hasta         TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_price_reference_concepto ON price_reference(concepto, unidad);
CREATE INDEX IF NOT EXISTS idx_price_reference_estado   ON price_reference(estado);
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
