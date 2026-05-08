"""
Tests del analizador de presupuestos históricos.
"""

import json
from datetime import datetime

from src.core.historical_budget_analyzer import HistoricalBudgetAnalyzer
from src.core import database
from src.core.repositories import get_historical_budget_by_path, upsert_historical_budget


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

    def test_analyzer_persists_versioning_and_probe_diagnostics(self, tmp_path, monkeypatch):
        db_path = tmp_path / "datos_historical_versions_test.db"
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
        with database.get_connection() as _conn:
            pass

        excel_path = tmp_path / "demo_versions.xlsx"
        excel_path.write_text("placeholder", encoding="utf-8")

        analyzer = HistoricalBudgetAnalyzer()
        monkeypatch.setattr(
            analyzer.probe,
            "probe",
            lambda *_args, **_kwargs: {
                "is_compatible": True,
                "score": 24,
                "header_score": 12,
                "partida_score": 12,
                "selected_sheet": "PTO",
                "selected_sheet_index": 0,
                "expected_numero": "001-26",
                "detected_numero": "001-26",
                "numero_matches": True,
                "partidas_detectadas": 1,
                "issues": [],
            },
        )
        monkeypatch.setattr(
            analyzer.reader,
            "read",
            lambda *_args, **_kwargs: {
                "cabecera": {"numero": "001-26", "obra": "Reparacion bajante", "fecha": "2026-01-01", "cliente": "Test"},
                "partidas": [
                    {"numero": "1.1", "concepto": "Desmontaje bajante", "unidad": "ml", "cantidad": 1, "precio": 10, "importe": 10}
                ],
                "total": 10.0,
                "diagnostics": {"selected_sheet": "PTO", "selected_sheet_index": 0, "detected_numero": "001-26", "numero_matches": True},
            },
        )

        result = analyzer.analyze_budget(str(excel_path), force_reanalyze=True)
        assert result["status"] == "processed"

        stored = get_historical_budget_by_path(str(excel_path))
        assert stored is not None
        assert stored["analyzer_version"] == HistoricalBudgetAnalyzer.ANALYZER_VERSION
        assert stored["probe_version"] == HistoricalBudgetAnalyzer.PROBE_VERSION
        assert stored["reader_version"] == HistoricalBudgetAnalyzer.READER_VERSION
        assert stored["quality_rules_version"] == HistoricalBudgetAnalyzer.QUALITY_RULES_VERSION
        assert stored["classifier_version"] == HistoricalBudgetAnalyzer.CLASSIFIER_VERSION
        assert stored["probe_diagnostics_json"]
        diagnostics = json.loads(stored["probe_diagnostics_json"])
        assert diagnostics["is_compatible"] is True
        assert diagnostics["score"] == 24
