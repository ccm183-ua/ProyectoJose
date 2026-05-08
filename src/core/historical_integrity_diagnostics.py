"""
Diagnosticos de integridad para memoria historica y patrones.
"""

import sqlite3
from pathlib import Path
from typing import Dict, List

from src.core import database
from src.core.historical_issue_catalog import KNOWN_HISTORICAL_ISSUE_CODES


REQUIRED_HISTORICAL_TABLES = {
    "historical_budget",
    "historical_budget_issue",
    "historical_partida",
    "historical_partida_module",
    "execution_module",
    "suggested_partida_pattern",
    "historical_pattern_build_run",
    "suggested_partida_pattern_source",
}


def diagnose_historical_integrity(limit_per_check: int = 100) -> Dict:
    """Ejecuta comprobaciones de integridad sin modificar la base de datos."""
    db_path = database.get_db_path()
    result = {
        "db_path": str(db_path),
        "schema_ok": False,
        "missing_tables": [],
        "findings": [],
        "counts": {},
    }
    if not Path(db_path).exists():
        result["missing_tables"] = sorted(REQUIRED_HISTORICAL_TABLES)
        result["findings"].append(
            _finding(
                category="schema",
                check="database_missing",
                severity="ERROR",
                message="No existe el fichero de base de datos.",
            )
        )
        return result

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        existing_tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        missing = sorted(REQUIRED_HISTORICAL_TABLES - existing_tables)
        result["missing_tables"] = missing
        result["schema_ok"] = not missing
        if missing:
            result["findings"].append(
                _finding(
                    category="schema",
                    check="missing_historical_tables",
                    severity="ERROR",
                    message=f"Faltan tablas historicas: {', '.join(missing)}.",
                    data={"missing_tables": missing},
                )
            )
            return result

        for table_name in sorted(REQUIRED_HISTORICAL_TABLES):
            result["counts"][table_name] = _count(conn, table_name)

        checks = _budget_checks() + _partida_checks() + _pattern_checks() + _issue_checks()
        for check in checks:
            rows = conn.execute(check["sql"], check.get("params", ())).fetchmany(limit_per_check)
            for row in rows:
                result["findings"].append(
                    _finding(
                        category=check["category"],
                        check=check["check"],
                        severity=check["severity"],
                        message=check["message"],
                        table=check.get("table", ""),
                        row_id=_row_identifier(row),
                        data=dict(row),
                    )
                )
    finally:
        conn.close()

    return result


def _count(conn: sqlite3.Connection, table_name: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0] or 0)


def _row_identifier(row: sqlite3.Row):
    for key in ("id", "historical_budget_id", "pattern_id", "historical_partida_id"):
        if key in row.keys() and row[key] is not None:
            return row[key]
    return None


def _finding(
    *,
    category: str,
    check: str,
    severity: str,
    message: str,
    table: str = "",
    row_id=None,
    data: Dict | None = None,
) -> Dict:
    return {
        "category": category,
        "check": check,
        "severity": severity,
        "message": message,
        "table": table,
        "row_id": row_id,
        "data": data or {},
    }


def _budget_checks() -> List[Dict]:
    return [
        {
            "category": "budgets",
            "check": "included_invalid_analysis_status",
            "severity": "ERROR",
            "table": "historical_budget",
            "message": "Presupuesto incluido en memoria con estado tecnico no valido.",
            "sql": """
                SELECT id, ruta_excel, analysis_status, learning_status, usable_for_learning, num_partidas, total
                FROM historical_budget
                WHERE learning_status='INCLUDED'
                  AND COALESCE(analysis_status,'') NOT IN ('VALID','VALID_WITH_WARNINGS')
            """,
        },
        {
            "category": "budgets",
            "check": "included_without_partidas",
            "severity": "ERROR",
            "table": "historical_budget",
            "message": "Presupuesto incluido en memoria sin partidas persistidas.",
            "sql": """
                SELECT hb.id, hb.ruta_excel, hb.num_partidas, hb.total
                FROM historical_budget hb
                LEFT JOIN historical_partida hp ON hp.historical_budget_id=hb.id
                WHERE hb.learning_status='INCLUDED'
                GROUP BY hb.id
                HAVING COUNT(hp.id)=0
            """,
        },
        {
            "category": "budgets",
            "check": "included_zero_total",
            "severity": "WARN",
            "table": "historical_budget",
            "message": "Presupuesto incluido con total cero o no detectado.",
            "sql": """
                SELECT id, ruta_excel, total, analysis_status, learning_status
                FROM historical_budget
                WHERE learning_status='INCLUDED'
                  AND COALESCE(total,0)<=0
            """,
        },
        {
            "category": "budgets",
            "check": "pending_review_used_in_patterns",
            "severity": "ERROR",
            "table": "historical_budget",
            "message": "Presupuesto pendiente de revision usado como fuente de patrones.",
            "sql": """
                SELECT DISTINCT hb.id, hb.ruta_excel, hb.analysis_status, hb.learning_status
                FROM suggested_partida_pattern_source s
                JOIN historical_budget hb ON hb.id=s.historical_budget_id
                WHERE hb.learning_status='PENDING_REVIEW'
            """,
        },
        {
            "category": "budgets",
            "check": "not_eligible_marked_usable",
            "severity": "ERROR",
            "table": "historical_budget",
            "message": "Presupuesto no apto marcado como usable_for_learning.",
            "sql": """
                SELECT id, ruta_excel, analysis_status, learning_status, usable_for_learning
                FROM historical_budget
                WHERE learning_status='NOT_ELIGIBLE'
                  AND usable_for_learning=1
            """,
        },
        {
            "category": "budgets",
            "check": "null_or_incoherent_learning_status",
            "severity": "WARN",
            "table": "historical_budget",
            "message": "Presupuesto con learning_status nulo o fuera del catalogo.",
            "sql": """
                SELECT id, ruta_excel, analysis_status, learning_status, usable_for_learning
                FROM historical_budget
                WHERE learning_status IS NULL
                   OR learning_status NOT IN ('INCLUDED','PENDING_REVIEW','EXCLUDED','NOT_ELIGIBLE')
            """,
        },
        {
            "category": "budgets",
            "check": "duplicate_detected_budget_key",
            "severity": "WARN",
            "table": "historical_budget",
            "message": "Posible duplicado por numero detectado, cliente y total.",
            "sql": """
                SELECT MIN(id) AS id, detected_numero, cliente, ROUND(COALESCE(total,0),2) AS total_key, COUNT(*) AS duplicates
                FROM historical_budget
                WHERE COALESCE(detected_numero,'')<>'' OR COALESCE(cliente,'')<>''
                GROUP BY detected_numero, cliente, ROUND(COALESCE(total,0),2)
                HAVING COUNT(*)>1
            """,
        },
        {
            "category": "budgets",
            "check": "missing_probe_diagnostics",
            "severity": "WARN",
            "table": "historical_budget",
            "message": "Presupuesto analizado sin diagnostico estructurado del probe.",
            "sql": """
                SELECT id, ruta_excel, analysis_status, analyzer_version, probe_diagnostics_json
                FROM historical_budget
                WHERE COALESCE(analyzer_version,'')<>''
                  AND COALESCE(probe_diagnostics_json,'')=''
            """,
        },
    ]


def _partida_checks() -> List[Dict]:
    return [
        {
            "category": "partidas",
            "check": "missing_concept",
            "severity": "ERROR",
            "table": "historical_partida",
            "message": "Partida sin concepto original ni normalizado.",
            "sql": """
                SELECT id, historical_budget_id, codigo, concepto_original, concepto_normalizado
                FROM historical_partida
                WHERE TRIM(COALESCE(concepto_original,''))=''
                  AND TRIM(COALESCE(concepto_normalizado,''))=''
            """,
        },
        {
            "category": "partidas",
            "check": "non_positive_price",
            "severity": "WARN",
            "table": "historical_partida",
            "message": "Partida con precio unitario cero o negativo.",
            "sql": """
                SELECT id, historical_budget_id, concepto_original, precio_unitario
                FROM historical_partida
                WHERE COALESCE(precio_unitario,0)<=0
            """,
        },
        {
            "category": "partidas",
            "check": "zero_quantity",
            "severity": "WARN",
            "table": "historical_partida",
            "message": "Partida con cantidad cero o negativa.",
            "sql": """
                SELECT id, historical_budget_id, concepto_original, cantidad
                FROM historical_partida
                WHERE COALESCE(cantidad,0)<=0
            """,
        },
        {
            "category": "partidas",
            "check": "looks_like_total_or_header",
            "severity": "WARN",
            "table": "historical_partida",
            "message": "Partida que parece total, IVA, base imponible o cabecera.",
            "sql": """
                SELECT id, historical_budget_id, codigo, concepto_original, concepto_normalizado
                FROM historical_partida
                WHERE LOWER(COALESCE(concepto_normalizado,'')) LIKE '%total%'
                   OR LOWER(COALESCE(concepto_normalizado,'')) LIKE '%iva%'
                   OR LOWER(COALESCE(concepto_normalizado,'')) LIKE '%base imponible%'
                   OR LOWER(COALESCE(concepto_normalizado,'')) LIKE '%presupuesto%'
            """,
        },
        {
            "category": "partidas",
            "check": "duplicate_partida_in_budget",
            "severity": "WARN",
            "table": "historical_partida",
            "message": "Partidas duplicadas dentro del mismo presupuesto.",
            "sql": """
                SELECT MIN(id) AS id, historical_budget_id, concepto_normalizado, unidad, precio_unitario, COUNT(*) AS duplicates
                FROM historical_partida
                GROUP BY historical_budget_id, concepto_normalizado, unidad, precio_unitario
                HAVING COUNT(*)>1
            """,
        },
        {
            "category": "partidas",
            "check": "pattern_source_from_non_included_budget",
            "severity": "ERROR",
            "table": "suggested_partida_pattern_source",
            "message": "Fuente de patron procedente de presupuesto no incluido o tecnicamente no valido.",
            "sql": """
                SELECT s.pattern_id, s.historical_partida_id, s.historical_budget_id,
                       hb.analysis_status, hb.learning_status
                FROM suggested_partida_pattern_source s
                JOIN historical_budget hb ON hb.id=s.historical_budget_id
                WHERE hb.learning_status<>'INCLUDED'
                   OR hb.analysis_status NOT IN ('VALID','VALID_WITH_WARNINGS')
            """,
        },
        {
            "category": "partidas",
            "check": "included_budget_partida_without_module",
            "severity": "WARN",
            "table": "historical_partida",
            "message": "Partida de presupuesto incluido sin modulo asignado.",
            "sql": """
                SELECT hp.id, hp.historical_budget_id, hp.concepto_original
                FROM historical_partida hp
                JOIN historical_budget hb ON hb.id=hp.historical_budget_id
                LEFT JOIN historical_partida_module hpm ON hpm.partida_id=hp.id
                WHERE hb.learning_status='INCLUDED'
                  AND hb.analysis_status IN ('VALID','VALID_WITH_WARNINGS')
                  AND hpm.partida_id IS NULL
            """,
        },
    ]


def _pattern_checks() -> List[Dict]:
    return [
        {
            "category": "patterns",
            "check": "pattern_without_sources",
            "severity": "ERROR",
            "table": "suggested_partida_pattern",
            "message": "Patron activo sin fuentes.",
            "sql": """
                SELECT spp.id, spp.concepto_normalizado, spp.frecuencia
                FROM suggested_partida_pattern spp
                LEFT JOIN suggested_partida_pattern_source s ON s.pattern_id=spp.id
                WHERE spp.activo=1
                  AND s.pattern_id IS NULL
            """,
        },
        {
            "category": "patterns",
            "check": "orphan_pattern_source",
            "severity": "ERROR",
            "table": "suggested_partida_pattern_source",
            "message": "Fuente de patron con referencias inexistentes.",
            "sql": """
                SELECT s.pattern_id, s.historical_partida_id, s.historical_budget_id
                FROM suggested_partida_pattern_source s
                LEFT JOIN suggested_partida_pattern spp ON spp.id=s.pattern_id
                LEFT JOIN historical_partida hp ON hp.id=s.historical_partida_id
                LEFT JOIN historical_budget hb ON hb.id=s.historical_budget_id
                WHERE spp.id IS NULL OR hp.id IS NULL OR hb.id IS NULL
            """,
        },
        {
            "category": "patterns",
            "check": "low_frequency_pattern",
            "severity": "INFO",
            "table": "suggested_partida_pattern",
            "message": "Patron con frecuencia inferior al minimo usado por sugerencias.",
            "sql": """
                SELECT id, concepto_normalizado, frecuencia, confianza
                FROM suggested_partida_pattern
                WHERE activo=1
                  AND COALESCE(frecuencia,0)<2
            """,
        },
        {
            "category": "patterns",
            "check": "mean_far_from_median",
            "severity": "WARN",
            "table": "suggested_partida_pattern",
            "message": "Precio medio muy alejado de la mediana.",
            "sql": """
                SELECT id, concepto_normalizado, precio_unitario_medio, precio_unitario_mediana
                FROM suggested_partida_pattern
                WHERE COALESCE(precio_unitario_mediana,0)>0
                  AND ABS(precio_unitario_medio - precio_unitario_mediana) / precio_unitario_mediana > 0.5
            """,
        },
        {
            "category": "patterns",
            "check": "excessive_price_range",
            "severity": "WARN",
            "table": "suggested_partida_pattern",
            "message": "Rango de precios excesivo para un mismo patron.",
            "sql": """
                SELECT id, concepto_normalizado, precio_unitario_min, precio_unitario_max
                FROM suggested_partida_pattern
                WHERE COALESCE(precio_unitario_min,0)>0
                  AND precio_unitario_max / precio_unitario_min > 5
            """,
        },
        {
            "category": "patterns",
            "check": "duplicate_pattern_key",
            "severity": "ERROR",
            "table": "suggested_partida_pattern",
            "message": "Patrones duplicados por modulo, concepto normalizado y unidad.",
            "sql": """
                SELECT MIN(id) AS id, module_id, concepto_normalizado, unidad_habitual, COUNT(*) AS duplicates
                FROM suggested_partida_pattern
                WHERE activo=1
                GROUP BY module_id, concepto_normalizado, unidad_habitual
                HAVING COUNT(*)>1
            """,
        },
        {
            "category": "patterns",
            "check": "stale_pattern_build_run",
            "severity": "WARN",
            "table": "suggested_partida_pattern",
            "message": "Patron activo no pertenece a la ultima reconstruccion correcta.",
            "sql": """
                SELECT id, concepto_normalizado, pattern_build_run
                FROM suggested_partida_pattern
                WHERE activo=1
                  AND COALESCE(pattern_build_run,'') <> COALESCE((
                      SELECT id
                      FROM historical_pattern_build_run
                      WHERE error IS NULL
                      ORDER BY finished_at DESC
                      LIMIT 1
                  ), COALESCE(pattern_build_run,''))
            """,
        },
    ]


def _issue_checks() -> List[Dict]:
    known = tuple(sorted(KNOWN_HISTORICAL_ISSUE_CODES))
    placeholders = ",".join("?" for _ in known)
    return [
        {
            "category": "issues",
            "check": "included_with_severe_issue",
            "severity": "ERROR",
            "table": "historical_budget_issue",
            "message": "Presupuesto incluido con incidencias severas o errores.",
            "sql": """
                SELECT hb.id, hb.ruta_excel, i.severity, i.code, i.message
                FROM historical_budget hb
                JOIN historical_budget_issue i ON i.historical_budget_id=hb.id
                WHERE hb.learning_status='INCLUDED'
                  AND i.severity IN ('SEVERE','ERROR')
            """,
        },
        {
            "category": "issues",
            "check": "manual_excluded_without_issue",
            "severity": "WARN",
            "table": "historical_budget",
            "message": "Presupuesto excluido manualmente sin issue manual asociado.",
            "sql": """
                SELECT hb.id, hb.ruta_excel, hb.learning_status, hb.learning_status_source
                FROM historical_budget hb
                WHERE hb.learning_status='EXCLUDED'
                  AND hb.learning_status_source='MANUAL'
                  AND NOT EXISTS (
                      SELECT 1 FROM historical_budget_issue i
                      WHERE i.historical_budget_id=hb.id
                        AND i.code='MANUALLY_EXCLUDED'
                  )
            """,
        },
        {
            "category": "issues",
            "check": "manual_included_without_issue",
            "severity": "WARN",
            "table": "historical_budget",
            "message": "Presupuesto incluido manualmente sin issue manual asociado.",
            "sql": """
                SELECT hb.id, hb.ruta_excel, hb.learning_status, hb.learning_status_source
                FROM historical_budget hb
                WHERE hb.learning_status='INCLUDED'
                  AND hb.learning_status_source='MANUAL'
                  AND NOT EXISTS (
                      SELECT 1 FROM historical_budget_issue i
                      WHERE i.historical_budget_id=hb.id
                        AND i.code='MANUALLY_INCLUDED'
                  )
            """,
        },
        {
            "category": "issues",
            "check": "duplicate_manual_issues",
            "severity": "WARN",
            "table": "historical_budget_issue",
            "message": "Demasiadas incidencias manuales duplicadas.",
            "sql": """
                SELECT MIN(id) AS id, historical_budget_id, code, COUNT(*) AS duplicates
                FROM historical_budget_issue
                WHERE code IN ('MANUALLY_INCLUDED','MANUALLY_EXCLUDED')
                GROUP BY historical_budget_id, code
                HAVING COUNT(*)>1
            """,
        },
        {
            "category": "issues",
            "check": "unknown_issue_code",
            "severity": "WARN",
            "table": "historical_budget_issue",
            "message": "Codigo de issue no reconocido por el catalogo historico.",
            "sql": f"""
                SELECT id, historical_budget_id, severity, code, message
                FROM historical_budget_issue
                WHERE code NOT IN ({placeholders})
            """,
            "params": known,
        },
    ]
