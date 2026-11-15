"""Planificación de obras: reglas puras (fechas desde el nombre de carpeta, avisos).

Sin PySide6 ni BD. Ver docs/superpowers/specs/2026-11-13-planificacion-obras-design.md.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Optional, Tuple

DEFAULT_MARGEN_AVISO_DIAS = 7

_MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# dd-mm-aa, dd/mm/aaaa, dd.mm.aa como palabra suelta (no dentro de "28-03004").
_DMY_RE = re.compile(r"(?<![\d-])(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})(?![\d])")
# "julio'26", "julio 26", "julio 2026", "julio de 2026"
_MES_RE = re.compile(
    r"\b(" + "|".join(_MESES) + r")\s*(?:de\s+)?['´’]?\s*(\d{4}|\d{2})\b"
)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def date_from_folder_name(nombre: str) -> Optional[Tuple[date, bool]]:
    """Fecha escrita en el nombre de la carpeta: (fecha, aproximada) o None.

    Las de mes y año ("EN JULIO'26") se devuelven como día 1, aproximadas.
    """
    text = _fold(nombre)
    for match in _DMY_RE.finditer(text):
        day, month, year = (int(g) for g in match.groups())
        if year < 100:
            year += 2000
        try:
            return date(year, month, day), False
        except ValueError:
            continue
    match = _MES_RE.search(text)
    if match:
        year = int(match.group(2))
        if year < 100:
            year += 2000
        return date(year, _MESES[match.group(1)], 1), True
    return None


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def aviso_text(inicio: Optional[date], avisado: Optional[date], margen: int, hoy: date) -> str:
    """Texto de la columna Aviso (pestaña EJECUTAR)."""
    if inicio is None:
        return ""
    if avisado is not None:
        return f"avisada el {avisado:%d/%m}"
    dias = (inicio - hoy).days
    if dias < 0:
        return f"debía empezar hace {_plural(-dias, 'día', 'días')}"
    if dias == 0:
        return "hoy"
    if dias == 1:
        return "mañana"
    if dias <= margen:
        return f"en {dias} días"
    return ""


def color_category(inicio: Optional[date], margen: int, hoy: date) -> str:
    """"warning" (dentro del margen), "late" (ya pasó y sigue en EJECUTAR) o ""."""
    if inicio is None:
        return ""
    dias = (inicio - hoy).days
    if dias < 0:
        return "late"
    if dias <= margen:
        return "warning"
    return ""


def retraso_text(fin_previsto: Optional[date], hoy: date) -> str:
    """Días que lleva pasada la fecha de fin prevista (pestaña EJECUTANDO)."""
    if fin_previsto is None or hoy <= fin_previsto:
        return ""
    return _plural((hoy - fin_previsto).days, "día", "días")


def duracion_text(inicio: Optional[date], fin: Optional[date]) -> str:
    """Días entre inicio y fin reales (pestaña TERMINADO)."""
    if inicio is None or fin is None or fin < inicio:
        return ""
    return _plural((fin - inicio).days, "día", "días")
