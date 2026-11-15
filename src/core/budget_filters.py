"""Filtros del dashboard «Presupuestos existentes» (lógica pura, sin Qt).

Diseño: docs/superpowers/specs/2026-11-14-dashboard-filtros-ux-design.md
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Iterable, List, Optional, Tuple

from src.utils.budget_utils import normalize_date

_DATE_FORMATS = ("%d-%m-%y", "%d/%m/%y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d")
_TEXT_FIELDS = ("cliente", "administracion")


@dataclass(frozen=True)
class BudgetFilters:
    cliente: str = ""
    administracion: str = ""
    fecha_desde: Optional[date] = None
    fecha_hasta: Optional[date] = None
    importe_min: Optional[float] = None
    importe_max: Optional[float] = None

    def active_count(self) -> int:
        texts = [v for v in (self.cliente, self.administracion) if (v or "").strip()]
        others = [v for v in (self.fecha_desde, self.fecha_hasta, self.importe_min, self.importe_max)
                  if v is not None]
        return len(texts) + len(others)

    def is_empty(self) -> bool:
        return self.active_count() == 0


def _norm(value) -> str:
    return " ".join(str(value or "").split()).casefold()


def parse_budget_date(value) -> Optional[date]:
    """Fecha de un presupuesto (`dd-mm-yy`, `dd/mm/yyyy`, ISO o serial de Excel)."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = normalize_date(str(value or "")).strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _total(row: dict) -> Optional[float]:
    """Total con IVA; vacío, cero o ilegible cuenta como "sin total"."""
    try:
        value = float(row.get("total"))
    except (TypeError, ValueError):
        return None
    return value or None


def apply_filters(rows: Iterable[dict], filters: BudgetFilters) -> List[dict]:
    rows = list(rows)
    if filters is None or filters.is_empty():
        return rows
    cliente = _norm(filters.cliente)
    admin = _norm(filters.administracion)
    by_date = filters.fecha_desde is not None or filters.fecha_hasta is not None
    by_amount = filters.importe_min is not None or filters.importe_max is not None
    out = []
    for row in rows:
        if cliente and _norm(row.get("cliente")) != cliente:
            continue
        if admin and _norm(row.get("administracion_nombre")) != admin:
            continue
        if by_date:
            d = parse_budget_date(row.get("fecha"))
            if d is None:
                continue
            if filters.fecha_desde is not None and d < filters.fecha_desde:
                continue
            if filters.fecha_hasta is not None and d > filters.fecha_hasta:
                continue
        if by_amount:
            t = _total(row)
            if t is None:
                continue
            if filters.importe_min is not None and t < filters.importe_min:
                continue
            if filters.importe_max is not None and t > filters.importe_max:
                continue
        out.append(row)
    return out


def summarize(rows: Iterable[dict]) -> Tuple[int, float]:
    rows = list(rows)
    return len(rows), sum(t for t in (_total(r) for r in rows) if t is not None)


def format_eur(amount: float) -> str:
    return f"{float(amount or 0):,.0f}".replace(",", ".") + " €"


def summary_text(count: int, total: float) -> str:
    noun = "presupuesto" if count == 1 else "presupuestos"
    return f"{count} {noun} · {format_eur(total)}"


def distinct_values(rows: Iterable[dict], key: str) -> List[str]:
    seen = {}
    for row in rows:
        value = " ".join(str(row.get(key) or "").split())
        if value and _norm(value) not in seen:
            seen[_norm(value)] = value
    return sorted(seen.values(), key=str.casefold)


def _fmt_date(d: date) -> str:
    return d.strftime("%d/%m/%y")


def filter_chips(filters: BudgetFilters) -> List[Tuple[str, str]]:
    chips = []
    if (filters.cliente or "").strip():
        chips.append(("cliente", f"Cliente: {filters.cliente.strip()}"))
    if (filters.administracion or "").strip():
        chips.append(("administracion", f"Admin.: {filters.administracion.strip()}"))
    if filters.fecha_desde is not None:
        chips.append(("fecha_desde", f"desde {_fmt_date(filters.fecha_desde)}"))
    if filters.fecha_hasta is not None:
        chips.append(("fecha_hasta", f"hasta {_fmt_date(filters.fecha_hasta)}"))
    if filters.importe_min is not None:
        chips.append(("importe_min", f"≥ {format_eur(filters.importe_min)}"))
    if filters.importe_max is not None:
        chips.append(("importe_max", f"≤ {format_eur(filters.importe_max)}"))
    return chips


def without(filters: BudgetFilters, field: str) -> BudgetFilters:
    return replace(filters, **{field: "" if field in _TEXT_FIELDS else None})
