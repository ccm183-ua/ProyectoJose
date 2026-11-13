"""«Abrir Excel» lee cada fichero una vez, fuera del hilo de UI, y sin recarga completa."""

import os

import pytest

try:
    from PySide6.QtWidgets import QMessageBox

    from src.core import folder_scanner, services
    from src.core.settings import Settings
    from src.gui import budget_dashboard as bd
    from src.gui.budget_dashboard import BudgetDashboardFrame

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
def frame(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(Settings, "get_default_path", lambda self, key: "")
    monkeypatch.setattr(bd, "cleanup_orphaned_cache", lambda *a, **k: None)
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    dash = BudgetDashboardFrame()
    ruta = os.path.normpath(str(tmp_path / "1-26.xlsx"))
    open(ruta, "wb").close()
    monkeypatch.setattr(bd, "resolve_projects", lambda scanned, index, state: scanned)
    monkeypatch.setattr(folder_scanner, "scan_projects", lambda d: [_row("1-26", ruta)])
    dash._rebuild_tabs([STATE], str(tmp_path))
    dash._tab_tables[STATE].selectRow(0)
    yield dash, ruta
    dash.close()


@pytest.fixture
def spies(monkeypatch, frame):
    dash, _ = frame
    calls = {"refresh": [], "opened": [], "rows": [], "watch": []}

    class _FakeService:
        readable = True

        def refresh_budget_cache_entry(self, ruta, estado="", expected_numero=""):
            calls["refresh"].append(ruta)
            return _FakeService.readable

        def read_budget(self, *a, **k):
            raise AssertionError("no debe releer el Excel")

    monkeypatch.setattr(services, "BudgetService", _FakeService)
    monkeypatch.setattr(BudgetDashboardFrame, "_open_file", staticmethod(lambda p: calls["opened"].append(p) or True))
    monkeypatch.setattr(dash, "_watch_excel_changes_and_refresh", lambda ruta_excel, estado: calls["watch"].append(ruta_excel))
    monkeypatch.setattr(dash, "_refresh_rows", lambda rutas, on_done=None: calls["rows"].append(list(rutas)))
    monkeypatch.setattr(dash, "_load_data", lambda: pytest.fail("no debe recargar todo"))
    return calls, _FakeService


def test_open_excel_reads_once_and_refreshes_row(frame, spies):
    dash, ruta = frame
    calls, _ = spies

    dash._on_open_excel()

    assert calls["refresh"] == [ruta]
    assert calls["opened"] == [ruta]
    assert calls["watch"] == [ruta]
    assert calls["rows"] == [[ruta]]


def test_unreadable_excel_asks_and_respects_no(monkeypatch, frame, spies):
    dash, ruta = frame
    calls, fake = spies
    fake.readable = False
    asked = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: asked.append(1) or QMessageBox.StandardButton.No),
    )

    dash._on_open_excel()

    assert asked == [1]
    assert calls["opened"] == []
