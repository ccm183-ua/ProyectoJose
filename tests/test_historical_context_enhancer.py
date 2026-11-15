import pytest

import src.core.historical_context_enhancer as enhancer_module
from src.core.historical_context_enhancer import (
    HISTORICAL_SEARCH_CONTEXT_ENHANCER_SYSTEM_PROMPT,
    HistoricalSearchContextEnhancer,
)


class FakeAIClient:
    provider_name = "deepseek"
    model_name = "deepseek-v4-flash"

    def __init__(self):
        self.calls = []

    def generate_json(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "enhanced_description": (
                "Reparacion de bajante comunitaria con revision de tramos deteriorados "
                "y pintura de paramentos del patio interior afectados."
            ),
            "detected_work_types": ["bajante", "pintura"],
            "technical_terms": ["paramentos", "estanqueidad"],
            "confidence": 0.8,
            "warnings": [],
        }


def test_enhancer_uses_injected_ai_client_and_parses_response():
    client = FakeAIClient()
    result = HistoricalSearchContextEnhancer(ai_client=client).enhance(
        "reparar bajante y pintar patio",
        project_data={"localidad": "Alicante"},
    )

    assert client.calls
    assert result["original_description"] == "reparar bajante y pintar patio"
    assert "bajante comunitaria" in result["enhanced_description"]
    assert result["detected_work_types"] == ["bajante", "pintura"]
    assert result["technical_terms"] == ["paramentos", "estanqueidad"]
    assert result["provider"] == "deepseek"
    assert result["model"] == "deepseek-v4-flash"


def test_enhancer_uses_factory_when_no_client(monkeypatch):
    client = FakeAIClient()
    monkeypatch.setattr(enhancer_module, "get_ai_client_from_settings", lambda: client)

    result = HistoricalSearchContextEnhancer().enhance("arreglar fachada")

    assert client.calls
    assert result["enhanced_description"]


def test_prompt_states_it_does_not_create_partidas_or_budgets():
    prompt = HISTORICAL_SEARCH_CONTEXT_ENHANCER_SYSTEM_PROMPT.lower()
    assert "no es crear partidas ni presupuestos" in prompt
    assert "devuelve json estricto" in prompt


def test_invalid_ai_json_or_empty_description_returns_clear_error():
    class BadAIClient:
        provider_name = "gemini"
        model_name = "gemini-test"

        def generate_json(self, **kwargs):
            return {"enhanced_description": ""}

    with pytest.raises(RuntimeError) as exc:
        HistoricalSearchContextEnhancer(ai_client=BadAIClient()).enhance("arreglar fachada")

    assert "descripcion mejorada" in str(exc.value).lower()


def test_enhancer_errors_do_not_expose_api_keys():
    key = "sk-1234567890abcdef"

    class FailingAIClient:
        provider_name = "deepseek"
        model_name = "deepseek-v4-flash"

        def generate_json(self, **kwargs):
            raise RuntimeError(f"fallo con {key}")

    with pytest.raises(RuntimeError) as exc:
        HistoricalSearchContextEnhancer(ai_client=FailingAIClient()).enhance("arreglar fachada")

    assert key not in str(exc.value)
