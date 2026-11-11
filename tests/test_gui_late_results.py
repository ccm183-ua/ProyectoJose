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


def _wait_until(qapp, cond, timeout=5.0):
    import time

    end = time.time() + timeout
    while not cond() and time.time() < end:
        qapp.processEvents()
        time.sleep(0.01)
    assert cond()


def test_coalescing_task_no_ejecuta_en_paralelo_y_agrupa_peticiones(qapp):
    import threading

    from src.utils.helpers import CoalescingBackgroundTask

    gate = threading.Event()
    state = {"runs": 0, "concurrent": 0, "max_concurrent": 0}
    done = []

    def work():
        state["concurrent"] += 1
        state["max_concurrent"] = max(state["max_concurrent"], state["concurrent"])
        state["runs"] += 1
        gate.wait(2)
        state["concurrent"] -= 1
        return state["runs"]

    task = CoalescingBackgroundTask(work, lambda ok, r: done.append((ok, r)))
    for _ in range(5):  # cinco acciones seguidas mientras la primera trabaja
        task.request()
    gate.set()
    _wait_until(qapp, lambda: done)

    assert state["max_concurrent"] == 1
    assert state["runs"] == 2  # la primera + una única repetición agrupada
    assert done == [(True, 2)]
    assert not task.running


def test_coalescing_task_entrega_errores_al_callback(qapp):
    from src.utils.helpers import CoalescingBackgroundTask

    done = []

    def boom():
        raise RuntimeError("database is locked")

    CoalescingBackgroundTask(boom, lambda ok, r: done.append((ok, str(r)))).request()
    _wait_until(qapp, lambda: done)
    assert done == [(False, "database is locked")]


@pytest.mark.parametrize("respuesta,esperado", [("No", "refresh"), ("Yes", "finalize")])
def test_guardar_excel_pregunta_antes_de_finalizar(qapp, monkeypatch, respuesta, esperado):
    """Decisión E1: al guardar el Excel abierto desde el dashboard ya no se
    finaliza sin preguntar; con "No" solo se refresca la caché."""
    import src.gui.budget_dashboard as bd
    from src.core import services

    llamadas = []

    class _FakeService:
        def finalize_budget(self, ruta, estado=""):
            llamadas.append("finalize"); return True

        def refresh_budget_cache_entry(self, ruta, estado=""):
            llamadas.append("refresh"); return True

    mtimes = iter([100.0, 200.0])
    monkeypatch.setattr(bd.os.path, "getmtime", lambda _p: next(mtimes, 200.0))
    monkeypatch.setattr(bd.time, "sleep", lambda _s: None)
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    monkeypatch.setattr(services, "BudgetService", _FakeService)
    preguntas = []
    monkeypatch.setattr(
        QMessageBox, "question",
        staticmethod(lambda *a, **k: preguntas.append(1) or getattr(QMessageBox.StandardButton, respuesta)),
    )

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._load_data = lambda: llamadas.append("reload")
    bd.BudgetDashboardFrame._watch_excel_changes_and_refresh(dash, "C:/obra/presupuesto.xlsx", "PRESUPUESTADO")

    assert preguntas == [1]
    assert llamadas == [esperado, "reload"]
