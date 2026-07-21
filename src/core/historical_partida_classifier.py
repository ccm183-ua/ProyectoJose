"""
Clasificación de partidas históricas en módulos de ejecución.
"""

from typing import Dict, List

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
        "fachada",
        "fachadas",
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


class HistoricalPartidaClassifier:
    """Clasificador por reglas basado en palabras clave normalizadas."""

    def classify(self, partida: Dict) -> List[Dict]:
        text = self._compose_partida_text(partida)
        return self.classify_text(text)

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
