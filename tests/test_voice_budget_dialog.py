"""
Tests de contrato para VoiceBudgetDialog (H1.3): ningún final del diálogo
debe dejar los controles bloqueados ni tocar widgets ya destruidos.
"""

import types

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
    def __init__(self, exc_type=RuntimeError):
        self._exc_type = exc_type

    def generate(self, **kwargs):
        raise self._exc_type("fallo inesperado del proveedor IA")


class _OkOrchestrator:
    def __init__(self, result):
        self._result = result

    def generate(self, **kwargs):
        return self._result


class _PartialThenCompleteOrchestrator:
    def __init__(self, partial, complete):
        self._partial = partial
        self._complete = complete
        self.retry_calls = 0
        self.retry_descripcion = None

    def generate(self, **kwargs):
        return self._partial

    def retry_pending(self, descripcion_libre, previous_result, **kwargs):
        self.retry_calls += 1
        self.retry_descripcion = descripcion_libre
        return self._complete


class _InlineThread:
    """Ejecuta el target en el hilo del test: sin depender del planificador."""

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


class _RetryRaisingOrchestrator:
    def generate(self, **kwargs):
        return _partial_result()

    def retry_pending(self, descripcion_libre, previous_result, **kwargs):
        raise RuntimeError("reintento caido")


def _make_dialog(qapp, orchestrator):
    dlg = VoiceBudgetDialog(parent=None)
    dlg._orchestrator = orchestrator
    return dlg


def _partial_result():
    return {
        "partidas": [{"titulo": "Reparacion fachada", "source": "historical_exact"}],
        "source": "historico",
        "status": "partial",
        "error": "Timeout",
        "cobertura": {
            "partidas_historicas": 1,
            "partidas_ia": 0,
            "modulos_pendientes": ["sustitucion_bajante"],
            "error_ia": "Timeout",
        },
    }


def _complete_result():
    return {
        "partidas": [
            {"titulo": "Reparacion fachada", "source": "historical_exact"},
            {"titulo": "Sustitucion bajante", "source": "ai_completion"},
        ],
        "source": "orquestado",
        "status": "ok",
        "error": None,
        "cobertura": {
            "partidas_historicas": 1,
            "partidas_ia": 1,
            "modulos_pendientes": [],
            "error_ia": None,
        },
    }


@pytest.mark.parametrize("exc_type", [RuntimeError, TimeoutError])
def test_unhandled_exception_in_worker_yields_sanitized_error_and_reenables_controls(qapp, exc_type):
    dlg = _make_dialog(qapp, _RaisingOrchestrator(exc_type))
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
    dlg = _make_dialog(qapp, _OkOrchestrator({"partidas": [], "status": "error", "error": "sin cobertura", "cobertura": {}}))
    dlg._set_buttons_enabled(False)

    dlg._run_generation("Descripción demasiado genérica")

    assert dlg.get_result() is None
    assert dlg._btn_generar.isEnabled()


# H16 (S1-E): Cancelar, Esc y la X deben comportarse igual durante la
# generación; el botón no puede quedar deshabilitado por un camino y libre por
# los otros.
def test_cancel_stays_enabled_while_generating(qapp):
    dlg = _make_dialog(qapp, _OkOrchestrator({"partidas": []}))

    dlg._set_buttons_enabled(False)

    assert dlg._btn_cancelar.isEnabled()
    assert not dlg._btn_generar.isEnabled()


# H16 (S1-E): mientras hay trabajo en vuelo el texto no puede cambiar respecto a
# la copia que tiene el worker, o el presupuesto se aceptaría contra una versión
# distinta de la que ve el usuario.
def test_description_is_read_only_while_generating_and_editable_after(qapp):
    dlg = _make_dialog(
        qapp,
        _OkOrchestrator({"partidas": [], "error": "sin cobertura", "cobertura": {}}),
    )

    dlg._set_buttons_enabled(False)
    assert dlg._txt_descripcion.isReadOnly()

    dlg._run_generation("Sustituir bajante")

    assert not dlg._txt_descripcion.isReadOnly()


# H16 (S1-E): cerrar durante la generación descarta el resultado tardío y deja el
# diálogo rechazado; no puede aceptarse por un resultado que llega después.
def test_closing_during_generation_discards_late_result_and_leaves_no_result(qapp):
    result = {
        "partidas": [{"titulo": "X", "source": "historical"}],
        "source": "historico",
        "error": None,
        "cobertura": {"partidas_historicas": 1},
    }
    dlg = _make_dialog(qapp, _OkOrchestrator(result))

    dlg.reject()  # equivalente a Esc o a la X de la ventana
    dlg._run_generation("Sustituir bajante")

    assert dlg.get_result() is None
    assert dlg.result() == 0  # QDialog.Rejected


# H03 (S1-C): un resultado parcial ya no se acepta en silencio; el usuario
# decide entre reintentar lo pendiente o continuar con lo generado.
def test_partial_result_offers_retry_and_keeps_merged_result(qapp, monkeypatch):
    monkeypatch.setattr(
        "src.gui.voice_budget_dialog.threading",
        types.SimpleNamespace(Thread=_InlineThread),
    )
    orch = _PartialThenCompleteOrchestrator(_partial_result(), _complete_result())
    dlg = _make_dialog(qapp, orch)
    dlg._ask_partial_choice = lambda result: True
    dlg._txt_descripcion.setPlainText("Sustituir bajante")

    dlg._on_generar()

    assert orch.retry_calls == 1
    assert orch.retry_descripcion == "Sustituir bajante"
    assert dlg.get_result()["status"] == "ok"
    assert len(dlg.get_result()["partidas"]) == 2
    assert dlg.result() == 1  # QDialog.Accepted
    assert dlg._btn_generar.isEnabled()


# H03 (S1-C): si el usuario prefiere continuar, el parcial se conserva tal cual
# y no se dispara ninguna llamada de reintento.
def test_partial_result_is_accepted_untouched_when_user_continues(qapp, monkeypatch):
    monkeypatch.setattr(
        "src.gui.voice_budget_dialog.threading",
        types.SimpleNamespace(Thread=_InlineThread),
    )
    partial = _partial_result()
    orch = _PartialThenCompleteOrchestrator(partial, _complete_result())
    dlg = _make_dialog(qapp, orch)
    dlg._ask_partial_choice = lambda result: False
    dlg._txt_descripcion.setPlainText("Sustituir bajante")

    dlg._on_generar()

    assert orch.retry_calls == 0
    assert dlg.get_result() == partial
    assert dlg.get_result()["status"] == "partial"
    assert len(dlg.get_result()["partidas"]) == 1
    assert dlg.result() == 1  # QDialog.Accepted


# H03 (S1-C): si el reintento revienta con una excepción inesperada, el motivo
# mostrado (cobertura['error_ia']) es el nuevo fallo, no el del intento previo.
def test_retry_exception_surfaces_new_motive_and_keeps_partidas(qapp):
    dlg = _make_dialog(qapp, _RetryRaisingOrchestrator())
    dlg._ask_partial_choice = lambda result: False
    partial = _partial_result()

    dlg._run_retry(partial)

    result = dlg.get_result()
    assert result["partidas"] == partial["partidas"]
    assert result["status"] == "partial"
    assert "reintento caido" in result["cobertura"]["error_ia"]
    assert result["cobertura"]["modulos_pendientes"] == ["sustitucion_bajante"]
    assert dlg.result() == 1  # QDialog.Accepted
