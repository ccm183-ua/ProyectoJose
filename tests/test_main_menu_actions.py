"""S3-D / H15: los atajos del menú Archivo existen y 'Abrir' abre el documento."""

from types import SimpleNamespace

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow


def _frame(qapp):
    from src.gui.main_frame import MainFrame

    frame = MainFrame.__new__(MainFrame)
    QMainWindow.__init__(frame)
    frame._create_menu()
    return frame


def test_atajos_del_menu_archivo_estan_registrados(qapp):
    frame = _frame(qapp)
    acciones = {a.text(): a for a in frame.findChildren(QAction) if a.text()}

    assert acciones["Abrir presupuesto..."].shortcut().toString() == "Ctrl+O"
    assert acciones["Crear nuevo presupuesto..."].shortcut().toString() == "Ctrl+N"
    assert acciones["Salir"].shortcut().toString() == "Ctrl+Q"


def _open_excel_con(monkeypatch, frame, tmp_path, opened_ok):
    import src.gui.main_frame as mf

    path = str(tmp_path / "p.xlsx")
    lanzados, errores = [], []
    monkeypatch.setattr(mf.QFileDialog, "getOpenFileName", lambda *a, **k: (path, ""))
    monkeypatch.setattr(mf.QMessageBox, "critical", lambda *a, **k: errores.append(a))
    monkeypatch.setattr(mf.os, "startfile", lambda p: lanzados.append(p), raising=False)
    frame._budget_svc = SimpleNamespace(open_budget=lambda p: opened_ok)
    frame._open_excel()
    return path, lanzados, errores


def test_abrir_lanza_el_archivo_en_la_aplicacion_asociada(qapp, monkeypatch, tmp_path):
    path, lanzados, errores = _open_excel_con(monkeypatch, _frame(qapp), tmp_path, True)

    assert lanzados == [path]
    assert errores == []


def test_abrir_no_lanza_nada_si_el_archivo_no_se_puede_leer(qapp, monkeypatch, tmp_path):
    _, lanzados, errores = _open_excel_con(monkeypatch, _frame(qapp), tmp_path, False)

    assert lanzados == []
    assert len(errores) == 1
