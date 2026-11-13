"""La caché de presupuestos se lee en bloque, no con una consulta por proyecto."""

from src.core import database
from src.core.budget_cache import _get_file_mtime_iso, sync_presupuestos
from src.core.repositories import get_presupuestos_por_rutas, upsert_presupuesto


def _seed(ruta, mtime="2026-01-01T00:00:00", numero="1-26"):
    _id, err = upsert_presupuesto({
        "numero_proyecto": numero,
        "nombre_proyecto": f"{numero} obra",
        "ruta_excel": ruta,
        "ruta_carpeta": "",
        "estado": "PRESUPUESTADO",
        "cliente": "Comunidad",
        "total": 100.0,
        "fecha_modificacion_excel": mtime,
        "datos_completos": True,
    })
    assert err is None


def test_get_presupuestos_por_rutas_returns_only_requested(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "bulk.db"))
    _seed("C:/a.xlsx")
    _seed("C:/b.xlsx")

    result = get_presupuestos_por_rutas(["C:/a.xlsx", "C:/nope.xlsx", ""])

    assert set(result) == {"C:/a.xlsx"}
    assert result["C:/a.xlsx"]["cliente"] == "Comunidad"


def test_get_presupuestos_por_rutas_empty_list(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "bulk.db"))
    assert get_presupuestos_por_rutas([]) == {}


def test_get_presupuestos_por_rutas_more_than_batch_size(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "bulk.db"))
    rutas = [f"C:/p{i}.xlsx" for i in range(1203)]
    with database.get_connection() as conn:
        conn.executemany(
            "INSERT INTO presupuesto (nombre_proyecto, ruta_excel, fecha_modificacion_excel, fecha_cache) "
            "VALUES ('x', ?, 'm', 'c')",
            [(r,) for r in rutas],
        )
        conn.commit()

    assert len(get_presupuestos_por_rutas(rutas)) == 1203


def test_sync_with_cached_projects_opens_few_connections(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "bulk.db"))
    scanned = []
    for i in range(20):
        excel = tmp_path / f"{i}-26.xlsx"
        excel.write_bytes(b"x")
        # Sin número de proyecto: no hay comprobación de hoja, solo caché.
        _seed(str(excel), mtime=_get_file_mtime_iso(str(excel)), numero="")
        scanned.append({
            "nombre_carpeta": f"{i}-26 obra",
            "numero_proyecto": "",
            "ruta_excel": str(excel),
            "ruta_carpeta": str(tmp_path),
        })

    calls = []
    original = database.connect
    monkeypatch.setattr(database, "connect", lambda *a, **k: (calls.append(1), original(*a, **k))[1])

    result = sync_presupuestos(scanned, {}, "PRESUPUESTADO")

    assert len(result) == 20
    assert all(r["cliente"] == "Comunidad" for r in result)
    assert len(calls) <= 2
