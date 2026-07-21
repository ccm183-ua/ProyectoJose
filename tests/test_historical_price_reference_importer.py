"""Tests del importador histórico -> catálogo de precios de referencia (H5)."""

from datetime import datetime

import pytest

from src.core.historical_price_reference_importer import import_price_references_from_historical
from src.core.repositories import insert_historical_partida, upsert_historical_budget
from src.core.repositories.price_reference_repository import list_price_references


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_hist_price_import_test.db"))
    return tmp_path


def _seed_historical_budget(tmp_path, nombre, learning_status, analysis_status="VALID", usable_for_learning=True):
    budget_id, err = upsert_historical_budget(
        {
            "ruta_excel": str(tmp_path / f"{nombre}.xlsx"),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": nombre,
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "analisis_ok": True,
            "analysis_status": analysis_status,
            "usable_for_learning": usable_for_learning,
            "learning_status": learning_status,
        }
    )
    assert err is None
    return budget_id


def _seed_partida(budget_id, concepto_normalizado, unidad, precio):
    partida_id, err = insert_historical_partida(
        budget_id,
        {
            "titulo": concepto_normalizado,
            "concepto_original": concepto_normalizado,
            "concepto_normalizado": concepto_normalizado,
            "unidad": unidad,
            "precio_unitario": precio,
            "cantidad": 1,
            "total_linea": precio,
        },
    )
    assert err is None
    return partida_id


def test_imports_included_historical_partidas_as_proposed(db_env):
    budget_id = _seed_historical_budget(db_env, "obra_incluida", "INCLUDED")
    _seed_partida(budget_id, "sustitucion bajante", "ml", 20.0)

    summary = import_price_references_from_historical()
    assert summary.total_candidatos == 1
    assert summary.importados == 1
    assert summary.errores == []

    refs = list_price_references(concepto="sustitucion bajante", unidad="ml")
    assert len(refs) == 1
    assert refs[0]["origen"] == "historical"
    assert refs[0]["estado"] == "proposed"
    assert refs[0]["importe"] == 20.0


def test_does_not_import_excluded_historical_partidas(db_env):
    budget_id = _seed_historical_budget(db_env, "obra_excluida", "EXCLUDED")
    _seed_partida(budget_id, "pintura fachada", "m2", 12.0)

    summary = import_price_references_from_historical()
    assert summary.total_candidatos == 0
    assert summary.importados == 0
    assert list_price_references(concepto="pintura fachada") == []


def test_running_importer_twice_does_not_duplicate(db_env):
    budget_id = _seed_historical_budget(db_env, "obra_repetida", "INCLUDED")
    _seed_partida(budget_id, "sustitucion bajante", "ml", 20.0)

    first = import_price_references_from_historical()
    assert first.importados == 1

    second = import_price_references_from_historical()
    assert second.importados == 0
    assert second.omitidos_ya_existentes == 1

    assert len(list_price_references(concepto="sustitucion bajante", unidad="ml")) == 1
