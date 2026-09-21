"""
H06: incluir desde el panel de memoria debe pasar por
approve_budget_for_learning (único camino que registra approved_by/approved_at),
no por el setter genérico que dejaba la aprobación sin actor ni fecha.
"""

import pytest

try:
    from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QToolButton

    from src.gui import historical_memory_dashboard as dash_mod
    from src.gui.historical_memory_dashboard import HistoricalMemoryDashboard

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


class _NoUiMessageBox:
    class StandardButton:
        Yes = 1
        No = 0

    calls = []

    @classmethod
    def reset(cls):
        cls.calls = []

    @classmethod
    def information(cls, *args, **kwargs):
        cls.calls.append(("information", args))
        return 0

    @classmethod
    def warning(cls, *args, **kwargs):
        cls.calls.append(("warning", args))
        return 0

    @classmethod
    def question(cls, *args, **kwargs):
        cls.calls.append(("question", args))
        return cls.StandardButton.Yes


def _run_inline(work, callback):
    """run_in_background sin hilo (mismo contrato de resultado) para probar el comportamiento."""
    try:
        outcome = (True, work())
    except Exception as exc:
        outcome = (False, exc)
    callback(*outcome)


def _make_dashboard(qapp, monkeypatch):
    dlg = HistoricalMemoryDashboard.__new__(HistoricalMemoryDashboard)
    QDialog.__init__(dlg)
    dlg._busy = False
    dlg._closed = False
    dlg._btn_actions = QToolButton(dlg)
    dlg._btn_maintenance = QToolButton(dlg)
    dlg._btn_diagnostics = QPushButton(dlg)
    dlg._stats_lbl = QLabel(dlg)
    dlg._analyzer = type(
        "FakeAnalyzer",
        (),
        {
            "reclassify_budget_modules": lambda self, budget_id: {"ok": True},
            "rebuild_patterns_and_publish": lambda self: {"patterns_inserted": 0, "publication_error": None},
        },
    )()
    monkeypatch.setattr(dash_mod, "run_in_background", _run_inline)
    monkeypatch.setattr(dash_mod, "QMessageBox", _NoUiMessageBox)
    monkeypatch.setattr(dash_mod, "append_budget_issue", lambda *a, **k: None)
    monkeypatch.setattr(dlg, "_rebuild_patterns", lambda silent=False: None)
    monkeypatch.setattr(dlg, "_reload", lambda: None)
    monkeypatch.setattr(
        dlg,
        "_selected_rows_data",
        lambda: [{"id": 7, "analysis_status": "VALID"}],
    )
    _NoUiMessageBox.reset()
    return dlg


def test_include_selected_approves_with_current_user(qapp, monkeypatch):
    dlg = _make_dashboard(qapp, monkeypatch)
    calls = []
    monkeypatch.setattr(
        dash_mod,
        "approve_budget_for_learning",
        lambda budget_id, approved_by: calls.append((budget_id, approved_by)) or None,
    )
    monkeypatch.setattr(
        dash_mod,
        "set_historical_budget_learning_status",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("el setter genérico no registra actor/fecha de aprobación")
        ),
    )

    dlg._include_selected()

    assert calls == [(7, dlg._current_user())]


def test_rebuild_patterns_uses_single_rebuild_and_publish_operation(qapp, monkeypatch):
    """H09/R4: reconstruir cambia la memoria y debe republicar el paquete en la
    misma operacion, no en dos pasos que puedan quedarse a medias."""
    dlg = _make_dashboard(qapp, monkeypatch)
    calls = []
    dlg._analyzer = type(
        "FakeAnalyzer",
        (),
        {
            "rebuild_patterns_and_publish": lambda self: calls.append(True)
            or {"patterns_inserted": 1, "publication_error": None}
        },
    )()
    monkeypatch.setattr(dlg, "_refresh_kpis", lambda: None)

    HistoricalMemoryDashboard._rebuild_patterns(dlg, silent=True)

    assert calls == [True]


def test_rebuild_patterns_warns_when_publication_fails(qapp, monkeypatch):
    dlg = _make_dashboard(qapp, monkeypatch)
    dlg._analyzer = type(
        "FakeAnalyzer",
        (),
        {
            "rebuild_patterns_and_publish": lambda self: {
                "patterns_inserted": 1,
                "publication_error": "disco lleno",
            }
        },
    )()
    monkeypatch.setattr(dlg, "_refresh_kpis", lambda: None)
    _NoUiMessageBox.reset()

    HistoricalMemoryDashboard._rebuild_patterns(dlg, silent=True)

    warnings = [c for c in _NoUiMessageBox.calls if c[0] == "warning"]
    assert warnings
    assert "disco lleno" in warnings[0][1][2]


def test_publish_context_pack_warns_when_publication_fails(qapp, monkeypatch):
    dlg = _make_dashboard(qapp, monkeypatch)
    dlg._analyzer = type(
        "FakeAnalyzer",
        (),
        {"publish_context_pack": lambda self: "disco lleno"},
    )()

    dlg._publish_context_pack()

    warnings = [c for c in _NoUiMessageBox.calls if c[0] == "warning"]
    assert warnings
    assert "disco lleno" in warnings[0][1][2]

# --- H10: el trabajo pesado del panel corre fuera del hilo de interfaz -----------


def _wait(qapp, predicate, timeout=5.0):
    import time

    end = time.time() + timeout
    while not predicate() and time.time() < end:
        qapp.processEvents()
        time.sleep(0.01)
    return predicate()


def test_h10_rebuild_runs_off_ui_thread_and_locks_controls(qapp, monkeypatch):
    import threading

    dlg = _make_dashboard(qapp, monkeypatch)
    monkeypatch.undo()  # restaura run_in_background real
    monkeypatch.setattr(dash_mod, "QMessageBox", _NoUiMessageBox)
    monkeypatch.setattr(dlg, "_reload", lambda: None)
    ui_thread = threading.get_ident()
    seen = {}
    release = threading.Event()

    def _work():
        seen["worker_thread"] = threading.get_ident()
        seen["controls_locked"] = not dlg._btn_actions.isEnabled()
        release.wait(2)
        return "ok"

    def _done(result):
        seen["done_thread"] = threading.get_ident()
        seen["result"] = result

    dlg._run_busy("Prueba", _work, _done)
    assert dlg._busy is True
    assert not dlg._btn_maintenance.isEnabled()
    release.set()
    assert _wait(qapp, lambda: "result" in seen)

    assert seen["worker_thread"] != ui_thread
    assert seen["done_thread"] == ui_thread
    assert seen["controls_locked"] is True
    assert dlg._busy is False
    assert dlg._btn_actions.isEnabled()


def test_h10_second_operation_is_rejected_while_busy(qapp, monkeypatch):
    dlg = _make_dashboard(qapp, monkeypatch)
    dlg._busy = True
    ran = []

    dlg._run_busy("Otra", lambda: ran.append(1), lambda r: ran.append(2))

    assert ran == []
    assert any(c[0] == "information" for c in _NoUiMessageBox.calls)


def test_h10_result_is_discarded_if_dialog_closed_meanwhile(qapp, monkeypatch):
    dlg = _make_dashboard(qapp, monkeypatch)
    done = []

    def _work():
        dlg._closed = True
        return "x"

    dlg._run_busy("Prueba", _work, lambda r: done.append(r))

    assert done == []
    assert dlg._busy is False


def test_h10_worker_exception_unlocks_controls_and_warns(qapp, monkeypatch):
    dlg = _make_dashboard(qapp, monkeypatch)
    monkeypatch.setattr(dlg, "_reload", lambda: None)

    def _boom():
        raise RuntimeError("fallo simulado")

    dlg._run_busy("Prueba", _boom, lambda r: None)

    assert dlg._busy is False
    assert dlg._btn_actions.isEnabled()
    warnings = [c for c in _NoUiMessageBox.calls if c[0] == "warning"]
    assert warnings and "fallo simulado" in warnings[0][1][2]

