"""
Tests para Settings.

Cubren:
- Carga de API key desde variable de entorno
- Carga de API key desde archivo local
- Manejo de API key ausente
- Guardado y recuperación de API key
- Rutas por defecto (get/set/clear/persistencia)
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
        settings = Settings(config_dir=temp_dir)
        assert settings.get_api_key() is None

    def test_env_var_takes_precedence(self, monkeypatch, temp_dir):
        """La variable de entorno tiene prioridad sobre el archivo local."""
        monkeypatch.setenv("CUBIAPP_GEMINI_KEY", "env-key")
        settings = Settings(config_dir=temp_dir)
        settings.save_api_key("file-key")
        assert settings.get_api_key() == "env-key"


class TestSaveApiKey:
    """Tests para guardado y recuperación de API key."""

    def test_save_and_load_api_key(self, monkeypatch, temp_dir):
        """Guardar y recuperar API key de archivo local."""
        monkeypatch.delenv("CUBIAPP_GEMINI_KEY", raising=False)
        settings = Settings(config_dir=temp_dir)
        settings.save_api_key("my-saved-key-67890")
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


# ── Tests de rutas por defecto ────────────────────────────────────


class TestDefaultPaths:
    """Tests para get/set de rutas por defecto."""

    def test_set_and_get_default_path_save(self, temp_dir):
        """Guardar y recuperar ruta de guardado de presupuestos."""
        s = Settings(config_dir=temp_dir)
        s.set_default_path(Settings.PATH_SAVE_BUDGETS, "C:/presupuestos/nuevos")
        assert s.get_default_path(Settings.PATH_SAVE_BUDGETS) == "C:/presupuestos/nuevos"

    def test_set_and_get_default_path_open(self, temp_dir):
        """Guardar y recuperar ruta de apertura de presupuestos."""
        s = Settings(config_dir=temp_dir)
        s.set_default_path(Settings.PATH_OPEN_BUDGETS, "D:/archivos")
        assert s.get_default_path(Settings.PATH_OPEN_BUDGETS) == "D:/archivos"

    def test_set_and_get_default_path_relation(self, temp_dir):
        """Guardar y recuperar ruta del fichero de relación."""
        s = Settings(config_dir=temp_dir)
        s.set_default_path(Settings.PATH_RELATION_FILE, "E:/relacion.xlsx")
        assert s.get_default_path(Settings.PATH_RELATION_FILE) == "E:/relacion.xlsx"

    def test_get_default_path_nonexistent_key(self, temp_dir):
        """Clave no reconocida devuelve None."""
        s = Settings(config_dir=temp_dir)
        assert s.get_default_path("clave_inventada") is None

    def test_get_default_path_empty_string(self, temp_dir):
        """Ruta vacía devuelve None."""
        s = Settings(config_dir=temp_dir)
        s.set_default_path(Settings.PATH_SAVE_BUDGETS, "")
        assert s.get_default_path(Settings.PATH_SAVE_BUDGETS) is None

    def test_get_default_path_whitespace_only(self, temp_dir):
        """Ruta solo con espacios devuelve None."""
        s = Settings(config_dir=temp_dir)
        s.set_default_path(Settings.PATH_SAVE_BUDGETS, "   ")
        assert s.get_default_path(Settings.PATH_SAVE_BUDGETS) is None

    def test_get_all_default_paths(self, temp_dir):
        """Obtener las 3 rutas de una vez."""
        s = Settings(config_dir=temp_dir)
        s.set_default_path(Settings.PATH_SAVE_BUDGETS, "/a")
        s.set_default_path(Settings.PATH_OPEN_BUDGETS, "/b")
        paths = s.get_all_default_paths()
        assert paths[Settings.PATH_SAVE_BUDGETS] == "/a"
        assert paths[Settings.PATH_OPEN_BUDGETS] == "/b"
        assert paths[Settings.PATH_RELATION_FILE] is None

    def test_clear_default_path(self, temp_dir):
        """Limpiar una ruta estableciéndola vacía."""
        s = Settings(config_dir=temp_dir)
        s.set_default_path(Settings.PATH_SAVE_BUDGETS, "/ruta")
        assert s.get_default_path(Settings.PATH_SAVE_BUDGETS) == "/ruta"
        s.set_default_path(Settings.PATH_SAVE_BUDGETS, "")
        assert s.get_default_path(Settings.PATH_SAVE_BUDGETS) is None

    def test_paths_persist_across_instances(self, temp_dir):
        """Las rutas persisten entre instancias distintas."""
        s1 = Settings(config_dir=temp_dir)
        s1.set_default_path(Settings.PATH_RELATION_FILE, "/mi/relacion.xlsx")
        s2 = Settings(config_dir=temp_dir)
        assert s2.get_default_path(Settings.PATH_RELATION_FILE) == "/mi/relacion.xlsx"

    def test_set_ignores_unknown_key(self, temp_dir):
        """set_default_path con clave desconocida no escribe nada."""
        s = Settings(config_dir=temp_dir)
        s.set_default_path("desconocida", "/valor")
        assert s.get_default_path("desconocida") is None

    def test_paths_do_not_affect_api_key(self, monkeypatch, temp_dir):
        """Escribir rutas no altera la API key almacenada."""
        monkeypatch.delenv("CUBIAPP_GEMINI_KEY", raising=False)
        s = Settings(config_dir=temp_dir)
        s.save_api_key("mi-clave")
        s.set_default_path(Settings.PATH_SAVE_BUDGETS, "/ruta")
        assert s.get_api_key() == "mi-clave"
