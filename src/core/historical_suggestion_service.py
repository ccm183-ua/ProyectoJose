"""
Servicio de sugerencias históricas para nuevos presupuestos.
"""

from typing import Dict, List, Optional

from src.core import database
from src.core.historical_partida_classifier import HistoricalPartidaClassifier
from src.core.repositories import get_suggestion_patterns_by_modules
from src.core.work_type_normalizer import extract_work_signals, normalize_work_type


class HistoricalSuggestionService:
    """Genera módulos y partidas sugeridas desde el histórico persistido."""

    MIN_FREQUENCY = 2
    MIN_CONFIDENCE = 0.2

    def __init__(
        self,
        classifier: Optional[HistoricalPartidaClassifier] = None,
        enable_ai_fallback: bool = False,
        settings=None,
    ):
        self.classifier = classifier or HistoricalPartidaClassifier()
        self._enable_ai_fallback = enable_ai_fallback
        self._settings = settings
        self._ai_classifier = None

    def suggest_for_project(self, project_data: Dict, user_description: str = "") -> Dict:
        self._ensure_historical_schema()
        text = " ".join(
            [
                str(project_data.get("tipo", "") or ""),
                str(project_data.get("nombre_obra", "") or ""),
                str(project_data.get("descripcion", "") or ""),
                str(user_description or ""),
            ]
        ).strip()
        normalized_text = normalize_work_type(text)

        detected_signals = extract_work_signals(text)
        detected_modules = self._detect_modules(text, detected_signals)
        module_names = [m["name"] for m in detected_modules]
        patterns = get_suggestion_patterns_by_modules(module_names)
        partidas = [self._pattern_to_partida(p) for p in patterns]
        patterns_found = len(partidas)
        partidas = [
            p for p in partidas
            if p.get("historical_frequency", 0) >= self.MIN_FREQUENCY
            and p.get("confidence", 0.0) >= self.MIN_CONFIDENCE
        ]
        patterns_after_filters = len(partidas)
        stats = self._build_stats(module_names)

        confidence = 0.0
        if detected_modules:
            confidence = round(
                sum(m["confidence"] for m in detected_modules) / len(detected_modules), 2
            )

        result = {
            "source": "historical",
            "confidence": confidence,
            "input_text": text,
            "normalized_text": normalized_text,
            "detected_signals": detected_signals,
            "detected_modules": detected_modules,
            "patterns_found": patterns_found,
            "patterns_after_filters": patterns_after_filters,
            "min_frequency": self.MIN_FREQUENCY,
            "min_confidence": self.MIN_CONFIDENCE,
            "partidas": partidas,
            "stats": stats,
            "failure_reason": "OK",
        }
        if not module_names and self._has_generic_context_only(detected_signals):
            result["failure_reason"] = "TOO_GENERIC"
            result["reason"] = "Se ha detectado una actuación demasiado general y hace falta más detalle."
            result["message"] = (
                "Se ha detectado una actuación demasiado general. Añade detalle del elemento: "
                "fachada, cubierta, estructura, pintura, patios, etc."
            )
        elif not module_names:
            reason = "No se han podido detectar módulos porque la descripción del trabajo está vacía o es demasiado genérica."
            result["failure_reason"] = "NO_MODULES"
            result["reason"] = reason
            result["message"] = reason
        elif self._is_too_generic(module_names):
            result["failure_reason"] = "TOO_GENERIC"
            result["reason"] = "Se ha detectado una actuación demasiado general y hace falta más detalle."
            result["message"] = (
                "Se ha detectado una actuación demasiado general. Añade detalle del elemento: "
                "fachada, cubierta, estructura, pintura, patios, etc."
            )
        elif patterns_found == 0:
            result["failure_reason"] = "NO_PATTERNS"
            if "impermeabilizacion" in module_names:
                result["message"] = (
                    "Se ha detectado Impermeabilización/Cubierta, pero no hay patrones históricos suficientes en memoria. "
                    "Revisa que existan presupuestos incluidos y reconstruye patrones."
                )
            else:
                result["message"] = "Se detectaron módulos concretos, pero no hay patrones históricos suficientes."
        elif patterns_after_filters == 0:
            result["failure_reason"] = "FILTERED_OUT"
            result["message"] = (
                "Se han encontrado patrones, pero ninguno supera la frecuencia/confianza mínima configurada."
            )
        return result

    def _detect_modules(self, text: str, signals: Optional[List[str]] = None) -> List[Dict]:
        classified = self.classifier.classify_text(text)
        signals = signals or []
        by_name = {row["module"]: row for row in classified}

        # Fallback mínimo: cuando no hay módulos por reglas, usar señales del texto.
        signal_boost = {
            "bajante": "sustitucion_bajante",
            "residuo": "gestion_residuos",
            "escombro": "gestion_residuos",
            "albanileria": "albanileria",
            "pintura": "pintura",
            "alicatado": "alicatado",
            "impermeabilizacion": "impermeabilizacion",
            "cubierta": "impermeabilizacion",
            "filtracion": "impermeabilizacion",
            "fachada": "fachada",
            "garaje": "estructura",
            "hormigon": "estructura",
            "parking": "estructura",
            "pilar": "estructura",
            "refuerzo": "estructura",
            "viga": "estructura",
            "zuncho": "estructura",
        }
        if not by_name and signals:
            for signal in signals:
                module_name = signal_boost.get(signal)
                if not module_name:
                    continue
                if module_name not in by_name:
                    by_name[module_name] = {
                        "module": module_name,
                        "confidence": 0.6,
                        "source": "signals_fallback",
                    }

        # Red de seguridad IA (opt-in): si ni reglas ni señales detectaron módulos,
        # pedir a la IA que clasifique la descripción condensada del experto.
        if not by_name and self._enable_ai_fallback:
            for row in self._ai_detect_modules(text):
                module_name = row["module"]
                if module_name not in by_name:
                    by_name[module_name] = row

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

    def _ai_detect_modules(self, text: str) -> List[Dict]:
        """Clasificación de módulos por IA, perezosa y tolerante a fallos."""
        try:
            if self._ai_classifier is None:
                from src.core.ai_module_classifier import AIModuleClassifier

                self._ai_classifier = AIModuleClassifier(settings=self._settings)
            if not self._ai_classifier.is_available():
                return []
            return self._ai_classifier.classify_text(text)
        except Exception:
            return []

    @staticmethod
    def _is_too_generic(module_names: List[str]) -> bool:
        unique_modules = {m for m in module_names if m}
        if not unique_modules:
            return False
        if unique_modules == {"albanileria"}:
            return True
        return False

    @staticmethod
    def _has_generic_context_only(signals: List[str]) -> bool:
        signal_set = {s for s in signals if s}
        generic = {"rehabilitacion", "reparacion"}
        return bool(signal_set) and signal_set.issubset(generic)

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
            "pattern_build_run": pattern.get("pattern_build_run") or "",
            "pattern_source": pattern.get("pattern_source") or "",
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
                    JOIN historical_budget hb ON hb.id = hp.historical_budget_id
                    JOIN historical_partida_module hpm ON hpm.partida_id = hp.id
                    JOIN execution_module em ON em.id = hpm.module_id
                    WHERE em.nombre IN ({placeholders})
                      AND (
                          hb.usable_for_learning = 1
                          OR (
                              hb.analysis_status IS NULL
                              AND COALESCE(hb.warnings, '') NOT LIKE '%SEVERE:%'
                          )
                      )
                      AND (
                          hb.analysis_status IN ('VALID', 'VALID_WITH_WARNINGS')
                          OR hb.analysis_status IS NULL
                      )""",
                module_names,
            )
            cur_partidas = conn.execute(
                f"""SELECT COUNT(*)
                    FROM historical_partida hp
                    JOIN historical_budget hb ON hb.id = hp.historical_budget_id
                    JOIN historical_partida_module hpm ON hpm.partida_id = hp.id
                    JOIN execution_module em ON em.id = hpm.module_id
                    WHERE em.nombre IN ({placeholders})
                      AND (
                          hb.usable_for_learning = 1
                          OR (
                              hb.analysis_status IS NULL
                              AND COALESCE(hb.warnings, '') NOT LIKE '%SEVERE:%'
                          )
                      )
                      AND (
                          hb.analysis_status IN ('VALID', 'VALID_WITH_WARNINGS')
                          OR hb.analysis_status IS NULL
                      )""",
                module_names,
            )
            presupuestos_base = int((cur_budgets.fetchone() or [0])[0] or 0)
            partidas_base = int((cur_partidas.fetchone() or [0])[0] or 0)
        return {
            "presupuestos_base": presupuestos_base,
            "partidas_base": partidas_base,
        }

    @staticmethod
    def _ensure_historical_schema() -> None:
        """Garantiza que una base existente antigua tenga las tablas históricas."""
        conn = database.connect(read_only=False)
        conn.close()
