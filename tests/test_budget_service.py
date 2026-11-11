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


# ---------------------------------------------------------------------------
# Regresión: protección de snapshots finalizados
# ---------------------------------------------------------------------------

def _finalized_partidas(file_path):
    row = db_repository.get_presupuesto_por_ruta(file_path)
    assert row is not None
    from src.core.repositories.presupuesto_cache_repository import get_partidas_de_presupuesto
    return row, get_partidas_de_presupuesto(row["id"])


def _data_without_partidas():
    data = _sample_data()
    data["partidas"] = []
    return data


def test_finalize_with_unreadable_partidas_keeps_existing_snapshot(db_env, tmp_path):
    file_path = str(tmp_path / "obra.xlsx")
    open(file_path, "w").close()
    assert _make_service(_sample_data()).finalize_budget(file_path) is True

    # El Excel se edita y BudgetReader ya no reconoce las partidas.
    ok = _make_service(_data_without_partidas()).finalize_budget(file_path)

    assert ok is False
    row, partidas = _finalized_partidas(file_path)
    assert row["es_finalizado"] == 1
    assert len(partidas) == 1
    assert row["num_partidas"] == 1


def test_refresh_with_unreadable_partidas_keeps_existing_snapshot(db_env, tmp_path):
    file_path = str(tmp_path / "obra.xlsx")
    open(file_path, "w").close()
    assert _make_service(_sample_data()).finalize_budget(file_path) is True

    ok = _make_service(_data_without_partidas()).refresh_budget_cache_entry(file_path)

    assert ok is False
    _row, partidas = _finalized_partidas(file_path)
    assert len(partidas) == 1


def test_orphan_cleanup_never_deletes_finalized_snapshots(db_env, tmp_path):
    from src.core.repositories.presupuesto_cache_repository import (
        limpiar_presupuestos_huerfanos,
    )

    finalizado = str(tmp_path / "finalizado.xlsx")
    open(finalizado, "w").close()
    assert _make_service(_sample_data()).finalize_budget(finalizado) is True

    cache = str(tmp_path / "solo_cache.xlsx")
    _id, err = db_repository.upsert_presupuesto({
        "nombre_proyecto": "Solo cache",
        "ruta_excel": cache,
        "fecha_modificacion_excel": "2026-01-01T00:00:00",
    })
    assert err is None

    # Ninguno de los dos aparece en el escaneo (renombrado, unidad desmontada...).
    eliminados = limpiar_presupuestos_huerfanos([str(tmp_path / "otro.xlsx")])

    assert eliminados == 1
    assert db_repository.get_presupuesto_por_ruta(cache) is None
    _row, partidas = _finalized_partidas(finalizado)
    assert len(partidas) == 1
