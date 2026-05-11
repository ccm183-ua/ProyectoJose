"""
Generador de presupuestos con IA.

Orquesta el flujo completo de generación de partidas:
1. Construye el prompt (con o sin plantilla)
2. Llama a la IA si está disponible
3. Si falla, usa fallback offline (partidas_base de la plantilla)
4. Devuelve resultado con indicador de fuente
"""

import json
from typing import Dict, List, Optional

from src.core.ai_clients import DeepSeekAIClient, normalize_ai_error
from src.core.ai_service import AIService
from src.core.prompt_builder import PromptBuilder
from src.core.settings import AI_PROVIDER_DEEPSEEK, Settings


class BudgetGenerator:
    """Orquesta la generación de partidas presupuestarias."""

    def __init__(self, api_key: Optional[str] = None, settings: Optional[Settings] = None):
        """
        Inicializa el generador.

        Args:
            api_key: API key de Gemini. Si es None, solo funciona con fallback offline.
        """
        self._settings = settings
        self._active_provider = settings.get_ai_provider() if settings and api_key is None else "GEMINI"
        gemini_key = api_key if api_key is not None else (settings.get_gemini_api_key() if settings else None)
        gemini_model = settings.get_gemini_model() if settings else None
        self._ai_service = AIService(api_key=gemini_key, model=gemini_model)
        self._deepseek_client = None
        if self._active_provider == AI_PROVIDER_DEEPSEEK:
            self._deepseek_client = DeepSeekAIClient(
                self._settings.get_deepseek_api_key(),
                self._settings.get_deepseek_model(),
            )
        self._prompt_builder = PromptBuilder()

    def generate(
        self,
        tipo_obra: str,
        descripcion: str,
        plantilla: Optional[Dict] = None,
        datos_proyecto: Optional[Dict] = None,
        historical_context: Optional[Dict] = None,
    ) -> Dict:
        """
        Genera partidas presupuestarias para un tipo de obra.

        Args:
            tipo_obra: Tipo de obra escrito por el usuario.
            descripcion: Descripción adicional del usuario.
            plantilla: Plantilla seleccionada del catálogo (None = sin plantilla).
            datos_proyecto: Datos del proyecto (localidad, cliente, etc.).
            historical_context: Contexto histórico opcional para enriquecer el prompt.

        Returns:
            Diccionario con:
            - partidas: lista de partidas generadas
            - error: mensaje de error o None
            - source: 'ia' | 'offline' | 'error'
        """
        # Si el servicio de IA no está disponible, ir directo al fallback
        if not self._is_ai_available():
            return self._fallback(plantilla, "No hay API key configurada.")

        # Construir el prompt
        prompt = self._prompt_builder.build_prompt(
            tipo_obra=tipo_obra,
            descripcion=descripcion,
            plantilla=plantilla,
            datos_proyecto=datos_proyecto,
            historical_context=historical_context,
        )

        # Intentar generar con IA
        partidas, error = self._generate_partidas_with_active_provider(prompt)

        if partidas and not error:
            return {
                'partidas': partidas,
                'error': None,
                'source': 'ia',
            }

        # IA falló: intentar fallback
        return self._fallback(plantilla, error)

    def _is_ai_available(self) -> bool:
        if self._active_provider == AI_PROVIDER_DEEPSEEK:
            return bool(self._deepseek_client and self._deepseek_client.is_available())
        return self._ai_service.is_available()

    def _generate_partidas_with_active_provider(self, prompt: str):
        if self._active_provider != AI_PROVIDER_DEEPSEEK:
            return self._ai_service.generate_partidas(prompt)
        try:
            data = self._deepseek_client.generate_json(
                system_prompt=(
                    "Eres un asistente experto en presupuestos de construcción. "
                    "Devuelve JSON estricto con una clave partidas."
                ),
                user_payload={"prompt": prompt},
                temperature=0.2,
                max_tokens=1600,
            )
            partidas = self._ai_service.parse_response(json.dumps(data, ensure_ascii=False))
            return partidas, None if partidas else "La IA no devolvió partidas válidas."
        except Exception as exc:
            return [], normalize_ai_error(exc)

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
            concepto_raw = base.get('concepto', '')
            titulo = concepto_raw.upper()
            if not titulo.endswith('.'):
                titulo += '.'
            partidas.append({
                'titulo': titulo,
                'descripcion': '',
                'concepto': titulo,
                'cantidad': base.get('cantidad_ref', 1),
                'unidad': base.get('unidad', 'ud'),
                'precio_unitario': base.get('precio_ref', 0.0),
            })
        return partidas
