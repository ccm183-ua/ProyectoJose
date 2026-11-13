"""Las acciones sobre filas concretas refrescan solo esas filas, no todo el dashboard."""

import os

import pytest

try:
    from PySide6.QtWidgets import QMessageBox

    from src.core import folder_scanner
    from src.core.settings import Settings
    from src.gui import budget_dashboard as bd
    from src.gui.budget_dashboard import BudgetDashboardFrame

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")

STATE = "PRESUPUESTADO"


def _row(numero, cliente, ruta):
    return {
        "numero": numero,
        "nombre_proyecto": f"{numero} obra",
        "cliente": cliente,
        "administracion_nombre": "",
        "direccion": "",
        "localidad": "",
        "tipo_obra": "",
        "fecha": "",
        "subtotal": 0.0,
        "iva": 0.0,
        "total": 0.0,
        "fuente_datos": "scan",
        "es_finalizado": False,
        "calidad_datos": 100,
        "datos_completos": True,
        "ruta_excel": ruta,
        "ruta_carpeta": os.path.dirname(ruta),
    }


@pytest.fixture
def dashboard(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(Settings, "get_default_path", lambda self, key: "")
    monkeypatch.setattr(bd, "cleanup_orphaned_cache", lambda *a, **k: None)
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    frame = BudgetDashboardFrame()
    rutas = [os.path.normpath(str(tmp_path / f"{n}.xlsx")) for n in ("1-26", "2-26")]
    rows = [_row("1-26", "Antes 1", rutas[0]), _row("2-26", "Antes 2", rutas[1])]
    monkeypatch.setattr(bd, "resolve_projects", lambda scanned, index, state: scanned)
    monkeypatch.setattr(folder_scanner, "scan_projects", lambda state_dir: list(rows))
    frame._rebuild_tabs([STATE], str(tmp_path))
    yield frame, rutas
    frame.close()


def _clientes(frame):
    return [r["cliente"] for r in frame._tab_data[STATE]]


def test_refresh_rows_replaces_only_requested_row(monkeypatch, dashboard):
    frame, rutas = dashboard
    seen = []

    def _resolve(scanned, index, state):
        seen.append([s["ruta_excel"] for s in scanned])
        return [_row(s["numero_proyecto"], "Después", s["ruta_excel"]) for s in scanned]

    monkeypatch.setattr(bd, "resolve_projects", _resolve)

    frame._refresh_rows([rutas[1]])

    assert seen == [[rutas[1]]]
    assert _clientes(frame) == ["Antes 1", "Después"]
    table = frame._tab_tables[STATE]
    assert {table.item(r, 2).text() for r in range(table.rowCount())} >= {"Después"}


def test_refresh_rows_ignores_unknown_rutas(monkeypatch, dashboard):
    frame, _ = dashboard
    monkeypatch.setattr(
        bd, "resolve_projects",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debe resolver nada")),
    )
    done = []

    frame._refresh_rows(["C:/otra/ruta.xlsx"], on_done=lambda: done.append(1))

    assert done == [1]
    assert _clientes(frame) == ["Antes 1", "Antes 2"]


def test_refresh_rows_keeps_active_search(monkeypatch, dashboard):
    frame, rutas = dashboard
    frame._tab_searches[STATE].setText("2-26")
    monkeypatch.setattr(
        bd, "resolve_projects",
        lambda scanned, index, state: [_row("2-26", "Después", rutas[1])],
    )

    frame._refresh_rows([rutas[1]])

    assert frame._tab_searches[STATE].text() == "2-26"
    assert frame._tab_tables[STATE].rowCount() == 1


def test_scan_selected_refreshes_rows_instead_of_full_reload(monkeypatch, dashboard, tmp_path):
    frame, rutas = dashboard
    for r in rutas:
        open(r, "wb").close()
    frame._tab_tables[STATE].selectAll()

    class _FakeService:
        def refresh_budget_cache_entry(self, ruta, estado="", expected_numero=""):
            return True

    from src.core import services

    monkeypatch.setattr(services, "BudgetService", _FakeService)
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: 0))
    monkeypatch.setattr(frame, "_load_data", lambda: pytest.fail("no debe recargar todo"))
    refreshed = []
    monkeypatch.setattr(frame, "_refresh_rows", lambda r, on_done=None: refreshed.append(sorted(r)))

    frame._on_refresh_selected()

    assert refreshed == [sorted(rutas)]


def test_scan_summary_lists_reason_per_failure():
    failures = [(f"{i}-26.xlsx", "Ninguna hoja coincide") for i in range(17)]

    text = bd._scan_summary(3, failures)

    assert text.startswith("Actualizados: 3\nCon error: 17")
    assert "· 0-26.xlsx: Ninguna hoja coincide" in text
    assert "16-26.xlsx" not in text
    assert text.endswith("… y 2 más")


def test_scan_summary_without_failures():
    assert bd._scan_summary(5, []) == "Actualizados: 5\nCon error: 0"
