"""
Tests de BudgetService.finalize_budget() (H3): el espejo silencioso hacia el
dominio canonico nunca debe cambiar el resultado del flujo legacy Excel/cache.
"""

import pytest

from src.core import db_repository
from src.core.repositories.canonical_budget_repository import (
    get_active_version,
    get_budget_by_legacy_id,
    get_lines,
    list_versions,
)
from src.core.services.budget_service import BudgetService


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_budget_service_test.db"))
    return tmp_path


class _FakeBudgetReader:
    def __init__(self, data):
        self._data = data

    def read(self, file_path, expected_numero=""):
        return self._data


def _sample_data():
    return {
        "cabecera": {
            "cliente": "Comunidad Test",
            "localidad": "Alicante",
            "codigo_postal": "03001",
            "obra": "Obra de prueba",
            "fecha": "01-01-2026",
        },
        "partidas": [
            {"concepto": "Sustitucion bajante", "unidad": "ml", "cantidad": 10, "precio": 20.0, "importe": 200.0},
        ],
        "total": 220.0,
        "subtotal": 200.0,
        "iva": 20.0,
    }


def _make_service(data):
    return BudgetService(budget_reader=_FakeBudgetReader(data))


def test_finalize_budget_mirrors_to_canonical_domain_as_approved(db_env, tmp_path):
    file_path = str(tmp_path / "obra.xlsx")
    open(file_path, "w").close()
    svc = _make_service(_sample_data())

    ok = svc.finalize_budget(file_path)
    assert ok is True

    legacy = db_repository.get_presupuesto_por_ruta(file_path)
    assert legacy is not None
    budget = get_budget_by_legacy_id(legacy["id"])
    assert budget is not None

    version = get_active_version(budget["id"])
    assert version["estado"] == "approved"
    lines = get_lines(version["id"])
    assert len(lines) == 1
    assert lines[0]["concepto"] == "Sustitucion bajante"


def test_finalize_budget_twice_creates_new_canonical_version(db_env, tmp_path):
    file_path = str(tmp_path / "obra_repetida.xlsx")
    open(file_path, "w").close()
    svc = _make_service(_sample_data())

    assert svc.finalize_budget(file_path) is True
    assert svc.finalize_budget(file_path) is True

    legacy = db_repository.get_presupuesto_por_ruta(file_path)
    budget = get_budget_by_legacy_id(legacy["id"])
    versions = list_versions(budget["id"])
    assert len(versions) == 2
    assert versions[0]["estado"] == "superseded"
    assert versions[1]["estado"] == "approved"


def test_finalize_budget_returns_false_without_canonical_mirror_on_legacy_failure(
    db_env, tmp_path, monkeypatch,
):
    file_path = str(tmp_path / "obra_fallida.xlsx")
    open(file_path, "w").close()
    svc = _make_service(_sample_data())

    monkeypatch.setattr(
        db_repository, "upsert_presupuesto_finalizado", lambda payload, partidas: (None, "fallo forzado"),
    )

    ok = svc.finalize_budget(file_path)
    assert ok is False

    legacy = db_repository.get_presupuesto_por_ruta(file_path)
    assert legacy is None  # nunca se llego a escribir nada, ni legacy ni canonico


def test_finalize_budget_succeeds_even_if_canonical_mirror_reports_failure(
    db_env, tmp_path, monkeypatch,
):
    file_path = str(tmp_path / "obra_espejo_falla.xlsx")
    open(file_path, "w").close()
    svc = _make_service(_sample_data())

    from src.core.canonical_budget_importer import ImportResult

    monkeypatch.setattr(
        "src.core.canonical_budget_importer.import_from_cache_snapshot",
        lambda presupuesto, partidas: ImportResult(success=False, error="fallo simulado del espejo"),
    )

    ok = svc.finalize_budget(file_path)
    assert ok is True  # el flujo legacy no se entera del fallo del espejo

    legacy = db_repository.get_presupuesto_por_ruta(file_path)
    assert legacy is not None
    assert get_budget_by_legacy_id(legacy["id"]) is None  # el espejo realmente fallo


def test_finalize_budget_succeeds_even_if_canonical_mirror_raises(db_env, tmp_path, monkeypatch):
    file_path = str(tmp_path / "obra_espejo_excepcion.xlsx")
    open(file_path, "w").close()
    svc = _make_service(_sample_data())

    def _raise(*args, **kwargs):
        raise RuntimeError("excepcion inesperada del espejo")

    monkeypatch.setattr("src.core.canonical_budget_importer.import_from_cache_snapshot", _raise)

    ok = svc.finalize_budget(file_path)
    assert ok is True
