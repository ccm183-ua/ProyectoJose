"""Tests para el parser de números en español."""

import pytest

from src.utils.spanish_number_parser import (
    extract_total_from_asciende,
    parse_spanish_number,
)


class TestParseSpanishNumber:
    """Tests del parser de números en texto español."""

    def test_cero(self):
        assert parse_spanish_number("CERO") == 0.0

    def test_unidades(self):
        assert parse_spanish_number("UNO") == 1.0
        assert parse_spanish_number("DOS") == 2.0
        assert parse_spanish_number("NUEVE") == 9.0

    def test_decenas(self):
        assert parse_spanish_number("DIEZ") == 10.0
        assert parse_spanish_number("ONCE") == 11.0
        assert parse_spanish_number("QUINCE") == 15.0
        assert parse_spanish_number("VEINTE") == 20.0

    def test_compuestos_20(self):
        assert parse_spanish_number("VEINTIUNO") == 21.0
        assert parse_spanish_number("VEINTIDOS") == 22.0
        assert parse_spanish_number("VEINTIOCHO") == 28.0
        assert parse_spanish_number("VEINTINUEVE") == 29.0

    def test_decenas_con_y(self):
        assert parse_spanish_number("TREINTA Y UNO") == 31.0
        assert parse_spanish_number("CUARENTA Y CINCO") == 45.0
        assert parse_spanish_number("NOVENTA Y NUEVE") == 99.0

    def test_centenas(self):
        assert parse_spanish_number("CIEN") == 100.0
        assert parse_spanish_number("CIENTO CINCO") == 105.0
        assert parse_spanish_number("DOSCIENTOS") == 200.0
        assert parse_spanish_number("QUINIENTOS") == 500.0
        assert parse_spanish_number("NOVECIENTOS") == 900.0

    def test_centenas_compuestas(self):
        assert parse_spanish_number("CIENTO SESENTA Y CINCO") == 165.0
        assert parse_spanish_number("DOSCIENTOS VEINTE") == 220.0
        assert parse_spanish_number("TRESCIENTOS CUARENTA Y UNO") == 341.0
        assert parse_spanish_number("NOVECIENTOS NOVENTA Y NUEVE") == 999.0

    def test_miles(self):
        assert parse_spanish_number("MIL") == 1000.0
        assert parse_spanish_number("DOS MIL") == 2000.0
        assert parse_spanish_number("CINCO MIL") == 5000.0

    def test_miles_compuestos(self):
        assert parse_spanish_number("MIL CUATROCIENTOS OCHO") == 1408.0
        assert parse_spanish_number("DOS MIL CIENTO CUARENTA") == 2140.0
        assert parse_spanish_number("CINCO MIL CIENTO QUINCE") == 5115.0
        assert parse_spanish_number("NUEVE MIL NOVECIENTOS") == 9900.0

    def test_decenas_de_miles(self):
        assert parse_spanish_number("ONCE MIL DIECISEIS") == 11016.0
        assert parse_spanish_number("DIECISEIS MIL SEISCIENTOS TREINTA Y SIETE") == 16637.0
        assert parse_spanish_number("VEINTICUATRO MIL CIENTO SETENTA Y SEIS") == 24176.0

    def test_sesenta_y_un_mil(self):
        """Caso real: SESENTA Y UN MIL NOVECIENTOS OCHENTA Y OCHO."""
        assert parse_spanish_number(
            "SESENTA Y UN MIL NOVECIENTOS OCHENTA Y OCHO"
        ) == 61988.0

    def test_treinta_y_siete_mil(self):
        """Caso real: TREINTA Y SIETE MIL QUINIENTOS CUARENTA Y NUEVE."""
        assert parse_spanish_number(
            "TREINTA Y SIETE MIL QUINIENTOS CUARENTA Y NUEVE"
        ) == 37549.0

    def test_cincuenta_y_nueve_mil(self):
        assert parse_spanish_number(
            "CINCUENTA Y NUEVE MIL QUINIENTOS NOVENTA Y NUEVE"
        ) == 59599.0

    def test_con_tildes(self):
        """Las tildes se normalizan automáticamente."""
        assert parse_spanish_number("VEINTIÚN") == 21.0
        assert parse_spanish_number("DIECISÉIS") == 16.0

    def test_minusculas(self):
        assert parse_spanish_number("cinco mil ciento quince") == 5115.0

    def test_empty(self):
        assert parse_spanish_number("") is None
        assert parse_spanish_number(None) is None

    # ── Casos reales del diagnóstico ──────────────────────────────────

    def test_caso_real_novecientos_noventa(self):
        assert parse_spanish_number("NOVECIENTOS NOVENTA") == 990.0

    def test_caso_real_ciento_treinta_y_dos(self):
        assert parse_spanish_number("CIENTO TREINTA Y DOS") == 132.0

    def test_caso_real_cuatrocientos_doce(self):
        # 5-26: 412 (sin IVA) → pero texto dice 412
        assert parse_spanish_number("CUATROCIENTOS DOCE") == 412.0

    def test_caso_real_ocho_mil_doscientos_cincuenta(self):
        assert parse_spanish_number("OCHO MIL DOSCIENTOS CINCUENTA") == 8250.0


class TestExtractTotalFromAsciende:
    """Tests de extracción completa desde la frase 'Asciende...'."""

    def test_simple(self):
        text = (
            "Asciende el presupuesto de ejecución material a la expresada "
            "cantidad de CINCO MIL CIENTO QUINCE EUROS, I.V.A. INCLUIDO."
        )
        assert extract_total_from_asciende(text) == 5115.0

    def test_con_centimos(self):
        text = (
            "Asciende el presupuesto de ejecución material a la expresada "
            "cantidad de SEISCIENTOS CUARENTA Y TRES EUROS CON CINCUENTA "
            "CÉNTIMOS, I.V.A. INCLUIDO."
        )
        assert extract_total_from_asciende(text) == 643.50

    def test_centimos_con_sesenta_y_ocho(self):
        text = (
            "Asciende el presupuesto de ejecución material a la expresada "
            "cantidad de VEINTICUATRO MIL CIENTO SETENTA Y SEIS EUROS CON "
            "SESENTA Y OCHO CÉNTIMOS, I.V.A. INCLUIDO."
        )
        assert extract_total_from_asciende(text) == 24176.68

    def test_centimos_con_ochenta_y_ocho(self):
        text = (
            "Asciende el presupuesto de ejecución material a la expresada "
            "cantidad de TREINTA Y SIETE MIL QUINIENTOS CUARENTA Y NUEVE "
            "EUROS CON OCHENTA Y OCHO CÉNTIMOS, I.V.A. INCLUIDO."
        )
        assert extract_total_from_asciende(text) == 37549.88

    def test_centimos_veinte(self):
        text = (
            "Asciende el presupuesto de ejecución material a la expresada "
            "cantidad de SESENTA Y UN MIL NOVECIENTOS OCHENTA Y OCHO EUROS "
            "CON VEINTE CÉNTIMOS, I.V.A. INCLUIDO."
        )
        assert extract_total_from_asciende(text) == 61988.20

    def test_centimos_doce(self):
        text = (
            "Asciende el presupuesto de ejecución material a la expresada "
            "cantidad de CINCUENTA Y NUEVE MIL NOVECIENTOS NOVENTA Y DOS "
            "EUROS CON DOCE CÉNTIMOS, I.V.A. INCLUIDO."
        )
        assert extract_total_from_asciende(text) == 59992.12

    def test_centimos_veintidos(self):
        text = (
            "Asciende el presupuesto de ejecución material a la expresada "
            "cantidad de TREINTA Y NUEVE EUROS CON VEINTIDOS CÉNTIMOS, "
            "I.V.A. INCLUIDO, POR ML Y UD DE PARTIDA."
        )
        assert extract_total_from_asciende(text) == 39.22

    def test_sin_iva(self):
        text = (
            "Asciende el presupuesto de ejecución material a la expresada "
            "cantidad de CIENTO SESENTA Y CINCO EUROS."
        )
        assert extract_total_from_asciende(text) == 165.0

    def test_cero_euros(self):
        text = (
            "Asciende el presupuesto de ejecución material a la expresada "
            "cantidad de CERO EUROS."
        )
        assert extract_total_from_asciende(text) == 0.0

    def test_template_value(self):
        """Valor de la plantilla: DOS MIL CIENTO CUARENTA EUROS."""
        text = (
            "Asciende el presupuesto de ejecución material a la expresada "
            "cantidad de DOS MIL CIENTO CUARENTA EUROS."
        )
        assert extract_total_from_asciende(text) == 2140.0

    def test_centimos_cincuenta(self):
        text = (
            "Asciende el presupuesto de ejecución material a la expresada "
            "cantidad de MIL NOVECIENTOS CINCUENTA Y DOS EUROS CON CINCUENTA "
            "CÉNTIMOS, I.V.A. INCLUIDO."
        )
        assert extract_total_from_asciende(text) == 1952.50

    def test_none_si_no_hay_patron(self):
        assert extract_total_from_asciende("Texto sin patron") is None
        assert extract_total_from_asciende("") is None
        assert extract_total_from_asciende(None) is None

    def test_cuatrocientos_cuarenta_con_cincuenta(self):
        text = (
            "Asciende el presupuesto de ejecución material a la expresada "
            "cantidad de CUATROCIENTOS CUARENTA EUROS CON CINCUENTA "
            "CÉNTIMOS, I.V.A. INCLUIDO."
        )
        assert extract_total_from_asciende(text) == 440.50

    def test_centimos_ochenta(self):
        text = (
            "Asciende el presupuesto de ejecución material a la expresada "
            "cantidad de CINCUENTA Y NUEVE MIL QUINIENTOS NOVENTA Y NUEVE "
            "EUROS CON OCHENTA CÉNTIMOS."
        )
        assert extract_total_from_asciende(text) == 59599.80
