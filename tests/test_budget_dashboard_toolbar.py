"""Barra de botones de «Presupuestos existentes»: menos botones y directos."""

import os

import pytest

try:
    from src.core import folder_scanner, services
    from src.core.settings import Settings
    from src.gui import budget_dashboard as bd
    from src.gui.budget_dashboard import BudgetDashboardFrame
    from src.gui.widgets.toast import current_toast

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")

STATE = "PRESUPUESTADO"


def _row(numero, ruta):
    return {
        "numero": numero, "nombre_proyecto": f"{numero} obra", "cliente": "C",
        "administracion_nombre": "", "direccion": "", "localidad": "", "tipo_obra": "",
        "fecha": "", "subtotal": 0.0, "iva": 0.0, "total": 0.0, "fuente_datos": "scan",
        "es_finalizado": False, "calidad_datos": 100, "datos_completos": True,
        "ruta_excel": ruta, "ruta_carpeta": os.path.dirname(ruta),
    }


@pytest.fixture
def dash(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(Settings, "get_default_path", lambda self, key: "")
    monkeypatch.setattr(bd, "cleanup_orphaned_cache", lambda *a, **k: None)
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    monkeypatch.setattr(bd, "resolve_projects", lambda scanned, index, state: scanned)
    ruta = os.path.normpath(str(tmp_path / "1-26.xlsx"))
    open(ruta, "wb").close()
    monkeypatch.setattr(folder_scanner, "scan_projects", lambda d: [_row("1-26", ruta)])
    frame = BudgetDashboardFrame()
    frame._rebuild_tabs([STATE], str(tmp_path))
    yield frame, ruta
    frame.close()


def test_toolbar_buttons(dash):
    frame, _ = dash
    texts = [b.text() for b in (frame._btn_open_excel, frame._btn_open_folder,
                                frame._btn_edit, frame._btn_reread)]
    assert texts == ["Abrir Excel", "Abrir carpeta", "Editar ▼", "Releer del Excel"]
    for gone in ("_btn_toggle_extra", "_btn_reset_columns", "_btn_open",
                 "_btn_regen_fields", "_btn_refresh_selected"):
        assert not hasattr(frame, gone)


def test_buttons_disabled_without_selection_explain_why(dash):
    frame, _ = dash
    frame._tab_tables[STATE].clearSelection()
    frame._tab_tables[STATE].setCurrentCell(-1, -1)
    frame._update_buttons()
    assert not frame._btn_open_excel.isEnabled()
    assert frame._btn_open_excel.toolTip() == "Selecciona un presupuesto"


def test_buttons_enabled_with_selection(dash):
    frame, _ = dash
    frame._tab_tables[STATE].selectRow(0)
    frame._update_buttons()
    assert all(b.isEnabled() for b in (frame._btn_open_excel, frame._btn_open_folder,
                                       frame._btn_edit, frame._btn_reread))


def test_columns_menu_toggles_extra_and_restores(dash):
    frame, _ = dash
    table = frame._tab_tables[STATE]
    menu = frame._build_columns_menu()
    labels = [a.text() for a in menu.actions() if a.text()]
    assert "Datos extra (Origen, Finalizado, Calidad)" in labels
    assert "Restaurar columnas" in labels
    extra = next(a for a in menu.actions() if a.text().startswith("Datos extra"))
    extra.trigger()
    assert table.isColumnHidden(10) and table.isColumnHidden(12)
    table.setColumnHidden(2, True)
    restore = next(a for a in frame._build_columns_menu().actions() if a.text() == "Restaurar columnas")
    restore.trigger()
    assert not table.isColumnHidden(2) and not table.isColumnHidden(10)


def test_columns_menu_hides_a_single_column(dash):
    frame, _ = dash
    table = frame._tab_tables[STATE]
    menu = frame._build_columns_menu()
    cliente = next(a for a in menu.actions() if a.text() == "Cliente")
    assert cliente.isCheckable() and cliente.isChecked()
    cliente.trigger()
    assert table.isColumnHidden(2)


def test_edit_menu_has_regenerate_and_finalize(dash):
    frame, _ = dash
    frame._tab_tables[STATE].selectRow(0)
    labels = [a.text() for a in frame._build_edit_menu(frame).actions() if a.text()]
    assert labels == [
        "Regenerar campos", "Finalizar",
        "Regenerar todas las partidas (IA)", "Añadir más partidas (IA)",
        "Añadir partidas desde la biblioteca", "Exportar PDF",
    ]


def test_finalize_refreshes_row_and_notifies(monkeypatch, dash):
    frame, ruta = dash
    frame._tab_tables[STATE].selectRow(0)
    calls = []

    class _FakeService:
        def finalize_budget(self, r, estado=""):
            calls.append((r, estado))
            return True

    monkeypatch.setattr(services, "BudgetService", _FakeService)
    refreshed = []
    monkeypatch.setattr(frame, "_refresh_rows", lambda rutas, on_done=None: refreshed.append(list(rutas)))

    frame._on_finalize()

    assert calls == [(ruta, STATE)]
    assert refreshed == [[ruta]]
    assert current_toast(frame).text() == "Presupuesto finalizado: 1-26.xlsx"


def test_notify_survives_uninitialised_window():
    half = BudgetDashboardFrame.__new__(BudgetDashboardFrame)
    half._notify("hola")  # no lanza


def test_enter_opens_excel_unless_typing(monkeypatch, dash):
    frame, _ = dash
    opened = []
    monkeypatch.setattr(frame, "_on_open_excel", lambda: opened.append(1))
    monkeypatch.setattr(bd.QApplication, "focusWidget", staticmethod(lambda: frame._tab_tables[STATE]))
    frame._on_enter_shortcut()
    monkeypatch.setattr(bd.QApplication, "focusWidget", staticmethod(lambda: frame._tab_searches[STATE]))
    frame._on_enter_shortcut()
    assert opened == [1]
