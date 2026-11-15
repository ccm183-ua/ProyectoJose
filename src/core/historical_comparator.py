"""
Comparador determinista de compatibilidad entre dos fichas de partida
(Fase 3, Tarea 8; endurecido en fixes histórico evidenciado, Tarea 3). Sin
LLM: precondiciones de datos mínimos primero, luego igualdad de atributos
críticos, luego diferencias sobre campos no críticos.

Niveles (ver docs/superpowers/specs/2026-07-22-reconduccion-historico-evidenciado-design.md):
- exact: unidad, acción y elemento conocidos e idénticos, ambas líneas
  atómicas y sin diferencias en el resto -> puede sugerir precio.
- comparable: mismos unidad/acción/elemento (críticos), pero con diferencias
  en sistema/material/dimensiones/condiciones -> puede sugerir rango, con
  advertencia.
- related: falta algún atributo mínimo (unidad/acción/elemento) en cualquiera
  de las dos fichas, o alguna de las dos líneas no es atómica -> antecedente
  consultable, nunca precio. Una ficha incompleta NO es "probablemente
  exacta": es evidencia insuficiente, no se premia la ausencia de datos.
- incompatible: unidad, acción o elemento CONOCIDOS pero distintos -> se
  excluye explícitamente.
"""

from dataclasses import dataclass
from typing import Literal, Tuple

from src.core.historical_partida_features import PartidaFeatures

ComparisonLevel = Literal["exact", "comparable", "related", "incompatible"]


@dataclass(frozen=True)
class ComparisonResult:
    level: ComparisonLevel
    score: float
    differences: Tuple[str, ...]
    reasons: Tuple[str, ...]


def _incompatible(field: str) -> ComparisonResult:
    return ComparisonResult("incompatible", 0.0, (field,), (f"'{field}' distinto entre request y evidencia",))


def _related(reason: str) -> ComparisonResult:
    return ComparisonResult("related", 0.0, (), (reason,))


def compare_partida_features(request: PartidaFeatures, evidence: PartidaFeatures) -> ComparisonResult:
    # Precondición: sin unidad, acción y elemento conocidos en AMBAS fichas,
    # no hay evidencia limpia posible. Related, no exact/comparable: la
    # ausencia de datos no debe leerse como "coincide por defecto".
    if not all(
        (request.unit, request.action, request.element, evidence.unit, evidence.action, evidence.element)
    ):
        return _related("atributos mínimos incompletos (unidad, acción o elemento)")

    # Atributos críticos: deben ser IDÉNTICOS, no solo "ambos conocidos".
    # Element ya no degrada a 'comparable': una fachada y una cubierta no son
    # la misma evidencia aunque compartan unidad y acción.
    if request.unit != evidence.unit:
        return _incompatible("unit")
    if request.action != evidence.action:
        return _incompatible("action")
    if request.element != evidence.element:
        return _incompatible("element")

    # Líneas no atómicas (compuestas, auxiliares, desconocidas) nunca sirven
    # de precio limpio aunque coincidan en los atributos críticos.
    if request.line_kind != "atomic" or evidence.line_kind != "atomic":
        return _related("línea no atómica")

    differences = []
    if request.system and evidence.system and request.system != evidence.system:
        differences.append("system")
    if request.material and evidence.material and request.material != evidence.material:
        differences.append("material")
    if set(request.dimensions) != set(evidence.dimensions) and (request.dimensions or evidence.dimensions):
        differences.append("dimensions")

    condition_diff = set(request.conditions) ^ set(evidence.conditions)
    differences.extend(f"condition:{c}" for c in sorted(condition_diff))

    if not differences:
        return ComparisonResult(
            "exact", 1.0, (), ("misma unidad, acción, elemento y sin diferencias detectadas",)
        )

    return ComparisonResult(
        "comparable",
        0.6,
        tuple(differences),
        (f"diferencias detectadas: {', '.join(differences)}",),
    )
