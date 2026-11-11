"""
Normalización de texto y tipo de obra para inteligencia histórica.
"""

import math
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
    # Errata frecuente en el histórico real (44 apariciones).
    "imperbeabilizacion": "impermeabilizacion",
    # Formas que la expansión por prefijo antigua ya llevaba a
    # impermeabilizacion y que son del mismo dominio (lámina/mortero
    # impermeable, "Impermor"): se conservan explícitamente.
    "impermeable": "impermeabilizacion",
    "impermeables": "impermeabilizacion",
    "impermor": "impermeabilizacion",
}

# Claves excluidas de la coincidencia por PREFIJO (Decision 20, familia
# impermeabilizacion, 2026-08-04): "cub" capturaba por prefijo palabras
# reales sin relacion con cubierta/tejado -- "cubricion" (usada en
# albardilla, no en tejados), "cubrir", "cubo", "cubanita"... (~132 lineas
# reales verificadas). Sigue funcionando como abreviatura si aparece
# exacta (token == "cub"), via la comprobacion directa en
# _expand_abbreviation antes de este filtro.
#
# El mismo patron de colision existe tambien en "baj" ("baja"/"bajo",
# ~993 lineas), "rep" ("reposicion"/"replanteo"/"repaso", ~312 lineas),
# "sust" ("sustancia", ~56 lineas) e "imper" ("imperfecciones", ~23
# lineas) -- detectado en la misma revision pero deliberadamente NO
# corregido aqui: es un hallazgo sistemico que afecta a clasificaciones
# de toda la app, no solo a esta familia, y merece su propio plan con el
# mismo cuidado que este documento, no un parche de paso. Ver
# "Pendiente" mas abajo.
#
# Resuelto el 2026-11-11 en _expand_abbreviation: por prefijo solo se expande
# un truncamiento o una forma flexionada con raíz común larga. Medido sobre
# 19.205 partidas reales: 1.002 dejan de recibir un módulo por falso positivo
# (979 sustitucion_bajante por "planta baja"/"bajo"/"bajada"; 27
# impermeabilizacion) y ninguna gana o pierde un módulo legítimo.
_PREFIX_MATCH_EXCLUDED = {"cub"}

# Palabras reales que son truncamiento literal de una forma completa pero NO
# son abreviatura suya: "baja" (planta baja, dar de baja) no es "bajante".
_PREFIX_MATCH_STOPWORDS = {"baja"}

# Raíz común mínima (fracción de la palabra completa) para aceptar una forma
# flexionada: "reparar"/"reparacion" (6/10) sí; "reparto" (5/10) no.
_INFLECTION_MIN_SHARED_RATIO = 0.6

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
    "garaje",
    "hormigon",
    "filtracion",
    "parking",
    "pilar",
    "rehabilitacion",
    "refuerzo",
    "sustitucion",
    "reparacion",
    "viga",
    "zuncho",
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


_KEYWORD_RE_CACHE: dict = {}


def keyword_in_text(keyword: str, normalized_text: str) -> bool:
    """True si ``keyword`` aparece en el texto empezando en inicio de palabra.

    Ambos deben estar ya normalizados (``normalize_text``). El keyword puede
    ser una raíz ("impermeabiliz" casa con "impermeabilizacion"), pero no
    puede empezar a mitad de palabra: "atado" NO casa con "alicatado".
    """
    if not keyword or not normalized_text:
        return False
    pattern = _KEYWORD_RE_CACHE.get(keyword)
    if pattern is None:
        pattern = re.compile(r"(?<!\w)" + re.escape(keyword))
        _KEYWORD_RE_CACHE[keyword] = pattern
    return pattern.search(normalized_text) is not None


def _shared_prefix_len(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def _expand_abbreviation(token: str) -> str:
    """Expande una abreviatura a su forma completa.

    Por prefijo solo se expande cuando el token es de verdad la misma palabra:
      - un truncamiento de la forma completa ("impermeab", "sustit"), o
      - una forma flexionada que comparte una raíz larga con ella
        ("reparar", "bajantes", "sustituyendo").
    Antes bastaba con empezar por la clave, así que "reposicion",
    "replanteo" o "repicado" pasaban a "reparacion"; "bajo" y "baja" a
    "bajante"; "sustancia" a "sustitucion"; "imperfecciones" a
    "impermeabilizacion".
    """
    if token in ABBREVIATIONS:
        return ABBREVIATIONS[token]
    if token in _PREFIX_MATCH_STOPWORDS:
        return token
    for short, full in ABBREVIATIONS.items():
        if short in _PREFIX_MATCH_EXCLUDED:
            continue
        if len(token) < len(short) or not token.startswith(short):
            continue
        if full.startswith(token):
            return full
        min_shared = math.ceil(_INFLECTION_MIN_SHARED_RATIO * len(full))
        if _shared_prefix_len(token, full) >= min_shared:
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
