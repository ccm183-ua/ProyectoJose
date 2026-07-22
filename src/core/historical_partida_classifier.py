"""
Clasificación de partidas históricas en módulos de ejecución.
"""

from typing import Dict, List, Optional

from src.core.work_type_normalizer import normalize_text


MODULE_RULES = {
    "demolicion": [
        "demolicion",
        "demoler",
        "picado",
        "levantado",
        "desmontaje",
        "retirada",
        "apertura",
    ],
    "sustitucion_bajante": [
        "bajante",
        "pvc",
        "fecales",
        "pluviales",
        "manguito",
        "codo",
        "abrazadera",
    ],
    "albanileria": [
        "roza",
        "rozas",
        "mortero",
        "enfoscado",
        "tabique",
        "recibido",
        "albanileria",
        "cierre",
    ],
    "alicatado": [
        "alicatado",
        "azulejo",
        "ceramico",
        "rejuntado",
    ],
    "pintura": [
        "pintura",
        "pintado",
        "plastico",
        "revestimiento",
    ],
    "gestion_residuos": [
        "escombro",
        "vertedero",
        "residuo",
        "contenedor",
        "saca",
    ],
    "medios_auxiliares": [
        "andamio",
        "plataforma",
        "elevadora",
        "medio auxiliar",
        "proteccion",
        "seguridad",
        "tapado",
    ],
    "impermeabilizacion": [
        "impermeabilizacion",
        "imperm",
        "filtracion",
        "filtraciones",
        "gotera",
        "goteras",
        "cubierta",
        "tejado",
        "terraza",
        "tela asfaltica",
        "sumidero",
    ],
    "carpinteria": [
        "puerta",
        "pta",
        "portal",
        "madera",
        "barniz",
        "barnizado",
        "pasamanos",
    ],
    "cerrajeria": [
        "metalica",
        "cancela",
        "barandilla",
        "hierro",
        "acero",
        "cerrajeria",
    ],
    "estructura": [
        "viga",
        "vigas",
        "atado",
        "zuncho",
        "pilar",
        "pilares",
        "estructura",
        "estructural",
        "refuerzo",
        "hormigon",
        "dado",
        "dados",
        "parking",
        "garaje",
    ],
    "fachada": [
        # "fachadas" no esta como keyword aparte: normalize_text la expande a
        # "fachada" (abreviatura fachad->fachada), asi que contaba como un
        # segundo acierto duplicado e inflaba la confianza de este modulo
        # cada vez que aparecia la palabra (hallazgo Tarea 14, 2026-07-22).
        "fachada",
        "revision fachada",
        "grieta",
        "fisura",
        "enfoscado exterior",
    ],
}


MODULE_DESCRIPTIONS = {
    module_name: f"{module_name.replace('_', ' ').capitalize()}: {', '.join(keywords[:5])}."
    for module_name, keywords in MODULE_RULES.items()
}



# Orden de prioridad para desempatar entre candidatos con la misma confianza:
# la acción/elemento principal de una linea compuesta debe pesar mas que
# palabras sueltas de tareas auxiliares (p.ej. "picado" o "andamio" mencionados
# de pasada). Los modulos no listados aqui van al final del desempate.
PRIMARY_PRIORITY = (
    "demolicion",
    "estructura",
    "fachada",
    "impermeabilizacion",
    "sustitucion_bajante",
    "albanileria",
    "alicatado",
    "pintura",
    "carpinteria",
    "cerrajeria",
    "gestion_residuos",
    "medios_auxiliares",
)


# Módulos que casi siempre son incidentales a otra acción real (revisión
# humana Tarea 14, 2026-07-22: "DESMONTAJE BAJANTE...retirada...contenedor"
# se facturaba como demolición, no como gestión de residuos, aunque el texto
# mencionara más términos de residuos). Solo ganan como principal si son el
# único módulo detectado en la línea.
_INCIDENTAL_ONLY_MODULES = {"gestion_residuos"}

# Elemento semántico (historical_partida_features) -> módulo que debe ganar
# como principal si aparece entre los candidatos, aunque otro módulo tenga
# más confianza por coincidencias incidentales (fixes histórico evidenciado,
# Tarea 2, Step 4: "andamio"/"contenedor"/"picado" no deben pesar más que el
# elemento facturable real de la línea).
_ELEMENT_PRIMARY_OVERRIDE = {
    "facade_render": "fachada",
    "downspout": "sustitucion_bajante",
    "roof": "impermeabilizacion",
}


def pick_primary_module(candidates: List[Dict], element: Optional[str] = None) -> Dict:
    """Elige el módulo principal entre candidatos {module, confidence, ...}.

    Si `element` tiene un módulo semánticamente obligado (ver
    `_ELEMENT_PRIMARY_OVERRIDE`) y ese módulo está entre los candidatos, gana
    directamente sin mirar confianza/prioridad. Si no, desempata por
    PRIMARY_PRIORITY cuando dos módulos empatan en confianza. Compartida por
    HistoricalPartidaClassifier.classify() y
    historical_partida_features.extract_partida_features() para que ambos
    elijan siempre el mismo módulo principal de una línea compuesta.
    """
    forced_module = _ELEMENT_PRIMARY_OVERRIDE.get(element)
    if forced_module:
        forced = next((c for c in candidates if c["module"] == forced_module), None)
        if forced:
            return forced

    def priority_rank(module_name: str) -> int:
        try:
            return PRIMARY_PRIORITY.index(module_name)
        except ValueError:
            return len(PRIMARY_PRIORITY)

    non_incidental = [c for c in candidates if c["module"] not in _INCIDENTAL_ONLY_MODULES]
    pool = non_incidental or candidates
    return max(pool, key=lambda c: (c["confidence"], -priority_rank(c["module"])))


class HistoricalPartidaClassifier:
    """Clasificador por reglas basado en palabras clave normalizadas."""

    def classify(self, partida: Dict) -> Dict:
        """Clasifica una partida en un único módulo principal más etiquetas
        secundarias, para que una línea compuesta no duplique su precio en
        varios módulos (ver docs/criterios-clasificacion-partidas.md)."""
        text = self._compose_partida_text(partida)
        candidates = self.classify_text(text)
        if not candidates:
            return {
                "primary_module": None,
                "secondary_modules": [],
                "confidence": 0.0,
                "reasons": (),
            }

        primary = pick_primary_module(candidates)
        secondary = [c for c in candidates if c["module"] != primary["module"]]
        return {
            "primary_module": {"id": primary["module"], "confidence": primary["confidence"]},
            "secondary_modules": [
                {"id": c["module"], "confidence": c["confidence"]} for c in secondary
            ],
            "confidence": primary["confidence"],
            "reasons": (
                f"primary_module='{primary['module']}' entre candidatos "
                f"{[c['module'] for c in candidates]} (confianza + prioridad)",
            ),
        }

    def classify_text(self, text: str) -> List[Dict]:
        normalized = normalize_text(text)
        if not normalized:
            return []

        results: List[Dict] = []
        for module_name, keywords in MODULE_RULES.items():
            matches = self._count_matches(normalized, keywords)
            if matches == 0:
                continue
            confidence = self._calculate_confidence(matches, len(keywords))
            results.append(
                {
                    "module": module_name,
                    "confidence": confidence,
                    "source": "rules",
                }
            )
        results.sort(key=lambda row: row["confidence"], reverse=True)
        return results

    def _compose_partida_text(self, partida: Dict) -> str:
        parts = [
            partida.get("titulo", ""),
            partida.get("descripcion", ""),
            partida.get("concepto", ""),
            partida.get("concepto_original", ""),
            partida.get("capitulo", ""),
        ]
        return " ".join(str(item).strip() for item in parts if item).strip()

    @staticmethod
    def _count_matches(text: str, keywords: List[str]) -> int:
        count = 0
        for kw in keywords:
            normalized_kw = normalize_text(kw)
            if normalized_kw and normalized_kw in text:
                count += 1
        return count

    @staticmethod
    def _calculate_confidence(matches: int, total_keywords: int) -> float:
        if total_keywords <= 0:
            return 0.0
        score = 0.5 + (0.5 * (matches / total_keywords))
        return round(min(0.99, score), 2)
