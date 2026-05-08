import os
from datetime import datetime

from src.core import database
from src.core.repositories import (
    assign_partida_module,
    get_historical_memory_dashboard_metrics,
    get_or_create_execution_module,
    insert_historical_partida,
    list_historical_memory_dashboard_budgets,
    upsert_historical_budget,
)


def _budget(tmp_path, name: str, **overrides):
    data = {
        "ruta_excel": str(tmp_path / name),
        "ruta_carpeta": str(tmp_path),
        "nombre_proyecto": name,
        "numero_proyecto": "001-26",
        "cliente": "Comunidad Test",
        "fecha_modificacion_excel": datetime.now().isoformat(),
        "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analisis_ok": True,
        "analysis_status": "VALID",
        "learning_status": "INCLUDED",
        "usable_for_learning": True,
        "warning_count": 0,
        "total": 100.0,
        "num_partidas": 1,
        "selected_sheet": "Presupuesto",
        "compatible_score": 88,
    }
    data.update(overrides)
    budget_id, err = upsert_historical_budget(data)
    assert err is None
    assert budget_id is not None
    return int(budget_id)


def test_memory_dashboard_metrics_and_rows_include_modules_and_patterns(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "memory_dashboard.db"))
    with database.get_connection() as _conn:
        pass

    budget_id = _budget(tmp_path, "001-26_fachada.xlsx")
    module_id, err = get_or_create_execution_module("fachada")
    assert err is None
    partida_id, partida_err = insert_historical_partida(
        budget_id,
        {
            "orden": 1,
            "codigo": "01",
            "concepto_original": "Revision de fachada y reparacion de fisuras",
            "concepto_normalizado": "revision fachada reparacion fisuras",
            "unidad": "ud",
            "cantidad": 1,
            "precio_unitario": 100.0,
            "total_linea": 100.0,
        },
    )
    assert partida_err is None
    assert assign_partida_module(partida_id, module_id, 0.95, "rules") is None

    with database.get_connection() as conn:
        pattern_id = conn.execute(
            """INSERT INTO suggested_partida_pattern
               (module_id, concepto_normalizado, titulo_sugerido, unidad_habitual,
                precio_unitario_medio, precio_unitario_mediana, precio_unitario_min,
                precio_unitario_max, frecuencia, confianza, pattern_build_run,
                pattern_source, activo)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                module_id,
                "revision fachada reparacion fisuras",
                "Revision de fachada y reparacion de fisuras",
                "ud",
                100.0,
                100.0,
                100.0,
                100.0,
                2,
                0.8,
                "test_run",
                "historical",
            ),
        ).lastrowid
        conn.execute(
            """INSERT INTO suggested_partida_pattern_source
               (pattern_id, historical_partida_id, historical_budget_id,
                precio_unitario, total_linea, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                pattern_id,
                partida_id,
                budget_id,
                100.0,
                100.0,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()

    metrics = get_historical_memory_dashboard_metrics()
    assert metrics["total_budgets"] == 1
    assert metrics["valid"] == 1
    assert metrics["included"] == 1
    assert metrics["historical_partidas"] == 1
    assert metrics["active_patterns"] == 1
    assert metrics["patterns_with_sources"] == 1

    rows = list_historical_memory_dashboard_budgets({"search": "fachada"})
    assert len(rows) == 1
    assert rows[0]["id"] == budget_id
    assert rows[0]["modules"] == ["fachada"]
    assert rows[0]["related_patterns"] == 1


def test_memory_dashboard_filters_only_problems_and_learning_status(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "memory_dashboard_filters.db"))
    with database.get_connection() as _conn:
        pass

    _budget(tmp_path, "valid.xlsx")
    pending_id = _budget(
        tmp_path,
        "warning.xlsx",
        analysis_status="VALID_WITH_WARNINGS",
        learning_status="PENDING_REVIEW",
        usable_for_learning=False,
        warning_count=1,
    )
    _budget(
        tmp_path,
        "invalid.xlsx",
        analysis_status="EXCLUDED_INCOMPLETE_DATA",
        learning_status="NOT_ELIGIBLE",
        usable_for_learning=False,
    )

    rows = list_historical_memory_dashboard_budgets({"only_problems": True})
    assert {os.path.basename(row["ruta_excel"]) for row in rows} == {"warning.xlsx", "invalid.xlsx"}

    pending_rows = list_historical_memory_dashboard_budgets({"learning_status": "PENDING_REVIEW"})
    assert len(pending_rows) == 1
    assert pending_rows[0]["id"] == pending_id


def test_memory_dashboard_combined_filters_and_empty_relations(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "memory_dashboard_combined.db"))
    with database.get_connection() as _conn:
        pass

    included_id = _budget(tmp_path, "incluido.xlsx")
    warning_id = _budget(
        tmp_path,
        "warning_sin_modulos.xlsx",
        analysis_status="VALID_WITH_WARNINGS",
        learning_status="PENDING_REVIEW",
        usable_for_learning=False,
        warning_count=2,
        num_partidas=0,
    )

    module_id, err = get_or_create_execution_module("estructura")
    assert err is None
    partida_id, partida_err = insert_historical_partida(
        included_id,
        {
            "orden": 1,
            "codigo": "01",
            "concepto_original": "Refuerzo estructural",
            "concepto_normalizado": "refuerzo estructural",
            "unidad": "ud",
            "cantidad": 1,
            "precio_unitario": 200.0,
            "total_linea": 200.0,
        },
    )
    assert partida_err is None
    assert assign_partida_module(partida_id, module_id, 0.9, "rules") is None

    with database.get_connection() as conn:
        pattern_id = conn.execute(
            """INSERT INTO suggested_partida_pattern
               (module_id, concepto_normalizado, titulo_sugerido, unidad_habitual,
                precio_unitario_medio, precio_unitario_mediana, precio_unitario_min,
                precio_unitario_max, frecuencia, confianza, pattern_build_run,
                pattern_source, activo)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                module_id,
                "refuerzo estructural",
                "Refuerzo estructural",
                "ud",
                200.0,
                200.0,
                200.0,
                200.0,
                3,
                0.85,
                "run_test_2",
                "historical",
            ),
        ).lastrowid
        conn.execute(
            """INSERT INTO suggested_partida_pattern_source
               (pattern_id, historical_partida_id, historical_budget_id,
                precio_unitario, total_linea, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (pattern_id, partida_id, included_id, 200.0, 200.0, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()

    combined = list_historical_memory_dashboard_budgets(
        {
            "analysis_status": "VALID_WITH_WARNINGS",
            "learning_status": "PENDING_REVIEW",
            "with_warnings": True,
            "no_modules": True,
            "no_partidas": True,
            "no_related_patterns": True,
        }
    )
    assert len(combined) == 1
    assert combined[0]["id"] == warning_id
    assert combined[0]["module_count"] == 0
    assert combined[0]["persisted_partidas"] == 0
    assert combined[0]["related_patterns"] == 0

    no_patterns_rows = list_historical_memory_dashboard_budgets({"no_related_patterns": True})
    assert {row["id"] for row in no_patterns_rows} == {warning_id}
