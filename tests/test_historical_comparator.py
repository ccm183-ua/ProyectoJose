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
        is_price_eligible=True,
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


def test_missing_action_on_either_side_is_related_not_incompatible():
    """Fixes Tarea 3: una ficha sin acción detectada no es un choque real (no
    'incompatible'), pero tampoco es evidencia limpia sin ese dato mínimo
    (por eso 'related', no 'exact'/'comparable')."""
    request = _features(action=None)
    evidence = _features(action="repair")
    result = compare_partida_features(request, evidence)
    assert result.level == "related"


def test_missing_unit_on_request_is_related_not_incompatible():
    """Fixes Tarea 3: una request sin unidad concreta (descripcion libre a
    nivel de proyecto) no es un choque real, pero unidad es un atributo
    mínimo obligatorio: sin ella, la evidencia queda 'related', nunca precio."""
    request = _features(unit="")
    evidence = _features(unit="m2")
    result = compare_partida_features(request, evidence)
    assert result.level == "related"


class TestStrictPreconditions:
    """Fixes histórico evidenciado, Tarea 3: el comparador no debe conceder
    exact/comparable por AUSENCIA de datos, solo por igualdad/diferencia real
    de datos conocidos. Contrato del diseño de reconducción: exact exige
    unidad, acción y elemento conocidos e iguales."""

    def test_two_completely_unknown_features_are_related_not_exact(self):
        unknown = _features(action=None, element=None, unit="m2", material=None, is_price_eligible=False)
        result = compare_partida_features(unknown, unknown)
        assert result.level == "related"

    def test_different_element_is_incompatible_not_comparable(self):
        """Cambio de contrato: antes 'element' distinto producia 'comparable';
        ahora element es un atributo CRITICO como unidad/accion."""
        repair_facade = _features(element="facade_render")
        repair_roof = _features(element="roof")
        result = compare_partida_features(repair_facade, repair_roof)
        assert result.level == "incompatible"

    def test_same_critical_attributes_different_material_is_comparable(self):
        repair_r4 = _features(material="mortar_r4")
        repair_generic = _features(material="mortar")
        result = compare_partida_features(repair_r4, repair_generic)
        assert result.level == "comparable"
        assert "material" in result.differences

    def test_same_critical_attributes_different_dimensions_is_comparable(self):
        repair_10cm = _features(dimensions=("10 cm",))
        repair_15cm = _features(dimensions=("15 cm",))
        result = compare_partida_features(repair_10cm, repair_15cm)
        assert result.level == "comparable"
        assert "dimensions" in result.differences

    def test_identical_full_features_are_exact(self):
        result = compare_partida_features(_features(), _features())
        assert result.level == "exact"

    def test_missing_element_on_evidence_is_related_not_exact(self):
        request = _features(element="facade_render")
        evidence = _features(element=None)
        result = compare_partida_features(request, evidence)
        assert result.level == "related"
