"""
Contexto confirmado por usuario para sugerencias historicas.
"""

from typing import Dict, Optional

from src.core.historical_partida_classifier import HistoricalPartidaClassifier
from src.core.historical_suggestion_service import HistoricalSuggestionService
from src.core.work_type_normalizer import extract_work_signals, normalize_work_type


PREFERRED_CONTEXT_FIELDS = (
    "tipo",
    "nombre_obra",
    "descripcion",
    "direccion",
    "calle",
    "num_calle",
    "codigo_postal",
    "localidad",
)

GENERIC_CONTEXT_PATTERNS = {
    "rehabilitacion de edificio",
    "reparacion general",
    "obra comunidad",
    "varios trabajos",
}


def build_initial_historical_context(project_data: Dict) -> str:
    """Construye una descripcion inicial a partir de campos disponibles."""
    data = project_data or {}
    parts = []
    seen = set()

    for key in PREFERRED_CONTEXT_FIELDS:
        value = _clean_value(data.get(key))
        if value and value.lower() not in seen:
            seen.add(value.lower())
            parts.append(value)

    for key, raw_value in data.items():
        if key in PREFERRED_CONTEXT_FIELDS:
            continue
        if _should_skip_field(key):
            continue
        value = _clean_value(raw_value)
        if value and value.lower() not in seen:
            seen.add(value.lower())
            parts.append(value)

    return ". ".join(parts).strip()


def is_generic_historical_context(text: str) -> bool:
    normalized = normalize_work_type(text or "")
    if not normalized:
        return True
    if normalized in GENERIC_CONTEXT_PATTERNS:
        return True
    generic_tokens = {"rehabilitacion", "reparacion", "obra", "comunidad", "trabajos", "varios", "general"}
    tokens = set(normalized.split())
    return bool(tokens) and tokens.issubset(generic_tokens)


def is_useful_historical_context(
    text: str,
    classifier: Optional[HistoricalPartidaClassifier] = None,
) -> bool:
    normalized = normalize_work_type(text or "")
    if not normalized or is_generic_historical_context(normalized):
        return False

    words = normalized.split()
    if len(words) >= 8:
        return True
    if len(extract_work_signals(normalized)) >= 2:
        return True

    classifier = classifier or HistoricalPartidaClassifier()
    return bool(classifier.classify_text(normalized))


def request_historical_suggestions_for_context(
    project_data: Dict,
    confirmed_context: str,
    service: Optional[HistoricalSuggestionService] = None,
) -> Optional[Dict]:
    """Valida contexto confirmado y consulta sugerencias historicas."""
    if not is_useful_historical_context(confirmed_context):
        return None
    service = service or HistoricalSuggestionService()
    return service.suggest_for_project({}, user_description=confirmed_context)


def _clean_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set, dict)):
        return ""
    return " ".join(str(value).split()).strip()


def _should_skip_field(key: str) -> bool:
    key_lower = (key or "").strip().lower()
    skip_markers = (
        "id",
        "cif",
        "email",
        "telefono",
        "fecha",
        "numero",
        "postal",
        "mediacion",
        "api",
        "ruta",
        "path",
    )
    return any(marker in key_lower for marker in skip_markers)
