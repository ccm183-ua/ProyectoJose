"""Tests offscreen de la biblioteca de partidas en la interfaz."""

from datetime import date

import pytest

try:
    from PySide6.QtWidgets import QMessageBox

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")

from src.core.partida_library import LibraryLine, PartidaLibrary, to_candidate


def _library():
    return PartidaLibrary([
        LibraryLine(1, 10, "001-26 Obra A", "SUSTITUCIÓN BAJANTE PVC.\nSustitución de bajante de 110 mm",
                    "sustitucion bajante pvc", "ml", "m", 30.0, "approved", date(2026, 1, 1), "sustitucion_bajante"),
        LibraryLine(2, 11, "002-26 Obra B", "Bajante PVC", "sustitucion bajante pvc", "m", "m", 34.0,
                    "unreviewed", None, "sustitucion_bajante"),
        LibraryLine(3, 12, "003-26 Obra C", "Pintura escalera", "pintura escalera", "p.a.", "p.a.", 700.0,
                    "unreviewed", None, "pintura"),
    ])


# ── H5: revisión ────────────────────────────────────────────────────────

def test_revision_etiqueta_las_partidas_de_biblioteca(qapp):
    from src.gui.combined_partidas_review_dialog import CombinedPartidasReviewDialog

    grupo = _library().search("bajante").groups[0]
    dlg = CombinedPartidasReviewDialog(None, library_partidas=[to_candidate(grupo)])

    assert [r["origin"] for r in dlg._rows] == ["Biblioteca · aprobada"]
    assert dlg._rows[0]["raw"]["source"] == "library"
    tooltip = dlg._table.item(0, 1).toolTip()
    assert "Base del precio: mediana de obras aprobadas" in tooltip


# ── H6: diálogo ─────────────────────────────────────────────────────────

def _safe(work):
    try:
        return True, work()
    except Exception as exc:  # noqa: BLE001
        return False, exc


def test_dialogo_busca_y_devuelve_la_cesta(qapp):
    from src.gui.partida_library_dialog import PartidaLibraryDialog

    dlg = PartidaLibraryDialog(None, library=_library())
    dlg.set_query("bajante")
    assert len(dlg._result.groups) == 1

    dlg.add_group_to_basket(0)
    dlg.accept()
    candidatas = dlg.get_candidates()
    assert len(candidatas) == 1 and candidatas[0]["precio_unitario"] == 30.0
    assert candidatas[0]["library_price_basis"] == "median_approved"


def test_dialogo_usar_precio_de_una_obra(qapp):
    from src.gui.partida_library_dialog import PartidaLibraryDialog

    dlg = PartidaLibraryDialog(None, library=_library())
    dlg.set_query("bajante")
    obra_b = [l for l in dlg._result.groups[0].lines if l.partida_id == 2][0]
    dlg.add_group_to_basket(0, obra_b)
    dlg.accept()
    assert dlg.get_candidates()[0]["precio_unitario"] == 34.0


def test_dialogo_no_devuelve_nada_al_cancelar(qapp):
    from src.gui.partida_library_dialog import PartidaLibraryDialog

    dlg = PartidaLibraryDialog(None, library=_library())
    dlg.set_query("bajante")
    dlg.add_group_to_basket(0)
    dlg.reject()
    assert dlg.get_candidates() == []


def test_dialogo_avisa_si_falla_la_carga(qapp, monkeypatch):
    import src.gui.partida_library_dialog as mod

    def _boom():
        raise RuntimeError("database is locked")

    monkeypatch.setattr(mod.PartidaLibrary, "load", staticmethod(_boom))
    monkeypatch.setattr(mod, "run_in_background", lambda work, cb: cb(*_safe(work)))
    dlg = mod.PartidaLibraryDialog(None)
    assert "database is locked" in dlg._status.text()
    assert dlg._result.groups == []


def test_dialogo_quitar_de_la_cesta_y_boton_continuar(qapp):
    from src.gui.partida_library_dialog import PartidaLibraryDialog

    dlg = PartidaLibraryDialog(None, library=_library())
    dlg.set_query("bajante")
    assert not dlg._btn_ok.isEnabled()
    dlg.add_group_to_basket(0)
    assert dlg._btn_ok.isEnabled() and "(1)" in dlg._btn_ok.text()
    dlg._basket_list.setCurrentRow(0)
    dlg._remove_from_basket()
    assert dlg._basket == [] and not dlg._btn_ok.isEnabled()


# ── H7: dashboard ───────────────────────────────────────────────────────

def test_dashboard_anade_desde_la_biblioteca_sin_duplicados(qapp, monkeypatch):
    import src.gui.budget_dashboard as bd
    from src.core import services

    candidata = to_candidate(_library().search("bajante").groups[0])
    otra = to_candidate(_library().search("pintura").groups[0])
    escritas = []

    class _FakeService:
        def read_budget(self, ruta):
            return {"partidas": [dict(candidata)]}          # la bajante ya está en el Excel

        def append_partidas(self, ruta, partidas):
            escritas.extend(partidas)
            return True

        def finalize_budget(self, ruta, estado=""):
            return True

    class _FakeLibraryDialog:
        def __init__(self, parent=None, library=None):
            pass

        def exec(self):
            return 1

        def get_candidates(self):
            return [candidata, otra]

    class _FakeReview:
        def __init__(self, parent, library_partidas=None, **kw):
            self._p = library_partidas

        def exec(self):
            return 1

        def get_selected_partidas(self):
            return self._p

    monkeypatch.setattr(services, "BudgetService", _FakeService)
    monkeypatch.setattr("src.gui.partida_library_dialog.PartidaLibraryDialog", _FakeLibraryDialog)
    monkeypatch.setattr("src.gui.combined_partidas_review_dialog.CombinedPartidasReviewDialog", _FakeReview)
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._current_state = lambda: "PRESUPUESTADO"
    dash._load_data = lambda: None
    bd.BudgetDashboardFrame._edit_add_from_library(dash, "C:/obra/p.xlsx")

    assert [p["titulo"] for p in escritas] == ["Pintura escalera"]


def test_dashboard_biblioteca_cancelada_no_escribe(qapp, monkeypatch):
    import src.gui.budget_dashboard as bd
    from src.core import services

    escritas = []

    class _FakeService:
        def read_budget(self, ruta):
            return {"partidas": []}

        def append_partidas(self, ruta, partidas):
            escritas.extend(partidas)
            return True

    class _Cancelled:
        def __init__(self, parent=None, library=None):
            pass

        def exec(self):
            return 0

        def get_candidates(self):
            return []

    monkeypatch.setattr(services, "BudgetService", _FakeService)
    monkeypatch.setattr("src.gui.partida_library_dialog.PartidaLibraryDialog", _Cancelled)
    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    bd.BudgetDashboardFrame._edit_add_from_library(dash, "C:/obra/p.xlsx")
    assert escritas == []
