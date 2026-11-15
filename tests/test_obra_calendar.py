"""Núcleo del calendario de obras (sin Qt)."""

from datetime import date

from src.core import obra_calendar as oc

HOY = date(2026, 11, 16)


def _row(numero, plan=None, carpeta=None, duplicado=False, propuesta=None):
    nombre = carpeta or f"{numero} C.P. RAFAEL ASÍN 23 (HUMEDADES)"
    return {
        "numero": numero,
        "ruta_carpeta": f"C:/obras/X/{nombre}",
        "ruta_excel": f"C:/obras/X/{nombre}/p.xlsx",
        "planificacion": plan or {},
        "planificacion_duplicado": duplicado,
        "planificacion_propuesta": propuesta,
    }


def _ev(eventos, numero, tipo):
    return next(e for e in eventos if e.numero == numero and e.tipo == tipo)


def test_short_label_recorta_el_nombre():
    assert oc.short_label(_row("114-26")) == "114-26 C.P. RAFAEL ASÍN…"
    assert oc.short_label(_row("208-26", carpeta="208-26 OBRA")) == "208-26 OBRA"


def test_month_title():
    assert oc.month_title(2026, 11) == "Noviembre 2026"


def test_ejecutar_inicio_y_fin_previstos_arrastrables():
    plan = {"inicio_previsto": date(2026, 11, 20), "fin_previsto": date(2026, 11, 30)}
    eventos = oc.build_events({"EJECUTAR": [_row("114-26", plan)]}, HOY, 7)
    ini, fin = _ev(eventos, "114-26", "inicio"), _ev(eventos, "114-26", "fin")
    assert (ini.fecha, ini.real, ini.arrastrable, ini.color) == (date(2026, 11, 20), False, True, "warning")
    assert ini.texto.startswith("▶ 114-26")
    assert "dentro del margen" in ini.ayuda
    assert (fin.fecha, fin.real, fin.arrastrable, fin.color) == (date(2026, 11, 30), False, True, "")
    assert fin.texto.startswith("■ 114-26")


def test_ejecutar_inicio_pasado_en_rojo():
    eventos = oc.build_events({"EJECUTAR": [_row("114-26", {"inicio_previsto": date(2026, 11, 10)})]}, HOY, 7)
    ini = _ev(eventos, "114-26", "inicio")
    assert ini.color == "late" and "(pasada)" in ini.ayuda


def test_margen_propio_de_la_obra():
    plan = {"inicio_previsto": date(2026, 11, 20), "margen_aviso_dias": 2}
    eventos = oc.build_events({"EJECUTAR": [_row("114-26", plan)]}, HOY, 7)
    assert _ev(eventos, "114-26", "inicio").color == ""


def test_ejecutando_inicio_real_fijo_y_fin_con_retraso():
    plan = {"inicio_real": date(2026, 11, 1), "inicio_real_aproximado": True, "fin_previsto": date(2026, 11, 10)}
    eventos = oc.build_events({"EJECUTANDO": [_row("50-26", plan)]}, HOY, 7)
    ini, fin = _ev(eventos, "50-26", "inicio"), _ev(eventos, "50-26", "fin")
    assert (ini.real, ini.aproximada, ini.arrastrable) == (True, True, False)
    assert ini.texto.startswith("≈▶ 50-26")
    assert "Fecha real: se cambia con doble clic" in ini.ayuda
    assert (fin.arrastrable, fin.color) == (True, "late")
    assert "(con retraso)" in fin.ayuda


def test_ejecutando_sin_inicio_real_usa_el_previsto_sin_arrastrar():
    eventos = oc.build_events({"EJECUTANDO": [_row("50-26", {"inicio_previsto": date(2026, 11, 3)})]}, HOY, 7)
    ini = _ev(eventos, "50-26", "inicio")
    assert (ini.fecha, ini.real, ini.arrastrable) == (date(2026, 11, 3), False, False)


def test_terminado_fechas_reales():
    plan = {"inicio_real": date(2026, 11, 2), "fin_real": date(2026, 11, 12)}
    eventos = oc.build_events({"TERMINADO": [_row("7-26", plan)]}, HOY, 7)
    fin = _ev(eventos, "7-26", "fin")
    assert fin.texto.startswith("✔ 7-26") and fin.real and not fin.arrastrable


def test_sin_extremo_y_repetidas_no_salen():
    filas = {
        "EJECUTAR": [
            _row("1-26", {"fin_previsto": date(2026, 11, 30)}),
            _row("2-26", {"inicio_previsto": date(2026, 11, 20)}, duplicado=True),
        ]
    }
    eventos = oc.build_events(filas, HOY, 7)
    assert [(e.numero, e.tipo) for e in eventos] == [("1-26", "fin")]


def test_month_weeks_empieza_en_lunes():
    semanas = oc.month_weeks(2026, 11)  # el 1 de noviembre de 2026 es domingo
    assert semanas[0][0] == date(2026, 10, 26)
    assert semanas[0][6] == date(2026, 11, 1)
    assert all(len(s) == 7 for s in semanas)
    assert semanas[-1][0] == date(2026, 11, 30)


def test_month_weeks_febrero_bisiesto():
    dias = [d for s in oc.month_weeks(2028, 2) for d in s]
    assert date(2028, 2, 29) in dias


def test_events_by_day_inicio_antes_que_fin():
    filas = {
        "EJECUTAR": [
            _row("100-26", {"inicio_previsto": date(2026, 11, 1), "fin_previsto": date(2026, 11, 20)}),
            _row("200-26", {"inicio_previsto": date(2026, 11, 20)}),
        ]
    }
    por_dia = oc.events_by_day(oc.build_events(filas, HOY, 7))
    assert [(e.numero, e.tipo) for e in por_dia[date(2026, 11, 20)]] == [("200-26", "inicio"), ("100-26", "fin")]


def test_unscheduled_ordena_y_propone():
    filas = [
        _row("114-26", propuesta=(date(2026, 7, 13), False)),
        _row("30-26", propuesta=(date(2026, 7, 1), True)),
        _row("9-26", {"inicio_previsto": date(2026, 12, 1)}),
        _row("5-26", duplicado=True),
    ]
    items = oc.unscheduled(filas)
    assert [i["numero"] for i in items] == ["30-26", "114-26"]
    assert items[0]["propuesta_texto"] == "≈ julio de 2026 según el nombre"
    assert items[1]["propuesta_texto"] == "≈ 13/07/26 según el nombre"
    assert oc.proposal_text(None) == ""


def _resumen_filas():
    return {
        "EJECUTAR": [
            _row("1-26", {"inicio_previsto": date(2026, 11, 20)}),
            _row("2-26", {"inicio_previsto": date(2026, 11, 10)}),
        ],
        "EJECUTANDO": [
            _row("3-26", {"inicio_real": date(2026, 10, 1), "fin_previsto": date(2026, 11, 10)}),
        ],
        "TERMINADO": [
            _row("4-26", {"inicio_real": date(2026, 11, 1), "fin_real": date(2026, 11, 11)}),
            _row("5-26", {"inicio_real": date(2026, 11, 1), "fin_real": date(2026, 11, 21)}),
            _row("6-26", {"inicio_real": date(2026, 11, 5), "fin_real": date(2026, 11, 20)}),
        ],
    }


def test_month_summary_con_media():
    resumen = oc.month_summary(oc.build_events(_resumen_filas(), HOY, 7), 2026, 11)
    assert resumen == oc.MonthSummary(5, 4, 2, 15, 3)
    assert oc.summary_text(resumen) == (
        "Este mes: 5 empiezan · 4 terminan · 2 con retraso · duración media 15 días (3 obras)"
    )


def test_month_summary_sin_datos_suficientes():
    filas = _resumen_filas()
    filas["TERMINADO"] = filas["TERMINADO"][:2]
    resumen = oc.month_summary(oc.build_events(filas, HOY, 7), 2026, 11)
    assert resumen.duracion_media is None and resumen.obras_duracion == 2
    assert oc.summary_text(resumen).endswith("duración media: sin datos suficientes")


def test_summary_text_singular():
    assert oc.summary_text(oc.MonthSummary(1, 1, 0, None, 0)) == (
        "Este mes: 1 empieza · 1 termina · 0 con retraso · duración media: sin datos suficientes"
    )


def test_drop_inicio_desde_sin_fecha():
    assert oc.drop_fields({}, "EJECUTAR", "inicio", date(2026, 11, 25)) == ({"inicio_previsto": date(2026, 11, 25)}, "")


def test_drop_inicio_desplaza_el_fin():
    plan = {"inicio_previsto": date(2026, 11, 20), "fin_previsto": date(2026, 11, 30)}
    campos, motivo = oc.drop_fields(plan, "EJECUTAR", "inicio", date(2026, 11, 23))
    assert campos == {"inicio_previsto": date(2026, 11, 23), "fin_previsto": date(2026, 12, 3)} and motivo == ""


def test_drop_inicio_sin_previo_despues_del_fin_se_rechaza():
    campos, motivo = oc.drop_fields({"fin_previsto": date(2026, 11, 10)}, "EJECUTAR", "inicio", date(2026, 11, 25))
    assert campos is None and motivo == "El inicio no puede ser después del fin previsto (10/11)."


def test_drop_mismo_dia_no_hace_nada():
    assert oc.drop_fields({"inicio_previsto": date(2026, 11, 20)}, "EJECUTAR", "inicio", date(2026, 11, 20)) == (None, "")


def test_drop_inicio_fuera_de_ejecutar_se_rechaza():
    campos, motivo = oc.drop_fields({}, "EJECUTANDO", "inicio", date(2026, 11, 20))
    assert campos is None and motivo == "Solo se puede mover el inicio previsto de las obras de EJECUTAR."


def test_drop_fin_antes_del_inicio_se_rechaza():
    plan = {"inicio_previsto": date(2026, 11, 20), "fin_previsto": date(2026, 11, 30)}
    campos, motivo = oc.drop_fields(plan, "EJECUTAR", "fin", date(2026, 11, 10))
    assert campos is None and motivo == "El fin no puede ser antes del inicio (20/11)."


def test_drop_fin_en_ejecutando_usa_el_inicio_real():
    plan = {"inicio_real": date(2026, 11, 5), "fin_previsto": date(2026, 11, 30)}
    assert oc.drop_fields(plan, "EJECUTANDO", "fin", date(2026, 11, 6)) == ({"fin_previsto": date(2026, 11, 6)}, "")
    assert oc.drop_fields(plan, "EJECUTANDO", "fin", date(2026, 11, 4))[0] is None


def test_drop_fin_de_terminado_se_rechaza():
    campos, motivo = oc.drop_fields({"fin_real": date(2026, 11, 5)}, "TERMINADO", "fin", date(2026, 11, 6))
    assert campos is None and motivo == "Las fechas reales se cambian con doble clic."


def test_clear_fields():
    assert oc.clear_fields({}) is None
    assert oc.clear_fields({"inicio_previsto": date(2026, 11, 20)}) == {"inicio_previsto": None, "fin_previsto": None}


def test_proposal_fields():
    assert oc.proposal_fields({}, (date(2026, 7, 13), False)) == {"inicio_previsto": date(2026, 7, 13)}
    assert oc.proposal_fields({}, (date(2026, 7, 1), True)) == {
        "inicio_previsto": date(2026, 7, 1), "notas": oc.NOTA_PREVISTA_APROXIMADA,
    }
    assert oc.proposal_fields({"notas": "andamio"}, (date(2026, 7, 1), True)) == {"inicio_previsto": date(2026, 7, 1)}
