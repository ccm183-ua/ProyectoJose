from src.core.historical_suggestions_dedupe import (
    dedupe_historical_partidas,
    dedupe_merged_review_partidas,
)


def test_dedupe_identical_suggestions_keeps_one():
    partidas = [
        {
            "concepto": "REVESTIMIENTO DECORATIVO EN PARAMENTO VERTICAL.",
            "unidad": "m2",
            "precio_unitario": 45.0,
            "confidence": 0.7,
            "historical_frequency": 5,
        },
        {
            "concepto": "REVESTIMIENTO DECORATIVO EN PARAMENTO VERTICAL.",
            "unidad": "m2",
            "precio_unitario": 45.0,
            "confidence": 0.5,
            "historical_frequency": 3,
        },
    ]
    out, removed = dedupe_historical_partidas(partidas)
    assert len(out) == 1
    assert removed == 1
    assert out[0]["confidence"] == 0.7


def test_dedupe_keeps_higher_confidence():
    partidas = [
        {"concepto": "PICADO DE ENFOSCADO.", "unidad": "m2", "precio_unitario": 12.0, "confidence": 0.5, "historical_frequency": 10},
        {"concepto": "PICADO DE ENFOSCADO.", "unidad": "m2", "precio_unitario": 12.0, "confidence": 0.9, "historical_frequency": 2},
    ]
    out, removed = dedupe_historical_partidas(partidas)
    assert len(out) == 1
    assert out[0]["confidence"] == 0.9


def test_dedupe_different_prices_not_merged():
    partidas = [
        {"concepto": "MISMO TEXTO", "unidad": "ud", "precio_unitario": 10.0, "confidence": 0.8, "historical_frequency": 1},
        {"concepto": "MISMO TEXTO", "unidad": "ud", "precio_unitario": 20.0, "confidence": 0.8, "historical_frequency": 1},
    ]
    out, removed = dedupe_historical_partidas(partidas)
    assert len(out) == 2
    assert removed == 0


def test_dedupe_similar_same_module_and_close_price_keeps_one():
    partidas = [
        {
            "module": "mod-a",
            "concepto": "REVESTIMIENTO DECORATIVO EN FACHADA CON MORTERO TIPO A",
            "unidad": "m2",
            "precio_unitario": 45.0,
            "confidence": 0.9,
            "historical_frequency": 8,
        },
        {
            "module": "mod-a",
            "concepto": "REVESTIMIENTO DECORATIVO EN FACHADA CON MORTERO TIPO B",
            "unidad": "m2",
            "precio_unitario": 45.5,
            "confidence": 0.5,
            "historical_frequency": 2,
        },
    ]
    out, removed = dedupe_historical_partidas(partidas)
    assert len(out) == 1
    assert removed == 1
    assert out[0]["confidence"] == 0.9


def test_merge_review_prefers_historical_on_same_key():
    hist = [
        {
            "titulo": "PARTIDA X.",
            "descripcion": "Desc hist",
            "unidad": "m2",
            "precio_unitario": 10.0,
            "confidence": 0.5,
            "historical_frequency": 2,
        }
    ]
    ai = [
        {
            "titulo": "PARTIDA X.",
            "descripcion": "Desc IA",
            "unidad": "m2",
            "precio_unitario": 10.0,
            "confidence": 0.99,
            "historical_frequency": 0,
        }
    ]
    h2, a2, removed = dedupe_merged_review_partidas(hist, ai)
    assert removed == 1
    assert len(h2) == 1
    assert len(a2) == 0
