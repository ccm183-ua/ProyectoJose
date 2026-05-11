"""Persistencia segura de la configuracion IA desde formularios."""

from __future__ import annotations

from src.core.settings import Settings


def api_key_status_text(provider_name: str, source: str) -> str:
    if source == "env":
        return f"Clave {provider_name}: configurada en variable de entorno"
    if source == "local":
        return f"Clave {provider_name}: guardada en configuración local"
    return f"Clave {provider_name}: sin clave configurada"


def save_ai_settings_from_dialog(
    settings: Settings,
    *,
    provider: str,
    gemini_key_input: str,
    deepseek_key_input: str,
    gemini_model: str,
    deepseek_model: str,
    clear_gemini: bool = False,
    clear_deepseek: bool = False,
) -> None:
    settings.save_ai_provider(provider)
    settings.save_gemini_model(gemini_model)
    settings.save_deepseek_model(deepseek_model)
    gemini_key = (gemini_key_input or "").strip()
    deepseek_key = (deepseek_key_input or "").strip()
    if clear_gemini:
        settings.save_gemini_api_key("")
    elif gemini_key:
        settings.save_gemini_api_key(gemini_key)
    if clear_deepseek:
        settings.save_deepseek_api_key("")
    elif deepseek_key:
        settings.save_deepseek_api_key(deepseek_key)
