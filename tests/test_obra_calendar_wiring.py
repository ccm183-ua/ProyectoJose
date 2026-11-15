"""El dashboard y la pantalla de inicio enlazan con el calendario de obras."""

import pytest

try:
    from PySide6.QtWidgets import QMainWindow

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


def _escuchar():
    from src.gui import planning_events

    vistos = []
    ev = planning_events.planning_events()

    def _cambio(numeros, emisor):
        vistos.append(("cambio", numeros, emisor))

    def _recarga(emisor):
        vistos.append(("recarga", emisor))

    ev.planning_changed.connect(_cambio)
    ev.obras_reloaded.connect(_recarga)

    def _parar():
        ev.planning_changed.disconnect(_cambio)
        ev.obras_reloaded.disconnect(_recarga)

    return vistos, _parar


def _dash():
    import src.gui.budget_dashboard as bd

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._explorer_mode = False
    dash._tab_data = {
        "EJECUTAR": [
            {"ruta_excel": "C:/o/114-26 A/p.xlsx", "ruta_carpeta": "C:/o/114-26 A", "numero": "114-26"},
            {"ruta_excel": "C:/o/208-26 B/p.xlsx", "ruta_carpeta": "C:/o/208-26 B", "numero": "208-26"},
        ]
    }
    return bd, dash


def test_dashboard_refresca_las_filas_de_un_cambio_externo(qapp):
    bd, dash = _dash()
    refrescos = []
    dash._refresh_rows = lambda rutas, on_done=None: refrescos.append(rutas)
    bd.BudgetDashboardFrame._on_external_planning_changed(dash, ["114-26"], object())
    assert refrescos == [["C:/o/114-26 A/p.xlsx"]]
    bd.BudgetDashboardFrame._on_external_planning_changed(dash, ["114-26"], dash)
    assert len(refrescos) == 1


def test_dashboard_avisa_al_guardar_la_planificacion(qapp, monkeypatch):
    import src.core.repositories.obra_planificacion_repository as repo
    import src.gui.obra_planning_dialog as dlg_mod

    class _Dialogo:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 1

        def get_changes(self):
            return {"inicio_previsto": None, "fin_previsto": None}

    monkeypatch.setattr(dlg_mod, "ObraPlanningDialog", _Dialogo)
    monkeypatch.setattr(repo, "upsert_plan", lambda *a, **k: None)
    bd, dash = _dash()
    fila = dict(dash._tab_data["EJECUTAR"][0], planificacion={}, planificacion_duplicado=False,
                planificacion_propuesta=None)
    dash._get_selected_many = lambda: [fila]
    dash._planning_margin = lambda: 7
    dash._refresh_rows = lambda rutas, on_done=None: None
    vistos, parar = _escuchar()
    try:
        bd.BudgetDashboardFrame._on_planning(dash)
    finally:
        parar()
    assert vistos == [("cambio", ["114-26"], dash)]


def test_dashboard_avisa_al_terminar_una_recarga_completa(qapp, monkeypatch, tmp_path):
    bd, dash = _dash()

    class _Ajustes:
        def get_default_path(self, _clave):
            return str(tmp_path)

    class _Texto:
        def setText(self, _t):
            pass

    dash._settings = _Ajustes()
    dash._subtitle = _Texto()
    dash._capture_view_context = lambda: None
    dash._show_empty_state = lambda *_a: None
    dash._set_toolbar_enabled = lambda *_a: None
    reconstruidas = []
    dash._rebuild_tabs = lambda *a: reconstruidas.append(a)
    monkeypatch.setattr(
        bd, "run_in_background",
        lambda work, cb: cb(True, ({}, ["EJECUTAR"], {"EJECUTAR": []}, set())),
    )
    vistos, parar = _escuchar()
    try:
        bd.BudgetDashboardFrame._load_data(dash)
    finally:
        parar()
    assert len(reconstruidas) == 1
    assert vistos == [("recarga", dash)]


def test_pantalla_de_inicio_abre_una_sola_ventana(qapp, monkeypatch):
    import src.gui.main_frame as mf
    import src.gui.obra_calendar_window as cw

    creadas = []

    class _Ventana:
        def __init__(self, parent=None):
            creadas.append(self)
            self.visible = False

            class _Destroyed:
                def connect(self, _f):
                    pass

            self.destroyed = _Destroyed()

        def show(self):
            self.visible = True

        def isVisible(self):
            return self.visible

        def raise_(self):
            pass

        def activateWindow(self):
            pass

    monkeypatch.setattr(cw, "ObraCalendarWindow", _Ventana)
    frame = mf.MainFrame.__new__(mf.MainFrame)
    QMainWindow.__init__(frame)
    frame._obra_calendar = None
    mf.MainFrame._open_obra_calendar(frame)
    mf.MainFrame._open_obra_calendar(frame)
    assert len(creadas) == 1 and creadas[0].visible
