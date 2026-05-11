from src.core.settings import AI_PROVIDER_DEEPSEEK, Settings
from src.core.ai_settings_persistence import api_key_status_text, save_ai_settings_from_dialog


def test_empty_dialog_key_fields_preserve_existing_local_keys(tmp_path, monkeypatch):
    monkeypatch.delenv("CUBIAPP_GEMINI_KEY", raising=False)
    monkeypatch.delenv("CUBIAPP_DEEPSEEK_KEY", raising=False)
    settings = Settings(config_dir=str(tmp_path))
    settings.save_gemini_api_key("AI-local-key-not-real")
    settings.save_deepseek_api_key("sk-local-key-not-real")

    save_ai_settings_from_dialog(
        settings,
        provider=AI_PROVIDER_DEEPSEEK,
        gemini_key_input="",
        deepseek_key_input="",
        gemini_model="gemini-test",
        deepseek_model="deepseek-test",
    )

    assert settings.get_local_gemini_api_key() == "AI-local-key-not-real"
    assert settings.get_local_deepseek_api_key() == "sk-local-key-not-real"
    assert settings.get_ai_provider() == AI_PROVIDER_DEEPSEEK


def test_dialog_does_not_copy_environment_keys_to_local_config(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_GEMINI_KEY", "AI-env-key-not-real")
    monkeypatch.setenv("CUBIAPP_DEEPSEEK_KEY", "sk-env-key-not-real")
    settings = Settings(config_dir=str(tmp_path))

    save_ai_settings_from_dialog(
        settings,
        provider=AI_PROVIDER_DEEPSEEK,
        gemini_key_input="",
        deepseek_key_input="",
        gemini_model="gemini-test",
        deepseek_model="deepseek-test",
    )

    assert settings.get_gemini_api_key() == "AI-env-key-not-real"
    assert settings.get_deepseek_api_key() == "sk-env-key-not-real"
    assert settings.get_local_gemini_api_key() is None
    assert settings.get_local_deepseek_api_key() is None


def test_dialog_saves_explicit_new_key_and_can_clear_local_key(tmp_path, monkeypatch):
    monkeypatch.delenv("CUBIAPP_GEMINI_KEY", raising=False)
    monkeypatch.delenv("CUBIAPP_DEEPSEEK_KEY", raising=False)
    settings = Settings(config_dir=str(tmp_path))
    settings.save_gemini_api_key("AI-old-local-key")

    save_ai_settings_from_dialog(
        settings,
        provider=AI_PROVIDER_DEEPSEEK,
        gemini_key_input="AI-new-local-key",
        deepseek_key_input="sk-new-local-key",
        gemini_model="gemini-test",
        deepseek_model="deepseek-test",
    )
    assert settings.get_local_gemini_api_key() == "AI-new-local-key"
    assert settings.get_local_deepseek_api_key() == "sk-new-local-key"

    save_ai_settings_from_dialog(
        settings,
        provider=AI_PROVIDER_DEEPSEEK,
        gemini_key_input="",
        deepseek_key_input="",
        gemini_model="gemini-test",
        deepseek_model="deepseek-test",
        clear_gemini=True,
    )
    assert settings.get_local_gemini_api_key() is None
    assert settings.get_local_deepseek_api_key() == "sk-new-local-key"


def test_api_key_status_text():
    assert api_key_status_text("Gemini", "env") == "Clave Gemini: configurada en variable de entorno"
    assert api_key_status_text("DeepSeek", "local") == "Clave DeepSeek: guardada en configuración local"
    assert api_key_status_text("Gemini", "missing") == "Clave Gemini: sin clave configurada"
