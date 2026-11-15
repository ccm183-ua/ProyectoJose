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


@pytest.mark.parametrize("respuesta,esperado", [("No", "refresh"), ("Yes", "finalize")])
def test_guardar_excel_pregunta_antes_de_finalizar(qapp, monkeypatch, respuesta, esperado):
    """Decisión E1: al guardar el Excel abierto desde el dashboard ya no se
    finaliza sin preguntar; con "No" solo se refresca la caché y los guardados
    siguientes de ese Excel ya no vuelven a preguntar."""
    import src.gui.budget_dashboard as bd
    from src.core import services

    llamadas = []

    class _FakeService:
        def finalize_budget(self, ruta, estado=""):
            llamadas.append("finalize"); return True

        def refresh_budget_cache_entry(self, ruta, estado=""):
            llamadas.append("refresh"); return True

    # Dos guardados seguidos y, a la tercera espera, se cierra el dashboard.
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
    preguntas = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: preguntas.append(1) or getattr(QMessageBox.StandardButton, respuesta)),
    )

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._excel_watchers = {}
    dash._excel_no_finalize = set()
    dash._load_data = lambda: llamadas.append("full-reload")
    dash._refresh_rows = lambda rutas, on_done=None: llamadas.append("reload")
    bd.BudgetDashboardFrame._watch_excel_changes_and_refresh(dash, "C:/obra/presupuesto.xlsx", "PRESUPUESTADO")

    if respuesta == "No":
        assert preguntas == [1]  # el segundo guardado ya no pregunta
        assert llamadas == ["refresh", "reload", "refresh", "reload"]
    else:
        assert preguntas == [1, 1]
        assert llamadas == ["finalize", "reload", "finalize", "reload"]


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


def test_vigilancia_excel_se_para_si_se_cierra_durante_la_finalizacion(qapp, monkeypatch):
    """Cerrar el dashboard mientras se aplica la finalización debe detener la
    vigilancia, y la siguiente vuelta usa como referencia el mtime del guardado
    detectado (no el de después del diálogo)."""
    import src.gui.budget_dashboard as bd
    from src.core import services

    ruta = "C:/obra/presupuesto.xlsx"
    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._excel_watchers = {}
    dash._excel_no_finalize = set()
    dash._load_data = lambda: None
    dash._refresh_rows = lambda rutas, on_done=None: None
    bases = []
    mtimes = iter([100.0, 250.0])

    def _fake_wait(r, stop, baseline):
        bases.append(baseline)
        return len(bases) == 1  # solo el primer guardado

    class _FakeService:
        def finalize_budget(self, r, estado=""):
            dash._excel_watchers[ruta].set()  # el usuario cierra el dashboard aquí
            return True

    monkeypatch.setattr(bd.os.path, "getmtime", lambda _p: next(mtimes, 250.0))
    monkeypatch.setattr(bd, "_wait_for_excel_change", _fake_wait)
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    monkeypatch.setattr(services, "BudgetService", _FakeService)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    bd.BudgetDashboardFrame._watch_excel_changes_and_refresh(dash, ruta, "PRESUPUESTADO")

    assert bases == [100.0]  # no se re-arma tras cerrar


def test_vigilancia_excel_rearma_con_el_mtime_del_guardado_detectado(qapp, monkeypatch):
    import src.gui.budget_dashboard as bd
    from src.core import services

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._excel_watchers = {}
    dash._excel_no_finalize = set()
    dash._load_data = lambda: None
    dash._refresh_rows = lambda rutas, on_done=None: None
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
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    bd.BudgetDashboardFrame._watch_excel_changes_and_refresh(dash, "C:/obra/p.xlsx", "PRESUPUESTADO")

    assert bases == [100.0, 250.0]
    assert "C:/obra/p.xlsx" not in dash._excel_watchers
