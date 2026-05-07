"""
Tests del constructor de patrones históricos.
"""

from datetime import datetime

from src.core import database
from src.core.historical_pattern_builder import HistoricalPatternBuilder
from src.core.repositories import (
    assign_partida_module,
    get_or_create_execution_module,
    insert_historical_partida,
    upsert_historical_budget,
)


class TestHistoricalPatternBuilder:
    def test_rebuild_patterns_calculates_stats(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_pattern_test.db"))

        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / "hist.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "hist.xlsx",
                "fecha_modificacion_excel": datetime.now().isoformat(),
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
            }
        )
        assert err is None
        module_id, module_err = get_or_create_execution_module("sustitucion_bajante")
        assert module_err is None
        assert module_id is not None

        for price in [10.0, 20.0, 30.0]:
            partida_id, perr = insert_historical_partida(
                budget_id,
                {
                    "titulo": "Desmontaje bajante existente",
                    "concepto_original": "Desmontaje bajante existente",
                    "concepto_normalizado": "desmontaje bajante existente",
                    "unidad": "ml",
                    "precio_unitario": price,
                    "cantidad": 1,
                    "total_linea": price,
                },
            )
            assert perr is None
            assign_err = assign_partida_module(partida_id, module_id, 0.9, "rules")
            assert assign_err is None

        result = HistoricalPatternBuilder().rebuild_patterns()
        assert result["patterns_inserted"] >= 1

        with database.get_connection(read_only=True) as conn:
            cur = conn.execute(
                """SELECT precio_unitario_medio, precio_unitario_mediana, precio_unitario_min,
                          precio_unitario_max, frecuencia, confianza
                   FROM suggested_partida_pattern
                   WHERE module_id = ? AND concepto_normalizado = ?""",
                (module_id, "desmontaje bajante existente"),
            )
            row = cur.fetchone()

        assert row is not None
        assert row[0] == 20.0
        assert row[1] == 20.0
        assert row[2] == 10.0
        assert row[3] == 30.0
        assert row[4] == 3
        assert row[5] == 0.3
