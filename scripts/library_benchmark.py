"""Validación de la biblioteca de partidas con una BD real, en solo lectura.

Mide el tiempo de carga y de búsquedas de referencia, y comprueba que cada
búsqueda devuelve resultados. Objetivos (spec 2026-11-12): carga < 3 s,
búsqueda < 200 ms.

Uso: .venv/Scripts/python.exe scripts/library_benchmark.py --db <ruta a datos.db>
Recomendado sobre una COPIA de la BD.
"""

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REFERENCIAS = ("bajante pvc", "impermeabilizacion cubierta", "picado fachada", "tirar tabique")
MAX_CARGA_S = 3.0
MAX_BUSQUEDA_MS = 200.0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Ruta al fichero .db (mejor una copia)")
    args = parser.parse_args(argv)
    db = Path(args.db).resolve()
    if not db.exists():
        print(f"No existe el fichero: {db}")
        return 1
    os.environ["CUBIAPP_DB_PATH"] = str(db)
    from src.core.partida_library import PartidaLibrary

    t0 = time.perf_counter()
    lib = PartidaLibrary.load()
    carga = time.perf_counter() - t0
    print(f"carga: {len(lib.lines)} líneas, {lib.ignored} ignoradas, {carga:.2f} s")
    ok = carga < MAX_CARGA_S
    for q in REFERENCIAS:
        t0 = time.perf_counter()
        res = lib.search(q)
        ms = (time.perf_counter() - t0) * 1000
        top = res.groups[0] if res.groups else None
        resumen = f"{top.concepto_norm[:60]} | {top.proposed_price:.2f} ({top.price_basis})" if top else "-"
        print(f"{q!r}: {res.total_groups} grupos, {ms:.0f} ms | primero: {resumen}")
        ok = ok and ms < MAX_BUSQUEDA_MS and res.total_groups > 0
    print("OK" if ok else "FALLA: revisar tiempos o búsquedas sin resultados")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
