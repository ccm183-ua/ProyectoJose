"""
Gestión de configuración de la aplicación.

Maneja la API key de Gemini y otros ajustes de configuración.
Prioridad: variable de entorno > archivo local.
"""

import json
import os
from typing import Optional


# Variable de entorno para la API key
ENV_VAR_NAME = "CUBIAPP_GEMINI_KEY"

# Nombre del archivo de configuración local
CONFIG_FILENAME = "cubiapp_config.json"


class Settings:
    """Gestiona la configuración de la aplicación."""

    def __init__(self, config_dir: Optional[str] = None):
        """
        Inicializa la configuración.

        Args:
            config_dir: Directorio donde guardar/leer el archivo de configuración.
                        Si no se proporciona, usa el directorio de la aplicación.
        """
        if config_dir is None:
            # Usar directorio del usuario por defecto
            config_dir = os.path.join(
                os.path.expanduser("~"), ".cubiapp"
            )
        self._config_dir = config_dir
        self._config_path = os.path.join(config_dir, CONFIG_FILENAME)

    def get_api_key(self) -> Optional[str]:
        """
        Obtiene la API key de Gemini.

        Prioridad:
        1. Variable de entorno CUBIAPP_GEMINI_KEY
        2. Archivo de configuración local

        Returns:
            La API key o None si no está configurada.
        """
        # 1. Variable de entorno (prioridad máxima)
        env_key = os.environ.get(ENV_VAR_NAME)
        if env_key and env_key.strip():
            return env_key.strip()

        # 2. Archivo local
        config = self._load_config()
        file_key = config.get("gemini_api_key")
        if file_key and file_key.strip():
            return file_key.strip()

        return None

    def save_api_key(self, api_key: str):
        """
        Guarda la API key en el archivo de configuración local.

        Args:
            api_key: La API key a guardar.
        """
        config = self._load_config()
        config["gemini_api_key"] = api_key
        self._save_config(config)

    def has_api_key(self) -> bool:
        """
        Comprueba si hay una API key configurada.

        Returns:
            True si hay una API key disponible.
        """
        return self.get_api_key() is not None

    def _load_config(self) -> dict:
        """Carga la configuración desde el archivo local."""
        if not os.path.exists(self._config_path):
            return {}
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_config(self, config: dict):
        """Guarda la configuración en el archivo local."""
        os.makedirs(self._config_dir, exist_ok=True)
        with open(self._config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
