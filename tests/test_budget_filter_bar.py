"""Barra de filtros de una pestaña del dashboard."""

from datetime import date

import pytest

try:
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QLineEdit

    from src.core.budget_filters import BudgetFilters
    from src.gui.widgets.budget_filter_bar import BudgetFilterBar

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


@pytest.fixture
def bar(qapp):
    b = BudgetFilterBar(None, leading=QLineEdit())
    emitted = []
    b.filters_changed.connect(emitted.append)
    b.set_options(["CP Luna", "CP Sol"], [])
    yield b, emitted
    b.deleteLater()


def test_starts_collapsed_and_empty(bar):
    b, _ = bar
    assert not b.is_expanded()
    assert b.filters() == BudgetFilters()
    assert b.toggle_button().text() == "Filtros"
    assert b.chip_labels() == []


def test_toggle_button_expands_and_emits_expanded(bar):
    b, _ = bar
    seen = []
    b.expanded_changed.connect(seen.append)
    b.toggle_button().click()
    assert b.is_expanded() and seen == [True]


def test_choosing_cliente_emits_and_shows_chip(bar):
    b, emitted = bar
    b._cliente.setCurrentText("CP Sol")
    assert emitted[-1] == BudgetFilters(cliente="CP Sol")
    assert b.chip_labels() == ["Cliente: CP Sol"]
    assert b.toggle_button().text() == "Filtros (1)"


def test_partial_cliente_text_does_not_emit(bar):
    b, emitted = bar
    b._cliente.setCurrentText("CP S")
    assert emitted == []


def test_admin_combo_disabled_without_options(bar):
    b, _ = bar
    assert not b._admin.isEnabled()
    b.set_options(["CP Sol"], ["Fincas Sol"])
    assert b._admin.isEnabled()


def test_dates_and_amounts(bar):
    b, emitted = bar
    b._desde.setDate(QDate(2026, 1, 1))
    b._desde_chk.setChecked(True)
    b._min.setText("5000")
    b._min.editingFinished.emit()
    assert emitted[-1] == BudgetFilters(fecha_desde=date(2026, 1, 1), importe_min=5000.0)


def test_amount_accepts_spanish_format(bar):
    b, emitted = bar
    b._max.setText("12.500,50")
    b._max.editingFinished.emit()
    assert emitted[-1].importe_max == 12500.5


def test_remove_chip_and_clear(bar):
    b, emitted = bar
    b.set_filters(BudgetFilters(cliente="CP Sol", importe_min=10.0))
    b.remove_chip("cliente")
    assert emitted[-1] == BudgetFilters(importe_min=10.0)
    b.clear()
    assert emitted[-1] == BudgetFilters()
    assert b.chip_labels() == []


def test_set_filters_does_not_emit_and_keeps_unknown_cliente(bar):
    b, emitted = bar
    b.set_filters(BudgetFilters(cliente="Ya no existe"))
    b.set_options(["CP Sol"], [])
    assert emitted == []
    assert b.filters().cliente == "Ya no existe"


def test_summary(bar):
    b, _ = bar
    b.set_summary(12, 84300.0)
    assert b.summary() == "12 presupuestos · 84.300 €"
