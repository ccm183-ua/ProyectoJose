"""R4: el arranque debe pasar por la operacion unica de reconstruccion y
publicacion, y registrar el fallo de publicacion del paquete de contexto
tanto en la ruta con carpetas como en la que solo reconstruye patrones."""

import importlib.util
import logging

import pytest


def _skip_without_pyside():
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 no disponible en entorno de tests")


def _make_frame():
    from src.gui.main_frame import MainFrame

    return MainFrame.__new__(MainFrame)


def _run_inline(monkeypatch):
    from src.utils import helpers

    monkeypatch.setattr(
        helpers,
        "run_in_background",
        lambda work, callback: callback(True, work()),
    )


def test_startup_without_folders_rebuilds_and_publishes(monkeypatch):
    _skip_without_pyside()
    from src.core import historical_budget_analyzer as hba
    from src.core.settings import Settings

    calls = []

    class FakeAnalyzer:
        def analyze_folders(self, *args, **kwargs):
            raise AssertionError("no debe escanear carpetas si no hay configurada")

        def rebuild_patterns_and_publish(self):
            calls.append("rebuild_patterns_and_publish")
            return {"patterns_inserted": 0, "publication_error": None}

    monkeypatch.setattr(Settings, "get_historical_folders", lambda self: [])
    monkeypatch.setattr(hba, "HistoricalBudgetAnalyzer", FakeAnalyzer)
    _run_inline(monkeypatch)

    _make_frame()._schedule_startup_historical_refresh()

    assert calls == ["rebuild_patterns_and_publish"]


def test_startup_without_folders_logs_publication_error(monkeypatch, caplog):
    _skip_without_pyside()
    from src.core import historical_budget_analyzer as hba
    from src.core.settings import Settings

    class FakeAnalyzer:
        def rebuild_patterns_and_publish(self):
            return {"patterns_inserted": 0, "publication_error": "disco lleno"}

    monkeypatch.setattr(Settings, "get_historical_folders", lambda self: [])
    monkeypatch.setattr(hba, "HistoricalBudgetAnalyzer", FakeAnalyzer)
    _run_inline(monkeypatch)

    with caplog.at_level(logging.WARNING):
        _make_frame()._schedule_startup_historical_refresh()

    assert any("disco lleno" in record.getMessage() for record in caplog.records)


def test_startup_with_folders_logs_publication_error(monkeypatch, tmp_path, caplog):
    _skip_without_pyside()
    from src.core import historical_budget_analyzer as hba
    from src.core.settings import Settings

    called = []

    class FakeAnalyzer:
        def analyze_folders(self, folders, recursive=True):
            called.append((list(folders), recursive))
            return {"publication_error": "sin permisos"}

        def rebuild_patterns_and_publish(self):
            raise AssertionError("con carpetas debe escanear, no solo reconstruir")

    monkeypatch.setattr(Settings, "get_historical_folders", lambda self: [str(tmp_path)])
    monkeypatch.setattr(hba, "HistoricalBudgetAnalyzer", FakeAnalyzer)
    _run_inline(monkeypatch)

    with caplog.at_level(logging.WARNING):
        _make_frame()._schedule_startup_historical_refresh()

    assert called == [([str(tmp_path)], True)]
    assert any("sin permisos" in record.getMessage() for record in caplog.records)
