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
