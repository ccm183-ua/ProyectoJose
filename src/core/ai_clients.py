"""Clientes comunes para proveedores de IA."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional

from src.core.settings import (
    AI_PROVIDER_DEEPSEEK,
    AI_PROVIDER_GEMINI,
    DEFAULT_DEEPSEEK_MODEL,
    DEFAULT_GEMINI_MODEL,
    Settings,
)


AUTH_ERROR_MESSAGE = "La API key no es válida o no tiene saldo/permisos suficientes."
GENERIC_ERROR_MESSAGE = "Error al contactar con la IA."
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def mask_secret(secret: str) -> str:
    value = str(secret or "")
    if not value:
        return ""
    if len(value) <= 3:
        return "***"
    if len(value) <= 8:
        return f"{value[0]}...{value[-1]}"
    return f"{value[:3]}...{value[-4:]}"


def redact_secrets(text: str) -> str:
    clean = str(text or "")
    clean = re.sub(r"\bsk-[A-Za-z0-9_\-]{8,}\b", "[api-key-oculta]", clean)
    clean = re.sub(r"\bAI[A-Za-z0-9_\-]{12,}\b", "[api-key-oculta]", clean)
    return clean


def extract_json_from_markdown(text: str) -> str:
    clean = (text or "").strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", clean, re.DOTALL)
    return match.group(1).strip() if match else clean


class AIProviderClient(ABC):
    provider_name = ""

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @property
    def model_label(self) -> str:
        return f"{self.provider_name}:{self.model_name}"

    @abstractmethod
    def generate_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> dict:
        ...

    def test_connection(self) -> tuple[bool, str]:
        try:
            data = self.generate_json(
                system_prompt="Devuelve exclusivamente JSON valido.",
                user_payload={"instruction": 'Responde exactamente {"ok": true}.'},
                temperature=0.0,
                max_tokens=32,
            )
        except Exception as exc:
            return False, normalize_ai_error(exc)
        return (True, "Conexión correcta") if data.get("ok") is True else (False, "La IA no devolvió la respuesta esperada.")


class GeminiAIClient(AIProviderClient):
    provider_name = "gemini"

    def __init__(self, api_key: Optional[str], model: Optional[str] = None):
        self._api_key = api_key.strip() if api_key and api_key.strip() else None
        self._configured_model = (model or DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
        self._last_model = self._configured_model
        self._client = None

    @property
    def model_name(self) -> str:
        return self._last_model or self._configured_model

    def is_available(self) -> bool:
        return self._api_key is not None

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> dict:
        prompt = (
            f"{system_prompt}\n\n"
            "Devuelve exclusivamente un objeto JSON valido, sin markdown.\n\n"
            f"{json.dumps(user_payload or {}, ensure_ascii=False, sort_keys=True)}"
        )
        text = self.generate_text(prompt, temperature=temperature, max_tokens=max_tokens)
        try:
            data = json.loads(extract_json_from_markdown(text))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("La IA no devolvió JSON válido.") from exc
        if not isinstance(data, dict):
            raise ValueError("La respuesta de IA debe ser un objeto JSON.")
        return data

    def generate_text(self, prompt: str, temperature: float = 0.2, max_tokens: int = 1200) -> str:
        if not self.is_available():
            raise ValueError("No hay API key configurada.")
        try:
            from google import genai
        except ImportError as exc:
            raise ImportError("La librería 'google-genai' no está instalada. Ejecute: pip install google-genai") from exc

        if self._client is None:
            self._client = genai.Client(api_key=self._api_key)

        response = self._client.models.generate_content(
            model=self._configured_model,
            contents=prompt,
        )
        self._last_model = self._configured_model
        return response.text if hasattr(response, "text") else str(response)


Transport = Callable[[str, Dict[str, str], Dict[str, Any], int], Dict[str, Any]]


class DeepSeekAIClient(AIProviderClient):
    provider_name = "deepseek"

    def __init__(
        self,
        api_key: Optional[str],
        model: Optional[str] = None,
        *,
        base_url: str = DEEPSEEK_BASE_URL,
        transport: Optional[Transport] = None,
        timeout: int = 30,
    ):
        self._api_key = api_key.strip() if api_key and api_key.strip() else None
        self._model = (model or DEFAULT_DEEPSEEK_MODEL).strip() or DEFAULT_DEEPSEEK_MODEL
        self._base_url = base_url.rstrip("/")
        self._transport = transport or self._default_transport
        self._timeout = int(timeout or 30)

    @property
    def model_name(self) -> str:
        return self._model

    def is_available(self) -> bool:
        return self._api_key is not None

    def build_payload(
        self,
        *,
        system_prompt: str,
        user_payload: dict,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> dict:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt or ""},
                {
                    "role": "user",
                    "content": json.dumps(user_payload or {}, ensure_ascii=False, sort_keys=True),
                },
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        if self._model == DEFAULT_DEEPSEEK_MODEL:
            payload["thinking"] = {"type": "disabled"}
        return payload

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict,
        temperature: float = 0.2,
        max_tokens: int = 1200,
    ) -> dict:
        if not self.is_available():
            raise ValueError("No hay API key configurada.")
        payload = self.build_payload(
            system_prompt=system_prompt,
            user_payload=user_payload,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            raw = self._transport(f"{self._base_url}/chat/completions", headers, payload, self._timeout)
        except TimeoutError:
            raise TimeoutError("Tiempo de espera agotado al contactar con la IA.")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(_http_error_message(exc.code)) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(GENERIC_ERROR_MESSAGE) from exc

        choices = raw.get("choices") if isinstance(raw, dict) else None
        if not choices:
            raise ValueError("Respuesta de IA incompleta.")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else ""
        try:
            data = json.loads(extract_json_from_markdown(content))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("La IA no devolvió JSON válido.") from exc
        if not isinstance(data, dict):
            raise ValueError("La respuesta de IA debe ser un objeto JSON.")
        return data

    @staticmethod
    def _default_transport(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Respuesta de IA incompleta.")
        return data


def get_ai_client_from_settings(settings: Optional[Settings] = None) -> AIProviderClient:
    settings = settings or Settings()
    provider = settings.get_ai_provider()
    if provider == AI_PROVIDER_DEEPSEEK:
        return DeepSeekAIClient(settings.get_deepseek_api_key(), settings.get_deepseek_model())
    return GeminiAIClient(settings.get_gemini_api_key(), settings.get_gemini_model())


def normalize_ai_error(exc: Exception) -> str:
    text = redact_secrets(str(exc or ""))
    if any(token in text for token in ("401", "403", "API_KEY_INVALID", "PERMISSION_DENIED")):
        return AUTH_ERROR_MESSAGE
    if "429" in text or "RESOURCE_EXHAUSTED" in text:
        return "Cuota temporal agotada en la API de IA. Espere un minuto e inténtelo de nuevo."
    if "timeout" in text.lower() or "tiempo de espera" in text.lower():
        return "Tiempo de espera agotado al contactar con la IA. Inténtelo de nuevo."
    if "JSON" in text:
        return "La IA no devolvió JSON válido."
    return f"{GENERIC_ERROR_MESSAGE} {text[:160]}".strip()


def _http_error_message(status_code: int) -> str:
    if status_code in (401, 403):
        return AUTH_ERROR_MESSAGE
    if status_code == 429:
        return "Cuota temporal agotada en la API de IA. Espere un minuto e inténtelo de nuevo."
    if status_code >= 500:
        return "El proveedor de IA no está disponible temporalmente."
    return GENERIC_ERROR_MESSAGE


def sleep_for_retry(seconds: int) -> None:
    time.sleep(seconds)
