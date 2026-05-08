"""
Construcción de patrones reutilizables desde partidas históricas.
"""

from datetime import datetime
from statistics import median
from typing import Dict, List, Tuple

from src.core import database


class HistoricalPatternBuilder:
    """Genera patrones en suggested_partida_pattern a partir del histórico."""

    PATTERN_SOURCE = "historical_learning_included"

    def rebuild_patterns(self) -> Dict:
        groups = self._load_groups()
        inserted = 0
        build_run = datetime.now().strftime("pattern_build_%Y%m%d_%H%M%S")
        with database.get_connection() as conn:
            conn.execute("DELETE FROM suggested_partida_pattern")
            for group in groups:
                prices = group["prices"]
                if not prices:
                    continue
                frecuencia = len(prices)
                confianza = min(1.0, frecuencia / 10.0)
                conn.execute(
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
                inserted += 1
            conn.commit()
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
                          hp.precio_unitario
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
            key = (module_id, concepto, unidad)
            if key not in grouped:
                grouped[key] = {
                    "module_id": module_id,
                    "concepto_normalizado": concepto,
                    "unidad": unidad,
                    "titulo_sugerido": titulo,
                    "prices": [],
                }
            grouped[key]["prices"].append(precio)
        return list(grouped.values())
