"""
Tests de contrato para insert_historical_partida: asignación de `orden`.
"""

from datetime import datetime

from src.core.repositories.historical_repository import (
    insert_historical_partida,
    upsert_historical_budget,
)


def _crear_presupuesto(tmp_path, nombre="test.xlsx"):
    budget_id, err = upsert_historical_budget(
        {
            "ruta_excel": str(tmp_path / nombre),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": nombre,
            "fecha_modificacion_excel": datetime.now().isoformat(),
        }
    )
    assert err is None
    return budget_id


def test_insert_respects_explicit_orden(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "orden_explicito.db"))
    budget_id = _crear_presupuesto(tmp_path)

    partida_id, err = insert_historical_partida(
        budget_id, {"concepto_original": "Item", "unidad": "ud", "orden": 5}
    )
    assert err is None

    from src.core import database

    with database.get_connection(read_only=True) as conn:
        row = conn.execute(
            "SELECT orden FROM historical_partida WHERE id=?", (partida_id,)
        ).fetchone()
    assert row[0] == 5


def test_insert_assigns_next_orden_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "orden_ausente.db"))
    budget_id = _crear_presupuesto(tmp_path)

    partida_id, err = insert_historical_partida(
        budget_id, {"concepto_original": "Item sin orden", "unidad": "ud"}
    )
    assert err is None

    from src.core import database

    with database.get_connection(read_only=True) as conn:
        row = conn.execute(
            "SELECT orden FROM historical_partida WHERE id=?", (partida_id,)
        ).fetchone()
    assert row[0] == 1


def test_insert_assigns_incrementing_orden_across_consecutive_inserts(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "orden_consecutivo.db"))
    budget_id = _crear_presupuesto(tmp_path)

    id1, err1 = insert_historical_partida(budget_id, {"concepto_original": "A", "unidad": "ud"})
    id2, err2 = insert_historical_partida(budget_id, {"concepto_original": "B", "unidad": "ud"})
    assert err1 is None and err2 is None

    from src.core import database

    with database.get_connection(read_only=True) as conn:
        rows = conn.execute(
            "SELECT id, orden FROM historical_partida WHERE historical_budget_id=? ORDER BY id",
            (budget_id,),
        ).fetchall()
    assert rows == [(id1, 1), (id2, 2)]
