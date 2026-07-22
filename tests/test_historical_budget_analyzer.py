"""
Tests del analizador de presupuestos históricos.
"""

import json
from datetime import datetime
from pathlib import Path

from src.core.historical_budget_analyzer import HistoricalBudgetAnalyzer
from src.core import database
from src.core.repositories import (
    get_historical_budget_by_path,
    get_historical_partida,
    get_partida_features,
    insert_historical_partida,
    upsert_historical_budget,
)


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

    def test_analyzer_safe_json_dumps_handles_non_serializable_probe_values(self, tmp_path, monkeypatch):
        db_path = tmp_path / "datos_historical_nonserializable_probe.db"
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
        with database.get_connection() as _conn:
            pass

        excel_path = tmp_path / "demo_nonserializable_probe.xlsx"
        excel_path.write_text("placeholder", encoding="utf-8")

        analyzer = HistoricalBudgetAnalyzer()
        monkeypatch.setattr(
            analyzer.probe,
            "probe",
            lambda *_args, **_kwargs: {
                "is_compatible": True,
                "score": 18,
                "issues": [],
                "source_path": Path(excel_path),
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
                "diagnostics": {},
            },
        )

        result = analyzer.analyze_budget(str(excel_path), force_reanalyze=True)
        assert result["status"] == "processed"

        stored = get_historical_budget_by_path(str(excel_path))
        assert stored is not None
        diagnostics = json.loads(stored["probe_diagnostics_json"])
        assert diagnostics["source_path"].endswith("demo_nonserializable_probe.xlsx")

    def test_analyzer_keeps_probe_diagnostics_on_reader_error(self, tmp_path, monkeypatch):
        db_path = tmp_path / "datos_historical_reader_error_probe_diag.db"
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
        with database.get_connection() as _conn:
            pass

        excel_path = tmp_path / "demo_reader_error_probe_diag.xlsx"
        excel_path.write_text("placeholder", encoding="utf-8")

        analyzer = HistoricalBudgetAnalyzer()
        monkeypatch.setattr(
            analyzer.probe,
            "probe",
            lambda *_args, **_kwargs: {
                "is_compatible": True,
                "score": 20,
                "issues": [],
                "selected_sheet": "PTO",
            },
        )
        monkeypatch.setattr(
            analyzer.reader,
            "read",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("reader boom")),
        )

        result = analyzer.analyze_budget(str(excel_path), force_reanalyze=True)
        assert result["status"] == "error"

        stored = get_historical_budget_by_path(str(excel_path))
        assert stored is not None
        assert stored["analysis_status"] == "READ_ERROR"
        assert stored["probe_diagnostics_json"]
        diagnostics = json.loads(stored["probe_diagnostics_json"])
        assert diagnostics["is_compatible"] is True
        assert diagnostics["selected_sheet"] == "PTO"

    def test_reanalysis_preserves_manual_exclusion_when_budget_is_valid(self, tmp_path, monkeypatch):
        db_path = tmp_path / "datos_historical_manual_exclusion.db"
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
        with database.get_connection() as _conn:
            pass

        excel_path = tmp_path / "manual_excluded.xlsx"
        excel_path.write_text("placeholder", encoding="utf-8")
        mtime = datetime.fromtimestamp(excel_path.stat().st_mtime).isoformat()

        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(excel_path),
                "ruta_carpeta": str(tmp_path),
                "numero_proyecto": "001-26",
                "nombre_proyecto": "manual_excluded.xlsx",
                "fecha_modificacion_excel": mtime,
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "analysis_status": "VALID",
                "usable_for_learning": False,
                "learning_status": "EXCLUDED",
                "learning_status_source": "MANUAL",
                "learning_decision_reason": "Usuario no quiere usar este archivo.",
                "learning_decision_at": "2026-01-01 10:00:00",
            }
        )
        assert err is None
        assert budget_id is not None

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
                    {"numero": "1.1", "concepto": "Desmontaje bajante", "unidad": "ml", "cantidad": 1, "precio": 10, "importe": 10},
                    {"numero": "1.2", "concepto": "Instalacion bajante", "unidad": "ml", "cantidad": 1, "precio": 15, "importe": 15},
                ],
                "subtotal": 25.0,
                "total": 25.0,
                "diagnostics": {"selected_sheet": "PTO", "selected_sheet_index": 0, "detected_numero": "001-26", "numero_matches": True},
            },
        )

        result = analyzer.analyze_budget(str(excel_path), force_reanalyze=True)
        assert result["status"] == "processed"

        stored = get_historical_budget_by_path(str(excel_path))
        assert stored["analysis_status"] == "VALID"
        assert stored["learning_status"] == "EXCLUDED"
        assert stored["learning_status_source"] == "MANUAL"
        assert stored["usable_for_learning"] is False

    def test_reanalysis_does_not_preserve_manual_inclusion_when_budget_becomes_invalid(self, tmp_path, monkeypatch):
        db_path = tmp_path / "datos_historical_manual_inclusion_invalid.db"
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
        with database.get_connection() as _conn:
            pass

        excel_path = tmp_path / "manual_included_invalid.xlsx"
        excel_path.write_text("placeholder", encoding="utf-8")
        mtime = datetime.fromtimestamp(excel_path.stat().st_mtime).isoformat()

        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(excel_path),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "manual_included_invalid.xlsx",
                "fecha_modificacion_excel": mtime,
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "analysis_status": "VALID_WITH_WARNINGS",
                "usable_for_learning": True,
                "learning_status": "INCLUDED",
                "learning_status_source": "MANUAL",
                "learning_decision_reason": "Incluido tras revision.",
                "learning_decision_at": "2026-01-01 10:00:00",
            }
        )
        assert err is None
        assert budget_id is not None

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
                "partidas_detectadas": 2,
                "issues": [],
            },
        )
        monkeypatch.setattr(
            analyzer.reader,
            "read",
            lambda *_args, **_kwargs: {
                "cabecera": {"numero": "001-26", "obra": "Reparacion bajante", "fecha": "2026-01-01", "cliente": "Test"},
                "partidas": [
                    {"numero": "1.1", "concepto": "Desmontaje bajante", "unidad": "ml", "cantidad": 1, "precio": 0, "importe": 0},
                    {"numero": "1.2", "concepto": "Instalacion bajante", "unidad": "ml", "cantidad": 1, "precio": 0, "importe": 0},
                ],
                "subtotal": 0.0,
                "total": 0.0,
                "diagnostics": {"selected_sheet": "PTO", "selected_sheet_index": 0, "detected_numero": "001-26", "numero_matches": True},
            },
        )

        result = analyzer.analyze_budget(str(excel_path), force_reanalyze=True)
        assert result["status"] == "processed"

        stored = get_historical_budget_by_path(str(excel_path))
        assert stored["analysis_status"] == "EXCLUDED_INCOMPLETE_DATA"
        assert stored["learning_status"] == "NOT_ELIGIBLE"
        assert stored["learning_status_source"] == "AUTO"

    def _mock_valid_probe_and_reader(self, analyzer, monkeypatch):
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
                "partidas_detectadas": 2,
                "issues": [],
            },
        )
        monkeypatch.setattr(
            analyzer.reader,
            "read",
            lambda *_args, **_kwargs: {
                "cabecera": {"numero": "001-26", "obra": "Reparacion bajante", "fecha": "2026-01-01", "cliente": "Test"},
                "partidas": [
                    {"numero": "1.1", "concepto": "Desmontaje bajante", "unidad": "ml", "cantidad": 1, "precio": 10, "importe": 10},
                    {"numero": "1.2", "concepto": "Instalacion bajante", "unidad": "ml", "cantidad": 1, "precio": 15, "importe": 15},
                ],
                "subtotal": 25.0,
                "total": 25.0,
                "diagnostics": {"selected_sheet": "PTO", "selected_sheet_index": 0, "detected_numero": "001-26", "numero_matches": True},
            },
        )

    def test_own_final_budget_source_kind_stays_pending_review_even_when_valid(self, tmp_path, monkeypatch):
        """Fase 1, Tarea 4 (alcance reducido): el bucle de retroalimentación propio
        (presupuestos recién finalizados por la app) nunca debe auto-incluirse en
        la memoria de aprendizaje, aunque el análisis salga VALID."""
        db_path = tmp_path / "datos_historical_own_final_budget.db"
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
        with database.get_connection() as _conn:
            pass

        excel_path = tmp_path / "001-26 propio_finalizado.xlsx"
        excel_path.write_text("placeholder", encoding="utf-8")

        analyzer = HistoricalBudgetAnalyzer()
        self._mock_valid_probe_and_reader(analyzer, monkeypatch)

        result = analyzer.analyze_budget(
            str(excel_path), force_reanalyze=True, source_kind="own_final_budget"
        )
        assert result["status"] == "processed"

        stored = get_historical_budget_by_path(str(excel_path))
        assert stored["analysis_status"] == "VALID"
        assert stored["learning_status"] == "PENDING_REVIEW"
        assert stored["usable_for_learning"] is False
        assert stored["source_kind"] == "own_final_budget"

    def test_external_excel_source_kind_still_auto_includes_when_valid(self, tmp_path, monkeypatch):
        """El escaneo normal de un histórico externo real sigue auto-incluyendo
        presupuestos VALID, sin cambios de comportamiento (source_kind por defecto)."""
        db_path = tmp_path / "datos_historical_external_excel.db"
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
        with database.get_connection() as _conn:
            pass

        excel_path = tmp_path / "001-26 externo.xlsx"
        excel_path.write_text("placeholder", encoding="utf-8")

        analyzer = HistoricalBudgetAnalyzer()
        self._mock_valid_probe_and_reader(analyzer, monkeypatch)

        result = analyzer.analyze_budget(str(excel_path), force_reanalyze=True)
        assert result["status"] == "processed"

        stored = get_historical_budget_by_path(str(excel_path))
        assert stored["analysis_status"] == "VALID"
        assert stored["learning_status"] == "INCLUDED"
        assert stored["usable_for_learning"] is True
        assert stored["source_kind"] == "external_excel"


class TestRebuildPartidaFeatures:
    """Fase 2, Tarea 7: persistir la ficha derivada sin tocar el dato bruto."""

    def test_rebuild_partida_features_persists_primary_module_without_touching_raw_text(
        self, tmp_path, monkeypatch
    ):
        db_path = tmp_path / "datos_historical_features.db"
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))

        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / "features.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "features.xlsx",
                "fecha_modificacion_excel": datetime.now().isoformat(),
            }
        )
        assert err is None

        partida_id, err = insert_historical_partida(
            budget_id,
            {
                "concepto_original": "Picado y reparacion de fachada con grieta y mortero",
                "unidad": "m2",
            },
        )
        assert err is None

        before = get_historical_partida(partida_id)["concepto_original"]

        analyzer = HistoricalBudgetAnalyzer()
        count = analyzer.rebuild_partida_features([budget_id])
        assert count == 1

        after = get_historical_partida(partida_id)["concepto_original"]
        assert after == before

        features = get_partida_features(partida_id)
        assert features is not None
        assert features["primary_module_id"] == "fachada"
        assert features["unit"] == "m2"
        assert features["classifier_version"] == HistoricalBudgetAnalyzer.CLASSIFIER_VERSION

    def test_rebuild_partida_features_is_idempotent(self, tmp_path, monkeypatch):
        db_path = tmp_path / "datos_historical_features_idempotent.db"
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))

        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / "features_idem.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "features_idem.xlsx",
                "fecha_modificacion_excel": datetime.now().isoformat(),
            }
        )
        assert err is None
        partida_id, err = insert_historical_partida(
            budget_id, {"concepto_original": "Instalacion de bajante PVC", "unidad": "ml"}
        )
        assert err is None

        analyzer = HistoricalBudgetAnalyzer()
        first_count = analyzer.rebuild_partida_features([budget_id])
        second_count = analyzer.rebuild_partida_features([budget_id])
        assert first_count == second_count == 1

        with database.get_connection(read_only=True) as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM historical_partida_feature WHERE partida_id=?", (partida_id,)
            ).fetchone()[0]
        assert total == 1
