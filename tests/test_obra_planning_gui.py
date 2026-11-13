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
