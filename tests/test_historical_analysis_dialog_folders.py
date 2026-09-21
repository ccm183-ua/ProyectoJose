"""
H19: el diálogo de análisis multicarpetas trata la lista completa como el
conjunto de fuentes, lo precarga al reabrir y lo persiste entero.
"""

import pytest

try:
    from PySide6.QtWidgets import QApplication

    from src.core.settings import Settings
    from src.gui import historical_analysis_dialog as dialog_mod
    from src.gui.historical_analysis_dialog import HistoricalAnalysisDialog

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


def test_dialog_preloads_all_remembered_folders(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_CONFIG_DIR", str(tmp_path / "config"))
    Settings().set_historical_folders([str(tmp_path / "a"), str(tmp_path / "b")])

    dlg = HistoricalAnalysisDialog()

    loaded = [dlg._folder_list.item(i).text() for i in range(dlg._folder_list.count())]
    assert loaded == [str(tmp_path / "a"), str(tmp_path / "b")]


def test_on_run_persists_the_whole_set(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_CONFIG_DIR", str(tmp_path / "config"))
    dlg = HistoricalAnalysisDialog()
    dlg._folder_list.clear()
    dlg._folder_list.addItem(str(tmp_path / "a"))
    dlg._folder_list.addItem(str(tmp_path / "b"))

    captured = []
    monkeypatch.setattr(
        dialog_mod,
        "run_in_background",
        lambda work, done: captured.append((work, done)),
    )

    dlg._on_run()

    assert Settings().get_historical_folders() == [str(tmp_path / "a"), str(tmp_path / "b")]
    assert captured, "el análisis debe lanzarse en segundo plano"
