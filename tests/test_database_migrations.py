"""
Tests de migración e recuperación de BDD (H2.4).

Usa el snapshot legacy en tests/fixtures/legacy_schema_v0.db (datos
ficticios, generado por tests/fixtures/_generate_legacy_snapshot.py) para
probar: migración con preservación de recuentos/relaciones, doble ejecución
idempotente, backup previo a migrar y restauración desde ese backup.
"""

import shutil
import sqlite3
from pathlib import Path

import pytest

from src.core import database

FIXTURES_DIR = Path(__file__).parent / "fixtures"
LEGACY_SNAPSHOT = FIXTURES_DIR / "legacy_schema_v0.db"


@pytest.fixture
def legacy_db_env(tmp_path, monkeypatch):
    """Copia el snapshot legacy a un .db temporal y fija CUBIAPP_DB_PATH/BACKUP_DIR."""
    db_path = tmp_path / "datos.db"
    shutil.copy2(LEGACY_SNAPSHOT, db_path)
    backup_dir = tmp_path / "backups"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
    monkeypatch.setenv("CUBIAPP_BACKUP_DIR", str(backup_dir))
    return db_path, backup_dir


def _columns(conn: sqlite3.Connection, table: str) -> set:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_migrates_legacy_snapshot_preserving_counts_and_relations(legacy_db_env):
    db_path, _ = legacy_db_env

    with database.get_connection() as conn:
        assert database.get_schema_version(conn) == database.CURRENT_SCHEMA_VERSION

        assert "nombre" in _columns(conn, "administracion")
        assert "cif" in _columns(conn, "comunidad")
        assert "descripcion" in _columns(conn, "execution_module")
        v2_cols = {"direccion", "es_finalizado", "num_partidas", "calidad_datos"}
        assert v2_cols.issubset(_columns(conn, "presupuesto"))

        assert conn.execute("SELECT COUNT(*) FROM administracion").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM comunidad").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM contacto").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM presupuesto").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM historical_budget").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM historical_partida").fetchone()[0] == 2

        total = conn.execute("SELECT SUM(total_linea) FROM historical_partida").fetchone()[0]
        assert total == 200.0

        comunidad = conn.execute("SELECT administracion_id FROM comunidad WHERE id=1").fetchone()
        presupuesto = conn.execute(
            "SELECT comunidad_id, administracion_id FROM presupuesto WHERE id=1"
        ).fetchone()
        assert comunidad[0] == 1
        assert presupuesto == (1, 1)


def test_migration_is_idempotent_on_double_execution(legacy_db_env):
    with database.get_connection() as conn:
        pass  # primera conexion: dispara la migracion

    with database.get_connection() as conn:
        version_after_first = database.get_schema_version(conn)
        database.init_schema(conn)  # segunda ejecucion explicita
        database.init_schema(conn)  # tercera, por si acaso
        version_after_repeat = database.get_schema_version(conn)

        assert version_after_first == database.CURRENT_SCHEMA_VERSION
        assert version_after_repeat == database.CURRENT_SCHEMA_VERSION
        assert conn.execute("SELECT COUNT(*) FROM historical_partida").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM administracion").fetchone()[0] == 1


def test_backup_is_created_before_migrating_and_restores_original_schema(legacy_db_env):
    db_path, backup_dir = legacy_db_env

    with database.get_connection() as conn:
        pass  # dispara backup + migracion

    backups = list(backup_dir.glob("*before_migration*"))
    assert len(backups) == 1

    backup_conn = sqlite3.connect(backups[0])
    try:
        assert "nombre" not in _columns(backup_conn, "administracion")
        assert backup_conn.execute("SELECT COUNT(*) FROM historical_partida").fetchone()[0] == 2
    finally:
        backup_conn.close()

    # Restauracion: sustituir el fichero activo (ya migrado) por el backup
    # pre-migracion y comprobar que el esquema vuelve a ser el legacy.
    shutil.copy2(backups[0], db_path)
    restored = sqlite3.connect(db_path)
    try:
        assert "nombre" not in _columns(restored, "administracion")
    finally:
        restored.close()


def test_fresh_database_reaches_same_version_as_migrated_legacy_snapshot(
    legacy_db_env, tmp_path, monkeypatch,
):
    with database.get_connection() as conn:
        legacy_version = database.get_schema_version(conn)

    fresh_path = tmp_path / "fresh.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(fresh_path))
    with database.get_connection() as conn:
        fresh_version = database.get_schema_version(conn)

    assert fresh_version == legacy_version == database.CURRENT_SCHEMA_VERSION


_CANONICAL_TABLES = (
    "budget", "budget_version", "budget_line", "evidence", "field_evidence",
    "document", "approval",
)


def test_canonical_schema_tables_exist_in_fresh_and_migrated_database(
    legacy_db_env, tmp_path, monkeypatch,
):
    with database.get_connection() as conn:
        legacy_cols = {t: _columns(conn, t) for t in _CANONICAL_TABLES}
        assert database.get_schema_version(conn) == database.CURRENT_SCHEMA_VERSION

    fresh_path = tmp_path / "fresh_canonical.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(fresh_path))
    with database.get_connection() as conn:
        fresh_cols = {t: _columns(conn, t) for t in _CANONICAL_TABLES}

    for table in _CANONICAL_TABLES:
        assert legacy_cols[table], f"tabla {table} sin columnas en BDD migrada"
        assert legacy_cols[table] == fresh_cols[table], f"columnas de {table} difieren"
