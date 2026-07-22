"""
Fase 3, Tarea 8: compatibilidad determinista entre dos fichas de partida.

compare_partida_features() decide si la evidencia histórica de una partida
puede sugerir precio (exact/comparable), servir solo de antecedente (related)
o queda excluida (incompatible). Reglas de exclusión ANTES de puntuar
(unidad, acción, línea compuesta): dos partidas con distinta unidad o acción
nunca son exact, y una línea compuesta nunca es exact/comparable (no se debe
copiar su precio, solo consultarla como antecedente).
"""

from src.core.historical_comparator import compare_partida_features
from src.core.historical_partida_features import PartidaFeatures


def _features(**overrides) -> PartidaFeatures:
    base = dict(
        action="repair",
        element="facade_render",
        system=None,
        unit="m2",
        material="mortar_r4",
        dimensions=(),
        conditions=(),
        line_kind="atomic",
        primary_module_id="fachada",
        secondary_module_ids=(),
        confidence=0.8,
        reasons=(),
    )
    base.update(overrides)
    return PartidaFeatures(**base)


def test_identical_features_are_exact():
    request = _features()
    evidence = _features()
    result = compare_partida_features(request, evidence)
    assert result.level == "exact"
    assert result.differences == ()


def test_different_unit_is_always_incompatible():
    request = _features(unit="m2")
    evidence = _features(unit="ml")
    result = compare_partida_features(request, evidence)
    assert result.level == "incompatible"
    assert "unit" in result.differences


def test_different_action_is_always_incompatible():
    request = _features(action="repair")
    evidence = _features(action="demolish")
    result = compare_partida_features(request, evidence)
    assert result.level == "incompatible"
    assert "action" in result.differences


def test_different_material_is_comparable_not_incompatible():
    request = _features(material="mortar_r4")
    evidence = _features(material="mortar")
    result = compare_partida_features(request, evidence)
    assert result.level == "comparable"
    assert "material" in result.differences


def test_different_conditions_are_reported_and_stay_comparable():
    request = _features(conditions=())
    evidence = _features(conditions=("scaffolding",))
    result = compare_partida_features(request, evidence)
    assert result.level == "comparable"
    assert result.differences == ("condition:scaffolding",)


def test_composite_line_is_always_related_never_exact_or_comparable():
    request = _features(line_kind="atomic")
    evidence = _features(line_kind="composite")
    result = compare_partida_features(request, evidence)
    assert result.level == "related"


def test_request_composite_line_is_also_related():
    request = _features(line_kind="composite")
    evidence = _features(line_kind="atomic")
    result = compare_partida_features(request, evidence)
    assert result.level == "related"


def test_missing_action_on_either_side_does_not_force_incompatible():
    """Una ficha sin acción detectada (vocabulario cerrado que no matcheo) no debe
    excluir automáticamente la comparación: solo un choque real de acciones
    conocidas descarta la evidencia."""
    request = _features(action=None)
    evidence = _features(action="repair")
    result = compare_partida_features(request, evidence)
    assert result.level != "incompatible"


def test_missing_unit_on_request_does_not_force_incompatible():
    """Una request sin unidad concreta (descripcion libre a nivel de proyecto)
    no debe descartar toda la evidencia por comparar '' contra 'm2'."""
    request = _features(unit="")
    evidence = _features(unit="m2")
    result = compare_partida_features(request, evidence)
    assert result.level != "incompatible"
