"""
Servicio de sugerencias históricas para nuevos presupuestos.
"""

import json
from dataclasses import dataclass, replace
from typing import Dict, List, Optional

from src.core import database
from src.core.historical_comparator import ComparisonResult, compare_partida_features
from src.core.historical_partida_classifier import HistoricalPartidaClassifier
from src.core.historical_partida_features import PartidaFeatures, extract_partida_features
from src.core.repositories import get_suggestion_patterns_by_modules
from src.core.work_type_normalizer import extract_work_signals, normalize_work_type

# Prioridad de nivel al ordenar evidencia: exact primero, related/incompatible
# al final (nunca deben usarse para sugerir precio).
_LEVEL_RANK = {"exact": 0, "comparable": 1, "related": 2, "incompatible": 3}
_PRICED_LEVELS = {"exact", "comparable"}


@dataclass(frozen=True)
class EvidenceCandidate:
    partida_id: int
    historical_budget_id: int
    precio_unitario: float
    source_date: str
    comparison: ComparisonResult

    def to_dict(self) -> Dict:
        return {
            "partida_id": self.partida_id,
            "historical_budget_id": self.historical_budget_id,
            "precio_unitario": self.precio_unitario,
            "source_date": self.source_date,
            "level": self.comparison.level,
            "score": self.comparison.score,
            "differences": list(self.comparison.differences),
            "reasons": list(self.comparison.reasons),
        }


def _row_to_features(row) -> PartidaFeatures:
    return PartidaFeatures(
        action=row[4],
        element=row[5],
        system=row[6],
        unit=row[7] or "",
        material=row[8],
        dimensions=tuple(json.loads(row[9])) if row[9] else (),
        conditions=tuple(json.loads(row[10])) if row[10] else (),
        line_kind=row[11] or "unknown",
        primary_module_id=row[12],
        secondary_module_ids=tuple(json.loads(row[13])) if row[13] else (),
        confidence=float(row[14] or 0.0),
        reasons=(),
    )


def find_comparable_evidence(request: PartidaFeatures) -> List[EvidenceCandidate]:
    """Compara `request` contra toda la evidencia real (historical_partida +
    su ficha derivada) del mismo módulo principal, en presupuestos aprobados.

    A diferencia de los patrones agregados por texto (Tarea 9), aquí se
    aplica el comparador determinista (Tarea 8) partida a partida, así que
    una línea 'related' (compuesta) puede aparecer como antecedente sin
    nunca colarse como precio exacto/comparable.
    """
    if not request.primary_module_id:
        return []
    with database.get_connection(read_only=True) as conn:
        rows = conn.execute(
            """SELECT hp.id, hp.historical_budget_id, hp.precio_unitario,
                      COALESCE(hb.fecha_presupuesto, hb.fecha_analisis, ''),
                      f.action, f.element, f.system, f.unit, f.material,
                      f.dimensions_json, f.conditions_json, f.line_kind,
                      f.primary_module_id, f.secondary_module_ids_json, f.confidence
               FROM historical_partida hp
               JOIN historical_partida_feature f ON f.partida_id = hp.id
               JOIN historical_budget hb ON hb.id = hp.historical_budget_id
               WHERE f.primary_module_id = ?
                 AND hb.learning_status = 'INCLUDED'
                 AND hb.analysis_status IN ('VALID', 'VALID_WITH_WARNINGS')
                 AND hp.precio_unitario IS NOT NULL
                 AND hp.precio_unitario > 0""",
            (request.primary_module_id,),
        ).fetchall()

    candidates = [
        EvidenceCandidate(
            partida_id=int(row[0]),
            historical_budget_id=int(row[1]),
            precio_unitario=float(row[2]),
            source_date=(row[3] or ""),
            comparison=compare_partida_features(request, _row_to_features(row)),
        )
        for row in rows
    ]
    # Sort estable en pasadas de la clave menos significativa a la mas
    # significativa: fecha reciente > mayor score > mejor nivel (exact primero).
    candidates.sort(key=lambda c: c.source_date, reverse=True)
    candidates.sort(key=lambda c: c.comparison.score, reverse=True)
    candidates.sort(key=lambda c: _LEVEL_RANK.get(c.comparison.level, 99))
    return candidates


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

        # Tarea 10: evidencia comparada por el comparador determinista (Tarea 8)
        # contra la ficha derivada real, no solo texto normalizado. Aditivo:
        # no sustituye 'partidas' (agregado por patrones, Tarea 9), solo añade
        # trazabilidad por línea individual para el módulo principal detectado.
        request_features = extract_partida_features(text, "", self.classifier.classify_text(text))
        if request_features.line_kind == "composite":
            # La exclusion de 'composite' del comparador es para no fiarse de
            # una LINEA HISTORICA compuesta como precio limpio; una descripcion
            # de proyecto libre que toca varias palabras clave a la vez no es
            # una linea compuesta real, es una consulta amplia. No forzarla a
            # 'related' aqui, o ninguna evidencia exact/comparable seria posible.
            request_features = replace(request_features, line_kind="atomic")
        evidence = find_comparable_evidence(request_features)
        evidence_report = [c.to_dict() for c in evidence]
        priced_evidence = [d for d in evidence_report if d["level"] in _PRICED_LEVELS]

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
            "evidence_report": evidence_report,
            "priced_evidence": priced_evidence,
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
