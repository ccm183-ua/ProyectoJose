"""Backups seguros de la base de datos activa."""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from src.core import database


def get_backup_dir() -> Path:
    env_dir = os.environ.get("CUBIAPP_BACKUP_DIR")
    if env_dir and os.path.isabs(env_dir):
        return Path(env_dir)
    return Path.home() / "Documents" / "CubiApp" / "backups"


def create_database_backup(reason: str) -> Path:
    db_path = database.get_db_path()
    backup_dir = get_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_reason = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in (reason or "backup"))
    target = backup_dir / f"datos_{stamp}_{safe_reason}.db"
    if db_path.exists():
        shutil.copy2(db_path, target)
    else:
        target.touch()
    try:
        from src.core.database_persistence import log_historical_memory_event

        log_historical_memory_event(
            "DB_BACKUP_CREATED",
            "Backup de base de datos creado.",
            {"reason": reason or "", "backup_path": str(target), "source_path": str(db_path)},
        )
    except Exception:
        pass
    return target


def list_database_backups() -> List[Path]:
    backup_dir = get_backup_dir()
    if not backup_dir.exists():
        return []
    return sorted(
        [p for p in backup_dir.glob("*.db") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def prune_old_backups(keep_last: int = 10) -> None:
    keep = max(0, int(keep_last or 0))
    for path in list_database_backups()[keep:]:
        try:
            path.unlink()
        except OSError:
            pass
