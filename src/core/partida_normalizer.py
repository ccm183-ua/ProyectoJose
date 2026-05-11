"""
Normalización de partidas para revisión y escritura homogénea en Excel.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Tuple


def _to_float(value, default: float = 0.0) -> float:
    try:
        if isinstance(value, str):
            value = value.replace(",", ".").strip()
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_historical_source(source: str) -> bool:
    s = (source or "").strip().lower()
    return s in {"historical", "historica", "histórica"}


def _unique_nonempty_parts(values: List[str]) -> str:
    seen: set[str] = set()
    parts: List[str] = []
    for v in values:
        t = (v or "").strip()
        if not t:
            continue
        key = re.sub(r"\s+", " ", t.lower())
        if key in seen:
            continue
        seen.add(key)
        parts.append(t)
    return "\n".join(parts)


def merge_historical_raw_blob(partida: Dict[str, Any]) -> str:
    """Une textos relevantes de una partida histórica para analizar título/descripción."""
    p = partida or {}
    fields = []
    for key in (
        "titulo",
        "descripcion",
        "concepto_original",
        "concepto",
        "description",
        "detalle",
        "texto",
    ):
        val = p.get(key)
        if val is not None and str(val).strip():
            fields.append(str(val).strip())
    return _unique_nonempty_parts(fields)


def strip_duplicate_title_prefix(title: str, description: str) -> Tuple[str, str]:
    t = (title or "").strip()
    d = (description or "").strip()
    if not t or not d:
        return t, d
    if d.lower().startswith(t.lower()):
        return t, d[len(t) :].strip()
    first_line_d = d.split("\n", 1)[0].strip()
    if first_line_d.lower() == t.lower():
        rest = d.split("\n", 1)[1] if "\n" in d else ""
        return t, rest.strip()
    return t, d


def split_title_description(text: str) -> Tuple[str, str]:
    """
    Divide un texto en título y descripción (heurística general, también usada por el writer).
    """
    raw = (text or "").strip()
    if not raw:
        return "", ""

    if "\n" in raw:
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lines:
            return "", ""
        return lines[0], "\n".join(lines[1:]).strip()

    # Punto como fin de título (20–120 caracteres antes del punto)
    dot_idx = raw.find(".")
    if 20 <= dot_idx <= 120:
        title = raw[: dot_idx + 1].strip()
        desc = raw[dot_idx + 1 :].strip()
        if title and desc:
            return title, desc

    # Punto corto (compatibilidad con heurística previa)
    if 0 < dot_idx < 20:
        title = raw[: dot_idx + 1].strip()
        desc = raw[dot_idx + 1 :].strip()
        if title and desc:
            return title, desc

    # Coma tras introducción razonable (15–90)
    comma_idx = raw.find(",")
    if 10 <= comma_idx <= 100:
        title = raw[:comma_idx].strip()
        desc = raw[comma_idx + 1 :].strip()
        if title and desc and len(title) <= 110:
            return title, desc

    return raw, ""


def force_split_long_plain_text(text: str, max_title: int = 85) -> Tuple[str, str]:
    """Parte un texto largo en título corto (aprox. max_title) y resto como descripción."""
    raw = (text or "").strip()
    if not raw or len(raw) <= max_title:
        return raw, ""
    chunk = raw[:max_title]
    sp = chunk.rfind(" ")
    cut = sp if sp > max_title // 2 else max_title
    title = raw[:cut].strip()
    desc = raw[cut:].strip()
    if not desc:
        title, desc = raw[:max_title].strip(), raw[max_title:].strip()
    return title, desc


def _all_uppercase(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters)


def aggressive_split_historical_text(text: str) -> Tuple[str, str]:
    """
    Separación agresiva para huella histórica: evita un único bloque largo como título.
    """
    raw = (text or "").strip()
    if not raw:
        return "", ""

    t, d = split_title_description(raw)
    if d:
        return t, d

    if len(raw) > 120:
        return force_split_long_plain_text(raw, max_title=85)

    if _all_uppercase(raw) and len(raw) > 80:
        return force_split_long_plain_text(raw, max_title=78)

    return raw, ""


def ensure_title_punctuation(title: str) -> str:
    t = (title or "").strip()
    if not t:
        return t
    if t[-1] not in ".!?:":
        t = t + "."
    return t


def format_excel_title_historical(title: str) -> str:
    """Una línea, mayúsculas y cierre de frase corta para Excel/UI histórica."""
    t = " ".join((title or "").replace("\n", " ").split())
    t = ensure_title_punctuation(t)
    return t.upper()


_ACRONYM_CANON = {
    "led": "LED",
    "pvc": "PVC",
    "kg": "KG",
    "iva": "IVA",
    "cte": "CTE",
    "ud": "ud",
    "m2": "m2",
    "m²": "m²",
    "ml": "ml",
    "mm": "mm",
}


def _letters_upper_ratio(s: str) -> float:
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if c.isupper()) / len(letters)


def format_historical_description_readable(desc: str) -> str:
    """
    Casing legible para descripciones históricas: no forzar todo a minúsculas si ya es mixto.
    Si viene casi todo en mayúsculas, pasa a frase con primera letra en mayúscula y siglas comunes.
    """
    raw = (desc or "").strip()
    if not raw:
        return ""
    if len(raw) < 12 or _letters_upper_ratio(raw) < 0.82:
        if raw and raw[0].islower():
            return raw[0].upper() + raw[1:]
        return raw

    s = raw.lower()

    def _cap_after_boundary(m: re.Match) -> str:
        g1, g2 = m.group(1), m.group(2)
        return g1 + g2.upper()

    s = re.sub(r"(^|[.!?]\s+|\n\s*)([a-záéíóúñü])", _cap_after_boundary, s, flags=re.MULTILINE)
    for low, up in _ACRONYM_CANON.items():
        s = re.sub(rf"\b{re.escape(low)}\b", up, s, flags=re.IGNORECASE)
    return s.strip()


def split_title_for_excel_bold(titulo: str, max_bold: int = 72) -> Tuple[str, str]:
    """
    Limita el tramo en negrita del título en Excel; el resto se antepone a la descripción.
    """
    t = (titulo or "").strip()
    if len(t) <= max_bold:
        return t, ""
    cut = t[:max_bold]
    sp = cut.rfind(" ")
    if sp < max_bold // 2:
        sp = max_bold
    bold = t[:sp].strip()
    tail = t[sp:].strip()
    return bold, tail


def normalize_partida_for_excel(partida: Dict, source: str = "") -> Dict:
    """
    Devuelve una partida con forma canónica para UI y writer Excel.
    """
    partida = partida or {}
    normalized_source = source or str(partida.get("source") or "").strip() or "unknown"
    historical = _is_historical_source(normalized_source)

    raw_title = str(partida.get("titulo", "") or "").strip()
    raw_desc = str(
        partida.get("descripcion")
        or partida.get("description")
        or partida.get("detalle")
        or partida.get("texto")
        or ""
    ).strip()

    if historical:
        if raw_title and raw_desc:
            title, description = raw_title, raw_desc
        elif raw_title and not raw_desc:
            title, description = aggressive_split_historical_text(raw_title)
        else:
            blob = merge_historical_raw_blob(partida)
            title, description = aggressive_split_historical_text(blob)
        title, description = strip_duplicate_title_prefix(title, description)
        if title and not description and len(title) > 120:
            title, description = force_split_long_plain_text(title, max_title=85)
            title, description = strip_duplicate_title_prefix(title, description)
        full_len = len(title) + len(description)
        if full_len > 120 and not description.strip():
            title, description = force_split_long_plain_text(title or merge_historical_raw_blob(partida), 85)
            title, description = strip_duplicate_title_prefix(title, description)
    else:
        if raw_title and raw_desc:
            title, description = raw_title, raw_desc
        elif raw_title and not raw_desc:
            title, description = split_title_description(raw_title)
        else:
            preferred_text = (
                partida.get("concepto_original")
                or partida.get("concepto")
                or partida.get("title")
                or ""
            )
            title, description = split_title_description(str(preferred_text))

    title = (title or "").strip()
    description = (description or "").strip()
    title, description = strip_duplicate_title_prefix(title, description)

    if historical:
        title = format_excel_title_historical(title)
        description = format_historical_description_readable(description)

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
    total = round(cantidad * precio, 2)

    if not title:
        title = (
            str(partida.get("concepto") or partida.get("concepto_original") or "Partida")
            .strip()[:240]
        )

    concepto = str(partida.get("concepto") or title).strip()

    return {
        "codigo": str(partida.get("codigo", "") or "").strip(),
        "titulo": title,
        "descripcion": description,
        "concepto": concepto or title,
        "unidad": unidad,
        "cantidad": cantidad,
        "precio": precio,
        "precio_unitario": precio,
        "total": total,
        "source": normalized_source,
        "confidence": partida.get("confidence", ""),
        "historical_frequency": partida.get("historical_frequency", 0),
    }
