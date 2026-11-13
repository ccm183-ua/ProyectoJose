"""El esquema se aplica una sola vez por proceso y ruta de BD.

Antes cada conexión reejecutaba ``init_schema`` (5 scripts + commit), lo que
costaba ~5 ms por conexión y cientos de conexiones por recarga del dashboard.
"""

import os

import pytest

from src.core import database


@pytest.fixture
def init_counter(monkeypatch):
    calls = []
    original = database.init_schema

    def _counting(conn):
        calls.append(1)
        return original(conn)

    monkeypatch.setattr(database, "init_schema", _counting)
    database.invalidate_schema_cache()
    yield calls
    database.invalidate_schema_cache()


def _tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_schema_applied_once_for_repeated_connections(tmp_path, monkeypatch, init_counter):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "a.db"))

    with database.get_connection():
        pass
    after_first = len(init_counter)
    assert after_first >= 1

    for _ in range(3):
        with database.get_connection() as conn:
            conn.execute("SELECT 1")

    assert len(init_counter) == after_first


def test_schema_reapplied_when_db_file_deleted(tmp_path, monkeypatch, init_counter):
    db_path = tmp_path / "b.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
    with database.get_connection():
        pass
    after_first = len(init_counter)
    os.remove(db_path)

    with database.get_connection() as conn:
        assert "presupuesto" in _tables(conn)
    assert len(init_counter) > after_first


def test_invalidate_forces_schema_on_next_connection(tmp_path, monkeypatch, init_counter):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "c.db"))
    with database.get_connection():
        pass
    after_first = len(init_counter)

    database.invalidate_schema_cache()
    with database.get_connection():
        pass

    assert len(init_counter) == after_first + 1


def test_each_db_path_initialized_separately(tmp_path, monkeypatch, init_counter):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "d1.db"))
    with database.get_connection():
        pass
    after_first = len(init_counter)
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "d2.db"))
    with database.get_connection() as conn:
        assert "presupuesto" in _tables(conn)

    assert len(init_counter) > after_first
