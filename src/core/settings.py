"""
Gestión de configuración de la aplicación.

Maneja la API key de Gemini, rutas por defecto y otros ajustes de configuración.
Prioridad API key: variable de entorno > archivo local.
"""

import json
import os
from typing import Dict, Optional


# Variable de entorno para la API key
ENV_VAR_NAME = "CUBIAPP_GEMINI_KEY"

# Nombre del archivo de configuración local
CONFIG_FILENAME = "cubiapp_config.json"


class Settings:
    """Gestiona la configuración de la aplicación."""

    # Claves para rutas por defecto
    PATH_SAVE_BUDGETS = "ruta_guardar_presupuestos"
    PATH_OPEN_BUDGETS = "ruta_abrir_presupuestos"
    PATH_RELATION_FILE = "ruta_relacion_presupuestos"

    _ALL_PATH_KEYS = (PATH_SAVE_BUDGETS, PATH_OPEN_BUDGETS, PATH_RELATION_FILE)

    def __init__(self, config_dir: Optional[str] = None):
        if config_dir is None:
            config_dir = os.path.join(
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
        env_key = os.environ.get(ENV_VAR_NAME)
        if env_key and env_key.strip():
            return env_key.strip()

        config = self._load_config()
        file_key = config.get("gemini_api_key")
        if file_key and file_key.strip():
            return file_key.strip()

        return None

    def save_api_key(self, api_key: str):
        config = self._load_config()
        config["gemini_api_key"] = api_key
        self._save_config(config)

    def has_api_key(self) -> bool:
        return self.get_api_key() is not None

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

    def _save_config(self, config: dict):
        os.makedirs(self._config_dir, exist_ok=True)
        with open(self._config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
