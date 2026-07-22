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
