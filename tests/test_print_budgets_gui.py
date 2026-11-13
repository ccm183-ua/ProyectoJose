"""Imprimir presupuestos desde el dashboard (decisión D, 2026-11-13)."""

import pytest

try:
    from PySide6.QtWidgets import QMessageBox

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


@pytest.fixture
def dash(qapp, monkeypatch, tmp_path):
    import src.gui.budget_dashboard as bd

    rutas = []
    for nombre in ("166-26.xlsx", "168-26.xlsx"):
        ruta = tmp_path / nombre
        ruta.write_bytes(b"x")
        rutas.append(str(ruta))
    frame = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    frame._get_selected_many = lambda: [{"ruta_excel": r} for r in rutas]
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    return frame, rutas


@pytest.fixture
def mensajes(monkeypatch):
    vistos = []
    for nombre in ("information", "warning", "critical"):
        monkeypatch.setattr(
            QMessageBox, nombre,
            staticmethod(lambda *a, _n=nombre, **k: vistos.append((_n, a[2] if len(a) > 2 else ""))),
        )
    return vistos


def _fake_exporter(monkeypatch, printer="HP LaserJet Pro M404", fallos=()):
    from src.core import pdf_exporter

    impresos = []

    def _print(self, ruta, copies=1):
        if any(f in ruta for f in fallos):
            return False, "Error al imprimir: atasco de papel"
        impresos.append(ruta)
        return True, ruta

    monkeypatch.setattr(pdf_exporter.PDFExporter, "is_available", lambda self: True)
    monkeypatch.setattr(pdf_exporter.PDFExporter, "default_printer_name", staticmethod(lambda: printer))
    monkeypatch.setattr(pdf_exporter.PDFExporter, "print_workbook", _print)
    return impresos


def test_contestar_no_no_imprime(dash, monkeypatch, mensajes):
    import src.gui.budget_dashboard as bd

    frame, _rutas = dash
    impresos = _fake_exporter(monkeypatch)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    bd.BudgetDashboardFrame._on_print_selected(frame)

    assert impresos == []


def test_contestar_si_imprime_todos_y_resume_fallos(dash, monkeypatch, mensajes):
    import src.gui.budget_dashboard as bd

    frame, rutas = dash
    impresos = _fake_exporter(monkeypatch, fallos=("168-26",))
    preguntas = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: preguntas.append(a[2]) or QMessageBox.StandardButton.Yes),
    )

    bd.BudgetDashboardFrame._on_print_selected(frame)

    assert "2 presupuestos" in preguntas[0] and "HP LaserJet Pro M404" in preguntas[0]
    assert impresos == [rutas[0]]
    tipo, texto = mensajes[-1]
    assert tipo == "warning" and "Impresos: 1" in texto and "168-26.xlsx" in texto


def test_impresora_virtual_no_imprime_y_avisa(dash, monkeypatch, mensajes):
    import src.gui.budget_dashboard as bd

    frame, _rutas = dash
    impresos = _fake_exporter(monkeypatch, printer="Microsoft Print to PDF")
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: pytest.fail("no debe preguntar con impresora virtual")),
    )

    bd.BudgetDashboardFrame._on_print_selected(frame)

    assert impresos == []
    tipo, texto = mensajes[-1]
    assert tipo == "warning" and "Microsoft Print to PDF" in texto and "Exportar PDF" in texto
