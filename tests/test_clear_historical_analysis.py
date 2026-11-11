"""
Regresión: el borrado total de la memoria histórica debe ser atómico y dejar
un backup antes de borrar (el ADR 0001 la declara única fuente cuando el Excel
original ya no existe).
"""

import os
import sqlite3
from datetime import datetime

import pytest

from src.core import database
from src.core.repositories import (
    clear_all_historical_analysis_data,
    insert_historical_partida,
    upsert_historical_budget,
)


@pytest.fixture
def db_con_historico(tmp_path, monkeypatch):
    db_path = tmp_path / "historico.db"
    backup_dir = tmp_path / "backups"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
    monkeypatch.setenv("CUBIAPP_BACKUP_DIR", str(backup_dir))
    budget_id, err = upsert_historical_budget({
        "ruta_excel": str(tmp_path / "001-26.xlsx"),
        "ruta_carpeta": str(tmp_path),
        "nombre_proyecto": "001-26",
        "fecha_modificacion_excel": datetime.now().isoformat(),
        "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analisis_ok": True,
        "analysis_status": "VALID",
        "total": 100.0,
        "num_partidas": 1,
    })
    assert err is None
    _pid, err = insert_historical_partida(
        int(budget_id),
        {"concepto": "Picado de revestimiento", "unidad": "m2", "cantidad": 1, "precio_unitario": 10},
    )
    assert err is None
    return db_path, backup_dir


def _count(db_path, table):
    con = sqlite3.connect(db_path)
    try:
        return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        con.close()


def test_borrado_total_crea_backup_con_los_datos(db_con_historico):
    db_path, backup_dir = db_con_historico

    ok, detail = clear_all_historical_analysis_data()

    assert ok, detail
    assert _count(db_path, "historical_budget") == 0
    backups = [p for p in backup_dir.iterdir() if "before_clear_historical" in p.name]
    assert len(backups) == 1
    assert _count(backups[0], "historical_budget") == 1
    assert _count(backups[0], "historical_partida") == 1


def test_borrado_total_es_atomico_si_falla_a_mitad(db_con_historico):
    db_path, _backup_dir = db_con_historico
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE TRIGGER falla_borrado BEFORE DELETE ON historical_budget "
        "BEGIN SELECT RAISE(ABORT, 'fallo simulado'); END"
    )
    con.commit()
    con.close()

    ok, detail = clear_all_historical_analysis_data()

    assert ok is False
    assert "fallo simulado" in detail
    # historical_partida se borra ANTES que historical_budget: si el borrado no
    # fuera atómico, las partidas ya se habrían perdido.
    assert _count(db_path, "historical_partida") == 1
    assert _count(db_path, "historical_budget") == 1
