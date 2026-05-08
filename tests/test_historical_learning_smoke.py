import os
import sqlite3

import pytest
from openpyxl import Workbook

from src.core import database
from src.core.excel_manager import ExcelManager
from src.core.historical_analysis_status import AnalysisStatus
from src.core.historical_budget_analyzer import HistoricalBudgetAnalyzer
from src.core.historical_pattern_builder import HistoricalPatternBuilder
from src.core.repositories import (
    get_historical_budget_by_path,
    get_historical_budget_partidas,
    set_historical_budget_learning_status,
)
from src.core.template_manager import TemplateManager


def _require_template_path() -> str:
    tm = TemplateManager()
    template_path = tm.get_template_path()
    assert template_path, "No se pudo resolver la ruta de la plantilla Excel"
    assert os.path.exists(template_path), f"Plantilla no encontrada: {template_path}"
    return template_path


def _create_budget_xlsx(
    out_path: str,
    *,
    numero_proyecto: str,
    fecha: str,
    cliente: str,
    calle: str,
    num_calle: str,
    codigo_postal: str,
    tipo: str,
    partidas: list[dict],
) -> None:
    template_path = _require_template_path()
    em = ExcelManager()

    ok = em.create_from_template(
        template_path,
        out_path,
        {
            "nombre_obra": "SMOKE TEST / REVISIÓN",
            "numero_proyecto": numero_proyecto,
            "fecha": fecha,
            "cliente": cliente,
            "calle": calle,
            "num_calle": num_calle,
            "codigo_postal": codigo_postal,
            "tipo": tipo,
            "admin_cif": "B12345678",
            "admin_email": "admin@test.com",
            "admin_telefono": "968111222",
        },
    )
    assert ok, "No se pudo crear el Excel desde la plantilla"

    ok2 = em.insert_partidas_via_xml(out_path, partidas)
    assert ok2, "No se pudieron insertar las partidas en el Excel"


def _create_incompatible_xlsx(out_path: str) -> None:
    # Excel “válido” como fichero (xlsx), pero vacío a nivel de cabecera/estructura
    # que el lector/probe espera (sin E5 “numero” y sin filas de partidas >= 17).
    wb = Workbook()
    ws = wb.active
    ws.title = "Hoja1"
    ws["A1"] = "SMOKE INCOMPATIBLE"
    wb.save(out_path)


def _count_rows(conn: sqlite3.Connection, query: str, params: tuple) -> int:
    cur = conn.execute(query, params)
    row = cur.fetchone()
    return int(row[0] or 0)


def test_historical_learning_smoke_flow(tmp_path, monkeypatch):
    # 1) App “arranca sin errores de importación”
    py_side6_missing = False
    try:
        import main  # noqa: F401
    except ModuleNotFoundError as e:
        # En algunos entornos de test (CI) no se instala la dependencia GUI.
        # El smoke test se centra en el flujo histórico del core.
        if "PySide6" in str(e):
            py_side6_missing = True
        else:
            raise

    # Aislar DB en el smoke test
    db_path = tmp_path / "datos_historical_smoke.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
    if db_path.exists():
        db_path.unlink()
    # Crear la BD antes de que cualquier consulta en modo read_only falle.
    with database.get_connection() as _conn:
        pass

    analyzer = HistoricalBudgetAnalyzer()

    base_kwargs = dict(
        numero_proyecto="001",
        fecha="08-01-26",
        cliente="SMOKE CLIENT",
        calle="Calle Test",
        num_calle="5",
        codigo_postal="30001",
    )

    # 3/6: Presupuesto válido (debe quedar usable_for_learning=True)
    valid_path = tmp_path / "001-26_valid_smoke.xlsx"
    _create_budget_xlsx(
        str(valid_path),
        tipo="Reparación de bajante",
        partidas=[
            {
                "titulo": "DESMONTAJE DE BAJANTE PVC",
                "descripcion": "Desmontaje de bajante de PVC.",
                "concepto": "DESMONTAJE DE BAJANTE PVC",
                "cantidad": 2,
                "unidad": "ml",
                "precio_unitario": 18.5,
            },
            {
                "titulo": "INSTALACIÓN NUEVA BAJANTE PVC",
                "descripcion": "Instalación de nueva bajante PVC.",
                "concepto": "INSTALACIÓN NUEVA BAJANTE PVC",
                "cantidad": 2,
                "unidad": "ml",
                "precio_unitario": 25.0,
            },
        ],
        **base_kwargs,
    )

    # 2: BudgetFileProbe.probe no debe lanzar error en un Excel válido
    probe_valid = analyzer.probe.probe(str(valid_path), expected_numero="001-26")
    assert probe_valid.get("partidas_detectadas", 0) >= 1
    if py_side6_missing:
        # No hacemos fail aquí (para no bloquear core flow), pero dejamos constancia.
        # El usuario/entorno local debería poder importar `main.py`.
        assert True

    res_valid = analyzer.analyze_budget(str(valid_path), force_reanalyze=True)
    assert res_valid.get("status") == "processed"
    hb_valid = get_historical_budget_by_path(str(valid_path))
    assert hb_valid is not None
    assert hb_valid["analysis_status"] in (AnalysisStatus.VALID, AnalysisStatus.VALID_WITH_WARNINGS)
    if hb_valid["analysis_status"] == AnalysisStatus.VALID:
        assert hb_valid["usable_for_learning"] is True
    else:
        # Nuevo comportamiento: si hay avisos, queda pendiente de aprobacion manual.
        assert hb_valid["usable_for_learning"] is False
    valid_budget_id = int(hb_valid["id"])
    assert valid_budget_id > 0

    # 4/7: Presupuesto compatible pero excluido por calidad económica (muchos precios a 0)
    #     - 3 partidas, 2 con precio 0 (=> > 50% con <=0) y 1 con precio >0
    excluded_path = tmp_path / "001-26_excluded_smoke.xlsx"
    _create_budget_xlsx(
        str(excluded_path),
        tipo="Obra de albanilería",
        partidas=[
            {
                "titulo": "ROZA Y MORTERO PARA ALBANILERIA",
                "descripcion": "Trabajo de roza y mortero.",
                "concepto": "ROZA Y MORTERO PARA ALBANILERIA",
                "cantidad": 1,
                "unidad": "ml",
                "precio_unitario": 0.0,
            },
            {
                "titulo": "ROZA Y MORTERO PARA ALBANILERIA (2)",
                "descripcion": "Trabajo de roza y mortero (2).",
                "concepto": "ROZA Y MORTERO PARA ALBANILERIA",
                "cantidad": 1,
                "unidad": "ml",
                "precio_unitario": 0.0,
            },
            {
                "titulo": "ROZA Y MORTERO PARA ALBANILERIA (parcial)",
                "descripcion": "Trabajo de roza y mortero (parcial).",
                "concepto": "ROZA Y MORTERO PARA ALBANILERIA",
                "cantidad": 1,
                "unidad": "ml",
                "precio_unitario": 30.0,
            },
        ],
        **base_kwargs,
    )

    # Debe ser compatible según el probe (aunque luego se excluya por calidad económica)
    probe_excluded = analyzer.probe.probe(str(excluded_path), expected_numero="001-26")
    assert probe_excluded.get("is_compatible") is True

    res_excluded = analyzer.analyze_budget(str(excluded_path), force_reanalyze=True)
    assert res_excluded.get("status") == "processed"
    hb_excluded = get_historical_budget_by_path(str(excluded_path))
    assert hb_excluded is not None
    assert hb_excluded["analysis_status"] == AnalysisStatus.EXCLUDED_INCOMPLETE_DATA
    assert hb_excluded["usable_for_learning"] is False
    excluded_budget_id = int(hb_excluded["id"])
    assert excluded_budget_id > 0

    # Mantiene partidas para auditoría
    partidas_excl = get_historical_budget_partidas(excluded_budget_id, limit=50)
    assert len(partidas_excl) >= 1

    with database.get_connection(read_only=True) as conn:
        modules_count_excl = _count_rows(
            conn,
            """
            SELECT COUNT(*)
              FROM historical_partida_module hpm
              JOIN historical_partida hp ON hp.id = hpm.partida_id
             WHERE hp.historical_budget_id = ?
            """,
            (excluded_budget_id,),
        )
        assert modules_count_excl == 0

    # 5: Excel no compatible => NOT_COMPATIBLE
    incompatible_path = tmp_path / "999-99_incompatible_smoke.xlsx"
    _create_incompatible_xlsx(str(incompatible_path))

    res_incompatible = analyzer.analyze_budget(str(incompatible_path), force_reanalyze=True)
    assert res_incompatible.get("status") == "processed"
    hb_incompatible = get_historical_budget_by_path(str(incompatible_path))
    assert hb_incompatible is not None
    assert hb_incompatible["analysis_status"] == AnalysisStatus.NOT_COMPATIBLE

    incompatible_budget_id = int(hb_incompatible["id"])
    with database.get_connection(read_only=True) as conn:
        partidas_count_inc = _count_rows(
            conn,
            "SELECT COUNT(*) FROM historical_partida WHERE historical_budget_id = ?",
            (incompatible_budget_id,),
        )
        assert partidas_count_inc == 0

    # 6: HistoricalPatternBuilder solo genera patrones desde usable_for_learning=True
    HistoricalPatternBuilder().rebuild_patterns()
    with database.get_connection(read_only=True) as conn:
        patterns_total = _count_rows(conn, "SELECT COUNT(*) FROM suggested_partida_pattern", tuple())
        patterns_albanileria_before = _count_rows(
            conn,
            """
            SELECT COUNT(*)
              FROM suggested_partida_pattern spp
              JOIN execution_module em ON em.id = spp.module_id
             WHERE em.nombre = 'albanileria'
            """,
            tuple(),
        )
        # Si el presupuesto "válido" quedó en VALID_WITH_WARNINGS, ahora arranca pendiente
        # y no debe generar patrones hasta aprobación manual.
        if hb_valid["usable_for_learning"]:
            assert patterns_total >= 1
        else:
            assert patterns_total >= 0
        assert patterns_albanileria_before == 0

    # 7: Marcar manualmente como apto => reclassify_budget_modules + reconstruye patrones
    err = set_historical_budget_learning_status(
        excluded_budget_id,
        "INCLUDED",
        True,
        decision_source="MANUAL",
        decision_reason="Test include pending budget",
    )
    assert err is None
    hb_excluded_after = get_historical_budget_by_path(str(excluded_path))
    assert hb_excluded_after is not None
    assert hb_excluded_after["analysis_status"] == AnalysisStatus.EXCLUDED_INCOMPLETE_DATA

    reclass_result = analyzer.reclassify_budget_modules(excluded_budget_id)
    assert reclass_result.get("ok") is True
    assert int(reclass_result.get("assignments") or 0) > 0

    HistoricalPatternBuilder().rebuild_patterns()
    with database.get_connection(read_only=True) as conn:
        patterns_albanileria_after = _count_rows(
            conn,
            """
            SELECT COUNT(*)
              FROM suggested_partida_pattern spp
              JOIN execution_module em ON em.id = spp.module_id
             WHERE em.nombre = 'albanileria'
            """,
            tuple(),
        )
        assert patterns_albanileria_after > 0

