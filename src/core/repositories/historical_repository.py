"""
Repositorio para análisis y sugerencias históricas de presupuestos.
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.core import database
from src.core.repositories._common import _mensaje_integridad


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_analysis_run(carpeta_origen: str) -> Tuple[Optional[int], Optional[str]]:
    with database.get_connection() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO historical_analysis_run
                   (fecha_inicio, carpeta_origen, estado)
                   VALUES (?, ?, ?)""",
                (_now_str(), (carpeta_origen or "").strip() or None, "running"),
            )
            conn.commit()
            return (cur.lastrowid, None)
        except sqlite3.OperationalError as e:
            conn.rollback()
            return (None, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}.")


def finish_analysis_run(run_id: int, summary: Dict) -> Optional[str]:
    with database.get_connection() as conn:
        try:
            conn.execute(
                """UPDATE historical_analysis_run
                   SET fecha_fin=?, total_archivos=?, archivos_procesados=?,
                       archivos_omitidos=?, archivos_error=?, estado=?, error=?
                   WHERE id=?""",
                (
                    _now_str(),
                    int(summary.get("total_archivos", 0)),
                    int(summary.get("procesados", 0)),
                    int(summary.get("omitidos", 0)),
                    int(summary.get("errores", 0)),
                    (summary.get("estado") or "finished"),
                    (summary.get("error") or None),
                    run_id,
                ),
            )
            conn.commit()
            return None
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def get_historical_budget_by_path(ruta_excel: str) -> Optional[Dict]:
    ruta = (ruta_excel or "").strip()
    if not ruta:
        return None
    with database.get_connection(read_only=True) as conn:
        cur = conn.execute(
            """SELECT id, ruta_excel, ruta_carpeta, numero_proyecto, nombre_proyecto,
                      cliente, localidad, tipo_obra_original, tipo_obra_normalizado, estado,
                      total, fecha_presupuesto, fecha_modificacion_excel, fecha_analisis,
                      num_partidas, analysis_run_id, analisis_ok, warning_count, warnings,
                      analysis_status, compatible_score, selected_sheet, selected_sheet_index,
                      expected_numero, detected_numero, numero_matches, usable_for_learning,
                      learning_status, learning_status_source, learning_decision_reason,
                      learning_decision_at, analyzer_version, probe_version, reader_version,
                      quality_rules_version, classifier_version, probe_diagnostics_json,
                      header_score, partida_score, error
               FROM historical_budget WHERE ruta_excel=?""",
            (ruta,),
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "ruta_excel": row[1] or "",
        "ruta_carpeta": row[2] or "",
        "numero_proyecto": row[3] or "",
        "nombre_proyecto": row[4] or "",
        "cliente": row[5] or "",
        "localidad": row[6] or "",
        "tipo_obra_original": row[7] or "",
        "tipo_obra_normalizado": row[8] or "",
        "estado": row[9] or "",
        "total": row[10],
        "fecha_presupuesto": row[11] or "",
        "fecha_modificacion_excel": row[12] or "",
        "fecha_analisis": row[13] or "",
        "num_partidas": int(row[14] or 0),
        "analysis_run_id": row[15],
        "analisis_ok": bool(row[16]),
        "warning_count": int(row[17] or 0),
        "warnings": row[18] or "",
        "analysis_status": row[19] or "",
        "compatible_score": int(row[20] or 0),
        "selected_sheet": row[21] or "",
        "selected_sheet_index": row[22],
        "expected_numero": row[23] or "",
        "detected_numero": row[24] or "",
        "numero_matches": bool(row[25]),
        "usable_for_learning": bool(row[26]),
        "learning_status": row[27] or "",
        "learning_status_source": row[28] or "",
        "learning_decision_reason": row[29] or "",
        "learning_decision_at": row[30] or "",
        "analyzer_version": row[31] or "",
        "probe_version": row[32] or "",
        "reader_version": row[33] or "",
        "quality_rules_version": row[34] or "",
        "classifier_version": row[35] or "",
        "probe_diagnostics_json": row[36] or "",
        "header_score": int(row[37] or 0),
        "partida_score": int(row[38] or 0),
        "error": row[39] or "",
    }


def upsert_historical_budget(data: Dict) -> Tuple[Optional[int], Optional[str]]:
    ruta = (data.get("ruta_excel") or "").strip()
    fecha_mod = (data.get("fecha_modificacion_excel") or "").strip()
    if not ruta or not fecha_mod:
        return (None, "ruta_excel y fecha_modificacion_excel son obligatorios.")
    with database.get_connection() as conn:
        try:
            conn.execute(
                """INSERT INTO historical_budget
                   (ruta_excel, ruta_carpeta, numero_proyecto, nombre_proyecto, cliente,
                    localidad, tipo_obra_original, tipo_obra_normalizado, estado, total,
                    fecha_presupuesto, fecha_modificacion_excel, fecha_analisis, num_partidas,
                    analysis_run_id, analisis_ok, warning_count, warnings, analysis_status,
                    compatible_score, selected_sheet, selected_sheet_index, expected_numero,
                    detected_numero, numero_matches, usable_for_learning, learning_status,
                    learning_status_source, learning_decision_reason, learning_decision_at,
                    analyzer_version, probe_version, reader_version, quality_rules_version,
                    classifier_version, probe_diagnostics_json, header_score, partida_score, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(ruta_excel) DO UPDATE SET
                       ruta_carpeta=excluded.ruta_carpeta,
                       numero_proyecto=excluded.numero_proyecto,
                       nombre_proyecto=excluded.nombre_proyecto,
                       cliente=excluded.cliente,
                       localidad=excluded.localidad,
                       tipo_obra_original=excluded.tipo_obra_original,
                       tipo_obra_normalizado=excluded.tipo_obra_normalizado,
                       estado=excluded.estado,
                       total=excluded.total,
                       fecha_presupuesto=excluded.fecha_presupuesto,
                       fecha_modificacion_excel=excluded.fecha_modificacion_excel,
                       fecha_analisis=excluded.fecha_analisis,
                       num_partidas=excluded.num_partidas,
                       analysis_run_id=excluded.analysis_run_id,
                       analisis_ok=excluded.analisis_ok,
                       warning_count=excluded.warning_count,
                       warnings=excluded.warnings,
                       analysis_status=excluded.analysis_status,
                       compatible_score=excluded.compatible_score,
                       selected_sheet=excluded.selected_sheet,
                       selected_sheet_index=excluded.selected_sheet_index,
                       expected_numero=excluded.expected_numero,
                       detected_numero=excluded.detected_numero,
                       numero_matches=excluded.numero_matches,
                       usable_for_learning=excluded.usable_for_learning,
                       learning_status=excluded.learning_status,
                       learning_status_source=excluded.learning_status_source,
                       learning_decision_reason=excluded.learning_decision_reason,
                       learning_decision_at=excluded.learning_decision_at,
                       analyzer_version=excluded.analyzer_version,
                       probe_version=excluded.probe_version,
                       reader_version=excluded.reader_version,
                       quality_rules_version=excluded.quality_rules_version,
                       classifier_version=excluded.classifier_version,
                       probe_diagnostics_json=excluded.probe_diagnostics_json,
                       header_score=excluded.header_score,
                       partida_score=excluded.partida_score,
                       error=excluded.error
                """,
                (
                    ruta,
                    (data.get("ruta_carpeta") or "").strip() or None,
                    (data.get("numero_proyecto") or "").strip() or None,
                    (data.get("nombre_proyecto") or "").strip() or None,
                    (data.get("cliente") or "").strip() or None,
                    (data.get("localidad") or "").strip() or None,
                    (data.get("tipo_obra_original") or "").strip() or None,
                    (data.get("tipo_obra_normalizado") or "").strip() or None,
                    (data.get("estado") or "").strip() or None,
                    data.get("total"),
                    (data.get("fecha_presupuesto") or "").strip() or None,
                    fecha_mod,
                    (data.get("fecha_analisis") or _now_str()),
                    int(data.get("num_partidas", 0)),
                    data.get("analysis_run_id"),
                    1 if data.get("analisis_ok") else 0,
                    int(data.get("warning_count", 0)),
                    (data.get("warnings") or "").strip() or None,
                    (data.get("analysis_status") or "").strip() or None,
                    int(data.get("compatible_score", 0)),
                    (data.get("selected_sheet") or "").strip() or None,
                    data.get("selected_sheet_index"),
                    (data.get("expected_numero") or "").strip() or None,
                    (data.get("detected_numero") or "").strip() or None,
                    1 if data.get("numero_matches") else 0,
                    1 if data.get("usable_for_learning") else 0,
                    (data.get("learning_status") or "").strip() or None,
                    (data.get("learning_status_source") or "").strip() or None,
                    (data.get("learning_decision_reason") or "").strip() or None,
                    (data.get("learning_decision_at") or "").strip() or None,
                    (data.get("analyzer_version") or "").strip() or None,
                    (data.get("probe_version") or "").strip() or None,
                    (data.get("reader_version") or "").strip() or None,
                    (data.get("quality_rules_version") or "").strip() or None,
                    (data.get("classifier_version") or "").strip() or None,
                    (data.get("probe_diagnostics_json") or "").strip() or None,
                    int(data.get("header_score", 0)),
                    int(data.get("partida_score", 0)),
                    (data.get("error") or "").strip() or None,
                ),
            )
            conn.commit()
            cur = conn.execute("SELECT id FROM historical_budget WHERE ruta_excel=?", (ruta,))
            row = cur.fetchone()
            return (row[0] if row else None, None)
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return (None, _mensaje_integridad(e))
        except sqlite3.OperationalError as e:
            conn.rollback()
            return (None, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}.")


def delete_partidas_for_budget(historical_budget_id: int) -> Optional[str]:
    with database.get_connection() as conn:
        try:
            conn.execute("DELETE FROM historical_partida WHERE historical_budget_id=?", (historical_budget_id,))
            conn.commit()
            return None
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def insert_historical_partida(historical_budget_id: int, partida: Dict) -> Tuple[Optional[int], Optional[str]]:
    with database.get_connection() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO historical_partida
                   (historical_budget_id, orden, codigo, titulo, descripcion, concepto_original,
                    concepto_normalizado, unidad, cantidad, precio_unitario, total_linea, capitulo, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    historical_budget_id,
                    partida.get("orden"),
                    (partida.get("codigo") or "").strip() or None,
                    (partida.get("titulo") or "").strip() or None,
                    (partida.get("descripcion") or "").strip() or None,
                    (partida.get("concepto_original") or "").strip() or None,
                    (partida.get("concepto_normalizado") or "").strip() or None,
                    (partida.get("unidad") or "").strip() or None,
                    partida.get("cantidad"),
                    partida.get("precio_unitario"),
                    partida.get("total_linea"),
                    (partida.get("capitulo") or "").strip() or None,
                    _now_str(),
                ),
            )
            conn.commit()
            return (cur.lastrowid, None)
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return (None, _mensaje_integridad(e))
        except sqlite3.OperationalError as e:
            conn.rollback()
            return (None, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}.")


def get_or_create_execution_module(nombre: str, categoria: str = "") -> Tuple[Optional[int], Optional[str]]:
    module_name = (nombre or "").strip().lower()
    if not module_name:
        return (None, "nombre de módulo obligatorio.")
    with database.get_connection() as conn:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO execution_module (nombre, categoria, activo)
                   VALUES (?, ?, 1)""",
                (module_name, (categoria or "").strip() or None),
            )
            conn.commit()
            cur = conn.execute("SELECT id FROM execution_module WHERE nombre=?", (module_name,))
            row = cur.fetchone()
            return (row[0] if row else None, None)
        except sqlite3.OperationalError as e:
            conn.rollback()
            return (None, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}.")


def assign_partida_module(partida_id: int, module_id: int, confidence: float, source: str) -> Optional[str]:
    with database.get_connection() as conn:
        try:
            conn.execute(
                """INSERT INTO historical_partida_module (partida_id, module_id, confidence, source)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(partida_id, module_id) DO UPDATE SET
                       confidence=excluded.confidence,
                       source=excluded.source
                """,
                (partida_id, module_id, confidence, (source or "rules")),
            )
            conn.commit()
            return None
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return _mensaje_integridad(e)
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def rebuild_budget_module_summary(historical_budget_id: int) -> Optional[str]:
    with database.get_connection() as conn:
        try:
            conn.execute("DELETE FROM budget_module_summary WHERE historical_budget_id=?", (historical_budget_id,))
            cur_total = conn.execute(
                "SELECT COALESCE(total, 0) FROM historical_budget WHERE id=?",
                (historical_budget_id,),
            )
            total_budget = float((cur_total.fetchone() or [0])[0] or 0)
            conn.execute(
                """INSERT INTO budget_module_summary (historical_budget_id, module_id, num_partidas, total_importe, porcentaje_presupuesto)
                   SELECT hp.historical_budget_id,
                          hpm.module_id,
                          COUNT(*) AS num_partidas,
                          COALESCE(SUM(COALESCE(hp.total_linea, 0)), 0) AS total_importe,
                          CASE
                              WHEN ? > 0 THEN COALESCE(SUM(COALESCE(hp.total_linea, 0)), 0) / ?
                              ELSE 0
                          END AS porcentaje_presupuesto
                   FROM historical_partida hp
                   JOIN historical_partida_module hpm ON hpm.partida_id = hp.id
                   WHERE hp.historical_budget_id = ?
                   GROUP BY hp.historical_budget_id, hpm.module_id
                """,
                (total_budget, total_budget, historical_budget_id),
            )
            conn.commit()
            return None
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def get_suggestion_patterns_by_modules(module_names: List[str]) -> List[Dict]:
    names = [n.strip().lower() for n in module_names if (n or "").strip()]
    if not names:
        return []
    placeholders = ",".join("?" for _ in names)
    with database.get_connection(read_only=True) as conn:
        cur = conn.execute(
            f"""SELECT spp.id, em.nombre, spp.concepto_normalizado, spp.titulo_sugerido,
                       spp.descripcion_sugerida, spp.unidad_habitual, spp.precio_unitario_medio,
                       spp.precio_unitario_mediana, spp.precio_unitario_min, spp.precio_unitario_max,
                       spp.frecuencia, spp.confianza, spp.pattern_build_run, spp.pattern_source
                FROM suggested_partida_pattern spp
                JOIN execution_module em ON em.id = spp.module_id
                WHERE em.nombre IN ({placeholders}) AND spp.activo = 1
                ORDER BY spp.confianza DESC, spp.frecuencia DESC
                LIMIT 50""",
            names,
        )
        rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "module": r[1] or "",
            "concepto_normalizado": r[2] or "",
            "titulo_sugerido": r[3] or "",
            "descripcion_sugerida": r[4] or "",
            "unidad_habitual": r[5] or "",
            "precio_unitario_medio": r[6],
            "precio_unitario_mediana": r[7],
            "precio_unitario_min": r[8],
            "precio_unitario_max": r[9],
            "frecuencia": int(r[10] or 0),
            "confianza": float(r[11] or 0),
            "pattern_build_run": r[12] or "",
            "pattern_source": r[13] or "",
        }
        for r in rows
    ]


def get_templates_by_work_type(tipo_obra_normalizado: str) -> List[Dict]:
    tipo = (tipo_obra_normalizado or "").strip().lower()
    with database.get_connection(read_only=True) as conn:
        cur = conn.execute(
            """SELECT id, nombre, tipo_obra_normalizado, descripcion, min_confidence,
                      num_presupuestos_base, fecha_actualizacion, activo
               FROM suggestion_template
               WHERE activo = 1 AND (tipo_obra_normalizado = ? OR ? = '')
               ORDER BY num_presupuestos_base DESC, min_confidence DESC""",
            (tipo, tipo),
        )
        rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "nombre": r[1] or "",
            "tipo_obra_normalizado": r[2] or "",
            "descripcion": r[3] or "",
            "min_confidence": float(r[4] or 0),
            "num_presupuestos_base": int(r[5] or 0),
            "fecha_actualizacion": r[6] or "",
            "activo": bool(r[7]),
        }
        for r in rows
    ]


def replace_budget_issues(historical_budget_id: int, issues: List[Dict]) -> Optional[str]:
    with database.get_connection() as conn:
        try:
            conn.execute(
                "DELETE FROM historical_budget_issue WHERE historical_budget_id=?",
                (historical_budget_id,),
            )
            for issue in issues:
                conn.execute(
                    """INSERT INTO historical_budget_issue
                       (historical_budget_id, severity, code, message, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        historical_budget_id,
                        (issue.get("severity") or "WARN"),
                        (issue.get("code") or "UNSPECIFIED"),
                        (issue.get("message") or "").strip(),
                        _now_str(),
                    ),
                )
            conn.commit()
            return None
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def append_budget_issue(historical_budget_id: int, issue: Dict) -> Optional[str]:
    with database.get_connection() as conn:
        try:
            conn.execute(
                """INSERT INTO historical_budget_issue
                   (historical_budget_id, severity, code, message, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    historical_budget_id,
                    (issue.get("severity") or "WARN"),
                    (issue.get("code") or "UNSPECIFIED"),
                    (issue.get("message") or "").strip(),
                    _now_str(),
                ),
            )
            conn.commit()
            return None
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def list_historical_budgets_by_run(analysis_run_id: int) -> List[Dict]:
    with database.get_connection(read_only=True) as conn:
        cur = conn.execute(
            """SELECT id, ruta_excel, numero_proyecto, total, num_partidas, warning_count,
                      analysis_status, selected_sheet, expected_numero, detected_numero,
                      numero_matches, usable_for_learning, compatible_score,
                      learning_status, learning_status_source, learning_decision_reason,
                      learning_decision_at
               FROM historical_budget
               WHERE analysis_run_id=?
               ORDER BY ruta_excel ASC""",
            (analysis_run_id,),
        )
        rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "ruta_excel": r[1] or "",
            "numero_proyecto": r[2] or "",
            "total": float(r[3] or 0.0),
            "num_partidas": int(r[4] or 0),
            "warning_count": int(r[5] or 0),
            "analysis_status": r[6] or "",
            "selected_sheet": r[7] or "",
            "expected_numero": r[8] or "",
            "detected_numero": r[9] or "",
            "numero_matches": bool(r[10]),
            "usable_for_learning": bool(r[11]),
            "compatible_score": int(r[12] or 0),
            "learning_status": r[13] or "",
            "learning_status_source": r[14] or "",
            "learning_decision_reason": r[15] or "",
            "learning_decision_at": r[16] or "",
        }
        for r in rows
    ]


def get_historical_budget_issues(historical_budget_id: int) -> List[Dict]:
    with database.get_connection(read_only=True) as conn:
        cur = conn.execute(
            """SELECT severity, code, message, created_at
               FROM historical_budget_issue
               WHERE historical_budget_id=?
               ORDER BY id ASC""",
            (historical_budget_id,),
        )
        rows = cur.fetchall()
    return [
        {
            "severity": r[0] or "",
            "code": r[1] or "",
            "message": r[2] or "",
            "created_at": r[3] or "",
        }
        for r in rows
    ]


def get_historical_budget_partidas(historical_budget_id: int, limit: int = 200) -> List[Dict]:
    safe_limit = max(1, int(limit or 200))
    with database.get_connection(read_only=True) as conn:
        cur = conn.execute(
            """SELECT orden, codigo, concepto_original, unidad, cantidad, precio_unitario, total_linea
               FROM historical_partida
               WHERE historical_budget_id=?
               ORDER BY orden ASC
               LIMIT ?""",
            (historical_budget_id, safe_limit),
        )
        rows = cur.fetchall()
    return [
        {
            "orden": int(r[0] or 0),
            "codigo": r[1] or "",
            "concepto_original": r[2] or "",
            "unidad": r[3] or "",
            "cantidad": float(r[4] or 0.0),
            "precio_unitario": float(r[5] or 0.0),
            "total_linea": float(r[6] or 0.0),
        }
        for r in rows
    ]


def set_historical_budget_manual_status(
    historical_budget_id: int,
    analysis_status: str,
    usable_for_learning: bool,
) -> Optional[str]:
    with database.get_connection() as conn:
        try:
            conn.execute(
                """UPDATE historical_budget
                   SET analysis_status=?,
                       usable_for_learning=?,
                       fecha_analisis=?
                   WHERE id=?""",
                (
                    (analysis_status or "").strip() or None,
                    1 if usable_for_learning else 0,
                    _now_str(),
                    historical_budget_id,
                ),
            )
            conn.commit()
            return None
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def set_historical_budget_learning_status(
    historical_budget_id: int,
    learning_status: str,
    usable_for_learning: bool,
    decision_source: str = "MANUAL",
    decision_reason: str = "",
) -> Optional[str]:
    with database.get_connection() as conn:
        try:
            target_status = (learning_status or "").strip().upper()
            wants_learning = target_status == "INCLUDED" or bool(usable_for_learning)
            if wants_learning:
                cur = conn.execute(
                    "SELECT analysis_status FROM historical_budget WHERE id=?",
                    (historical_budget_id,),
                )
                row = cur.fetchone()
                if not row:
                    return "No se encontro el presupuesto historico indicado."
                analysis_status = (row[0] or "").strip().upper()
                if analysis_status not in ("VALID", "VALID_WITH_WARNINGS"):
                    return (
                        "No se puede incluir en memoria: el estado tecnico del "
                        f"presupuesto es {analysis_status or 'desconocido'}."
                    )
            conn.execute(
                """UPDATE historical_budget
                   SET learning_status=?,
                       learning_status_source=?,
                       learning_decision_reason=?,
                       learning_decision_at=?,
                       usable_for_learning=?,
                       fecha_analisis=?
                   WHERE id=?""",
                (
                    (learning_status or "").strip() or None,
                    (decision_source or "").strip() or None,
                    (decision_reason or "").strip() or None,
                    _now_str(),
                    1 if usable_for_learning else 0,
                    _now_str(),
                    historical_budget_id,
                ),
            )
            conn.commit()
            return None
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def get_historical_learning_metrics(analysis_run_id: Optional[int] = None) -> Dict:
    with database.get_connection(read_only=True) as conn:
        if analysis_run_id:
            cur_budgets = conn.execute(
                """SELECT COUNT(*)
                   FROM historical_budget
                   WHERE analysis_run_id=?
                     AND usable_for_learning=1
                     AND analysis_status IN ('VALID', 'VALID_WITH_WARNINGS')""",
                (analysis_run_id,),
            )
            presupuestos_usados = int((cur_budgets.fetchone() or [0])[0] or 0)
            cur_partidas = conn.execute(
                """SELECT COUNT(*)
                   FROM historical_partida hp
                   JOIN historical_budget hb ON hb.id = hp.historical_budget_id
                   WHERE hb.analysis_run_id=?
                     AND hb.usable_for_learning=1
                     AND hb.analysis_status IN ('VALID', 'VALID_WITH_WARNINGS')
                     AND COALESCE(hp.precio_unitario, 0) > 0""",
                (analysis_run_id,),
            )
        else:
            cur_budgets = conn.execute(
                """SELECT COUNT(*)
                   FROM historical_budget
                   WHERE usable_for_learning=1
                     AND analysis_status IN ('VALID', 'VALID_WITH_WARNINGS')"""
            )
            presupuestos_usados = int((cur_budgets.fetchone() or [0])[0] or 0)
            cur_partidas = conn.execute(
                """SELECT COUNT(*)
                   FROM historical_partida hp
                   JOIN historical_budget hb ON hb.id = hp.historical_budget_id
                   WHERE hb.usable_for_learning=1
                     AND hb.analysis_status IN ('VALID', 'VALID_WITH_WARNINGS')
                     AND COALESCE(hp.precio_unitario, 0) > 0"""
            )
        partidas_utiles = int((cur_partidas.fetchone() or [0])[0] or 0)

        cur_patterns = conn.execute("SELECT COUNT(*) FROM suggested_partida_pattern WHERE activo=1")
        patrones_generados = int((cur_patterns.fetchone() or [0])[0] or 0)

    return {
        "presupuestos_usados": presupuestos_usados,
        "partidas_utiles": partidas_utiles,
        "patrones_generados": patrones_generados,
    }


def get_historical_memory_dashboard_metrics() -> Dict:
    """Devuelve KPIs globales de memoria historica para el panel de control."""
    with database.get_connection(read_only=True) as conn:
        budget_row = conn.execute(
            """SELECT
                   COUNT(*),
                   SUM(CASE WHEN analysis_status='VALID' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN analysis_status='VALID_WITH_WARNINGS' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN analysis_status='EXCLUDED_INCOMPLETE_DATA' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN analysis_status='NOT_COMPATIBLE' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN analysis_status='READ_ERROR' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN learning_status='INCLUDED' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN learning_status='PENDING_REVIEW' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN learning_status='EXCLUDED' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN learning_status='NOT_ELIGIBLE' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN COALESCE(warning_count, 0) > 0 THEN 1 ELSE 0 END)
               FROM historical_budget"""
        ).fetchone() or [0] * 11
        partidas = conn.execute("SELECT COUNT(*) FROM historical_partida").fetchone()
        patterns = conn.execute(
            """SELECT
                   COUNT(*),
                   SUM(CASE WHEN src.sources_count > 0 THEN 1 ELSE 0 END)
               FROM suggested_partida_pattern p
               LEFT JOIN (
                   SELECT pattern_id, COUNT(*) AS sources_count
                     FROM suggested_partida_pattern_source
                    GROUP BY pattern_id
               ) src ON src.pattern_id = p.id
               WHERE p.activo=1"""
        ).fetchone() or [0, 0]
    return {
        "total_budgets": int(budget_row[0] or 0),
        "valid": int(budget_row[1] or 0),
        "valid_with_warnings": int(budget_row[2] or 0),
        "invalid": int(budget_row[3] or 0),
        "not_compatible": int(budget_row[4] or 0),
        "read_error": int(budget_row[5] or 0),
        "included": int(budget_row[6] or 0),
        "pending_review": int(budget_row[7] or 0),
        "excluded": int(budget_row[8] or 0),
        "not_eligible": int(budget_row[9] or 0),
        "with_warnings": int(budget_row[10] or 0),
        "historical_partidas": int((partidas or [0])[0] or 0),
        "active_patterns": int(patterns[0] or 0),
        "patterns_with_sources": int(patterns[1] or 0),
    }


def list_historical_memory_dashboard_budgets(
    filters: Optional[Dict] = None,
    limit: int = 1000,
) -> List[Dict]:
    """Lista presupuestos historicos con datos agregados para el panel global."""
    filters = filters or {}
    safe_limit = max(1, min(int(limit or 1000), 5000))
    where = []
    having = []
    params: List[object] = []

    analysis_status = (filters.get("analysis_status") or "").strip()
    if analysis_status:
        where.append("hb.analysis_status=?")
        params.append(analysis_status)

    learning_status = (filters.get("learning_status") or "").strip()
    if learning_status:
        where.append("hb.learning_status=?")
        params.append(learning_status)

    search = (filters.get("search") or "").strip().lower()
    if search:
        where.append(
            """(LOWER(COALESCE(hb.ruta_excel, '')) LIKE ?
                OR LOWER(COALESCE(hb.nombre_proyecto, '')) LIKE ?
                OR LOWER(COALESCE(hb.numero_proyecto, '')) LIKE ?
                OR LOWER(COALESCE(hb.cliente, '')) LIKE ?)"""
        )
        like = f"%{search}%"
        params.extend([like, like, like, like])

    if filters.get("only_problems"):
        where.append(
            """(hb.analysis_status IN ('VALID_WITH_WARNINGS', 'EXCLUDED_INCOMPLETE_DATA', 'NOT_COMPATIBLE', 'READ_ERROR')
                OR hb.learning_status IN ('PENDING_REVIEW', 'NOT_ELIGIBLE')
                OR COALESCE(hb.warning_count, 0) > 0
                OR hb.learning_status IS NULL
                OR hb.learning_status='')"""
        )
    if filters.get("with_warnings"):
        where.append("COALESCE(hb.warning_count, 0) > 0")

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    if filters.get("no_modules"):
        having.append("COUNT(DISTINCT em.id)=0")
    if filters.get("no_partidas"):
        having.append("(COUNT(DISTINCT hp.id)=0 OR COALESCE(hb.num_partidas,0)=0)")
    if filters.get("no_related_patterns"):
        having.append("COUNT(DISTINCT spp.id)=0")
    having_sql = f"HAVING {' AND '.join(having)}" if having else ""
    params.append(safe_limit)
    with database.get_connection(read_only=True) as conn:
        cur = conn.execute(
            f"""SELECT
                    hb.id,
                    hb.ruta_excel,
                    hb.numero_proyecto,
                    hb.nombre_proyecto,
                    hb.cliente,
                    hb.total,
                    hb.analysis_status,
                    hb.learning_status,
                    hb.usable_for_learning,
                    hb.warning_count,
                    hb.num_partidas,
                    hb.fecha_analisis,
                    hb.selected_sheet,
                    hb.compatible_score,
                    hb.probe_diagnostics_json,
                    COALESCE(GROUP_CONCAT(DISTINCT em.nombre), '') AS modules,
                    COUNT(DISTINCT em.id) AS module_count,
                    COUNT(DISTINCT hp.id) AS persisted_partidas,
                    COUNT(DISTINCT spp.id) AS related_patterns
               FROM historical_budget hb
               LEFT JOIN historical_partida hp ON hp.historical_budget_id = hb.id
               LEFT JOIN historical_partida_module hpm ON hpm.partida_id = hp.id
               LEFT JOIN execution_module em ON em.id = hpm.module_id
               LEFT JOIN suggested_partida_pattern_source spps ON spps.historical_budget_id = hb.id
               LEFT JOIN suggested_partida_pattern spp ON spp.id = spps.pattern_id AND spp.activo = 1
               {where_sql}
               GROUP BY hb.id
               {having_sql}
               ORDER BY hb.fecha_analisis DESC, hb.ruta_excel ASC
               LIMIT ?""",
            tuple(params),
        )
        rows = cur.fetchall()
    return [
        {
            "id": int(r[0]),
            "ruta_excel": r[1] or "",
            "numero_proyecto": r[2] or "",
            "nombre_proyecto": r[3] or "",
            "cliente": r[4] or "",
            "total": float(r[5] or 0.0),
            "analysis_status": r[6] or "",
            "learning_status": r[7] or "",
            "usable_for_learning": bool(r[8]),
            "warning_count": int(r[9] or 0),
            "num_partidas": int(r[10] or 0),
            "fecha_analisis": r[11] or "",
            "selected_sheet": r[12] or "",
            "compatible_score": int(r[13] or 0),
            "probe_diagnostics_json": r[14] or "",
            "modules": [m for m in (r[15] or "").split(",") if m],
            "module_count": int(r[16] or 0),
            "persisted_partidas": int(r[17] or 0),
            "related_patterns": int(r[18] or 0),
        }
        for r in rows
    ]


def get_historical_partidas_for_classification(historical_budget_id: int) -> List[Dict]:
    with database.get_connection(read_only=True) as conn:
        cur = conn.execute(
            """SELECT id, COALESCE(concepto_original, ''), COALESCE(titulo, ''), COALESCE(capitulo, '')
               FROM historical_partida
               WHERE historical_budget_id=?
               ORDER BY orden ASC""",
            (historical_budget_id,),
        )
        rows = cur.fetchall()
    return [
        {
            "id": int(r[0]),
            "concepto_original": r[1] or "",
            "titulo": r[2] or "",
            "capitulo": r[3] or "",
        }
        for r in rows
    ]


def clear_historical_partida_modules_for_budget(historical_budget_id: int) -> Optional[str]:
    with database.get_connection() as conn:
        try:
            conn.execute(
                """DELETE FROM historical_partida_module
                   WHERE partida_id IN (
                       SELECT id FROM historical_partida WHERE historical_budget_id=?
                   )""",
                (historical_budget_id,),
            )
            conn.execute("DELETE FROM budget_module_summary WHERE historical_budget_id=?", (historical_budget_id,))
            conn.commit()
            return None
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."
