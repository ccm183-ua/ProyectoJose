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


# ── H3: búsqueda, agrupación, cifras y orden ────────────────────────────

from src.core.partida_library import (
    WARNING_LUMP_SUM,
    WARNING_NO_APPROVED,
    LibraryLine,
)


def _line(pid, concepto_norm, precio, status="approved", unidad="m2", budget=None, fecha=None, module="fachada"):
    return LibraryLine(
        partida_id=pid, budget_id=budget if budget is not None else pid, proyecto=f"obra {pid}",
        concepto=concepto_norm.upper(), concepto_norm=concepto_norm, unidad=unidad,
        unidad_canon=canonical_unit(unidad), precio=precio, status=status, fecha=fecha, module=module,
    )


def test_busqueda_exige_todas_las_palabras_desde_inicio_de_palabra():
    lib = PartidaLibrary([
        _line(1, "impermeabilizacion de cubierta plana", 20),
        _line(2, "alicatado de bano", 30, module="alicatado"),
        _line(3, "impermeabilizacion de terraza", 25),
    ])
    conceptos = [g.concepto_norm for g in lib.search("imperm cubierta").groups]
    assert conceptos == ["impermeabilizacion de cubierta plana"]
    assert lib.search("atado").groups == []       # no casa dentro de "alicatado"


def test_consulta_vacia_sin_filtros_no_devuelve_nada():
    lib = PartidaLibrary([_line(1, "bajante pvc", 30)])
    assert lib.search("").groups == []
    assert [g.concepto_norm for g in lib.search("", module="fachada").groups] == ["bajante pvc"]


def test_agrupa_por_concepto_y_unidad_canonica_con_cifras():
    lib = PartidaLibrary([
        _line(1, "bajante pvc", 30, unidad="ml", fecha=date(2026, 1, 10)),
        _line(2, "bajante pvc", 34, unidad="m", status="unreviewed", fecha=date(2026, 3, 1)),
        _line(3, "bajante pvc", 50, unidad="M", status="unreviewed"),
        _line(4, "bajante pvc", 90, unidad="ud"),          # otra unidad: otro grupo
    ])
    grupos = {g.unidad_canon: g for g in lib.search("bajante").groups}
    g = grupos["m"]
    assert len(g.lines) == 3 and g.n_budgets == 3
    assert (g.price_min, g.price_median, g.price_max) == (30, 34, 50)
    assert g.approved_median == 30
    assert g.status == "approved"
    assert g.fecha == date(2026, 3, 1)
    assert (g.proposed_price, g.price_basis) == (30, "median_approved")
    assert g.warnings == ()


def test_sin_aprobadas_propone_la_mediana_de_todas_con_aviso():
    lib = PartidaLibrary([
        _line(1, "picado fachada", 10, status="unreviewed", unidad="p.a."),
        _line(2, "picado fachada", 20, status="unreviewed", unidad="P.A."),
    ])
    g = lib.search("picado").groups[0]
    assert (g.proposed_price, g.price_basis, g.approved_median) == (15, "median_all", None)
    assert WARNING_NO_APPROVED in g.warnings and WARNING_LUMP_SUM in g.warnings


def test_filtros_de_estado_unidad_y_modulo():
    lib = PartidaLibrary([
        _line(1, "pintura escalera", 100, status="approved", unidad="p.a.", module="pintura"),
        _line(2, "pintura fachada", 200, status="ineligible", unidad="m2", module="pintura"),
        _line(3, "pintura techo", 50, status="unreviewed", unidad="m2", module="pintura"),
    ])
    assert {g.concepto_norm for g in lib.search("pintura", status_filter="approved").groups} == {"pintura escalera"}
    assert {g.concepto_norm for g in lib.search("pintura", status_filter="no_ineligible").groups} == {
        "pintura escalera", "pintura techo"}
    assert {g.concepto_norm for g in lib.search("pintura", unit="m2").groups} == {"pintura fachada", "pintura techo"}
    assert lib.search("pintura", module="fachada").groups == []


def test_orden_aprobadas_primero_luego_obras_y_fecha():
    lib = PartidaLibrary([
        _line(1, "sellado junta a", 10, status="unreviewed", budget=1),
        _line(2, "sellado junta a", 11, status="unreviewed", budget=2),
        _line(3, "sellado junta b", 12, status="approved", budget=3),
        _line(4, "sellado junta c", 13, status="unreviewed", budget=4, fecha=date(2026, 5, 1)),
    ])
    assert [g.concepto_norm for g in lib.search("sellado").groups] == [
        "sellado junta b",   # evidencia aprobada
        "sellado junta a",   # 2 obras
        "sellado junta c",   # 1 obra, con fecha
    ]


def test_limite_de_grupos():
    lib = PartidaLibrary([_line(i, f"partida {i:03d}", 10) for i in range(250)])
    result = lib.search("partida")
    assert len(result.groups) == 200 and result.total_groups == 250 and result.truncated


# ── H4: conversión a candidata ──────────────────────────────────────────

from src.core.partida_library import to_candidate
from src.core.services.budget_partidas_flow import MODE_APPEND, split_generated_partidas_for_review


def _grupo_bajante():
    lines = [
        LibraryLine(1, 10, "001-26", "SUSTITUCIÓN BAJANTE PVC.\nSustitución de bajante de PVC de 110 mm",
                    "sustitucion bajante pvc", "ml", "m", 30.0, "approved", date(2026, 1, 1), "sustitucion_bajante"),
        LibraryLine(2, 11, "002-26", "Bajante PVC", "sustitucion bajante pvc", "m", "m", 34.0, "unreviewed",
                    date(2026, 3, 1), "sustitucion_bajante"),
    ]
    return PartidaLibrary(lines).search("bajante").groups[0]


def test_candidata_con_la_mediana_del_grupo():
    c = to_candidate(_grupo_bajante())
    assert c["titulo"] == "SUSTITUCIÓN BAJANTE PVC."
    assert c["descripcion"] == "Sustitución de bajante de PVC de 110 mm"
    assert c["unidad"] == "ml" and c["cantidad"] == 1.0
    assert c["precio_unitario"] == 30.0
    assert c["source"] == "library"
    assert c["library_status"] == "approved"
    assert c["library_price_basis"] == "median_approved"
    assert c["library_partida_ids"] == [1, 2] and c["library_budget_ids"] == [10, 11]


def test_candidata_con_el_precio_de_una_obra_concreta():
    grupo = _grupo_bajante()
    obra = [l for l in grupo.lines if l.partida_id == 2][0]
    c = to_candidate(grupo, obra)
    assert c["precio_unitario"] == 34.0
    assert c["library_price_basis"] == "instance"
    assert c["library_status"] == "unreviewed"
    assert c["titulo"] == "Bajante PVC" and c["descripcion"] == ""
    assert c["library_partida_ids"] == [2]


def test_candidatas_de_biblioteca_no_cuentan_como_historicas():
    historicas, otras = split_generated_partidas_for_review([to_candidate(_grupo_bajante())], "create")
    assert historicas == [] and len(otras) == 1


def test_en_modo_anadir_se_descarta_el_duplicado_exacto():
    candidata = to_candidate(_grupo_bajante())
    existente = dict(candidata)
    historicas, otras = split_generated_partidas_for_review(
        [candidata], MODE_APPEND, existing_partidas=[existente]
    )
    assert historicas == [] and otras == []
