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
