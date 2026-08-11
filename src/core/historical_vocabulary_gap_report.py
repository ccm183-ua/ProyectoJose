"""
Informe de impacto por familia (Task 1 del plan
docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md).

Solo lectura. Identifica, por familia de execution_module, cuantas lineas
atomicas reales del historico no tienen ficha completa (action o element
vacios) y con que frecuencia se repite cada frase normalizada, para
priorizar que familia revisar primero y que ejemplos traer a la revision.
"""

from typing import Dict, List

from src.core import database


def rank_families_by_gap(families: List[str]) -> List[Dict]:
    """Ordena las familias dadas por numero de lineas atomicas sin ficha
    completa (action o element vacios), de mayor a menor impacto."""
    with database.get_connection(read_only=True) as conn:
        rows = conn.execute(
            """SELECT f.primary_module_id,
                      COUNT(*) AS total,
                      SUM(
                          CASE WHEN (f.action IS NULL OR f.action = '')
                                 OR (f.element IS NULL OR f.element = '')
                               THEN 1 ELSE 0 END
                      ) AS sin_ficha_completa
               FROM historical_partida_feature f
               JOIN historical_partida hp ON hp.id = f.partida_id
               JOIN historical_budget hb ON hb.id = hp.historical_budget_id
               WHERE f.primary_module_id IN ({placeholders})
                 AND hb.learning_status = 'INCLUDED'
                 AND hb.analysis_status IN ('VALID', 'VALID_WITH_WARNINGS')
                 AND f.line_kind = 'atomic'
               GROUP BY f.primary_module_id""".format(
                placeholders=",".join("?" for _ in families)
            ),
            tuple(families),
        ).fetchall()

    by_family = {
        row[0]: {"familia": row[0], "total_atomicas": int(row[1]), "sin_ficha_completa": int(row[2] or 0)}
        for row in rows
    }
    ranking = [
        by_family.get(f, {"familia": f, "total_atomicas": 0, "sin_ficha_completa": 0})
        for f in families
    ]
    ranking.sort(key=lambda r: r["sin_ficha_completa"], reverse=True)
    return ranking


def top_unmatched_phrases_for_family(family: str, limit: int = 10) -> List[Dict]:
    """Frases normalizadas mas frecuentes de `family` sin ficha completa,
    con un ejemplo de texto original real por frase."""
    with database.get_connection(read_only=True) as conn:
        rows = conn.execute(
            """SELECT hp.concepto_normalizado,
                      MIN(hp.concepto_original) AS ejemplo_original,
                      COUNT(*) AS frecuencia
               FROM historical_partida_feature f
               JOIN historical_partida hp ON hp.id = f.partida_id
               JOIN historical_budget hb ON hb.id = hp.historical_budget_id
               WHERE f.primary_module_id = ?
                 AND hb.learning_status = 'INCLUDED'
                 AND hb.analysis_status IN ('VALID', 'VALID_WITH_WARNINGS')
                 AND f.line_kind = 'atomic'
                 AND ((f.action IS NULL OR f.action = '')
                      OR (f.element IS NULL OR f.element = ''))
               GROUP BY hp.concepto_normalizado
               ORDER BY frecuencia DESC
               LIMIT ?""",
            (family, limit),
        ).fetchall()

    return [
        {
            "concepto_normalizado": row[0],
            "ejemplo_original": row[1],
            "frecuencia": int(row[2]),
        }
        for row in rows
    ]
