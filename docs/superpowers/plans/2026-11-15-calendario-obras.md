# Calendario de obras (pieza C) — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ventana «Calendario de obras» con un mes en cuadrícula, la lista «Sin fecha», una franja de resumen y fechas previstas que se ponen y se mueven arrastrando, con Deshacer.

**Architecture:** Un núcleo sin Qt (`src/core/obra_calendar.py`) convierte las filas con planificación en etiquetas por día, «Sin fecha», resumen y campos a guardar al soltar. Un servicio (`obra_calendar_service.py`) lee la caché del dashboard y añade la planificación con `enrich_with_planning`. La ventana (`src/gui/obra_calendar_window.py`) pinta y guarda con `upsert_plan` / `restore_plan_snapshot`; una señal compartida (`src/gui/planning_events.py`) mantiene al día dashboard y calendario.

**Tech Stack:** Python 3, PySide6, SQLite, pytest (offscreen).

**Diseño:** `docs/superpowers/specs/2026-11-15-calendario-obras-design.md`.

## Global Constraints

- Carpeta de trabajo: `C:\Users\cayet\Documentos\Documentos\Dev\ProyectoJose-calendario`, rama `calendario-obras`.
- Tests: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider <ruta>` desde la carpeta de trabajo.
- Todos los textos de interfaz en castellano de España, con tildes.
- Los tests de interfaz importan PySide6 dentro de `try/except ImportError` y usan `pytestmark = pytest.mark.skipif(...)` y la fixture `qapp`, como `tests/test_budget_dashboard_move_undo.py`.
- Ningún test puede abrir una ventana modal real: se sustituye `QMessageBox.information/warning/critical/question` con `monkeypatch`.
- Los tests que tocan la BD usan `CUBIAPP_DB_PATH` y `CUBIAPP_BACKUP_DIR` en `tmp_path`.
- No se toca el esquema de `obra_planificacion` ni el vocabulario/precios del pipeline de IA.
- Fechas previstas guardadas al arrastrar: exactas. Fechas reales: nunca se arrastran.
- Ajustes respecto al diseño (aprobados al planificar): `month_summary(eventos, año, mes)` calcula todo desde las etiquetas (no necesita planes) y `drop_fields(plan, fase, tipo, nueva_fecha)` recibe también la fase.

---

### Task C1: Núcleo del calendario

**Files:**
- Create: `src/core/obra_calendar.py`
- Modify: `src/core/obra_planning_service.py` (alias público `folder_name`)
- Test: `tests/test_obra_calendar.py`

**Interfaces:**
- Consumes: `src.core.obra_planning.color_category(inicio, margen, hoy) -> "" | "warning" | "late"`; `src.core.obra_planning_service.planning_key(row) -> str`. Filas como las deja `enrich_with_planning`: claves `ruta_carpeta`, `ruta_excel`, `nombre_proyecto`, `numero`, `planificacion` (dict con `inicio_previsto`, `fin_previsto`, `inicio_real`, `fin_real` como `date | None`, `inicio_real_aproximado`, `fin_real_aproximado` bool, `margen_aviso_dias` int | None, `notas`), `planificacion_duplicado` bool, `planificacion_propuesta` `(date, bool) | None`.
- Produces:
  - `FASES = ("EJECUTAR", "EJECUTANDO", "TERMINADO")`, `MAX_ETIQUETAS_DIA = 3`, `MIN_OBRAS_MEDIA = 3`, `NOTA_PREVISTA_APROXIMADA`.
  - `CalendarEvent` (frozen dataclass): `numero, texto, ayuda, fase, tipo ("inicio"|"fin"), fecha, real, aproximada, color, arrastrable, ruta_excel, ruta_carpeta`.
  - `MonthSummary(empiezan, terminan, con_retraso, duracion_media: int | None, obras_duracion)`.
  - `folder_name(row) -> str` (reexportado), `short_label(row) -> str`, `numero_sort_key(numero)`, `month_title(año, mes) -> str`.
  - `build_events(filas_por_estado, hoy, margen_general=7) -> list[CalendarEvent]`.
  - `month_weeks(año, mes) -> list[list[date]]`, `events_by_day(eventos) -> dict[date, list[CalendarEvent]]`.
  - `unscheduled(filas_ejecutar) -> list[dict]` con claves `numero, texto, ayuda, propuesta, propuesta_texto, ruta_excel, ruta_carpeta`; `proposal_text(propuesta) -> str`.
  - `month_summary(eventos, año, mes) -> MonthSummary`, `summary_text(MonthSummary) -> str`.
  - `drop_fields(plan, fase, tipo, nueva) -> tuple[dict | None, str]`, `clear_fields(plan) -> dict | None`, `proposal_fields(plan, propuesta) -> dict`.

- [ ] **Step 1: Escribir los tests**

`tests/test_obra_calendar.py`:

```python
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
```

- [ ] **Step 2: Ejecutarlos y ver que fallan**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_obra_calendar.py`
Expected: FAIL (`ModuleNotFoundError: No module named 'src.core.obra_calendar'`).

- [ ] **Step 3: Alias público en el servicio de planificación**

En `src/core/obra_planning_service.py`, justo debajo de la línea `_numero = planning_key`, añadir:

```python
folder_name = _folder_name
```

- [ ] **Step 4: Escribir el núcleo**

`src/core/obra_calendar.py`:

```python
"""Calendario de obras (núcleo, sin Qt).

Convierte las filas con planificación (ver
`obra_planning_service.enrich_with_planning`) en etiquetas por día, la lista
«Sin fecha», el resumen del mes y los campos a guardar al soltar una etiqueta.
Diseño: docs/superpowers/specs/2026-11-15-calendario-obras-design.md.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Optional, Tuple

from src.core.obra_planning import color_category
from src.core.obra_planning_service import folder_name, planning_key

FASES = ("EJECUTAR", "EJECUTANDO", "TERMINADO")
MAX_ETIQUETAS_DIA = 3
MIN_OBRAS_MEDIA = 3
NOTA_PREVISTA_APROXIMADA = "Fecha prevista aproximada (solo el mes en el nombre de la carpeta)"

_MAX_CORTO = 18
_NUM_RE = re.compile(r"^\s*\d+-\d+(?:-\d+)?[\s.\-–]*")
_MESES = (
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
    "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

__all__ = [
    "FASES", "MAX_ETIQUETAS_DIA", "MIN_OBRAS_MEDIA", "NOTA_PREVISTA_APROXIMADA",
    "CalendarEvent", "MonthSummary", "folder_name", "short_label", "numero_sort_key",
    "month_title", "build_events", "month_weeks", "events_by_day", "unscheduled",
    "proposal_text", "month_summary", "summary_text", "drop_fields", "clear_fields",
    "proposal_fields",
]


@dataclass(frozen=True)
class CalendarEvent:
    numero: str
    texto: str
    ayuda: str
    fase: str
    tipo: str          # "inicio" | "fin"
    fecha: date
    real: bool
    aproximada: bool
    color: str         # "" | "warning" | "late"
    arrastrable: bool
    ruta_excel: str = ""
    ruta_carpeta: str = ""


@dataclass(frozen=True)
class MonthSummary:
    empiezan: int
    terminan: int
    con_retraso: int
    duracion_media: Optional[int]
    obras_duracion: int


def short_label(row: Dict) -> str:
    """Número + lo que sigue en el nombre de la carpeta, recortado."""
    resto = _NUM_RE.sub("", folder_name(row), count=1).strip()
    if len(resto) > _MAX_CORTO:
        resto = resto[: _MAX_CORTO - 1].rstrip() + "…"
    return f"{planning_key(row)} {resto}".strip()


def numero_sort_key(numero: str):
    """«30-26» antes que «114-26»: por año y luego por número."""
    partes = [int(p) for p in re.findall(r"\d+", numero or "")]
    if len(partes) >= 2:
        return (0, partes[1], partes[0], tuple(partes[2:]), numero)
    return (1, 0, 0, (), numero or "")


def month_title(year: int, month: int) -> str:
    return f"{_MESES[month].capitalize()} {year}"


def _margen(plan: Dict, general: int) -> int:
    propio = plan.get("margen_aviso_dias")
    return general if propio is None else int(propio)


def _event(row: Dict, fase: str, tipo: str, fecha: date, real: bool, aproximada: bool,
           color: str, arrastrable: bool) -> CalendarEvent:
    simbolo = "▶" if tipo == "inicio" else ("✔" if fase == "TERMINADO" else "■")
    texto = f"{'≈' if aproximada else ''}{simbolo} {short_label(row)}"
    clase = ("real aproximado" if aproximada else "real") if real else "previsto"
    extremo = "Inicio" if tipo == "inicio" else "Fin"
    aviso = ""
    if color == "late":
        aviso = " (pasada)" if tipo == "inicio" else " (con retraso)"
    elif color == "warning":
        aviso = " (dentro del margen de aviso)"
    if arrastrable:
        pista = "Arrastra para cambiar la fecha · doble clic para editar"
    elif real:
        pista = "Fecha real: se cambia con doble clic"
    else:
        pista = "Doble clic para editar"
    ayuda = f"{folder_name(row)}\n{fase} · {extremo} {clase}: {fecha:%d/%m/%Y}{aviso}\n{pista}"
    return CalendarEvent(
        numero=planning_key(row), texto=texto, ayuda=ayuda, fase=fase, tipo=tipo, fecha=fecha,
        real=real, aproximada=aproximada, color=color, arrastrable=arrastrable,
        ruta_excel=row.get("ruta_excel") or "", ruta_carpeta=row.get("ruta_carpeta") or "",
    )


def build_events(filas_por_estado: Dict[str, List[Dict]], hoy: date, margen_general: int = 7) -> List[CalendarEvent]:
    """Etiquetas de inicio y fin de cada obra (real si existe; si no, prevista)."""
    eventos: List[CalendarEvent] = []
    for fase in FASES:
        for row in filas_por_estado.get(fase, []):
            if row.get("planificacion_duplicado") or not planning_key(row):
                continue
            plan = row.get("planificacion") or {}
            if fase == "EJECUTAR":
                ini = plan.get("inicio_previsto")
                if ini:
                    color = color_category(ini, _margen(plan, margen_general), hoy)
                    eventos.append(_event(row, fase, "inicio", ini, False, False, color, True))
                fin = plan.get("fin_previsto")
                if fin:
                    eventos.append(_event(row, fase, "fin", fin, False, False, "", True))
            elif fase == "EJECUTANDO":
                if plan.get("inicio_real"):
                    eventos.append(_event(row, fase, "inicio", plan["inicio_real"], True,
                                          bool(plan.get("inicio_real_aproximado")), "", False))
                elif plan.get("inicio_previsto"):
                    eventos.append(_event(row, fase, "inicio", plan["inicio_previsto"], False, False, "", False))
                fin = plan.get("fin_previsto")
                if fin:
                    eventos.append(_event(row, fase, "fin", fin, False, False, "late" if fin < hoy else "", True))
            else:
                if plan.get("inicio_real"):
                    eventos.append(_event(row, fase, "inicio", plan["inicio_real"], True,
                                          bool(plan.get("inicio_real_aproximado")), "", False))
                if plan.get("fin_real"):
                    eventos.append(_event(row, fase, "fin", plan["fin_real"], True,
                                          bool(plan.get("fin_real_aproximado")), "", False))
    return eventos


def month_weeks(year: int, month: int) -> List[List[date]]:
    """Semanas (lunes a domingo) que cubren el mes, con días de los meses vecinos."""
    return calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)


def events_by_day(eventos: Iterable[CalendarEvent]) -> Dict[date, List[CalendarEvent]]:
    out: Dict[date, List[CalendarEvent]] = {}
    for ev in sorted(eventos, key=lambda e: (e.fecha, e.tipo != "inicio", numero_sort_key(e.numero))):
        out.setdefault(ev.fecha, []).append(ev)
    return out


def proposal_text(propuesta: Optional[Tuple[date, bool]]) -> str:
    if not propuesta:
        return ""
    fecha, aproximada = propuesta
    if aproximada:
        return f"≈ {_MESES[fecha.month]} de {fecha.year} según el nombre"
    return f"≈ {fecha:%d/%m/%y} según el nombre"


def unscheduled(filas_ejecutar: Iterable[Dict]) -> List[Dict]:
    """Obras de EJECUTAR sin inicio previsto, con la fecha propuesta por el nombre."""
    items = []
    for row in filas_ejecutar:
        numero = planning_key(row)
        if row.get("planificacion_duplicado") or not numero:
            continue
        if (row.get("planificacion") or {}).get("inicio_previsto"):
            continue
        propuesta = row.get("planificacion_propuesta")
        items.append({
            "numero": numero,
            "texto": short_label(row),
            "ayuda": folder_name(row),
            "propuesta": propuesta,
            "propuesta_texto": proposal_text(propuesta),
            "ruta_excel": row.get("ruta_excel") or "",
            "ruta_carpeta": row.get("ruta_carpeta") or "",
        })
    return sorted(items, key=lambda i: numero_sort_key(i["numero"]))


def month_summary(eventos: List[CalendarEvent], year: int, month: int) -> MonthSummary:
    def en_mes(d: date) -> bool:
        return d.year == year and d.month == month

    empiezan = sum(1 for e in eventos if e.tipo == "inicio" and en_mes(e.fecha))
    terminan = sum(1 for e in eventos if e.tipo == "fin" and en_mes(e.fecha))
    con_retraso = len({e.numero for e in eventos if e.color == "late"})
    inicios = {e.numero: e.fecha for e in eventos if e.fase == "TERMINADO" and e.tipo == "inicio"}
    duraciones = [
        (e.fecha - inicios[e.numero]).days
        for e in eventos
        if e.fase == "TERMINADO" and e.tipo == "fin" and en_mes(e.fecha)
        and e.numero in inicios and e.fecha >= inicios[e.numero]
    ]
    media = round(sum(duraciones) / len(duraciones)) if len(duraciones) >= MIN_OBRAS_MEDIA else None
    return MonthSummary(empiezan, terminan, con_retraso, media, len(duraciones))


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def summary_text(resumen: MonthSummary) -> str:
    partes = [
        _plural(resumen.empiezan, "empieza", "empiezan"),
        _plural(resumen.terminan, "termina", "terminan"),
        f"{resumen.con_retraso} con retraso",
    ]
    if resumen.duracion_media is None:
        partes.append("duración media: sin datos suficientes")
    else:
        partes.append(f"duración media {resumen.duracion_media} días ({resumen.obras_duracion} obras)")
    return "Este mes: " + " · ".join(partes)


def drop_fields(plan: Optional[Dict], fase: str, tipo: str, nueva: date) -> Tuple[Optional[Dict], str]:
    """Campos a guardar al soltar una etiqueta en `nueva`.

    Devuelve (campos, ""), o (None, motivo) si no se puede, o (None, "") si no
    cambia nada.
    """
    plan = plan or {}
    if tipo == "inicio":
        if fase != "EJECUTAR":
            return None, "Solo se puede mover el inicio previsto de las obras de EJECUTAR."
        viejo, fin = plan.get("inicio_previsto"), plan.get("fin_previsto")
        if viejo == nueva:
            return None, ""
        campos: Dict = {"inicio_previsto": nueva}
        if fin is not None:
            if viejo is not None:
                campos["fin_previsto"] = fin + (nueva - viejo)
            elif fin < nueva:
                return None, f"El inicio no puede ser después del fin previsto ({fin:%d/%m})."
        return campos, ""
    if tipo == "fin":
        if fase not in ("EJECUTAR", "EJECUTANDO"):
            return None, "Las fechas reales se cambian con doble clic."
        if plan.get("fin_previsto") == nueva:
            return None, ""
        inicio = plan.get("inicio_real") or plan.get("inicio_previsto")
        if inicio is not None and nueva < inicio:
            return None, f"El fin no puede ser antes del inicio ({inicio:%d/%m})."
        return {"fin_previsto": nueva}, ""
    raise ValueError(f"tipo desconocido: {tipo}")


def clear_fields(plan: Optional[Dict]) -> Optional[Dict]:
    """Quitar las fechas previstas, o None si no tiene ninguna."""
    plan = plan or {}
    if not plan.get("inicio_previsto") and not plan.get("fin_previsto"):
        return None
    return {"inicio_previsto": None, "fin_previsto": None}


def proposal_fields(plan: Optional[Dict], propuesta: Tuple[date, bool]) -> Dict:
    """«Poner esta fecha»: la propuesta como inicio previsto; si solo era el mes,
    se deja una nota (si no había ninguna), porque la prevista no tiene marca
    de aproximada."""
    fecha, aproximada = propuesta
    campos: Dict = {"inicio_previsto": fecha}
    if aproximada and not (plan or {}).get("notas"):
        campos["notas"] = NOTA_PREVISTA_APROXIMADA
    return campos
```

- [ ] **Step 5: Ejecutar los tests**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_obra_calendar.py tests/test_obra_planning_service.py`
Expected: todos PASS.

- [ ] **Step 6: Commit**

```bash
git add src/core/obra_calendar.py src/core/obra_planning_service.py tests/test_obra_calendar.py
git commit -m "feat(obras): núcleo del calendario de obras (etiquetas, sin fecha, resumen, soltar)"
```

---

### Task C2: Carga de datos y señal compartida

**Files:**
- Create: `src/core/obra_calendar_service.py`
- Create: `src/gui/planning_events.py`
- Test: `tests/test_obra_calendar_service.py`

**Interfaces:**
- Consumes: `get_all_presupuestos_cache()` de `src.core.repositories.presupuesto_cache_repository` (dicts con `numero_proyecto`, `nombre_proyecto`, `ruta_excel`, `ruta_carpeta`, `estado`…); `enrich_with_planning(data, hoy, reconcile)`; `get_planes(numeros)`; `date_from_folder_name(nombre) -> (date, bool) | None`; `FASES`, `folder_name`, `planning_key`.
- Produces:
  - `CalendarData` (dataclass): `filas_por_estado: dict[str, list[dict]]` (solo FASES), `repetidas: int`, `error: str`, `vacia: bool`.
  - `ERROR_LECTURA`, `load_calendar_data(hoy) -> CalendarData`, `refresh_planning(filas_por_estado, numeros) -> None`.
  - `planning_events()` → objeto con señales `planning_changed(object numeros, object emisor)` y `obras_reloaded(object emisor)`; `notify_planning_changed(numeros, source=None)`, `notify_obras_reloaded(source=None)`.

- [ ] **Step 1: Escribir los tests**

`tests/test_obra_calendar_service.py`:

```python
"""Carga del calendario desde la caché del dashboard y señal compartida."""

from datetime import date

import pytest

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
```

El último test necesita PySide6; si no está instalado, añadir al principio del fichero el mismo bloque `try: import PySide6 ... _HAS_PYSIDE6` y marcar **solo ese test** con `@pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")`:

```python
try:
    import PySide6  # noqa: F401

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False
```

- [ ] **Step 2: Ejecutarlos y ver que fallan**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_obra_calendar_service.py`
Expected: FAIL (`No module named 'src.core.obra_calendar_service'`).

- [ ] **Step 3: Escribir el servicio**

`src/core/obra_calendar_service.py`:

```python
"""Datos del calendario de obras (sin Qt): caché del dashboard + planificación.

No escanea carpetas: usa lo que dejó la última recarga del dashboard. Para
detectar obras movidas fuera de la app hay que actualizar el dashboard.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Iterable, List

from src.core.obra_calendar import FASES
from src.core.obra_planning import date_from_folder_name
from src.core.obra_planning_service import enrich_with_planning, folder_name, planning_key

logger = logging.getLogger(__name__)

ERROR_LECTURA = "No se pudo leer la planificación: las obras se muestran sin fechas."


@dataclass
class CalendarData:
    filas_por_estado: Dict[str, List[Dict]] = field(default_factory=dict)
    repetidas: int = 0
    error: str = ""
    vacia: bool = False


def load_calendar_data(hoy: date) -> CalendarData:
    from src.core.repositories import presupuesto_cache_repository as cache_repo

    data: Dict[str, List[Dict]] = {}
    for cached in cache_repo.get_all_presupuestos_cache():
        estado = (cached.get("estado") or "").strip().upper()
        if not estado:
            continue
        row = dict(cached)
        row.setdefault("numero", row.get("numero_proyecto", ""))
        data.setdefault(estado, []).append(row)

    error = ""
    try:
        # Todas las fases cuentan para detectar números repetidos, como en el dashboard.
        enrich_with_planning(data, hoy, reconcile=False)
    except Exception:
        logger.exception("No se pudo leer la planificación para el calendario")
        error = ERROR_LECTURA
        for fase in FASES:
            for row in data.get(fase, []):
                row["planificacion"] = {}
                row["planificacion_duplicado"] = False
                row["planificacion_propuesta"] = None

    filas = {fase: data.get(fase, []) for fase in FASES}
    repetidas = sum(1 for rows in filas.values() for r in rows if r.get("planificacion_duplicado"))
    return CalendarData(filas, repetidas, error, vacia=not any(filas.values()))


def refresh_planning(filas_por_estado: Dict[str, List[Dict]], numeros: Iterable[str]) -> None:
    """Relee el plan de `numeros` y recalcula su propuesta (tras guardar o deshacer)."""
    from src.core.repositories.obra_planificacion_repository import get_planes

    wanted = {n for n in numeros if n}
    if not wanted:
        return
    planes = get_planes(wanted)
    for fase, rows in filas_por_estado.items():
        for row in rows:
            numero = planning_key(row)
            if row.get("planificacion_duplicado") or numero not in wanted:
                continue
            row["planificacion"] = planes.get(numero, {})
            propuesta = None
            if fase == "EJECUTAR" and not row["planificacion"].get("inicio_previsto"):
                propuesta = date_from_folder_name(folder_name(row))
            row["planificacion_propuesta"] = propuesta
```

- [ ] **Step 4: Escribir la señal compartida**

`src/gui/planning_events.py`:

```python
"""Aviso interno «la planificación ha cambiado» entre dashboard y calendario.

- `planning_changed(numeros, emisor)`: se guardaron fechas de esas obras; quien
  la recibe relee solo su planificación (sin escanear carpetas).
- `obras_reloaded(emisor)`: el dashboard terminó una recarga completa (pudo
  mover obras de fase); el calendario se recarga entero.

Cada ventana ignora lo que emitió ella misma.
"""

from __future__ import annotations

from typing import Iterable, Optional

from PySide6.QtCore import QObject, Signal


class _PlanningEvents(QObject):
    planning_changed = Signal(object, object)
    obras_reloaded = Signal(object)


_instance: Optional[_PlanningEvents] = None


def planning_events() -> _PlanningEvents:
    global _instance
    if _instance is None:
        _instance = _PlanningEvents()
    return _instance


def notify_planning_changed(numeros: Iterable[str], source=None) -> None:
    planning_events().planning_changed.emit(list(numeros), source)


def notify_obras_reloaded(source=None) -> None:
    planning_events().obras_reloaded.emit(source)
```

- [ ] **Step 5: Ejecutar los tests**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_obra_calendar_service.py`
Expected: 5 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/core/obra_calendar_service.py src/gui/planning_events.py tests/test_obra_calendar_service.py
git commit -m "feat(obras): datos del calendario desde la caché y aviso compartido de planificación"
```

---

### Task C3: Ventana del calendario

**Files:**
- Create: `src/gui/obra_calendar_window.py`
- Test: `tests/test_obra_calendar_window.py`

**Interfaces:**
- Consumes: todo `src.core.obra_calendar` (C1); `CalendarData`, `load_calendar_data`, `refresh_planning` (C2); `planning_events`, `notify_planning_changed` (C2); `show_toast(parent, text, actions=None)` y `current_toast(parent)` de `src.gui.widgets.toast` (el toast tiene `text()`, `action_labels()`, `trigger(label)`); `ObraPlanningDialog(parent, titulo, plan, margen_general, propuesta)` con `exec()` y `get_changes()`; `upsert_plan`, `get_planes`, `restore_plan_snapshot`; `run_in_background(work, cb)`; `Settings().get_obra_margen_aviso_dias()`.
- Produces: `ObraCalendarWindow(parent=None, hoy=None, autoload=True)` con: `reload()`, `set_data(CalendarData)`, `go_prev()`, `go_next()`, `go_today()`, `cell_for(dia) -> _DayCell | None`, `unscheduled_numeros() -> list[str]`, `drop_on_day(numero, fase, tipo, dia)`, `drop_on_unscheduled(numero, fase, tipo)`, `clear_planned(numero)`, `put_proposal(numero)`, `edit_planning(numero)`, `build_menu(numero, parent=None) -> QMenu`, atributos `month_label`, `summary_label`, `message_label`, `footer_label`, `unscheduled_panel` (con `rows`, cada fila con `proposal_button`). `_DayCell` tiene `dia`, `en_mes`, `chips` (cada `_EventChip` con `event` y `_payload`) y `more_button`. Constante `MIME_OBRA`.

- [ ] **Step 1: Escribir los tests**

`tests/test_obra_calendar_window.py`:

```python
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
    assert [c.event.numero for c in win.cell_for(date(2026, 11, 20)).chips] == ["114-26"]
    vecino = win.cell_for(date(2026, 10, 26))
    assert vecino.en_mes is False and vecino.chips == []
    assert win.summary_label.text().startswith("Este mes: 1 empieza")


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
    assert [c.event.numero for c in win.cell_for(date(2026, 11, 25)).chips] == ["114-26"]
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
    assert [c.event.numero for c in win.cell_for(date(2026, 11, 20)).chips] == ["114-26"]


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
```

- [ ] **Step 2: Ejecutarlos y ver que fallan**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_obra_calendar_window.py`
Expected: FAIL (`No module named 'src.gui.obra_calendar_window'`).

- [ ] **Step 3: Escribir la ventana**

`src/gui/obra_calendar_window.py`:

```python
"""Ventana «Calendario de obras» (pieza C).

Mes en cuadrícula con las etiquetas de inicio y fin de cada obra, la lista
«Sin fecha» y una franja de resumen. Las fechas previstas se ponen y se
mueven arrastrando, sin preguntar y con Deshacer. Diseño:
docs/superpowers/specs/2026-11-15-calendario-obras-design.md.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from datetime import date
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QMimeData, Qt, QTimer
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QMessageBox,
    QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget,
)

from src.core import obra_calendar as oc
from src.core.obra_calendar_service import CalendarData, load_calendar_data, refresh_planning
from src.core.obra_planning_service import planning_key
from src.gui import planning_events
from src.gui.widgets.toast import show_toast
from src.utils.helpers import run_in_background

logger = logging.getLogger(__name__)

MIME_OBRA = "application/x-cubiapp-obra"
_TITULO = "Calendario de obras"
_DIAS = ("L", "M", "X", "J", "V", "S", "D")
_AVISO_VACIA = "No hay obras cargadas. Abre «Presupuestos existentes» una vez para cargarlas."


def _encode(numero: str, fase: str, tipo: str) -> bytes:
    return f"{numero}|{fase}|{tipo}".encode("utf-8")


def _decode(raw) -> Optional[Tuple[str, str, str]]:
    partes = bytes(raw).decode("utf-8", errors="replace").split("|")
    return (partes[0], partes[1], partes[2]) if len(partes) == 3 else None


def _margen_general() -> int:
    try:
        from src.core.settings import Settings

        return Settings().get_obra_margen_aviso_dias()
    except Exception:
        return 7


def _chip_style(ev: oc.CalendarEvent) -> str:
    if ev.real:
        return ("QLabel{background:#e5e7eb;color:#111827;border:1px solid #9ca3af;"
                "border-radius:4px;padding:1px 4px;}")
    borde = {"warning": "#d97706", "late": "#dc2626"}.get(ev.color, "#6b7280")
    texto = {"warning": "#92400e", "late": "#991b1b"}.get(ev.color, "palette(text)")
    return (f"QLabel{{background:transparent;color:{texto};border:1px dashed {borde};"
            "border-radius:4px;padding:1px 4px;}")


class _DragSource:
    """Mezcla: arrastra `_payload` (número, fase, tipo) al mover con el botón pulsado."""

    _payload: Optional[Tuple[str, str, str]] = None
    _press_pos = None

    def _drag_press(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()

    def _drag_move(self, event) -> bool:
        if not self._payload or self._press_pos is None:
            return False
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return False
        if (event.position().toPoint() - self._press_pos).manhattanLength() < QApplication.startDragDistance():
            return False
        mime = QMimeData()
        mime.setData(MIME_OBRA, _encode(*self._payload))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        self._press_pos = None
        drag.exec(Qt.DropAction.MoveAction)
        return True


class _EventChip(QLabel, _DragSource):
    def __init__(self, window: "ObraCalendarWindow", event: oc.CalendarEvent, parent=None):
        super().__init__(event.texto, parent)
        self._window = window
        self.event = event
        self._payload = (event.numero, event.fase, event.tipo) if event.arrastrable else None
        self.setToolTip(event.ayuda)
        self.setStyleSheet(_chip_style(event))
        if event.arrastrable:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: window.build_menu(event.numero).exec(self.mapToGlobal(pos))
        )

    def mousePressEvent(self, e):
        self._drag_press(e)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not self._drag_move(e):
            super().mouseMoveEvent(e)

    def mouseDoubleClickEvent(self, e):
        self._window.edit_planning(self.event.numero)


class _DayCell(QFrame):
    def __init__(self, window: "ObraCalendarWindow", dia: date, en_mes: bool, es_hoy: bool,
                 eventos: List[oc.CalendarEvent], parent=None):
        super().__init__(parent)
        self._window = window
        self.dia = dia
        self.en_mes = en_mes
        self.setObjectName("dayCell")
        self.setAcceptDrops(en_mes)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumSize(110, 90)
        if es_hoy:
            self.setStyleSheet("#dayCell{border:2px solid #2563eb;}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setSpacing(2)
        numero = QLabel(str(dia.day), self)
        numero.setEnabled(en_mes)
        if es_hoy:
            numero.setStyleSheet("font-weight:bold;color:#2563eb;")
        lay.addWidget(numero)
        self.chips: List[_EventChip] = []
        self.more_button: Optional[QToolButton] = None
        if en_mes:
            for ev in eventos[: oc.MAX_ETIQUETAS_DIA]:
                chip = _EventChip(window, ev, self)
                lay.addWidget(chip)
                self.chips.append(chip)
            if len(eventos) > oc.MAX_ETIQUETAS_DIA:
                btn = QToolButton(self)
                btn.setText(f"+{len(eventos) - oc.MAX_ETIQUETAS_DIA} más")
                btn.setAutoRaise(True)
                btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                btn.setMenu(window.build_day_menu(eventos, btn))
                lay.addWidget(btn)
                self.more_button = btn
        lay.addStretch(1)

    def dragEnterEvent(self, e):
        if self.en_mes and e.mimeData().hasFormat(MIME_OBRA):
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        self.dragEnterEvent(e)

    def dropEvent(self, e):
        payload = _decode(e.mimeData().data(MIME_OBRA).data())
        if not payload:
            e.ignore()
            return
        e.acceptProposedAction()
        dia, window = self.dia, self._window
        # Después de que termine el arrastre: guardar repinta y borra esta celda.
        QTimer.singleShot(0, lambda: window.drop_on_day(*payload, dia))


class _UnscheduledRow(QFrame, _DragSource):
    def __init__(self, window: "ObraCalendarWindow", item: Dict, parent=None):
        super().__init__(parent)
        self._window = window
        self.numero = item["numero"]
        self._payload = (item["numero"], "EJECUTAR", "inicio")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(f"{item['ayuda']}\nArrastra a un día para poner el inicio previsto · doble clic para editar")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)
        lay.addWidget(QLabel(item["texto"], self))
        self.proposal_button: Optional[QPushButton] = None
        if item["propuesta"]:
            fila = QHBoxLayout()
            propuesta = QLabel(item["propuesta_texto"], self)
            propuesta.setStyleSheet("font-style:italic;color:#6b7280;")
            btn = QPushButton("Poner esta fecha", self)
            numero = self.numero
            btn.clicked.connect(lambda: window.put_proposal(numero))
            fila.addWidget(propuesta, 1)
            fila.addWidget(btn)
            lay.addLayout(fila)
            self.proposal_button = btn
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: window.build_menu(self.numero).exec(self.mapToGlobal(pos))
        )

    def mousePressEvent(self, e):
        self._drag_press(e)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not self._drag_move(e):
            super().mouseMoveEvent(e)

    def mouseDoubleClickEvent(self, e):
        self._window.edit_planning(self.numero)


class _UnscheduledPanel(QFrame):
    def __init__(self, window: "ObraCalendarWindow", parent=None):
        super().__init__(parent)
        self._window = window
        self.setAcceptDrops(True)
        self.setFixedWidth(290)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel("Sin fecha (0)", self)
        self.title.setStyleSheet("font-weight:bold;")
        lay.addWidget(self.title)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self._list = QVBoxLayout(inner)
        self._list.setContentsMargins(0, 0, 0, 0)
        self._list.addStretch(1)
        scroll.setWidget(inner)
        self._inner = inner
        lay.addWidget(scroll, 1)
        pista = QLabel("Arrastra una obra a un día para ponerle fecha, o una etiqueta ▶ aquí para quitarla.", self)
        pista.setWordWrap(True)
        lay.addWidget(pista)
        self.rows: List[_UnscheduledRow] = []

    def set_items(self, items: List[Dict]) -> None:
        for row in self.rows:
            self._list.removeWidget(row)
            row.deleteLater()
        self.rows = []
        for i, item in enumerate(items):
            row = _UnscheduledRow(self._window, item, self._inner)
            self._list.insertWidget(i, row)
            self.rows.append(row)
        self.title.setText(f"Sin fecha ({len(items)})")

    def dragEnterEvent(self, e):
        payload = _decode(e.mimeData().data(MIME_OBRA).data()) if e.mimeData().hasFormat(MIME_OBRA) else None
        if payload and payload[1] == "EJECUTAR" and payload[2] == "inicio":
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        self.dragEnterEvent(e)

    def dropEvent(self, e):
        payload = _decode(e.mimeData().data(MIME_OBRA).data())
        if not payload:
            e.ignore()
            return
        e.acceptProposedAction()
        window = self._window
        QTimer.singleShot(0, lambda: window.drop_on_unscheduled(*payload))


class ObraCalendarWindow(QWidget):
    def __init__(self, parent=None, hoy: Optional[date] = None, autoload: bool = True):
        super().__init__(parent, Qt.WindowType.Window)
        self.setWindowTitle(_TITULO)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(1150, 720)
        self._hoy = hoy or date.today()
        self._year, self._month = self._hoy.year, self._hoy.month
        self._data = CalendarData()
        self._eventos: List[oc.CalendarEvent] = []
        self._rows_by_numero: Dict[str, Tuple[str, Dict]] = {}
        self._cells: List[_DayCell] = []
        self._margen = _margen_general()
        self._loading = False
        self._build_ui()
        eventos = planning_events.planning_events()
        eventos.planning_changed.connect(self._on_planning_changed)
        eventos.obras_reloaded.connect(self._on_obras_reloaded)
        self._render()
        if autoload:
            self.reload()

    # ── Interfaz ─────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        cabecera = QHBoxLayout()
        self._btn_prev = QPushButton("◀", self)
        self._btn_prev.setToolTip("Mes anterior")
        self._btn_prev.clicked.connect(self.go_prev)
        self.month_label = QLabel(self)
        self.month_label.setStyleSheet("font-size:16px;font-weight:bold;padding:0 8px;")
        self._btn_next = QPushButton("▶", self)
        self._btn_next.setToolTip("Mes siguiente")
        self._btn_next.clicked.connect(self.go_next)
        self._btn_today = QPushButton("Hoy", self)
        self._btn_today.clicked.connect(self.go_today)
        self._btn_reload = QPushButton("⟳", self)
        self._btn_reload.setToolTip(
            "Volver a leer las obras y su planificación.\n"
            "Para detectar carpetas movidas fuera de la app, actualiza «Presupuestos existentes»."
        )
        self._btn_reload.clicked.connect(self.reload)
        for w in (self._btn_prev, self.month_label, self._btn_next, self._btn_today):
            cabecera.addWidget(w)
        cabecera.addStretch(1)
        cabecera.addWidget(self._btn_reload)
        root.addLayout(cabecera)

        self.summary_label = QLabel("", self)
        root.addWidget(self.summary_label)
        self.message_label = QLabel("", self)
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("color:#b45309;")
        self.message_label.hide()
        root.addWidget(self.message_label)

        cuerpo = QHBoxLayout()
        grid_host = QWidget(self)
        self._grid = QGridLayout(grid_host)
        self._grid.setSpacing(2)
        for c, nombre in enumerate(_DIAS):
            cab = QLabel(nombre, grid_host)
            cab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid.addWidget(cab, 0, c)
            self._grid.setColumnStretch(c, 1)
        cuerpo.addWidget(grid_host, 1)
        self.unscheduled_panel = _UnscheduledPanel(self, self)
        cuerpo.addWidget(self.unscheduled_panel)
        root.addLayout(cuerpo, 1)

        self.footer_label = QLabel("", self)
        self.footer_label.setStyleSheet("color:#6b7280;")
        root.addWidget(self.footer_label)

    def _render(self) -> None:
        self.month_label.setText(oc.month_title(self._year, self._month))
        self.summary_label.setText(oc.summary_text(oc.month_summary(self._eventos, self._year, self._month)))
        mensaje = self._data.error or (_AVISO_VACIA if self._data.vacia else "")
        self.message_label.setText(mensaje)
        self.message_label.setVisible(bool(mensaje))

        for cell in self._cells:
            self._grid.removeWidget(cell)
            cell.deleteLater()
        self._cells = []
        por_dia = oc.events_by_day(self._eventos)
        host = self._grid.parentWidget()
        for r, semana in enumerate(oc.month_weeks(self._year, self._month), start=1):
            for c, dia in enumerate(semana):
                cell = _DayCell(self, dia, dia.month == self._month, dia == self._hoy, por_dia.get(dia, []), host)
                self._grid.addWidget(cell, r, c)
                self._cells.append(cell)

        self.unscheduled_panel.set_items(oc.unscheduled(self._data.filas_por_estado.get("EJECUTAR", [])))
        n = self._data.repetidas
        if n == 1:
            self.footer_label.setText("1 obra con número repetido, no se puede planificar")
        elif n > 1:
            self.footer_label.setText(f"{n} obras con número repetido, no se pueden planificar")
        else:
            self.footer_label.setText("")

    # ── Datos ────────────────────────────────────────────────────────────

    def reload(self) -> None:
        if self._loading:
            return
        self._loading = True
        self._btn_reload.setEnabled(False)
        hoy = self._hoy

        def _done(ok, payload):
            self._loading = False
            try:
                self._btn_reload.setEnabled(True)
            except RuntimeError:
                return  # la ventana se cerró mientras cargaba
            if not ok:
                logger.error("No se pudieron cargar las obras del calendario: %s", payload)
                self.set_data(CalendarData(error=f"No se pudieron cargar las obras: {payload}"))
                return
            self.set_data(payload)

        run_in_background(lambda: load_calendar_data(hoy), _done)

    def set_data(self, data: CalendarData) -> None:
        self._data = data
        self._index()
        self._render()

    def _index(self) -> None:
        self._rows_by_numero = {}
        for fase, rows in self._data.filas_por_estado.items():
            for row in rows:
                numero = planning_key(row)
                if numero and not row.get("planificacion_duplicado"):
                    self._rows_by_numero[numero] = (fase, row)
        self._eventos = oc.build_events(self._data.filas_por_estado, self._hoy, self._margen)

    def _row(self, numero: str) -> Tuple[Optional[str], Optional[Dict]]:
        return self._rows_by_numero.get(numero, (None, None))

    def _plan(self, numero: str) -> Dict:
        return (self._row(numero)[1] or {}).get("planificacion") or {}

    # ── Navegación y consultas (también para los tests) ───────────────────

    def go_prev(self) -> None:
        self._year, self._month = (self._year - 1, 12) if self._month == 1 else (self._year, self._month - 1)
        self._render()

    def go_next(self) -> None:
        self._year, self._month = (self._year + 1, 1) if self._month == 12 else (self._year, self._month + 1)
        self._render()

    def go_today(self) -> None:
        self._year, self._month = self._hoy.year, self._hoy.month
        self._render()

    def cell_for(self, dia: date) -> Optional[_DayCell]:
        return next((c for c in self._cells if c.dia == dia), None)

    def unscheduled_numeros(self) -> List[str]:
        return [r.numero for r in self.unscheduled_panel.rows]

    # ── Acciones ─────────────────────────────────────────────────────────

    def drop_on_day(self, numero: str, fase: str, tipo: str, dia: date) -> None:
        fase_actual, row = self._row(numero)
        if row is None:
            return
        plan = self._plan(numero)
        campos, motivo = oc.drop_fields(plan, fase_actual, tipo, dia)
        if campos is None:
            if motivo:
                show_toast(self, motivo)
            return
        if tipo == "inicio":
            verbo = "movido al" if plan.get("inicio_previsto") else "el"
            mensaje = f"{numero}: inicio previsto {verbo} {dia:%d/%m}"
        else:
            mensaje = f"{numero}: fin previsto el {dia:%d/%m}"
        self._save(numero, campos, mensaje)

    def drop_on_unscheduled(self, numero: str, fase: str, tipo: str) -> None:
        fase_actual, row = self._row(numero)
        if row is None or fase_actual != "EJECUTAR" or tipo != "inicio":
            return
        if not self._plan(numero).get("inicio_previsto"):
            return
        self.clear_planned(numero)

    def clear_planned(self, numero: str) -> None:
        campos = oc.clear_fields(self._plan(numero))
        if campos:
            self._save(numero, campos, f"{numero}: fechas previstas quitadas")

    def put_proposal(self, numero: str) -> None:
        propuesta = (self._row(numero)[1] or {}).get("planificacion_propuesta")
        if not propuesta:
            return
        self._save(numero, oc.proposal_fields(self._plan(numero), propuesta),
                   f"{numero}: inicio previsto el {propuesta[0]:%d/%m}")

    def edit_planning(self, numero: str) -> None:
        from src.gui import obra_planning_dialog

        fase, row = self._row(numero)
        if row is None:
            return
        dlg = obra_planning_dialog.ObraPlanningDialog(
            self, titulo=oc.folder_name(row) or numero, plan=self._plan(numero),
            margen_general=self._margen, propuesta=row.get("planificacion_propuesta"),
        )
        if dlg.exec() != 1 or dlg.get_changes() is None:
            return
        self._save(numero, dlg.get_changes(), f"{numero}: planificación guardada")

    def _save(self, numero: str, campos: Dict, mensaje: str) -> None:
        from src.core.repositories import obra_planificacion_repository as repo

        try:
            snapshot = repo.get_planes([numero]).get(numero)
        except Exception as exc:
            QMessageBox.critical(self, _TITULO, f"No se pudo leer la planificación de {numero}:\n{exc}")
            return
        err = repo.upsert_plan(numero, **campos)
        if err:
            QMessageBox.critical(self, _TITULO, f"No se pudo guardar {numero}:\n{err}")
            self._render()
            return
        self._after_change([numero])
        show_toast(self, mensaje, [("Deshacer", lambda: self._undo(numero, snapshot))])

    def _undo(self, numero: str, snapshot: Optional[Dict]) -> None:
        from src.core.repositories import obra_planificacion_repository as repo

        err = repo.restore_plan_snapshot(numero, snapshot)
        if err:
            QMessageBox.critical(self, _TITULO, f"No se pudo deshacer {numero}:\n{err}")
            return
        self._after_change([numero])
        show_toast(self, f"{numero}: cambio deshecho")

    def _after_change(self, numeros: List[str]) -> None:
        try:
            refresh_planning(self._data.filas_por_estado, numeros)
        except Exception:
            logger.exception("No se pudo releer la planificación de %s", numeros)
        self._index()
        self._render()
        planning_events.notify_planning_changed(numeros, source=self)

    # ── Menús y abrir ficheros ───────────────────────────────────────────

    def build_menu(self, numero: str, parent=None) -> QMenu:
        menu = QMenu(parent or self)
        row = self._row(numero)[1] or {}
        menu.addAction("Planificación…").triggered.connect(lambda: self.edit_planning(numero))
        menu.addAction("Abrir Excel").triggered.connect(
            lambda: self._open_path(row.get("ruta_excel", ""), "El archivo Excel ya no existe."))
        menu.addAction("Abrir carpeta").triggered.connect(
            lambda: self._open_path(row.get("ruta_carpeta", ""), "La carpeta ya no existe."))
        menu.addSeparator()
        quitar = menu.addAction("Quitar fechas previstas")
        quitar.triggered.connect(lambda: self.clear_planned(numero))
        quitar.setEnabled(oc.clear_fields(self._plan(numero)) is not None)
        return menu

    def build_day_menu(self, eventos: List[oc.CalendarEvent], parent) -> QMenu:
        menu = QMenu(parent)
        for ev in eventos:
            sub = self.build_menu(ev.numero, menu)
            sub.setTitle(ev.texto)
            menu.addMenu(sub)
        return menu

    def _open_path(self, path: str, missing: str) -> None:
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, _TITULO, missing)
            return
        path = os.path.normpath(path)
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=True)
            else:
                subprocess.run(["xdg-open", path], check=True)
        except Exception as exc:
            QMessageBox.critical(self, _TITULO, f"No se pudo abrir:\n{path}\n\nError: {exc}")

    # ── Avisos de otras ventanas ─────────────────────────────────────────

    def _on_planning_changed(self, numeros, source) -> None:
        if source is self:
            return
        try:
            refresh_planning(self._data.filas_por_estado, numeros)
        except Exception:
            logger.exception("No se pudo releer la planificación de %s", numeros)
            return
        self._index()
        self._render()

    def _on_obras_reloaded(self, source) -> None:
        if source is not self:
            self.reload()

    def closeEvent(self, event):
        eventos = planning_events.planning_events()
        for senal, slot in ((eventos.planning_changed, self._on_planning_changed),
                            (eventos.obras_reloaded, self._on_obras_reloaded)):
            try:
                senal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        super().closeEvent(event)
```

Nota para quien implemente: `test_recarga_externa_vuelve_a_cargar` sustituye `win.reload` con `monkeypatch.setattr(win, "reload", …)`. La señal está conectada a `self._on_obras_reloaded`, que llama a `self.reload()` en el momento, así que el sustituto se usa. No conectar la señal directamente a `self.reload`.

- [ ] **Step 4: Ejecutar los tests**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_obra_calendar_window.py`
Expected: 16 PASS. Si algún test se queda colgado, hay un `QMessageBox` o un `exec()` de menú real sin sustituir: buscarlo, no aumentar el tiempo de espera.

- [ ] **Step 5: Commit**

```bash
git add src/gui/obra_calendar_window.py tests/test_obra_calendar_window.py
git commit -m "feat(obras): ventana del calendario de obras con arrastrar y Deshacer"
```

---

### Task C4: Dashboard y pantalla de inicio

**Files:**
- Modify: `src/gui/budget_dashboard.py` (import, `__init__`, `closeEvent`, `_load_data._on_done`, `_on_planning`, nuevo `_on_external_planning_changed`)
- Modify: `src/gui/main_frame.py` (`__init__`, botones, menú Herramientas, nuevo `_open_obra_calendar`)
- Test: `tests/test_obra_calendar_wiring.py`

**Interfaces:**
- Consumes: `planning_events()`, `notify_planning_changed(numeros, source)`, `notify_obras_reloaded(source)` (C2); `ObraCalendarWindow(parent)` (C3); en el dashboard: `self._tab_data`, `self._explorer_mode`, `self._refresh_rows(rutas)`, `planning_key(row)`.
- Produces: `BudgetDashboardFrame._on_external_planning_changed(numeros, source)`; `MainFrame._open_obra_calendar()` y `self._obra_calendar`.

- [ ] **Step 1: Escribir los tests**

`tests/test_obra_calendar_wiring.py`:

```python
"""El dashboard y la pantalla de inicio enlazan con el calendario de obras."""

import pytest

try:
    from PySide6.QtWidgets import QMainWindow

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


def _escuchar():
    from src.gui import planning_events

    vistos = []
    ev = planning_events.planning_events()

    def _cambio(numeros, emisor):
        vistos.append(("cambio", numeros, emisor))

    def _recarga(emisor):
        vistos.append(("recarga", emisor))

    ev.planning_changed.connect(_cambio)
    ev.obras_reloaded.connect(_recarga)

    def _parar():
        ev.planning_changed.disconnect(_cambio)
        ev.obras_reloaded.disconnect(_recarga)

    return vistos, _parar


def _dash():
    import src.gui.budget_dashboard as bd

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._explorer_mode = False
    dash._tab_data = {
        "EJECUTAR": [
            {"ruta_excel": "C:/o/114-26 A/p.xlsx", "ruta_carpeta": "C:/o/114-26 A", "numero": "114-26"},
            {"ruta_excel": "C:/o/208-26 B/p.xlsx", "ruta_carpeta": "C:/o/208-26 B", "numero": "208-26"},
        ]
    }
    return bd, dash


def test_dashboard_refresca_las_filas_de_un_cambio_externo(qapp):
    bd, dash = _dash()
    refrescos = []
    dash._refresh_rows = lambda rutas, on_done=None: refrescos.append(rutas)
    bd.BudgetDashboardFrame._on_external_planning_changed(dash, ["114-26"], object())
    assert refrescos == [["C:/o/114-26 A/p.xlsx"]]
    bd.BudgetDashboardFrame._on_external_planning_changed(dash, ["114-26"], dash)
    assert len(refrescos) == 1


def test_dashboard_avisa_al_guardar_la_planificacion(qapp, monkeypatch):
    import src.core.repositories.obra_planificacion_repository as repo
    import src.gui.obra_planning_dialog as dlg_mod

    class _Dialogo:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 1

        def get_changes(self):
            return {"inicio_previsto": None, "fin_previsto": None}

    monkeypatch.setattr(dlg_mod, "ObraPlanningDialog", _Dialogo)
    monkeypatch.setattr(repo, "upsert_plan", lambda *a, **k: None)
    bd, dash = _dash()
    fila = dict(dash._tab_data["EJECUTAR"][0], planificacion={}, planificacion_duplicado=False,
                planificacion_propuesta=None)
    dash._get_selected_many = lambda: [fila]
    dash._planning_margin = lambda: 7
    dash._refresh_rows = lambda rutas, on_done=None: None
    vistos, parar = _escuchar()
    try:
        bd.BudgetDashboardFrame._on_planning(dash)
    finally:
        parar()
    assert vistos == [("cambio", ["114-26"], dash)]


def test_dashboard_avisa_al_terminar_una_recarga_completa(qapp, monkeypatch, tmp_path):
    bd, dash = _dash()

    class _Ajustes:
        def get_default_path(self, _clave):
            return str(tmp_path)

    class _Texto:
        def setText(self, _t):
            pass

    dash._settings = _Ajustes()
    dash._subtitle = _Texto()
    dash._capture_view_context = lambda: None
    dash._show_empty_state = lambda *_a: None
    dash._set_toolbar_enabled = lambda *_a: None
    reconstruidas = []
    dash._rebuild_tabs = lambda *a: reconstruidas.append(a)
    monkeypatch.setattr(
        bd, "run_in_background",
        lambda work, cb: cb(True, ({}, ["EJECUTAR"], {"EJECUTAR": []}, set())),
    )
    vistos, parar = _escuchar()
    try:
        bd.BudgetDashboardFrame._load_data(dash)
    finally:
        parar()
    assert len(reconstruidas) == 1
    assert vistos == [("recarga", dash)]


def test_pantalla_de_inicio_abre_una_sola_ventana(qapp, monkeypatch):
    import src.gui.main_frame as mf
    import src.gui.obra_calendar_window as cw

    creadas = []

    class _Ventana:
        def __init__(self, parent=None):
            creadas.append(self)
            self.visible = False

            class _Destroyed:
                def connect(self, _f):
                    pass

            self.destroyed = _Destroyed()

        def show(self):
            self.visible = True

        def isVisible(self):
            return self.visible

        def raise_(self):
            pass

        def activateWindow(self):
            pass

    monkeypatch.setattr(cw, "ObraCalendarWindow", _Ventana)
    frame = mf.MainFrame.__new__(mf.MainFrame)
    QMainWindow.__init__(frame)
    frame._obra_calendar = None
    mf.MainFrame._open_obra_calendar(frame)
    mf.MainFrame._open_obra_calendar(frame)
    assert len(creadas) == 1 and creadas[0].visible
```

- [ ] **Step 2: Ejecutarlos y ver que fallan**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_obra_calendar_wiring.py`
Expected: FAIL (`AttributeError: ... '_on_external_planning_changed'` / `'_open_obra_calendar'` y la lista de avisos vacía).

- [ ] **Step 3: Dashboard**

En `src/gui/budget_dashboard.py`:

1. Debajo de `from src.utils.helpers import run_in_background` (línea 43), añadir:

```python
from src.gui import planning_events
```

2. En `__init__`, sustituir

```python
        self._build_ui()
        self._center()
        self._load_data()
```

por

```python
        self._build_ui()
        self._center()
        planning_events.planning_events().planning_changed.connect(self._on_external_planning_changed)
        self._load_data()
```

3. En `closeEvent`, antes de `super().closeEvent(event)`, añadir:

```python
        try:
            planning_events.planning_events().planning_changed.disconnect(self._on_external_planning_changed)
        except (RuntimeError, TypeError):
            pass
```

4. En `_load_data`, dentro de `_on_done`, sustituir

```python
            self._rebuild_tabs(
                states, root_path, prefetched if explorer == self._explorer_mode else None
            )
```

por

```python
            self._rebuild_tabs(
                states, root_path, prefetched if explorer == self._explorer_mode else None
            )
            if not explorer and explorer == self._explorer_mode:
                # La recarga completa puede haber movido obras de fase: el calendario se recarga.
                planning_events.notify_obras_reloaded(source=self)
```

5. En `_on_planning`, sustituir

```python
        if errores:
            QMessageBox.critical(self, "Planificación", f"No se pudo guardar:\n{errores[0]}")
        rutas = [s.get("ruta_excel") for s in selected if s.get("ruta_excel")]
```

por

```python
        if errores:
            QMessageBox.critical(self, "Planificación", f"No se pudo guardar:\n{errores[0]}")
        planning_events.notify_planning_changed([planning_key(s) for s in selected], source=self)
        rutas = [s.get("ruta_excel") for s in selected if s.get("ruta_excel")]
```

6. Debajo del método `_planning_margin`, añadir:

```python
    def _on_external_planning_changed(self, numeros, source):
        """Otra ventana (el calendario) guardó fechas: se repintan solo esas filas."""
        if source is self or self._explorer_mode:
            return
        wanted = set(numeros or ())
        rutas = [
            r.get("ruta_excel")
            for rows in self._tab_data.values()
            for r in rows
            if r.get("ruta_excel") and planning_key(r) in wanted
        ]
        if rutas:
            self._refresh_rows(rutas)
```

- [ ] **Step 4: Pantalla de inicio**

En `src/gui/main_frame.py`:

1. En `__init__`, debajo de `self._historical_memory_dashboard = None`, añadir:

```python
        self._obra_calendar = None
```

2. Debajo del bloque de `btn_open` (después de `btn_layout.addWidget(btn_open, ...)`), añadir:

```python
        btn_calendar = QPushButton("Calendario de obras")
        btn_calendar.setFixedSize(320, 46)
        btn_calendar.setFont(theme.font_base())
        btn_calendar.clicked.connect(self._open_obra_calendar)
        btn_layout.addWidget(btn_calendar, alignment=Qt.AlignmentFlag.AlignHCenter)
```

3. En `_create_menu`, justo después de `m_tools = menubar.addMenu("&Herramientas")`, añadir:

```python
        act_calendar = m_tools.addAction("Calendario de obras...")
        act_calendar.triggered.connect(self._open_obra_calendar)
```

4. Debajo del método `_open_dashboard`, añadir:

```python
    def _open_obra_calendar(self):
        try:
            from src.gui import obra_calendar_window

            if self._obra_calendar is not None:
                try:
                    if self._obra_calendar.isVisible():
                        self._obra_calendar.raise_()
                        self._obra_calendar.activateWindow()
                        return
                except RuntimeError:
                    self._obra_calendar = None
            self._obra_calendar = obra_calendar_window.ObraCalendarWindow(self)
            self._obra_calendar.destroyed.connect(lambda: setattr(self, "_obra_calendar", None))
            self._obra_calendar.show()
            self._obra_calendar.raise_()
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Error al abrir el calendario de obras: {ex}")
```

- [ ] **Step 5: Ejecutar los tests nuevos y los del dashboard**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_obra_calendar_wiring.py tests/test_obra_planning_gui.py tests/test_budget_dashboard_move_undo.py tests/test_budget_dashboard_row_refresh.py tests/test_gui_late_results.py`
Expected: todos PASS.

- [ ] **Step 6: Commit**

```bash
git add src/gui/budget_dashboard.py src/gui/main_frame.py tests/test_obra_calendar_wiring.py
git commit -m "feat(obras): abrir el calendario desde inicio y mantenerlo al día con el dashboard"
```

---

### Task C5: Documentación, suite completa y prueba manual

**Files:**
- Modify: `docs/README.md`
- Modify: `docs/superpowers/specs/2026-11-13-planificacion-obras-design.md` (solo la cabecera de estado)

- [ ] **Step 1: Índice de documentación**

En `docs/README.md`, sección «Planes pendientes», añadir como primera fila:

```markdown
| [`superpowers/plans/2026-11-15-calendario-obras.md`](superpowers/plans/2026-11-15-calendario-obras.md) | Pieza C de la batería de obras (calendario y resumen del mes), rama `calendario-obras`. Implementada; falta la prueba manual. Diseño: [`superpowers/specs/2026-11-15-calendario-obras-design.md`](superpowers/specs/2026-11-15-calendario-obras-design.md). |
```

Y en la fila de `2026-11-13-planificacion-obras.md`, sustituir «Siguen B (avisos y correo) y C (calendario y métricas).» por «Sigue B (avisos y correo); C (calendario) en `calendario-obras`.».

Los ficheros usan CRLF: si `Edit` falla por los finales de línea, leer el fichero antes con `Read`.

- [ ] **Step 2: Cabecera del diseño de la pieza A**

En `docs/superpowers/specs/2026-11-13-planificacion-obras-design.md`, debajo de la línea `> métricas. B y C usarán los datos de A.`, añadir:

```markdown
>
> Estado (2026-11-15): C hecha en la rama `calendario-obras`
> (`docs/superpowers/specs/2026-11-15-calendario-obras-design.md`); B sin empezar.
```

- [ ] **Step 3: Suite completa**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: todo PASS (referencia: 1275 passed, 2 skipped antes de esta rama, más los tests nuevos).

- [ ] **Step 4: Commit**

```bash
git add docs/README.md docs/superpowers/specs/2026-11-13-planificacion-obras-design.md
git commit -m "docs(obras): estado del calendario de obras"
```

- [ ] **Step 5: Prueba manual con el usuario**

Abrir la app desde la carpeta de trabajo (`../ProyectoJose/.venv/Scripts/python.exe main.py`) y comprobar con la BD real:

1. «Calendario de obras» en la pantalla de inicio y en Herramientas; un segundo clic trae la misma ventana.
2. El mes actual con «Hoy» resaltado; ◀ ▶ y «Hoy» cambian de mes.
3. «Sin fecha» con las obras de EJECUTAR; las que tienen fecha en el nombre muestran la propuesta y «Poner esta fecha».
4. Arrastrar una obra de «Sin fecha» a un día → etiqueta ▶ en ese día y aviso con Deshacer; Deshacer la devuelve.
5. Arrastrar la etiqueta a otro día; arrastrarla de vuelta a «Sin fecha».
6. Con «Presupuestos existentes» abierto: la fecha puesta en el calendario aparece en la columna «Inicio previsto» de EJECUTAR; cambiarla allí con doble clic actualiza el calendario.
7. Doble clic en una etiqueta abre la ventana de planificación; clic derecho → Abrir Excel / Abrir carpeta.
8. Franja de resumen con los números del mes.
```

