from src.core.historical_context import (
    build_initial_historical_context,
    is_generic_historical_context,
    is_useful_historical_context,
    request_historical_suggestions_for_context,
)


class FakeHistoricalSuggestionService:
    def __init__(self):
        self.calls = []

    def suggest_for_project(self, project_data, user_description=""):
        self.calls.append(
            {
                "project_data": project_data,
                "user_description": user_description,
            }
        )
        return {"source": "historical", "partidas": []}


def test_empty_description_is_not_useful():
    assert is_useful_historical_context("") is False


def test_generic_description_is_not_useful():
    assert is_useful_historical_context("reparación general") is False
    assert is_useful_historical_context("rehabilitación de edificio") is False
    assert is_useful_historical_context("obra comunidad") is False
    assert is_useful_historical_context("varios trabajos") is False


def test_valid_real_contexts_are_useful():
    assert is_useful_historical_context("Reparación de bajante en patio interior con sustitución de PVC") is True
    assert is_useful_historical_context("Impermeabilización de cubierta con reparación de filtraciones") is True
    assert is_useful_historical_context("Reparación de viga con refuerzo estructural") is True


def test_module_detection_can_make_short_context_useful():
    assert is_useful_historical_context("pintura") is True


def test_build_initial_context_uses_available_project_fields():
    context = build_initial_historical_context(
        {
            "tipo": "Reparación de bajante",
            "nombre_obra": "Patio interior",
            "descripcion": "Sustitución de PVC",
            "calle": "Calle Mayor",
            "num_calle": "12",
            "email_admin": "admin@example.com",
        }
    )

    assert "Reparación de bajante" in context
    assert "Patio interior" in context
    assert "Sustitución de PVC" in context
    assert "Calle Mayor" in context
    assert "admin@example.com" not in context


def test_request_historical_suggestions_does_not_call_service_for_invalid_context():
    service = FakeHistoricalSuggestionService()

    result = request_historical_suggestions_for_context(
        {"tipo": "reparación general"},
        "reparación general",
        service=service,
    )

    assert result is None
    assert service.calls == []


def test_valid_description_calls_service_with_confirmed_context_only():
    service = FakeHistoricalSuggestionService()
    context = "Reparación de bajante en patio interior con sustitución de PVC"

    result = request_historical_suggestions_for_context(
        {"tipo": "Nombre previo que no debe disparar búsqueda directa"},
        context,
        service=service,
    )

    assert result == {"source": "historical", "partidas": []}
    assert service.calls == [
        {
            "project_data": {},
            "user_description": context,
        }
    ]


def test_generic_context_detector_marks_initial_generic_text():
    assert is_generic_historical_context("rehabilitación de edificio") is True
    assert is_generic_historical_context("Reparación de bajante en patio interior") is False
