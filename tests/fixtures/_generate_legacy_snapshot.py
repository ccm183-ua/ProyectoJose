"""
Genera tests/fixtures/legacy_schema_v0.db: una BDD SQLite con el esquema
anterior a las migraciones de H2.4 (sin columnas nuevas, sin tabla
schema_version), sembrada con datos claramente ficticios para poder probar
que la migración preserva recuentos y relaciones.

Ejecutar una sola vez (o si cambia el esquema legacy de referencia):
    python tests/fixtures/_generate_legacy_snapshot.py
"""

import sqlite3
from pathlib import Path

TARGET = Path(__file__).parent / "legacy_schema_v0.db"

LEGACY_SCHEMA = """
CREATE TABLE administracion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    telefono TEXT,
    direccion TEXT
);

CREATE TABLE comunidad (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    direccion TEXT,
    email TEXT,
    telefono TEXT,
    administracion_id INTEGER NOT NULL REFERENCES administracion(id) ON DELETE RESTRICT
);

CREATE TABLE contacto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    telefono TEXT NOT NULL UNIQUE,
    telefono2 TEXT,
    email TEXT,
    notas TEXT
);

CREATE TABLE administracion_contacto (
    administracion_id INTEGER NOT NULL REFERENCES administracion(id) ON DELETE CASCADE,
    contacto_id INTEGER NOT NULL REFERENCES contacto(id) ON DELETE CASCADE,
    PRIMARY KEY (administracion_id, contacto_id)
);

CREATE TABLE comunidad_contacto (
    comunidad_id INTEGER NOT NULL REFERENCES comunidad(id) ON DELETE CASCADE,
    contacto_id INTEGER NOT NULL REFERENCES contacto(id) ON DELETE CASCADE,
    PRIMARY KEY (comunidad_id, contacto_id)
);

CREATE TABLE historial_presupuesto (
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

CREATE TABLE presupuesto (
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

CREATE TABLE execution_module (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    categoria TEXT,
    activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE historical_budget (
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
    analysis_run_id INTEGER,
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

CREATE TABLE historical_partida (
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
"""

SEED_DATA = """
INSERT INTO administracion (id, email, telefono, direccion)
    VALUES (1, 'admin-legacy-fake@example.test', '600000001', 'Calle Ficticia 1');

INSERT INTO comunidad (id, nombre, direccion, administracion_id)
    VALUES (1, 'Comunidad Legacy Fake', 'Calle Ficticia 2', 1);

INSERT INTO contacto (id, nombre, telefono)
    VALUES (1, 'Contacto Legacy Fake', '600000002');

INSERT INTO comunidad_contacto (comunidad_id, contacto_id) VALUES (1, 1);

INSERT INTO presupuesto (
    id, numero_proyecto, nombre_proyecto, ruta_excel, estado, cliente,
    comunidad_id, administracion_id, fecha_modificacion_excel, fecha_cache, datos_completos
) VALUES (
    1, '1-20', 'Proyecto Legacy Fake', 'C:/fake/legacy.xlsx', 'PRESUPUESTADO',
    'Comunidad Legacy Fake', 1, 1, '2020-01-01T00:00:00', '2020-01-01T00:00:00', 1
);

INSERT INTO historical_budget (id, ruta_excel, nombre_proyecto, fecha_modificacion_excel, analysis_status, usable_for_learning, learning_status)
    VALUES (1, 'C:/fake/historico_legacy.xlsx', 'Historico Legacy Fake', '2020-01-01T00:00:00', 'VALID', 1, 'INCLUDED');

INSERT INTO historical_partida (
    historical_budget_id, orden, titulo, concepto_normalizado, unidad, cantidad, precio_unitario, total_linea
) VALUES
    (1, 1, 'PARTIDA LEGACY UNO.', 'partida legacy uno', 'ud', 1, 100.0, 100.0),
    (1, 2, 'PARTIDA LEGACY DOS.', 'partida legacy dos', 'ml', 2, 50.0, 100.0);
"""


def main() -> None:
    if TARGET.exists():
        TARGET.unlink()
    conn = sqlite3.connect(TARGET)
    try:
        conn.executescript(LEGACY_SCHEMA)
        conn.executescript(SEED_DATA)
        conn.commit()
    finally:
        conn.close()
    print(f"Snapshot legacy generado: {TARGET}")


if __name__ == "__main__":
    main()
