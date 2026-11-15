"""Enriquecer las filas del dashboard con la planificación (núcleo, sin Qt)."""

from datetime import date

import pytest

from src.core import database
from src.core.obra_planning_service import PLANNING_STATES, enrich_with_planning
from src.core.repositories.obra_planificacion_repository import get_planes, upsert_plan

HOY = date(2026, 11, 13)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "obras.db"))
    monkeypatch.setenv("CUBIAPP_BACKUP_DIR", str(tmp_path / "backups"))
    with database.get_connection():
        pass


def _row(numero, carpeta):
    return {"numero": numero, "ruta_carpeta": f"C:/raiz/X/{carpeta}", "nombre_proyecto": carpeta}


def test_anade_plan_y_propuesta_solo_en_estados_de_planificacion(db):
    upsert_plan("208-26", inicio_previsto=date(2026, 6, 25))
    data = {
        "EJECUTAR": [_row("114-26", "114-26 C.P. RAFAEL ASÍN (HUMEDADES) EJECUTAR EL 13-07-26"),
                     _row("208-26", "208-26 C. P. JUAN DE HERRERA EJECUTAR EL 01-01-27")],
        "PRESUPUESTADO": [_row("300-26", "300-26 OBRA EJECUTAR EL 01-02-27")],
    }
    duplicados = enrich_with_planning(data, hoy=HOY, reconcile=False)

    assert duplicados == set()
    a, b = data["EJECUTAR"]
    assert a["planificacion"] == {} and a["planificacion_propuesta"] == (date(2026, 7, 13), False)
    assert b["planificacion"]["inicio_previsto"] == date(2026, 6, 25)
    assert b["planificacion_propuesta"] is None          # ya tiene fecha: no se propone
    assert "planificacion" not in data["PRESUPUESTADO"][0]
    assert set(PLANNING_STATES) == {"EJECUTAR", "EJECUTANDO", "TERMINADO"}


def test_numeros_repetidos_no_se_planifican(db):
    data = {"EJECUTAR": [_row("114-26", "114-26 A"), _row("114-26", "114-26 B")]}
    duplicados = enrich_with_planning(data, hoy=HOY, reconcile=False)
    assert duplicados == {"114-26"}
    assert all(r["planificacion_duplicado"] for r in data["EJECUTAR"])
    assert all(r["planificacion"] == {} for r in data["EJECUTAR"])


def test_duplicados_conocidos_se_respetan_al_refrescar_una_fila(db):
    data = {"EJECUTAR": [_row("114-26", "114-26 A")]}
    enrich_with_planning(data, hoy=HOY, reconcile=False, known_duplicates={"114-26"})
    assert data["EJECUTAR"][0]["planificacion_duplicado"]


def test_reconcilia_solo_si_se_pide(db):
    data = {"EJECUTANDO": [_row("107-26", "107-26 X")]}
    enrich_with_planning(data, hoy=HOY, reconcile=False)
    assert get_planes(["107-26"]) == {}
    enrich_with_planning(data, hoy=HOY, reconcile=True)
    assert get_planes(["107-26"])["107-26"]["estado_conocido"] == "EJECUTANDO"
    assert data["EJECUTANDO"][0]["planificacion"]["inicio_real"] is None   # primer escaneo


def test_identidad_con_sufijo_desde_el_nombre_de_la_carpeta(db):
    from src.core.obra_planning_service import planning_key

    assert planning_key({"numero": "160-26", "ruta_carpeta": "C:/r/PRESUPUESTADO/160-26-2 C.P. DR. BERGEZ"}) == "160-26-2"
    assert planning_key({"numero": "160-26", "ruta_carpeta": "C:/r/PRESUPUESTADO/160-26 C.P. DR. BERGEZ"}) == "160-26"
    assert planning_key({"numero": "42-26", "ruta_carpeta": ""}) == "42-26"


def test_subpresupuestos_no_cuentan_como_repetidos_y_se_indica_donde_esta_la_copia(db):
    data = {
        "EJECUTAR": [_row("42-26", "42-26-2 C.P. FELIPE HERRERO (ATORNILLAR VENTANAS)"),
                     _row("127-25", "127-25 C.P. TENIENTE LLORCA SE EJECUTARÁ EN JULIO'26")],
        "TERMINADO": [_row("42-26", "42-26 C.P. FELIPE HERRERO (REP. FACHADA)"),
                      _row("127-25", "127-25 C.P. TENIENTE LLORCA")],
    }
    duplicados = enrich_with_planning(data, hoy=HOY, reconcile=False)
    assert duplicados == {"127-25"}
    sub, copia = data["EJECUTAR"]
    assert not sub["planificacion_duplicado"]
    assert copia["planificacion_duplicado"] and copia["planificacion_duplicado_en"] == ["EJECUTAR", "TERMINADO"]
