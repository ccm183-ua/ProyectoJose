"""Biblioteca de partidas: buscar en el histórico y convertir la selección en candidatas.

Núcleo sin PySide6. Solo lectura sobre la BD. Ver
docs/superpowers/specs/2026-11-12-biblioteca-partidas-design.md.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from typing import Dict, Optional

STATUS_RANK: Dict[str, int] = {"approved": 0, "unreviewed": 1, "ineligible": 2}
STATUS_LABELS: Dict[str, str] = {"approved": "aprobada", "unreviewed": "sin revisar", "ineligible": "no apta"}

_VALID_ANALYSIS = {"VALID", "VALID_WITH_WARNINGS"}

_UNIT_ALIASES: Dict[str, str] = {
    "p.a.": "p.a.", "p.a": "p.a.", "pa": "p.a.", "partida": "p.a.",
    "ud": "ud", "ud.": "ud", "u": "ud",
    "m2": "m2",
    "m": "m", "ml": "m",
    "m3": "m3",
    "kg": "kg",
    "dia": "día", "dias": "día",
}

_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})")
_EMBEDDED_DATE_RE = re.compile(r"fecha:\s*(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\b", re.IGNORECASE)
_EXCEL_EPOCH = date(1899, 12, 30)


def _fold(text) -> str:
    """Minúsculas y sin tildes (NFKD convierte '²' en '2')."""
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower().strip()


def canonical_unit(raw) -> str:
    """Unidad canónica para agrupar; '?' si no se reconoce."""
    return _UNIT_ALIASES.get(_fold(raw), "?")


def parse_budget_date(raw) -> Optional[date]:
    """Fecha de presupuesto desde 'dd/mm/aa', 'dd/mm/aaaa' o número de serie de Excel."""
    text = str(raw or "").strip()
    if not text:
        return None
    # Certificaciones: "CERTIFICACIÓN Nº 2   Fecha: 08/11/24".
    match = _DATE_RE.fullmatch(text) or _EMBEDDED_DATE_RE.search(text)
    if match:
        day, month, year = (int(g) for g in match.groups())
        if year < 100:
            year += 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None
    try:
        serial = float(text.replace(",", "."))
    except ValueError:
        return None
    if 30000 <= serial <= 60000:
        return _EXCEL_EPOCH + timedelta(days=int(serial))
    return None


def line_status(learning_status: str, analysis_status: str) -> str:
    """Estado de una línea según su presupuesto."""
    if (analysis_status or "") not in _VALID_ANALYSIS:
        return "ineligible"
    if learning_status == "INCLUDED":
        return "approved"
    if learning_status == "PENDING_REVIEW":
        return "unreviewed"
    return "ineligible"
