"""Comprobaciones de UI en tablas de sugerencias y revisión combinada (checkbox columna Usar)."""

import pytest

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from src.gui.combined_partidas_review_dialog import CombinedPartidasReviewDialog
    from src.gui.historical_suggestions_dialog import HistoricalSuggestionsDialog

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _suggestion_result():
    return {
        "partidas": [
            {
                "module": "A",
                "concepto": "Partida uno",
                "cantidad": 1,
                "unidad": "ud",
                "precio_unitario": 10,
                "precio_min": 9,
                "precio_max": 11,
                "historical_frequency": 5,
                "confidence": 0.8,
            },
            {
                "module": "B",
                "concepto": "Partida dos",
                "cantidad": 2,
                "unidad": "m2",
                "precio_unitario": 20,
                "precio_min": 18,
                "precio_max": 22,
                "historical_frequency": 1,
                "confidence": 0.5,
            },
        ],
        "detected_modules": [{"label": "M1", "confidence": 0.9}],
        "stats": {"partidas_base": 10},
        "duplicates_hidden_count": 0,
    }


def test_historical_suggestions_usar_column_is_real_checkbox(qapp):
    dlg = HistoricalSuggestionsDialog(None, _suggestion_result(), project_data={})
    for row in range(dlg._table.rowCount()):
        it = dlg._table.item(row, 0)
        assert it is not None
        assert bool(it.flags() & Qt.ItemFlag.ItemIsUserCheckable)
        assert not (it.flags() & Qt.ItemFlag.ItemIsEditable)
        assert it.text() != "✓"
        assert it.data(Qt.ItemDataRole.CheckStateRole) is not None


def test_historical_suggestions_select_all_none_toggle_check(qapp):
    dlg = HistoricalSuggestionsDialog(None, _suggestion_result(), project_data={})
    dlg._select_none()
    for row in range(dlg._table.rowCount()):
        assert dlg._table.item(row, 0).checkState() == Qt.CheckState.Unchecked
    dlg._select_all()
    for row in range(dlg._table.rowCount()):
        assert dlg._table.item(row, 0).checkState() == Qt.CheckState.Checked


def test_combined_review_usar_checkbox_and_apply_only_checked(qapp):
    hist = [{"titulo": "H1", "descripcion": "d", "unidad": "ud", "cantidad": 1, "precio_unitario": 1}]
    ai = [{"titulo": "I1", "descripcion": "x", "unidad": "ud", "cantidad": 1, "precio_unitario": 2}]
    dlg = CombinedPartidasReviewDialog(None, historical_partidas=hist, ai_partidas=ai)
    for row in range(dlg._table.rowCount()):
        it = dlg._table.item(row, 0)
        assert bool(it.flags() & Qt.ItemFlag.ItemIsUserCheckable)
        assert not (it.flags() & Qt.ItemFlag.ItemIsEditable)
        assert it.text() != "✓"
    dlg._table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    dlg._table.item(1, 0).setCheckState(Qt.CheckState.Checked)
    dlg._on_apply()
    out = dlg.get_selected_partidas()
    assert len(out) == 1
    assert (out[0].get("titulo") or out[0].get("concepto")) == "I1"


def test_combined_select_all_none(qapp):
    hist = [{"titulo": "H1", "descripcion": "", "unidad": "ud", "cantidad": 1, "precio_unitario": 1}]
    ai = [{"titulo": "I1", "descripcion": "", "unidad": "ud", "cantidad": 1, "precio_unitario": 2}]
    dlg = CombinedPartidasReviewDialog(None, historical_partidas=hist, ai_partidas=ai)
    dlg._select_none()
    assert all(
        dlg._table.item(r, 0).checkState() == Qt.CheckState.Unchecked for r in range(dlg._table.rowCount())
    )
    dlg._select_all()
    assert all(
        dlg._table.item(r, 0).checkState() == Qt.CheckState.Checked for r in range(dlg._table.rowCount())
    )
