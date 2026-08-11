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
    # "quitar" (Decision 3, familia demolicion): verbo mayoritario de
    # retirada/demolicion en el historico real (1.418 lineas), sin falsos
    # positivos por substring verificados. "tirar" NO se anade: es
    # substring literal de "retirar" (13 lineas reales, sentido distinto -
    # retirada de escombros ya generados, no demolicion), y el motor de
    # coincidencia actual es por substring sin limite de palabra.
    # "derribar" (Decision 14, familia albanileria): verbo no cubierto por
    # "demoler". "quitan" (Decision 15): forma conjugada de "quitar" que
    # el infinitivo no cubre por substring. Ambos sin falsos positivos
    # verificados.
    # "desmontar" (Decision 16, familia impermeabilizacion): forma verbal
    # no cubierta por el sustantivo "desmontaje". "arranque" (Decision 17):
    # sinonimo de demoler/arrancar. Ambos sin falsos positivos verificados.
    ("demolish", ("demolicion", "demoler", "picado", "levantado", "desmontaje", "quitar", "derribar", "quitan", "desmontar", "arranque")),
    # "sustitucion" (Decision 21, familia carpinteria): 629 lineas reales,
    # 0 falsos positivos, sin ninguna accion propia pese a dar nombre al
    # modulo sustitucion_bajante. Se mapea a install (sustituir implica
    # instalar lo nuevo), consistente con las lineas de sustitucion_bajante
    # que ya evidencian precio via "colocacion" aparte.
    ("install", ("instalacion", "instalar", "colocacion", "colocar", "montaje", "sustitucion")),
    # "esmalte"/"esmaltado" y "barnizado"/"barnizar" (Decision 23, familia
    # carpinteria): variantes del mismo concepto de acabado/pintura.
    # "esmaltado" tiene un falso positivo minoritario aceptado
    # ("termoesmaltado", ficha tecnica de material, 3 de 34 lineas).
    # "imprimacion" (Decision 26, familia cerrajeria): a diferencia de
    # "lijado" (descartado por ser solo preparacion), el patron real
    # muestra que puede ser el trabajo completo por si solo (recubrimiento
    # anticorrosivo/de proteccion). 714 lineas, 0 falsos positivos, 76%
    # concentradas en pintura+cerrajeria con sentido siempre consistente.
    ("paint", ("pintura", "pintado", "pintar", "esmalte", "esmaltado", "barnizado", "barnizar", "imprimacion")),
    ("waterproof", ("impermeabilizacion", "impermeabilizar")),
    # Decision 18 (familia impermeabilizacion): "sellado"/"sellar" no
    # encajaban en ninguna accion existente. Repartido entre varios
    # modulos (impermeabilizacion, fachada, pintura, sustitucion_bajante)
    # pero significa siempre lo mismo -- a diferencia de "revestimiento"/
    # "galeria"/"formacion" (descartados en esta misma familia por ser
    # terminos genericos usados con sentidos distintos segun el contexto).
    ("seal", ("sellado", "sellar")),
    # Decision 24 (familia carpinteria): "enlucido"/"maestreado" son la
    # misma tecnica de acabado de paramentos (enlucir tras maestrear) --
    # mismo termino "render" que ya usa _SYSTEM_BY_ELEMENT para
    # facade_render. 0 falsos positivos verificados en 644+155 lineas.
    ("render", ("enlucido", "maestreado")),
    ("clean", ("limpieza", "limpiar")),
    ("rent", ("alquiler", "arrendamiento")),
)

# Entradas compuestas (p.ej. "revoco en fachada") antes que la genérica
# ("fachada") para no perder precisión cuando ambas aparecen.
_ELEMENT_SYNONYMS: _KeywordTable = (
    # Decision 4 (familia demolicion): "paramento vertical exterior" y
    # "enfoscado de cemento" describen la misma evidencia que "revoco de
    # fachada" sin usar la palabra "fachada" (patron mas repetido sin
    # ficha de toda la familia demolicion, frecuencia 8).
    ("facade_render", ("revoco en fachada", "revoco de fachada", "revoco fachada", "enfoscado fachada", "enfoscado de fachada", "paramento vertical exterior", "enfoscado de cemento")),
    ("facade", ("fachada",)),
    ("downspout", ("bajante",)),
    ("roof", ("cubierta", "tejado")),
    ("structure", ("estructura", "viga", "pilar", "zuncho")),
    ("door", ("puerta", "portal")),
    ("railing", ("barandilla", "pasamanos")),
    # Decision 5 (familia demolicion): "tabique" sin falsos positivos
    # verificados contra el historico real.
    ("partition_wall", ("tabique",)),
    # Decision 6 (familia demolicion): sin falsos positivos verificados.
    ("sanitary_ware", ("wc", "lavabo", "sanitario")),
    # Decision 7 (familia demolicion) + Decision 11 (familia alicatado):
    # "suelo" colisiona con "entresuelo" (6 lineas reales, es una
    # planta/piso, no el elemento) frente a 485 lineas reales genuinas de
    # suelo/pavimento -- se acepta ese riesgo medido, a diferencia de
    # "tirar" en la Decision 3. "solado"/"pavimento"/"baldosa" no tienen
    # ese problema (0 falsos positivos verificados).
    ("flooring", ("suelo", "solado", "pavimento", "baldosa")),
    # Decision 8 (familia demolicion): variantes singular/plural
    # necesarias porque el motor compara substrings completos, no por
    # token ("mueble de cocina" no es substring de "muebles de cocina").
    ("kitchen_furniture", ("mueble de cocina", "muebles de cocina", "electrodomestico")),
    # Decision 9 (familia alicatado): el hueco mas grande de toda la
    # revision -- "azulejo"/"alicatado" no tenian elemento propio pese a
    # ser el nucleo de esta familia. 0 falsos positivos verificados en
    # 577 (azulejo) y 1257 (alicatado) lineas reales.
    ("tile", ("azulejo", "alicatado")),
    # Decision 10 (familia alicatado): elemento facturable propio,
    # distinto de tile aunque a veces coincidan en la misma obra. 0 falsos
    # positivos verificados en 540 lineas reales.
    ("skirting", ("rodapie",)),
    # Decision 12 (familia albanileria): sin falsos positivos verificados
    # en 750 lineas reales.
    ("plaster", ("yeso",)),
    # Decision 13 (familia albanileria): canal abierto en pared/muro para
    # alojar instalaciones (electricidad, fontaneria) -- elemento
    # facturable propio, distinto de partition_wall. Sin falsos positivos
    # verificados en 262 lineas reales.
    ("wall_channel", ("roza",)),
    # Decision 19 (familia impermeabilizacion): chapa/flashing metalico de
    # remates. Un falso positivo minoritario aceptado ("rechapado" de
    # puertas de madera, sentido distinto) frente a 230 lineas reales.
    ("sheet_metal", ("chapa",)),
    # Decision 20 (familia impermeabilizacion): albardilla de cubricion de
    # muros -- elemento facturable propio. Sin falsos positivos
    # verificados en 21 lineas reales.
    ("coping", ("albardilla",)),
    # Decision 22 (familia carpinteria): mobiliario generico, distinto de
    # kitchen_furniture (mueble de cocina especificamente). Dos falsos
    # positivos menores aceptados (error de OCR "lmueble") de 693 lineas
    # reales.
    ("furniture", ("mueble",)),
    # Decision 25 (familia cerrajeria): elemento facturable propio, sin
    # falsos positivos verificados en 421 lineas reales.
    ("sink", ("fregadero",)),
    # Decision 27 (familia sustitucion_bajante): agrupa accesorios de
    # desagüe (rejilla, desague, cazoleta, sumidero) en un unico elemento
    # facturable. 0 falsos positivos verificados en 186+307+44+59 lineas.
    ("drain_fitting", ("rejilla", "desague", "cazoleta", "sumidero")),
    # Decision 28 (familia sustitucion_bajante): agrupa accesorios de
    # tuberia PVC (manguito, codo) -- tema recurrente aunque cada frase
    # concreta tenga frecuencia baja. 0 falsos positivos verificados en
    # 19+45 lineas.
    ("pipe_fitting", ("manguito", "codo")),
    # Decision 29 (familia sustitucion_bajante): elemento facturable
    # propio. Los "falsos positivos" de "electrobomba" siguen siendo una
    # bomba, no un error real. Sin falsos positivos verificados en 83
    # lineas.
    ("pump", ("bomba",)),
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
    "partition_wall": "partition_wall",
    "sanitary_ware": "sanitary_ware",
    "flooring": "flooring",
    "kitchen_furniture": "kitchen_furniture",
    "tile": "tile",
    "skirting": "skirting",
    "plaster": "plaster",
    "wall_channel": "wall_channel",
    "sheet_metal": "sheet_metal",
    "coping": "coping",
    "furniture": "furniture",
    "sink": "sink",
    "drain_fitting": "drain_fitting",
    "pipe_fitting": "pipe_fitting",
    "pump": "pump",
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
