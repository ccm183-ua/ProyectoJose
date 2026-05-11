"""Mejora opcional de contexto de busqueda historica con IA."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.core.ai_clients import get_ai_client_from_settings, normalize_ai_error, redact_secrets


HISTORICAL_SEARCH_CONTEXT_ENHANCER_PROMPT_VERSION = "historical_search_context_enhancer_v1"

HISTORICAL_SEARCH_CONTEXT_ENHANCER_SYSTEM_PROMPT = """
Eres un asistente tecnico especializado en presupuestos de construccion, reformas,
mantenimiento de comunidades y reparaciones.

Tu tarea NO es crear partidas ni presupuestos.
Tu tarea es reescribir una descripcion breve del usuario en una descripcion tecnica
mas completa para mejorar una busqueda en una base historica de presupuestos.

Reglas:
- Respeta estrictamente la intencion del usuario.
- No inventes cantidades, precios, mediciones ni ubicaciones.
- No inventes materiales especificos si el usuario no los menciona, salvo terminos genericos razonables.
- No anadas trabajos no relacionados.
- Si puedes anadir vocabulario tecnico habitual.
- Si puedes explicar fases probables de la intervencion de forma generica.
- El resultado debe ser util para encontrar partidas similares en una base historica.
- Escribe en espanol profesional.
- Devuelve JSON estricto.

Formato:
{
  "enhanced_description": "...",
  "detected_work_types": ["..."],
  "technical_terms": ["..."],
  "confidence": 0.0,
  "warnings": []
}
""".strip()


class HistoricalSearchContextEnhancer:
    """Mejora una descripcion breve para buscar mejor en memoria historica."""

    def __init__(self, ai_client: Optional[Any] = None):
        self._ai_client = ai_client

    def enhance(self, base_description: str, project_data: dict | None = None) -> dict:
        original = " ".join(str(base_description or "").split()).strip()
        if not original:
            raise ValueError("Escribe una descripcion antes de mejorarla con IA.")

        client = self._ai_client or get_ai_client_from_settings()
        try:
            data = client.generate_json(
                system_prompt=HISTORICAL_SEARCH_CONTEXT_ENHANCER_SYSTEM_PROMPT,
                user_payload={
                    "base_description": original,
                    "project_data": _safe_project_context(project_data or {}),
                    "prompt_version": HISTORICAL_SEARCH_CONTEXT_ENHANCER_PROMPT_VERSION,
                },
                temperature=0.2,
                max_tokens=700,
            )
            enhanced = " ".join(str(data.get("enhanced_description") or "").split()).strip()
            if not enhanced:
                raise ValueError("La IA no devolvio una descripcion mejorada.")
            return {
                "original_description": original,
                "enhanced_description": enhanced,
                "detected_work_types": _clean_string_list(data.get("detected_work_types")),
                "technical_terms": _clean_string_list(data.get("technical_terms")),
                "warnings": _clean_string_list(data.get("warnings")),
                "confidence": _safe_confidence(data.get("confidence")),
                "provider": str(getattr(client, "provider_name", "") or ""),
                "model": str(getattr(client, "model_name", "") or ""),
                "prompt_version": HISTORICAL_SEARCH_CONTEXT_ENHANCER_PROMPT_VERSION,
            }
        except Exception as exc:
            message = normalize_ai_error(exc)
            if not message:
                message = redact_secrets(str(exc))
            raise RuntimeError(message) from exc


def _safe_project_context(project_data: Dict) -> Dict:
    allowed = (
        "tipo",
        "nombre_obra",
        "descripcion",
        "direccion",
        "calle",
        "localidad",
    )
    result = {}
    for key in allowed:
        value = project_data.get(key)
        if value is None or isinstance(value, (dict, list, tuple, set)):
            continue
        text = " ".join(str(value).split()).strip()
        if text:
            result[key] = text[:240]
    return result


def _clean_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    result = []
    for item in value:
        text = " ".join(str(item or "").split()).strip()
        if text:
            result.append(text[:120])
    return result[:12]


def _safe_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))
