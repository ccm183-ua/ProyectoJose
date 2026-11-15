"""
Regresión GUI: resultados tardíos de la IA tras cerrar el diálogo y debounce
del buscador de la memoria histórica.
"""

import pytest

try:
    from PySide6.QtWidgets import QMessageBox

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


@pytest.fixture
def popups(monkeypatch):
    """Registra cualquier QMessageBox en vez de bloquear (offscreen)."""
    calls = []
    for name in ("warning", "information", "critical"):
        monkeypatch.setattr(
            QMessageBox, name, staticmethod(lambda *a, _n=name, **k: calls.append(_n))
        )
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: calls.append("question") or QMessageBox.StandardButton.No),
    )
    return calls


@pytest.mark.parametrize("result", [
    {"source": "error", "error": "cuota agotada"},
    {"source": "offline", "partidas": [{"concepto": "x"}]},
])
def test_ai_budget_dialog_ignora_resultado_tras_saltar(qapp, popups, result):
    from src.gui.ai_budget_dialog import AIBudgetDialog

    dlg = AIBudgetDialog(None, datos_proyecto={})
    dlg.reject()  # "Saltar" mientras la IA sigue trabajando

    dlg._on_generation_complete(result)

    assert popups == []
    assert dlg.get_result() is None


def test_ai_complete_historical_dialog_ignora_resultado_tras_cerrar(qapp, popups):
    from src.gui.ai_complete_historical_budget_dialog import AICompleteHistoricalBudgetDialog

    dlg = AICompleteHistoricalBudgetDialog(None, project_data={})
    dlg.reject()

    dlg._on_generation_complete({"error": "timeout"})

    assert popups == []
    assert dlg.get_action() != "ai_completion"


def test_buscador_memoria_historica_no_recarga_en_cada_tecla(qapp, popups, monkeypatch, tmp_path):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "dash.db"))
    from src.core import database

    with database.get_connection():  # crea el esquema antes de abrir en solo lectura
        pass
    from src.gui.historical_memory_dashboard import HistoricalMemoryDashboard

    dash = HistoricalMemoryDashboard(None)
    calls = []
    monkeypatch.setattr(dash, "_reload", lambda *a, **k: calls.append(1))
    dash._search_timer.timeout.disconnect()
    dash._search_timer.timeout.connect(dash._reload)

    for text in ("a", "al", "ali", "alic"):
        dash._search.setText(text)

    assert calls == []  # nada síncrono mientras se teclea
    assert dash._search_timer.isActive()
    dash._search_timer.timeout.emit()
    assert calls == [1]


def test_guardar_excel_refresca_sin_preguntar_y_ofrece_finalizar(qapp, monkeypatch):
    """Al guardar el Excel abierto desde el dashboard se refresca la fila sin
    ventanas y se ofrece «Finalizar» en un aviso pasajero."""
    import src.gui.budget_dashboard as bd
    from src.core import services

    llamadas, avisos, finalizados = [], [], []

    class _FakeService:
        def finalize_budget(self, ruta, estado=""):
            raise AssertionError("guardar no debe finalizar")

        def refresh_budget_cache_entry(self, ruta, estado=""):
            llamadas.append("refresh"); return True

    eventos = iter([True, True])

    def _fake_wait(ruta, stop, baseline):
        try:
            return next(eventos)
        except StopIteration:
            stop.set()
            return False

    monkeypatch.setattr(bd.os.path, "getmtime", lambda _p: 100.0)
    monkeypatch.setattr(bd, "_wait_for_excel_change", _fake_wait)
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    monkeypatch.setattr(services, "BudgetService", _FakeService)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: pytest.fail("no debe preguntar")))

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._excel_watchers = {}
    dash._load_data = lambda: llamadas.append("full-reload")
    dash._refresh_rows = lambda rutas, on_done=None: llamadas.append("reload")
    dash._notify = lambda text, actions=None: avisos.append((text, actions))
    dash._finalize_ruta = lambda ruta, estado: finalizados.append((ruta, estado))
    bd.BudgetDashboardFrame._watch_excel_changes_and_refresh(dash, "C:/obra/presupuesto.xlsx", "PRESUPUESTADO")

    assert llamadas == ["refresh", "reload", "refresh", "reload"]
    assert [t for t, _a in avisos] == ["Se guardó presupuesto.xlsx · ¿finalizar?"] * 2
    label, action = avisos[0][1][0]
    assert label == "Finalizar"
    action()
    assert finalizados == [("C:/obra/presupuesto.xlsx", "PRESUPUESTADO")]


@pytest.mark.parametrize("overwrote,respuesta,descarta", [
    (True, "No", False),   # sustituyó un Excel existente: nunca se descarta
    (False, "No", True),   # borrador nuevo: "No" lo descarta
    (False, "Yes", False),
])
def test_borrador_que_sobrescribio_un_excel_no_se_puede_descartar(qapp, monkeypatch, overwrote, respuesta, descarta):
    import src.gui.main_frame as mf

    descartes = []

    class _FakeSvc:
        def discard_budget(self, excel, folder):
            descartes.append(excel); return True

    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: getattr(QMessageBox.StandardButton, respuesta)),
    )
    frame = mf.MainFrame.__new__(mf.MainFrame)
    frame._budget_svc = _FakeSvc()
    mf.MainFrame._handle_unfinished_budget(
        frame, "C:/obra/presupuesto.xlsx", "C:/obra", "cancelled", overwrote_existing=overwrote,
    )
    assert bool(descartes) is descarta


def test_vigilancia_excel_se_para_si_se_cierra_durante_el_refresco(qapp, monkeypatch):
    """Cerrar el dashboard mientras se refresca el guardado detiene la vigilancia."""
    import src.gui.budget_dashboard as bd
    from src.core import services

    ruta = "C:/obra/presupuesto.xlsx"
    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._excel_watchers = {}
    dash._load_data = lambda: None
    dash._refresh_rows = lambda rutas, on_done=None: None
    dash._notify = lambda *a, **k: None
    bases = []
    mtimes = iter([100.0, 250.0])

    def _fake_wait(r, stop, baseline):
        bases.append(baseline)
        return len(bases) == 1  # solo el primer guardado

    class _FakeService:
        def refresh_budget_cache_entry(self, r, estado=""):
            dash._excel_watchers[ruta].set()  # el usuario cierra el dashboard aquí
            return True

    monkeypatch.setattr(bd.os.path, "getmtime", lambda _p: next(mtimes, 250.0))
    monkeypatch.setattr(bd, "_wait_for_excel_change", _fake_wait)
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    monkeypatch.setattr(services, "BudgetService", _FakeService)

    bd.BudgetDashboardFrame._watch_excel_changes_and_refresh(dash, ruta, "PRESUPUESTADO")

    assert bases == [100.0]  # no se re-arma tras cerrar


def test_vigilancia_excel_rearma_con_el_mtime_del_guardado_detectado(qapp, monkeypatch):
    import src.gui.budget_dashboard as bd
    from src.core import services

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._excel_watchers = {}
    dash._load_data = lambda: None
    dash._refresh_rows = lambda rutas, on_done=None: None
    dash._notify = lambda *a, **k: None
    bases = []
    mtimes = iter([100.0, 250.0])

    def _fake_wait(r, stop, baseline):
        bases.append(baseline)
        if len(bases) == 1:
            return True
        stop.set()
        return False

    class _FakeService:
        def refresh_budget_cache_entry(self, r, estado=""):
            return True

    monkeypatch.setattr(bd.os.path, "getmtime", lambda _p: next(mtimes, 999.0))
    monkeypatch.setattr(bd, "_wait_for_excel_change", _fake_wait)
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    monkeypatch.setattr(services, "BudgetService", _FakeService)

    bd.BudgetDashboardFrame._watch_excel_changes_and_refresh(dash, "C:/obra/p.xlsx", "PRESUPUESTADO")

    assert bases == [100.0, 250.0]
    assert "C:/obra/p.xlsx" not in dash._excel_watchers
