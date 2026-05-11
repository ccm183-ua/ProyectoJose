import json
import urllib.error

import pytest
from unittest.mock import patch

from src.core.ai_clients import (
    AUTH_ERROR_MESSAGE,
    DeepSeekAIClient,
    GeminiAIClient,
    get_ai_client_from_settings,
    mask_secret,
    normalize_ai_error,
    redact_secrets,
)
from src.core.settings import AI_PROVIDER_DEEPSEEK, AI_PROVIDER_GEMINI, Settings


def test_mask_secret_examples():
    assert mask_secret("") == ""
    assert mask_secret("abc") == "***"
    assert mask_secret("sk-1234567890abcdef") == "sk-...cdef"


def test_factory_returns_provider_from_settings(tmp_path, monkeypatch):
    monkeypatch.delenv("CUBIAPP_GEMINI_KEY", raising=False)
    monkeypatch.delenv("CUBIAPP_DEEPSEEK_KEY", raising=False)
    s = Settings(config_dir=str(tmp_path))
    s.save_ai_provider(AI_PROVIDER_GEMINI)
    assert isinstance(get_ai_client_from_settings(s), GeminiAIClient)

    s.save_ai_provider(AI_PROVIDER_DEEPSEEK)
    assert isinstance(get_ai_client_from_settings(s), DeepSeekAIClient)


def test_deepseek_builds_payload_without_exposing_key():
    captured = {}

    def fake_transport(url, headers, payload, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return {"choices": [{"message": {"content": '{"ok": true}'}}]}

    client = DeepSeekAIClient("sk-test-secret-123456", "deepseek-v4-flash", transport=fake_transport)
    result = client.generate_json(system_prompt="system", user_payload={"x": 1})

    assert result == {"ok": True}
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer sk-test-secret-123456"
    payload_dump = json.dumps(captured["payload"], ensure_ascii=False)
    assert "sk-test-secret-123456" not in payload_dump
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["thinking"] == {"type": "disabled"}


def test_gemini_client_normalizes_json_response():
    client = GeminiAIClient("AI-test-key-not-real", "gemini-test")
    with patch.object(client, "generate_text", return_value='```json\n{"ok": true}\n```'):
        assert client.generate_json(system_prompt="system", user_payload={"x": 1}) == {"ok": True}


@pytest.mark.parametrize(
    "status",
    [401, 403],
)
def test_deepseek_auth_errors_are_normalized(status):
    def fake_transport(url, headers, payload, timeout):
        raise urllib.error.HTTPError(url, status, "auth", {}, None)

    client = DeepSeekAIClient("sk-test-secret-abcdef", transport=fake_transport)
    with pytest.raises(RuntimeError) as exc:
        client.generate_json(system_prompt="system", user_payload={})
    assert AUTH_ERROR_MESSAGE in str(exc.value)
    assert "sk-test-secret-abcdef" not in str(exc.value)


def test_deepseek_invalid_json_is_normalized_without_key():
    def fake_transport(url, headers, payload, timeout):
        return {"choices": [{"message": {"content": "not-json sk-test-secret-abcdef"}}]}

    client = DeepSeekAIClient("sk-test-secret-abcdef", transport=fake_transport)
    with pytest.raises(ValueError) as exc:
        client.generate_json(system_prompt="system", user_payload={})
    message = normalize_ai_error(exc.value)
    assert message == "La IA no devolvió JSON válido."
    assert "sk-test-secret-abcdef" not in message


def test_deepseek_transport_error_redacts_key():
    key = "sk-test-secret-abcdef"

    def fake_transport(url, headers, payload, timeout):
        raise RuntimeError(f"fallo con {key}")

    client = DeepSeekAIClient(key, transport=fake_transport)
    with pytest.raises(RuntimeError) as exc:
        client.generate_json(system_prompt="system", user_payload={})
    assert key not in str(exc.value)


def test_redact_secrets_removes_known_key_shapes():
    text = redact_secrets("fallo sk-1234567890abcdef y AIabcdefghijklmnopqrstuvwxyz")
    assert "sk-1234567890abcdef" not in text
    assert "AIabcdefghijklmnopqrstuvwxyz" not in text


def test_normalized_errors_do_not_expose_full_key():
    key = "sk-1234567890abcdef"
    message = normalize_ai_error(RuntimeError(f"fallo para {key}"))
    assert key not in message
