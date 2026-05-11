import os

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return app


def test_enhancement_result_does_not_auto_search(monkeypatch, qapp):
    from src.gui import historical_suggestions_dialog as module

    class FakeReviewDialog:
        def __init__(self, parent, result):
            self._result = result

        def exec(self):
            return QtWidgets.QDialog.DialogCode.Rejected

    monkeypatch.setattr(module, "EnhancedDescriptionReviewDialog", FakeReviewDialog)
    dlg = module.HistoricalSuggestionDescriptionDialog(None, {})
    dlg._context_edit.setPlainText("reparar bajante y pintar patio")

    dlg._on_enhancement_done(
        {
            "original_description": "reparar bajante y pintar patio",
            "enhanced_description": "Descripcion tecnica mejorada",
            "warnings": [],
            "error": "",
        }
    )

    assert dlg.wants_search() is False
    assert dlg.get_confirmed_context() == ""


def test_search_uses_confirmed_user_description(qapp):
    from src.gui.historical_suggestions_dialog import HistoricalSuggestionDescriptionDialog

    dlg = HistoricalSuggestionDescriptionDialog(None, {})
    text = "Reparacion de bajante en patio interior con pintura de paramentos afectados"
    dlg._context_edit.setPlainText(text)
    dlg._on_search()

    assert dlg.wants_search() is True
    assert dlg.get_confirmed_context() == text


def test_enhance_button_disabled_without_api_key(monkeypatch, tmp_path, qapp):
    monkeypatch.delenv("CUBIAPP_GEMINI_KEY", raising=False)
    monkeypatch.delenv("CUBIAPP_DEEPSEEK_KEY", raising=False)
    monkeypatch.setenv("CUBIAPP_CONFIG_DIR", str(tmp_path))

    from src.gui.historical_suggestions_dialog import HistoricalSuggestionDescriptionDialog

    dlg = HistoricalSuggestionDescriptionDialog(None, {})
    dlg._context_edit.setPlainText("arreglar fachada")
    dlg._update_enhance_button()

    assert dlg._btn_enhance.isEnabled() is False
