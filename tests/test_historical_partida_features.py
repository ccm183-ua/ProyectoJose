"""
Fase 2, Tarea 5: contrato de la ficha estructurada derivada de una partida.

extract_partida_features() no usa LLM: vocabulario cerrado por palabras clave
(ver docs/criterios-clasificacion-partidas.md) sobre el texto ya normalizado
por work_type_normalizer.normalize_text. El módulo principal y las etiquetas
secundarias reutilizan la salida de HistoricalPartidaClassifier.classify_text
tal cual (ordenada por confianza), sin volver a implementar esa clasificación.
"""

from src.core.historical_partida_classifier import HistoricalPartidaClassifier
from src.core.historical_partida_features import extract_partida_features

_classifier = HistoricalPartidaClassifier()


def test_composite_facade_repair_picks_fachada_as_primary_with_secondary_tags():
    text = "Picado y reparación de revoco en fachada con mortero R4"
    modules = _classifier.classify_text(text)

    features = extract_partida_features(text, "m2", modules)

    assert features.action == "repair"
    assert features.element == "facade_render"
    assert features.material == "mortar_r4"
    assert features.primary_module_id == "fachada"
    assert set(features.secondary_module_ids) == {"demolicion", "albanileria"}
    assert features.line_kind == "composite"
    assert features.unit == "m2"
    assert features.reasons


def test_auxiliary_equipment_rental_is_line_kind_auxiliary():
    text = "Alquiler de plataforma elevadora"
    modules = _classifier.classify_text(text)

    features = extract_partida_features(text, "ud", modules)

    assert features.line_kind == "auxiliary"
    assert features.primary_module_id == "medios_auxiliares"
    assert features.secondary_module_ids == ()


def test_no_module_match_yields_unknown_line_kind_and_no_primary_module():
    features = extract_partida_features("Texto sin ninguna palabra clave reconocible", "ud", [])

    assert features.line_kind == "unknown"
    assert features.primary_module_id is None
    assert features.secondary_module_ids == ()
    assert features.confidence == 0.0


def test_features_are_frozen():
    features = extract_partida_features("Fachada", "m2", [])
    try:
        features.action = "repair"
        assert False, "PartidaFeatures debe ser inmutable"
    except AttributeError:
        pass


class TestPriceEligibility:
    """Fixes histórico evidenciado, Tarea 2: ficha mínima comparable.

    is_price_eligible exige línea atómica con unidad/acción/elemento/módulo
    principal conocidos. Las líneas 'composite' se detectan por acciones o
    elementos REALMENTE distintos mencionados (no por número de módulos
    matcheados: un material incidental, como 'mortero' en una reparación de
    fachada, no debe convertir una línea atómica en compuesta).
    """

    def test_unknown_line_without_any_module_is_not_price_eligible(self):
        features = extract_partida_features("Trabajos varios", "m2", [])
        assert features.is_price_eligible is False
        assert features.line_kind == "unknown"

    def test_line_with_two_distinct_actions_is_composite_and_not_eligible(self):
        text = "Picado, mortero y pintura de fachada"
        modules = _classifier.classify_text(text)
        features = extract_partida_features(text, "m2", modules)
        assert features.line_kind == "composite"
        assert features.is_price_eligible is False

    def test_facade_render_repair_with_incidental_material_module_is_atomic_and_eligible(self):
        """Caso central de la Tarea 2: 'mortero' dispara tambien el modulo
        albanileria (via el clasificador de modulos), pero es solo el
        MATERIAL de una reparacion de fachada, una unica linea real."""
        text = "Reparación de revoco de fachada con mortero R4"
        modules = _classifier.classify_text(text)
        features = extract_partida_features(text, "m2", modules)
        assert features.action == "repair"
        assert features.element == "facade_render"
        assert features.material == "mortar_r4"
        assert features.line_kind == "atomic"
        assert features.is_price_eligible is True

    def test_missing_action_makes_line_not_eligible_even_if_atomic(self):
        """Una linea 'atomic' (un solo modulo) sin accion reconocida no debe
        ser elegible para precio: faltan atributos minimos."""
        features = extract_partida_features("Fachada en mal estado", "m2", [{"module": "fachada", "confidence": 0.6, "source": "rules"}])
        assert features.line_kind == "atomic"
        assert features.action is None
        assert features.is_price_eligible is False

    def test_auxiliary_line_is_never_price_eligible(self):
        text = "Alquiler de plataforma elevadora"
        modules = _classifier.classify_text(text)
        features = extract_partida_features(text, "ud", modules)
        assert features.line_kind == "auxiliary"
        assert features.is_price_eligible is False


class TestSystemAndDimensions:
    """Fixes histórico evidenciado, Tarea 2: sistema (vocabulario cerrado
    derivado del elemento) y dimensiones (regex sobre magnitudes explícitas)."""

    def test_facade_render_element_implies_render_system(self):
        text = "Reparación de revoco de fachada con mortero R4"
        modules = _classifier.classify_text(text)
        features = extract_partida_features(text, "m2", modules)
        assert features.system == "render"

    def test_downspout_element_implies_downspout_system(self):
        features = extract_partida_features(
            "Sustitucion de bajante de PVC", "ml", [{"module": "sustitucion_bajante", "confidence": 0.7, "source": "rules"}]
        )
        assert features.element == "downspout"
        assert features.system == "downspout"

    def test_dimension_is_extracted_from_free_text(self):
        features = extract_partida_features(
            "Junta de dilatacion de 15 mm de anchura", "m", []
        )
        assert "15 mm" in features.dimensions

    def test_no_dimension_present_yields_empty_tuple(self):
        features = extract_partida_features("Reparacion de fachada", "m2", [])
        assert features.dimensions == ()
