"""
S1-D / H04: cancelar la descripción o la revisión de partidas —o fallar la
inserción— no marca el presupuesto como terminado. Regresión del flujo de
partidas mudo, que finalizaba pasara lo que pasara.
"""

import importlib.util
import os

import pytest

from src.core.services.budget_partidas_flow import (
    OUTCOME_APPLIED,
    OUTCOME_CANCELLED,
    OUTCOME_EMPTY,
    OUTCOME_FAILED,
)
from src.core.services.budget_service import BudgetCreationResult, BudgetService
from src.core.template_manager import TemplateManager


def _proyecto():
    return {
        "numero": "99",
        "fecha": "13-02-26",
        "cliente": "C",
        "calle": "Calle Test",
        "num_calle": "1",
        "codigo_postal": "03001",
        "tipo": "Obra",
        "localidad": "Alicante",
    }


class _StandardButton:
    Yes = 1
    No = 0


class _MessageBoxSpy:
    StandardButton = _StandardButton
    question_result = _StandardButton.Yes
    question_calls = []

    @classmethod
    def question(cls, *args, **kwargs):
        cls.question_calls.append(args)
        return cls.question_result

    @staticmethod
    def information(*args, **kwargs):
        return 0

    @staticmethod
    def warning(*args, **kwargs):
        return 0

    @staticmethod
    def critical(*args, **kwargs):
        return 0


class _Spy:
    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))


class _FakeBudgetService:
    def __init__(self, create_result=None, insert_ok=True, finalize_ok=True, discard_ok=True):
        self.create_result = create_result
        self.insert_ok = insert_ok
        self.finalize_ok = finalize_ok
        self.discard_ok = discard_ok
        self.insert_calls = []
        self.finalize_calls = []
        self.discard_calls = []

    def get_template_path(self):
        return "plantilla.xlsx"

    def create_budget(self, *args, **kwargs):
        return self.create_result

    def insert_partidas(self, excel_path, partidas, project_data=None):
        self.insert_calls.append((excel_path, partidas, project_data))
        return self.insert_ok

    def append_partidas(self, excel_path, partidas):
        return self.insert_ok

    def finalize_budget(self, *args, **kwargs):
        self.finalize_calls.append((args, kwargs))
        return self.finalize_ok

    def discard_budget(self, *args, **kwargs):
        self.discard_calls.append((args, kwargs))
        return self.discard_ok


class _DummyDbService:
    @staticmethod
    def get_admin_para_comunidad(comunidad_data):
        return None


def _skip_without_pyside():
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 no disponible en entorno de tests")


def _frame(monkeypatch, tmp_path, budget_svc=None, question_answer=None, chosen=None):
    from src.core.settings import Settings
    from src.gui import main_frame as main_mod
    from src.gui.main_frame import MainFrame

    _MessageBoxSpy.question_result = (
        _StandardButton.Yes if question_answer is None else question_answer
    )
    _MessageBoxSpy.question_calls = []
    monkeypatch.setattr(main_mod, "QMessageBox", _MessageBoxSpy)
    # Solo se redirige la carpeta de guardado: el resto de claves (base de datos)
    # deben seguir resolviéndose por CUBIAPP_DB_PATH para aislar el test.
    monkeypatch.setattr(
        "src.core.settings.Settings.get_default_path",
        lambda self, key: str(tmp_path) if key == Settings.PATH_SAVE_BUDGETS else None,
    )
    destino = chosen or (tmp_path / "Obra" / "Obra.xlsx")
    monkeypatch.setattr(
        main_mod.QFileDialog, "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(destino), "")),
    )

    frame = MainFrame.__new__(MainFrame)
    frame._budget_svc = budget_svc or _FakeBudgetService()
    frame._db_svc = _DummyDbService()
    frame._obtain_project_data = lambda: (dict(_proyecto()), "Obra")
    frame._buscar_comunidad_para_presupuesto = lambda *args, **kwargs: None
    frame._open_dashboard = lambda *args, **kwargs: None
    frame._schedule_historical_feedback = _Spy()
    return frame


def _partida():
    return {"concepto": "P1", "cantidad": 1, "unidad": "ud", "precio_unitario": 10}


def test_cancelar_voz_devuelve_cancelled(monkeypatch, tmp_path):
    _skip_without_pyside()
    from src.gui import voice_budget_dialog as voice_mod

    class VoiceDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 0

        def get_result(self):
            return {}

    monkeypatch.setattr(voice_mod, "VoiceBudgetDialog", VoiceDialog)
    frame = _frame(monkeypatch, tmp_path)

    assert frame._offer_partidas_unified("Obra.xlsx", {}) == OUTCOME_CANCELLED


def test_cancelar_revision_devuelve_cancelled(monkeypatch, tmp_path):
    _skip_without_pyside()
    from src.gui import voice_budget_dialog as voice_mod
    from src.gui import combined_partidas_review_dialog as review_mod

    class VoiceDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

        def get_result(self):
            return {"partidas": [_partida()], "cobertura": None}

    class ReviewDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 0

        def get_selected_partidas(self):
            return []

    monkeypatch.setattr(voice_mod, "VoiceBudgetDialog", VoiceDialog)
    monkeypatch.setattr(review_mod, "CombinedPartidasReviewDialog", ReviewDialog)
    frame = _frame(monkeypatch, tmp_path)

    assert frame._offer_partidas_unified("Obra.xlsx", {}) == OUTCOME_CANCELLED


def test_fallo_de_insercion_devuelve_failed(monkeypatch, tmp_path):
    _skip_without_pyside()
    from src.gui import voice_budget_dialog as voice_mod
    from src.gui import combined_partidas_review_dialog as review_mod

    class VoiceDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

        def get_result(self):
            return {"partidas": [_partida()], "cobertura": None}

    class ReviewDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

        def get_selected_partidas(self):
            return [_partida()]

    monkeypatch.setattr(voice_mod, "VoiceBudgetDialog", VoiceDialog)
    monkeypatch.setattr(review_mod, "CombinedPartidasReviewDialog", ReviewDialog)
    frame = _frame(
        monkeypatch, tmp_path, budget_svc=_FakeBudgetService(insert_ok=False),
    )

    assert frame._offer_partidas_unified("Obra.xlsx", {}) == OUTCOME_FAILED


@pytest.mark.parametrize(
    "outcome", [OUTCOME_CANCELLED, OUTCOME_FAILED, OUTCOME_EMPTY, None],
)
def test_create_budget_no_finaliza_si_no_se_aplicaron_partidas(
    monkeypatch, tmp_path, outcome,
):
    _skip_without_pyside()
    destino = tmp_path / "Obra" / "Obra.xlsx"
    svc = _FakeBudgetService(create_result=BudgetCreationResult(
        success=True,
        excel_path=str(destino),
        folder_path=str(destino.parent),
    ))
    frame = _frame(monkeypatch, tmp_path, budget_svc=svc)
    frame._offer_partidas_unified = lambda *args, **kwargs: outcome

    frame._create_budget()

    assert svc.finalize_calls == []
    assert frame._schedule_historical_feedback.calls == []
    assert svc.discard_calls == []


def test_create_budget_finaliza_cuando_se_aplicaron_partidas(monkeypatch, tmp_path):
    _skip_without_pyside()
    destino = tmp_path / "Obra" / "Obra.xlsx"
    svc = _FakeBudgetService(create_result=BudgetCreationResult(
        success=True,
        excel_path=str(destino),
        folder_path=str(destino.parent),
    ))
    frame = _frame(monkeypatch, tmp_path, budget_svc=svc)
    frame._offer_partidas_unified = lambda *args, **kwargs: OUTCOME_APPLIED

    frame._create_budget()

    assert len(svc.finalize_calls) == 1
    assert svc.finalize_calls[0][0][0] == str(destino)
    assert len(frame._schedule_historical_feedback.calls) == 1


def test_descartar_borrador_elimina_el_presupuesto(monkeypatch, tmp_path):
    _skip_without_pyside()
    destino = tmp_path / "Obra" / "Obra.xlsx"
    svc = _FakeBudgetService(create_result=BudgetCreationResult(
        success=True,
        excel_path=str(destino),
        folder_path=str(destino.parent),
    ))
    frame = _frame(
        monkeypatch, tmp_path, budget_svc=svc, question_answer=_StandardButton.No,
    )
    frame._offer_partidas_unified = lambda *args, **kwargs: OUTCOME_CANCELLED

    frame._create_budget()

    assert svc.discard_calls == [((str(destino), str(destino.parent)), {})]


def test_cancelar_conserva_borrador_sin_finalizar_en_sqlite(monkeypatch, tmp_path):
    _skip_without_pyside()
    template_path = TemplateManager().get_template_path()
    if not os.path.exists(template_path):
        pytest.skip("Plantilla no disponible")
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_cancel_persist.db"))
    destino = tmp_path / "Obra" / "Obra.xlsx"

    from src.core import db_repository

    frame = _frame(monkeypatch, tmp_path, budget_svc=BudgetService())
    frame._offer_partidas_unified = lambda *args, **kwargs: OUTCOME_CANCELLED

    frame._create_budget()

    assert os.path.exists(destino)
    assert db_repository.get_presupuesto_por_ruta(str(destino)) is None
    assert frame._schedule_historical_feedback.calls == []


def test_descartar_cancelado_no_deja_rastro_en_sqlite(monkeypatch, tmp_path):
    _skip_without_pyside()
    template_path = TemplateManager().get_template_path()
    if not os.path.exists(template_path):
        pytest.skip("Plantilla no disponible")
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_cancel_discard.db"))
    destino = tmp_path / "Obra" / "Obra.xlsx"

    from src.core import db_repository

    frame = _frame(
        monkeypatch,
        tmp_path,
        budget_svc=BudgetService(),
        question_answer=_StandardButton.No,
    )
    frame._offer_partidas_unified = lambda *args, **kwargs: OUTCOME_CANCELLED

    frame._create_budget()

    assert not os.path.exists(destino)
    assert not destino.parent.exists()
    assert all(
        entry["ruta_excel"] != str(destino)
        for entry in db_repository.get_historial_reciente()
    )
    assert frame._schedule_historical_feedback.calls == []
