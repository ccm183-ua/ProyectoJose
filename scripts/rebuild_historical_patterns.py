"""
Fase 5, Tarea 13: reconstrucción controlada y reversible del histórico existente.

Recalcula la ficha derivada (Fase 2) de TODAS las partidas históricas y
reconstruye los patrones de precio desde evidencia primaria (Fase 3): módulo
principal, línea atómica, presupuesto INCLUDED.

--dry-run: de solo lectura (sqlite3 nativo, sin pasar por src.core.database
para no disparar una migración de esquema); nunca modifica el fichero, ni
siquiera su schema_version. Seguro incluso sobre una base todavía en v1.

--apply: crea copia de seguridad ANTES de tocar nada y aborta si el SHA-256
de la copia no coincide con el original; solo entonces reconstruye fichas y
patrones sobre el fichero real (eso sí puede disparar la migración de
esquema, de forma idéntica a abrir la app normalmente).

Uso:
    python scripts/rebuild_historical_patterns.py --db PATH --dry-run
    python scripts/rebuild_historical_patterns.py --db PATH --apply
"""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def sha256_file(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def build_summary(db_path: str) -> dict:
    """Informe de solo lectura: nunca escribe, nunca migra el esquema."""
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        schema_version = 0
        if _table_exists(conn, "schema_version"):
            row = conn.execute("SELECT version FROM schema_version WHERE id=1").fetchone()
            schema_version = int(row[0]) if row else 0

        total_partidas = conn.execute("SELECT COUNT(*) FROM historical_partida").fetchone()[0]
        patrones_actuales = conn.execute(
            "SELECT COUNT(*) FROM suggested_partida_pattern"
        ).fetchone()[0]
        pending_review = conn.execute(
            "SELECT COUNT(*) FROM historical_budget WHERE learning_status='PENDING_REVIEW'"
        ).fetchone()[0]

        line_kinds: dict = {}
        if _table_exists(conn, "historical_partida_feature"):
            line_kinds = dict(
                conn.execute(
                    "SELECT COALESCE(line_kind, 'sin_ficha'), COUNT(*) "
                    "FROM historical_partida_feature GROUP BY 1"
                ).fetchall()
            )
        con_ficha = sum(line_kinds.values())

    return {
        "schema_version": schema_version,
        "schema_migrada": schema_version >= 3,
        "total_partidas": total_partidas,
        "con_ficha_actual": con_ficha,
        "sin_ficha_actual": total_partidas - con_ficha,
        "would_reclassify": total_partidas,
        "line_kinds_actuales": line_kinds,
        "presupuestos_pending_review": pending_review,
        "patrones_actuales": patrones_actuales,
    }


def apply_rebuild(db_path: str) -> dict:
    """Recalcula fichas y patrones sobre el fichero real. Puede migrar el
    esquema (idéntico a abrir la app normalmente); el llamador ya habrá
    verificado el backup antes de invocar esto."""
    os.environ["CUBIAPP_DB_PATH"] = str(db_path)
    from src.core import database
    from src.core.historical_budget_analyzer import HistoricalBudgetAnalyzer
    from src.core.historical_pattern_builder import HistoricalPatternBuilder

    with database.get_connection() as conn:
        budget_ids = [r[0] for r in conn.execute("SELECT id FROM historical_budget").fetchall()]
        patrones_antes = conn.execute("SELECT COUNT(*) FROM suggested_partida_pattern").fetchone()[0]

    fichas_reconstruidas = HistoricalBudgetAnalyzer().rebuild_partida_features(budget_ids)

    with database.get_connection(read_only=True) as conn:
        line_kinds_despues = dict(
            conn.execute(
                "SELECT COALESCE(line_kind, 'sin_ficha'), COUNT(*) "
                "FROM historical_partida_feature GROUP BY 1"
            ).fetchall()
        )

    pattern_result = HistoricalPatternBuilder().rebuild_patterns()

    with database.get_connection(read_only=True) as conn:
        patrones_despues = conn.execute("SELECT COUNT(*) FROM suggested_partida_pattern").fetchone()[0]

    return {
        "fichas_reconstruidas": fichas_reconstruidas,
        "line_kinds_despues": line_kinds_despues,
        "patrones_antes": patrones_antes,
        "patrones_despues": patrones_despues,
        "patrones_eliminados": max(0, patrones_antes - patrones_despues),
        "patrones_creados": pattern_result.get("patterns_inserted", 0),
        "pattern_build_run": pattern_result.get("pattern_build_run", ""),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Ruta al fichero .db")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true")
    group.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(json.dumps({"error": f"No existe el fichero: {db_path}"}, ensure_ascii=False))
        return 1

    if args.dry_run:
        before_hash = sha256_file(db_path)
        summary = build_summary(str(db_path))
        after_hash = sha256_file(db_path)
        summary["dry_run"] = True
        summary["hash_unchanged"] = before_hash == after_hash
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0 if summary["hash_unchanged"] else 1

    # --apply: backup primero, verificado por SHA-256, y solo entonces se toca el original.
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = db_path.with_suffix(db_path.suffix + f".bak-{timestamp}")
    shutil.copy2(db_path, backup_path)
    if sha256_file(db_path) != sha256_file(backup_path):
        print(
            json.dumps(
                {"error": "La copia de seguridad no coincide (SHA-256); abortado sin tocar el original."},
                ensure_ascii=False,
            )
        )
        return 1

    summary = apply_rebuild(str(db_path))
    summary["dry_run"] = False
    summary["backup_path"] = str(backup_path)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
