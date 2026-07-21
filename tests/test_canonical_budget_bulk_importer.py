"""
Tests de la migracion masiva cache -> dominio canonico (H3, paso 6 del
roadmap). Datos ficticios, sin BDD real.
"""

from datetime import datetime

import pytest

from src.core.canonical_budget_bulk_importer import import_all_from_cache
from src.core.repositories.canonical_budget_repository import list_versions
from src.core.repositories.presupuesto_cache_repository import upsert_presupuesto, upsert_presupuesto_finalizado


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_bulk_test.db"))
    return tmp_path


def _finalizar(db_env, nombre, total, partidas):
    payload = {
        "numero_proyecto": f"{nombre}-26",
        "nombre_proyecto": nombre,
        "ruta_excel": str(db_env / f"{nombre}.xlsx"),
        "fecha_modificacion_excel": datetime.now().isoformat(),
        "total": total,
        "num_partidas": len(partidas),
    }
    presupuesto_id, err = upsert_presupuesto_finalizado(payload, partidas)
    assert err is None
    return presupuesto_id


def test_import_all_from_empty_cache_returns_zeroed_summary(db_env):
    summary = import_all_from_cache()
    assert summary.total_presupuestos == 0
    assert summary.importados_ok == 0
    assert summary.fallidos == 0
    assert summary.totales_cuadran is True
    assert summary.partidas_cuadran is True


def test_import_all_from_cache_matches_counts_and_totals(db_env):
    _finalizar(db_env, "obra_a", 220.0, [
        {"orden": 1, "concepto": "Sustitucion bajante", "unidad": "ml", "cantidad": 10, "precio": 20.0, "importe": 200.0},
    ])
    _finalizar(db_env, "obra_b", 132.0, [
        {"orden": 1, "concepto": "Pintura fachada", "unidad": "m2", "cantidad": 10, "precio": 12.0, "importe": 120.0},
    ])

    summary = import_all_from_cache()

    assert summary.total_presupuestos == 2
    assert summary.importados_ok == 2
    assert summary.fallidos == 0
    assert summary.total_partidas_origen == 2
    assert summary.total_partidas_importadas == 2
    assert summary.partidas_cuadran is True
    assert summary.total_importe_origen == pytest.approx(352.0)
    assert summary.total_importe_canonico == pytest.approx(352.0)
    assert summary.totales_cuadran is True


def test_import_all_from_cache_reports_total_mismatch_warning(db_env):
    # total manipulado en cabecera (200.0) frente al recalculado real (220.0)
    _finalizar(db_env, "obra_manipulada", 200.0, [
        {"orden": 1, "concepto": "Sustitucion bajante", "unidad": "ml", "cantidad": 10, "precio": 20.0, "importe": 200.0},
    ])

    summary = import_all_from_cache()

    assert summary.importados_ok == 1
    assert summary.warnings_por_codigo.get("TOTAL_MISMATCH") == 1


def test_import_all_from_cache_is_idempotent_creates_new_versions_on_rerun(db_env):
    _finalizar(db_env, "obra_repetida", 220.0, [
        {"orden": 1, "concepto": "Sustitucion bajante", "unidad": "ml", "cantidad": 10, "precio": 20.0, "importe": 200.0},
    ])

    first = import_all_from_cache()
    second = import_all_from_cache()

    assert first.importados_ok == 1
    assert second.importados_ok == 1
    # mismo budget en ambas pasadas: la segunda anade version 2, no un budget nuevo
    from src.core.repositories.presupuesto_cache_repository import get_presupuesto_por_ruta
    from src.core.repositories.canonical_budget_repository import get_budget_by_legacy_id

    legacy = get_presupuesto_por_ruta(str(db_env / "obra_repetida.xlsx"))
    budget = get_budget_by_legacy_id(legacy["id"])
    versions = list_versions(budget["id"])
    assert len(versions) == 2


def test_import_all_from_cache_records_failure_without_stopping_others(db_env):
    # nombre_proyecto vacio: la BDD lo acepta (NOT NULL solo prohibe NULL, no
    # cadena vacia), pero el importador lo rechaza -> debe registrarse como
    # fallo sin abortar el resto del lote.
    incompleta_id = _finalizar(db_env, "obra_incompleta", 0.0, [])
    from src.core import database

    with database.get_connection() as conn:
        conn.execute("UPDATE presupuesto SET nombre_proyecto='' WHERE id=?", (incompleta_id,))
        conn.commit()

    _finalizar(db_env, "obra_ok", 220.0, [
        {"orden": 1, "concepto": "Sustitucion bajante", "unidad": "ml", "cantidad": 10, "precio": 20.0, "importe": 200.0},
    ])

    summary = import_all_from_cache()

    assert summary.total_presupuestos == 2
    assert summary.importados_ok == 1
    assert summary.fallidos == 1
    assert summary.errores[0]["presupuesto_id"] == incompleta_id
