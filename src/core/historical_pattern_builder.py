"""
Construcción de patrones reutilizables desde partidas históricas.
"""

from datetime import datetime
from statistics import median
from typing import Dict, List, Tuple
from uuid import uuid4

from src.core import database


class HistoricalPatternBuilder:
    """Genera patrones en suggested_partida_pattern a partir del histórico."""

    BUILDER_VERSION = "historical_pattern_builder_v2"
    PATTERN_SOURCE = "historical_learning_included"

    def rebuild_patterns(self) -> Dict:
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
            try:
                conn.execute("DELETE FROM suggested_partida_pattern")
                for group in groups:
                    prices = group["prices"]
                    if not prices:
                        continue
                    frecuencia = len(prices)
                    confianza = min(1.0, frecuencia / 10.0)
                    cur = conn.execute(
                        """INSERT INTO suggested_partida_pattern
                           (module_id, concepto_normalizado, titulo_sugerido, descripcion_sugerida,
                            unidad_habitual, precio_unitario_medio, precio_unitario_mediana,
                            precio_unitario_min, precio_unitario_max, frecuencia, confianza,
                            pattern_build_run, pattern_source, activo)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                        (
                            group["module_id"],
                            group["concepto_normalizado"],
                            group["titulo_sugerido"],
                            None,
                            group["unidad"],
                            round(sum(prices) / frecuencia, 2),
                            round(float(median(prices)), 2),
                            round(min(prices), 2),
                            round(max(prices), 2),
                            frecuencia,
                            round(confianza, 2),
                            build_run,
                            self.PATTERN_SOURCE,
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
                conn.commit()
            except Exception as exc:
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
        with database.get_connection(read_only=True) as conn:
            cur = conn.execute(
                """SELECT hpm.module_id,
                          hp.concepto_normalizado,
                          COALESCE(hp.unidad, ''),
                          COALESCE(hp.titulo, ''),
                          hp.precio_unitario,
                          hp.id,
                          hp.historical_budget_id,
                          COALESCE(hp.total_linea, 0)
                   FROM historical_partida hp
                   JOIN historical_partida_module hpm ON hpm.partida_id = hp.id
                   JOIN historical_budget hb ON hb.id = hp.historical_budget_id
                   WHERE hp.concepto_normalizado IS NOT NULL
                     AND hp.concepto_normalizado <> ''
                     AND hp.precio_unitario IS NOT NULL
                     AND hp.precio_unitario > 0
                     AND (
                         hb.learning_status = 'INCLUDED'
                         OR (
                             hb.learning_status IS NULL
                             AND hb.usable_for_learning = 1
                         )
                     )
                   ORDER BY hpm.module_id, hp.concepto_normalizado"""
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
                }
            )
        return list(grouped.values())
