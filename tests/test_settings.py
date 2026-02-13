"""
Tests para Settings (FASE 3 - RED).

Cubren:
- Carga de API key desde variable de entorno
- Carga de API key desde archivo local
- Manejo de API key ausente
- Guardado y recuperación de API key
"""

import os
import tempfile
import pytest

from src.core.settings import Settings


@pytest.fixture
def temp_dir():
    """Directorio temporal para pruebas."""
    path = tempfile.mkdtemp()
    yield path
    # Limpiar
    import shutil
    shutil.rmtree(path, ignore_errors=True)


class TestLoadApiKey:
    """Tests para la carga de API key."""

    def test_load_api_key_from_env(self, monkeypatch):
        """Lee API key desde la variable de entorno CUBIAPP_GEMINI_KEY."""
        monkeypatch.setenv("CUBIAPP_GEMINI_KEY", "test-api-key-12345")
        settings = Settings()
        assert settings.get_api_key() == "test-api-key-12345"

    def test_load_api_key_missing(self, monkeypatch, temp_dir):
        """Sin API key configurada devuelve None."""
        monkeypatch.delenv("CUBIAPP_GEMINI_KEY", raising=False)
        # Usar un directorio sin archivo de settings
        settings = Settings(config_dir=temp_dir)
        assert settings.get_api_key() is None

    def test_env_var_takes_precedence(self, monkeypatch, temp_dir):
        """La variable de entorno tiene prioridad sobre el archivo local."""
        monkeypatch.setenv("CUBIAPP_GEMINI_KEY", "env-key")
        settings = Settings(config_dir=temp_dir)
        # Guardar una key diferente en archivo
        settings.save_api_key("file-key")
        # La de entorno debe ganar
        assert settings.get_api_key() == "env-key"


class TestSaveApiKey:
    """Tests para guardado y recuperación de API key."""

    def test_save_and_load_api_key(self, monkeypatch, temp_dir):
        """Guardar y recuperar API key de archivo local."""
        monkeypatch.delenv("CUBIAPP_GEMINI_KEY", raising=False)
        settings = Settings(config_dir=temp_dir)
        settings.save_api_key("my-saved-key-67890")
        # Crear nueva instancia para verificar persistencia
        settings2 = Settings(config_dir=temp_dir)
        assert settings2.get_api_key() == "my-saved-key-67890"

    def test_save_empty_key(self, monkeypatch, temp_dir):
        """Guardar una key vacía equivale a no tener key."""
        monkeypatch.delenv("CUBIAPP_GEMINI_KEY", raising=False)
        settings = Settings(config_dir=temp_dir)
        settings.save_api_key("")
        assert settings.get_api_key() is None

    def test_has_api_key_true(self, monkeypatch):
        """has_api_key devuelve True cuando hay key configurada."""
        monkeypatch.setenv("CUBIAPP_GEMINI_KEY", "some-key")
        settings = Settings()
        assert settings.has_api_key() is True

    def test_has_api_key_false(self, monkeypatch, temp_dir):
        """has_api_key devuelve False cuando no hay key."""
        monkeypatch.delenv("CUBIAPP_GEMINI_KEY", raising=False)
        settings = Settings(config_dir=temp_dir)
        assert settings.has_api_key() is False
