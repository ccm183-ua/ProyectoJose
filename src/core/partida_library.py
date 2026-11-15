"""Biblioteca de partidas: buscar en el histórico y convertir la selección en candidatas.

Núcleo sin PySide6. Solo lectura sobre la BD. Ver
docs/superpowers/specs/2026-11-12-biblioteca-partidas-design.md.
"""

from __future__ import annotations

import math
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from src.core import database
from src.core.work_type_normalizer import keyword_in_text, normalize_text

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


WARNING_NO_APPROVED = "sin evidencia aprobada"
WARNING_LUMP_SUM = "partida alzada: revisa el alcance"
WARNING_UNKNOWN_UNIT = "unidad no reconocida"
MAX_GROUPS = 200


@dataclass
class LibraryGroup:
    concepto_norm: str
    unidad_canon: str
    lines: List[LibraryLine]
    n_budgets: int = 0
    price_min: float = 0.0
    price_median: float = 0.0
    price_max: float = 0.0
    approved_median: Optional[float] = None
    status: str = "ineligible"
    fecha: Optional[date] = None
    module: str = ""
    proposed_price: float = 0.0
    price_basis: str = "median_all"
    warnings: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def representative(self) -> LibraryLine:
        """Línea cuyo texto se usa al insertar: mejor estado y, a igualdad, la más reciente."""
        return min(
            self.lines,
            key=lambda l: (STATUS_RANK[l.status], -(l.fecha.toordinal() if l.fecha else 0), l.partida_id),
        )


@dataclass
class SearchResult:
    groups: List[LibraryGroup]
    total_groups: int

    @property
    def truncated(self) -> bool:
        return self.total_groups > len(self.groups)


def _build_group(concepto_norm: str, unidad_canon: str, lines: List[LibraryLine]) -> LibraryGroup:
    prices = [l.precio for l in lines]
    approved = [l.precio for l in lines if l.status == "approved"]
    fechas = [l.fecha for l in lines if l.fecha]
    modules = Counter(l.module for l in lines if l.module)
    group = LibraryGroup(
        concepto_norm=concepto_norm,
        unidad_canon=unidad_canon,
        lines=lines,
        n_budgets=len({l.budget_id for l in lines}),
        price_min=min(prices),
        price_median=statistics.median(prices),
        price_max=max(prices),
        approved_median=statistics.median(approved) if approved else None,
        status=min((l.status for l in lines), key=STATUS_RANK.__getitem__),
        fecha=max(fechas) if fechas else None,
        module=modules.most_common(1)[0][0] if modules else "",
    )
    warnings: List[str] = []
    if group.approved_median is not None:
        group.proposed_price, group.price_basis = group.approved_median, "median_approved"
    else:
        group.proposed_price, group.price_basis = group.price_median, "median_all"
        warnings.append(WARNING_NO_APPROVED)
    if unidad_canon == "p.a.":
        warnings.append(WARNING_LUMP_SUM)
    if unidad_canon == "?":
        warnings.append(WARNING_UNKNOWN_UNIT)
    group.warnings = tuple(warnings)
    return group


def _group_sort_key(group: LibraryGroup):
    return (
        0 if group.approved_median is not None else 1,
        -group.n_budgets,
        -(group.fecha.toordinal() if group.fecha else 0),
        group.concepto_norm,
    )


def to_candidate(group: LibraryGroup, line: Optional[LibraryLine] = None) -> Dict:
    """Partida candidata para la revisión. Nunca lleva un source 'historical*'.

    Sin `line`, usa el precio propuesto del grupo y el texto de su línea
    representativa; con `line`, el precio y el texto de esa obra concreta.
    """
    if line is None:
        rep = group.representative
        lines = group.lines
        price, basis, status = group.proposed_price, group.price_basis, group.status
        units = Counter(l.unidad for l in lines if l.unidad)
        unidad = rep.unidad or (units.most_common(1)[0][0] if units else "ud")
    else:
        rep, lines = line, [line]
        price, basis, status = line.precio, "instance", line.status
        unidad = line.unidad or "ud"
    titulo, _, descripcion = rep.concepto.partition("\n")
    return {
        "titulo": titulo.strip(),
        "descripcion": descripcion.strip(),
        "concepto": rep.concepto,
        "unidad": unidad,
        "cantidad": 1.0,
        "precio_unitario": round(float(price), 2),
        "source": "library",
        "library_status": status,
        "library_price_basis": basis,
        "library_partida_ids": sorted(l.partida_id for l in lines),
        "library_budget_ids": sorted({l.budget_id for l in lines}),
    }


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

    def search(self, query: str = "", module: str = "", unit: str = "",
               status_filter: str = "all", limit: int = MAX_GROUPS) -> SearchResult:
        """Grupos que contienen todas las palabras de `query` desde inicio de palabra.

        `status_filter`: "all", "approved" o "no_ineligible". Sin texto ni
        filtros no devuelve nada (no se listan las ~17.000 partidas).
        """
        tokens = normalize_text(query or "").split()
        if not tokens and not module and not unit:
            return SearchResult([], 0)
        buckets: Dict[Tuple[str, str], List[LibraryLine]] = defaultdict(list)
        for line in self.lines:
            if module and line.module != module:
                continue
            if unit and line.unidad_canon != unit:
                continue
            if status_filter == "approved" and line.status != "approved":
                continue
            if status_filter == "no_ineligible" and line.status == "ineligible":
                continue
            if not all(keyword_in_text(t, line.concepto_norm) for t in tokens):
                continue
            buckets[(line.concepto_norm, line.unidad_canon)].append(line)
        groups = [_build_group(c, u, ls) for (c, u), ls in buckets.items()]
        groups.sort(key=_group_sort_key)
        return SearchResult(groups[:limit], len(groups))

