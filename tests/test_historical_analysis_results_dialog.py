"""
Fixes histórico evidenciado, Tarea 6: la aprobación explícita del diálogo de
resultados debe pasar por approve_budget_for_learning (Tarea 1, único camino
que registra approved_by/approved_at), no por el genérico
set_historical_budget_learning_status, y debe pedir confirmación nombrando
el archivo antes de aprobar memoria histórica reutilizable.
"""

import pytest

try:
    from PySide6.QtWidgets import QDialog, QLabel, QPushButton

    from src.gui import busy_operations as busy_mod
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


def _run_inline(work, callback):
    """run_in_background sin hilo (mismo contrato de resultado) para probar el comportamiento."""
    try:
        outcome = (True, work())
    except Exception as exc:
        outcome = (False, exc)
    callback(*outcome)


def _make_dialog(qapp, monkeypatch):
    dlg = HistoricalAnalysisResultsDialog.__new__(HistoricalAnalysisResultsDialog)
    QDialog.__init__(dlg)
    dlg._stats_lbl = QLabel(dlg)
    dlg._write_buttons = (QPushButton(dlg), QPushButton(dlg), QPushButton(dlg))
    dlg._analyzer = type(
        "FakeAnalyzer",
        (),
        {
            "reclassify_budget_modules": lambda self, budget_id: {"ok": True},
            "rebuild_patterns_and_publish": lambda self: {"patterns_inserted": 0, "publication_error": None},
        },
    )()
    monkeypatch.setattr(busy_mod, "run_in_background", _run_inline)
    monkeypatch.setattr(busy_mod, "QMessageBox", _NoUiMessageBox)
    monkeypatch.setattr(dialog_mod, "QMessageBox", _NoUiMessageBox)
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


def test_include_runs_single_rebuild_and_publish_and_closes_detail_dialog(qapp, monkeypatch):
    """El detalle modal se cierra al confirmar y la reconstrucción es la operación única que publica."""
    dlg = _make_dialog(qapp, monkeypatch)
    rebuilds = []
    dlg._analyzer = type(
        "FakeAnalyzer",
        (),
        {
            "reclassify_budget_modules": lambda self, budget_id: {"ok": True},
            "rebuild_patterns_and_publish": lambda self: rebuilds.append(1)
            or {"patterns_inserted": 1, "publication_error": None},
        },
    )()
    monkeypatch.setattr(dialog_mod, "approve_budget_for_learning", lambda *a, **k: None)
    closed = []
    detail = QDialog()
    detail.accept = lambda: closed.append(True)

    dlg._include_selected({"id": 7, "analysis_status": "VALID", "ruta_excel": "x.xlsx"}, detail)

    assert closed == [True]
    assert rebuilds == [1]
    assert [c for c in _NoUiMessageBox.calls if c[0] == "warning"] == []


def test_include_warns_when_publication_fails(qapp, monkeypatch):
    """Un fallo al publicar el paquete tras reconstruir la memoria llega al usuario."""
    dlg = _make_dialog(qapp, monkeypatch)
    dlg._analyzer = type(
        "FakeAnalyzer",
        (),
        {
            "reclassify_budget_modules": lambda self, budget_id: {"ok": True},
            "rebuild_patterns_and_publish": lambda self: {"patterns_inserted": 1, "publication_error": "disco lleno"},
        },
    )()
    monkeypatch.setattr(dialog_mod, "approve_budget_for_learning", lambda *a, **k: None)

    dlg._include_selected({"id": 7, "analysis_status": "VALID", "ruta_excel": "x.xlsx"}, QDialog())

    warnings = [c for c in _NoUiMessageBox.calls if c[0] == "warning"]
    assert len(warnings) == 1
    assert "disco lleno" in warnings[0][1][2]


def test_apply_decisions_writes_in_worker_with_one_rebuild(qapp, monkeypatch):
    dlg = _make_dialog(qapp, monkeypatch)
    rebuilds, approved, excluded = [], [], []
    dlg._analyzer = type(
        "FakeAnalyzer",
        (),
        {
            "reclassify_budget_modules": lambda self, budget_id: {"ok": True},
            "rebuild_patterns_and_publish": lambda self: rebuilds.append(1)
            or {"patterns_inserted": 2, "publication_error": None},
        },
    )()
    dlg._rows = [
        {"id": 1, "analysis_status": "VALID", "usable_for_learning": False, "learning_status": "EXCLUDED"},
        {"id": 2, "analysis_status": "VALID", "usable_for_learning": True, "learning_status": "INCLUDED"},
    ]
    dlg._pending_learning_decisions = {1: True, 2: False}
    monkeypatch.setattr(dialog_mod, "approve_budget_for_learning", lambda b, u: approved.append(b) or None)
    monkeypatch.setattr(
        dialog_mod,
        "set_historical_budget_learning_status",
        lambda b, *a, **k: excluded.append(b) or None,
    )

    dlg._apply_learning_decisions()

    assert approved == [1]
    assert excluded == [2]
    assert rebuilds == [1]
    assert any(c[0] == "information" and "aplicadas" in c[1][2] for c in _NoUiMessageBox.calls)


def test_apply_decisions_without_effective_changes_does_not_start_work(qapp, monkeypatch):
    dlg = _make_dialog(qapp, monkeypatch)
    started = []
    monkeypatch.setattr(busy_mod, "run_in_background", lambda work, cb: started.append(1))
    dlg._rows = [{"id": 1, "analysis_status": "VALID", "usable_for_learning": True, "learning_status": "INCLUDED"}]
    dlg._pending_learning_decisions = {1: True}

    dlg._apply_learning_decisions()

    assert started == []
    assert any("No hubo cambios efectivos" in str(c[1]) for c in _NoUiMessageBox.calls)
