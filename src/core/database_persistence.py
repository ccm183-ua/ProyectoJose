"""Diagnostico y proteccion de persistencia para la memoria historica."""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.core import database
from src.core.database_backup import create_database_backup


COUNT_TABLES = (
    "historical_budget",
    "historical_partida",
    "historical_budget_enrichment",
    "suggested_partida_pattern",
    "historical_analysis_run",
)


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_historical_memory_event(event_type: str, message: str = "", metadata: Optional[Dict] = None) -> None:
    try:
        with database.get_connection() as conn:
            conn.execute(
                """INSERT INTO historical_memory_event (event_type, message, metadata_json, created_at)
                   VALUES (?, ?, ?, ?)""",
                (
                    (event_type or "").strip().upper() or "UNSPECIFIED",
                    (message or "").strip(),
                    json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                    _now_str(),
                ),
            )
            conn.commit()
    except sqlite3.Error:
        pass


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def _count_table(conn: sqlite3.Connection, table: str) -> int:
    if not _table_exists(conn, table):
        return 0
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)


def _read_identity(conn: sqlite3.Connection) -> str:
    if not _table_exists(conn, "app_database_identity"):
        return ""
    row = conn.execute("SELECT database_uuid FROM app_database_identity WHERE id=1").fetchone()
    return row[0] if row and row[0] else ""


def inspect_database_file(path: Path) -> Dict:
    path = Path(path)
    info = {
        "path": str(path),
        "exists": path.exists(),
        "size_bytes": 0,
        "modified_at": "",
        "counts": {table: 0 for table in COUNT_TABLES},
        "included_budgets": 0,
        "descriptions_ai": 0,
        "descriptions_manual": 0,
        "database_uuid": "",
        "is_empty": True,
    }
    if not path.exists():
        return info
    stat = path.stat()
    info["size_bytes"] = int(stat.st_size)
    info["modified_at"] = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    if stat.st_size <= 0:
        return info
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            info["counts"] = {table: _count_table(conn, table) for table in COUNT_TABLES}
            if _table_exists(conn, "historical_budget"):
                info["included_budgets"] = int(
                    conn.execute(
                        """SELECT COUNT(*) FROM historical_budget
                           WHERE learning_status='INCLUDED' OR usable_for_learning=1"""
                    ).fetchone()[0]
                    or 0
                )
            if _table_exists(conn, "historical_budget_enrichment"):
                row = conn.execute(
                    """SELECT
                           SUM(CASE WHEN source='AI' THEN 1 ELSE 0 END),
                           SUM(CASE WHEN source='MANUAL' THEN 1 ELSE 0 END)
                       FROM historical_budget_enrichment
                       WHERE enrichment_type='TECHNICAL_DESCRIPTION'"""
                ).fetchone()
                info["descriptions_ai"] = int((row[0] if row else 0) or 0)
                info["descriptions_manual"] = int((row[1] if row else 0) or 0)
            info["database_uuid"] = _read_identity(conn)
    except sqlite3.Error as exc:
        info["error"] = str(exc)
    info["is_empty"] = int(info["counts"].get("historical_budget", 0) or 0) == 0
    info["is_truly_empty"] = not info["exists"] or int(info["size_bytes"] or 0) == 0
    info["has_historical_data"] = int(info["counts"].get("historical_budget", 0) or 0) > 0
    return info


def get_database_diagnostics() -> Dict:
    path = database.get_db_path()
    # Ensure schema and identity exist for active DB before reading diagnostics.
    with database.get_connection() as _conn:
        pass
    info = inspect_database_file(path)
    info["active_path"] = str(path)
    return info


def find_database_candidates() -> List[Dict]:
    candidates: List[Path] = [database.get_db_path(), database.get_legacy_db_path(), database.get_stable_default_db_path()]
    env_path = os.environ.get("CUBIAPP_DB_PATH")
    if env_path and os.path.isabs(env_path):
        candidates.append(Path(env_path))
    unique = []
    seen = set()
    for path in candidates:
        resolved = str(Path(path))
        if resolved in seen:
            continue
        seen.add(resolved)
        info = inspect_database_file(Path(path))
        info["is_active"] = resolved == str(database.get_db_path())
        unique.append(info)
    return unique


def find_candidate_with_historical_data() -> Optional[Dict]:
    active = str(database.get_db_path())
    for candidate in find_database_candidates():
        if candidate["path"] == active:
            continue
        if int(candidate.get("counts", {}).get("historical_budget", 0) or 0) > 0:
            return candidate
    return None


def copy_database_as_active(source_path: str) -> Dict:
    source = Path(source_path)
    if not source.exists():
        return {"ok": False, "error": "La base de datos origen no existe."}
    active = database.get_db_path()
    if source.resolve() == active.resolve():
        return {"ok": False, "error": "La base seleccionada ya es la activa."}
    database.ensure_db_directory(active)
    backup_path = None
    if active.exists():
        backup_path = create_database_backup("before_db_copy")
    shutil.copy2(source, active)
    with database.get_connection() as _conn:
        pass
    log_historical_memory_event(
        "DB_COPIED_FROM_LEGACY",
        "Base de datos copiada como activa.",
        {"source": str(source), "destination": str(active), "backup": str(backup_path) if backup_path else ""},
    )
    return {"ok": True, "source": str(source), "destination": str(active), "backup": str(backup_path) if backup_path else ""}
