"""
Generador de presupuestos con IA.

Orquesta el flujo completo de generación de partidas:
1. Construye el prompt (con o sin plantilla)
2. Llama a la IA si está disponible
3. Si falla, usa fallback offline (partidas_base de la plantilla)
4. Devuelve resultado con indicador de fuente
"""

from typing import Dict, List, Optional

from src.core.ai_service import AIService
from src.core.prompt_builder import PromptBuilder


class BudgetGenerator:
    """Orquesta la generación de partidas presupuestarias."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa el generador.

        Args:
            api_key: API key de Gemini. Si es None, solo funciona con fallback offline.
        """
        self._ai_service = AIService(api_key=api_key)
        self._prompt_builder = PromptBuilder()

    def generate(
        self,
        tipo_obra: str,
        descripcion: str,
        plantilla: Optional[Dict] = None,
        datos_proyecto: Optional[Dict] = None,
    ) -> Dict:
        """
        Genera partidas presupuestarias para un tipo de obra.

        Args:
            tipo_obra: Tipo de obra escrito por el usuario.
            descripcion: Descripción adicional del usuario.
            plantilla: Plantilla seleccionada del catálogo (None = sin plantilla).
            datos_proyecto: Datos del proyecto (localidad, cliente, etc.).

        Returns:
            Diccionario con:
            - partidas: lista de partidas generadas
            - error: mensaje de error o None
            - source: 'ia' | 'offline' | 'error'
        """
        # Si el servicio de IA no está disponible, ir directo al fallback
        if not self._ai_service.is_available():
            return self._fallback(plantilla, "No hay API key configurada.")

        # Construir el prompt
        prompt = self._prompt_builder.build_prompt(
            tipo_obra=tipo_obra,
            descripcion=descripcion,
            plantilla=plantilla,
            datos_proyecto=datos_proyecto,
        )

        # Intentar generar con IA
        partidas, error = self._ai_service.generate_partidas(prompt)

        if partidas and not error:
            return {
                'partidas': partidas,
                'error': None,
                'source': 'ia',
            }

        # IA falló: intentar fallback
        return self._fallback(plantilla, error)

    def _fallback(
        self,
        plantilla: Optional[Dict],
        original_error: Optional[str],
    ) -> Dict:
        """
        Fallback offline cuando la IA no está disponible o falla.

        Si hay plantilla seleccionada, devuelve sus partidas_base adaptadas.
        Si no hay plantilla, devuelve error descriptivo.

        Args:
            plantilla: Plantilla del catálogo (puede ser None).
            original_error: Mensaje de error original de la IA.

        Returns:
            Diccionario con partidas, error y source.
        """
        if plantilla is not None:
            # Convertir partidas_base al formato estándar de partidas
            partidas = self._adapt_partidas_base(plantilla.get('partidas_base', []))
            if partidas:
                return {
                    'partidas': partidas,
                    'error': None,
                    'source': 'offline',
                }

        # Sin plantilla y sin IA: no se pueden generar partidas
        return {
            'partidas': [],
            'error': (
                "No se pudieron generar partidas. "
                "Sin conexión a la IA y sin plantilla de referencia seleccionada. "
                f"Detalle: {original_error}"
            ),
            'source': 'error',
        }

    def _adapt_partidas_base(self, partidas_base: List[Dict]) -> List[Dict]:
        """
        Adapta partidas_base del catálogo al formato estándar de partidas.

        Las partidas_base tienen: concepto, unidad, precio_ref
        El formato estándar tiene: concepto, cantidad, unidad, precio_unitario

        Args:
            partidas_base: Lista de partidas del catálogo.

        Returns:
            Lista de partidas en formato estándar.
        """
        partidas = []
        for base in partidas_base:
            partidas.append({
                'concepto': base.get('concepto', ''),
                'cantidad': 1,  # Cantidad por defecto
                'unidad': base.get('unidad', 'ud'),
                'precio_unitario': base.get('precio_ref', 0.0),
            })
        return partidas
