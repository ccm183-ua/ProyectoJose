"""
Comparador determinista de compatibilidad entre dos fichas de partida
(Fase 3, Tarea 8). Sin LLM: reglas de exclusión primero, luego diferencias
sobre campos no críticos.

Niveles (ver docs/superpowers/plans/2026-07-22-historico-estructurado-y-cruce-fiable.md):
- exact: misma unidad, acción y sin diferencias en el resto -> puede sugerir precio.
- comparable: misma unidad/acción pero con diferencias en elemento/material/
  sistema/dimensiones/condiciones -> puede sugerir rango, con advertencia.
- related: al menos una de las dos líneas es compuesta -> antecedente, nunca precio.
- incompatible: distinta unidad o distinta acción -> se excluye.
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


def compare_partida_features(request: PartidaFeatures, evidence: PartidaFeatures) -> ComparisonResult:
    # Igual que accion/elemento/material: solo excluye si AMBAS unidades son
    # conocidas y distintas. Una request sin unidad concreta (p.ej. una
    # descripcion libre a nivel de proyecto) no debe descartar toda la
    # evidencia por comparar "" contra "m2".
    if request.unit and evidence.unit and request.unit != evidence.unit:
        return _incompatible("unit")

    if request.action and evidence.action and request.action != evidence.action:
        return _incompatible("action")

    if request.line_kind == "composite" or evidence.line_kind == "composite":
        return ComparisonResult(
            "related",
            0.0,
            (),
            ("línea compuesta: sirve de antecedente, nunca como precio exacto",),
        )

    differences = []
    if request.element and evidence.element and request.element != evidence.element:
        differences.append("element")
    if request.system and evidence.system and request.system != evidence.system:
        differences.append("system")
    if request.material and evidence.material and request.material != evidence.material:
        differences.append("material")
    if set(request.dimensions) != set(evidence.dimensions) and (request.dimensions or evidence.dimensions):
        differences.append("dimensions")

    condition_diff = set(request.conditions) ^ set(evidence.conditions)
    differences.extend(f"condition:{c}" for c in sorted(condition_diff))

    if not differences:
        return ComparisonResult("exact", 1.0, (), ("misma unidad, acción y sin diferencias detectadas",))

    return ComparisonResult(
        "comparable",
        0.6,
        tuple(differences),
        (f"diferencias detectadas: {', '.join(differences)}",),
    )
