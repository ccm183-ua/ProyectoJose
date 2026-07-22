"""
Fase 4, Tarea 12: modelo puro de procedencia por partida, probado sin
arrancar PySide6/QApplication (row_for_partida es una función de datos).
"""

from src.gui.partida_provenance_model import row_for_partida


def test_ai_draft_without_evidence_shows_no_comparable_evidence():
    row = row_for_partida({"source": "ai_completion", "evidence_level": None})
    assert row["Fuente"] == "IA — borrador"
    assert row["Rango histórico"] == "Sin evidencia privada comparable"
    assert row["Nivel"] == "Sin evidencia privada comparable"
    assert row["Diferencias"] == "—"


def test_historical_exact_evidence_shows_level_and_price():
    row = row_for_partida(
        {
            "source": "historical",
            "evidence_level": "exact",
            "evidence_precio_unitario": 50.0,
            "evidence_differences": [],
        }
    )
    assert row["Fuente"] == "Histórico"
    assert row["Nivel"] == "Exacto"
    assert row["Rango histórico"] == "50.00"
    assert row["Diferencias"] == "—"


def test_comparable_evidence_lists_differences():
    row = row_for_partida(
        {
            "source": "historical",
            "evidence_level": "comparable",
            "evidence_precio_unitario": 40.0,
            "evidence_differences": ["material", "condition:scaffolding"],
        }
    )
    assert row["Nivel"] == "Comparable"
    assert row["Diferencias"] == "material, condition:scaffolding"


def test_related_evidence_never_shows_a_price():
    row = row_for_partida(
        {
            "source": "historical",
            "evidence_level": "related",
            "evidence_precio_unitario": 999.0,
        }
    )
    assert row["Nivel"] == "Relacionado (sin precio)"
    assert row["Rango histórico"] == "Sin evidencia privada comparable"


def test_unknown_source_falls_back_to_raw_value():
    row = row_for_partida({"source": "algo_nuevo", "evidence_level": None})
    assert row["Fuente"] == "algo_nuevo"
