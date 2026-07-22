"""
Fixes histórico evidenciado, Tarea 6: la aprobación explícita del diálogo de
resultados debe pasar por approve_budget_for_learning (Tarea 1, único camino
que registra approved_by/approved_at), no por el genérico
set_historical_budget_learning_status, y debe pedir confirmación nombrando
el archivo antes de aprobar memoria histórica reutilizable.
"""

import pytest

try:
    from PySide6.QtWidgets import QDialog

    from src.gui import historical_analysis_results_dialog as dialog_mod
    from src.gui.historical_analysis_results_dialog import HistoricalAnalysisResultsDialog

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


def _make_dialog(qapp, monkeypatch):
    dlg = HistoricalAnalysisResultsDialog.__new__(HistoricalAnalysisResultsDialog)
    QDialog.__init__(dlg)
    dlg._analyzer = type(
        "FakeAnalyzer", (), {"reclassify_budget_modules": lambda self, budget_id: {"ok": True}}
    )()
    monkeypatch.setattr(dialog_mod, "QMessageBox", _NoUiMessageBox)
    monkeypatch.setattr(dlg, "_rebuild_patterns", lambda: None)
    monkeypatch.setattr(dialog_mod, "append_budget_issue", lambda *a, **k: None)
    monkeypatch.setattr(dialog_mod, "get_historical_budget_partidas", lambda *a, **k: [{"precio_unitario": 10.0}])
    monkeypatch.setattr(dlg, "_reload_rows", lambda: None)
    _NoUiMessageBox.reset()
    return dlg


def test_include_valid_file_asks_confirmation_naming_the_file_and_calls_approve(qapp, monkeypatch):
    dlg = _make_dialog(qapp, monkeypatch)
    calls = []
    monkeypatch.setattr(
        dialog_mod,
        "approve_budget_for_learning",
        lambda budget_id, approved_by: calls.append((budget_id, approved_by)) or None,
    )
    monkeypatch.setattr(
        dialog_mod,
        "set_historical_budget_learning_status",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe usarse este camino para aprobar")),
    )

    data = {"id": 7, "analysis_status": "VALID", "ruta_excel": r"C:\obras\historico_fachada.xlsx"}
    parent = QDialog()

    dlg._include_selected(data, parent)

    assert calls == [(7, dlg._current_user())]
    question_calls = [c for c in _NoUiMessageBox.calls if c[0] == "question"]
    assert len(question_calls) == 1
    message = question_calls[0][1][2]
    assert "historico_fachada.xlsx" in message


def test_include_cancelled_confirmation_does_not_approve(qapp, monkeypatch):
    dlg = _make_dialog(qapp, monkeypatch)

    class _DeclineMessageBox(_NoUiMessageBox):
        @classmethod
        def question(cls, *args, **kwargs):
            cls.calls.append(("question", args))
            return cls.StandardButton.No

    monkeypatch.setattr(dialog_mod, "QMessageBox", _DeclineMessageBox)
    _DeclineMessageBox.reset()

    calls = []
    monkeypatch.setattr(
        dialog_mod,
        "approve_budget_for_learning",
        lambda budget_id, approved_by: calls.append((budget_id, approved_by)) or None,
    )

    data = {"id": 9, "analysis_status": "VALID", "ruta_excel": r"C:\obras\otro.xlsx"}
    dlg._include_selected(data, QDialog())

    assert calls == []


def test_include_button_disabled_when_not_valid(qapp, monkeypatch):
    dlg = _make_dialog(qapp, monkeypatch)
    assert dlg._can_be_included_in_memory({"analysis_status": "NOT_COMPATIBLE"}) is False
    assert dlg._can_be_included_in_memory({"analysis_status": "VALID"}) is True
    assert dlg._can_be_included_in_memory({"analysis_status": "VALID_WITH_WARNINGS"}) is True
