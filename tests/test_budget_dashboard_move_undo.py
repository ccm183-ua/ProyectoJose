"""Mover proyectos no pregunta; el aviso ofrece Deshacer (carpetas y planificación)."""

from datetime import date

import pytest

try:
    from PySide6.QtWidgets import QMessageBox

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


@pytest.fixture
def mover(qapp, tmp_path, monkeypatch):
    import src.gui.budget_dashboard as bd
    from src.core import database

    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "obras.db"))
    monkeypatch.setenv("CUBIAPP_BACKUP_DIR", str(tmp_path / "backups"))
    with database.get_connection():
        pass
    root = tmp_path / "PRESUPUESTOS"
    for estado in ("EJECUTAR", "EJECUTANDO"):
        (root / estado).mkdir(parents=True)
    boxes = []
    for name in ("question", "information", "warning"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(
            lambda *a, _n=name, **k: boxes.append(_n) or QMessageBox.StandardButton.Yes))

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._root_path = str(root)
    dash._planning_duplicates = set()
    reloads, toasts = [], []
    dash._load_data = lambda: reloads.append(1)
    dash._notify = lambda text, actions=None: toasts.append((text, dict(actions or [])))

    def _obra(estado, numero):
        carpeta = root / estado / f"{numero} OBRA"
        carpeta.mkdir()
        return {"ruta_carpeta": str(carpeta), "numero": numero}

    return bd, dash, _obra, root, boxes, toasts, reloads


def test_move_does_not_ask_and_offers_undo(mover):
    bd, dash, obra, root, boxes, toasts, reloads = mover
    bd.BudgetDashboardFrame._move_project(dash, [obra("EJECUTAR", "114-26")], "EJECUTAR", "EJECUTANDO")
    assert boxes == []
    assert (root / "EJECUTANDO" / "114-26 OBRA").is_dir()
    text, actions = toasts[-1]
    assert text == "1 proyecto movido a EJECUTANDO"
    assert list(actions) == ["Deshacer"]
    assert reloads == [1]


def test_undo_moves_back_and_restores_planning(mover):
    from src.core.repositories.obra_planificacion_repository import get_planes, upsert_plan

    bd, dash, obra, root, boxes, toasts, reloads = mover
    upsert_plan("114-26", inicio_previsto=date(2026, 9, 1), estado_conocido="EJECUTAR")
    before = get_planes(["114-26"])["114-26"]

    bd.BudgetDashboardFrame._move_project(dash, [obra("EJECUTAR", "114-26")], "EJECUTAR", "EJECUTANDO")
    assert get_planes(["114-26"])["114-26"]["inicio_real"] == date.today()

    toasts[-1][1]["Deshacer"]()

    assert (root / "EJECUTAR" / "114-26 OBRA").is_dir()
    assert not (root / "EJECUTANDO" / "114-26 OBRA").exists()
    after = get_planes(["114-26"])["114-26"]
    for field in ("inicio_previsto", "inicio_real", "estado_conocido", "inicio_real_aproximado"):
        assert after[field] == before[field]
    assert toasts[-1][0] == "Movimiento deshecho"
    assert reloads == [1, 1]


def test_undo_removes_plan_row_that_did_not_exist(mover):
    from src.core.repositories.obra_planificacion_repository import get_planes

    bd, dash, obra, root, boxes, toasts, reloads = mover
    bd.BudgetDashboardFrame._move_project(dash, [obra("EJECUTAR", "200-26")], "EJECUTAR", "EJECUTANDO")
    assert "200-26" in get_planes(["200-26"])
    toasts[-1][1]["Deshacer"]()
    assert get_planes(["200-26"]) == {}


def test_failed_move_shows_dialog_with_failures(mover, monkeypatch):
    bd, dash, obra, root, boxes, toasts, reloads = mover

    def _boom(*a, **k):
        raise OSError("carpeta en uso")

    monkeypatch.setattr(bd.shutil, "move", _boom)
    bd.BudgetDashboardFrame._move_project(dash, [obra("EJECUTAR", "114-26")], "EJECUTAR", "EJECUTANDO")
    assert boxes == ["warning"]
    assert toasts == []


def test_restore_plan_snapshot_none_deletes(mover):
    from src.core.repositories.obra_planificacion_repository import (
        get_planes, restore_plan_snapshot, upsert_plan,
    )

    upsert_plan("1-26", notas="x")
    assert restore_plan_snapshot("1-26", None) is None
    assert get_planes(["1-26"]) == {}


# ── Revisión 2026-11-15 ──────────────────────────────────────────────────

def test_undo_keeps_planning_if_it_could_not_be_read_before_moving(mover, monkeypatch):
    import src.core.repositories.obra_planificacion_repository as repo

    bd, dash, obra, root, boxes, toasts, reloads = mover
    repo.upsert_plan("114-26", inicio_previsto=date(2026, 9, 1), notas="andamio")
    real_get = repo.get_planes
    monkeypatch.setattr(repo, "get_planes", lambda *_a: (_ for _ in ()).throw(RuntimeError("bd ocupada")))
    bd.BudgetDashboardFrame._move_project(dash, [obra("EJECUTAR", "114-26")], "EJECUTAR", "EJECUTANDO")
    monkeypatch.setattr(repo, "get_planes", real_get)

    toasts[-1][1]["Deshacer"]()

    plan = repo.get_planes(["114-26"])["114-26"]
    assert plan["inicio_previsto"] == date(2026, 9, 1) and plan["notas"] == "andamio"
    assert (root / "EJECUTAR" / "114-26 OBRA").is_dir()


def test_undo_waits_for_the_running_reload(mover):
    """Deshacer durante la recarga del movimiento: si no esperase, la
    reconciliación de esa recarga apuntaría un inicio real que no ocurrió."""
    from src.core.repositories.obra_planificacion_repository import get_planes, upsert_plan

    bd, dash, obra, root, boxes, toasts, reloads = mover
    upsert_plan("114-26", estado_conocido="EJECUTAR")
    bd.BudgetDashboardFrame._move_project(dash, [obra("EJECUTAR", "114-26")], "EJECUTAR", "EJECUTANDO")
    dash._full_loads_running = 1  # la recarga lanzada por el movimiento sigue en marcha

    toasts[-1][1]["Deshacer"]()
    assert (root / "EJECUTANDO" / "114-26 OBRA").is_dir()  # aún no

    bd.BudgetDashboardFrame._finish_full_load(dash)
    assert (root / "EJECUTAR" / "114-26 OBRA").is_dir()
    assert get_planes(["114-26"])["114-26"]["inicio_real"] is None


def test_full_load_counts_running_and_flushes(qapp, monkeypatch, tmp_path):
    import src.gui.budget_dashboard as bd

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._explorer_mode = False

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
    dash._rebuild_tabs = lambda *a: None
    pendientes = []
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: pendientes.append(cb))

    bd.BudgetDashboardFrame._load_data(dash)
    assert dash._full_loads_running == 1
    hechos = []
    bd.BudgetDashboardFrame._when_full_load_idle(dash, lambda: hechos.append(1))
    assert hechos == []

    pendientes[0](False, RuntimeError("fallo al escanear"))  # también al fallar
    assert dash._full_loads_running == 0 and hechos == [1]

    bd.BudgetDashboardFrame._when_full_load_idle(dash, lambda: hechos.append(2))
    assert hechos == [1, 2]  # sin recarga en marcha, en el momento
