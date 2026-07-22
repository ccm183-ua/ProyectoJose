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
    upsert_partida_features,
)


def _mark_atomic_primary(
    partida_id: int, module_name: str, action: str = "repair", element: str = "generic", unit: str = "ud"
) -> None:
    """Registra la ficha derivada mínima (Fase 2) que _load_groups() exige:
    línea atómica con módulo principal único y atributos completos
    (Fixes histórico evidenciado, Tarea 2/7: is_price_eligible exige
    unit/action/element no vacíos, no solo line_kind='atomic')."""
    err = upsert_partida_features(
        partida_id,
        {
            "action": action,
            "element": element,
            "system": None,
            "unit": unit,
            "material": None,
            "dimensions": (),
            "conditions": (),
            "line_kind": "atomic",
            "primary_module_id": module_name,
            "secondary_module_ids": (),
            "confidence": 0.9,
            "reasons": (),
            "classifier_version": "test",
        },
    )
    assert err is None


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
                "analysis_status": "VALID",
                "usable_for_learning": True,
                "learning_status": "INCLUDED",
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
            _mark_atomic_primary(partida_id, "sustitucion_bajante")

        result = HistoricalPatternBuilder().rebuild_patterns()
        assert result["patterns_inserted"] >= 1
        assert result["pattern_build_run"].startswith("pattern_build_")
        assert result["pattern_source"] == HistoricalPatternBuilder.PATTERN_SOURCE

        with database.get_connection(read_only=True) as conn:
            cur = conn.execute(
                """SELECT precio_unitario_medio, precio_unitario_mediana, precio_unitario_min,
                          precio_unitario_max, frecuencia, confianza, pattern_build_run, pattern_source
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
        assert row[6].startswith("pattern_build_")
        assert row[7] == HistoricalPatternBuilder.PATTERN_SOURCE

    def test_rebuild_patterns_uses_included_and_ignores_pending_review(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_pattern_filter_test.db"))

        included_id, err_inc = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / "included.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "included.xlsx",
                "fecha_modificacion_excel": datetime.now().isoformat(),
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "analysis_status": "VALID",
                "usable_for_learning": True,
                "learning_status": "INCLUDED",
            }
        )
        assert err_inc is None

        pending_id, err_pen = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / "pending.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "pending.xlsx",
                "fecha_modificacion_excel": datetime.now().isoformat(),
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "analysis_status": "VALID_WITH_WARNINGS",
                "usable_for_learning": False,
                "learning_status": "PENDING_REVIEW",
            }
        )
        assert err_pen is None

        module_id, module_err = get_or_create_execution_module("sustitucion_bajante")
        assert module_err is None
        assert module_id is not None

        part_inc, part_inc_err = insert_historical_partida(
            included_id,
            {
                "titulo": "Desmontaje bajante existente",
                "concepto_original": "Desmontaje bajante existente",
                "concepto_normalizado": "desmontaje bajante existente",
                "unidad": "ml",
                "precio_unitario": 10.0,
                "cantidad": 1,
                "total_linea": 10.0,
            },
        )
        assert part_inc_err is None
        assert assign_partida_module(part_inc, module_id, 0.9, "rules") is None
        _mark_atomic_primary(part_inc, "sustitucion_bajante")

        part_pen, part_pen_err = insert_historical_partida(
            pending_id,
            {
                "titulo": "Desmontaje bajante existente",
                "concepto_original": "Desmontaje bajante existente",
                "concepto_normalizado": "desmontaje bajante existente",
                "unidad": "ml",
                "precio_unitario": 100.0,
                "cantidad": 1,
                "total_linea": 100.0,
            },
        )
        assert part_pen_err is None
        assert assign_partida_module(part_pen, module_id, 0.9, "rules") is None
        _mark_atomic_primary(part_pen, "sustitucion_bajante")

        result = HistoricalPatternBuilder().rebuild_patterns()
        assert result["patterns_inserted"] >= 1
        assert result["pattern_build_run"].startswith("pattern_build_")
        assert result["pattern_source"] == HistoricalPatternBuilder.PATTERN_SOURCE

        with database.get_connection(read_only=True) as conn:
            cur = conn.execute(
                """SELECT precio_unitario_medio, frecuencia, pattern_build_run, pattern_source
                   FROM suggested_partida_pattern
                   WHERE module_id=? AND concepto_normalizado=?""",
                (module_id, "desmontaje bajante existente"),
            )
            row = cur.fetchone()

        assert row is not None
        # Debe usar solo el presupuesto INCLUDED (10.0), ignorando PENDING_REVIEW (100.0)
        assert row[0] == 10.0
        assert row[1] == 1
        assert row[2].startswith("pattern_build_")
        assert row[3] == HistoricalPatternBuilder.PATTERN_SOURCE

    def test_rebuild_patterns_ignores_technically_invalid_manual_included_budgets(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_pattern_invalid_included.db"))

        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / "invalid_but_included.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "invalid_but_included.xlsx",
                "fecha_modificacion_excel": datetime.now().isoformat(),
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "analysis_status": "EXCLUDED_INCOMPLETE_DATA",
                "usable_for_learning": True,
                "learning_status": "INCLUDED",
                "learning_status_source": "MANUAL",
            }
        )
        assert err is None

        module_id, module_err = get_or_create_execution_module("albanileria")
        assert module_err is None
        partida_id, perr = insert_historical_partida(
            budget_id,
            {
                "titulo": "Roza y mortero",
                "concepto_original": "Roza y mortero",
                "concepto_normalizado": "roza y mortero",
                "unidad": "ml",
                "precio_unitario": 30.0,
                "cantidad": 1,
                "total_linea": 30.0,
            },
        )
        assert perr is None
        assert assign_partida_module(partida_id, module_id, 0.9, "rules") is None
        _mark_atomic_primary(partida_id, "albanileria")

        result = HistoricalPatternBuilder().rebuild_patterns()
        assert result["patterns_inserted"] == 0

        with database.get_connection(read_only=True) as conn:
            cur = conn.execute("SELECT COUNT(*) FROM suggested_partida_pattern")
            assert int((cur.fetchone() or [0])[0] or 0) == 0

    def test_rebuild_patterns_persists_build_run_and_pattern_sources(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_pattern_traceability_test.db"))

        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / "trace.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "trace.xlsx",
                "fecha_modificacion_excel": datetime.now().isoformat(),
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "analysis_status": "VALID",
                "usable_for_learning": True,
                "learning_status": "INCLUDED",
            }
        )
        assert err is None
        assert budget_id is not None

        module_id, module_err = get_or_create_execution_module("sustitucion_bajante")
        assert module_err is None
        assert module_id is not None

        partida_ids = []
        for price in [15.0, 25.0]:
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
            partida_ids.append(int(partida_id))
            assert assign_partida_module(partida_id, module_id, 0.9, "rules") is None
            _mark_atomic_primary(partida_id, "sustitucion_bajante")

        result1 = HistoricalPatternBuilder().rebuild_patterns()
        result2 = HistoricalPatternBuilder().rebuild_patterns()
        assert result1["pattern_build_run"] != result2["pattern_build_run"]

        with database.get_connection(read_only=True) as conn:
            cur_run = conn.execute(
                """SELECT id, started_at, finished_at, source_budget_count, source_partida_count,
                          patterns_inserted, builder_version, error
                   FROM historical_pattern_build_run
                   WHERE id=?""",
                (result2["pattern_build_run"],),
            )
            run_row = cur_run.fetchone()
            assert run_row is not None
            assert run_row[0] == result2["pattern_build_run"]
            assert run_row[1]
            assert run_row[2]
            assert int(run_row[3] or 0) >= 1
            assert int(run_row[4] or 0) >= 2
            assert int(run_row[5] or 0) >= 1
            assert run_row[6] == HistoricalPatternBuilder.BUILDER_VERSION
            assert (run_row[7] or "") == ""

            cur_pattern = conn.execute(
                """SELECT id
                   FROM suggested_partida_pattern
                   WHERE pattern_build_run=?
                   LIMIT 1""",
                (result2["pattern_build_run"],),
            )
            pattern_row = cur_pattern.fetchone()
            assert pattern_row is not None
            pattern_id = int(pattern_row[0])

            cur_sources = conn.execute(
                """SELECT pattern_id, historical_partida_id, historical_budget_id, precio_unitario, total_linea
                   FROM suggested_partida_pattern_source
                   WHERE pattern_id=?""",
                (pattern_id,),
            )
            source_rows = cur_sources.fetchall()
            assert len(source_rows) >= 1

            cur_real_refs = conn.execute(
                """SELECT COUNT(*)
                   FROM suggested_partida_pattern_source spps
                   JOIN historical_partida hp ON hp.id = spps.historical_partida_id
                   JOIN historical_budget hb ON hb.id = spps.historical_budget_id
                   WHERE spps.pattern_id=?""",
                (pattern_id,),
            )
            real_ref_count = int((cur_real_refs.fetchone() or [0])[0] or 0)
            assert real_ref_count == len(source_rows)

            partida_ids_from_source = {int(r[1]) for r in source_rows}
            assert partida_ids_from_source.issubset(set(partida_ids))

    def test_rebuild_patterns_preserves_previous_patterns_when_rebuild_fails(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_pattern_failure_preserve.db"))

        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / "stable.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "stable.xlsx",
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
        _mark_atomic_primary(partida_id, "sustitucion_bajante")

        HistoricalPatternBuilder().rebuild_patterns()
        with database.get_connection(read_only=True) as conn:
            before_count = int(conn.execute("SELECT COUNT(*) FROM suggested_partida_pattern").fetchone()[0])
        assert before_count > 0

        class BrokenPatternBuilder(HistoricalPatternBuilder):
            def _load_groups(self):
                return [
                    {
                        "module_id": module_id,
                        "concepto_normalizado": "patron roto",
                        "titulo_sugerido": "Patron roto",
                        "unidad": "ud",
                        "prices": [10.0],
                        "sources": [
                            {
                                "historical_partida_id": 999999,
                                "historical_budget_id": 999999,
                                "precio_unitario": 10.0,
                                "total_linea": 10.0,
                            }
                        ],
                    }
                ]

        try:
            BrokenPatternBuilder().rebuild_patterns()
            assert False, "El rebuild roto deberia fallar por claves foraneas"
        except Exception:
            pass

        with database.get_connection(read_only=True) as conn:
            after_count = int(conn.execute("SELECT COUNT(*) FROM suggested_partida_pattern").fetchone()[0])
            failed_runs = int(
                conn.execute(
                    "SELECT COUNT(*) FROM historical_pattern_build_run WHERE error IS NOT NULL"
                ).fetchone()[0]
            )
        assert after_count == before_count
        assert failed_runs == 1


class TestPrimaryModuleEvidence:
    """Fase 3, Tarea 9: patrones solo desde evidencia primaria (línea atómica,
    módulo principal único, presupuesto aprobado)."""

    def test_partida_with_secondary_modules_only_generates_one_pattern(self, tmp_path, monkeypatch):
        """Regresión del caso auditado: una partida asignada a varios módulos
        (historical_partida_module, como hacía el clasificador antiguo) ya no
        debe generar un patrón por cada etiqueta secundaria, solo por su
        módulo principal (historical_partida_feature.primary_module_id)."""
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_primary_dedupe.db"))

        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / "compuesta.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "compuesta.xlsx",
                "fecha_modificacion_excel": datetime.now().isoformat(),
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "analysis_status": "VALID",
                "usable_for_learning": True,
                "learning_status": "INCLUDED",
            }
        )
        assert err is None

        fachada_id, _ = get_or_create_execution_module("fachada")
        demolicion_id, _ = get_or_create_execution_module("demolicion")
        albanileria_id, _ = get_or_create_execution_module("albanileria")

        partida_id, perr = insert_historical_partida(
            budget_id,
            {
                "titulo": "Reparacion de fachada compuesta",
                "concepto_original": "Reparacion de fachada compuesta",
                "concepto_normalizado": "reparacion de fachada compuesta",
                "unidad": "m2",
                "precio_unitario": 45.0,
                "cantidad": 1,
                "total_linea": 45.0,
            },
        )
        assert perr is None
        # El clasificador (Tarea 6) asigna varias etiquetas: se conservan en
        # historical_partida_module para consulta, pero ya no alimentan patrones.
        assert assign_partida_module(partida_id, fachada_id, 0.8, "rules") is None
        assert assign_partida_module(partida_id, demolicion_id, 0.6, "rules") is None
        assert assign_partida_module(partida_id, albanileria_id, 0.55, "rules") is None
        _mark_atomic_primary(partida_id, "fachada")

        result = HistoricalPatternBuilder().rebuild_patterns()
        assert result["patterns_inserted"] == 1

        with database.get_connection(read_only=True) as conn:
            total = conn.execute("SELECT COUNT(*) FROM suggested_partida_pattern").fetchone()[0]
        assert total == 1

    def test_composite_line_never_produces_a_pattern(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_composite_excluded.db"))

        budget_id, err = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / "compuesta2.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": "compuesta2.xlsx",
                "fecha_modificacion_excel": datetime.now().isoformat(),
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "analysis_status": "VALID",
                "usable_for_learning": True,
                "learning_status": "INCLUDED",
            }
        )
        assert err is None
        partida_id, perr = insert_historical_partida(
            budget_id,
            {
                "titulo": "Linea compuesta",
                "concepto_original": "Linea compuesta",
                "concepto_normalizado": "linea compuesta",
                "unidad": "m2",
                "precio_unitario": 99.0,
                "cantidad": 1,
                "total_linea": 99.0,
            },
        )
        assert perr is None
        err = upsert_partida_features(
            partida_id,
            {
                "action": "repair", "element": None, "system": None, "unit": "m2",
                "material": None, "dimensions": (), "conditions": (),
                "line_kind": "composite", "primary_module_id": "fachada",
                "secondary_module_ids": ("demolicion",), "confidence": 0.6,
                "reasons": (), "classifier_version": "test",
            },
        )
        assert err is None

        result = HistoricalPatternBuilder().rebuild_patterns()
        assert result["patterns_inserted"] == 0

    def test_pattern_records_distinct_budget_count_and_price_spread(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_pattern_spread.db"))

        module_id, module_err = get_or_create_execution_module("fachada")
        assert module_err is None

        prices_and_budgets = [(40.0, "b1.xlsx"), (60.0, "b2.xlsx")]
        for price, name in prices_and_budgets:
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
            partida_id, perr = insert_historical_partida(
                budget_id,
                {
                    "titulo": "Revoco de fachada",
                    "concepto_original": "Revoco de fachada",
                    "concepto_normalizado": "revoco de fachada",
                    "unidad": "m2",
                    "precio_unitario": price,
                    "cantidad": 1,
                    "total_linea": price,
                },
            )
            assert perr is None
            assert assign_partida_module(partida_id, module_id, 0.8, "rules") is None
            _mark_atomic_primary(partida_id, "fachada")

        result = HistoricalPatternBuilder().rebuild_patterns()
        assert result["patterns_inserted"] == 1

        with database.get_connection(read_only=True) as conn:
            row = conn.execute(
                """SELECT precio_unitario_mediana, distinct_budget_count, price_spread_ratio, evidence_quality
                   FROM suggested_partida_pattern
                   WHERE module_id=? AND concepto_normalizado=?""",
                (module_id, "revoco de fachada"),
            ).fetchone()
        assert row is not None
        assert row[0] == 50.0
        assert row[1] == 2
        assert row[2] == 0.4
        assert row[3] == "medium"
