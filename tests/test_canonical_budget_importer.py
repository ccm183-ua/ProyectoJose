"""
Tests del importador presupuesto/presupuesto_partida -> dominio canonico (H3).

Cada escenario se monta con las funciones de repositorio ya existentes
(presupuesto_cache_repository), sin datos reales ni ficheros Excel.
"""

from datetime import datetime

import pytest

from src.core.canonical_budget_importer import import_from_cache_snapshot
from src.core.repositories.canonical_budget_repository import get_active_version, get_lines, list_versions
from src.core.repositories.presupuesto_cache_repository import upsert_presupuesto


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_importer_test.db"))
    return tmp_path


def _presupuesto(db_env, **overrides):
    data = {
        "nombre_proyecto": "Obra importable",
        "numero_proyecto": "1-26",
        "ruta_excel": str(db_env / "obra.xlsx"),
        "fecha_modificacion_excel": datetime.now().isoformat(),
        "fecha_cache": datetime.now().isoformat(),
        "total": 220.0,
        "subtotal": 200.0,
        "iva": 20.0,
        "es_finalizado": False,
    }
    data.update(overrides)
    legacy_id, err = upsert_presupuesto(data)
    assert err is None
    data["id"] = legacy_id
    return data


def _partidas():
    return [
        {"orden": 1, "concepto": "Sustitucion bajante", "unidad": "ml", "cantidad": 10, "precio": 20.0, "importe": 200.0},
    ]


def test_import_finalizado_creates_approved_version(db_env):
    presupuesto = _presupuesto(db_env, es_finalizado=True)
    result = import_from_cache_snapshot(presupuesto, _partidas())

    assert result.success is True
    assert result.error == ""
    version = get_active_version(result.budget_id)
    assert version["estado"] == "approved"


def test_import_no_finalizado_creates_draft_version(db_env):
    presupuesto = _presupuesto(db_env, es_finalizado=False)
    result = import_from_cache_snapshot(presupuesto, _partidas())

    assert result.success is True
    version = get_active_version(result.budget_id)
    assert version["estado"] == "draft"


def test_import_total_mismatch_generates_warning_with_exact_detail(db_env):
    presupuesto = _presupuesto(db_env, total=300.0)  # real total calculado sera 220.0
    result = import_from_cache_snapshot(presupuesto, _partidas())

    assert result.success is True
    mismatch = next(w for w in result.warnings if w["codigo"] == "TOTAL_MISMATCH")
    assert mismatch["detalle"]["calculado"] == 220.0
    assert mismatch["detalle"]["leido"] == 300.0
    assert mismatch["detalle"]["diferencia"] == 80.0


def test_import_total_within_tolerance_does_not_warn(db_env):
    presupuesto = _presupuesto(db_env, total=220.01)  # dentro de la tolerancia de 0,01
    result = import_from_cache_snapshot(presupuesto, _partidas())

    assert result.success is True
    assert not [w for w in result.warnings if w["codigo"] == "TOTAL_MISMATCH"]


def test_import_total_just_over_tolerance_warns(db_env):
    presupuesto = _presupuesto(db_env, total=220.02)
    result = import_from_cache_snapshot(presupuesto, _partidas())

    assert [w for w in result.warnings if w["codigo"] == "TOTAL_MISMATCH"]


def test_import_missing_concepto_keeps_line_and_warns(db_env):
    presupuesto = _presupuesto(db_env, total=200.0)
    partidas = [{"orden": 1, "concepto": "", "unidad": "ud", "cantidad": 1, "precio": 200.0, "importe": 200.0}]
    result = import_from_cache_snapshot(presupuesto, partidas)

    assert result.success is True
    assert [w for w in result.warnings if w["codigo"] == "MISSING_CONCEPTO"]
    lines = get_lines(get_active_version(result.budget_id)["id"])
    assert len(lines) == 1


def test_import_negative_quantity_warns(db_env):
    presupuesto = _presupuesto(db_env, total=-200.0)
    partidas = [{"orden": 1, "concepto": "Partida rara", "unidad": "ud", "cantidad": -1, "precio": 200.0, "importe": -200.0}]
    result = import_from_cache_snapshot(presupuesto, partidas)

    assert result.success is True
    assert [w for w in result.warnings if w["codigo"] == "NEGATIVE_OR_ZERO_QUANTITY"]


def test_import_duplicate_orden_reassigned_and_warns(db_env):
    presupuesto = _presupuesto(db_env, total=400.0)
    partidas = [
        {"orden": 1, "concepto": "Partida A", "unidad": "ud", "cantidad": 1, "precio": 200.0, "importe": 200.0},
        {"orden": 1, "concepto": "Partida B", "unidad": "ud", "cantidad": 1, "precio": 200.0, "importe": 200.0},
    ]
    result = import_from_cache_snapshot(presupuesto, partidas)

    assert result.success is True
    assert [w for w in result.warnings if w["codigo"] == "DUPLICATE_ORDEN"]
    lines = get_lines(get_active_version(result.budget_id)["id"])
    assert sorted(l["orden"] for l in lines) == [1, 2]


def test_reimport_same_legacy_id_is_idempotent_and_creates_new_version(db_env):
    presupuesto = _presupuesto(db_env)
    first = import_from_cache_snapshot(presupuesto, _partidas())
    assert first.success is True

    second = import_from_cache_snapshot(presupuesto, _partidas())
    assert second.success is True
    assert second.budget_id == first.budget_id
    assert second.budget_version_id != first.budget_version_id

    versions = list_versions(first.budget_id)
    assert len(versions) == 2
    first_version = next(v for v in versions if v["id"] == first.budget_version_id)
    assert first_version["estado"] == "superseded"


def test_import_requires_nombre_proyecto(db_env):
    result = import_from_cache_snapshot({"nombre_proyecto": ""}, [])
    assert result.success is False
    assert "nombre_proyecto" in result.error
