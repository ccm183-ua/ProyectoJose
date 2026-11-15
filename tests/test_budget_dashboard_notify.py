"""Los éxitos se notifican con un aviso pasajero, no con una ventana."""

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
    frame._tab_tables[STATE].selectRow(0)
    toasts, boxes = [], []
    monkeypatch.setattr(frame, "_notify", lambda text, actions=None: toasts.append(
        (text, [label for label, _cb in (actions or [])])))
    monkeypatch.setattr(frame, "_refresh_rows", lambda rutas, on_done=None: None)
    for name in ("information", "question", "warning"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(
            lambda *a, _n=name, **k: boxes.append(_n) or QMessageBox.StandardButton.Yes))
    yield frame, ruta, toasts, boxes
    frame.close()


def test_reread_without_failures_is_a_toast(monkeypatch, dash):
    frame, _, toasts, boxes = dash

    class _Svc:
        def refresh_budget_cache_entry(self, ruta, estado="", expected_numero=""):
            return True

    monkeypatch.setattr(services, "BudgetService", _Svc)
    frame._on_refresh_selected()
    assert toasts == [("Releídos 1", [])]
    assert boxes == []


def test_reread_with_failures_keeps_the_dialog(monkeypatch, dash):
    frame, _, toasts, boxes = dash

    class _Svc:
        def refresh_budget_cache_entry(self, ruta, estado="", expected_numero=""):
            return False

        def diagnose_read_failure(self, ruta, numero=""):
            return "Ninguna hoja coincide"

    monkeypatch.setattr(services, "BudgetService", _Svc)
    frame._on_refresh_selected()
    assert boxes == ["information"]
    assert toasts == []


def test_unreadable_excel_opens_without_asking(monkeypatch, dash):
    frame, ruta, toasts, boxes = dash
    opened = []

    class _Svc:
        def refresh_budget_cache_entry(self, r, estado="", expected_numero=""):
            return False

        def diagnose_read_failure(self, r, numero=""):
            return "E5 vacío en todas las hojas"

    monkeypatch.setattr(services, "BudgetService", _Svc)
    monkeypatch.setattr(BudgetDashboardFrame, "_open_file", staticmethod(lambda p: opened.append(p) or True))
    monkeypatch.setattr(frame, "_watch_excel_changes_and_refresh", lambda ruta_excel, estado: None)

    frame._on_open_excel()

    assert opened == [ruta]
    assert boxes == []
    assert toasts == [("No se pudo leer bien 1-26.xlsx: E5 vacío en todas las hojas. "
                       "Se ha abierto igualmente.", [])]


def test_regen_header_single_does_not_warn_first(monkeypatch, dash):
    frame, ruta, toasts, boxes = dash
    monkeypatch.setattr(frame, "_obtain_project_data", lambda preselect_numero="": ({"numero": "1-26"}, "1-26 obra"))
    monkeypatch.setattr(frame, "_write_regenerated_header", lambda *a: True)
    frame._edit_regen_header(ruta, "1-26")
    assert boxes == []
    assert toasts == [("Campos actualizados: 1-26.xlsx", [])]


def test_pdf_done_offers_open_and_folder(monkeypatch, dash, tmp_path):
    frame, _, toasts, boxes = dash

    class _Exporter:
        def is_available(self):
            return True

        def export(self, ruta):
            return True, str(tmp_path / "1-26.pdf")

    import src.core.pdf_exporter as pdf_mod
    monkeypatch.setattr(pdf_mod, "PDFExporter", _Exporter)
    frame._on_export_pdf()
    assert toasts == [("PDF generado: 1-26.pdf", ["Abrir", "Carpeta"])]
    assert boxes == []
