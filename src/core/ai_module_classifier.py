"""
Clasificador de módulos de ejecución asistido por IA.

Complemento OPCIONAL del HistoricalPartidaClassifier (basado en reglas).
Se usa únicamente como red de seguridad cuando las reglas por palabras clave
no detectan ningún módulo en una descripción libre — el caso típico del
arquitecto experto que describe la obra de forma muy condensada y técnica,
sin usar las palabras exactas del vocabulario de reglas.

Devuelve siempre módulos dentro del vocabulario controlado (MODULE_RULES);
nunca inventa módulos nuevos. Ante cualquier fallo (sin API key, error de red,
JSON inválido) devuelve lista vacía y el llamador mantiene su comportamiento
previo. Por eso es seguro activarlo sin riesgo de romper el flujo existente.
"""

import json
import logging
from typing import Dict, List, Optional

from src.core.historical_partida_classifier import MODULE_RULES
from src.core.settings import AI_PROVIDER_DEEPSEEK, Settings

logger = logging.getLogger(__name__)

# Confianza asignada a un módulo detectado por IA. Por encima del umbral mínimo
# del servicio de sugerencias (0.2) pero por debajo de una coincidencia fuerte
# de reglas, para reflejar que es una señal más blanda.
AI_MODULE_CONFIDENCE = 0.7


class AIModuleClassifier:
    """Detecta módulos de ejecución a partir de texto libre usando IA."""

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or Settings()

    def is_available(self) -> bool:
        """True si hay una API key activa para el proveedor configurado."""
        try:
            return self._settings.has_active_ai_key()
        except Exception:
            return False

    def classify_text(
        self, text: str, allowed_modules: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Clasifica *text* en uno o varios módulos del vocabulario controlado.

        Args:
            text: Descripción libre de la obra.
            allowed_modules: Lista de módulos válidos (por defecto MODULE_RULES).

        Returns:
            Lista de dicts ``{"module", "confidence", "source": "ai"}``.
            Vacía si no hay IA disponible o ante cualquier error.
        """
        text = (text or "").strip()
        if not text or not self.is_available():
            return []

        allowed = allowed_modules or list(MODULE_RULES.keys())
        allowed_set = set(allowed)

        try:
            raw = self._call_ai(text, allowed)
        except Exception as exc:  # noqa: BLE001 — degradación silenciosa por diseño
            logger.debug("AIModuleClassifier falló, se ignora: %s", exc)
            return []

        return self._parse(raw, allowed_set)

    # ── Llamada al proveedor ──────────────────────────────────────────────────

    def _call_ai(self, text: str, allowed: List[str]) -> str:
        """Devuelve la respuesta cruda (texto JSON) del proveedor activo."""
        system_prompt = (
            "Eres un clasificador experto de obras de construcción y reformas. "
            "Clasificas una descripción de obra en módulos de ejecución."
        )
        instruction = self._build_instruction(text, allowed)

        if self._settings.get_ai_provider() == AI_PROVIDER_DEEPSEEK:
            from src.core.ai_clients import DeepSeekAIClient

            client = DeepSeekAIClient(
                self._settings.get_deepseek_api_key(),
                self._settings.get_deepseek_model(),
            )
            data = client.generate_json(
                system_prompt=system_prompt,
                user_payload={"instruccion": instruction},
                temperature=0.0,
                max_tokens=300,
            )
            return json.dumps(data, ensure_ascii=False)

        from src.core.ai_service import AIService

        service = AIService(
            api_key=self._settings.get_gemini_api_key(),
            model=self._settings.get_gemini_model(),
        )
        prompt = f"{system_prompt}\n\n{instruction}"
        response_text, error, _ = service.generate_text(prompt)
        if error:
            raise RuntimeError(error)
        return response_text

    @staticmethod
    def _build_instruction(text: str, allowed: List[str]) -> str:
        modules_str = ", ".join(allowed)
        return (
            "Lista de módulos válidos (usa EXCLUSIVAMENTE estos identificadores):\n"
            f"{modules_str}\n\n"
            "Descripción de la obra:\n"
            f'"{text}"\n\n'
            "Devuelve ÚNICAMENTE un objeto JSON con la forma:\n"
            '{"modules": ["modulo1", "modulo2"]}\n'
            "Incluye solo los módulos realmente implicados en la obra descrita. "
            "Si no reconoces ninguno con seguridad, devuelve {\"modules\": []}. "
            "No añadas texto fuera del JSON."
        )

    # ── Parseo ────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse(raw: str, allowed_set: set) -> List[Dict]:
        text = (raw or "").strip()
        if not text:
            return []

        # Tolerar JSON envuelto en markdown.
        if "```" in text:
            import re

            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
            if match:
                text = match.group(1).strip()

        try:
            data = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return []

        modules_raw = data.get("modules") if isinstance(data, dict) else None
        if not isinstance(modules_raw, list):
            return []

        results: List[Dict] = []
        seen: set = set()
        for item in modules_raw:
            name = str(item or "").strip().lower()
            if name in allowed_set and name not in seen:
                seen.add(name)
                results.append(
                    {
                        "module": name,
                        "confidence": AI_MODULE_CONFIDENCE,
                        "source": "ai",
                    }
                )
        return results
