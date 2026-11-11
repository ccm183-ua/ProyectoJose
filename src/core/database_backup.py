"""Backups seguros de la base de datos activa."""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List

from src.core import database

# Retención (decisión D1, 2026-11-11): se guardan los últimos N backups y,
# siempre, los de migración de esquema y los previos a un borrado total.
BACKUP_KEEP_LAST = 15
PROTECTED_BACKUP_REASONS = ("before_migration", "before_clear_historical")


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
    try:
        prune_old_backups(BACKUP_KEEP_LAST)
    except Exception:  # noqa: BLE001 - purgar nunca puede impedir el backup
        pass
    return target


def list_database_backups() -> List[Path]:
    backup_dir = get_backup_dir()
    if not backup_dir.exists():
        return []
    # Orden por la marca de tiempo del nombre (datos_AAAAMMDD_HHMMSS_ffffff_...),
    # no por mtime: shutil.copy2 conserva el mtime de la BD original, así que
    # todos los backups llevaban la fecha de la última escritura en la BD.
    return sorted(
        [p for p in backup_dir.glob("*.db") if p.is_file()],
        key=lambda p: (p.name, p.stat().st_mtime),
        reverse=True,
    )


def _is_protected(path: Path) -> bool:
    return any(reason in path.name for reason in PROTECTED_BACKUP_REASONS)


def prune_old_backups(keep_last: int = BACKUP_KEEP_LAST) -> int:
    """Borra los backups más antiguos, conservando los ``keep_last`` más
    recientes y siempre los protegidos (migraciones y borrados totales).
    Devuelve cuántos se han borrado."""
    keep = max(0, int(keep_last or 0))
    candidates = [p for p in list_database_backups() if not _is_protected(p)]
    removed = 0
    for path in candidates[keep:]:
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed
