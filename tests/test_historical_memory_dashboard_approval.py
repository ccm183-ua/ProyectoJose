"""
H06: incluir desde el panel de memoria debe pasar por
approve_budget_for_learning (único camino que registra approved_by/approved_at),
no por el setter genérico que dejaba la aprobación sin actor ni fecha.
"""

import pytest

try:
    from PySide6.QtWidgets import QDialog

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


def _make_dashboard(qapp, monkeypatch):
    dlg = HistoricalMemoryDashboard.__new__(HistoricalMemoryDashboard)
    QDialog.__init__(dlg)
    dlg._analyzer = type(
        "FakeAnalyzer",
        (),
        {"reclassify_budget_modules": lambda self, budget_id: {"ok": True}},
    )()
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
