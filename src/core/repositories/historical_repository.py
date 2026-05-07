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
                      num_partidas, analysis_run_id, analisis_ok, warning_count, warnings, error
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
        "error": row[19] or "",
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
                    analysis_run_id, analisis_ok, warning_count, warnings, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                       spp.frecuencia, spp.confianza
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
