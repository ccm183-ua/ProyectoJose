"""Tests del registro de auditoria del backend privado (H4)."""

import sqlite3

import pytest

from src.core import database
from src.core.repositories.audit_log_repository import record_event


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_audit_test.db"))
    return tmp_path


def test_record_event_inserts_row(db_env):
    err = record_event("login_success", email="cayetanocanovas13@gmail.com")
    assert err is None

    with database.get_connection() as conn:
        rows = conn.execute("SELECT event_type, email FROM audit_log").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "login_success"
    assert rows[0][1] == "cayetanocanovas13@gmail.com"


def test_record_event_rejects_unknown_event_type(db_env):
    err = record_event("no_existe")
    assert err is not None
    assert "no valido" in err.lower()


def test_audit_log_check_constraint_rejects_invalid_event_type_at_db_level(db_env):
    with database.get_connection() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO audit_log (event_type, created_at) VALUES ('no_existe', '2026-01-01 00:00:00')"
            )
