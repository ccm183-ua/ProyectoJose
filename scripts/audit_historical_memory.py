"""
Fase 0 del roadmap docs/superpowers/plans/2026-07-22-historico-estructurado-y-cruce-fiable.md.

Auditoria de solo lectura de la memoria historica actual (nunca modifica el
fichero .db: abre en modo ro y no llama a init_schema ni a ninguna migracion).
Sirve de linea base reproducible antes de tocar clasificacion, patrones u
orquestador.

Uso:
    python scripts/audit_historical_memory.py --db "C:\\ruta\\a\\datos.db"
"""

import argparse
import json
import sqlite3
from pathlib import Path


def _fetchone(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else 0


def build_audit_report(db_path: str) -> dict:
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        lines_total = _fetchone(conn, "SELECT COUNT(*) FROM historical_partida")

        lines_unclassified = _fetchone(
            conn,
            """SELECT COUNT(*) FROM historical_partida hp
               WHERE NOT EXISTS (
                   SELECT 1 FROM historical_partida_module hpm WHERE hpm.partida_id = hp.id
               )""",
        )

        lines_multimodule = _fetchone(
            conn,
            """SELECT COUNT(*) FROM (
                   SELECT partida_id FROM historical_partida_module
                   GROUP BY partida_id HAVING COUNT(*) > 1
               )""",
        )

        module_assignments_total = _fetchone(conn, "SELECT COUNT(*) FROM historical_partida_module")

        patterns = _fetchone(conn, "SELECT COUNT(*) FROM suggested_partida_pattern WHERE activo=1")
        patterns_freq_ge_2 = _fetchone(
            conn, "SELECT COUNT(*) FROM suggested_partida_pattern WHERE activo=1 AND frecuencia >= 2"
        )
        patterns_freq_ge_6 = _fetchone(
            conn, "SELECT COUNT(*) FROM suggested_partida_pattern WHERE activo=1 AND frecuencia >= 6"
        )

        budgets_total = _fetchone(conn, "SELECT COUNT(*) FROM historical_budget")
        budgets_not_compatible = _fetchone(
            conn, "SELECT COUNT(*) FROM historical_budget WHERE analysis_status='NOT_COMPATIBLE'"
        )
        budgets_included = _fetchone(
            conn, "SELECT COUNT(*) FROM historical_budget WHERE learning_status='INCLUDED'"
        )

        lines_non_positive_price = _fetchone(
            conn, "SELECT COUNT(*) FROM historical_partida WHERE COALESCE(precio_unitario, 0) <= 0"
        )
        lines_non_positive_price_in_included = _fetchone(
            conn,
            """SELECT COUNT(*) FROM historical_partida hp
               JOIN historical_budget hb ON hb.id = hp.historical_budget_id
               WHERE COALESCE(hp.precio_unitario, 0) <= 0
                 AND hb.learning_status = 'INCLUDED'""",
        )

        # Fixes histórico evidenciado, Tarea 7: visibilidad de la misma
        # categorización de elegibilidad que usa rebuild_historical_patterns
        # (Tarea 2/4: is_price_eligible) y de duplicados por hash (Tarea 1),
        # para decidir si conviene revisar antes de --apply.
        lines_price_eligible = _fetchone(
            conn,
            """SELECT COUNT(*) FROM historical_partida_feature
               WHERE line_kind='atomic'
                 AND unit IS NOT NULL AND unit<>''
                 AND action IS NOT NULL AND action<>''
                 AND element IS NOT NULL AND element<>''
                 AND primary_module_id IS NOT NULL AND primary_module_id<>''""",
        )
        lines_composite = _fetchone(
            conn, "SELECT COUNT(*) FROM historical_partida_feature WHERE line_kind='composite'"
        )
        duplicate_file_hashes = _fetchone(
            conn,
            """SELECT COUNT(*) FROM (
                   SELECT file_sha256 FROM historical_budget
                   WHERE file_sha256 IS NOT NULL AND file_sha256 <> ''
                   GROUP BY file_sha256 HAVING COUNT(*) > 1
               )""",
        )

    return {
        "lines_total": lines_total,
        "lines_unclassified": lines_unclassified,
        "lines_multimodule": lines_multimodule,
        "module_assignments_total": module_assignments_total,
        "patterns": patterns,
        "patterns_freq_ge_2": patterns_freq_ge_2,
        "patterns_freq_ge_6": patterns_freq_ge_6,
        "budgets_total": budgets_total,
        "budgets_not_compatible": budgets_not_compatible,
        "budgets_included": budgets_included,
        "lines_non_positive_price": lines_non_positive_price,
        "lines_non_positive_price_in_included": lines_non_positive_price_in_included,
        "lines_price_eligible": lines_price_eligible,
        "lines_composite": lines_composite,
        "duplicate_file_hashes": duplicate_file_hashes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Ruta al fichero .db a auditar (solo lectura)")
    args = parser.parse_args()

    report = build_audit_report(args.db)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
