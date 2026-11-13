"""Planificación de obras en la interfaz (offscreen)."""

from datetime import date

import pytest

try:
    from PySide6.QtWidgets import QMessageBox

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


@pytest.fixture
def avisos(monkeypatch):
    vistos = []
    for nombre in ("information", "warning", "critical"):
        monkeypatch.setattr(
            QMessageBox, nombre, staticmethod(lambda *a, _n=nombre, **k: vistos.append(_n))
        )
    return vistos


# ── P4: diálogo ─────────────────────────────────────────────────────────

def test_dialogo_precarga_y_devuelve_cambios(qapp):
    from src.gui.obra_planning_dialog import ObraPlanningDialog

    plan = {"inicio_previsto": date(2026, 7, 13), "notas": "andamio", "margen_aviso_dias": None}
    dlg = ObraPlanningDialog(None, titulo="114-26 C.P. RAFAEL ASÍN", plan=plan, margen_general=7)
    assert dlg._inicio_previsto.is_set() and dlg._inicio_previsto.value() == date(2026, 7, 13)
    assert not dlg._fin_previsto.is_set()

    dlg._fin_previsto.set_value(date(2026, 7, 31))
    dlg._margen.setValue(15)
    dlg._on_save()

    cambios = dlg.get_changes()
    assert cambios["inicio_previsto"] == date(2026, 7, 13)
    assert cambios["fin_previsto"] == date(2026, 7, 31)
    assert cambios["margen_aviso_dias"] == 15
    assert cambios["notas"] == "andamio"


def test_dialogo_propuesta_desde_el_nombre_viene_precargada(qapp):
    from src.gui.obra_planning_dialog import ObraPlanningDialog

    dlg = ObraPlanningDialog(None, titulo="127-25 …", plan={}, margen_general=7,
                             propuesta=(date(2026, 7, 1), True))
    assert dlg._inicio_previsto.value() == date(2026, 7, 1)
    assert "aproximada" in dlg._aviso_propuesta.text()


def test_dialogo_rechaza_fin_anterior_al_inicio(qapp, avisos):
    from src.gui.obra_planning_dialog import ObraPlanningDialog

    dlg = ObraPlanningDialog(None, titulo="x", plan={"inicio_previsto": date(2026, 7, 13)}, margen_general=7)
    dlg._fin_previsto.set_value(date(2026, 7, 1))
    dlg._on_save()
    assert dlg.get_changes() is None and avisos == ["warning"]


def test_dialogo_quitar_fechas_y_cancelar(qapp):
    from src.gui.obra_planning_dialog import ObraPlanningDialog

    plan = {"inicio_previsto": date(2026, 7, 13), "inicio_real": date(2026, 7, 14)}
    dlg = ObraPlanningDialog(None, titulo="x", plan=plan, margen_general=7)
    dlg._on_clear_dates()
    cambios = dlg.get_changes()
    assert cambios["inicio_previsto"] is None and cambios["inicio_real"] is None

    dlg2 = ObraPlanningDialog(None, titulo="x", plan=plan, margen_general=7)
    dlg2.reject()
    assert dlg2.get_changes() is None


def test_dialogo_varias_obras_solo_fechas_previstas(qapp):
    from src.gui.obra_planning_dialog import ObraPlanningDialog

    dlg = ObraPlanningDialog(None, titulo="3 obras", plan={}, margen_general=7, varias=True)
    dlg._inicio_previsto.set_value(date(2026, 9, 1))
    dlg._on_save()
    assert dlg.get_changes() == {"inicio_previsto": date(2026, 9, 1), "fin_previsto": None}


# ── P6: "Mover a…" registra las fechas reales ───────────────────────────

@pytest.fixture
def mover(qapp, tmp_path, monkeypatch, avisos):
    import src.gui.budget_dashboard as bd
    from src.core import database

    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "obras.db"))
    monkeypatch.setenv("CUBIAPP_BACKUP_DIR", str(tmp_path / "backups"))
    with database.get_connection():
        pass
    root = tmp_path / "PRESUPUESTOS"
    for estado in ("EJECUTAR", "EJECUTANDO", "TERMINADO"):
        (root / estado).mkdir(parents=True)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._root_path = str(root)
    dash._planning_duplicates = set()
    dash._load_data = lambda: None

    def _obra(estado, numero):
        carpeta = root / estado / f"{numero} OBRA"
        carpeta.mkdir()
        return {"ruta_carpeta": str(carpeta), "numero": numero}

    return dash, _obra


def test_mover_a_ejecutando_y_terminado_registra_fechas(mover):
    import src.gui.budget_dashboard as bd
    from src.core.repositories.obra_planificacion_repository import get_planes

    dash, obra = mover
    p = obra("EJECUTAR", "114-26")
    bd.BudgetDashboardFrame._move_project(dash, [p], "EJECUTAR", "EJECUTANDO")
    plan = get_planes(["114-26"])["114-26"]
    assert plan["inicio_real"] == date.today() and not plan["inicio_real_aproximado"]

    p2 = {"ruta_carpeta": p["ruta_carpeta"].replace("EJECUTAR", "EJECUTANDO", 1), "numero": "114-26"}
    bd.BudgetDashboardFrame._move_project(dash, [p2], "EJECUTANDO", "TERMINADO")
    plan = get_planes(["114-26"])["114-26"]
    assert plan["fin_real"] == date.today() and plan["estado_conocido"] == "TERMINADO"


def test_mover_numero_repetido_no_registra(mover):
    import src.gui.budget_dashboard as bd
    from src.core.repositories.obra_planificacion_repository import get_planes

    dash, obra = mover
    dash._planning_duplicates = {"114-26"}
    bd.BudgetDashboardFrame._move_project(dash, [obra("EJECUTAR", "114-26")], "EJECUTAR", "EJECUTANDO")
    assert get_planes(["114-26"]) == {}


def test_movimiento_fallido_no_registra(mover, monkeypatch):
    import src.gui.budget_dashboard as bd
    from src.core.repositories.obra_planificacion_repository import get_planes

    dash, obra = mover

    def _boom(*a, **k):
        raise OSError("carpeta en uso")

    monkeypatch.setattr(bd.shutil, "move", _boom)
    bd.BudgetDashboardFrame._move_project(dash, [obra("EJECUTAR", "114-26")], "EJECUTAR", "EJECUTANDO")
    assert get_planes(["114-26"]) == {}


# ── P5: columnas y celdas en el dashboard ───────────────────────────────

def _tabla(state):
    import src.gui.budget_dashboard as bd
    from PySide6.QtWidgets import QTableWidget

    cols = bd._columns_for_state(state)
    table = QTableWidget(1, len(cols))
    table.setHorizontalHeaderLabels([c[0] for c in cols])
    bd.BudgetDashboardFrame._place_planning_columns(table, state)
    return table


def _visual_headers(table):
    hdr = table.horizontalHeader()
    return [table.horizontalHeaderItem(hdr.logicalIndex(v)).text() for v in range(table.columnCount())]


def test_columnas_solo_en_estados_de_planificacion_y_detras_de_proyecto(qapp):
    import src.gui.budget_dashboard as bd

    assert bd._columns_for_state("PRESUPUESTADO") == bd._COLUMNS
    assert _visual_headers(_tabla("EJECUTAR"))[:5] == ["Nº", "Proyecto", "Inicio previsto", "Fin previsto", "Aviso"]
    assert _visual_headers(_tabla("TERMINADO"))[2:5] == ["Inicio real", "Fin real", "Duración"]


def _dash():
    import src.gui.budget_dashboard as bd

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._planning_margin = lambda: 7
    return dash


def test_celdas_ejecutar_propuesta_y_aviso(qapp):
    import src.gui.budget_dashboard as bd
    from datetime import timedelta

    table = _tabla("EJECUTAR")
    base = len(bd._COLUMNS)
    proj = {"planificacion": {}, "planificacion_propuesta": (date(2026, 7, 1), True)}
    bd.BudgetDashboardFrame._fill_planning_cells(_dash(), table, 0, proj, "EJECUTAR")
    item = table.item(0, base)
    assert item.text() == "≈ 01/07/2026" and item.font().italic()

    pronto = date.today() + timedelta(days=3)
    proj = {"planificacion": {"inicio_previsto": pronto}, "planificacion_propuesta": None}
    bd.BudgetDashboardFrame._fill_planning_cells(_dash(), table, 0, proj, "EJECUTAR")
    assert table.item(0, base).text() == pronto.strftime("%d/%m/%Y")
    assert table.item(0, base + 2).text() == "en 3 días"


def test_celdas_numero_repetido(qapp):
    import src.gui.budget_dashboard as bd

    table = _tabla("EJECUTANDO")
    bd.BudgetDashboardFrame._fill_planning_cells(
        _dash(), table, 0, {"planificacion_duplicado": True}, "EJECUTANDO"
    )
    assert table.item(0, len(bd._COLUMNS)).text() == "nº repetido"


def test_doble_clic_segun_columna(qapp):
    import src.gui.budget_dashboard as bd

    llamadas = []
    dash = _dash()
    dash._current_state = lambda: "EJECUTAR"
    dash._on_planning = lambda: llamadas.append("planificacion")
    dash._on_preview = lambda: llamadas.append("vista previa")

    class _Index:
        def __init__(self, col):
            self._col = col

        def column(self):
            return self._col

    bd.BudgetDashboardFrame._on_item_dblclick(dash, _Index(len(bd._COLUMNS)))
    bd.BudgetDashboardFrame._on_item_dblclick(dash, _Index(1))
    dash._current_state = lambda: "PRESUPUESTADO"
    bd.BudgetDashboardFrame._on_item_dblclick(dash, _Index(len(bd._COLUMNS)))
    assert llamadas == ["planificacion", "vista previa", "vista previa"]


# ── P7: margen general desde Configuración ──────────────────────────────

def test_configurar_margen_de_aviso(qapp, monkeypatch, tmp_path):
    import src.gui.main_frame as mf
    from PySide6.QtWidgets import QInputDialog
    from src.core.settings import Settings

    monkeypatch.setenv("CUBIAPP_CONFIG_DIR", str(tmp_path / "config"))
    vistos = []
    monkeypatch.setattr(QInputDialog, "getInt",
                        staticmethod(lambda *a, **k: vistos.append(a[3]) or (15, True)))
    frame = mf.MainFrame.__new__(mf.MainFrame)
    mf.MainFrame._configure_obra_margin(frame)
    assert vistos == [7]                                  # muestra el valor actual
    assert Settings().get_obra_margen_aviso_dias() == 15

    monkeypatch.setattr(QInputDialog, "getInt", staticmethod(lambda *a, **k: (30, False)))
    mf.MainFrame._configure_obra_margin(frame)            # cancelar no guarda
    assert Settings().get_obra_margen_aviso_dias() == 15
