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
    """Informe de solo lectura: nunca escribe, nunca migra el esquema.

    Fixes histórico evidenciado, Tarea 7: además del recuento genérico por
    `line_kind`, categoriza en los tres cubos que importan para decidir si
    aplicar es seguro (eligible_atomic/composite/unknown_or_incomplete),
    cuenta hashes de fichero duplicados (posibles en una BDD anterior a la
    Tarea 1, que no tenía el índice único) y predice cuántos patrones
    resultarían de `HistoricalPatternBuilder.rebuild_patterns()` replicando
    exactamente su consulta de agrupación (_load_groups), sin escribir nada.
    """
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
        eligible_atomic = 0
        composite = 0
        if _table_exists(conn, "historical_partida_feature"):
            line_kinds = dict(
                conn.execute(
                    "SELECT COALESCE(line_kind, 'sin_ficha'), COUNT(*) "
                    "FROM historical_partida_feature GROUP BY 1"
                ).fetchall()
            )
            eligible_atomic, composite = conn.execute(
                """SELECT
                       SUM(CASE WHEN line_kind='atomic'
                                 AND unit IS NOT NULL AND unit<>''
                                 AND action IS NOT NULL AND action<>''
                                 AND element IS NOT NULL AND element<>''
                                 AND primary_module_id IS NOT NULL AND primary_module_id<>''
                                THEN 1 ELSE 0 END),
                       SUM(CASE WHEN line_kind='composite' THEN 1 ELSE 0 END)
                   FROM historical_partida_feature"""
            ).fetchone()
            eligible_atomic = int(eligible_atomic or 0)
            composite = int(composite or 0)
        con_ficha = sum(line_kinds.values())

        duplicate_hashes = 0
        if _table_exists(conn, "historical_budget"):
            columns = {row[1] for row in conn.execute("PRAGMA table_info(historical_budget)")}
            if "file_sha256" in columns:
                duplicate_hashes = conn.execute(
                    """SELECT COUNT(*) FROM (
                           SELECT file_sha256 FROM historical_budget
                           WHERE file_sha256 IS NOT NULL AND file_sha256 <> ''
                           GROUP BY file_sha256 HAVING COUNT(*) > 1
                       )"""
                ).fetchone()[0]

        patterns_after_rebuild = 0
        if _table_exists(conn, "execution_module") and _table_exists(conn, "historical_partida_feature"):
            patterns_after_rebuild = conn.execute(
                """SELECT COUNT(*) FROM (
                       SELECT em.id, hp.concepto_normalizado
                       FROM historical_partida hp
                       JOIN historical_partida_feature f ON f.partida_id = hp.id
                       JOIN historical_budget hb ON hb.id = hp.historical_budget_id
                       JOIN execution_module em ON em.nombre = f.primary_module_id
                       WHERE hp.concepto_normalizado IS NOT NULL AND hp.concepto_normalizado <> ''
                         AND hp.precio_unitario IS NOT NULL AND hp.precio_unitario > 0
                         AND hb.analysis_status IN ('VALID', 'VALID_WITH_WARNINGS')
                         AND hb.learning_status = 'INCLUDED'
                         AND f.line_kind = 'atomic'
                       GROUP BY em.id, hp.concepto_normalizado
                   )"""
            ).fetchone()[0]

    return {
        "schema_version": schema_version,
        "schema_migrada": schema_version >= 3,
        "total_partidas": total_partidas,
        "con_ficha_actual": con_ficha,
        "sin_ficha_actual": total_partidas - con_ficha,
        "would_reclassify": total_partidas,
        "line_kinds_actuales": line_kinds,
        "eligible_atomic": eligible_atomic,
        "composite": composite,
        "unknown_or_incomplete": total_partidas - eligible_atomic - composite,
        "pending_review": pending_review,
        "duplicate_hashes": duplicate_hashes,
        "patrones_actuales": patrones_actuales,
        "patterns_after_rebuild": patterns_after_rebuild,
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
        # Fixes histórico evidenciado, Tarea 7: verificación de integridad
        # post-apply. Cada fuente de patrón debe proceder de un presupuesto
        # INCLUDED, una línea atómica y una ficha con atributos mínimos
        # completos (is_price_eligible=1) — si el pattern builder alguna vez
        # se desvía de esto (Tarea 4/9), el rebuild debe fallar aquí en vez
        # de dejar patrones no evidenciados en la BDD real.
        invalid_sources = conn.execute(
            """SELECT COUNT(*) FROM suggested_partida_pattern_source sps
               JOIN historical_partida hp ON hp.id = sps.historical_partida_id
               JOIN historical_partida_feature f ON f.partida_id = hp.id
               JOIN historical_budget hb ON hb.id = sps.historical_budget_id
               WHERE NOT (
                   hb.learning_status = 'INCLUDED'
                   AND f.line_kind = 'atomic'
                   AND f.unit IS NOT NULL AND f.unit <> ''
                   AND f.action IS NOT NULL AND f.action <> ''
                   AND f.element IS NOT NULL AND f.element <> ''
                   AND f.primary_module_id IS NOT NULL AND f.primary_module_id <> ''
               )"""
        ).fetchone()[0]

    return {
        "fichas_reconstruidas": fichas_reconstruidas,
        "line_kinds_despues": line_kinds_despues,
        "patrones_antes": patrones_antes,
        "patrones_despues": patrones_despues,
        "patrones_eliminados": max(0, patrones_antes - patrones_despues),
        "patrones_creados": pattern_result.get("patterns_inserted", 0),
        "pattern_build_run": pattern_result.get("pattern_build_run", ""),
        "invalid_pattern_sources": invalid_sources,
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

    # Fixes histórico evidenciado, Tarea 7: si hay hashes duplicados (posible
    # en una BDD anterior a la Tarea 1), abortar ANTES de crear backup ni
    # tocar el fichero: hay que revisar y deduplicar a mano primero.
    pre_summary = build_summary(str(db_path))
    if pre_summary["duplicate_hashes"]:
        print(
            json.dumps(
                {"error": "Hay duplicados por hash; revisar antes de aplicar."},
                ensure_ascii=False,
            )
        )
        return 1

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
    if summary.get("invalid_pattern_sources", 0):
        # El backup ya existe y es válido; el original quedó reconstruido
        # pero con patrones que no cumplen el contrato de evidencia. No se
        # deshace automáticamente (el backup permite restaurar a mano):
        # error explícito para que el operador revise antes de confiar en
        # estos patrones.
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
