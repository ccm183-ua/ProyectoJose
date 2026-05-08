import sqlite3
from datetime import datetime

from src.core import database
from src.core.historical_integrity_diagnostics import diagnose_historical_integrity
from src.core.historical_issue_catalog import historical_issue_label, is_known_historical_issue_code
from src.core.repositories import (
    assign_partida_module,
    get_or_create_execution_module,
    insert_historical_partida,
    upsert_historical_budget,
)


def _check_names(report):
    return {finding["check"] for finding in report["findings"]}


def test_diagnostics_report_missing_historical_schema(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE legacy_marker (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))

    report = diagnose_historical_integrity()

    assert report["schema_ok"] is False
    assert "historical_budget" in report["missing_tables"]
    assert "missing_historical_tables" in _check_names(report)


def test_diagnostics_empty_initialized_schema_is_clean(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "clean.db"))
    with database.get_connection() as _conn:
        pass

    report = diagnose_historical_integrity()

    assert report["schema_ok"] is True
    assert report["missing_tables"] == []
    assert report["findings"] == []
    assert report["counts"]["historical_budget"] == 0


def test_diagnostics_detect_contaminated_memory_and_unknown_issue(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "contaminated.db"))

    budget_id, err = upsert_historical_budget(
        {
            "ruta_excel": str(tmp_path / "bad.xlsx"),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": "bad.xlsx",
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "analisis_ok": True,
            "analysis_status": "EXCLUDED_INCOMPLETE_DATA",
            "usable_for_learning": True,
            "learning_status": "INCLUDED",
            "learning_status_source": "MANUAL",
            "total": 0.0,
        }
    )
    assert err is None
    module_id, module_err = get_or_create_execution_module("albanileria")
    assert module_err is None
    partida_id, partida_err = insert_historical_partida(
        budget_id,
        {
            "titulo": "Total presupuesto",
            "concepto_original": "Total presupuesto",
            "concepto_normalizado": "total presupuesto",
            "unidad": "ud",
            "cantidad": 1,
            "precio_unitario": 30.0,
            "total_linea": 30.0,
        },
    )
    assert partida_err is None
    assert assign_partida_module(partida_id, module_id, 0.9, "rules") is None

    with database.get_connection() as conn:
        pattern_id = conn.execute(
            """INSERT INTO suggested_partida_pattern
               (module_id, concepto_normalizado, unidad_habitual, precio_unitario_medio,
                precio_unitario_mediana, precio_unitario_min, precio_unitario_max,
                frecuencia, confianza, pattern_build_run, pattern_source, activo)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                module_id,
                "total presupuesto",
                "ud",
                30.0,
                30.0,
                30.0,
                30.0,
                1,
                0.1,
                "manual_test_run",
                "test",
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
                30.0,
                30.0,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.execute(
            """INSERT INTO historical_budget_issue
               (historical_budget_id, severity, code, message, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                budget_id,
                "WARN",
                "UNKNOWN_TEST_CODE",
                "Codigo no catalogado",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )
        conn.commit()

    report = diagnose_historical_integrity()
    checks = _check_names(report)

    assert report["schema_ok"] is True
    assert "included_invalid_analysis_status" in checks
    assert "included_zero_total" in checks
    assert "pattern_source_from_non_included_budget" in checks
    assert "looks_like_total_or_header" in checks
    assert "unknown_issue_code" in checks


def test_historical_issue_catalog_known_and_unknown_labels():
    assert is_known_historical_issue_code("READ_ERROR") is True
    assert is_known_historical_issue_code("does_not_exist") is False
    assert historical_issue_label("does_not_exist") == "Aviso del analisis historico."
