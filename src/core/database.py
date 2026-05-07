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
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def get_db_path() -> Path:
    """
    Ruta del fichero de base de datos.

    Orden de decisión:
    1. Variable de entorno CUBIAPP_DB_PATH (ruta absoluta al .db).
    2. Por defecto: datos.db en la raíz del proyecto.

    Returns:
        Path absoluto al fichero .db
    """
    env_path = os.environ.get("CUBIAPP_DB_PATH")
    if env_path and os.path.isabs(env_path):
        return Path(env_path)
    # Ruta relativa a la raíz del proyecto (donde está src/)
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / "datos.db"


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


def init_schema(conn: sqlite3.Connection) -> None:
    """
    Crea las tablas si no existen. No modifica tablas ya existentes.

    Si el fichero fue reemplazado por otro .db que ya tiene estas tablas,
    no hace nada. Si fue reemplazado por un .db vacío, crea las tablas.
    Ejecuta migraciones para añadir columnas nuevas a tablas existentes.
    """
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    _migrate_administracion_nombre(conn)
    _migrate_comunidad_cif(conn)
    _seed_execution_modules(conn)


def _seed_execution_modules(conn: sqlite3.Connection) -> None:
    """Inserta módulos de ejecución iniciales de forma idempotente."""
    modules = (
        ("demolicion", "obra_civil", "Demolición y desmontajes", "demolicion,demoler,picado,levantado,desmontaje,apertura"),
        ("desmontaje", "obra_civil", "Trabajos de desmontaje", "desmontaje,retirada"),
        ("sustitucion_bajante", "fontaneria", "Sustitución de bajantes", "bajante,pvc,fecales,pluviales,manguito,codo,abrazadera"),
        ("fontaneria", "instalaciones", "Trabajos de fontanería", "fontaneria,tuberia,saneamiento"),
        ("impermeabilizacion", "obra_civil", "Impermeabilización", "impermeabilizacion,tela asfaltica,membrana,filtracion"),
        ("andamio", "medios_auxiliares", "Andamios y medios de elevación", "andamio,plataforma,elevadora"),
        ("medios_auxiliares", "medios_auxiliares", "Medios auxiliares y seguridad", "medio auxiliar,proteccion,seguridad"),
        ("pintura", "acabados", "Pintura y acabados", "pintura,pintado,plastico,revestimiento"),
        ("alicatado", "acabados", "Alicatado y cerámica", "alicatado,azulejo,ceramico,rejuntado"),
        ("enlucido", "acabados", "Enlucidos y enfoscados", "enlucido,enfoscado,mortero"),
        ("gestion_residuos", "logistica", "Gestión de residuos y escombros", "escombro,vertedero,residuo,contenedor,saca"),
        ("limpieza_final", "logistica", "Limpieza final de obra", "limpieza final"),
        ("electricidad", "instalaciones", "Trabajos de electricidad", "electricidad,cableado,cuadro,iluminacion"),
        ("carpinteria", "acabados", "Trabajos de carpintería", "carpinteria,puerta,madera"),
        ("cerrajeria", "acabados", "Trabajos de cerrajería", "cerrajeria,metal,barandilla"),
        ("albanileria", "obra_civil", "Trabajos de albañilería", "albanileria,roza,tabique,recibido,mortero"),
    )
    conn.executemany(
        """INSERT OR IGNORE INTO execution_module (nombre, categoria, descripcion, keywords, activo)
           VALUES (?, ?, ?, ?, 1)""",
        modules,
    )
    conn.commit()


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
    comunidad_id             INTEGER REFERENCES comunidad(id) ON DELETE SET NULL,
    administracion_id        INTEGER REFERENCES administracion(id) ON DELETE SET NULL,
    fecha_modificacion_excel TEXT NOT NULL,
    fecha_cache              TEXT NOT NULL,
    datos_completos          INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_presupuesto_numero ON presupuesto(numero_proyecto);
CREATE INDEX IF NOT EXISTS idx_presupuesto_estado ON presupuesto(estado);
CREATE INDEX IF NOT EXISTS idx_presupuesto_ruta ON presupuesto(ruta_excel);

-- Ejecuciones de análisis histórico
CREATE TABLE IF NOT EXISTS historical_analysis_run (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_inicio TEXT NOT NULL,
    fecha_fin TEXT,
    carpeta_origen TEXT,
    total_archivos INTEGER DEFAULT 0,
    archivos_procesados INTEGER DEFAULT 0,
    archivos_omitidos INTEGER DEFAULT 0,
    archivos_error INTEGER DEFAULT 0,
    estado TEXT,
    error TEXT
);

-- Presupuestos históricos analizados
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
    fecha_analisis TEXT NOT NULL,
    num_partidas INTEGER DEFAULT 0,
    analysis_run_id INTEGER REFERENCES historical_analysis_run(id) ON DELETE SET NULL,
    analisis_ok INTEGER DEFAULT 0,
    error TEXT
);

-- Partidas extraídas de presupuestos históricos
CREATE TABLE IF NOT EXISTS historical_partida (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    historical_budget_id INTEGER NOT NULL REFERENCES historical_budget(id) ON DELETE CASCADE,
    orden INTEGER,
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
    created_at TEXT NOT NULL
);

-- Módulos de ejecución reutilizables
CREATE TABLE IF NOT EXISTS execution_module (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    categoria TEXT,
    descripcion TEXT,
    keywords TEXT,
    activo INTEGER DEFAULT 1
);

-- Relación N:M partida <-> módulo
CREATE TABLE IF NOT EXISTS historical_partida_module (
    partida_id INTEGER NOT NULL REFERENCES historical_partida(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES execution_module(id) ON DELETE CASCADE,
    confidence REAL DEFAULT 1.0,
    source TEXT DEFAULT 'rules',
    PRIMARY KEY (partida_id, module_id)
);

-- Resumen de módulos por presupuesto
CREATE TABLE IF NOT EXISTS budget_module_summary (
    historical_budget_id INTEGER NOT NULL REFERENCES historical_budget(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES execution_module(id) ON DELETE CASCADE,
    num_partidas INTEGER DEFAULT 0,
    total_importe REAL DEFAULT 0,
    porcentaje_presupuesto REAL DEFAULT 0,
    PRIMARY KEY (historical_budget_id, module_id)
);

-- Plantillas aprendidas
CREATE TABLE IF NOT EXISTS suggestion_template (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    tipo_obra_normalizado TEXT,
    descripcion TEXT,
    min_confidence REAL DEFAULT 0.0,
    num_presupuestos_base INTEGER DEFAULT 0,
    fecha_actualizacion TEXT NOT NULL,
    activo INTEGER DEFAULT 1
);

-- Módulos por plantilla
CREATE TABLE IF NOT EXISTS suggestion_template_module (
    template_id INTEGER NOT NULL REFERENCES suggestion_template(id) ON DELETE CASCADE,
    module_id INTEGER NOT NULL REFERENCES execution_module(id) ON DELETE CASCADE,
    frecuencia REAL DEFAULT 0,
    obligatorio INTEGER DEFAULT 0,
    orden INTEGER DEFAULT 0,
    PRIMARY KEY (template_id, module_id)
);

-- Patrones reutilizables de partidas
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
    frecuencia INTEGER DEFAULT 0,
    confianza REAL DEFAULT 0,
    activo INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_historical_budget_ruta ON historical_budget(ruta_excel);
CREATE INDEX IF NOT EXISTS idx_historical_budget_mtime ON historical_budget(fecha_modificacion_excel);
CREATE INDEX IF NOT EXISTS idx_historical_partida_budget ON historical_partida(historical_budget_id);
CREATE INDEX IF NOT EXISTS idx_historical_partida_module_module ON historical_partida_module(module_id);
CREATE INDEX IF NOT EXISTS idx_suggested_partida_pattern_module ON suggested_partida_pattern(module_id);
CREATE INDEX IF NOT EXISTS idx_suggested_partida_pattern_concepto ON suggested_partida_pattern(concepto_normalizado);
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
