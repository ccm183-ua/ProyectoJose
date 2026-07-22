"""
Tests de contrato para insert_historical_partida: asignación de `orden`.
"""

from datetime import datetime

from src.core.repositories.historical_repository import (
    approve_budget_for_learning,
    get_historical_budget,
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


class TestApproveBudgetForLearning:
    """Fase 4, Tarea 11/12: unico camino de aprobacion humana explicita para
    que un presupuesto entre en la memoria reutilizable (ver Tarea 4)."""

    def test_approve_sets_included_with_manual_source_and_approver(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "approve_ok.db"))
        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / "propio.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "propio.xlsx",
                "fecha_modificacion_excel": datetime.now().isoformat(),
                "analysis_status": "VALID",
                "learning_status": "PENDING_REVIEW",
                "source_kind": "own_final_budget",
            }
        )
        assert err is None

        approve_err = approve_budget_for_learning(budget_id, "SERGIO")
        assert approve_err is None

        stored = get_historical_budget(budget_id)
        assert stored["learning_status"] == "INCLUDED"
        assert stored["learning_status_source"] == "MANUAL"
        assert stored["usable_for_learning"] is True
        assert stored["approved_by"] == "SERGIO"
        assert stored["approved_at"] != ""

    def test_approve_requires_non_empty_approver(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "approve_no_approver.db"))
        budget_id = _crear_presupuesto(tmp_path)

        err = approve_budget_for_learning(budget_id, "")
        assert err is not None
        assert get_historical_budget(budget_id)["learning_status"] != "INCLUDED"

    def test_approve_rejects_technically_invalid_budget(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "approve_invalid.db"))
        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / "invalido.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "invalido.xlsx",
                "fecha_modificacion_excel": datetime.now().isoformat(),
                "analysis_status": "EXCLUDED_INCOMPLETE_DATA",
            }
        )
        assert err is None

        approve_err = approve_budget_for_learning(budget_id, "SERGIO")
        assert approve_err is not None
        assert get_historical_budget(budget_id)["learning_status"] != "INCLUDED"
