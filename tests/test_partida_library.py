"""Tests del núcleo de la biblioteca de partidas (sin PySide6)."""

from datetime import date

import pytest

from src.core.partida_library import canonical_unit, line_status, parse_budget_date


@pytest.mark.parametrize("raw,esperada", [
    ("p.a.", "p.a."), ("P.A.", "p.a."), ("p.a", "p.a."), ("pa", "p.a."), ("P.a.", "p.a."), ("Partida", "p.a."),
    ("ud", "ud"), ("Ud", "ud"), ("UD", "ud"), ("ud.", "ud"),
    ("m2", "m2"), ("M2", "m2"), ("m²", "m2"),
    ("m", "m"), ("M", "m"), ("ml", "m"),
    ("m3", "m3"), ("kg", "kg"), ("DIAS", "día"), ("día", "día"),
    ("65807DC0", "?"), ("1650", "?"), ("", "?"), (None, "?"),
])
def test_canonical_unit(raw, esperada):
    assert canonical_unit(raw) == esperada


@pytest.mark.parametrize("raw,esperada", [
    ("13/02/26", date(2026, 2, 13)),
    ("13/02/2026", date(2026, 2, 13)),
    ("46036", date(2026, 1, 14)),
    ("46041", date(2026, 1, 19)),
    ("%", None), ("SAN VICENTE", None), ("", None), (None, None),
    ("CERTIFICACIÓN Nº 2          Fecha: 08/11/24", date(2024, 11, 8)),  # certificaciones
    ("CERTIFICACIÓN Nº 3", None),
    ("31/02/26", None),      # fecha imposible
    ("12345", None),         # serie fuera de [30000, 60000]
])
def test_parse_budget_date(raw, esperada):
    assert parse_budget_date(raw) == esperada


@pytest.mark.parametrize("learning,analysis,esperado", [
    ("INCLUDED", "VALID", "approved"),
    ("INCLUDED", "VALID_WITH_WARNINGS", "approved"),
    ("PENDING_REVIEW", "VALID", "unreviewed"),
    ("NOT_ELIGIBLE", "VALID", "ineligible"),
    ("INCLUDED", "READ_ERROR", "ineligible"),
    ("PENDING_REVIEW", "EXCLUDED_INCOMPLETE_DATA", "ineligible"),
    ("", "", "ineligible"),
])
def test_line_status(learning, analysis, esperado):
    assert line_status(learning, analysis) == esperado
