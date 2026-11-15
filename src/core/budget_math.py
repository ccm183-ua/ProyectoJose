"""
Cálculo determinista de importes y totales de presupuesto.

Única fuente de verdad de estas fórmulas: ni Excel, ni la IA, ni ningún
adapter deben calcular esto por su cuenta. Un total leído de otra fuente
sirve solo para comparar y generar una advertencia si difiere.
"""

import math
import re
from typing import Any, Dict, Iterable

IVA_RATE = 0.10  # tipo de IVA por defecto

_DECIMAL_JUNK_RE = re.compile(r"[\s €]")


def parse_decimal_es(value: Any) -> float:
    """Convierte un importe/cantidad a float entendiendo el formato español.

    Sustituye a ``float(texto.replace(",", "."))``, que convertía
    "1.250,00" en error (y los llamadores lo tapaban con 0.0).

    Reglas:
      - Números (no bool) se devuelven tal cual.
      - Con "." y "," a la vez, el último separador es el decimal
        ("1.250,00" → 1250.0; "1,250.00" → 1250.0).
      - Solo ",": una coma es decimal ("12,5"); varias son de miles.
      - Solo ".": varios puntos son de miles ("1.250.000"); uno solo es
        decimal ("12.5"), como lo devuelve la IA o un JSON.
      - Se ignoran espacios y el símbolo €.

    Raises:
        ValueError / TypeError si no es un número finito.
    """
    if isinstance(value, bool) or value is None:
        raise TypeError(f"valor no numérico: {value!r}")
    if isinstance(value, (int, float)):
        result = float(value)
    else:
        text = _DECIMAL_JUNK_RE.sub("", str(value))
        if not text:
            raise ValueError("valor vacío")
        has_dot, has_comma = "." in text, "," in text
        thousands = None
        if has_dot and has_comma:
            if text.rfind(",") > text.rfind("."):
                thousands, decimal = ".", ","
            else:
                thousands, decimal = ",", "."
        elif has_comma:
            if text.count(",") == 1:
                text = text.replace(",", ".")
            else:
                thousands, decimal = ",", None
        elif has_dot and text.count(".") > 1:
            thousands, decimal = ".", None
        if thousands:
            int_part, _, dec_part = (
                text.rpartition(decimal) if decimal else (text, "", "")
            )
            if decimal and not int_part:
                int_part, dec_part = dec_part, ""
            groups = int_part.lstrip("+-").split(thousands)
            if not groups[0] or any(len(g) != 3 for g in groups[1:]):
                raise ValueError(f"separador de miles mal formado: {value!r}")
            text = int_part.replace(thousands, "") + ("." + dec_part if dec_part else "")
        result = float(text)
    if not math.isfinite(result):
        raise ValueError(f"valor no finito: {value!r}")
    return result


def calcular_importe_linea(cantidad: float, precio: float) -> float:
    return round(float(cantidad or 0) * float(precio or 0), 2)


def calcular_totales(importes: Iterable[float], iva_rate: float = IVA_RATE) -> Dict[str, float]:
    subtotal = round(sum(float(i or 0) for i in importes), 2)
    iva = round(subtotal * iva_rate, 2)
    total = round(subtotal + iva, 2)
    return {"subtotal": subtotal, "iva": iva, "total": total}
