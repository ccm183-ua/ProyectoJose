"""
Mide la recarga del dashboard «Presupuestos existentes» con los datos configurados.

Plan: docs/superpowers/plans/2026-11-13-rendimiento-dashboard.md (Tarea 7).

Cuenta tiempo, lecturas completas de Excel y conexiones SQLite de varias
recargas seguidas. Escribe solo en la caché de presupuestos (lo mismo que hace
el dashboard). Para no tocar la BD real, apunta CUBIAPP_DB_PATH a una copia:

    set CUBIAPP_DB_PATH=C:\\ruta\\copia\\datos.db
    .venv\\Scripts\\python.exe scripts\\bench_dashboard_reload.py --veces 3
"""

import argparse
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import budget_cache, database, folder_scanner  # noqa: E402
from src.core.budget_reader import BudgetReader  # noqa: E402
from src.core.project_data_resolver import build_relation_index  # noqa: E402
from src.core.settings import Settings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--veces", type=int, default=3, help="recargas consecutivas a medir")
    args = parser.parse_args()
    logging.disable(logging.CRITICAL)

    root = Settings().get_default_path(Settings.PATH_OPEN_BUDGETS)
    if not root or not os.path.isdir(root):
        print("La ruta de presupuestos existentes no está configurada.")
        return 1
    print(f"BD: {database.get_db_path()}\nCarpeta: {root}")

    counts = {"conexiones": 0, "lecturas_excel": 0}
    original_connect = database.connect
    original_load = BudgetReader._load_file_bytes

    def _connect(*a, **k):
        counts["conexiones"] += 1
        return original_connect(*a, **k)

    def _load(path):
        counts["lecturas_excel"] += 1
        return original_load(path)

    database.connect = _connect
    BudgetReader._load_file_bytes = staticmethod(_load)

    for i in range(1, args.veces + 1):
        counts.update(conexiones=0, lecturas_excel=0)
        start = time.perf_counter()
        index = build_relation_index()
        proyectos = 0
        for state in folder_scanner.scan_root(root):
            scanned = folder_scanner.scan_projects(os.path.join(root, state))
            proyectos += len(scanned)
            budget_cache.sync_presupuestos(scanned, index, state)
        elapsed = time.perf_counter() - start
        print(
            f"Recarga {i}: {elapsed:.2f} s | {proyectos} proyectos | "
            f"{counts['lecturas_excel']} lecturas de Excel | {counts['conexiones']} conexiones"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
