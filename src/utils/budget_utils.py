"""
Utilidades compartidas para procesamiento de datos de presupuestos.

Funciones auxiliares usadas tanto por ``project_data_resolver`` como
por ``budget_cache`` para normalizar fechas y limpiar textos del Excel.
"""

import re
from datetime import datetime, timedelta

_RE_OBRA_PREFIX = re.compile(r"^\s*Obra\s*:\s*", re.IGNORECASE)

EXCEL_EPOCH = datetime(1899, 12, 30)

# Regex para extraer (número, año) de formatos como "71-26", "71/26", "120/20"
RE_PROJECT_NUM = re.compile(r"(\d{1,4})[/-](\d{2})")


def normalize_project_num(value: str) -> str:
    """Normaliza un número de proyecto a formato ``N-YY`` para comparación.

    Acepta formatos como ``71-26``, ``71/26``, ``120/20``, ``06-26``, etc.
    Elimina ceros iniciales para que ``06-26`` y ``6/26`` se consideren iguales.
    Devuelve cadena vacía si no se puede parsear.
    """
    m = RE_PROJECT_NUM.search(value or "")
    if not m:
        return ""
    num = str(int(m.group(1)))
    year = m.group(2)
    return f"{num}-{year}"


def normalize_date(value: str) -> str:
    """Convierte un valor de fecha a formato DD-MM-YY.

    Si el valor es un número serial de Excel (ej: '44174'), lo convierte.
    Si ya es texto legible lo devuelve tal cual.
    """
    if not value:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        num = float(text)
        if 1 < num < 200000:
            dt = EXCEL_EPOCH + timedelta(days=int(num))
            return dt.strftime("%d-%m-%y")
    except (ValueError, TypeError, OverflowError):
        pass

    # Formatos textuales comunes: DD/MM/YY, DD/MM/YYYY, DD-MM-YY, DD.MM.YYYY
    text_norm = text.replace(".", "-").replace("/", "-")
    m = re.match(r"^\s*(\d{1,2})-(\d{1,2})-(\d{2}|\d{4})\s*$", text_norm)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year_raw = m.group(3)
        year = int(year_raw)
        if len(year_raw) == 2:
            year += 2000
        try:
            dt = datetime(year, month, day)
            return dt.strftime("%d-%m-%y")
        except ValueError:
            pass

    return text


def strip_obra_prefix(value: str) -> str:
    """Elimina el prefijo 'Obra: ' que se escribe en el Excel, dejando solo el texto útil."""
    cleaned = _RE_OBRA_PREFIX.sub("", value).strip()
    if cleaned.endswith("."):
        cleaned = cleaned[:-1].strip()
    return cleaned
