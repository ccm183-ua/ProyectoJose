"""
Construcción de patrones reutilizables desde partidas históricas.
"""

from datetime import datetime
from statistics import median
from typing import Dict, List, Tuple
from uuid import uuid4

from src.core import database
from src.core.database_backup import create_database_backup
from src.core.database_persistence import log_historical_memory_event


class HistoricalPatternBuilder:
    """Genera patrones en suggested_partida_pattern a partir del histórico.

    Agrupa únicamente por módulo principal (historical_partida_feature.
    primary_module_id) de líneas atómicas en presupuestos aprobados
    (learning_status='INCLUDED'): una partida con varias etiquetas
    secundarias ya no genera un patrón de precio por cada una (ver
    docs/criterios-clasificacion-partidas.md).
    """

    BUILDER_VERSION = "historical_pattern_builder_v3"
    PATTERN_SOURCE = "historical_learning_included"

    def rebuild_patterns(self) -> Dict:
        try:
            create_database_backup("before_patterns_rebuild")
        except Exception:
            pass
        groups = self._load_groups()
        inserted = 0
        build_run = f"pattern_build_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{uuid4().hex[:8]}"
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        source_budget_ids = set()
        source_partida_count = 0
        with database.get_connection() as conn:
            conn.execute(
                """INSERT INTO historical_pattern_build_run
                   (id, started_at, builder_version)
                   VALUES (?, ?, ?)""",
                (build_run, started_at, self.BUILDER_VERSION),
            )
            conn.execute("SAVEPOINT pattern_rebuild")
            try:
                # Borrado explícito para no depender de ON DELETE CASCADE.
                conn.execute("DELETE FROM suggested_partida_pattern_source")
                conn.execute("DELETE FROM suggested_partida_pattern")
                for group in groups:
                    prices = group["prices"]
                    if not prices:
                        continue
                    frecuencia = len(prices)
                    confianza = min(1.0, frecuencia / 10.0)
                    mediana = float(median(prices))
                    distinct_budget_count = len(
                        {int(s["historical_budget_id"]) for s in group["sources"]}
                    )
                    price_spread_ratio = (
                        round((max(prices) - min(prices)) / mediana, 2) if mediana > 0 else 0.0
                    )
                    latest_source_date = max(
                        (s.get("source_date") or "" for s in group["sources"]), default=""
                    )
                    # ponytail: umbrales fijos (>=3 fuerte, ==2 media, 1 debil);
                    # subir a ponderacion por dispersion si hace falta mas adelante.
                    if distinct_budget_count >= 3:
                        evidence_quality = "strong"
                    elif distinct_budget_count == 2:
                        evidence_quality = "medium"
                    else:
                        evidence_quality = "weak"
                    cur = conn.execute(
                        """INSERT INTO suggested_partida_pattern
                           (module_id, concepto_normalizado, titulo_sugerido, descripcion_sugerida,
                            unidad_habitual, precio_unitario_medio, precio_unitario_mediana,
                            precio_unitario_min, precio_unitario_max, frecuencia, confianza,
                            pattern_build_run, pattern_source, activo,
                            distinct_budget_count, price_spread_ratio, latest_source_date, evidence_quality)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
                        (
                            group["module_id"],
                            group["concepto_normalizado"],
                            group["titulo_sugerido"],
                            None,
                            group["unidad"],
                            round(sum(prices) / frecuencia, 2),
                            round(mediana, 2),
                            round(min(prices), 2),
                            round(max(prices), 2),
                            frecuencia,
                            round(confianza, 2),
                            build_run,
                            self.PATTERN_SOURCE,
                            distinct_budget_count,
                            price_spread_ratio,
                            latest_source_date or None,
                            evidence_quality,
                        ),
                    )
                    pattern_id = int(cur.lastrowid or 0)
                    if pattern_id <= 0:
                        continue
                    inserted += 1

                    for source in group["sources"]:
                        source_budget_ids.add(int(source["historical_budget_id"]))
                        source_partida_count += 1
                        conn.execute(
                            """INSERT INTO suggested_partida_pattern_source
                               (pattern_id, historical_partida_id, historical_budget_id,
                                precio_unitario, total_linea, created_at)
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (
                                pattern_id,
                                int(source["historical_partida_id"]),
                                int(source["historical_budget_id"]),
                                float(source["precio_unitario"]),
                                float(source["total_linea"]),
                                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            ),
                        )

                conn.execute(
                    """UPDATE historical_pattern_build_run
                       SET finished_at=?, source_budget_count=?, source_partida_count=?,
                           patterns_inserted=?, error=NULL
                       WHERE id=?""",
                    (
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        len(source_budget_ids),
                        source_partida_count,
                        inserted,
                        build_run,
                    ),
                )
                conn.execute("RELEASE SAVEPOINT pattern_rebuild")
                conn.commit()
                log_historical_memory_event(
                    "PATTERNS_REBUILT",
                    "Patrones historicos reconstruidos.",
                    {
                        "patterns_inserted": inserted,
                        "source_budget_count": len(source_budget_ids),
                        "source_partida_count": source_partida_count,
                        "build_run": build_run,
                    },
                )
            except Exception as exc:
                conn.execute("ROLLBACK TO SAVEPOINT pattern_rebuild")
                conn.execute("RELEASE SAVEPOINT pattern_rebuild")
                conn.execute(
                    """UPDATE historical_pattern_build_run
                       SET finished_at=?, source_budget_count=?, source_partida_count=?,
                           patterns_inserted=?, error=?
                       WHERE id=?""",
                    (
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        len(source_budget_ids),
                        source_partida_count,
                        inserted,
                        str(exc),
                        build_run,
                    ),
                )
                conn.commit()
                raise
        return {
            "groups": len(groups),
            "patterns_inserted": inserted,
            "pattern_build_run": build_run,
            "pattern_source": self.PATTERN_SOURCE,
        }

    def _load_groups(self) -> List[Dict]:
        """Carga evidencia primaria: solo líneas atómicas (una única acción/
        elemento, sin etiquetas secundarias que compitan por el precio) de
        presupuestos aprobados explícitamente, agrupadas por su módulo
        principal — nunca por cada etiqueta secundaria."""
        with database.get_connection(read_only=True) as conn:
            cur = conn.execute(
                """SELECT em.id,
                          hp.concepto_normalizado,
                          COALESCE(hp.unidad, ''),
                          COALESCE(hp.titulo, ''),
                          hp.precio_unitario,
                          hp.id,
                          hp.historical_budget_id,
                          COALESCE(hp.total_linea, 0),
                          COALESCE(hb.fecha_presupuesto, hb.fecha_analisis, '')
                   FROM historical_partida hp
                   JOIN historical_partida_feature f ON f.partida_id = hp.id
                   JOIN historical_budget hb ON hb.id = hp.historical_budget_id
                   JOIN execution_module em ON em.nombre = f.primary_module_id
                   WHERE hp.concepto_normalizado IS NOT NULL
                     AND hp.concepto_normalizado <> ''
                     AND hp.precio_unitario IS NOT NULL
                     AND hp.precio_unitario > 0
                     AND hb.analysis_status IN ('VALID', 'VALID_WITH_WARNINGS')
                     AND hb.learning_status = 'INCLUDED'
                     AND f.line_kind = 'atomic'
                   ORDER BY em.id, hp.concepto_normalizado"""
            )
            rows = cur.fetchall()

        grouped: Dict[Tuple[int, str, str], Dict] = {}
        for row in rows:
            module_id = int(row[0])
            concepto = row[1].strip()
            unidad = row[2].strip()
            titulo = row[3].strip()
            precio = float(row[4])
            historical_partida_id = int(row[5])
            historical_budget_id = int(row[6])
            total_linea = float(row[7] or 0.0)
            source_date = (row[8] or "").strip()
            key = (module_id, concepto, unidad)
            if key not in grouped:
                grouped[key] = {
                    "module_id": module_id,
                    "concepto_normalizado": concepto,
                    "unidad": unidad,
                    "titulo_sugerido": titulo,
                    "prices": [],
                    "sources": [],
                }
            grouped[key]["prices"].append(precio)
            grouped[key]["sources"].append(
                {
                    "historical_partida_id": historical_partida_id,
                    "historical_budget_id": historical_budget_id,
                    "precio_unitario": precio,
                    "total_linea": total_linea,
                    "source_date": source_date,
                }
            )
        return list(grouped.values())
