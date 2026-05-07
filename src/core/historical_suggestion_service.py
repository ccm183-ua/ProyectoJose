"""
Servicio de sugerencias históricas para nuevos presupuestos.
"""

from typing import Dict, List, Optional

from src.core import database
from src.core.historical_partida_classifier import HistoricalPartidaClassifier
from src.core.repositories import get_suggestion_patterns_by_modules
from src.core.work_type_normalizer import extract_work_signals


class HistoricalSuggestionService:
    """Genera módulos y partidas sugeridas desde el histórico persistido."""

    def __init__(self, classifier: Optional[HistoricalPartidaClassifier] = None):
        self.classifier = classifier or HistoricalPartidaClassifier()

    def suggest_for_project(self, project_data: Dict, user_description: str = "") -> Dict:
        text = " ".join(
            [
                str(project_data.get("tipo", "") or ""),
                str(project_data.get("nombre_obra", "") or ""),
                str(project_data.get("descripcion", "") or ""),
                str(user_description or ""),
            ]
        ).strip()

        detected_modules = self._detect_modules(text)
        module_names = [m["name"] for m in detected_modules]
        patterns = get_suggestion_patterns_by_modules(module_names)
        partidas = [self._pattern_to_partida(p) for p in patterns]
        partidas = [
            p for p in partidas
            if p.get("historical_frequency", 0) >= 2 and p.get("confidence", 0.0) >= 0.2
        ]
        stats = self._build_stats(module_names)

        confidence = 0.0
        if detected_modules:
            confidence = round(
                sum(m["confidence"] for m in detected_modules) / len(detected_modules), 2
            )

        result = {
            "source": "historical",
            "confidence": confidence,
            "detected_modules": detected_modules,
            "partidas": partidas,
            "stats": stats,
        }
        if not module_names:
            result["message"] = "No se han detectado módulos suficientes para sugerencias históricas."
        elif not partidas:
            result["message"] = "No hay patrones históricos con confianza/frecuencia suficientes."
        return result

    def _detect_modules(self, text: str) -> List[Dict]:
        classified = self.classifier.classify_text(text)
        signals = extract_work_signals(text)
        by_name = {row["module"]: row for row in classified}

        # Señales simples para no perder módulos frecuentes cuando el texto es breve.
        signal_boost = {
            "bajante": "sustitucion_bajante",
            "residuo": "gestion_residuos",
            "albanileria": "albanileria",
            "pintura": "pintura",
            "alicatado": "alicatado",
        }
        for signal in signals:
            module_name = signal_boost.get(signal)
            if not module_name:
                continue
            if module_name not in by_name:
                by_name[module_name] = {
                    "module": module_name,
                    "confidence": 0.6,
                    "source": "rules",
                }

        results = []
        for row in by_name.values():
            module_name = row["module"]
            conf = float(row.get("confidence") or 0)
            results.append(
                {
                    "name": module_name,
                    "label": module_name.replace("_", " ").title(),
                    "confidence": round(conf, 2),
                    "mandatory": conf >= 0.85,
                }
            )
        results.sort(key=lambda item: item["confidence"], reverse=True)
        return results

    @staticmethod
    def _pattern_to_partida(pattern: Dict) -> Dict:
        precio = pattern.get("precio_unitario_mediana")
        if precio is None:
            precio = pattern.get("precio_unitario_medio") or 0.0
        titulo = (pattern.get("titulo_sugerido") or pattern.get("concepto_normalizado") or "").upper()
        concepto = pattern.get("concepto_normalizado") or ""
        return {
            "pattern_id": pattern.get("id"),
            "titulo": titulo,
            "descripcion": pattern.get("descripcion_sugerida") or "",
            "concepto": concepto,
            "cantidad": 1.0,
            "unidad": pattern.get("unidad_habitual") or "ud",
            "precio_unitario": float(precio or 0.0),
            "module": pattern.get("module") or "",
            "confidence": float(pattern.get("confianza") or 0.0),
            "historical_frequency": int(pattern.get("frecuencia") or 0),
            "precio_min": float(pattern.get("precio_unitario_min") or 0.0),
            "precio_max": float(pattern.get("precio_unitario_max") or 0.0),
            "precio_mediana": float(pattern.get("precio_unitario_mediana") or 0.0),
        }

    @staticmethod
    def _build_stats(module_names: List[str]) -> Dict:
        if not module_names:
            return {"presupuestos_base": 0, "partidas_base": 0}
        placeholders = ",".join("?" for _ in module_names)
        with database.get_connection(read_only=True) as conn:
            cur_budgets = conn.execute(
                f"""SELECT COUNT(DISTINCT hp.historical_budget_id)
                    FROM historical_partida hp
                    JOIN historical_partida_module hpm ON hpm.partida_id = hp.id
                    JOIN execution_module em ON em.id = hpm.module_id
                    WHERE em.nombre IN ({placeholders})""",
                module_names,
            )
            cur_partidas = conn.execute(
                f"""SELECT COUNT(*)
                    FROM historical_partida hp
                    JOIN historical_partida_module hpm ON hpm.partida_id = hp.id
                    JOIN execution_module em ON em.id = hpm.module_id
                    WHERE em.nombre IN ({placeholders})""",
                module_names,
            )
            presupuestos_base = int((cur_budgets.fetchone() or [0])[0] or 0)
            partidas_base = int((cur_partidas.fetchone() or [0])[0] or 0)
        return {
            "presupuestos_base": presupuestos_base,
            "partidas_base": partidas_base,
        }

