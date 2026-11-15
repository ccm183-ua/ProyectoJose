"""
H09: un fallo al publicar el paquete de contexto no debe quedar oculto tras un
"Análisis completado". El resumen del diálogo lo hace visible y cambia el estado.
"""

import pytest

try:
    from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QTextEdit

    from src.gui.historical_analysis_dialog import HistoricalAnalysisDialog

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


def _make_dialog():
    dlg = HistoricalAnalysisDialog.__new__(HistoricalAnalysisDialog)
    QDialog.__init__(dlg)
    dlg._status_label = QLabel()
    dlg._summary = QTextEdit()
    dlg._run_btn = QPushButton()
    return dlg


def test_render_summary_shows_publication_failure(qapp):
    dlg = _make_dialog()

    dlg._render_analysis_summary(
        {
            "run_id": None,
            "errores": 1,
            "publication_error": "disco lleno",
            "status_counts": {},
        }
    )

    assert "incidencias" in dlg._status_label.text().lower()
    assert "disco lleno" in dlg._summary.toPlainText()


def test_render_summary_reports_clean_completion_when_no_errors(qapp):
    dlg = _make_dialog()

    dlg._render_analysis_summary({"run_id": None, "errores": 0, "status_counts": {}})

    assert dlg._status_label.text() == "Análisis completado"
