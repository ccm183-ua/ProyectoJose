"""
Servicio de IA para generación de partidas presupuestarias.

Utiliza Google Gemini 2.5 Flash para generar partidas a partir de un prompt.
Incluye parseo robusto de respuestas, reintentos automáticos, fallback de
modelos y manejo de errores amigable.
"""

import json
import re
import time
from typing import Dict, List, Optional, Tuple


# Modelos en orden de preferencia (cada uno tiene cuota independiente)
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]

# Reintentos por modelo antes de pasar al siguiente
MAX_RETRIES_PER_MODEL = 1
RETRY_DELAY = 10  # segundos


class AIService:
    """Cliente de IA para generación de partidas presupuestarias."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Inicializa el servicio de IA.

        Args:
            api_key: API key de Google Gemini. Si es None o vacía,
                     el servicio no estará disponible.
        """
        self._api_key = api_key if api_key and api_key.strip() else None
        self._model = None

    def is_available(self) -> bool:
        """
        Comprueba si el servicio está disponible.

        Returns:
            True si hay API key configurada.
        """
        return self._api_key is not None

    def generate_contexto_ia(self, nombre: str, partidas: list) -> Optional[str]:
        """
        Genera un contexto_ia descriptivo a partir del nombre y las partidas.

        Usa la IA para crear un párrafo descriptivo que se usará como
        contexto en futuros prompts de generación de partidas.

        Args:
            nombre: Nombre de la plantilla.
            partidas: Lista de partidas extraídas del Excel.

        Returns:
            String con el contexto generado, o None si la IA no está disponible
            o hay algún error.
        """
        if not self.is_available():
            return None

        # Extraer lista de conceptos para el prompt
        conceptos = [p.get('concepto', '') for p in partidas[:15]]
        lista_conceptos = ", ".join(c for c in conceptos if c)

        prompt = (
            f"Genera un párrafo descriptivo (3-5 líneas) para un contexto de "
            f"presupuesto de obra de tipo '{nombre}'. Las partidas incluidas son: "
            f"{lista_conceptos}. Describe qué incluye este tipo de obra, "
            f"materiales habituales y consideraciones técnicas importantes. "
            f"Responde solo con el texto descriptivo, sin formato JSON ni markdown."
        )

        try:
            response = self._call_api(prompt)
            response_text = response.text if hasattr(response, 'text') else str(response)
            text = response_text.strip()
            if len(text) >= 20:
                return text
            return None
        except Exception:
            return None

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
            return [], self._friendly_error(e)

    def _call_api(self, prompt: str):
        """
        Realiza la llamada a la API de Gemini con fallback entre modelos.

        Intenta cada modelo de la lista MODELS en orden. Si un modelo
        falla con 429 (cuota agotada), reintenta una vez y si sigue
        fallando, pasa al siguiente modelo. Así maximizamos la
        disponibilidad aprovechando las cuotas independientes de cada modelo.

        Args:
            prompt: Prompt completo a enviar.

        Returns:
            Respuesta de la API.
        """
        # Importar aquí para no requerir la dependencia si no se usa
        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "La librería 'google-genai' no está instalada. "
                "Ejecute: pip install google-genai"
            )

        if self._model is None:
            client = genai.Client(api_key=self._api_key)
            self._client = client

        last_error = None
        for model_name in MODELS:
            for attempt in range(MAX_RETRIES_PER_MODEL + 1):
                try:
                    response = self._client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                    return response
                except Exception as e:
                    last_error = e
                    error_str = str(e)
                    is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str
                    if is_rate_limit and attempt < MAX_RETRIES_PER_MODEL:
                        time.sleep(RETRY_DELAY)
                        continue
                    elif is_rate_limit:
                        # Cuota agotada para este modelo, probar el siguiente
                        break
                    else:
                        # Error no relacionado con cuota, propagar
                        raise

        # Todos los modelos fallaron
        raise last_error

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        """
        Traduce excepciones de la API de Gemini a mensajes legibles en español.

        Args:
            exc: Excepción capturada.

        Returns:
            Mensaje de error amigable para mostrar al usuario.
        """
        error_str = str(exc)

        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            return (
                "Cuota temporal agotada en la API de Gemini. "
                "Se reintentó automáticamente pero sigue ocupada. "
                "Espere un minuto e inténtelo de nuevo."
            )

        if "403" in error_str or "PERMISSION_DENIED" in error_str:
            return (
                "API key sin permisos. Verifique su clave en Configuración > IA."
            )

        if "API_KEY_INVALID" in error_str or "400" in error_str and "API key" in error_str:
            return (
                "La API key no es válida. Configúrela de nuevo en Configuración > IA."
            )

        if "DEADLINE_EXCEEDED" in error_str or "timeout" in error_str.lower():
            return "Tiempo de espera agotado al contactar con la IA. Inténtelo de nuevo."

        # Error genérico: truncar para no mostrar JSON crudo completo
        return f"Error al contactar con la IA: {error_str[:200]}"

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
