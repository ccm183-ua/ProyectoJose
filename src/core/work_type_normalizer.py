"""
Normalización de texto y tipo de obra para inteligencia histórica.
"""

import re
import unicodedata
from typing import List


ABBREVIATIONS = {
    "rep": "reparacion",
    "repar": "reparacion",
    "sust": "sustitucion",
    "imper": "impermeabilizacion",
    "imperm": "impermeabilizacion",
    "rehab": "rehabilitacion",
    "filt": "filtracion",
    "filtr": "filtracion",
    "cub": "cubierta",
    "fachad": "fachada",
    "baj": "bajante",
}

_SIGNAL_TERMS = {
    "bajante",
    "fontaneria",
    "demolicion",
    "desmontaje",
    "albanileria",
    "alicatado",
    "pintura",
    "residuo",
    "escombro",
    "impermeabilizacion",
    "cubierta",
    "fachada",
    "filtracion",
    "rehabilitacion",
    "sustitucion",
    "reparacion",
}


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_text(text: str) -> str:
    """
    Normaliza un texto: minúsculas, sin tildes, sin puntuación y abreviaturas.
    """
    if not text:
        return ""
    value = _strip_accents(text.lower())
    value = re.sub(r"[^\w\s]", " ", value)
    raw_tokens = [token for token in value.split() if token]
    normalized_tokens = [_expand_abbreviation(token) for token in raw_tokens]
    return " ".join(normalized_tokens).strip()


def _expand_abbreviation(token: str) -> str:
    if token in ABBREVIATIONS:
        return ABBREVIATIONS[token]
    for short, full in ABBREVIATIONS.items():
        if token.startswith(short) and len(token) >= len(short):
            return full
    return token


def normalize_work_type(text: str) -> str:
    """
    Normaliza una descripción de tipo de obra retirando ruido frecuente.
    """
    normalized = normalize_text(text)
    if not normalized:
        return ""
    # Eliminar referencias de piso/letra típicas: "8 c", "3 b", etc.
    normalized = re.sub(r"\b\d{1,2}\s*[a-z]\b", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def extract_work_signals(text: str) -> List[str]:
    """
    Extrae señales de trabajo detectadas en un texto normalizado.
    """
    normalized = normalize_work_type(text)
    if not normalized:
        return []
    tokens = normalized.split()
    found = []
    seen = set()
    for token in tokens:
        candidates = [token]
        if token.endswith("es") and len(token) > 4:
            candidates.append(token[:-2])
        if token.endswith("s") and len(token) > 3:
            candidates.append(token[:-1])
        for candidate in candidates:
            if candidate in _SIGNAL_TERMS and candidate not in seen:
                seen.add(candidate)
                found.append(candidate)
    return found
