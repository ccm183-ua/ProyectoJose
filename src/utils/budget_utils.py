"""
Utilidades compartidas para procesamiento de datos de presupuestos.

Funciones auxiliares usadas tanto por ``project_data_resolver`` como
por ``budget_cache`` para normalizar fechas y limpiar textos del Excel.
"""

import re
from datetime import datetime, timedelta

_RE_OBRA_PREFIX = re.compile(r"^Obra:\s*", re.IGNORECASE)

_EXCEL_EPOCH = datetime(1899, 12, 30)


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
    # Intentar convertir serial de Excel
    try:
        num = float(text)
        if 1 < num < 200000:
            dt = _EXCEL_EPOCH + timedelta(days=int(num))
            return dt.strftime("%d-%m-%y")
    except (ValueError, TypeError, OverflowError):
        pass
    return text


def strip_obra_prefix(value: str) -> str:
    """Elimina el prefijo 'Obra: ' que se escribe en el Excel, dejando solo el texto útil."""
    cleaned = _RE_OBRA_PREFIX.sub("", value).strip()
    if cleaned.endswith("."):
        cleaned = cleaned[:-1].strip()
    return cleaned
