import inspect
import importlib.util
from pathlib import Path
import pytest

from src.core.budget_generator import BudgetGenerator


class _DummyBudgetService:
    def __init__(self):
        self.insert_calls = []
        self.generate_called = 0

    def insert_partidas(self, excel_path, partidas, project_data=None):
        self.insert_calls.append((excel_path, partidas, project_data))
        return True


class _NoUiMessageBox:
    class StandardButton:
        Yes = 1
        No = 0

    @staticmethod
    def information(*args, **kwargs):
        return 0

    @staticmethod
    def warning(*args, **kwargs):
        return 0

    @staticmethod
    def question(*args, **kwargs):
        return _NoUiMessageBox.StandardButton.No


def _build_frame(monkeypatch):
    from src.gui.main_frame import MainFrame
    from src.gui import main_frame as main_mod

    monkeypatch.setattr(main_mod, "QMessageBox", _NoUiMessageBox)
    frame = MainFrame.__new__(MainFrame)
    frame._budget_svc = _DummyBudgetService()
    frame._offer_ai_partidas = lambda *args, **kwargs: None
    frame._request_historical_context = lambda project_data: "contexto confirmado"
    frame._should_offer_context_retry = lambda suggestion_result: False
    frame._try_historical_suggestions = lambda project_data, confirmed_context="": {
        "partidas": [{"concepto": "Hist 1", "cantidad": 1, "unidad": "ud", "precio_unitario": 10}],
        "detected_modules": [{"name": "modulo", "confidence": 0.9}],
        "patterns": [{"concepto": "Patrón A", "frequency": 4}],
    }
    return frame


def test_historical_only_inserts_once(monkeypatch):
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 no disponible en entorno de tests")
    from src.gui import historical_suggestions_dialog as hist_mod
    from src.gui import combined_partidas_review_dialog as review_mod
    from src.gui import historical_selection_next_step_dialog as step_mod

    frame = _build_frame(monkeypatch)

    class HistDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

        def get_selected_partidas(self):
            return [{"concepto": "Hist 1", "cantidad": 1, "unidad": "ud", "precio_unitario": 10}]

    class ReviewDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

        def get_selected_partidas(self):
            return [{"concepto": "Hist 1", "cantidad": 1, "unidad": "ud", "precio_unitario": 10}]

    class StepDialog:
        CREATE_ONLY = "CREATE_ONLY"
        COMPLETE_WITH_AI = "COMPLETE_WITH_AI"
        CANCEL = "CANCEL"

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

        def get_result(self):
            return self.CREATE_ONLY

    monkeypatch.setattr(hist_mod, "HistoricalSuggestionsDialog", HistDialog)
    monkeypatch.setattr(review_mod, "CombinedPartidasReviewDialog", ReviewDialog)
    monkeypatch.setattr(step_mod, "HistoricalSelectionNextStepDialog", StepDialog)
    frame._offer_partidas("budget.xlsx", {"cliente": "X"})

    assert len(frame._budget_svc.insert_calls) == 1
    assert frame._budget_svc.insert_calls[0][1][0]["concepto"] == "Hist 1"


def test_historical_plus_ai_inserts_once_at_end(monkeypatch):
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 no disponible en entorno de tests")
    from src.gui import historical_suggestions_dialog as hist_mod
    from src.gui import combined_partidas_review_dialog as review_mod
    from src.gui import ai_complete_historical_budget_dialog as complete_mod
    from src.gui import historical_selection_next_step_dialog as step_mod

    frame = _build_frame(monkeypatch)

    class HistDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

        def get_selected_partidas(self):
            return [{"concepto": "Hist 1", "cantidad": 1, "unidad": "ud", "precio_unitario": 10}]

    class CompleteDialog:
        def __init__(self, parent, **kwargs):
            self._frame = parent

        def exec(self):
            # Verifica que aún NO se insertó nada antes de generar complementarias/revisar
            assert len(self._frame._budget_svc.insert_calls) == 0
            return 1

        def get_action(self):
            return "ai_completion"

        def get_result(self):
            return {
                "partidas": [{"concepto": "IA 1", "cantidad": 2, "unidad": "ml", "precio_unitario": 12}],
                "source": "ai_completion",
                "mode": "complete_historical_selection",
            }

    class ReviewDialog:
        def __init__(self, parent, historical_partidas=None, ai_partidas=None):
            self._combined = (historical_partidas or []) + (ai_partidas or [])

        def exec(self):
            return 1

        def get_selected_partidas(self):
            return self._combined

    class StepDialog:
        CREATE_ONLY = "CREATE_ONLY"
        COMPLETE_WITH_AI = "COMPLETE_WITH_AI"
        CANCEL = "CANCEL"

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

        def get_result(self):
            return self.COMPLETE_WITH_AI

    monkeypatch.setattr(hist_mod, "HistoricalSuggestionsDialog", HistDialog)
    monkeypatch.setattr(complete_mod, "AICompleteHistoricalBudgetDialog", CompleteDialog)
    monkeypatch.setattr(review_mod, "CombinedPartidasReviewDialog", ReviewDialog)
    monkeypatch.setattr(step_mod, "HistoricalSelectionNextStepDialog", StepDialog)
    frame._offer_partidas("budget.xlsx", {"cliente": "X"})

    assert len(frame._budget_svc.insert_calls) == 1
    inserted = frame._budget_svc.insert_calls[0][1]
    assert len(inserted) == 2
    assert {p["concepto"] for p in inserted} == {"Hist 1", "IA 1"}


def test_ai_empty_keeps_historical(monkeypatch):
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 no disponible en entorno de tests")
    from src.gui import historical_suggestions_dialog as hist_mod
    from src.gui import combined_partidas_review_dialog as review_mod
    from src.gui import ai_complete_historical_budget_dialog as complete_mod
    from src.gui import historical_selection_next_step_dialog as step_mod

    frame = _build_frame(monkeypatch)

    class HistDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

        def get_selected_partidas(self):
            return [{"concepto": "Hist 1", "cantidad": 1, "unidad": "ud", "precio_unitario": 10}]

    class CompleteDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

        def get_action(self):
            return "ai_completion"

        def get_result(self):
            return {"partidas": [], "source": "ai_completion", "mode": "complete_historical_selection"}

    class ReviewDialog:
        def __init__(self, parent, historical_partidas=None, ai_partidas=None):
            assert ai_partidas == []
            self._historical = historical_partidas or []

        def exec(self):
            return 1

        def get_selected_partidas(self):
            return self._historical

    class StepDialog:
        CREATE_ONLY = "CREATE_ONLY"
        COMPLETE_WITH_AI = "COMPLETE_WITH_AI"
        CANCEL = "CANCEL"

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return 1

        def get_result(self):
            return self.COMPLETE_WITH_AI

    monkeypatch.setattr(hist_mod, "HistoricalSuggestionsDialog", HistDialog)
    monkeypatch.setattr(complete_mod, "AICompleteHistoricalBudgetDialog", CompleteDialog)
    monkeypatch.setattr(review_mod, "CombinedPartidasReviewDialog", ReviewDialog)
    monkeypatch.setattr(step_mod, "HistoricalSelectionNextStepDialog", StepDialog)
    frame._offer_partidas("budget.xlsx", {"cliente": "X"})

    assert len(frame._budget_svc.insert_calls) == 1
    inserted = frame._budget_svc.insert_calls[0][1]
    assert len(inserted) == 1
    assert inserted[0]["concepto"] == "Hist 1"


def test_complementary_prompt_contains_guardrails():
    generator = BudgetGenerator(api_key="fake-key")
    captured_prompt = {}

    def _fake_generate(prompt):
        captured_prompt["value"] = prompt
        return [], None

    generator._ai_service.generate_partidas = _fake_generate
    generator.generate_complementary_partidas(
        project_data={"cliente": "Comunidad", "localidad": "Alicante"},
        confirmed_context="Reparación de bajante en patio interior",
        selected_historical_partidas=[{"concepto": "H1", "cantidad": 1, "unidad": "ud", "precio_unitario": 10}],
        historical_result={"detected_modules": [{"name": "bajante", "confidence": 0.9}]},
        user_instructions="No incluir pintura",
    )
    prompt = captured_prompt["value"].lower()
    assert "no las repitas" in prompt
    assert "no las sustituyas" in prompt
    assert "solo partidas complementarias" in prompt


def test_complementary_result_has_expected_metadata():
    generator = BudgetGenerator(api_key="fake-key")
    generator._ai_service.generate_partidas = lambda prompt: (
        [{"concepto": "IA 1", "cantidad": 1, "unidad": "ud", "precio_unitario": 11}],
        None,
    )
    result = generator.generate_complementary_partidas(
        project_data={},
        confirmed_context="ctx",
        selected_historical_partidas=[],
        historical_result={},
    )
    assert result["source"] == "ai_completion"
    assert result["mode"] == "complete_historical_selection"
    assert isinstance(result["partidas"], list)


def test_complete_dialog_does_not_require_tipo_or_plantilla_fields():
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 no disponible en entorno de tests")
    from src.gui.ai_complete_historical_budget_dialog import AICompleteHistoricalBudgetDialog
    source = inspect.getsource(AICompleteHistoricalBudgetDialog)
    assert "Tipo de obra:" not in source
    assert "Plantilla de referencia" not in source


def test_combined_review_sorting_is_disabled_in_source():
    src = Path("src/gui/combined_partidas_review_dialog.py").read_text(encoding="utf-8")
    assert "setSortingEnabled(False)" in src


def test_combined_review_has_input_validations_in_source():
    src = Path("src/gui/combined_partidas_review_dialog.py").read_text(encoding="utf-8")
    assert "concepto vacío" in src
    assert "unidad vacía" in src
    assert "cantidad <= 0" in src
    assert "precio negativo" in src


def test_next_step_dialog_has_compact_clear_buttons_in_source():
    src = Path("src/gui/historical_selection_next_step_dialog.py").read_text(encoding="utf-8")
    assert "Crear presupuesto" in src
    assert "Completar con IA" in src
    assert "Volver" in src
    assert "CREATE_ONLY" in src
    assert "COMPLETE_WITH_AI" in src
    assert "CANCEL" in src


def test_writer_uses_same_title_description_path_without_source_branching():
    src = Path("src/core/excel_partidas_writer.py").read_text(encoding="utf-8")
    assert "partida.get('titulo'" in src
    assert "partida.get('descripcion'" in src
    assert "partida.get('source'" not in src
