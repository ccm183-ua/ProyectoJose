"""
Tests del servicio de sugerencias históricas.
"""

from datetime import datetime

from src.core.historical_pattern_builder import HistoricalPatternBuilder
from src.core.historical_suggestion_service import HistoricalSuggestionService
from src.core.repositories import (
    assign_partida_module,
    get_or_create_execution_module,
    insert_historical_partida,
    upsert_historical_budget,
)


class TestHistoricalSuggestionService:
    def test_suggestion_service_returns_expected_format(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_suggestion_test.db"))
        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / "hist.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "hist.xlsx",
                "fecha_modificacion_excel": datetime.now().isoformat(),
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "analysis_status": "VALID",
                "usable_for_learning": True,
                "learning_status": "INCLUDED",
            }
        )
        assert err is None

        module_id, module_err = get_or_create_execution_module("sustitucion_bajante")
        assert module_err is None
        for price in [18.5, 20.0]:
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
            assert assign_partida_module(partida_id, module_id, 0.9, "rules") is None

        HistoricalPatternBuilder().rebuild_patterns()

        result = HistoricalSuggestionService().suggest_for_project(
            {"tipo": "Reparación de bajante en patio interior"}
        )

        assert result["source"] == "historical"
        assert isinstance(result["detected_modules"], list)
        assert isinstance(result["partidas"], list)
        assert isinstance(result["stats"], dict)
        assert result["partidas"], "Debe devolver partidas sugeridas"

        partida = result["partidas"][0]
        expected_keys = {
            "titulo",
            "descripcion",
            "concepto",
            "cantidad",
            "unidad",
            "precio_unitario",
        }
        assert expected_keys.issubset(partida.keys())
        assert "pattern_build_run" in partida
        assert "pattern_source" in partida

    def test_stats_exclude_severe_warning_budgets(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_suggestion_severe.db"))
        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / "hist_severe.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "hist_severe.xlsx",
                "fecha_modificacion_excel": datetime.now().isoformat(),
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "warning_count": 1,
                "warnings": "SEVERE:Total de presupuesto cero o no detectado.",
            }
        )
        assert err is None

        module_id, module_err = get_or_create_execution_module("sustitucion_bajante")
        assert module_err is None
        partida_id, perr = insert_historical_partida(
            budget_id,
            {
                "titulo": "Desmontaje bajante existente",
                "concepto_original": "Desmontaje bajante existente",
                "concepto_normalizado": "desmontaje bajante existente",
                "unidad": "ml",
                "precio_unitario": 20.0,
                "cantidad": 1,
                "total_linea": 20.0,
            },
        )
        assert perr is None
        assert assign_partida_module(partida_id, module_id, 0.9, "rules") is None

        # No debe construir patrón al provenir de presupuesto con warning SEVERE.
        HistoricalPatternBuilder().rebuild_patterns()
        result = HistoricalSuggestionService().suggest_for_project(
            {"tipo": "Reparación de bajante en patio interior"}
        )
        assert result["stats"]["partidas_base"] == 0

    def test_detects_impermeabilizacion_module_from_text(self):
        result = HistoricalSuggestionService().suggest_for_project(
            {"tipo": "impermeabilización tejado entero"}
        )
        module_names = {m.get("name") for m in result.get("detected_modules", [])}
        assert "impermeabilizacion" in module_names
        assert result["failure_reason"] in {"NO_PATTERNS", "FILTERED_OUT", "OK"}

    def test_detects_carpinteria_module_from_text(self):
        result = HistoricalSuggestionService().suggest_for_project(
            {"tipo": "barnizado puerta entrada"}
        )
        module_names = {m.get("name") for m in result.get("detected_modules", [])}
        assert "carpinteria" in module_names

    def test_detects_hormigon_module_from_text(self):
        result = HistoricalSuggestionService().suggest_for_project(
            {"tipo": "dados hormigón parking"}
        )
        module_names = {m.get("name") for m in result.get("detected_modules", [])}
        assert "hormigon" in module_names

    def test_detects_fachada_module_from_text(self):
        result = HistoricalSuggestionService().suggest_for_project(
            {"tipo": "revisión fachadas"}
        )
        module_names = {m.get("name") for m in result.get("detected_modules", [])}
        assert "fachada" in module_names

    def test_empty_text_returns_clear_reason_and_diagnostics(self):
        result = HistoricalSuggestionService().suggest_for_project(
            {"tipo": "", "nombre_obra": "", "descripcion": ""},
            user_description="",
        )
        assert result["detected_modules"] == []
        assert result["input_text"] == ""
        assert result["normalized_text"] == ""
        assert result["detected_signals"] == []
        assert result["reason"] == (
            "No se han podido detectar módulos porque la descripción del trabajo está vacía o es demasiado genérica."
        )
        assert result["message"] == result["reason"]
        assert result["failure_reason"] == "NO_MODULES"
        assert result["patterns_found"] == 0
        assert result["patterns_after_filters"] == 0

    def test_real_case_imperm_cubierta_returns_detailed_no_patterns_reason(self):
        result = HistoricalSuggestionService().suggest_for_project({"tipo": "IMPERM CUBIERTA"})
        module_names = {m.get("name") for m in result.get("detected_modules", [])}
        assert "impermeabilizacion" in module_names
        assert result["failure_reason"] in {"NO_PATTERNS", "FILTERED_OUT", "OK"}
        if result["failure_reason"] == "NO_PATTERNS":
            assert "Impermeabilización/Cubierta" in result["message"]

    def test_real_case_rep_viga_atado_detects_structure_related_module(self):
        result = HistoricalSuggestionService().suggest_for_project({"tipo": "REP. VIGA ATADO PLANTA 12º"})
        module_names = {m.get("name") for m in result.get("detected_modules", [])}
        assert any(name in module_names for name in ("estructura", "hormigon", "albanileria"))
        assert result["failure_reason"] != "NO_MODULES"

    def test_real_case_rehabilitacion_de_edificio_is_too_generic(self):
        result = HistoricalSuggestionService().suggest_for_project({"tipo": "REHABILITACIÓN DE EDIFICIO"})
        assert result["failure_reason"] == "TOO_GENERIC"
        assert "demasiado general" in result["message"].lower()
