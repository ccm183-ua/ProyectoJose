"""Filtros por pestaña en «Presupuestos existentes»."""

import os

import pytest

try:
    from src.core import folder_scanner
    from src.core.budget_filters import BudgetFilters
    from src.core.settings import Settings
    from src.gui import budget_dashboard as bd
    from src.gui.budget_dashboard import BudgetDashboardFrame

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")

A, B = "PRESUPUESTADO", "EJECUTAR"


def _row(numero, cliente, total, ruta, fecha="10-01-26"):
    return {
        "numero": numero, "nombre_proyecto": f"{numero} obra", "cliente": cliente,
        "administracion_nombre": "", "direccion": "", "localidad": "", "tipo_obra": "",
        "fecha": fecha, "subtotal": 0.0, "iva": 0.0, "total": total, "fuente_datos": "scan",
        "es_finalizado": False, "calidad_datos": 100, "datos_completos": True,
        "ruta_excel": ruta, "ruta_carpeta": os.path.dirname(ruta),
    }


@pytest.fixture
def dash(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(Settings, "get_default_path", lambda self, key: "")
    monkeypatch.setattr(bd, "cleanup_orphaned_cache", lambda *a, **k: None)
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    monkeypatch.setattr(bd, "resolve_projects", lambda scanned, index, state: scanned)
    monkeypatch.setattr(bd, "enrich_with_planning", lambda *a, **k: set())
    rows = {
        A: [_row("1-26", "CP Sol", 1000.0, str(tmp_path / "1.xlsx")),
            _row("2-26", "CP Luna", 3000.0, str(tmp_path / "2.xlsx")),
            _row("3-26", "CP Sol", None, str(tmp_path / "3.xlsx"))],
        B: [_row("4-26", "CP Mar", 500.0, str(tmp_path / "4.xlsx"))],
    }
    monkeypatch.setattr(
        folder_scanner, "scan_projects", lambda d: list(rows[os.path.basename(d)])
    )
    frame = BudgetDashboardFrame()
    frame._rebuild_tabs([A, B], str(tmp_path))
    yield frame
    frame.close()


def _numeros(frame, state):
    table = frame._tab_tables[state]
    return sorted(table.item(r, 0).text() for r in range(table.rowCount()))


def test_each_tab_has_a_filter_bar_with_summary(dash):
    assert set(dash._tab_filter_bars) == {A, B}
    assert dash._tab_filter_bars[A].summary() == "3 presupuestos · 4.000 €"


def test_filter_applies_only_to_its_tab(dash):
    dash._on_filters_changed(A, BudgetFilters(cliente="CP Sol"))
    assert _numeros(dash, A) == ["1-26", "3-26"]
    assert _numeros(dash, B) == ["4-26"]
    assert dash._tab_filter_bars[A].summary() == "2 presupuestos · 1.000 €"


def test_filters_combine_with_text_search(dash):
    dash._on_filters_changed(A, BudgetFilters(cliente="CP Sol"))
    dash._tab_searches[A].setText("3-26")
    assert _numeros(dash, A) == ["3-26"]


def test_row_data_matches_filtered_rows(dash):
    dash._on_filters_changed(A, BudgetFilters(importe_min=2000.0))
    assert dash._get_row_data(A, 0)["numero"] == "2-26"


def test_filters_survive_rebuild(dash, tmp_path):
    dash._on_filters_changed(A, BudgetFilters(cliente="CP Luna"))
    dash._rebuild_tabs([A, B], str(tmp_path))
    assert _numeros(dash, A) == ["2-26"]
    assert dash._tab_filter_bars[A].filters() == BudgetFilters(cliente="CP Luna")


def test_options_come_from_tab_rows(dash):
    bar = dash._tab_filter_bars[A]
    assert [bar._cliente.itemText(i) for i in range(bar._cliente.count())] == ["CP Luna", "CP Sol"]
    assert not bar._admin.isEnabled()


def test_empty_result_shows_filter_message(dash):
    dash._on_filters_changed(A, BudgetFilters(importe_min=99999.0))
    table = dash._tab_tables[A]
    assert table.rowCount() == 1
    assert "Ningún presupuesto cumple los filtros" in table.item(0, 0).text()


def test_explorer_mode_has_no_filter_bar(dash, tmp_path, monkeypatch):
    monkeypatch.setattr(folder_scanner, "scan_explorer", lambda d: [])
    dash._explorer_mode = True
    dash._rebuild_tabs([A, B], str(tmp_path))
    assert dash._tab_filter_bars == {}
