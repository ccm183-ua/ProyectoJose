"""
Catálogo de tipos de obra con plantillas predefinidas y personalizadas.

Carga y gestiona el catálogo JSON de tipos de obra que sirve como:
- Contexto enriquecido para la IA (partidas de referencia por tipo)
- Fallback offline cuando no hay conexión a internet

Combina plantillas predefinidas (work_types.json) con las personalizadas
del usuario (custom_templates.json en ~/.cubiapp/).
"""

import json
import os
from typing import Dict, List, Optional

from src.core.custom_templates import CustomTemplateStore


class WorkTypeCatalog:
    """Gestiona el catálogo de tipos de obra y sus plantillas."""

    def __init__(self, catalog_path: Optional[str] = None,
                 custom_store: Optional[CustomTemplateStore] = None):
        """
        Inicializa el catálogo cargando las plantillas predefinidas y personalizadas.

        Args:
            catalog_path: Ruta al archivo JSON del catálogo predefinido.
                          Si no se proporciona, usa la ruta por defecto.
            custom_store: Almacén de plantillas personalizadas.
                          Si no se proporciona, crea uno con la ruta por defecto.
        """
        if catalog_path is None:
            catalog_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data',
                'work_types.json'
            )
        self._catalog_path = catalog_path
        self._custom_store = custom_store or CustomTemplateStore()
        self._predefined: List[Dict] = []
        self._load()

    def _load(self):
        """Carga las plantillas predefinidas desde el JSON."""
        with open(self._catalog_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self._predefined = data.get('plantillas', [])

    def _combined(self) -> List[Dict]:
        """Devuelve la lista combinada: predefinidas + personalizadas."""
        custom = self._custom_store.load_all()
        return self._predefined + custom

    def get_all(self) -> List[Dict]:
        """
        Devuelve todas las plantillas (predefinidas + personalizadas).

        Returns:
            Lista de diccionarios con las plantillas.
        """
        return self._combined()

    def get_all_names(self) -> List[str]:
        """
        Devuelve los nombres de todas las plantillas disponibles.

        Returns:
            Lista de strings con los nombres.
        """
        return [p['nombre'] for p in self._combined()]

    def get_predefined_names(self) -> List[str]:
        """Devuelve solo los nombres de las plantillas predefinidas."""
        return [p['nombre'] for p in self._predefined]

    def get_custom_names(self) -> List[str]:
        """Devuelve solo los nombres de las plantillas personalizadas."""
        return [p['nombre'] for p in self._custom_store.load_all()]

    def get_by_name(self, nombre: str) -> Optional[Dict]:
        """
        Busca una plantilla por nombre exacto (predefinida o personalizada).

        Args:
            nombre: Nombre de la plantilla a buscar.

        Returns:
            Diccionario con la plantilla o None si no se encuentra.
        """
        for plantilla in self._combined():
            if plantilla['nombre'] == nombre:
                return plantilla
        return None

    def add_custom(self, plantilla: Dict) -> bool:
        """
        Añade una plantilla personalizada al catálogo.

        Args:
            plantilla: Diccionario con la plantilla.

        Returns:
            True si se añadió correctamente.
        """
        return self._custom_store.add(plantilla)

    def update_custom(self, nombre: str, changes: dict) -> bool:
        """
        Actualiza una plantilla personalizada. No permite modificar predefinidas.

        Args:
            nombre: Nombre de la plantilla a actualizar.
            changes: Diccionario con los campos a actualizar.

        Returns:
            True si se actualizó, False si no existe o es predefinida.
        """
        if any(p['nombre'] == nombre for p in self._predefined):
            return False
        return self._custom_store.update(nombre, changes)

    def remove_custom(self, nombre: str) -> bool:
        """
        Elimina una plantilla personalizada.

        Args:
            nombre: Nombre de la plantilla a eliminar.

        Returns:
            True si se eliminó, False si no existía o es predefinida.
        """
        # No permitir eliminar predefinidas
        if any(p['nombre'] == nombre for p in self._predefined):
            return False
        return self._custom_store.remove(nombre)
