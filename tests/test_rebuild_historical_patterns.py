"""
Fase 5, Tarea 13: reconstrucción reversible del histórico existente.

--dry-run nunca debe modificar el fichero (mismo SHA-256 antes/después,
incluso sobre una base sin migrar); --apply debe crear un backup verificado
por SHA-256 antes de tocar el original.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from scripts.rebuild_historical_patterns import main, sha256_file


def _seed_db(tmp_path, monkeypatch) -> Path:
    db_path = tmp_path / "seed.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
    from src.core.repositories import (
        assign_partida_module,
        get_or_create_execution_module,
        insert_historical_partida,
        upsert_historical_budget,
    )

    budget_id, err = upsert_historical_budget(
        {
            "ruta_excel": str(tmp_path / "hist.xlsx"),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": "hist.xlsx",
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "analysis_status": "VALID",
            "usable_for_learning": True,
            "learning_status": "INCLUDED",
        }
    )
    assert err is None
    module_id, module_err = get_or_create_execution_module("fachada")
    assert module_err is None
    partida_id, perr = insert_historical_partida(
        budget_id,
        {
            "concepto_original": "Revision de fachada con grieta",
            "concepto_normalizado": "revision de fachada con grieta",
            "unidad": "m2",
            "precio_unitario": 30.0,
            "cantidad": 1,
            "total_linea": 30.0,
        },
    )
    assert perr is None
    assert assign_partida_module(partida_id, module_id, 0.8, "rules") is None
    return db_path


def test_dry_run_never_modifies_the_file(tmp_path, monkeypatch, capsys):
    db_path = _seed_db(tmp_path, monkeypatch)
    before = sha256_file(db_path)

    exit_code = main(["--db", str(db_path), "--dry-run"])

    after = sha256_file(db_path)
    assert exit_code == 0
    assert after == before

    summary = json.loads(capsys.readouterr().out)
    assert summary["dry_run"] is True
    assert summary["hash_unchanged"] is True
    assert summary["would_reclassify"] == 1
    assert summary["total_partidas"] == 1


def test_dry_run_is_safe_on_unmigrated_v1_schema(tmp_path, monkeypatch, capsys):
    """No debe fallar ni tocar el fichero aunque historical_partida_feature
    todavia no exista (base real de produccion, hoy en schema_version=1)."""
    db_path = tmp_path / "legacy_v1.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE historical_budget (id INTEGER PRIMARY KEY, learning_status TEXT);
        CREATE TABLE historical_partida (id INTEGER PRIMARY KEY);
        CREATE TABLE suggested_partida_pattern (id INTEGER PRIMARY KEY);
        """
    )
    conn.commit()
    conn.close()
    before = sha256_file(db_path)

    exit_code = main(["--db", str(db_path), "--dry-run"])

    assert exit_code == 0
    assert sha256_file(db_path) == before
    summary = json.loads(capsys.readouterr().out)
    assert summary["schema_migrada"] is False
    assert summary["con_ficha_actual"] == 0


def test_missing_db_file_returns_error_without_crashing(tmp_path, capsys):
    missing = tmp_path / "no_existe.db"
    exit_code = main(["--db", str(missing), "--dry-run"])
    assert exit_code == 1
    assert "error" in json.loads(capsys.readouterr().out)


def test_apply_creates_verified_backup_before_touching_original(tmp_path, monkeypatch, capsys):
    db_path = _seed_db(tmp_path, monkeypatch)
    original_hash_before_apply = sha256_file(db_path)

    exit_code = main(["--db", str(db_path), "--apply"])
    assert exit_code == 0

    summary = json.loads(capsys.readouterr().out)
    backup_path = Path(summary["backup_path"])
    assert backup_path.exists()
    assert sha256_file(backup_path) == original_hash_before_apply
    assert summary["fichas_reconstruidas"] == 1
    assert summary["patrones_creados"] == 1


def test_apply_rebuilds_patterns_from_primary_evidence(tmp_path, monkeypatch, capsys):
    db_path = _seed_db(tmp_path, monkeypatch)

    main(["--db", str(db_path), "--apply"])
    capsys.readouterr()

    from src.core import database

    with database.get_connection(read_only=True) as conn:
        pattern = conn.execute(
            "SELECT precio_unitario_mediana FROM suggested_partida_pattern"
        ).fetchone()
        feature = conn.execute(
            "SELECT primary_module_id, line_kind FROM historical_partida_feature"
        ).fetchone()
    assert pattern is not None
    assert pattern[0] == 30.0
    assert feature == ("fachada", "atomic")
