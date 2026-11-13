"""Biblioteca de partidas: buscar en el histórico y convertir la selección en candidatas.

Núcleo sin PySide6. Solo lectura sobre la BD. Ver
docs/superpowers/specs/2026-11-12-biblioteca-partidas-design.md.
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional

from src.core import database
from src.core.work_type_normalizer import normalize_text

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


@dataclass(frozen=True)
class LibraryLine:
    partida_id: int
    budget_id: int
    proyecto: str
    concepto: str
    concepto_norm: str
    unidad: str
    unidad_canon: str
    precio: float
    status: str
    fecha: Optional[date]
    module: str


_LOAD_SQL = """
    SELECT hp.id, hp.historical_budget_id, COALESCE(hb.nombre_proyecto, ''),
           COALESCE(NULLIF(hp.concepto_original, ''), hp.titulo, ''),
           COALESCE(hp.concepto_normalizado, ''), COALESCE(hp.unidad, ''),
           hp.precio_unitario, COALESCE(hb.learning_status, ''),
           COALESCE(hb.analysis_status, ''), COALESCE(hb.fecha_presupuesto, ''),
           COALESCE(f.primary_module_id, '')
    FROM historical_partida hp
    JOIN historical_budget hb ON hb.id = hp.historical_budget_id
    LEFT JOIN historical_partida_feature f ON f.partida_id = hp.id
    WHERE hp.precio_unitario > 0
"""


class PartidaLibrary:
    """Partidas con precio del histórico, cargadas en memoria para buscar."""

    def __init__(self, lines: List[LibraryLine], ignored: int = 0):
        self.lines = list(lines)
        self.ignored = ignored

    @classmethod
    def load(cls) -> "PartidaLibrary":
        lines: List[LibraryLine] = []
        ignored = 0
        with database.get_connection(read_only=True) as conn:
            rows = conn.execute(_LOAD_SQL).fetchall()
        for (pid, bid, proyecto, concepto, concepto_norm, unidad, precio,
             learning, analysis, fecha_raw, module) in rows:
            concepto = (concepto or "").replace("\r\n", "\n").strip()
            norm = (concepto_norm or "").strip() or normalize_text(concepto)
            try:
                price = float(precio)
            except (TypeError, ValueError):
                price = float("nan")
            if not norm or not math.isfinite(price) or price <= 0:
                ignored += 1
                continue
            lines.append(LibraryLine(
                partida_id=int(pid), budget_id=int(bid), proyecto=proyecto or "",
                concepto=concepto, concepto_norm=norm, unidad=(unidad or "").strip(),
                unidad_canon=canonical_unit(unidad), precio=price,
                status=line_status(learning, analysis), fecha=parse_budget_date(fecha_raw),
                module=(module or "").strip(),
            ))
        return cls(lines, ignored)

