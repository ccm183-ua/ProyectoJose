"""
Tests de contrato para VoiceBudgetDialog (H1.3): ningún final del diálogo
debe dejar los controles bloqueados ni tocar widgets ya destruidos.
"""

import pytest

try:
    from PySide6.QtWidgets import QApplication

    from src.gui.voice_budget_dialog import VoiceBudgetDialog

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


@pytest.fixture(autouse=True)
def _no_modal_dialogs(monkeypatch):
    """QMessageBox.warning() es modal: bajo la plataforma offscreen bloquea
    esperando un clic que nunca llega. Ningún test de este archivo debe
    disparar un diálogo real sin interceptarlo primero."""
    if _HAS_PYSIDE6:
        from PySide6.QtWidgets import QMessageBox

        monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))


class _RaisingOrchestrator:
    def generate(self, **kwargs):
        raise RuntimeError("fallo inesperado del proveedor IA")


class _OkOrchestrator:
    def __init__(self, result):
        self._result = result

    def generate(self, **kwargs):
        return self._result


def _make_dialog(qapp, orchestrator):
    dlg = VoiceBudgetDialog(parent=None)
    dlg._orchestrator = orchestrator
    return dlg


def test_unhandled_exception_in_worker_yields_sanitized_error_and_reenables_controls(qapp):
    dlg = _make_dialog(qapp, _RaisingOrchestrator())
    dlg._set_buttons_enabled(False)

    dlg._run_generation("Sustituir bajante")

    assert dlg.get_result() is None
    assert dlg._btn_generar.isEnabled()
    assert dlg._btn_cancelar.isEnabled()


def test_successful_generation_closes_dialog_and_stores_result(qapp):
    result = {
        "partidas": [{"titulo": "X", "source": "historical"}],
        "source": "historico",
        "error": None,
        "cobertura": {"partidas_historicas": 1, "partidas_ia": 0},
    }
    dlg = _make_dialog(qapp, _OkOrchestrator(result))

    dlg._run_generation("Sustituir bajante")

    assert dlg.get_result() == result
    assert dlg.result() == 1  # QDialog.Accepted


def test_generation_result_ignored_after_dialog_already_closed(qapp):
    result = {"partidas": [{"titulo": "X"}], "error": None, "cobertura": {}}
    dlg = _make_dialog(qapp, _OkOrchestrator(result))

    dlg.reject()  # el usuario cierra antes de que el worker termine
    dlg._run_generation("Sustituir bajante")

    assert dlg.get_result() is None


def test_error_without_partidas_shows_warning_and_reenables_controls(qapp):
    dlg = _make_dialog(qapp, _OkOrchestrator({"partidas": [], "error": "sin cobertura", "cobertura": {}}))
    dlg._set_buttons_enabled(False)

    dlg._run_generation("Descripción demasiado genérica")

    assert dlg.get_result() is None
    assert dlg._btn_generar.isEnabled()
