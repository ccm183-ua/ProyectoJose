"""
Orquestador unificado de creación de presupuestos con IA.

Pipeline completo — un único punto de entrada para el cliente:
  descripción libre (voz o texto)
       ↓
  1. HistoricalSuggestionService — busca partidas en el histórico
       ↓
  2. Análisis de cobertura — módulos cubiertos vs. módulos gap
       ↓
  3a. Partidas históricas con confianza suficiente → output directo (source='historical')
  3b. Módulos sin cobertura → BudgetGenerator con IA (source='ai_completion')
       ↓
  4. Merge final con etiquetas de source por partida
"""

import logging
from typing import Dict, List, Optional, Tuple

from src.core.budget_generator import BudgetGenerator
from src.core.historical_suggestion_service import HistoricalSuggestionService
from src.core.settings import Settings

logger = logging.getLogger(__name__)

# Partidas históricas que superen ambos umbrales van directas al presupuesto sin pasar por IA.
HISTORICAL_CONFIDENCE_THRESHOLD = 0.60
HISTORICAL_FREQUENCY_THRESHOLD = 2


class BudgetOrchestrator:
    """
    Punto de entrada único para la creación de presupuestos con IA.

    El cliente describe la obra libremente (texto o voz dictada). El orquestador
    decide internamente qué partidas vienen del histórico y cuáles genera la IA,
    sin que el usuario elija entre caminos.

    Resultado siempre tiene campo 'source' por partida (mismo vocabulario que
    normalize_partida_for_excel y el resto de servicios de IA):
      - 'historical'    → precio y concepto reales de obras anteriores
      - 'ai_completion' → generado por IA, requiere revisión rápida
    """

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or Settings()
        self._suggestion_service = HistoricalSuggestionService(
            enable_ai_fallback=True,
            settings=self._settings,
        )
        self._generator = BudgetGenerator(settings=self._settings)

    def generate(
        self,
        descripcion_libre: str,
        datos_proyecto: Optional[Dict] = None,
        plantilla: Optional[Dict] = None,
    ) -> Dict:
        """
        Genera un presupuesto completo a partir de una descripción libre.

        Args:
            descripcion_libre: Texto en lenguaje natural; puede venir de STT.
            datos_proyecto: Datos opcionales del proyecto (localidad, cliente, etc.).
            plantilla: Plantilla de referencia opcional para la generación IA.

        Returns:
            {
                'partidas': List[Dict],   # Cada partida tiene campo 'source'
                'source': str,            # 'orquestado'|'historico'|'ia'|'error'
                'error': str | None,
                'cobertura': {
                    'modulos_historico': List[str],
                    'modulos_ia': List[str],
                    'partidas_historicas': int,
                    'partidas_ia': int,
                    'historical_confidence': float,
                    'failure_reason': str,
                }
            }
        """
        try:
            return self._generate(descripcion_libre, datos_proyecto, plantilla)
        except Exception as exc:
            logger.exception("Fallo inesperado generando presupuesto")
            return {
                "partidas": [],
                "source": "error",
                "error": f"Error inesperado al generar el presupuesto: {exc}",
                "cobertura": {
                    "modulos_historico": [],
                    "modulos_ia": [],
                    "partidas_historicas": 0,
                    "partidas_ia": 0,
                    "historical_confidence": 0.0,
                    "failure_reason": "UNEXPECTED_ERROR",
                },
            }

    def _generate(
        self,
        descripcion_libre: str,
        datos_proyecto: Optional[Dict],
        plantilla: Optional[Dict],
    ) -> Dict:
        datos_proyecto = datos_proyecto or {}

        project_data_for_history = {
            "tipo": datos_proyecto.get("tipo_obra", ""),
            "descripcion": descripcion_libre,
        }
        project_data_for_history.update(datos_proyecto)

        # Paso 1 — consultar histórico
        historical_result = self._suggestion_service.suggest_for_project(
            project_data=project_data_for_history,
            user_description=descripcion_libre,
        )

        # Paso 2 — separar partidas por nivel de cobertura
        partidas_historicas, modulos_cubiertos, modulos_gap = self._split_coverage(
            historical_result
        )

        tipo_obra = datos_proyecto.get("tipo_obra", "") or descripcion_libre[:80]
        partidas_ia: List[Dict] = []
        error_ia: Optional[str] = None

        # Paso 3a — IA solo para módulos sin cobertura histórica suficiente
        if modulos_gap:
            ia_result = self._generator.generate_for_gap_modules(
                tipo_obra=tipo_obra,
                descripcion=descripcion_libre,
                gap_modules=modulos_gap,
                datos_proyecto=datos_proyecto,
                historical_context=historical_result,
                plantilla=plantilla,
            )
            partidas_ia = ia_result.get("partidas", [])
            error_ia = ia_result.get("error")
            for p in partidas_ia:
                p["source"] = "ai_completion"

        # Paso 3b — sin histórico ni módulos detectados: IA completa como fallback
        elif not partidas_historicas:
            logger.info(
                "Sin cobertura histórica para '%s', generando con IA completa.",
                descripcion_libre[:60],
            )
            ia_result = self._generator.generate(
                tipo_obra=tipo_obra,
                descripcion=descripcion_libre,
                plantilla=plantilla,
                datos_proyecto=datos_proyecto,
                historical_context=(
                    historical_result
                    if historical_result.get("detected_modules")
                    else None
                ),
            )
            partidas_ia = ia_result.get("partidas", [])
            error_ia = ia_result.get("error")
            for p in partidas_ia:
                p["source"] = "ai_completion"

        # Paso 4 — merge
        todas_partidas = partidas_historicas + partidas_ia

        if partidas_historicas and partidas_ia:
            source = "orquestado"
        elif partidas_historicas:
            source = "historico"
        elif partidas_ia:
            source = "ia"
        else:
            source = "error"

        return {
            "partidas": todas_partidas,
            "source": source,
            "error": error_ia if not todas_partidas else None,
            "cobertura": {
                "modulos_historico": modulos_cubiertos,
                "modulos_ia": modulos_gap,
                "partidas_historicas": len(partidas_historicas),
                "partidas_ia": len(partidas_ia),
                "historical_confidence": historical_result.get("confidence", 0.0),
                "failure_reason": historical_result.get("failure_reason", "OK"),
            },
        }

    def _split_coverage(
        self, historical_result: Dict
    ) -> Tuple[List[Dict], List[str], List[str]]:
        """
        Divide las partidas históricas en dos grupos:
        - partidas_ok: confianza y frecuencia suficientes → van directas al presupuesto
        - modulos_gap: módulos detectados sin cobertura suficiente → pasan a la IA

        Returns:
            (partidas_ok, modulos_cubiertos, modulos_gap)
        """
        all_historical = historical_result.get("partidas", []) or []
        detected_modules = {
            m["name"]
            for m in (historical_result.get("detected_modules") or [])
        }

        partidas_ok: List[Dict] = []
        modulos_con_partidas: set = set()

        for p in all_historical:
            confianza = float(p.get("confidence", 0.0) or 0.0)
            frecuencia = int(p.get("historical_frequency", 0) or 0)
            if (
                confianza >= HISTORICAL_CONFIDENCE_THRESHOLD
                and frecuencia >= HISTORICAL_FREQUENCY_THRESHOLD
            ):
                partida = dict(p)
                partida["source"] = "historical"
                partidas_ok.append(partida)
                modulo = p.get("module", "")
                if modulo:
                    modulos_con_partidas.add(modulo)

        modulos_gap = sorted(detected_modules - modulos_con_partidas)
        modulos_cubiertos = sorted(modulos_con_partidas)

        return partidas_ok, modulos_cubiertos, modulos_gap
