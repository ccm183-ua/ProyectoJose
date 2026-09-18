import functools

import pytest

from src.core.settings import AI_PROVIDER_DEEPSEEK, Settings
from src.core.ai_settings_persistence import api_key_status_text, save_ai_settings_from_dialog

try:
    from src.core.ai_clients import DeepSeekAIClient as RealDeepSeekAIClient
    from src.gui import ai_settings_dialog
    from src.gui.ai_settings_dialog import AISettingsDialog

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False


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


# ── H17 (S1-E): prueba de proveedor sin leer widgets desde el worker ────────


@pytest.fixture(autouse=True)
def _no_modal_dialogs(monkeypatch):
    """Los QMessageBox modales cuelgan la suite bajo la plataforma offscreen."""
    if not _HAS_PYSIDE6:
        return
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))


def _make_dialog(tmp_path):
    return AISettingsDialog(settings=Settings(config_dir=str(tmp_path)))


@pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")
def test_testing_one_provider_leaves_the_other_button_untouched(tmp_path, qapp, monkeypatch):
    monkeypatch.setattr(ai_settings_dialog, "run_in_background", lambda work, callback: None)
    dlg = _make_dialog(tmp_path)

    dlg._test_provider(AI_PROVIDER_DEEPSEEK)

    assert not dlg._btn_test_deepseek.isEnabled()
    assert dlg._btn_test_deepseek.text() == "Probando…"
    assert dlg._btn_test_gemini.isEnabled()
    assert dlg._btn_test_gemini.text() == "Probar Gemini"


@pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")
def test_provider_timeout_restores_button_and_reports_timeout(tmp_path, qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    def _raise_timeout(url, headers, payload, timeout):
        raise TimeoutError("transporte agotado")

    monkeypatch.setattr(
        ai_settings_dialog,
        "DeepSeekAIClient",
        functools.partial(RealDeepSeekAIClient, transport=_raise_timeout),
    )
    monkeypatch.setattr(
        ai_settings_dialog, "run_in_background", lambda work, callback: callback(True, work())
    )
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    dlg = _make_dialog(tmp_path)
    dlg._deepseek_key.setText("sk-test-not-real")

    dlg._test_provider(AI_PROVIDER_DEEPSEEK)

    assert shown
    assert "Tiempo de espera agotado" in str(shown[0])
    assert dlg._btn_test_deepseek.isEnabled()
    assert dlg._btn_test_deepseek.text() == "Probar DeepSeek"


@pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")
def test_unexpected_exception_before_the_call_restores_the_button(tmp_path, qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    class _BoomClient:
        def __init__(self, *args, **kwargs):
            pass

        def test_connection(self):
            raise RuntimeError("boom antes de la llamada")

    def _sync_background(work, callback):
        try:
            callback(True, work())
        except Exception as exc:
            callback(False, exc)

    monkeypatch.setattr(ai_settings_dialog, "DeepSeekAIClient", _BoomClient)
    monkeypatch.setattr(ai_settings_dialog, "run_in_background", _sync_background)
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    dlg = _make_dialog(tmp_path)

    dlg._test_provider(AI_PROVIDER_DEEPSEEK)

    assert shown
    assert "boom antes de la llamada" in str(shown[0])
    assert dlg._btn_test_deepseek.isEnabled()
    assert dlg._btn_test_deepseek.text() == "Probar DeepSeek"


@pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")
def test_result_arriving_after_dialog_closed_touches_no_widget(tmp_path, qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: shown.append(a)))
    dlg = _make_dialog(tmp_path)
    dlg.done(0)

    dlg._on_test_done(AI_PROVIDER_DEEPSEEK, "DeepSeek", True, (False, "resultado tardío"))

    assert shown == []
    assert dlg._btn_test_deepseek.text() == "Probar DeepSeek"
