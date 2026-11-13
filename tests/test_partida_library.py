"""Tests del núcleo de la biblioteca de partidas (sin PySide6)."""

from datetime import date

import pytest

from src.core.partida_library import canonical_unit, line_status, parse_budget_date


@pytest.mark.parametrize("raw,esperada", [
    ("p.a.", "p.a."), ("P.A.", "p.a."), ("p.a", "p.a."), ("pa", "p.a."), ("P.a.", "p.a."), ("Partida", "p.a."),
    ("ud", "ud"), ("Ud", "ud"), ("UD", "ud"), ("ud.", "ud"),
    ("m2", "m2"), ("M2", "m2"), ("m²", "m2"),
    ("m", "m"), ("M", "m"), ("ml", "m"),
    ("m3", "m3"), ("kg", "kg"), ("DIAS", "día"), ("día", "día"),
    ("65807DC0", "?"), ("1650", "?"), ("", "?"), (None, "?"),
])
def test_canonical_unit(raw, esperada):
    assert canonical_unit(raw) == esperada


@pytest.mark.parametrize("raw,esperada", [
    ("13/02/26", date(2026, 2, 13)),
    ("13/02/2026", date(2026, 2, 13)),
    ("46036", date(2026, 1, 14)),
    ("46041", date(2026, 1, 19)),
    ("%", None), ("SAN VICENTE", None), ("", None), (None, None),
    ("CERTIFICACIÓN Nº 2          Fecha: 08/11/24", date(2024, 11, 8)),  # certificaciones
    ("CERTIFICACIÓN Nº 3", None),
    ("31/02/26", None),      # fecha imposible
    ("12345", None),         # serie fuera de [30000, 60000]
])
def test_parse_budget_date(raw, esperada):
    assert parse_budget_date(raw) == esperada


@pytest.mark.parametrize("learning,analysis,esperado", [
    ("INCLUDED", "VALID", "approved"),
    ("INCLUDED", "VALID_WITH_WARNINGS", "approved"),
    ("PENDING_REVIEW", "VALID", "unreviewed"),
    ("NOT_ELIGIBLE", "VALID", "ineligible"),
    ("INCLUDED", "READ_ERROR", "ineligible"),
    ("PENDING_REVIEW", "EXCLUDED_INCOMPLETE_DATA", "ineligible"),
    ("", "", "ineligible"),
])
def test_line_status(learning, analysis, esperado):
    assert line_status(learning, analysis) == esperado


# ── H2: carga desde la BD ───────────────────────────────────────────────

from datetime import datetime

from src.core.partida_library import PartidaLibrary
from src.core.repositories import (
    approve_budget_for_learning,
    insert_historical_partida,
    upsert_historical_budget,
)


def _budget(tmp_path, nombre, *, aprobado=False, analysis="VALID", fecha="13/02/26"):
    bid, err = upsert_historical_budget({
        "ruta_excel": str(tmp_path / f"{nombre}.xlsx"),
        "ruta_carpeta": str(tmp_path),
        "nombre_proyecto": nombre,
        "fecha_modificacion_excel": datetime.now().isoformat(),
        "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fecha_presupuesto": fecha,
        "analisis_ok": True,
        "analysis_status": analysis,
        # Como hace el analizador: todo presupuesto nuevo empieza pendiente.
        "learning_status": "PENDING_REVIEW",
        "file_sha256": f"sha-{nombre}",
    })
    assert err is None
    if aprobado:
        assert approve_budget_for_learning(bid, "TEST") is None
    return bid


def _partida(bid, concepto, unidad, precio, orden=1):
    pid, err = insert_historical_partida(bid, {
        "orden": orden,
        "titulo": concepto.split("\n")[0],
        "concepto_original": concepto,
        "unidad": unidad,
        "precio_unitario": precio,
        "cantidad": 1,
        "total_linea": precio,
    })
    assert err is None
    return pid


@pytest.fixture
def db_biblioteca(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "biblioteca.db"))
    monkeypatch.setenv("CUBIAPP_BACKUP_DIR", str(tmp_path / "backups"))
    aprobado = _budget(tmp_path, "001-26 Aprobado", aprobado=True)
    pendiente = _budget(tmp_path, "002-26 Pendiente", fecha="46036")
    roto = _budget(tmp_path, "003-26 Roto", analysis="READ_ERROR", fecha="%")
    _partida(aprobado, "SUSTITUCIÓN BAJANTE PVC.\nSustitución de bajante de PVC de 110 mm", "ml", 30.0, 1)
    _partida(aprobado, "Pintura de escalera", "p.a.", 0, 2)            # sin precio: no se carga
    _partida(pendiente, "SUSTITUCIÓN BAJANTE PVC.\nSustitución de bajante de PVC de 110 mm", "m", 34.0, 1)
    _partida(pendiente, "Impermeabilización de cubierta", "M2", 22.5, 2)
    _partida(roto, "Impermeabilización de cubierta", "m2", 50.0, 1)
    return tmp_path


def test_load_carga_solo_partidas_con_precio_y_su_estado(db_biblioteca):
    lib = PartidaLibrary.load()

    assert len(lib.lines) == 4
    por_proyecto = {(l.proyecto, l.precio): l for l in lib.lines}
    bajante_ok = por_proyecto[("001-26 Aprobado", 30.0)]
    assert bajante_ok.status == "approved"
    assert bajante_ok.unidad == "ml" and bajante_ok.unidad_canon == "m"
    assert bajante_ok.concepto.startswith("SUSTITUCIÓN BAJANTE PVC.")
    assert bajante_ok.concepto_norm  # normalizado no vacío
    assert por_proyecto[("002-26 Pendiente", 34.0)].status == "unreviewed"
    assert por_proyecto[("002-26 Pendiente", 34.0)].fecha == date(2026, 1, 14)
    roto = por_proyecto[("003-26 Roto", 50.0)]
    assert roto.status == "ineligible" and roto.fecha is None


def test_load_ignora_lineas_invalidas_y_las_cuenta(db_biblioteca):
    from src.core import database

    with database.get_connection() as conn:
        conn.execute("UPDATE historical_partida SET concepto_original='', titulo='', concepto_normalizado='' "
                     "WHERE precio_unitario = 22.5")
        conn.commit()

    lib = PartidaLibrary.load()

    assert len(lib.lines) == 3
    assert lib.ignored == 1
