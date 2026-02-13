"""
Almacenamiento de plantillas personalizadas del usuario.

Las plantillas personalizadas se guardan en un archivo JSON local
(~/.cubiapp/custom_templates.json) separado del catálogo predefinido.
Esto permite al usuario construir su propia biblioteca de plantillas
sin modificar el catálogo base de la aplicación.
"""

import json
import os
from typing import Dict, List, Optional


# Archivo de plantillas personalizadas
CUSTOM_TEMPLATES_FILENAME = "custom_templates.json"


class CustomTemplateStore:
    """Gestiona la persistencia de plantillas personalizadas del usuario."""

    def __init__(self, config_dir: Optional[str] = None):
        """
        Inicializa el almacén de plantillas personalizadas.

        Args:
            config_dir: Directorio donde guardar el archivo.
                        Si no se proporciona, usa ~/.cubiapp/
        """
        if config_dir is None:
            config_dir = os.path.join(
                os.path.expanduser("~"), ".cubiapp"
            )
        self._config_dir = config_dir
        self._file_path = os.path.join(config_dir, CUSTOM_TEMPLATES_FILENAME)

    def load_all(self) -> List[Dict]:
        """
        Carga todas las plantillas personalizadas.

        Returns:
            Lista de plantillas (mismo formato que work_types.json).
        """
        if not os.path.exists(self._file_path):
            return []
        try:
            with open(self._file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('plantillas', [])
        except (json.JSONDecodeError, IOError):
            return []

    def save_all(self, plantillas: List[Dict]):
        """
        Guarda la lista completa de plantillas personalizadas.

        Args:
            plantillas: Lista de plantillas a guardar.
        """
        os.makedirs(self._config_dir, exist_ok=True)
        with open(self._file_path, 'w', encoding='utf-8') as f:
            json.dump({'plantillas': plantillas}, f, indent=2, ensure_ascii=False)

    def add(self, plantilla: Dict) -> bool:
        """
        Añade una nueva plantilla personalizada.

        Si ya existe una con el mismo nombre, la reemplaza.

        Args:
            plantilla: Diccionario con la plantilla (nombre, categoria,
                       descripcion, contexto_ia, partidas_base).

        Returns:
            True si se añadió correctamente.
        """
        if not plantilla.get('nombre'):
            return False

        plantillas = self.load_all()

        # Reemplazar si ya existe con el mismo nombre
        plantillas = [p for p in plantillas if p['nombre'] != plantilla['nombre']]
        plantilla['personalizada'] = True  # Marcar como personalizada
        plantillas.append(plantilla)

        self.save_all(plantillas)
        return True

    def remove(self, nombre: str) -> bool:
        """
        Elimina una plantilla personalizada por nombre.

        Args:
            nombre: Nombre de la plantilla a eliminar.

        Returns:
            True si se eliminó, False si no existía.
        """
        plantillas = self.load_all()
        original_count = len(plantillas)
        plantillas = [p for p in plantillas if p['nombre'] != nombre]

        if len(plantillas) == original_count:
            return False

        self.save_all(plantillas)
        return True

    def get_by_name(self, nombre: str) -> Optional[Dict]:
        """
        Busca una plantilla personalizada por nombre.

        Args:
            nombre: Nombre de la plantilla.

        Returns:
            La plantilla o None si no existe.
        """
        for p in self.load_all():
            if p['nombre'] == nombre:
                return p
        return None

    def count(self) -> int:
        """Devuelve el número de plantillas personalizadas."""
        return len(self.load_all())
