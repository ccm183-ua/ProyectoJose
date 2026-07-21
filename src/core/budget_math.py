"""
Cálculo determinista de importes y totales de presupuesto.

Única fuente de verdad de estas fórmulas: ni Excel, ni la IA, ni ningún
adapter deben calcular esto por su cuenta. Un total leído de otra fuente
sirve solo para comparar y generar una advertencia si difiere.
"""

from typing import Dict, Iterable

IVA_RATE = 0.10  # tipo de IVA por defecto


def calcular_importe_linea(cantidad: float, precio: float) -> float:
    return round(float(cantidad or 0) * float(precio or 0), 2)


def calcular_totales(importes: Iterable[float], iva_rate: float = IVA_RATE) -> Dict[str, float]:
    subtotal = round(sum(float(i or 0) for i in importes), 2)
    iva = round(subtotal * iva_rate, 2)
    total = round(subtotal + iva, 2)
    return {"subtotal": subtotal, "iva": iva, "total": total}
