"""
Migracion masiva desde la cache (presupuesto/presupuesto_partida) al dominio
canonico (H3, paso 6 del roadmap): recorre todos los presupuestos cacheados,
los importa uno a uno via `canonical_budget_importer`, y agrega un resumen
que compara numero de presupuestos, partidas y totales entre origen y
dominio canonico.

No borra ni modifica el origen (presupuesto/presupuesto_partida). Pensado
para ejecutarse sobre una copia de la BDD (anonimizada si los datos son
reales) y revisar el resumen antes de confiar en el resultado — nunca contra
produccion sin verificar antes.

Uso como comando:
    python -m src.core.canonical_budget_bulk_importer
"""

from dataclasses import dataclass, field
from typing import Dict, List

from src.core.canonical_budget_importer import import_from_cache_snapshot
from src.core.repositories.canonical_budget_repository import get_active_version, get_lines
from src.core.repositories.presupuesto_cache_repository import (
    get_all_presupuestos_cache,
    get_partidas_de_presupuesto,
)

TOLERANCE_EUR = 0.01


@dataclass
class BulkImportSummary:
    total_presupuestos: int = 0
    importados_ok: int = 0
    fallidos: int = 0
    errores: List[Dict] = field(default_factory=list)
    total_partidas_origen: int = 0
    total_partidas_importadas: int = 0
    total_importe_origen: float = 0.0
    total_importe_canonico: float = 0.0
    warnings_por_codigo: Dict[str, int] = field(default_factory=dict)

    @property
    def totales_cuadran(self) -> bool:
        return abs(self.total_importe_origen - self.total_importe_canonico) <= TOLERANCE_EUR

    @property
    def partidas_cuadran(self) -> bool:
        return self.total_partidas_origen == self.total_partidas_importadas


def import_all_from_cache() -> BulkImportSummary:
    """Importa todos los presupuestos de la cache al dominio canonico.

    Idempotente: si ya se ejecuto antes, cada presupuesto ya importado se
    reimporta como una nueva version (ver `import_from_cache_snapshot`), no
    se duplica el `budget`.
    """
    summary = BulkImportSummary()
    presupuestos = get_all_presupuestos_cache()
    summary.total_presupuestos = len(presupuestos)

    for presupuesto in presupuestos:
        partidas = get_partidas_de_presupuesto(presupuesto_id=presupuesto["id"])
        summary.total_partidas_origen += len(partidas)
        summary.total_importe_origen += float(presupuesto.get("total") or 0)

        result = import_from_cache_snapshot(presupuesto, partidas)
        if not result.success:
            summary.fallidos += 1
            summary.errores.append({
                "presupuesto_id": presupuesto["id"],
                "ruta_excel": presupuesto.get("ruta_excel", ""),
                "error": result.error,
            })
            continue

        summary.importados_ok += 1
        for w in result.warnings:
            summary.warnings_por_codigo[w["codigo"]] = summary.warnings_por_codigo.get(w["codigo"], 0) + 1

        version = get_active_version(result.budget_id)
        if version:
            summary.total_importe_canonico += float(version.get("total") or 0)
        summary.total_partidas_importadas += len(get_lines(result.budget_version_id))

    return summary


def _print_report(summary: BulkImportSummary) -> None:
    print(f"Presupuestos en cache:      {summary.total_presupuestos}")
    print(f"Importados correctamente:  {summary.importados_ok}")
    print(f"Fallidos:                  {summary.fallidos}")
    print(f"Partidas origen:           {summary.total_partidas_origen}")
    print(f"Partidas importadas:       {summary.total_partidas_importadas}  "
          f"({'OK' if summary.partidas_cuadran else 'DIFIEREN'})")
    print(f"Total importe origen:      {summary.total_importe_origen:.2f} EUR")
    print(f"Total importe canonico:    {summary.total_importe_canonico:.2f} EUR  "
          f"({'OK' if summary.totales_cuadran else 'DIFIEREN'})")
    if summary.warnings_por_codigo:
        print("Advertencias de reconciliacion:")
        for codigo, n in sorted(summary.warnings_por_codigo.items()):
            print(f"  {codigo}: {n}")
    if summary.errores:
        print("Errores:")
        for e in summary.errores:
            print(f"  presupuesto_id={e['presupuesto_id']} ({e['ruta_excel']}): {e['error']}")


def main() -> int:
    summary = import_all_from_cache()
    _print_report(summary)
    return 0 if summary.fallidos == 0 else 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
