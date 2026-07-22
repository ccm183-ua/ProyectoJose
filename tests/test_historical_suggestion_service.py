"""
Tests del servicio de sugerencias históricas.
"""

import sqlite3
from datetime import datetime

from src.core.historical_pattern_builder import HistoricalPatternBuilder
from src.core.historical_suggestion_service import HistoricalSuggestionService
from src.core.repositories import (
    assign_partida_module,
    get_or_create_execution_module,
    insert_historical_partida,
    upsert_historical_budget,
    upsert_partida_features,
)


def _mark_atomic_primary(partida_id: int, module_name: str) -> None:
    """Ficha derivada mínima (Fase 2) que _load_groups() exige desde la Tarea 9."""
    err = upsert_partida_features(
        partida_id,
        {
            "action": None, "element": None, "system": None, "unit": "",
            "material": None, "dimensions": (), "conditions": (),
            "line_kind": "atomic", "primary_module_id": module_name,
            "secondary_module_ids": (), "confidence": 0.9, "reasons": (),
            "classifier_version": "test",
        },
    )
    assert err is None


def _mark_features(partida_id: int, **overrides) -> None:
    """Ficha derivada con campos concretos, para probar el comparador
    (Fase 3, Tarea 10) contra evidencia real."""
    base = {
        "action": None, "element": None, "system": None, "unit": "",
        "material": None, "dimensions": (), "conditions": (),
        "line_kind": "atomic", "primary_module_id": None,
        "secondary_module_ids": (), "confidence": 0.9, "reasons": (),
        "classifier_version": "test",
    }
    base.update(overrides)
    assert upsert_partida_features(partida_id, base) is None


class TestHistoricalSuggestionService:
    def test_suggestion_service_initializes_missing_historical_schema(self, tmp_path, monkeypatch):
        db_path = tmp_path / "legacy_without_historical_tables.db"
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE legacy_marker (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))

        result = HistoricalSuggestionService().suggest_for_project(
            {"tipo": "reparacion de bajante en patio"}
        )

        assert result["source"] == "historical"
        assert result["failure_reason"] in {"NO_PATTERNS", "FILTERED_OUT", "OK"}

        conn = sqlite3.connect(db_path)
        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='suggested_partida_pattern'"
            )
            assert cur.fetchone() is not None
        finally:
            conn.close()

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
            _mark_atomic_primary(partida_id, "sustitucion_bajante")

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

    def test_detects_estructura_from_hormigon_context(self):
        result = HistoricalSuggestionService().suggest_for_project(
            {"tipo": "dados hormigón parking"}
        )
        module_names = {m.get("name") for m in result.get("detected_modules", [])}
        assert "estructura" in module_names
        assert "hormigon" not in module_names

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
        assert "estructura" in module_names
        assert "reparacion" not in module_names
        assert "hormigon" not in module_names
        assert result["failure_reason"] != "NO_MODULES"

    def test_real_case_rehabilitacion_de_edificio_is_too_generic(self):
        result = HistoricalSuggestionService().suggest_for_project({"tipo": "REHABILITACIÓN DE EDIFICIO"})
        assert result["failure_reason"] == "TOO_GENERIC"
        assert "demasiado general" in result["message"].lower()
        module_names = {m.get("name") for m in result.get("detected_modules", [])}
        assert "rehabilitacion" not in module_names


class TestFindComparableEvidence:
    """Fase 3, Tarea 10: aplicar el comparador (Tarea 8) a la evidencia real
    del módulo principal, en vez de solo texto normalizado. La evidencia
    'related' (líneas compuestas) nunca debe rellenar precio."""

    def _seed_budget(self, tmp_path, name: str) -> int:
        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / name),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": name,
                "fecha_modificacion_excel": datetime.now().isoformat(),
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "analysis_status": "VALID",
                "usable_for_learning": True,
                "learning_status": "INCLUDED",
            }
        )
        assert err is None
        return budget_id

    def test_exact_evidence_prices_the_suggestion(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_evidence_exact.db"))
        budget_id = self._seed_budget(tmp_path, "exacto.xlsx")

        partida_id, perr = insert_historical_partida(
            budget_id,
            {
                "concepto_original": "Reparacion revoco fachada mortero R4",
                "unidad": "m2",
                "precio_unitario": 50.0,
                "cantidad": 1,
                "total_linea": 50.0,
            },
        )
        assert perr is None
        _mark_features(
            partida_id,
            action="repair", element="facade_render", unit="m2", material="mortar_r4",
            line_kind="atomic", primary_module_id="fachada",
        )

        result = HistoricalSuggestionService().suggest_for_project(
            {"tipo": "Reparar revoco fachada con mortero R4"}
        )

        assert result["evidence_report"], "debe encontrar evidencia"
        assert result["evidence_report"][0]["level"] == "exact"
        assert result["evidence_report"][0]["precio_unitario"] == 50.0
        assert all(item["level"] != "related" for item in result["priced_evidence"])

    def test_composite_evidence_is_related_and_never_priced(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_evidence_composite.db"))
        budget_id = self._seed_budget(tmp_path, "compuesta.xlsx")

        partida_id, perr = insert_historical_partida(
            budget_id,
            {
                "concepto_original": "Picado y reparacion de fachada con mortero",
                "unidad": "m2",
                "precio_unitario": 999.0,
                "cantidad": 1,
                "total_linea": 999.0,
            },
        )
        assert perr is None
        _mark_features(
            partida_id,
            action="repair", element="facade_render", unit="m2", material="mortar_r4",
            line_kind="composite", primary_module_id="fachada",
            secondary_module_ids=("demolicion",),
        )

        result = HistoricalSuggestionService().suggest_for_project(
            {"tipo": "Reparar revoco fachada con mortero R4"}
        )

        assert result["evidence_report"]
        assert result["evidence_report"][0]["level"] == "related"
        assert result["priced_evidence"] == []

    def test_different_material_is_comparable_and_still_priced(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_evidence_comparable.db"))
        budget_id = self._seed_budget(tmp_path, "comparable.xlsx")

        partida_id, perr = insert_historical_partida(
            budget_id,
            {
                "concepto_original": "Reparacion revoco fachada mortero generico",
                "unidad": "m2",
                "precio_unitario": 40.0,
                "cantidad": 1,
                "total_linea": 40.0,
            },
        )
        assert perr is None
        _mark_features(
            partida_id,
            action="repair", element="facade_render", unit="m2", material="mortar",
            line_kind="atomic", primary_module_id="fachada",
        )

        result = HistoricalSuggestionService().suggest_for_project(
            {"tipo": "Reparar revoco fachada con mortero R4"}
        )

        assert result["evidence_report"][0]["level"] == "comparable"
        assert result["priced_evidence"], "comparable tambien debe poder sugerir precio"

    def test_no_primary_module_detected_returns_empty_evidence(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_evidence_none.db"))
        result = HistoricalSuggestionService().suggest_for_project(
            {"tipo": "Texto sin ninguna palabra clave reconocible"}
        )
        assert result["evidence_report"] == []
        assert result["priced_evidence"] == []


class TestPricedPartidas:
    """Fixes histórico evidenciado, Tarea 4: priced_partidas es la única
    fuente legítima de precio histórico aplicable al borrador. Un patrón
    textual (Tarea 9, clave 'partidas') puede seguir existiendo como índice,
    pero sin evidencia apta priced_partidas debe quedar vacío."""

    def _seed_budget(self, tmp_path, name: str) -> int:
        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / name),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": name,
                "fecha_modificacion_excel": datetime.now().isoformat(),
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "analysis_status": "VALID",
                "usable_for_learning": True,
                "learning_status": "INCLUDED",
            }
        )
        assert err is None
        return budget_id

    def test_no_evidence_yields_empty_priced_partidas_even_if_pattern_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "no_evidence.db"))
        result = HistoricalSuggestionService().suggest_for_project({}, "Reparación de fachada")
        assert result["priced_partidas"] == []

    def test_exact_evidence_produces_a_priced_partida_with_source_and_ids(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "priced_exact.db"))
        budget_id = self._seed_budget(tmp_path, "exacto.xlsx")
        partida_id, perr = insert_historical_partida(
            budget_id,
            {
                "concepto_original": "Reparacion revoco fachada mortero R4",
                "unidad": "m2",
                "precio_unitario": 50.0,
                "cantidad": 1,
                "total_linea": 50.0,
            },
        )
        assert perr is None
        _mark_features(
            partida_id,
            action="repair", element="facade_render", unit="m2", material="mortar_r4",
            line_kind="atomic", primary_module_id="fachada",
        )

        result = HistoricalSuggestionService().suggest_for_project(
            {}, "Reparación de revoco de fachada con mortero R4"
        )

        assert len(result["priced_partidas"]) == 1
        priced = result["priced_partidas"][0]
        assert priced["evidence_level"] == "exact"
        assert priced["source"] == "historical_exact"
        assert priced["precio_unitario"] == 50.0
        assert priced["evidence_budget_ids"] == [budget_id]
        assert priced["evidence_partida_ids"] == [partida_id]
        assert priced["module"] == "fachada"
        assert priced["unidad"] == "m2"
        assert priced["concepto"] == "Reparacion revoco fachada mortero R4"

    def test_related_evidence_never_appears_in_priced_partidas(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "priced_related.db"))
        budget_id = self._seed_budget(tmp_path, "compuesta.xlsx")
        partida_id, perr = insert_historical_partida(
            budget_id,
            {
                "concepto_original": "Picado y reparacion de fachada con mortero",
                "unidad": "m2",
                "precio_unitario": 999.0,
                "cantidad": 1,
                "total_linea": 999.0,
            },
        )
        assert perr is None
        _mark_features(
            partida_id,
            action="repair", element="facade_render", unit="m2", material="mortar_r4",
            line_kind="composite", primary_module_id="fachada",
            secondary_module_ids=("demolicion",),
        )

        result = HistoricalSuggestionService().suggest_for_project(
            {}, "Reparación de revoco de fachada con mortero R4"
        )
        assert result["priced_partidas"] == []

    def test_two_exact_sources_are_grouped_with_median_and_both_ids(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "priced_grouped.db"))
        budget_1 = self._seed_budget(tmp_path, "a.xlsx")
        budget_2 = self._seed_budget(tmp_path, "b.xlsx")
        partida_1, err1 = insert_historical_partida(
            budget_1,
            {"concepto_original": "Reparacion revoco fachada mortero R4", "unidad": "m2",
             "precio_unitario": 40.0, "cantidad": 1, "total_linea": 40.0},
        )
        partida_2, err2 = insert_historical_partida(
            budget_2,
            {"concepto_original": "Reparacion revoco fachada mortero R4", "unidad": "m2",
             "precio_unitario": 60.0, "cantidad": 1, "total_linea": 60.0},
        )
        assert err1 is None and err2 is None
        for pid in (partida_1, partida_2):
            _mark_features(
                pid, action="repair", element="facade_render", unit="m2", material="mortar_r4",
                line_kind="atomic", primary_module_id="fachada",
            )

        result = HistoricalSuggestionService().suggest_for_project(
            {}, "Reparación de revoco de fachada con mortero R4"
        )

        assert len(result["priced_partidas"]) == 1
        priced = result["priced_partidas"][0]
        assert priced["precio_unitario"] == 50.0
        assert priced["evidence_price_min"] == 40.0
        assert priced["evidence_price_max"] == 60.0
        assert sorted(priced["evidence_budget_ids"]) == sorted([budget_1, budget_2])
