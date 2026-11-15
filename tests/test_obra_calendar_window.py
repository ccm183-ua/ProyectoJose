"""Ventana del calendario de obras (offscreen)."""

from datetime import date

import pytest

try:
    from PySide6.QtWidgets import QMessageBox

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")

HOY = date(2026, 11, 16)


def _row(numero, plan=None, carpeta=None, propuesta=None):
    nombre = carpeta or f"{numero} C.P. OBRA {numero}"
    return {
        "numero": numero, "ruta_carpeta": f"C:/obras/X/{nombre}", "ruta_excel": f"C:/obras/X/{nombre}/p.xlsx",
        "planificacion": dict(plan or {}), "planificacion_duplicado": False, "planificacion_propuesta": propuesta,
    }


@pytest.fixture
def entorno(qapp, tmp_path, monkeypatch):
    from src.core import database

    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "obras.db"))
    monkeypatch.setenv("CUBIAPP_BACKUP_DIR", str(tmp_path / "backups"))
    with database.get_connection():
        pass
    cajas = []
    for nombre in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, nombre, staticmethod(lambda *a, _n=nombre, **k: cajas.append(_n)))
    ventanas = []

    def abrir(filas, **extra):
        from src.core.obra_calendar_service import CalendarData
        from src.core.repositories.obra_planificacion_repository import upsert_plan
        from src.gui.obra_calendar_window import ObraCalendarWindow

        for rows in filas.values():
            for r in rows:
                if r["planificacion"]:
                    upsert_plan(r["numero"], **{k: v for k, v in r["planificacion"].items()})
        win = ObraCalendarWindow(None, hoy=HOY, autoload=False)
        win.set_data(CalendarData(filas_por_estado=filas, **extra))
        ventanas.append(win)
        return win

    yield abrir, cajas
    for w in ventanas:
        w.close()


def _plan(numero):
    from src.core.repositories.obra_planificacion_repository import get_planes

    return get_planes([numero]).get(numero)


def _toast(win):
    from src.gui.widgets.toast import current_toast

    return current_toast(win)


def test_pinta_el_mes_con_sus_etiquetas(entorno):
    abrir, _ = entorno
    win = abrir({"EJECUTAR": [_row("114-26", {"inicio_previsto": date(2026, 11, 20)})]})
    assert win.month_label.text() == "Noviembre 2026"
    assert [c.calendar_event.numero for c in win.cell_for(date(2026, 11, 20)).chips] == ["114-26"]
    vecino = win.cell_for(date(2026, 10, 26))
    assert vecino.en_mes is False and vecino.chips == []
    assert [c.text() for c in win.summary_cards] == [
        "1 empieza", "0 terminan", "0 con retraso", "Duración media: sin datos suficientes",
    ]


def test_mas_de_tres_en_un_dia(entorno):
    abrir, _ = entorno
    filas = [_row(f"{n}-26", {"inicio_previsto": date(2026, 11, 20)}) for n in range(1, 6)]
    win = abrir({"EJECUTAR": filas})
    celda = win.cell_for(date(2026, 11, 20))
    assert len(celda.chips) == 3
    assert celda.more_button.text() == "+2 más"
    assert len(celda.more_button.menu().actions()) == 5


def test_navegacion_de_meses(entorno):
    abrir, _ = entorno
    win = abrir({"EJECUTAR": []})
    win.go_next()
    assert win.month_label.text() == "Diciembre 2026"
    win.go_prev()
    win.go_prev()
    assert win.month_label.text() == "Octubre 2026"
    win.go_today()
    assert win.month_label.text() == "Noviembre 2026"


def test_sin_fecha_ordenada_con_propuesta(entorno):
    abrir, _ = entorno
    win = abrir({"EJECUTAR": [
        _row("114-26", propuesta=(date(2026, 7, 13), False)),
        _row("30-26"),
        _row("9-26", {"inicio_previsto": date(2026, 11, 20)}),
    ]})
    assert win.unscheduled_numeros() == ["30-26", "114-26"]
    filas = {r.numero: r for r in win.unscheduled_panel.rows}
    assert filas["114-26"].proposal_button is not None
    assert filas["30-26"].proposal_button is None
    assert win.unscheduled_panel.title.text() == "Sin fecha (2)"


def test_soltar_en_un_dia_guarda_y_deshacer_lo_quita(entorno):
    abrir, cajas = entorno
    win = abrir({"EJECUTAR": [_row("114-26")]})
    win.drop_on_day("114-26", "EJECUTAR", "inicio", date(2026, 11, 25))
    assert _plan("114-26")["inicio_previsto"] == date(2026, 11, 25)
    assert [c.calendar_event.numero for c in win.cell_for(date(2026, 11, 25)).chips] == ["114-26"]
    assert win.unscheduled_numeros() == []
    toast = _toast(win)
    assert toast.text() == "114-26: inicio previsto el 25/11"
    assert toast.action_labels() == ["Deshacer"]
    toast.trigger("Deshacer")
    assert _plan("114-26") is None
    assert win.cell_for(date(2026, 11, 25)).chips == []
    assert win.unscheduled_numeros() == ["114-26"]
    assert cajas == []


def test_mover_el_inicio_desplaza_el_fin(entorno):
    abrir, _ = entorno
    win = abrir({"EJECUTAR": [_row("114-26", {"inicio_previsto": date(2026, 11, 20),
                                               "fin_previsto": date(2026, 11, 30)})]})
    win.drop_on_day("114-26", "EJECUTAR", "inicio", date(2026, 11, 23))
    plan = _plan("114-26")
    assert (plan["inicio_previsto"], plan["fin_previsto"]) == (date(2026, 11, 23), date(2026, 12, 3))
    assert _toast(win).text() == "114-26: inicio previsto movido al 23/11"


def test_fin_antes_del_inicio_no_se_guarda(entorno):
    abrir, _ = entorno
    win = abrir({"EJECUTAR": [_row("114-26", {"inicio_previsto": date(2026, 11, 20),
                                               "fin_previsto": date(2026, 11, 30)})]})
    win.drop_on_day("114-26", "EJECUTAR", "fin", date(2026, 11, 10))
    assert _plan("114-26")["fin_previsto"] == date(2026, 11, 30)
    toast = _toast(win)
    assert toast.text() == "El fin no puede ser antes del inicio (20/11)."
    assert toast.action_labels() == []


def test_fecha_real_no_se_arrastra(entorno):
    abrir, _ = entorno
    win = abrir({"EJECUTANDO": [_row("50-26", {"inicio_real": date(2026, 11, 3)})]})
    chip = win.cell_for(date(2026, 11, 3)).chips[0]
    assert chip._payload is None
    win.drop_on_day("50-26", "EJECUTANDO", "inicio", date(2026, 11, 5))
    assert _plan("50-26")["inicio_real"] == date(2026, 11, 3)
    assert _toast(win).text() == "Solo se puede mover el inicio previsto de las obras de EJECUTAR."


def test_volver_a_sin_fecha_quita_las_previstas(entorno):
    abrir, _ = entorno
    win = abrir({"EJECUTAR": [_row("114-26", {"inicio_previsto": date(2026, 11, 20),
                                               "fin_previsto": date(2026, 11, 30)})]})
    win.drop_on_unscheduled("114-26", "EJECUTAR", "inicio")
    plan = _plan("114-26")
    assert plan["inicio_previsto"] is None and plan["fin_previsto"] is None
    assert _toast(win).text() == "114-26: fechas previstas quitadas"
    assert win.unscheduled_numeros() == ["114-26"]


def test_poner_esta_fecha_aproximada_deja_nota(entorno):
    from src.core.obra_calendar import NOTA_PREVISTA_APROXIMADA

    abrir, _ = entorno
    win = abrir({"EJECUTAR": [_row("30-26", propuesta=(date(2026, 7, 1), True))]})
    win.put_proposal("30-26")
    plan = _plan("30-26")
    assert plan["inicio_previsto"] == date(2026, 7, 1)
    assert plan["notas"] == NOTA_PREVISTA_APROXIMADA
    assert _toast(win).action_labels() == ["Deshacer"]


def test_error_al_guardar_no_cambia_nada(entorno, monkeypatch):
    import src.core.repositories.obra_planificacion_repository as repo

    abrir, cajas = entorno
    win = abrir({"EJECUTAR": [_row("114-26")]})
    monkeypatch.setattr(repo, "upsert_plan", lambda *a, **k: "disco lleno")
    win.drop_on_day("114-26", "EJECUTAR", "inicio", date(2026, 11, 25))
    assert cajas == ["critical"]
    assert _toast(win) is None
    assert win.unscheduled_numeros() == ["114-26"]


def test_guardar_avisa_al_resto_y_se_ignora_a_si_misma(entorno):
    from src.gui import planning_events

    abrir, _ = entorno
    win = abrir({"EJECUTAR": [_row("114-26")]})
    vistos = []

    def _oir(numeros, emisor):
        vistos.append((numeros, emisor))

    planning_events.planning_events().planning_changed.connect(_oir)
    try:
        win.drop_on_day("114-26", "EJECUTAR", "inicio", date(2026, 11, 25))
    finally:
        planning_events.planning_events().planning_changed.disconnect(_oir)
    assert vistos == [(["114-26"], win)]


def test_cambio_externo_refresca(entorno):
    from src.core.repositories.obra_planificacion_repository import upsert_plan
    from src.gui import planning_events

    abrir, _ = entorno
    win = abrir({"EJECUTAR": [_row("114-26")]})
    upsert_plan("114-26", inicio_previsto=date(2026, 11, 20))
    planning_events.notify_planning_changed(["114-26"], source=object())
    assert [c.calendar_event.numero for c in win.cell_for(date(2026, 11, 20)).chips] == ["114-26"]


def test_recarga_externa_vuelve_a_cargar(entorno, monkeypatch):
    from src.gui import planning_events

    abrir, _ = entorno
    win = abrir({"EJECUTAR": []})
    recargas = []
    monkeypatch.setattr(win, "reload", lambda: recargas.append(1))
    planning_events.notify_obras_reloaded(source=object())
    planning_events.notify_obras_reloaded(source=win)
    assert recargas == [1]


def test_avisos_de_cache_vacia_error_y_repetidas(entorno):
    from src.core.obra_calendar_service import ERROR_LECTURA

    abrir, _ = entorno
    vacia = abrir({}, vacia=True)
    assert "Presupuestos existentes" in vacia.message_label.text()
    assert not vacia.message_label.isHidden()
    rota = abrir({"EJECUTAR": [_row("114-26")]}, error=ERROR_LECTURA, repetidas=2)
    assert rota.message_label.text() == ERROR_LECTURA
    assert rota.footer_label.text() == "2 obras con número repetido, no se pueden planificar"
    normal = abrir({"EJECUTAR": [_row("114-26")]})
    assert normal.message_label.isHidden()
    assert normal.footer_label.text() == ""


def test_menu_de_obra(entorno):
    abrir, _ = entorno
    win = abrir({"EJECUTAR": [_row("114-26"), _row("9-26", {"inicio_previsto": date(2026, 11, 20)})]})
    sin_fechas = {a.text(): a.isEnabled() for a in win.build_menu("114-26").actions() if a.text()}
    assert sin_fechas == {"Planificación…": True, "Abrir Excel": True, "Abrir carpeta": True,
                          "Quitar fechas previstas": False}
    con_fechas = {a.text(): a.isEnabled() for a in win.build_menu("9-26").actions() if a.text()}
    assert con_fechas["Quitar fechas previstas"] is True


def test_doble_clic_guarda_lo_del_dialogo(entorno, monkeypatch):
    import src.gui.obra_planning_dialog as dlg_mod

    class _Dialogo:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 1

        def get_changes(self):
            return {"inicio_previsto": date(2026, 11, 27), "fin_previsto": None}

    monkeypatch.setattr(dlg_mod, "ObraPlanningDialog", _Dialogo)
    abrir, _ = entorno
    win = abrir({"EJECUTAR": [_row("114-26")]})
    win.edit_planning("114-26")
    assert _plan("114-26")["inicio_previsto"] == date(2026, 11, 27)
    assert _toast(win).text() == "114-26: planificación guardada"


# ── Revisión de diseño ───────────────────────────────────────────────────

def test_flechas_fijas_y_hoy_desactivado_en_el_mes_actual(entorno):
    abrir, _ = entorno
    win = abrir({"EJECUTAR": []})
    ancho = win.month_label.width()
    assert not win._btn_today.isEnabled()
    win.go_next()  # diciembre
    win.go_next()  # enero: nombre mucho más corto
    assert win.month_label.width() == ancho
    assert win._btn_today.isEnabled()


def test_resumen_con_retrasos_en_rojo(entorno):
    abrir, _ = entorno
    win = abrir({"EJECUTAR": [_row("114-26", {"inicio_previsto": date(2026, 11, 10)})]})
    retraso = win.summary_cards[2]
    assert retraso.text() == "1 con retraso"
    assert "#b91c1c" in retraso.styleSheet()
    assert len(win.summary_cards) == 4
    win.go_next()
    assert len(win.summary_cards) == 4


def test_etiqueta_recortada_con_puntos_suspensivos(entorno):
    abrir, _ = entorno
    carpeta = "114-26 C.P. RAFAEL ASIN 23 - GENERAL PINTOS 17 (HUMEDADES EN FACHADA)"
    win = abrir({"EJECUTAR": [_row("114-26", {"inicio_previsto": date(2026, 11, 20)}, carpeta=carpeta)]})
    win.resize(900, 700)
    win.show()
    chip = win.cell_for(date(2026, 11, 20)).chips[0]
    chip.resize(90, chip.height())
    assert chip.full_text() == f"▶ {carpeta}"
    assert chip.text().endswith("…") and len(chip.text()) < len(chip.full_text())
    assert carpeta in chip.toolTip()


def test_sin_fecha_muestra_el_nombre_completo_y_busca(entorno):
    abrir, _ = entorno
    win = abrir({"EJECUTAR": [
        _row("114-26", carpeta="114-26 C.P. RAFAEL ASIN 23 - GENERAL PINTOS 17 (HUMEDADES)"),
        _row("30-26", carpeta="30-26 C.P. DR. FLEMING 1 (FACHADA)"),
    ]})
    panel = win.unscheduled_panel
    textos = [l.text() for l in panel.rows[1].findChildren(type(panel.title))]
    assert "C.P. RAFAEL ASIN 23 - GENERAL PINTOS 17 (HUMEDADES)" in textos
    panel.search.setText("fleming")
    assert panel.visible_numeros() == ["30-26"]
    panel.search.setText("nada que coincida")
    assert panel.visible_numeros() == []
    assert panel.empty_label.text() == "Ninguna obra coincide con la búsqueda."
    panel.search.clear()
    assert panel.visible_numeros() == ["30-26", "114-26"]


def test_la_busqueda_se_mantiene_al_repintar(entorno):
    abrir, _ = entorno
    win = abrir({"EJECUTAR": [_row("114-26"), _row("30-26"), _row("9-26")]})
    win.unscheduled_panel.search.setText("114")
    win.drop_on_day("30-26", "EJECUTAR", "inicio", date(2026, 11, 25))
    assert win.unscheduled_panel.visible_numeros() == ["114-26"]


def test_el_dia_se_ilumina_al_arrastrar(entorno):
    abrir, _ = entorno
    win = abrir({"EJECUTAR": []})
    celda = win.cell_for(date(2026, 11, 20))
    antes = celda.styleSheet()
    celda._set_highlight(True)
    assert celda.highlighted and celda.styleSheet() != antes
    celda._set_highlight(False)
    assert celda.styleSheet() == antes


def test_ayuda_explica_arrastrar_y_atajos(entorno, monkeypatch):
    import src.gui.obra_calendar_window as cw

    abrir, _ = entorno
    win = abrir({"EJECUTAR": []})
    for frase in ("Arrastra una obra", "Deshacer", "doble clic", "RePág", "▶", "■", "✓"):
        assert frase in cw.HELP_HTML
    abiertas = []
    monkeypatch.setattr(cw._HelpDialog, "exec", lambda self: abiertas.append(self) or 0)
    win.show_help()
    assert len(abiertas) == 1


def test_atajos_de_teclado(entorno):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence

    abrir, _ = entorno
    win = abrir({"EJECUTAR": []})
    teclas = {a.key() for a in win._shortcuts}
    for tecla in (Qt.Key.Key_PageUp, Qt.Key.Key_PageDown, Qt.Key.Key_Home, Qt.Key.Key_F5, Qt.Key.Key_F1):
        assert QKeySequence(tecla) in teclas
    siguiente = next(a for a in win._shortcuts if a.key() == QKeySequence(Qt.Key.Key_PageDown))
    siguiente.activated.emit()
    assert win.month_label.text() == "Diciembre 2026"


def test_al_repintar_no_quedan_casillas_viejas_visibles(entorno):
    abrir, _ = entorno
    win = abrir({"EJECUTAR": []})
    win.show()
    win.go_next()
    from PySide6.QtWidgets import QApplication

    from src.gui.obra_calendar_window import _DayCell

    QApplication.processEvents()  # muestra las casillas nuevas; el borrado de las viejas sigue pendiente
    visibles = [c for c in win.findChildren(_DayCell) if c.isVisible()]
    assert len(visibles) == len(win._cells)


def test_ayuda_en_castellano(entorno):
    from PySide6.QtWidgets import QPushButton

    from src.gui.obra_calendar_window import _HelpDialog

    dialogo = _HelpDialog()  # referencia viva: si no, se destruye antes de leer los botones
    textos = [b.text() for b in dialogo.findChildren(QPushButton)]
    assert textos == ["Cerrar"]
