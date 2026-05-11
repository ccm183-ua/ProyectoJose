"""
Gestión de configuración de la aplicación.

Maneja la API key de Gemini, rutas por defecto y otros ajustes de configuración.
Prioridad API key: variable de entorno > archivo local.
"""

import json
import os
import tempfile
from typing import Dict, Optional


# Variables de entorno para API keys. Se mantienen fuera de Git.
ENV_VAR_NAME = "CUBIAPP_GEMINI_KEY"
DEEPSEEK_ENV_VAR_NAME = "CUBIAPP_DEEPSEEK_KEY"

AI_PROVIDER_GEMINI = "GEMINI"
AI_PROVIDER_DEEPSEEK = "DEEPSEEK"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"

# Nombre del archivo de configuración local
CONFIG_FILENAME = "cubiapp_config.json"


class Settings:
    """Gestiona la configuración de la aplicación."""

    # Claves para rutas por defecto
    PATH_SAVE_BUDGETS = "ruta_guardar_presupuestos"
    PATH_OPEN_BUDGETS = "ruta_abrir_presupuestos"
    PATH_RELATION_FILE = "ruta_relacion_presupuestos"
    PATH_DATABASE = "ruta_base_datos"

    _ALL_PATH_KEYS = (PATH_SAVE_BUDGETS, PATH_OPEN_BUDGETS, PATH_RELATION_FILE, PATH_DATABASE)

    def get_database_path(self) -> Optional[str]:
        return self.get_default_path(self.PATH_DATABASE)

    def set_database_path(self, path: str) -> None:
        self.set_default_path(self.PATH_DATABASE, path)

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            config_dir = os.environ.get("CUBIAPP_CONFIG_DIR") or os.path.join(
                os.path.expanduser("~"), ".cubiapp"
            )
        self._config_dir = config_dir
        self._config_path = os.path.join(config_dir, CONFIG_FILENAME)

    # ── API key ──────────────────────────────────────────────────────

    def get_api_key(self) -> Optional[str]:
        """
        Obtiene la API key de Gemini.

        Prioridad:
        1. Variable de entorno CUBIAPP_GEMINI_KEY
        2. Archivo de configuración local
        """
        return self.get_gemini_api_key()

    def save_api_key(self, api_key: str):
        self.save_gemini_api_key(api_key)

    def has_api_key(self) -> bool:
        return self.get_api_key() is not None

    # ── Configuración IA ─────────────────────────────────────────────────────

    def get_ai_provider(self) -> str:
        config = self._load_config()
        provider = str(config.get("ai_provider") or AI_PROVIDER_GEMINI).strip().upper()
        if provider not in (AI_PROVIDER_GEMINI, AI_PROVIDER_DEEPSEEK):
            return AI_PROVIDER_GEMINI
        return provider

    def save_ai_provider(self, provider: str) -> None:
        provider_clean = str(provider or "").strip().upper()
        if provider_clean not in (AI_PROVIDER_GEMINI, AI_PROVIDER_DEEPSEEK):
            provider_clean = AI_PROVIDER_GEMINI
        config = self._load_config()
        config["ai_provider"] = provider_clean
        self._save_config(config)

    def get_gemini_api_key(self) -> Optional[str]:
        env_key = os.environ.get(ENV_VAR_NAME)
        if env_key and env_key.strip():
            return env_key.strip()
        return self._get_config_secret("gemini_api_key")

    def save_gemini_api_key(self, api_key: str) -> None:
        self._save_config_value("gemini_api_key", api_key.strip() if api_key else "")

    def get_local_gemini_api_key(self) -> Optional[str]:
        return self._get_config_secret("gemini_api_key")

    def get_gemini_api_key_source(self) -> str:
        env_key = os.environ.get(ENV_VAR_NAME)
        if env_key and env_key.strip():
            return "env"
        if self.get_local_gemini_api_key():
            return "local"
        return "missing"

    def get_deepseek_api_key(self) -> Optional[str]:
        env_key = os.environ.get(DEEPSEEK_ENV_VAR_NAME)
        if env_key and env_key.strip():
            return env_key.strip()
        return self._get_config_secret("deepseek_api_key")

    def save_deepseek_api_key(self, api_key: str) -> None:
        self._save_config_value("deepseek_api_key", api_key.strip() if api_key else "")

    def get_local_deepseek_api_key(self) -> Optional[str]:
        return self._get_config_secret("deepseek_api_key")

    def get_deepseek_api_key_source(self) -> str:
        env_key = os.environ.get(DEEPSEEK_ENV_VAR_NAME)
        if env_key and env_key.strip():
            return "env"
        if self.get_local_deepseek_api_key():
            return "local"
        return "missing"

    def get_gemini_model(self) -> str:
        return self._get_config_text("gemini_model", DEFAULT_GEMINI_MODEL)

    def save_gemini_model(self, model: str) -> None:
        self._save_config_value("gemini_model", (model or "").strip() or DEFAULT_GEMINI_MODEL)

    def get_deepseek_model(self) -> str:
        return self._get_config_text("deepseek_model", DEFAULT_DEEPSEEK_MODEL)

    def save_deepseek_model(self, model: str) -> None:
        self._save_config_value("deepseek_model", (model or "").strip() or DEFAULT_DEEPSEEK_MODEL)

    def has_active_ai_key(self) -> bool:
        if self.get_ai_provider() == AI_PROVIDER_DEEPSEEK:
            return self.get_deepseek_api_key() is not None
        return self.get_gemini_api_key() is not None

    # ── Rutas por defecto ────────────────────────────────────────────

    def get_default_path(self, key: str) -> Optional[str]:
        """Devuelve la ruta almacenada para *key*, o ``None`` si no existe o está vacía."""
        if key not in self._ALL_PATH_KEYS:
            return None
        config = self._load_config()
        value = config.get(key)
        if value and isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def set_default_path(self, key: str, path: str) -> None:
        """Guarda (o borra si *path* es vacío) la ruta para *key*."""
        if key not in self._ALL_PATH_KEYS:
            return
        config = self._load_config()
        config[key] = path.strip() if path else ""
        self._save_config(config)

    def get_all_default_paths(self) -> Dict[str, Optional[str]]:
        """Devuelve un diccionario con las tres rutas configuradas."""
        return {k: self.get_default_path(k) for k in self._ALL_PATH_KEYS}

    # ── Persistencia ─────────────────────────────────────────────────

    def _load_config(self) -> dict:
        if not os.path.exists(self._config_path):
            return {}
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _get_config_secret(self, key: str) -> Optional[str]:
        config = self._load_config()
        value = config.get(key)
        if value and isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _get_config_text(self, key: str, default: str) -> str:
        config = self._load_config()
        value = config.get(key)
        if value and isinstance(value, str) and value.strip():
            return value.strip()
        return default

    def _save_config_value(self, key: str, value: str) -> None:
        config = self._load_config()
        config[key] = value
        self._save_config(config)

    def _save_config(self, config: dict):
        os.makedirs(self._config_dir, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=self._config_dir, suffix='.tmp', prefix='cfg_'
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self._config_path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
