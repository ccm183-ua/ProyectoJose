from unittest.mock import MagicMock

import pytest

from src.core.description_assistant import polish_budget_context_description
from src.core.settings import Settings


def test_polish_returns_error_when_no_api_key(monkeypatch):
    settings = MagicMock(spec=Settings)

    client = MagicMock()
    client.is_available.return_value = False

    monkeypatch.setattr(
        "src.core.description_assistant.get_ai_client_from_settings",
        lambda s: client,
    )

    text, err = polish_budget_context_description(
        settings,
        tipo_obra="Reforma",
        borrador="cambiar ventana",
        datos_proyecto=None,
    )
    assert text == ""
    assert err is not None
    assert "API" in err or "key" in err.lower()
