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
_PRICE_COL = 6
_TOTAL_COL = 7


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


def _partida_2x10():
    return {
        "titulo": "Reparacion fachada",
        "descripcion": "d",
        "unidad": "m2",
        "cantidad": 2,
        "precio_unitario": 10.0,
    }


@pytest.mark.parametrize(
    "kwargs, expected_source",
    [
        ({"historical_partidas": [dict(_partida_2x10(), source="historical_exact")]}, "historical_exact"),
        ({"ai_partidas": [_partida_2x10()]}, "ai_completion"),
    ],
)
def test_edited_price_survives_apply(qapp, kwargs, expected_source):
    """El precio escrito con coma decimal se guarda tal cual, en histórico y en IA."""
    dlg = CombinedPartidasReviewDialog(None, **kwargs)
    dlg._table.item(0, _PRICE_COL).setText("37,50")

    assert dlg._table.item(0, _TOTAL_COL).text() == "75.00"

    dlg._on_apply()
    selected = dlg.get_selected_partidas()
    assert len(selected) == 1
    assert selected[0]["precio"] == 37.5
    assert selected[0]["precio_unitario"] == 37.5
    assert selected[0]["total"] == 75.0
    assert selected[0]["source"] == expected_source


def test_edited_price_reaches_excel_and_survives_reread(qapp, temp_dir, monkeypatch):
    """El precio aprobado llega al Excel final y se relee igual (37,50 / 75,00)."""
    import os

    from src.core.budget_reader import BudgetReader
    from src.core.excel_manager import ExcelManager
    from src.core.services.budget_service import BudgetService
    from src.core.template_manager import TemplateManager

    monkeypatch.setenv("CUBIAPP_DB_PATH", os.path.join(temp_dir, "datos.db"))

    template = TemplateManager().get_template_path()
    if not os.path.exists(template):
        pytest.skip("Plantilla no disponible")
    excel_path = os.path.join(temp_dir, "presupuesto.xlsx")
    assert ExcelManager().create_from_template(
        template,
        excel_path,
        {
            "numero_proyecto": "99",
            "fecha": "13-02-26",
            "cliente": "TEST CLIENT",
            "calle": "Calle Test",
            "codigo_postal": "03001",
            "tipo": "TEST OBRA",
        },
    )

    dlg = CombinedPartidasReviewDialog(
        None,
        historical_partidas=[dict(_partida_2x10(), source="historical_exact")],
        ai_partidas=[],
    )
    dlg._table.item(0, _PRICE_COL).setText("37,50")
    dlg._on_apply()

    assert BudgetService().insert_partidas(excel_path, dlg.get_selected_partidas()) is True

    partidas = BudgetReader().read(excel_path)["partidas"]
    assert len(partidas) == 1
    assert partidas[0]["precio"] == pytest.approx(37.50)
    assert partidas[0]["importe"] == pytest.approx(75.00)


def test_summary_warns_about_pending_modules_instead_of_claiming_full_historical_coverage(qapp):
    """H03 (S1-C): con 1 histórica y 0 IA, el resumen no puede afirmar que
    todas las partidas son históricas sin nombrar el hueco pendiente."""
    hist = [
        {
            "titulo": "Reparacion fachada",
            "unidad": "m2",
            "cantidad": 1,
            "precio_unitario": 50.0,
            "source": "historical_exact",
        }
    ]
    dlg = CombinedPartidasReviewDialog(
        None,
        historical_partidas=hist,
        ai_partidas=[],
        cobertura={
            "partidas_historicas": 1,
            "partidas_ia": 0,
            "modulos_pendientes": ["sustitucion_bajante"],
            "error_ia": "Timeout",
        },
    )

    text = dlg._coverage_summary_text()

    assert "Resultado parcial" in text
    assert "sustitucion bajante" in text
    assert "Timeout" in text
    assert "Todas las partidas (1) provienen de referencias históricas." != text
