"""Carga del calendario desde la caché del dashboard y señal compartida."""

from datetime import date

import pytest

try:
    import PySide6  # noqa: F401

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

HOY = date(2026, 11, 16)


@pytest.fixture
def bd_temporal(tmp_path, monkeypatch):
    from src.core import database

    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "obras.db"))
    monkeypatch.setenv("CUBIAPP_BACKUP_DIR", str(tmp_path / "backups"))
    with database.get_connection():
        pass


def _cache(estado, carpeta, numero):
    ruta = f"C:/obras/{estado}/{carpeta}"
    return {"numero_proyecto": numero, "nombre_proyecto": carpeta, "ruta_carpeta": ruta,
            "ruta_excel": f"{ruta}/p.xlsx", "estado": estado}


def _con_cache(monkeypatch, filas):
    import src.core.repositories.presupuesto_cache_repository as repo

    monkeypatch.setattr(repo, "get_all_presupuestos_cache", lambda: [dict(f) for f in filas])


def test_agrupa_por_fase_y_anade_planificacion(bd_temporal, monkeypatch):
    from src.core.obra_calendar_service import load_calendar_data
    from src.core.repositories.obra_planificacion_repository import upsert_plan

    upsert_plan("208-26", inicio_previsto=date(2026, 11, 20))
    _con_cache(monkeypatch, [
        _cache("EJECUTAR", "114-26 C.P. RAFAEL ASIN EJECUTAR EL 13-07-26", "114-26"),
        _cache("EJECUTAR", "208-26 C.P. JUAN DE HERRERA", "208-26"),
        _cache("TERMINADO", "109-26 OBRA A", "109-26"),
        _cache("PRESUPUESTADO", "109-26 OBRA B", "109-26"),
        _cache("PRESUPUESTADO", "300-26 OTRA", "300-26"),
    ])
    data = load_calendar_data(HOY)
    assert set(data.filas_por_estado) == {"EJECUTAR", "EJECUTANDO", "TERMINADO"}
    ejecutar = {r["numero"]: r for r in data.filas_por_estado["EJECUTAR"]}
    assert ejecutar["208-26"]["planificacion"]["inicio_previsto"] == date(2026, 11, 20)
    assert ejecutar["114-26"]["planificacion_propuesta"] == (date(2026, 7, 13), False)
    assert data.filas_por_estado["TERMINADO"][0]["planificacion_duplicado"] is True
    assert data.repetidas == 1
    assert data.error == "" and data.vacia is False


def test_cache_vacia(bd_temporal, monkeypatch):
    from src.core.obra_calendar_service import load_calendar_data

    _con_cache(monkeypatch, [_cache("PRESUPUESTADO", "1-26 X", "1-26")])
    data = load_calendar_data(HOY)
    assert data.vacia is True


def test_fallo_de_planificacion_muestra_obras_sin_fechas(bd_temporal, monkeypatch):
    import src.core.obra_calendar_service as svc

    _con_cache(monkeypatch, [_cache("EJECUTAR", "114-26 X", "114-26")])

    def _falla(*a, **k):
        raise RuntimeError("bd rota")

    monkeypatch.setattr(svc, "enrich_with_planning", _falla)
    data = svc.load_calendar_data(HOY)
    assert data.error == svc.ERROR_LECTURA
    fila = data.filas_por_estado["EJECUTAR"][0]
    assert fila["planificacion"] == {} and fila["planificacion_duplicado"] is False
    assert fila["planificacion_propuesta"] is None


def test_refresh_planning_relee_plan_y_propuesta(bd_temporal, monkeypatch):
    from src.core.obra_calendar_service import load_calendar_data, refresh_planning
    from src.core.repositories.obra_planificacion_repository import upsert_plan

    _con_cache(monkeypatch, [_cache("EJECUTAR", "114-26 C.P. RAFAEL ASIN EJECUTAR EL 13-07-26", "114-26")])
    data = load_calendar_data(HOY)
    upsert_plan("114-26", inicio_previsto=date(2026, 11, 25))
    refresh_planning(data.filas_por_estado, ["114-26"])
    fila = data.filas_por_estado["EJECUTAR"][0]
    assert fila["planificacion"]["inicio_previsto"] == date(2026, 11, 25)
    assert fila["planificacion_propuesta"] is None

    upsert_plan("114-26", inicio_previsto=None)
    refresh_planning(data.filas_por_estado, ["114-26"])
    assert fila["planificacion_propuesta"] == (date(2026, 7, 13), False)


@pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")
def test_senales_compartidas(qapp):
    from src.gui import planning_events

    vistos = []
    ev = planning_events.planning_events()
    assert ev is planning_events.planning_events()

    def _cambio(numeros, emisor):
        vistos.append(("cambio", numeros, emisor))

    def _recarga(emisor):
        vistos.append(("recarga", emisor))

    ev.planning_changed.connect(_cambio)
    ev.obras_reloaded.connect(_recarga)
    try:
        planning_events.notify_planning_changed(("114-26",), source="yo")
        planning_events.notify_obras_reloaded(source="dash")
    finally:
        ev.planning_changed.disconnect(_cambio)
        ev.obras_reloaded.disconnect(_recarga)
    assert vistos == [("cambio", ["114-26"], "yo"), ("recarga", "dash")]
