"""
Normalización de partidas para revisión y escritura homogénea en Excel.
"""

from __future__ import annotations

from typing import Dict, Tuple


def _to_float(value, default: float = 0.0) -> float:
    try:
        if isinstance(value, str):
            value = value.replace(",", ".").strip()
        return float(value)
    except (TypeError, ValueError):
        return default


def split_title_description(text: str) -> Tuple[str, str]:
    """
    Divide un texto en título y descripción aplicando heurísticas conservadoras.
    """
    raw = (text or "").strip()
    if not raw:
        return "", ""

    if "\n" in raw:
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lines:
            return "", ""
        return lines[0], "\n".join(lines[1:]).strip()

    # Heurística simple: primera frase corta como título.
    dot_idx = raw.find(".")
    if 0 < dot_idx <= 70:
        title = raw[: dot_idx + 1].strip()
        desc = raw[dot_idx + 1 :].strip()
        if title and desc:
            return title, desc
    return raw, ""


def normalize_partida_for_excel(partida: Dict, source: str = "") -> Dict:
    """
    Devuelve una partida con forma canónica para UI y writer Excel.
    """
    partida = partida or {}
    raw_title = str(partida.get("titulo", "") or "").strip()
    raw_desc = str(partida.get("descripcion", "") or "").strip()

    if raw_title:
        title = raw_title
        description = raw_desc
    else:
        preferred_text = (
            partida.get("concepto_original")
            or partida.get("concepto")
            or partida.get("title")
            or ""
        )
        title, description = split_title_description(str(preferred_text))

    unidad = (
        str(
            partida.get("unidad")
            or partida.get("ud")
            or partida.get("unit")
            or "ud"
        )
        .strip()
        or "ud"
    )
    cantidad = _to_float(partida.get("cantidad"), 1.0)
    precio = _to_float(
        partida.get("precio")
        if partida.get("precio") is not None
        else partida.get("precio_unitario"),
        0.0,
    )
    concepto = str(partida.get("concepto") or title).strip()
    total = round(cantidad * precio, 2)

    normalized_source = source or str(partida.get("source") or "").strip() or "unknown"

    return {
        "codigo": str(partida.get("codigo", "") or "").strip(),
        "titulo": title,
        "descripcion": description,
        "concepto": concepto,
        "unidad": unidad,
        "cantidad": cantidad,
        "precio": precio,
        "precio_unitario": precio,
        "total": total,
        "source": normalized_source,
    }
