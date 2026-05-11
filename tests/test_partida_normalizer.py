from src.core.partida_normalizer import normalize_partida_for_excel


def test_historical_multiline_concepto_original_splits_title_and_description():
    partida = {
        "concepto_original": "DESMONTAJE BAJANTE.\nDesmontaje manual con retirada a vertedero.",
        "unidad": "ml",
        "cantidad": "12",
        "precio_unitario": "18.5",
    }
    normalized = normalize_partida_for_excel(partida, source="historical")
    assert normalized["titulo"] == "DESMONTAJE BAJANTE."
    assert "retirada a vertedero" in normalized["descripcion"]
    assert normalized["source"] == "historical"


def test_historical_long_concept_uses_sentence_split_when_possible():
    partida = {
        "concepto": "ALICATADO PARED. Incluye suministro, colocacion y rejuntado.",
        "ud": "m2",
        "cantidad": 4,
        "precio": 42,
    }
    normalized = normalize_partida_for_excel(partida, source="historical")
    assert normalized["titulo"] == "ALICATADO PARED."
    assert normalized["descripcion"].startswith("Incluye")


def test_ai_title_and_description_are_preserved():
    partida = {
        "titulo": "PINTURA INTERIOR.",
        "descripcion": "Pintura plástica lavable en dos manos.",
        "unidad": "m2",
        "cantidad": 20,
        "precio_unitario": 8.5,
    }
    normalized = normalize_partida_for_excel(partida, source="ai_completion")
    assert normalized["titulo"] == "PINTURA INTERIOR."
    assert normalized["descripcion"] == "Pintura plástica lavable en dos manos."
    assert normalized["source"] == "ai_completion"


def test_alternative_keys_are_normalized():
    partida = {"concepto": "PRUEBA", "ud": "ud", "cantidad": "2", "precio_unitario": "7,5"}
    normalized = normalize_partida_for_excel(partida, source="historical")
    assert normalized["unidad"] == "ud"
    assert normalized["precio"] == 7.5
    assert normalized["precio_unitario"] == 7.5


def test_historical_not_all_text_inside_title_when_multiline():
    partida = {
        "concepto": "REPARACION BAJANTE.\nApertura de rozas.\nCierre y remates.",
        "cantidad": 1,
        "unidad": "ud",
        "precio": 100,
    }
    normalized = normalize_partida_for_excel(partida, source="historical")
    assert normalized["titulo"] == "REPARACION BAJANTE."
    assert normalized["descripcion"] == "Apertura de rozas.\nCierre y remates."


def test_multiline_title_with_empty_description_is_split():
    partida = {
        "titulo": "PINTURA PAREDES.\nAplicación de pintura plástica mate en paredes.",
        "descripcion": "",
        "unidad": "m2",
        "cantidad": 100,
        "precio_unitario": 8.5,
    }
    normalized = normalize_partida_for_excel(partida, source="historical")
    assert normalized["titulo"] == "PINTURA PAREDES."
    assert normalized["descripcion"].startswith("Aplicación de pintura")


def test_title_with_short_sentence_and_implicit_description_is_split():
    partida = {
        "titulo": "PINTURA PAREDES. Aplicación de pintura plástica mate en paredes.",
        "descripcion": "",
        "unidad": "m2",
        "cantidad": 100,
        "precio_unitario": 8.5,
    }
    normalized = normalize_partida_for_excel(partida, source="historical")
    assert normalized["titulo"] == "PINTURA PAREDES."
    assert normalized["descripcion"].startswith("Aplicación de pintura")


def test_short_title_with_empty_description_stays_as_title():
    partida = {
        "titulo": "PINTURA PAREDES.",
        "descripcion": "",
        "unidad": "m2",
        "cantidad": 100,
        "precio_unitario": 8.5,
    }
    normalized = normalize_partida_for_excel(partida, source="historical")
    assert normalized["titulo"] == "PINTURA PAREDES."
    assert normalized["descripcion"] == ""
