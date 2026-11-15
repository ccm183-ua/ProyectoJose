"""
Importa precios de referencia (H5) desde el historico validado hacia el
catalogo `price_reference`. Reutiliza el mismo criterio de elegibilidad que
`historical_pattern_builder.py` (historico "INCLUDED"/`usable_for_learning`
y `analysis_status` valido): esos son los datos que el resto del codigo ya
trata como reutilizables.

Cada grupo (concepto_normalizado, unidad) genera una fila de evidencia
("historical", referencia=f"historical_partida:{id}") y un `price_reference`
en estado 'proposed' - nunca 'approved' automaticamente, tal y como pide el
roadmap ("no como precios actuales garantizados").

Idempotente: si ya existe un price_reference vinculado a una evidencia con
esa misma referencia, se omite (no se duplica al re-ejecutar).

Uso como comando:
    python -m src.core.historical_price_reference_importer
"""

from dataclasses import dataclass, field
from typing import List

from src.core import database
from src.core.repositories.canonical_budget_repository import record_evidence
from src.core.repositories.price_reference_repository import create_price_reference

_ELIGIBLE_HISTORICAL_PARTIDAS_SQL = """
    SELECT hp.concepto_normalizado, COALESCE(hp.unidad, ''), hp.precio_unitario,
           hp.id, COALESCE(hb.fecha_analisis, hb.fecha_modificacion_excel)
    FROM historical_partida hp
    JOIN historical_budget hb ON hb.id = hp.historical_budget_id
    WHERE hp.concepto_normalizado IS NOT NULL AND hp.concepto_normalizado <> ''
      AND hp.precio_unitario IS NOT NULL AND hp.precio_unitario > 0
      AND hb.analysis_status IN ('VALID', 'VALID_WITH_WARNINGS')
      AND (hb.learning_status = 'INCLUDED'
           OR (hb.learning_status IS NULL AND hb.usable_for_learning = 1))
    ORDER BY hp.concepto_normalizado, COALESCE(hp.unidad, '')
"""


@dataclass
class ImportSummary:
    total_candidatos: int = 0
    importados: int = 0
    omitidos_ya_existentes: int = 0
    errores: List[str] = field(default_factory=list)


def _referencia_ya_importada(conn, referencia: str) -> bool:
    row = conn.execute(
        """SELECT 1 FROM price_reference pr
           JOIN evidence e ON e.id = pr.evidence_id
           WHERE e.referencia = ? LIMIT 1""",
        (referencia,),
    ).fetchone()
    return row is not None


def import_price_references_from_historical() -> ImportSummary:
    summary = ImportSummary()
    with database.get_connection() as conn:
        rows = conn.execute(_ELIGIBLE_HISTORICAL_PARTIDAS_SQL).fetchall()

        grouped = {}
        for concepto, unidad, precio, partida_id, fecha in rows:
            key = (concepto.strip(), unidad.strip())
            if key not in grouped:
                grouped[key] = (float(precio), int(partida_id), fecha)

        summary.total_candidatos = len(grouped)

        for (concepto, unidad), (precio, partida_id, fecha) in grouped.items():
            referencia = f"historical_partida:{partida_id}"
            if _referencia_ya_importada(conn, referencia):
                summary.omitidos_ya_existentes += 1
                continue

            evidence_id, err = record_evidence("historical", referencia=referencia)
            if err is not None:
                summary.errores.append(f"{concepto}/{unidad}: {err}")
                continue

            _, pr_err = create_price_reference(
                concepto, unidad, precio, "historical", fecha or "",
                evidence_id=evidence_id, estado="proposed",
            )
            if pr_err is not None:
                summary.errores.append(f"{concepto}/{unidad}: {pr_err}")
                continue
            summary.importados += 1

    return summary


if __name__ == "__main__":
    result = import_price_references_from_historical()
    print(
        f"Candidatos: {result.total_candidatos} | Importados: {result.importados} | "
        f"Omitidos (ya existentes): {result.omitidos_ya_existentes} | Errores: {len(result.errores)}"
    )
    for e in result.errores:
        print(f"  - {e}")
