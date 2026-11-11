"""
Tests del cálculo determinista de importes/totales (H3): única fuente de
verdad para toda escritura canónica y para los adapters de Excel.
"""

from src.core.budget_math import IVA_RATE, calcular_importe_linea, calcular_totales


def test_calcular_importe_linea_redondea_a_dos_decimales():
    assert calcular_importe_linea(3, 10.005) == 30.02


def test_calcular_importe_linea_con_cantidad_o_precio_cero():
    assert calcular_importe_linea(0, 10) == 0.0
    assert calcular_importe_linea(5, 0) == 0.0


def test_calcular_importe_linea_con_valores_none_no_lanza():
    assert calcular_importe_linea(None, 10) == 0.0
    assert calcular_importe_linea(5, None) == 0.0


def test_calcular_importe_linea_con_cantidad_negativa():
    assert calcular_importe_linea(-2, 10) == -20.0


def test_calcular_totales_formula_estandar():
    totales = calcular_totales([100.0, 50.0])
    assert totales == {"subtotal": 150.0, "iva": 15.0, "total": 165.0}


def test_calcular_totales_usa_iva_rate_por_defecto():
    assert calcular_totales([100.0])["iva"] == round(100.0 * IVA_RATE, 2)


def test_calcular_totales_con_iva_rate_distinto():
    totales = calcular_totales([100.0], iva_rate=0.21)
    assert totales == {"subtotal": 100.0, "iva": 21.0, "total": 121.0}


def test_calcular_totales_con_lista_vacia():
    assert calcular_totales([]) == {"subtotal": 0.0, "iva": 0.0, "total": 0.0}


def test_calcular_totales_acumula_redondeos_de_muchas_lineas():
    importes = [calcular_importe_linea(3, 0.1) for _ in range(10)]
    totales = calcular_totales(importes)
    assert totales["subtotal"] == round(sum(importes), 2)
    assert totales["total"] == round(totales["subtotal"] + totales["iva"], 2)


# --- parse_decimal_es -------------------------------------------------------
import math

import pytest

from src.core.budget_math import parse_decimal_es


@pytest.mark.parametrize("raw,esperado", [
    (12, 12.0),
    (12.5, 12.5),
    ("12", 12.0),
    ("12,5", 12.5),
    ("12.5", 12.5),
    ("1.250,00", 1250.0),
    ("1.250.000", 1250000.0),
    ("1.250.000,75", 1250000.75),
    ("1,250.00", 1250.0),
    ("  1.250,00 € ", 1250.0),
    ("1 250,50", 1250.5),
    ("-3,5", -3.5),
])
def test_parse_decimal_es_acepta_formatos_habituales(raw, esperado):
    assert parse_decimal_es(raw) == pytest.approx(esperado)


@pytest.mark.parametrize("raw", ["", "abc", "nan", "inf", "-inf", None, "1,2,3,4.5", True, float("nan")])
def test_parse_decimal_es_rechaza_entradas_invalidas(raw):
    with pytest.raises((ValueError, TypeError)):
        parse_decimal_es(raw)


def test_to_float_del_normalizador_entiende_miles_espanoles():
    from src.core.partida_normalizer import _to_float

    assert _to_float("1.250,00") == 1250.0
    assert _to_float("nan", 1.0) == 1.0


def test_safe_number_de_ai_service_entiende_miles_espanoles():
    from src.core.ai_service import AIService

    svc = AIService.__new__(AIService)
    assert svc._safe_number("1.250,50") == 1250.5
    assert svc._safe_number("inf", 0) == 0
