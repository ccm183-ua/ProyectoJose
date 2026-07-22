"""
Fixes histórico evidenciado, Tarea 7: audit_historical_memory.py (Fase 0)
gana visibilidad de elegibilidad de precio (Tarea 2/4) y de duplicados por
hash (Tarea 1), útil para decidir si conviene revisar antes de --apply.
"""

from datetime import datetime
from pathlib import Path

from scripts.audit_historical_memory import build_audit_report


def test_reports_price_eligibility_and_duplicate_hashes(tmp_path, monkeypatch):
    db_path = tmp_path / "audit.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
    from src.core.historical_budget_analyzer import HistoricalBudgetAnalyzer
    from src.core.repositories import insert_historical_partida, upsert_historical_budget

    budget_id, err = upsert_historical_budget(
        {
            "ruta_excel": str(tmp_path / "audit.xlsx"),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": "audit.xlsx",
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "analysis_status": "VALID",
            "usable_for_learning": True,
            "learning_status": "INCLUDED",
            "file_sha256": "c" * 64,
        }
    )
    assert err is None
    for concepto, unidad in (
        ("Reparacion de fachada con grieta", "m2"),
        ("Demolicion de bajante y reparacion de cubierta", "ud"),
    ):
        _pid, perr = insert_historical_partida(
            budget_id,
            {
                "concepto_original": concepto,
                "concepto_normalizado": concepto.lower(),
                "unidad": unidad,
                "precio_unitario": 30.0,
                "cantidad": 1,
                "total_linea": 30.0,
            },
        )
        assert perr is None
    HistoricalBudgetAnalyzer().rebuild_partida_features([budget_id])

    report = build_audit_report(str(db_path))

    assert report["lines_price_eligible"] == 1
    assert report["lines_composite"] == 1
    assert report["duplicate_file_hashes"] == 0
