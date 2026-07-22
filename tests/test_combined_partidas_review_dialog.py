"""
Fixes histórico evidenciado, Tarea 6: procedencia real (Fuente/Nivel/Rango
histórico/Diferencias) visible en la tabla de revisión combinada, y el
`source` real (historical_exact/historical_comparable) debe sobrevivir a la
confirmación en vez de colapsarse al genérico 'historical' (Tarea 5).
"""

import pytest

try:
    from src.gui.combined_partidas_review_dialog import CombinedPartidasReviewDialog

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")

_PROVENANCE_COLUMNS = {"Fuente": 10, "Nivel": 11, "Rango histórico": 12, "Diferencias": 13}


def _cell(dlg, row, header):
    return dlg._table.item(row, _PROVENANCE_COLUMNS[header]).text()


def test_table_has_provenance_columns(qapp):
    dlg = CombinedPartidasReviewDialog(None, historical_partidas=[], ai_partidas=[])
    labels = [dlg._table.horizontalHeaderItem(c).text() for c in _PROVENANCE_COLUMNS.values()]
    assert labels == ["Fuente", "Nivel", "Rango histórico", "Diferencias"]


def test_exact_evidence_row_shows_source_level_and_range(qapp):
    hist = [
        {
            "titulo": "Reparacion fachada",
            "descripcion": "d",
            "unidad": "m2",
            "cantidad": 1,
            "precio_unitario": 50.0,
            "source": "historical_exact",
            "evidence_level": "exact",
            "evidence_price_min": 50.0,
            "evidence_price_median": 50.0,
            "evidence_price_max": 50.0,
            "evidence_differences": [],
        }
    ]
    dlg = CombinedPartidasReviewDialog(None, historical_partidas=hist, ai_partidas=[])
    assert _cell(dlg, 0, "Fuente") == "Histórico"
    assert _cell(dlg, 0, "Nivel") == "Exacto"
    assert _cell(dlg, 0, "Rango histórico") == "50.00 – 50.00 – 50.00"
    assert _cell(dlg, 0, "Diferencias") == "—"


def test_comparable_evidence_row_shows_differences(qapp):
    hist = [
        {
            "titulo": "Reparacion fachada",
            "descripcion": "d",
            "unidad": "m2",
            "cantidad": 1,
            "precio_unitario": 45.0,
            "source": "historical_comparable",
            "evidence_level": "comparable",
            "evidence_price_min": 40.0,
            "evidence_price_median": 45.0,
            "evidence_price_max": 50.0,
            "evidence_differences": ["material"],
        }
    ]
    dlg = CombinedPartidasReviewDialog(None, historical_partidas=hist, ai_partidas=[])
    assert _cell(dlg, 0, "Nivel") == "Comparable"
    assert _cell(dlg, 0, "Rango histórico") == "40.00 – 45.00 – 50.00"
    assert _cell(dlg, 0, "Diferencias") == "material"


def test_ai_completion_row_shows_no_comparable_evidence(qapp):
    ai = [{"titulo": "Estimacion IA", "descripcion": "", "unidad": "ud", "cantidad": 1, "precio_unitario": 10.0}]
    dlg = CombinedPartidasReviewDialog(None, historical_partidas=[], ai_partidas=ai)
    assert _cell(dlg, 0, "Fuente") == "IA — borrador"
    assert _cell(dlg, 0, "Rango histórico") == "Sin evidencia privada comparable"


def test_apply_preserves_real_evidence_source_not_generic_historical(qapp):
    hist = [
        {
            "titulo": "Reparacion fachada",
            "descripcion": "d",
            "unidad": "m2",
            "cantidad": 1,
            "precio_unitario": 45.0,
            "source": "historical_comparable",
            "evidence_level": "comparable",
            "evidence_price_min": 40.0,
            "evidence_price_median": 45.0,
            "evidence_price_max": 50.0,
            "evidence_differences": ["material"],
        }
    ]
    dlg = CombinedPartidasReviewDialog(None, historical_partidas=hist, ai_partidas=[])
    dlg._on_apply()
    selected = dlg.get_selected_partidas()
    assert len(selected) == 1
    assert selected[0]["source"] == "historical_comparable"
