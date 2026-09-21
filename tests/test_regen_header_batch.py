"""S3-B / H13: la regeneración masiva de cabeceras se valida una sola vez.

Un lote sin ambigüedades pide una única confirmación; las excepciones (Nº repetido
en la relación, comunidad solo aproximada, archivo inexistente) quedan pendientes
sin interrumpir ni modificarse.
"""

import pytest

try:
    from PySide6.QtWidgets import QMessageBox

    from src.core import excel_relation_reader
    from src.core.services import BudgetService, DatabaseService
    from src.core.settings import Settings
    from src.gui import budget_dashboard, dialogs
    from src.gui.budget_dashboard import BudgetDashboardFrame

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


@pytest.fixture
def batch(qapp, monkeypatch, tmp_path):
    relation = tmp_path / "relacion.xlsx"
    relation.write_text("x")
    monkeypatch.setattr(
        Settings,
        "get_default_path",
        lambda self, key: str(relation) if key == Settings.PATH_RELATION_FILE else "",
    )

    budgets = []

    class _Reader:
        def read(self, path):
            return budgets, None

    monkeypatch.setattr(excel_relation_reader, "ExcelRelationReader", _Reader)

    comunidades = {"Comunidad Exacta": {"id": 1, "cif": "A1", "administracion_id": None}}
    monkeypatch.setattr(
        DatabaseService,
        "buscar_comunidad",
        staticmethod(lambda nombre: (comunidades.get(nombre), [{"nombre": "parecida"}])),
    )
    monkeypatch.setattr(DatabaseService, "get_admin_para_comunidad", staticmethod(lambda c: None))

    written = []
    monkeypatch.setattr(BudgetService, "update_header_fields", lambda self, ruta, data: written.append(ruta) or True)
    monkeypatch.setattr(BudgetService, "finalize_budget", lambda self, *a, **k: True)

    dialogs_asked = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: dialogs_asked.append(a[2]) or QMessageBox.StandardButton.Yes
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: 0)
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: 0)

    def _no_individual_prompt(*a, **k):
        raise AssertionError("el lote no debe recurrir al flujo individual")

    monkeypatch.setattr(dialogs, "obtain_project_data", _no_individual_prompt)

    frame = BudgetDashboardFrame()
    monkeypatch.setattr(frame, "_load_data", lambda: None)
    yield frame, budgets, written, dialogs_asked, tmp_path
    frame.close()


def _budget(numero, cliente="Comunidad Exacta"):
    return {"numero": numero, "cliente": cliente, "calle": "C", "importe": "1"}


def _sel(tmp_path, numero, existe=True):
    path = tmp_path / f"{numero}.xlsx"
    if existe:
        path.write_text("x")
    return {"numero": numero, "ruta_excel": str(path)}


def test_lote_limpio_se_valida_con_una_sola_confirmacion(batch):
    frame, budgets, written, asked, tmp_path = batch
    selected = []
    for i in range(10):
        budgets.append(_budget(f"{i}-26"))
        selected.append(_sel(tmp_path, f"{i}-26"))

    frame._edit_regen_header_selected(selected)

    assert len(asked) == 1
    assert len(written) == 10


def test_excepciones_quedan_pendientes_sin_tocar_y_sin_preguntar(batch):
    frame, budgets, written, asked, tmp_path = batch
    budgets += [
        _budget("1-26"),
        _budget("2-26"), _budget("2-26"),  # Nº repetido: ambiguo
        _budget("3-26", cliente="Solo Parecida"),  # comunidad no exacta
    ]
    selected = [
        _sel(tmp_path, "1-26"),
        _sel(tmp_path, "2-26"),
        _sel(tmp_path, "3-26"),
        _sel(tmp_path, "4-26", existe=False),
    ]

    frame._edit_regen_header_selected(selected)

    assert len(asked) == 1
    assert "3 quedarán pendientes" in asked[0]
    assert [p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for p in written] == ["1-26.xlsx"]
