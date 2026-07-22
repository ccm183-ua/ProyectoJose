"""
Modelo de procedencia por partida (Fase 4, Tarea 12): traduce el par
(source, evidencia del comparador) a las columnas que debe ver el usuario,
sin depender de PySide6 para poder probarlo sin arrancar la GUI.

No sustituye las columnas "Origen"/"Motivo/Fuente" ya existentes en
combined_partidas_review_dialog.py; añade Fuente/Nivel/Rango histórico/
Diferencias como vocabulario de evidencia (Tarea 8/10) todavía no cableado
en la tabla real.
"""

from typing import Dict, List, Optional

_SOURCE_LABELS = {
    "historical": "Histórico",
    "historical_exact": "Histórico",
    "historical_comparable": "Histórico",
    "ai_completion": "IA — borrador",
    "ai_draft": "IA — borrador",
}

_LEVEL_LABELS = {
    "exact": "Exacto",
    "comparable": "Comparable",
    "related": "Relacionado (sin precio)",
    "incompatible": "Incompatible",
}

_NO_EVIDENCE = "Sin evidencia privada comparable"
_PRICED_LEVELS = {"exact", "comparable"}


def row_for_partida(partida: Dict) -> Dict[str, str]:
    source = partida.get("source") or ""
    level = partida.get("evidence_level")
    differences: Optional[List[str]] = partida.get("evidence_differences")

    nivel = _LEVEL_LABELS.get(level, _NO_EVIDENCE)
    if level in _PRICED_LEVELS:
        precio_min = float(partida.get("evidence_price_min") or 0)
        precio_median = float(partida.get("evidence_price_median") or 0)
        precio_max = float(partida.get("evidence_price_max") or 0)
        rango = f"{precio_min:.2f} – {precio_median:.2f} – {precio_max:.2f}"
    else:
        rango = _NO_EVIDENCE

    return {
        "Fuente": _SOURCE_LABELS.get(source, source or "Desconocido"),
        "Nivel": nivel,
        "Rango histórico": rango,
        "Diferencias": ", ".join(differences) if differences else "—",
    }
