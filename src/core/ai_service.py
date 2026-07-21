"""
Servicio de IA para generación de partidas presupuestarias.

Parseo del esquema "partidas" (esquema esperado por el generador de
presupuestos) sobre la respuesta de Gemini. La llamada real al proveedor se
delega en `GeminiAIClient` (src/core/ai_clients.py) — este módulo no importa
el SDK de Gemini directamente, solo añade el fallback entre varios modelos
(cada uno con cuota independiente) y el parseo específico de partidas.
"""

import json
import logging
import re
from typing import Dict, List, Optional, Tuple

from src.core.ai_clients import GeminiAIClient, normalize_ai_error

logger = logging.getLogger(__name__)


# Modelos en orden de preferencia (cada uno tiene cuota independiente)
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]


class AIService:
    """Cliente de IA para generación de partidas presupuestarias."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Inicializa el servicio de IA.

        Args:
            api_key: API key de Google Gemini. Si es None o vacía,
                     el servicio no estará disponible.
        """
        self._api_key = api_key if api_key and api_key.strip() else None
        self._configured_model = model.strip() if model and model.strip() else None
        self._client = GeminiAIClient(
            self._api_key, self._configured_model, fallback_models=MODELS,
        )

    @property
    def _model(self) -> Optional[str]:
        return self._client.model_name if self._api_key else None

    def is_available(self) -> bool:
        """
        Comprueba si el servicio está disponible.

        Returns:
            True si hay API key configurada.
        """
        return self._api_key is not None

    def generate_partidas(self, prompt: str) -> Tuple[List[Dict], Optional[str]]:
        """
        Genera partidas presupuestarias usando la IA.

        Args:
            prompt: Prompt completo construido por PromptBuilder.

        Returns:
            Tupla (lista_partidas, mensaje_error).
            Si hay error, lista_partidas estará vacía y mensaje_error tendrá info.
            Si todo va bien, mensaje_error será None.
        """
        if not self.is_available():
            return [], "No hay API key configurada. Configure su clave en Configuración > IA."

        try:
            response = self._call_api(prompt)
            response_text = response.text if hasattr(response, 'text') else str(response)
            partidas = self.parse_response(response_text)
            return partidas, None
        except TimeoutError:
            return [], "Tiempo de espera agotado al contactar con la IA. Inténtelo de nuevo."
        except ImportError as e:
            return [], str(e)
        except Exception as e:
            return [], normalize_ai_error(e)

    def generate_text(self, prompt: str) -> Tuple[str, Optional[str], str]:
        """
        Genera texto libre usando la IA.

        Se usa para flujos auxiliares que necesitan validar su propio JSON
        de salida sin reutilizar el parser de partidas.

        Returns:
            Tupla (texto, mensaje_error, modelo). Si hay error, texto estara
            vacio y mensaje_error tendra informacion legible.
        """
        if not self.is_available():
            return "", "No hay API key configurada. Configure su clave en Configuracion > IA.", ""

        try:
            response = self._call_api(prompt)
            response_text = response.text if hasattr(response, "text") else str(response)
            return response_text, None, self._model or ""
        except TimeoutError:
            return "", "Tiempo de espera agotado al contactar con la IA. Intentelo de nuevo.", ""
        except ImportError as e:
            return "", str(e), ""
        except Exception as e:
            return "", normalize_ai_error(e), ""

    def _call_api(self, prompt: str) -> str:
        """
        Llama al proveedor Gemini con fallback entre modelos (cada uno con
        cuota independiente). La llamada real al SDK vive en `GeminiAIClient`
        (src/core/ai_clients.py); este método solo delega.
        """
        return self._client.generate_text(prompt)

    def parse_response(self, response_text: str) -> List[Dict]:
        """
        Parsea la respuesta de la IA extrayendo las partidas.

        Maneja:
        - JSON limpio
        - JSON envuelto en bloques markdown (```json ... ```)
        - JSON mal formado (devuelve lista vacía)
        - Partidas con campos faltantes (rellena con valores por defecto)

        Args:
            response_text: Texto de respuesta de la IA.

        Returns:
            Lista de diccionarios con las partidas parseadas.
        """
        # Intentar extraer JSON de bloques markdown
        clean_text = self._extract_json_from_markdown(response_text)

        try:
            data = json.loads(clean_text)
        except (json.JSONDecodeError, TypeError):
            return []

        # Extraer la lista de partidas
        partidas_raw = data.get('partidas', [])
        if not isinstance(partidas_raw, list):
            return []

        # Normalizar cada partida con valores por defecto
        partidas = []
        for raw in partidas_raw:
            if not isinstance(raw, dict):
                continue

            # Formato nuevo: titulo + descripcion (separados)
            titulo = str(raw.get('titulo', '')).strip()
            descripcion = str(raw.get('descripcion', '')).strip()

            # Formato antiguo: solo concepto (backward compat)
            concepto = str(raw.get('concepto', '')).strip()

            # Si tiene titulo, usarlo como formato principal
            if titulo:
                # Asegurar mayúsculas en el título
                titulo = titulo.upper()
                if not titulo.endswith('.'):
                    titulo += '.'
            elif concepto:
                # Fallback: si solo hay concepto, intentar extraer titulo
                titulo = concepto.upper()
                if not titulo.endswith('.'):
                    titulo += '.'
            else:
                continue  # Sin titulo ni concepto, saltar

            # Construir concepto combinado para visualización simple
            if descripcion:
                concepto_combinado = f"{titulo}\n{descripcion}"
            else:
                concepto_combinado = titulo

            partida = {
                'titulo': titulo,
                'descripcion': descripcion,
                'concepto': concepto_combinado,
                'cantidad': self._safe_number(raw.get('cantidad'), default=1),
                'unidad': str(raw.get('unidad', 'ud')),
                'precio_unitario': self._safe_number(raw.get('precio_unitario'), default=0.0),
            }
            partidas.append(partida)

        return partidas

    def _extract_json_from_markdown(self, text: str) -> str:
        """
        Extrae JSON de un bloque markdown ```json ... ```.

        Args:
            text: Texto que puede contener bloques markdown.

        Returns:
            Texto JSON limpio.
        """
        # Buscar bloques ```json ... ``` o ``` ... ```
        pattern = r'```(?:json)?\s*\n?(.*?)\n?\s*```'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _safe_number(self, value, default=0):
        """
        Convierte un valor a número de forma segura.

        Args:
            value: Valor a convertir.
            default: Valor por defecto si la conversión falla.

        Returns:
            Número (int o float).
        """
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
