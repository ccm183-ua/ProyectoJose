"""
Tests del analizador de presupuestos históricos.
"""

from datetime import datetime

from src.core.historical_budget_analyzer import HistoricalBudgetAnalyzer
from src.core.repositories import upsert_historical_budget


class TestHistoricalBudgetAnalyzer:
    def test_analyzer_skips_unchanged_excel(self, tmp_path, monkeypatch):
        db_path = tmp_path / "datos_historical_test.db"
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))

        excel_path = tmp_path / "demo.xlsx"
        excel_path.write_text("placeholder", encoding="utf-8")
        mtime = datetime.fromtimestamp(excel_path.stat().st_mtime).isoformat()

        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(excel_path),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "demo.xlsx",
                "fecha_modificacion_excel": mtime,
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "num_partidas": 2,
                "error": "",
            }
        )
        assert err is None
        assert budget_id is not None

        analyzer = HistoricalBudgetAnalyzer()
        result = analyzer.analyze_budget(str(excel_path))
        assert result["status"] == "skipped"

    def test_analyzer_force_reanalyze_ignores_skip_cache(self, tmp_path, monkeypatch):
        db_path = tmp_path / "datos_historical_force_test.db"
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))

        excel_path = tmp_path / "demo_force.xlsx"
        excel_path.write_text("placeholder", encoding="utf-8")
        mtime = datetime.fromtimestamp(excel_path.stat().st_mtime).isoformat()

        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(excel_path),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "demo_force.xlsx",
                "fecha_modificacion_excel": mtime,
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "num_partidas": 1,
                "error": "",
            }
        )
        assert err is None
        assert budget_id is not None

        analyzer = HistoricalBudgetAnalyzer()
        monkeypatch.setattr(
            analyzer.reader,
            "read",
            lambda *_args, **_kwargs: {
                "cabecera": {"numero": "001-26", "obra": "Reparacion bajante", "fecha": "2026-01-01", "cliente": "Test"},
                "partidas": [
                    {"numero": "1.1", "concepto": "Desmontaje bajante", "unidad": "ml", "cantidad": 1, "precio": 10, "importe": 10}
                ],
                "total": 10.0,
            },
        )
        result = analyzer.analyze_budget(str(excel_path), force_reanalyze=True)
        assert result["status"] == "processed"
