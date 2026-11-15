"""Lógica pura de los filtros del dashboard (sin Qt)."""

from datetime import date

import pytest

from src.core.budget_filters import (
    BudgetFilters, apply_filters, distinct_values, filter_chips, format_eur,
    parse_budget_date, summarize, summary_text, without,
)


def _row(numero, cliente="", admin="", fecha="", total=None):
    return {"numero": numero, "cliente": cliente, "administracion_nombre": admin,
            "fecha": fecha, "total": total}


@pytest.mark.parametrize("raw,expected", [
    ("16-01-26", date(2026, 1, 16)),
    ("16/01/26", date(2026, 1, 16)),
    ("16-01-2026", date(2026, 1, 16)),
    ("16/01/2026", date(2026, 1, 16)),
    ("2026-01-16", date(2026, 1, 16)),
    ("46038", date(2026, 1, 16)),  # serial de Excel
    (date(2026, 1, 16), date(2026, 1, 16)),
    ("", None),
    (None, None),
    ("enero", None),
    ("32-01-26", None),
])
def test_parse_budget_date(raw, expected):
    assert parse_budget_date(raw) == expected


def test_empty_filters_return_all_rows():
    rows = [_row("1-26"), _row("2-26")]
    assert BudgetFilters().is_empty()
    assert apply_filters(rows, BudgetFilters()) == rows


def test_cliente_matches_normalized_exact():
    rows = [_row("1-26", cliente="CP  Sol 3"), _row("2-26", cliente="CP Sol 31")]
    out = apply_filters(rows, BudgetFilters(cliente="cp sol 3"))
    assert [r["numero"] for r in out] == ["1-26"]


def test_administracion_filter():
    rows = [_row("1-26", admin="Fincas Sol"), _row("2-26", admin="")]
    out = apply_filters(rows, BudgetFilters(administracion="FINCAS SOL"))
    assert [r["numero"] for r in out] == ["1-26"]


def test_date_range_inclusive_and_hides_rows_without_date():
    rows = [
        _row("1-26", fecha="01-01-26"), _row("2-26", fecha="15-01-26"),
        _row("3-26", fecha="31-01-26"), _row("4-26", fecha=""), _row("5-26", fecha="basura"),
    ]
    f = BudgetFilters(fecha_desde=date(2026, 1, 1), fecha_hasta=date(2026, 1, 15))
    assert [r["numero"] for r in apply_filters(rows, f)] == ["1-26", "2-26"]


def test_importe_range_inclusive_and_hides_rows_without_total():
    rows = [_row("1-26", total=1000.0), _row("2-26", total=5000.0),
            _row("3-26", total=None), _row("4-26", total=0.0), _row("5-26", total="x")]
    f = BudgetFilters(importe_min=1000.0, importe_max=5000.0)
    assert [r["numero"] for r in apply_filters(rows, f)] == ["1-26", "2-26"]
    assert [r["numero"] for r in apply_filters(rows, BudgetFilters(importe_max=2000.0))] == ["1-26"]


def test_active_count_counts_zero_amount():
    assert BudgetFilters(importe_min=0.0).active_count() == 1
    assert BudgetFilters(cliente="  ").active_count() == 0
    assert BudgetFilters(cliente="A", fecha_hasta=date(2026, 1, 1)).active_count() == 2


def test_summarize_counts_all_and_sums_only_totals():
    rows = [_row("1", total=1000.0), _row("2", total=None), _row("3", total=250.5)]
    assert summarize(rows) == (3, 1250.5)


def test_summary_text_and_format():
    assert format_eur(84300.4) == "84.300 €"
    assert format_eur(0) == "0 €"
    assert summary_text(12, 84300.0) == "12 presupuestos · 84.300 €"
    assert summary_text(1, 500.0) == "1 presupuesto · 500 €"


def test_distinct_values_dedupes_normalized_and_sorts():
    rows = [_row("1", cliente="Beta"), _row("2", cliente="alfa"), _row("3", cliente="BETA "),
            _row("4", cliente=""), _row("5", cliente=None)]
    assert distinct_values(rows, "cliente") == ["alfa", "Beta"]


def test_chips_and_without():
    f = BudgetFilters(cliente="CP Sol", fecha_desde=date(2026, 1, 1), importe_min=5000.0)
    chips = filter_chips(f)
    assert chips == [
        ("cliente", "Cliente: CP Sol"),
        ("fecha_desde", "desde 01/01/26"),
        ("importe_min", "≥ 5.000 €"),
    ]
    g = without(f, "fecha_desde")
    assert g.fecha_desde is None and g.cliente == "CP Sol"
    assert without(f, "cliente").cliente == ""
