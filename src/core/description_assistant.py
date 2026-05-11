"""Ayuda con IA para redactar la descripcion de contexto antes de generar partidas."""

from __future__ import annotations

import json
from typing import Dict, Optional, Tuple

from src.core.ai_clients import get_ai_client_from_settings, normalize_ai_error
from src.core.settings import Settings

_SYSTEM = (
    "Eres ayudante de un presupuestista. Redactas descripciones de obra claras para "
    "documentación interna y para que otra IA genere partidas de presupuesto.\n"
    "REGLAS:\n"
    '- Responde SOLO con un JSON válido con la clave exacta "descripcion_redactada" '
    "(string en español).\n"
    "- Tono profesional; puedes usar viñetas breves si clarifica el alcance.\n"
    "- No inventes datos que no figuren en el borrador ni en datos del proyecto.\n"
    "- Si el borrador está vacío, redacta una descripción inicial a partir del tipo de obra "
    "y los datos del proyecto, sin supuestos arriesgados.\n"
    "- Límite aproximado 2000 caracteres en descripcion_redactada."
)


def _datos_proyecto_texto(datos: Optional[Dict]) -> str:
    if not datos:
        return "(sin datos adicionales)"
    lines = []
    for key in ("cliente", "calle", "localidad", "tipo", "numero", "fecha"):
        val = datos.get(key)
        if val is not None and str(val).strip():
            lines.append(f"{key}: {str(val).strip()}")
    if not lines:
        return "(sin datos adicionales)"
    return "\n".join(lines)


def polish_budget_context_description(
    settings: Settings,
    *,
    tipo_obra: str,
    borrador: str,
    datos_proyecto: Optional[Dict] = None,
    context_extra: str = "",
) -> Tuple[str, Optional[str]]:
    """
    Devuelve (texto_redactado, error). Si hay error, texto_redactado vacio.
    """
    client = get_ai_client_from_settings(settings)
    if not client.is_available():
        return "", "Configure una API key de IA en Configuracion > IA."

    tipo = (tipo_obra or "").strip() or "(sin tipo indicado)"
    draft = (borrador or "").strip()
    payload = {
        "tipo_obra": tipo,
        "borrador_descripcion": draft if draft else "(vacío — generar desde tipo y datos)",
        "datos_proyecto": _datos_proyecto_texto(datos_proyecto),
        "contexto_memoria_historica": (context_extra or "").strip() or "(ninguno)",
    }
    try:
        data = client.generate_json(
            system_prompt=_SYSTEM,
            user_payload=payload,
            temperature=0.35,
            max_tokens=1200,
        )
    except Exception as exc:
        return "", normalize_ai_error(exc)

    text = data.get("descripcion_redactada")
    if not isinstance(text, str):
        return "", "La IA no devolvió el campo descripcion_redactada."
    text = text.strip()
    if not text:
        return "", "La IA devolvió una descripción vacía."
    return text, None
