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
