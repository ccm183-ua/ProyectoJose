"""
Parser de números escritos en español.

Convierte texto como ``CINCO MIL CIENTO QUINCE`` → 5115.0 y
``SEISCIENTOS CUARENTA Y TRES EUROS CON CINCUENTA CÉNTIMOS`` → 643.50.

Se usa para extraer el total de presupuestos desde la frase:
  "Asciende el presupuesto de ejecución material a la expresada cantidad de ..."
"""

import re
import unicodedata
from typing import Optional

# ---------------------------------------------------------------------------
# Diccionario: palabra → valor numérico
# ---------------------------------------------------------------------------
_UNITS = {
    "CERO": 0,
    "UN": 1, "UNO": 1, "UNA": 1,
    "DOS": 2,
    "TRES": 3,
    "CUATRO": 4,
    "CINCO": 5,
    "SEIS": 6,
    "SIETE": 7,
    "OCHO": 8,
    "NUEVE": 9,
    "DIEZ": 10,
    "ONCE": 11,
    "DOCE": 12,
    "TRECE": 13,
    "CATORCE": 14,
    "QUINCE": 15,
    "DIECISEIS": 16,
    "DIECISIETE": 17,
    "DIECIOCHO": 18,
    "DIECINUEVE": 19,
    "VEINTE": 20,
    "VEINTIUN": 21, "VEINTIUNO": 21, "VEINTIUNA": 21,
    "VEINTIDOS": 22,
    "VEINTITRES": 23,
    "VEINTICUATRO": 24,
    "VEINTICINCO": 25,
    "VEINTISEIS": 26,
    "VEINTISIETE": 27,
    "VEINTIOCHO": 28,
    "VEINTINUEVE": 29,
    "TREINTA": 30,
    "CUARENTA": 40,
    "CINCUENTA": 50,
    "SESENTA": 60,
    "SETENTA": 70,
    "OCHENTA": 80,
    "NOVENTA": 90,
}

_HUNDREDS = {
    "CIEN": 100,
    "CIENTO": 100,
    "DOSCIENTOS": 200, "DOSCIENTAS": 200,
    "TRESCIENTOS": 300, "TRESCIENTAS": 300,
    "CUATROCIENTOS": 400, "CUATROCIENTAS": 400,
    "QUINIENTOS": 500, "QUINIENTAS": 500,
    "SEISCIENTOS": 600, "SEISCIENTAS": 600,
    "SETECIENTOS": 700, "SETECIENTAS": 700,
    "OCHOCIENTOS": 800, "OCHOCIENTAS": 800,
    "NOVECIENTOS": 900, "NOVECIENTAS": 900,
}


def _strip_accents(text: str) -> str:
    """Elimina tildes y diacríticos para normalizar comparaciones."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _parse_group(words: list[str]) -> int:
    """Parsea un grupo de palabras que representan un número < 1000.

    Ejemplos:
        ["QUINIENTOS", "CUARENTA", "Y", "NUEVE"] → 549
        ["CIENTO", "SESENTA", "Y", "CINCO"] → 165
        ["ONCE"] → 11
        ["CIEN"] → 100
    """
    # Filtrar "Y" que conecta decenas con unidades
    words = [w for w in words if w != "Y"]
    if not words:
        return 0

    total = 0
    i = 0

    # Buscar centenas
    if i < len(words) and words[i] in _HUNDREDS:
        total += _HUNDREDS[words[i]]
        i += 1

    # Buscar decenas/unidades (pueden ser un solo token compuesto)
    if i < len(words) and words[i] in _UNITS:
        total += _UNITS[words[i]]
        i += 1

    # Buscar unidades sueltas después de decenas (TREINTA + OCHO)
    if i < len(words) and words[i] in _UNITS:
        total += _UNITS[words[i]]
        i += 1

    return total


def parse_spanish_number(text: str) -> Optional[float]:
    """Convierte un número escrito en español a float.

    Args:
        text: Texto con el número, ej: ``"CINCO MIL CIENTO QUINCE"``.

    Returns:
        El valor numérico, o None si no se pudo parsear.

    Ejemplos::

        >>> parse_spanish_number("CINCO MIL CIENTO QUINCE")
        5115.0
        >>> parse_spanish_number("NOVECIENTOS NOVENTA")
        990.0
        >>> parse_spanish_number("CERO")
        0.0
        >>> parse_spanish_number("SESENTA Y UN MIL NOVECIENTOS OCHENTA Y OCHO")
        61988.0
    """
    if not text:
        return None

    # Normalizar: mayúsculas, sin tildes, sin puntuación extra
    text = _strip_accents(text.upper().strip())
    # Limpiar caracteres no alfanuméricos excepto espacios
    text = re.sub(r"[^A-Z\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return None

    words = text.split()

    if words == ["CERO"]:
        return 0.0

    # Buscar "MILLON" / "MILLONES"
    million_value = 0
    if "MILLONES" in words or "MILLON" in words:
        sep = "MILLONES" if "MILLONES" in words else "MILLON"
        idx = words.index(sep)
        left = words[:idx]
        words = words[idx + 1:]
        # "DE" puede aparecer: "UN MILLÓN DE EUROS"
        if words and words[0] == "DE":
            words = words[1:]
        million_value = _parse_group(left) if left else 1
        million_value *= 1_000_000

    # Buscar "MIL"
    thousand_value = 0
    if "MIL" in words:
        idx = words.index("MIL")
        left = words[:idx]
        words = words[idx + 1:]
        thousand_value = _parse_group(left) if left else 1
        thousand_value *= 1000

    # Lo que queda son las unidades (0-999)
    remainder = _parse_group(words)

    total = million_value + thousand_value + remainder
    return float(total)


def extract_total_from_asciende(text: str) -> Optional[float]:
    """Extrae el importe total de la frase "Asciende el presupuesto...".

    Busca el patrón:
      ``... cantidad de [IMPORTE] EUROS [CON [CÉNTIMOS] CÉNTIMOS] ...``

    Args:
        text: Texto completo de la celda.

    Returns:
        Importe como float (ej: 5115.0, 643.50), o None si no encaja.
    """
    if not text:
        return None

    normalized = _strip_accents(text.upper())

    # Patrón: "CANTIDAD DE ... EUROS"
    match = re.search(
        r"CANTIDAD\s+DE\s+(.*?)\s+EUROS",
        normalized,
    )
    if not match:
        return None

    euros_text = match.group(1).strip()
    euros = parse_spanish_number(euros_text)
    if euros is None:
        return None

    # Buscar céntimos: "EUROS CON ... CENTIMOS"
    cents_match = re.search(
        r"EUROS\s+CON\s+(.*?)\s+CENTIMOS",
        normalized,
    )
    cents = 0.0
    if cents_match:
        cents_text = cents_match.group(1).strip()
        cents_val = parse_spanish_number(cents_text)
        if cents_val is not None:
            cents = cents_val / 100.0

    return round(euros + cents, 2)
