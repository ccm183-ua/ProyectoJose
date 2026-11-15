"""
Fase 0 del roadmap docs/superpowers/plans/2026-07-22-historico-estructurado-y-cruce-fiable.md.

Prueba de contrato para build_audit_report(): informe de solo lectura que
congela la verdad actual del histórico (partidas sin clasificar, multi-módulo
y patrones) antes de tocar clasificación o comparador.
"""

from datetime import datetime

from scripts.audit_historical_memory import build_audit_report
from src.core.repositories.historical_repository import (
    assign_partida_module,
    get_or_create_execution_module,
    insert_historical_partida,
    upsert_historical_budget,
)


def seed_history_db(tmp_path, monkeypatch):
    db_path = tmp_path / "seed.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))

    budget_id, err = upsert_historical_budget(
        {
            "ruta_excel": str(tmp_path / "seed.xlsx"),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": "seed",
            "fecha_modificacion_excel": datetime.now().isoformat(),
        }
    )
    assert err is None

    module_a, err = get_or_create_execution_module("fachada")
    assert err is None
    module_b, err = get_or_create_execution_module("demolicion")
    assert err is None

    # Partida 1: sin clasificar (0 módulos)
    partida_1, err = insert_historical_partida(
        budget_id, {"concepto_original": "Sin clasificar", "unidad": "ud"}
    )
    assert err is None

    # Partida 2: un único módulo
    partida_2, err = insert_historical_partida(
        budget_id, {"concepto_original": "Un modulo", "unidad": "ud"}
    )
    assert err is None
    assert assign_partida_module(partida_2, module_a, 0.5, "rules") is None

    # Partida 3: multi-módulo (misma línea con dos módulos)
    partida_3, err = insert_historical_partida(
        budget_id, {"concepto_original": "Multi modulo", "unidad": "ud"}
    )
    assert err is None
    assert assign_partida_module(partida_3, module_a, 0.5, "rules") is None
    assert assign_partida_module(partida_3, module_b, 0.5, "rules") is None

    return db_path


def test_build_audit_report_counts_unclassified_and_multimodule(tmp_path, monkeypatch):
    db_path = seed_history_db(tmp_path, monkeypatch)

    report = build_audit_report(str(db_path))

    assert report["lines_total"] == 3
    assert report["lines_unclassified"] == 1
    assert report["lines_multimodule"] == 1
    assert report["module_assignments_total"] == 3


def test_build_audit_report_does_not_modify_db(tmp_path, monkeypatch):
    import hashlib

    db_path = seed_history_db(tmp_path, monkeypatch)
    before = hashlib.sha256(db_path.read_bytes()).hexdigest()

    build_audit_report(str(db_path))

    after = hashlib.sha256(db_path.read_bytes()).hexdigest()
    assert before == after
