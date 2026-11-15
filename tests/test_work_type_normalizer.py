"""
Tests para normalización de tipo de obra y señales.
"""

from src.core.work_type_normalizer import (
    extract_work_signals,
    normalize_text,
    normalize_work_type,
)


class TestNormalizeText:
    def test_expande_abreviaturas_y_quita_tildes(self):
        value = normalize_text("REP. BAJANTE 8º C")
        assert "reparacion" in value
        assert "bajante" in value

    def test_cub_literal_sigue_expandiendo_a_cubierta(self):
        assert normalize_text("cub") == "cubierta"

    def test_cubricion_no_se_confunde_con_cubierta(self):
        """Decision 20 (familia impermeabilizacion, 2026-08-04): "cub" por
        prefijo capturaba "cubricion" (de albardilla), "cubrir", "cubo",
        "cubanita"... sin relacion con cubierta/tejado. Ver
        docs/criterios-clasificacion-partidas.md."""
        value = normalize_text("Albardilla ceramica para cubricion de muros")
        assert "cubricion" in value
        assert "cubierta" not in value

    def test_palabras_que_solo_empiezan_por_la_abreviatura_no_se_expanden(self):
        """Regresión: la expansión por prefijo convertía palabras reales."""
        value = normalize_text("Reposición de baldosa en planta baja, bajo replanteo")
        assert "reparacion" not in value
        assert "bajante" not in value
        assert value.split() == [
            "reposicion", "de", "baldosa", "en", "planta", "baja", "bajo", "replanteo",
        ]
        assert "sustitucion" not in normalize_text("sustancia")
        assert "impermeabilizacion" not in normalize_text("imperfecciones")
        assert normalize_text("repicado") == "repicado"

    def test_truncamientos_y_formas_flexionadas_si_se_expanden(self):
        assert normalize_text("impermeab sustit filtrac") == "impermeabilizacion sustitucion filtracion"
        assert normalize_text("bajantes") == "bajante"
        assert normalize_text("reparar") == "reparacion"
        assert normalize_text("sustituyendo") == "sustitucion"
        assert normalize_text("imperbeabilizacion") == "impermeabilizacion"


class TestNormalizeWorkType:
    def test_normalize_work_type(self):
        value = normalize_work_type("IMPERM. CUBIERTA")
        assert value == "impermeabilizacion cubierta"


class TestExtractWorkSignals:
    def test_extract_work_signals(self):
        signals = extract_work_signals("Reparación de bajante con gestión de residuos")
        assert "reparacion" in signals
        assert "bajante" in signals
        assert "residuo" in signals
