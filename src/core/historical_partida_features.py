"""
Ficha estructurada derivada de una partida histórica (Fase 2, Tarea 5).

Vocabulario cerrado por palabras clave sobre el texto normalizado, sin LLM
(ver docs/criterios-clasificacion-partidas.md para el listado completo y su
justificación). El módulo principal y las etiquetas secundarias reutilizan
tal cual la salida ya ordenada por confianza de
HistoricalPartidaClassifier.classify_text: esta función no reclasifica por
módulo, solo decide qué hacer con esa clasificación.
"""

import re
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple

from src.core.historical_partida_classifier import pick_primary_module
from src.core.work_type_normalizer import normalize_text

_DIMENSION_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:cm|mm|m)\b")

LineKind = Literal["atomic", "composite", "auxiliary", "unknown"]

_KeywordTable = Tuple[Tuple[str, Tuple[str, ...]], ...]

# Orden de prioridad: la primera categoría cuyo keyword aparece en el texto
# normalizado gana (no "todas las que matchean" como en la clasificación de
# módulos). "repair" antes que "demolish" porque "picado y reparación..."
# describe la intervención global, no el paso previo de picado.
_ACTION_SYNONYMS: _KeywordTable = (
    ("repair", ("reparacion", "reparar")),
    ("demolish", ("demolicion", "demoler", "picado", "levantado", "desmontaje")),
    ("install", ("instalacion", "instalar", "colocacion", "colocar", "montaje")),
    ("paint", ("pintura", "pintado", "pintar")),
    ("waterproof", ("impermeabilizacion", "impermeabilizar")),
    ("clean", ("limpieza", "limpiar")),
    ("rent", ("alquiler", "arrendamiento")),
)

# Entradas compuestas (p.ej. "revoco en fachada") antes que la genérica
# ("fachada") para no perder precisión cuando ambas aparecen.
_ELEMENT_SYNONYMS: _KeywordTable = (
    ("facade_render", ("revoco en fachada", "revoco de fachada", "revoco fachada", "enfoscado fachada", "enfoscado de fachada")),
    ("facade", ("fachada",)),
    ("downspout", ("bajante",)),
    ("roof", ("cubierta", "tejado")),
    ("structure", ("estructura", "viga", "pilar", "zuncho")),
    ("door", ("puerta", "portal")),
    ("railing", ("barandilla", "pasamanos")),
)

# Agrupa categorías de elemento que en realidad son el mismo elemento
# facturable a distinto nivel de detalle (facade_render es una fachada más
# específica, no un elemento aparte). Se usa para contar elementos REALMENTE
# distintos al decidir si una línea es compuesta (Tarea 2, fixes).
_ELEMENT_FAMILIES = {
    "facade_render": "facade",
    "facade": "facade",
    "downspout": "downspout",
    "roof": "roof",
    "structure": "structure",
    "door": "door",
    "railing": "railing",
}

# Sistema técnico implícito por elemento: vocabulario cerrado mínimo (Tarea 2,
# fixes). Ampliar solo cuando haga falta un elemento nuevo con sistema propio.
_SYSTEM_BY_ELEMENT = {
    "facade_render": "render",
    "downspout": "downspout",
    "roof": "roof_covering",
}

_MATERIAL_SYNONYMS: _KeywordTable = (
    ("mortar_r4", ("mortero r4",)),
    ("mortar", ("mortero",)),
    ("pvc", ("pvc",)),
    ("concrete", ("hormigon",)),
    ("steel", ("acero", "hierro", "metalica")),
    ("wood", ("madera",)),
)

_CONDITION_SYNONYMS: _KeywordTable = (
    ("scaffolding", ("andamio",)),
    ("elevated_platform", ("plataforma elevadora", "elevadora")),
    ("height_work", ("altura",)),
    ("difficult_access", ("dificil acceso", "acceso dificil", "sin acceso")),
    ("urgent", ("urgencia", "urgente")),
)

_AUXILIARY_MODULE_ID = "medios_auxiliares"


@dataclass(frozen=True)
class PartidaFeatures:
    action: Optional[str]
    element: Optional[str]
    system: Optional[str]
    unit: str
    material: Optional[str]
    dimensions: Tuple[str, ...]
    conditions: Tuple[str, ...]
    line_kind: LineKind
    primary_module_id: Optional[str]
    secondary_module_ids: Tuple[str, ...]
    confidence: float
    reasons: Tuple[str, ...]
    is_price_eligible: bool


def _match_first(normalized_text: str, table: _KeywordTable) -> Tuple[Optional[str], Optional[str]]:
    """Primera categoría de la tabla cuyo keyword aparece en el texto."""
    for category, keywords in table:
        for keyword in keywords:
            if keyword in normalized_text:
                return category, keyword
    return None, None


def _match_all(normalized_text: str, table: _KeywordTable) -> Tuple[str, ...]:
    return tuple(
        category
        for category, keywords in table
        if any(keyword in normalized_text for keyword in keywords)
    )


def _distinct_element_families(normalized_text: str) -> set:
    matched = _match_all(normalized_text, _ELEMENT_SYNONYMS)
    return {_ELEMENT_FAMILIES.get(cat, cat) for cat in matched}


def classify_line_kind(
    concept: str,
    action: Optional[str],
    element: Optional[str],
    modules: Optional[List[Dict]],
) -> LineKind:
    """Decide si una línea es atómica, compuesta, auxiliar o desconocida.

    No cuenta módulos matcheados (un material incidental como "mortero" en
    una reparación de fachada dispara también el módulo `albanileria`, pero
    sigue siendo una única línea real): cuenta ACCIONES y ELEMENTOS
    realmente distintos mencionados en el texto. Dos acciones o dos familias
    de elemento -> compuesta. Ver Tarea 2 de fixes histórico evidenciado.
    """
    candidates = modules or []
    if not candidates:
        return "unknown"

    normalized = normalize_text(concept)
    distinct_actions = set(_match_all(normalized, _ACTION_SYNONYMS))
    distinct_elements = _distinct_element_families(normalized)
    if len(distinct_actions) >= 2 or len(distinct_elements) >= 2:
        return "composite"

    primary_module_id = pick_primary_module(candidates, element=element)["module"]
    if primary_module_id == _AUXILIARY_MODULE_ID:
        return "auxiliary"
    return "atomic"


def extract_partida_features(concept: str, unit: str, modules: List[Dict]) -> PartidaFeatures:
    normalized = normalize_text(concept)
    reasons: List[str] = []

    action, action_kw = _match_first(normalized, _ACTION_SYNONYMS)
    if action:
        reasons.append(f"action='{action}' por keyword '{action_kw}'")

    element, element_kw = _match_first(normalized, _ELEMENT_SYNONYMS)
    if element:
        reasons.append(f"element='{element}' por keyword '{element_kw}'")

    system = _SYSTEM_BY_ELEMENT.get(element)

    material, material_kw = _match_first(normalized, _MATERIAL_SYNONYMS)
    if material:
        reasons.append(f"material='{material}' por keyword '{material_kw}'")

    # Sobre el texto en minúsculas SIN normalizar del todo: normalize_text
    # quita comas/puntos y rompería "15,5 mm" en "15" + "5 mm".
    dimensions = tuple(_DIMENSION_RE.findall((concept or "").lower()))
    if dimensions:
        reasons.append(f"dimensions={dimensions}")

    conditions = _match_all(normalized, _CONDITION_SYNONYMS)
    if conditions:
        reasons.append(f"conditions={conditions}")

    candidates = modules or []
    if candidates:
        primary = pick_primary_module(candidates, element=element)
        primary_module_id = primary["module"]
        secondary_module_ids = tuple(
            c["module"] for c in candidates if c["module"] != primary_module_id
        )
        confidence = float(primary.get("confidence", 0.0))
        reasons.append(
            f"primary_module_id='{primary_module_id}' (confianza clasificador {confidence:.2f})"
        )
    else:
        primary_module_id = None
        secondary_module_ids = ()
        confidence = 0.0

    line_kind = classify_line_kind(concept, action, element, candidates)

    is_price_eligible = (
        line_kind == "atomic"
        and bool(unit)
        and bool(action)
        and bool(element)
        and primary_module_id is not None
    )

    return PartidaFeatures(
        action=action,
        element=element,
        system=system,
        unit=unit,
        material=material,
        dimensions=dimensions,
        conditions=conditions,
        line_kind=line_kind,
        primary_module_id=primary_module_id,
        secondary_module_ids=secondary_module_ids,
        confidence=confidence,
        reasons=tuple(reasons),
        is_price_eligible=is_price_eligible,
    )
