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
