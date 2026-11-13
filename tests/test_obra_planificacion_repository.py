"""Repositorio de planificación de obras y migración v6."""

from datetime import date

import pytest

from src.core import database
from src.core.repositories.obra_planificacion_repository import (
    get_planes,
    reconcile_scan,
    record_state_change,
    upsert_plan,
)

HOY = date(2026, 11, 13)


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "obras.db"))
    monkeypatch.setenv("CUBIAPP_BACKUP_DIR", str(tmp_path / "backups"))
    with database.get_connection():
        pass
    return tmp_path


def test_la_tabla_existe_y_el_esquema_es_v6(db):
    with database.get_connection(read_only=True) as conn:
        assert database.get_schema_version(conn) == 6
        cols = {r[1] for r in conn.execute("PRAGMA table_info(obra_planificacion)")}
    assert {"numero_proyecto", "inicio_previsto", "fin_previsto", "inicio_real", "fin_real",
            "inicio_real_aproximado", "fin_real_aproximado", "margen_aviso_dias", "avisado_en",
            "notas", "estado_conocido", "actualizado_en"} <= cols


def test_upsert_y_get(db):
    assert upsert_plan("114-26", inicio_previsto=date(2026, 7, 13), notas="andamio") is None
    assert upsert_plan("114-26", fin_previsto=date(2026, 7, 31)) is None   # no borra lo anterior
    plan = get_planes(["114-26", "999-26"])["114-26"]
    assert plan["inicio_previsto"] == date(2026, 7, 13)
    assert plan["fin_previsto"] == date(2026, 7, 31)
    assert plan["notas"] == "andamio"
    assert "999-26" not in get_planes(["999-26"])


def test_upsert_puede_quitar_una_fecha(db):
    upsert_plan("114-26", inicio_previsto=date(2026, 7, 13))
    upsert_plan("114-26", inicio_previsto=None)
    assert get_planes(["114-26"])["114-26"]["inicio_previsto"] is None


def test_mover_con_la_app_registra_fechas_exactas(db):
    record_state_change("114-26", "EJECUTANDO", HOY, aproximada=False)
    record_state_change("114-26", "TERMINADO", date(2026, 12, 1), aproximada=False)
    plan = get_planes(["114-26"])["114-26"]
    assert plan["inicio_real"] == HOY and not plan["inicio_real_aproximado"]
    assert plan["fin_real"] == date(2026, 12, 1) and not plan["fin_real_aproximado"]
    assert plan["estado_conocido"] == "TERMINADO"


def test_no_sobrescribe_una_fecha_real_ya_puesta_ni_la_borra_al_volver(db):
    upsert_plan("114-26", inicio_real=date(2026, 10, 1))
    record_state_change("114-26", "EJECUTANDO", HOY, aproximada=False)
    record_state_change("114-26", "EJECUTAR", HOY, aproximada=False)   # vuelve atrás
    plan = get_planes(["114-26"])["114-26"]
    assert plan["inicio_real"] == date(2026, 10, 1)
    assert plan["estado_conocido"] == "EJECUTAR"


def test_primer_escaneo_solo_anota_el_estado(db):
    reconcile_scan({"EJECUTANDO": ["107-26"], "TERMINADO": ["120-26"], "EJECUTAR": ["114-26"]}, HOY)
    planes = get_planes(["107-26", "120-26", "114-26"])
    assert planes["107-26"]["estado_conocido"] == "EJECUTANDO"
    assert planes["107-26"]["inicio_real"] is None          # no se inventa
    assert planes["120-26"]["fin_real"] is None


def test_movimiento_fuera_de_la_app_se_registra_aproximado(db):
    reconcile_scan({"EJECUTAR": ["114-26"]}, date(2026, 11, 1))
    reconcile_scan({"EJECUTANDO": ["114-26"]}, HOY)
    plan = get_planes(["114-26"])["114-26"]
    assert plan["inicio_real"] == HOY and plan["inicio_real_aproximado"]
    assert plan["estado_conocido"] == "EJECUTANDO"


def test_numeros_repetidos_o_vacios_no_se_planifican(db):
    reconcile_scan({"EJECUTAR": ["114-26", "114-26", ""]}, HOY)
    assert get_planes(["114-26", ""]) == {}
