# Filtros y limpieza de UX en «Presupuestos existentes» — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir filtros por pestaña (cliente, administración, fechas, importe) al dashboard de presupuestos y quitarle botones repetidos y ventanas innecesarias, sustituyendo los avisos de éxito por un aviso pasajero con acciones (Deshacer, Finalizar, Abrir).

**Architecture:** La lógica de filtrado es un módulo puro (`src/core/budget_filters.py`). La interfaz se reparte en dos widgets nuevos (`src/gui/widgets/budget_filter_bar.py` y `src/gui/widgets/toast.py`) para que `budget_dashboard.py` (2.200 líneas) no crezca más de lo imprescindible. El dashboard guarda los filtros por pestaña en memoria y los aplica junto al buscador en un único punto (`_visible_rows`).

**Tech Stack:** Python 3, PySide6, SQLite, pytest (con `qapp` de `tests/conftest.py`).

**Spec:** `docs/superpowers/specs/2026-11-14-dashboard-filtros-ux-design.md`

## Global Constraints

- Rama `dashboard-filtros-ux`, carpeta de trabajo `C:\Users\cayet\Documentos\Documentos\Dev\ProyectoJose-filtros`. No tocar la carpeta principal `ProyectoJose` (es de la sesión de planificación).
- Tests: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` desde la carpeta de trabajo (el `python` del sistema no tiene openpyxl).
- Textos de la interfaz en castellano de España, con tildes.
- No cambiar el comportamiento del módulo de generar partidas (solo se mueven sus entradas de menú).
- Regla de confirmaciones: solo se pregunta antes de algo irreversible que borra o sustituye contenido del Excel; los éxitos van en aviso pasajero; los errores siguen en ventana.
- El aviso pasajero se cierra solo a los 5 s (8 s si tiene botones).
- Los filtros se guardan por pestaña en memoria; se mantienen al refrescar filas, al «⟳ Actualizar» y al cambiar de pestaña; se pierden al cerrar el dashboard.
- `src/core/repositories/obra_planificacion_repository.py` es de la sesión de planificación (dev-ab): avisarle antes de la Tarea 8.

## Estructura de ficheros

| Fichero | Responsabilidad |
|---|---|
| `src/core/budget_filters.py` (nuevo) | `BudgetFilters`, parseo de fechas, filtrar, resumen, valores distintos, etiquetas. Sin Qt. |
| `src/gui/widgets/toast.py` (nuevo) | Aviso pasajero `Toast` y `show_toast()`. |
| `src/gui/widgets/budget_filter_bar.py` (nuevo) | Barra de filtros de una pestaña: buscador embebido, botón Filtros, etiquetas, panel, resumen. |
| `src/gui/budget_dashboard.py` | Integración de filtros, nuevos botones, `_notify`, finalizar, vigilante, mover + deshacer. |
| `src/core/repositories/obra_planificacion_repository.py` | `restore_plan_snapshot()` para deshacer. |
| `tests/test_budget_filters.py`, `tests/test_toast.py`, `tests/test_budget_filter_bar.py`, `tests/test_budget_dashboard_filters.py`, `tests/test_budget_dashboard_toolbar.py`, `tests/test_budget_dashboard_notify.py`, `tests/test_budget_dashboard_move_undo.py` (nuevos) | Tests. |
| `tests/test_gui_late_results.py`, `tests/test_budget_dashboard_open_excel.py`, `tests/test_budget_dashboard_row_refresh.py`, `tests/test_obra_planning_gui.py`, `tests/test_partida_library_gui.py`, `tests/test_regen_header_batch.py` | Ajustes a los nuevos flujos. |

---

### Task 1: Lógica de filtros (`budget_filters.py`)

**Files:**
- Create: `src/core/budget_filters.py`
- Test: `tests/test_budget_filters.py`

**Interfaces:**
- Consumes: `src.utils.budget_utils.normalize_date(value) -> str` (convierte seriales de Excel a `dd-mm-yy`).
- Produces:
  - `BudgetFilters(cliente: str = "", administracion: str = "", fecha_desde: date | None = None, fecha_hasta: date | None = None, importe_min: float | None = None, importe_max: float | None = None)` — dataclass congelada; `.is_empty() -> bool`, `.active_count() -> int`.
  - `parse_budget_date(value) -> date | None`
  - `apply_filters(rows: list[dict], filters: BudgetFilters) -> list[dict]`
  - `summarize(rows: list[dict]) -> tuple[int, float]`
  - `summary_text(count: int, total: float) -> str` → `"12 presupuestos · 84.300 €"`
  - `distinct_values(rows: list[dict], key: str) -> list[str]`
  - `filter_chips(filters: BudgetFilters) -> list[tuple[str, str]]` → `[(campo, etiqueta), …]`
  - `without(filters: BudgetFilters, field: str) -> BudgetFilters`
  - `format_eur(amount: float) -> str` → `"84.300 €"` (sin decimales, punto de miles)

- [ ] **Step 1: Write the failing tests**

```python
"""Lógica pura de los filtros del dashboard (sin Qt)."""

from datetime import date

import pytest

from src.core.budget_filters import (
    BudgetFilters, apply_filters, distinct_values, filter_chips, format_eur,
    parse_budget_date, summarize, summary_text, without,
)


def _row(numero, cliente="", admin="", fecha="", total=None):
    return {"numero": numero, "cliente": cliente, "administracion_nombre": admin,
            "fecha": fecha, "total": total}


@pytest.mark.parametrize("raw,expected", [
    ("16-01-26", date(2026, 1, 16)),
    ("16/01/26", date(2026, 1, 16)),
    ("16-01-2026", date(2026, 1, 16)),
    ("16/01/2026", date(2026, 1, 16)),
    ("2026-01-16", date(2026, 1, 16)),
    ("46038", date(2026, 1, 16)),  # serial de Excel
    (date(2026, 1, 16), date(2026, 1, 16)),
    ("", None),
    (None, None),
    ("enero", None),
    ("32-01-26", None),
])
def test_parse_budget_date(raw, expected):
    assert parse_budget_date(raw) == expected


def test_empty_filters_return_all_rows():
    rows = [_row("1-26"), _row("2-26")]
    assert BudgetFilters().is_empty()
    assert apply_filters(rows, BudgetFilters()) == rows


def test_cliente_matches_normalized_exact():
    rows = [_row("1-26", cliente="CP  Sol 3"), _row("2-26", cliente="CP Sol 31")]
    out = apply_filters(rows, BudgetFilters(cliente="cp sol 3"))
    assert [r["numero"] for r in out] == ["1-26"]


def test_administracion_filter():
    rows = [_row("1-26", admin="Fincas Sol"), _row("2-26", admin="")]
    out = apply_filters(rows, BudgetFilters(administracion="FINCAS SOL"))
    assert [r["numero"] for r in out] == ["1-26"]


def test_date_range_inclusive_and_hides_rows_without_date():
    rows = [
        _row("1-26", fecha="01-01-26"), _row("2-26", fecha="15-01-26"),
        _row("3-26", fecha="31-01-26"), _row("4-26", fecha=""), _row("5-26", fecha="basura"),
    ]
    f = BudgetFilters(fecha_desde=date(2026, 1, 1), fecha_hasta=date(2026, 1, 15))
    assert [r["numero"] for r in apply_filters(rows, f)] == ["1-26", "2-26"]


def test_importe_range_inclusive_and_hides_rows_without_total():
    rows = [_row("1-26", total=1000.0), _row("2-26", total=5000.0),
            _row("3-26", total=None), _row("4-26", total=0.0), _row("5-26", total="x")]
    f = BudgetFilters(importe_min=1000.0, importe_max=5000.0)
    assert [r["numero"] for r in apply_filters(rows, f)] == ["1-26", "2-26"]
    assert [r["numero"] for r in apply_filters(rows, BudgetFilters(importe_max=2000.0))] == ["1-26"]


def test_active_count_counts_zero_amount():
    assert BudgetFilters(importe_min=0.0).active_count() == 1
    assert BudgetFilters(cliente="  ").active_count() == 0
    assert BudgetFilters(cliente="A", fecha_hasta=date(2026, 1, 1)).active_count() == 2


def test_summarize_counts_all_and_sums_only_totals():
    rows = [_row("1", total=1000.0), _row("2", total=None), _row("3", total=250.5)]
    assert summarize(rows) == (3, 1250.5)


def test_summary_text_and_format():
    assert format_eur(84300.4) == "84.300 €"
    assert format_eur(0) == "0 €"
    assert summary_text(12, 84300.0) == "12 presupuestos · 84.300 €"
    assert summary_text(1, 500.0) == "1 presupuesto · 500 €"


def test_distinct_values_dedupes_normalized_and_sorts():
    rows = [_row("1", cliente="Beta"), _row("2", cliente="alfa"), _row("3", cliente="BETA "),
            _row("4", cliente=""), _row("5", cliente=None)]
    assert distinct_values(rows, "cliente") == ["alfa", "Beta"]


def test_chips_and_without():
    f = BudgetFilters(cliente="CP Sol", fecha_desde=date(2026, 1, 1), importe_min=5000.0)
    chips = filter_chips(f)
    assert chips == [
        ("cliente", "Cliente: CP Sol"),
        ("fecha_desde", "desde 01/01/26"),
        ("importe_min", "≥ 5.000 €"),
    ]
    g = without(f, "fecha_desde")
    assert g.fecha_desde is None and g.cliente == "CP Sol"
    assert without(f, "cliente").cliente == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_budget_filters.py`
Expected: FAIL con `ModuleNotFoundError: No module named 'src.core.budget_filters'`.

- [ ] **Step 3: Write the implementation**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_budget_filters.py`
Expected: PASS (todos). Si `46038` no da 16/01/2026, comprobar `EXCEL_EPOCH` en `src/utils/budget_utils.py` y ajustar el serial del test al que da `normalize_date("…") == "16-01-26"`.

- [ ] **Step 5: Commit**

```bash
git add src/core/budget_filters.py tests/test_budget_filters.py
git commit -m "feat(dashboard): lógica de filtros por cliente, administración, fecha e importe"
```

---

### Task 2: Aviso pasajero (`toast.py`)

**Files:**
- Create: `src/gui/widgets/toast.py`
- Test: `tests/test_toast.py`

**Interfaces:**
- Produces:
  - `class Toast(QFrame)`: `.text() -> str`, `.action_labels() -> list[str]`, `.trigger(label: str) -> None`, `.timeout_ms() -> int`.
  - `show_toast(parent: QWidget, text: str, actions: list[tuple[str, Callable[[], None]]] | None = None, timeout_ms: int | None = None) -> Toast`. Un aviso nuevo en la misma ventana cierra el anterior. `timeout_ms=None` → 5000 sin acciones, 8000 con acciones.
  - `current_toast(parent: QWidget) -> Toast | None` (para tests).

- [ ] **Step 1: Write the failing tests**

```python
"""Aviso pasajero: no bloquea, se cierra solo y ejecuta sus acciones."""

import pytest

try:
    from PySide6.QtWidgets import QMainWindow

    from src.gui.widgets.toast import Toast, current_toast, show_toast

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


@pytest.fixture
def window(qapp):
    w = QMainWindow()
    w.resize(600, 400)
    yield w
    w.close()


def test_toast_without_actions_uses_short_timeout(window):
    toast = show_toast(window, "Releídos 3")
    assert isinstance(toast, Toast)
    assert toast.text() == "Releídos 3"
    assert toast.action_labels() == []
    assert toast.timeout_ms() == 5000
    assert current_toast(window) is toast


def test_toast_with_actions_runs_callback_and_closes(window):
    calls = []
    toast = show_toast(window, "3 movidos", actions=[("Deshacer", lambda: calls.append(1))])
    assert toast.timeout_ms() == 8000
    assert toast.action_labels() == ["Deshacer"]
    toast.trigger("Deshacer")
    assert calls == [1]
    assert current_toast(window) is None


def test_new_toast_replaces_previous(window):
    first = show_toast(window, "uno")
    second = show_toast(window, "dos")
    assert current_toast(window) is second
    assert first.isHidden()


def test_explicit_timeout(window):
    assert show_toast(window, "x", timeout_ms=1234).timeout_ms() == 1234
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_toast.py`
Expected: FAIL con `ModuleNotFoundError: No module named 'src.gui.widgets.toast'`.

- [ ] **Step 3: Write the implementation**

```python
"""Aviso pasajero en la parte inferior de una ventana (no bloquea ni roba el foco).

Sustituye a las ventanas de «Éxito»: los errores siguen en QMessageBox.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from src.gui import theme

_ATTR = "_cubiapp_toast"
_SHORT_MS = 5000
_WITH_ACTIONS_MS = 8000
_MARGIN = 16


class Toast(QFrame):
    def __init__(self, parent: QWidget, text: str,
                 actions: Optional[List[Tuple[str, Callable[[], None]]]], timeout_ms: int):
        super().__init__(parent)
        self.setObjectName("cubiToast")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(
            f"#cubiToast {{ background: {theme.BG_DARK}; border-radius: {theme.RADIUS_MD}px; }}"
            f"#cubiToast QLabel {{ color: {theme.TEXT_INVERSE}; background: transparent; }}"
            f"#cubiToast QPushButton {{ color: {theme.ACCENT_LIGHT}; background: transparent;"
            f" border: none; font-weight: bold; padding: 2px 6px; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_LG, theme.SPACE_SM, theme.SPACE_SM, theme.SPACE_SM)
        layout.setSpacing(theme.SPACE_SM)
        self._label = QLabel(text, self)
        self._label.setFont(theme.font_base())
        self._label.setWordWrap(True)
        layout.addWidget(self._label, 1)
        self._actions: dict = {}
        for label, callback in actions or []:
            btn = QPushButton(label, self)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, lb=label: self.trigger(lb))
            layout.addWidget(btn)
            self._actions[label] = callback
        close = QPushButton("×", self)
        close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close.setToolTip("Cerrar")
        close.clicked.connect(self.dismiss)
        layout.addWidget(close)
        self._timeout = timeout_ms
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)

    def text(self) -> str:
        return self._label.text()

    def action_labels(self) -> List[str]:
        return list(self._actions)

    def timeout_ms(self) -> int:
        return self._timeout

    def trigger(self, label: str) -> None:
        callback = self._actions.get(label)
        self.dismiss()
        if callback is not None:
            callback()

    def dismiss(self) -> None:
        self._timer.stop()
        parent = self.parentWidget()
        if parent is not None and getattr(parent, _ATTR, None) is self:
            setattr(parent, _ATTR, None)
        self.hide()
        self.deleteLater()

    def popup(self) -> None:
        parent = self.parentWidget()
        width = min(560, max(280, parent.width() - 2 * _MARGIN))
        self.setFixedWidth(width)
        self.adjustSize()
        self.move((parent.width() - width) // 2, parent.height() - self.height() - _MARGIN)
        self.show()
        self.raise_()
        self._timer.start(self._timeout)


def current_toast(parent: QWidget) -> Optional[Toast]:
    return getattr(parent, _ATTR, None)


def show_toast(parent: QWidget, text: str,
               actions: Optional[List[Tuple[str, Callable[[], None]]]] = None,
               timeout_ms: Optional[int] = None) -> Toast:
    previous = current_toast(parent)
    if previous is not None:
        previous.dismiss()
    if timeout_ms is None:
        timeout_ms = _WITH_ACTIONS_MS if actions else _SHORT_MS
    toast = Toast(parent, text, actions, timeout_ms)
    setattr(parent, _ATTR, toast)
    toast.popup()
    return toast
```

Nota: `dismiss()` llama a `deleteLater()`; en el test `first.isHidden()` se evalúa antes de procesar eventos, así que el objeto sigue vivo.

- [ ] **Step 4: Run tests to verify they pass**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_toast.py`
Expected: PASS (4).

- [ ] **Step 5: Commit**

```bash
git add src/gui/widgets/toast.py tests/test_toast.py
git commit -m "feat(gui): aviso pasajero con acciones que sustituye a las ventanas de éxito"
```

---

### Task 3: Barra de filtros (`budget_filter_bar.py`)

**Files:**
- Create: `src/gui/widgets/budget_filter_bar.py`
- Test: `tests/test_budget_filter_bar.py`

**Interfaces:**
- Consumes (Task 1): `BudgetFilters`, `filter_chips`, `without`, `summary_text`.
- Produces: `class BudgetFilterBar(QWidget)`:
  - `__init__(parent, leading: QWidget | None = None)` — `leading` (el buscador) se coloca a la izquierda de la primera fila.
  - Señales: `filters_changed = Signal(object)` (emite `BudgetFilters`), `expanded_changed = Signal(bool)`.
  - `filters() -> BudgetFilters`, `set_filters(f: BudgetFilters) -> None` (no emite).
  - `set_options(clientes: list[str], administraciones: list[str]) -> None` (no emite; conserva el texto elegido).
  - `set_summary(count: int, total: float) -> None`, `summary() -> str`.
  - `set_expanded(bool) -> None`, `is_expanded() -> bool`.
  - `toggle_button() -> QPushButton` (texto «Filtros» o «Filtros (N)»), `chip_labels() -> list[str]`, `remove_chip(field: str) -> None`, `clear() -> None` (emite).
  - Atributos para tests: `_cliente` y `_admin` (QComboBox editables), `_desde_chk`/`_desde` y `_hasta_chk`/`_hasta` (QCheckBox + QDateEdit), `_min`/`_max` (QLineEdit), `_clear_btn`.

- [ ] **Step 1: Write the failing tests**

```python
"""Barra de filtros de una pestaña del dashboard."""

from datetime import date

import pytest

try:
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QLineEdit

    from src.core.budget_filters import BudgetFilters
    from src.gui.widgets.budget_filter_bar import BudgetFilterBar

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


@pytest.fixture
def bar(qapp):
    b = BudgetFilterBar(None, leading=QLineEdit())
    emitted = []
    b.filters_changed.connect(emitted.append)
    b.set_options(["CP Luna", "CP Sol"], [])
    yield b, emitted
    b.deleteLater()


def test_starts_collapsed_and_empty(bar):
    b, _ = bar
    assert not b.is_expanded()
    assert b.filters() == BudgetFilters()
    assert b.toggle_button().text() == "Filtros"
    assert b.chip_labels() == []


def test_toggle_button_expands_and_emits_expanded(bar):
    b, _ = bar
    seen = []
    b.expanded_changed.connect(seen.append)
    b.toggle_button().click()
    assert b.is_expanded() and seen == [True]


def test_choosing_cliente_emits_and_shows_chip(bar):
    b, emitted = bar
    b._cliente.setCurrentText("CP Sol")
    assert emitted[-1] == BudgetFilters(cliente="CP Sol")
    assert b.chip_labels() == ["Cliente: CP Sol"]
    assert b.toggle_button().text() == "Filtros (1)"


def test_partial_cliente_text_does_not_emit(bar):
    b, emitted = bar
    b._cliente.setCurrentText("CP S")
    assert emitted == []


def test_admin_combo_disabled_without_options(bar):
    b, _ = bar
    assert not b._admin.isEnabled()
    b.set_options(["CP Sol"], ["Fincas Sol"])
    assert b._admin.isEnabled()


def test_dates_and_amounts(bar):
    b, emitted = bar
    b._desde.setDate(QDate(2026, 1, 1))
    b._desde_chk.setChecked(True)
    b._min.setText("5000")
    b._min.editingFinished.emit()
    assert emitted[-1] == BudgetFilters(fecha_desde=date(2026, 1, 1), importe_min=5000.0)


def test_amount_accepts_spanish_format(bar):
    b, emitted = bar
    b._max.setText("12.500,50")
    b._max.editingFinished.emit()
    assert emitted[-1].importe_max == 12500.5


def test_remove_chip_and_clear(bar):
    b, emitted = bar
    b.set_filters(BudgetFilters(cliente="CP Sol", importe_min=10.0))
    b.remove_chip("cliente")
    assert emitted[-1] == BudgetFilters(importe_min=10.0)
    b.clear()
    assert emitted[-1] == BudgetFilters()
    assert b.chip_labels() == []


def test_set_filters_does_not_emit_and_keeps_unknown_cliente(bar):
    b, emitted = bar
    b.set_filters(BudgetFilters(cliente="Ya no existe"))
    b.set_options(["CP Sol"], [])
    assert emitted == []
    assert b.filters().cliente == "Ya no existe"


def test_summary(bar):
    b, _ = bar
    b.set_summary(12, 84300.0)
    assert b.summary() == "12 presupuestos · 84.300 €"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_budget_filter_bar.py`
Expected: FAIL con `ModuleNotFoundError: No module named 'src.gui.widgets.budget_filter_bar'`.

- [ ] **Step 3: Write the implementation**

```python
"""Barra de filtros de una pestaña de «Presupuestos existentes».

Fila 1: buscador (leading) · botón «Filtros (N)» · resumen.
Fila 2: etiquetas de los filtros activos (× para quitar) · «Limpiar filtros».
Fila 3 (plegable): cliente, administración, fechas e importes.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QCompleter, QDateEdit, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from src.core.budget_filters import BudgetFilters, filter_chips, summary_text, without
from src.gui import theme


def _norm(text: str) -> str:
    return " ".join((text or "").split()).casefold()


def _parse_amount(text: str) -> Optional[float]:
    raw = (text or "").strip().replace("€", "").replace(" ", "")
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


class BudgetFilterBar(QWidget):
    filters_changed = Signal(object)
    expanded_changed = Signal(bool)

    def __init__(self, parent=None, leading: Optional[QWidget] = None):
        super().__init__(parent)
        self._options = {"cliente": set(), "admin": set()}
        self._chip_buttons: List[QPushButton] = []
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(theme.SPACE_XS)

        top = QHBoxLayout()
        if leading is not None:
            top.addWidget(leading, 1)
        self._toggle = QPushButton("Filtros", self)
        self._toggle.setCheckable(True)
        self._toggle.setFont(theme.font_base())
        self._toggle.setToolTip("Filtrar por cliente, administración, fecha o importe")
        self._toggle.toggled.connect(self._on_toggled)
        top.addWidget(self._toggle)
        self._summary = theme.create_text(self, "", muted=True)
        top.addWidget(self._summary)
        root.addLayout(top)

        self._chips_row = QWidget(self)
        self._chips_layout = QHBoxLayout(self._chips_row)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.addStretch()
        self._clear_btn = QPushButton("Limpiar filtros", self._chips_row)
        self._clear_btn.setFlat(True)
        self._clear_btn.clicked.connect(self.clear)
        self._chips_layout.addWidget(self._clear_btn)
        self._chips_row.setVisible(False)
        root.addWidget(self._chips_row)

        self._panel = QWidget(self)
        panel = QHBoxLayout(self._panel)
        panel.setContentsMargins(0, 0, 0, 0)
        self._cliente = self._make_combo("Todos los clientes")
        self._admin = self._make_combo("Todas las administraciones")
        panel.addWidget(QLabel("Cliente", self._panel))
        panel.addWidget(self._cliente, 2)
        panel.addWidget(QLabel("Administración", self._panel))
        panel.addWidget(self._admin, 2)
        self._desde_chk, self._desde = self._make_date("Desde")
        self._hasta_chk, self._hasta = self._make_date("Hasta")
        for w in (self._desde_chk, self._desde, self._hasta_chk, self._hasta):
            panel.addWidget(w)
        panel.addWidget(QLabel("Importe", self._panel))
        self._min = self._make_amount("mín. €")
        self._max = self._make_amount("máx. €")
        panel.addWidget(self._min)
        panel.addWidget(QLabel("–", self._panel))
        panel.addWidget(self._max)
        self._panel.setVisible(False)
        root.addWidget(self._panel)

        self._refresh_admin_enabled()

    # ── construcción ────────────────────────────────────────────────
    def _make_combo(self, placeholder: str) -> QComboBox:
        combo = QComboBox(self._panel)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.lineEdit().setPlaceholderText(placeholder)
        combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        combo.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        combo.currentTextChanged.connect(self._on_combo_text)
        return combo

    def _make_date(self, label: str):
        chk = QCheckBox(label, self._panel)
        edit = QDateEdit(self._panel)
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("dd/MM/yy")
        edit.setDate(QDate.currentDate())
        edit.setEnabled(False)
        chk.toggled.connect(edit.setEnabled)
        chk.toggled.connect(lambda _=False: self._emit())
        edit.dateChanged.connect(lambda _=None, c=chk: c.isChecked() and self._emit())
        return chk, edit

    def _make_amount(self, placeholder: str) -> QLineEdit:
        edit = QLineEdit(self._panel)
        edit.setPlaceholderText(placeholder)
        edit.setMaximumWidth(110)
        edit.editingFinished.connect(self._emit)
        return edit

    # ── API ─────────────────────────────────────────────────────────
    def toggle_button(self) -> QPushButton:
        return self._toggle

    def is_expanded(self) -> bool:
        return self._toggle.isChecked()

    def set_expanded(self, expanded: bool) -> None:
        self._toggle.setChecked(bool(expanded))

    def summary(self) -> str:
        return self._summary.text()

    def set_summary(self, count: int, total: float) -> None:
        self._summary.setText(summary_text(count, total))

    def chip_labels(self) -> List[str]:
        return [b.property("chip_label") for b in self._chip_buttons]

    def filters(self) -> BudgetFilters:
        def _date(chk, edit) -> Optional[date]:
            return edit.date().toPython() if chk.isChecked() else None

        return BudgetFilters(
            cliente=self._cliente.currentText().strip(),
            administracion=self._admin.currentText().strip(),
            fecha_desde=_date(self._desde_chk, self._desde),
            fecha_hasta=_date(self._hasta_chk, self._hasta),
            importe_min=_parse_amount(self._min.text()),
            importe_max=_parse_amount(self._max.text()),
        )

    def set_filters(self, f: BudgetFilters) -> None:
        self._loading = True
        try:
            self._cliente.setCurrentText(f.cliente)
            self._admin.setCurrentText(f.administracion)
            for chk, edit, value in ((self._desde_chk, self._desde, f.fecha_desde),
                                     (self._hasta_chk, self._hasta, f.fecha_hasta)):
                chk.setChecked(value is not None)
                if value is not None:
                    edit.setDate(QDate(value.year, value.month, value.day))
            self._min.setText("" if f.importe_min is None else f"{f.importe_min:g}")
            self._max.setText("" if f.importe_max is None else f"{f.importe_max:g}")
        finally:
            self._loading = False
        self._refresh_chips(f)
        self._refresh_admin_enabled()

    def set_options(self, clientes: List[str], administraciones: List[str]) -> None:
        self._loading = True
        try:
            for combo, key, values in ((self._cliente, "cliente", clientes),
                                       (self._admin, "admin", administraciones)):
                current = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(list(values))
                combo.setCurrentText(current)
                combo.blockSignals(False)
                self._options[key] = {_norm(v) for v in values}
        finally:
            self._loading = False
        self._refresh_admin_enabled()

    def remove_chip(self, field: str) -> None:
        self.set_filters(without(self.filters(), field))
        self._emit()

    def clear(self) -> None:
        self.set_filters(BudgetFilters())
        self._emit()

    # ── internos ────────────────────────────────────────────────────
    def _on_toggled(self, checked: bool) -> None:
        self._panel.setVisible(checked)
        self.expanded_changed.emit(checked)

    def _on_combo_text(self, text: str) -> None:
        if self._loading:
            return
        key = "cliente" if self.sender() is self._cliente else "admin"
        # Mientras se teclea un nombre a medias no se filtra (dejaría la tabla vacía).
        if not text.strip() or _norm(text) in self._options[key]:
            self._emit()

    def _emit(self) -> None:
        if self._loading:
            return
        f = self.filters()
        self._refresh_chips(f)
        self.filters_changed.emit(f)

    def _refresh_admin_enabled(self) -> None:
        has = bool(self._options["admin"]) or bool(self._admin.currentText().strip())
        self._admin.setEnabled(has)
        self._admin.setToolTip("" if has else "No hay administraciones en estos presupuestos")

    def _refresh_chips(self, f: BudgetFilters) -> None:
        for btn in self._chip_buttons:
            self._chips_layout.removeWidget(btn)
            btn.deleteLater()
        self._chip_buttons = []
        for i, (field, label) in enumerate(filter_chips(f)):
            btn = QPushButton(f"{label}  ×", self._chips_row)
            btn.setProperty("chip_label", label)
            btn.setToolTip("Quitar este filtro")
            btn.clicked.connect(lambda _=False, fl=field: self.remove_chip(fl))
            self._chips_layout.insertWidget(i, btn)
            self._chip_buttons.append(btn)
        count = f.active_count()
        self._toggle.setText(f"Filtros ({count})" if count else "Filtros")
        self._chips_row.setVisible(count > 0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_budget_filter_bar.py`
Expected: PASS (10).

- [ ] **Step 5: Commit**

```bash
git add src/gui/widgets/budget_filter_bar.py tests/test_budget_filter_bar.py
git commit -m "feat(dashboard): barra de filtros plegable con etiquetas y resumen"
```

---

### Task 4: Filtros en el dashboard

**Files:**
- Modify: `src/gui/budget_dashboard.py` (`__init__` ~197; `_rebuild_tabs` ~562; `_show_no_results_row` ~817; `_show_empty_state` ~826; `_create_search_box` ~856; `_filter_rows` ~879; `_populate_table` ~902; `_get_row_data` ~1355)
- Test: `tests/test_budget_dashboard_filters.py`

**Interfaces:**
- Consumes: Task 1 (`BudgetFilters`, `apply_filters`, `summarize`, `distinct_values`), Task 3 (`BudgetFilterBar`).
- Produces (dashboard): `_tab_filters: dict[str, BudgetFilters]`, `_tab_filter_bars: dict[str, BudgetFilterBar]`, `_filters_expanded: dict[str, bool]`, `_visible_rows(state_name) -> list[dict]`, `_on_filters_changed(state_name, filters) -> None`.

- [ ] **Step 1: Write the failing tests**

```python
"""Filtros por pestaña en «Presupuestos existentes»."""

import os

import pytest

try:
    from src.core import folder_scanner
    from src.core.budget_filters import BudgetFilters
    from src.core.settings import Settings
    from src.gui import budget_dashboard as bd
    from src.gui.budget_dashboard import BudgetDashboardFrame

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")

A, B = "PRESUPUESTADO", "EJECUTAR"


def _row(numero, cliente, total, ruta, fecha="10-01-26"):
    return {
        "numero": numero, "nombre_proyecto": f"{numero} obra", "cliente": cliente,
        "administracion_nombre": "", "direccion": "", "localidad": "", "tipo_obra": "",
        "fecha": fecha, "subtotal": 0.0, "iva": 0.0, "total": total, "fuente_datos": "scan",
        "es_finalizado": False, "calidad_datos": 100, "datos_completos": True,
        "ruta_excel": ruta, "ruta_carpeta": os.path.dirname(ruta),
    }


@pytest.fixture
def dash(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(Settings, "get_default_path", lambda self, key: "")
    monkeypatch.setattr(bd, "cleanup_orphaned_cache", lambda *a, **k: None)
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    monkeypatch.setattr(bd, "resolve_projects", lambda scanned, index, state: scanned)
    monkeypatch.setattr(bd, "enrich_with_planning", lambda *a, **k: set())
    rows = {
        A: [_row("1-26", "CP Sol", 1000.0, str(tmp_path / "1.xlsx")),
            _row("2-26", "CP Luna", 3000.0, str(tmp_path / "2.xlsx")),
            _row("3-26", "CP Sol", None, str(tmp_path / "3.xlsx"))],
        B: [_row("4-26", "CP Mar", 500.0, str(tmp_path / "4.xlsx"))],
    }
    monkeypatch.setattr(
        folder_scanner, "scan_projects", lambda d: list(rows[os.path.basename(d)])
    )
    frame = BudgetDashboardFrame()
    frame._rebuild_tabs([A, B], str(tmp_path))
    yield frame
    frame.close()


def _numeros(frame, state):
    table = frame._tab_tables[state]
    return sorted(table.item(r, 0).text() for r in range(table.rowCount()))


def test_each_tab_has_a_filter_bar_with_summary(dash):
    assert set(dash._tab_filter_bars) == {A, B}
    assert dash._tab_filter_bars[A].summary() == "3 presupuestos · 4.000 €"


def test_filter_applies_only_to_its_tab(dash):
    dash._on_filters_changed(A, BudgetFilters(cliente="CP Sol"))
    assert _numeros(dash, A) == ["1-26", "3-26"]
    assert _numeros(dash, B) == ["4-26"]
    assert dash._tab_filter_bars[A].summary() == "2 presupuestos · 1.000 €"


def test_filters_combine_with_text_search(dash):
    dash._on_filters_changed(A, BudgetFilters(cliente="CP Sol"))
    dash._tab_searches[A].setText("3-26")
    assert _numeros(dash, A) == ["3-26"]


def test_row_data_matches_filtered_rows(dash):
    dash._on_filters_changed(A, BudgetFilters(importe_min=2000.0))
    assert dash._get_row_data(A, 0)["numero"] == "2-26"


def test_filters_survive_rebuild(dash, tmp_path):
    dash._on_filters_changed(A, BudgetFilters(cliente="CP Luna"))
    dash._rebuild_tabs([A, B], str(tmp_path))
    assert _numeros(dash, A) == ["2-26"]
    assert dash._tab_filter_bars[A].filters() == BudgetFilters(cliente="CP Luna")


def test_options_come_from_tab_rows(dash):
    bar = dash._tab_filter_bars[A]
    assert [bar._cliente.itemText(i) for i in range(bar._cliente.count())] == ["CP Luna", "CP Sol"]
    assert not bar._admin.isEnabled()


def test_empty_result_shows_filter_message(dash):
    dash._on_filters_changed(A, BudgetFilters(importe_min=99999.0))
    table = dash._tab_tables[A]
    assert table.rowCount() == 1
    assert "Ningún presupuesto cumple los filtros" in table.item(0, 0).text()


def test_explorer_mode_has_no_filter_bar(dash, tmp_path, monkeypatch):
    monkeypatch.setattr(folder_scanner, "scan_explorer", lambda d: [])
    dash._explorer_mode = True
    dash._rebuild_tabs([A, B], str(tmp_path))
    assert dash._tab_filter_bars == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_budget_dashboard_filters.py`
Expected: FAIL con `AttributeError: 'BudgetDashboardFrame' object has no attribute '_tab_filter_bars'`.

- [ ] **Step 3: Implement**

3a. Imports (junto a los de `src.core`):

```python
from src.core.budget_filters import BudgetFilters, apply_filters, distinct_values, summarize
from src.gui.widgets.budget_filter_bar import BudgetFilterBar
```

3b. En `__init__`, tras `self._tab_searches: dict[str, QLineEdit] = {}`:

```python
        # Filtros por pestaña: sobreviven a las recargas; se pierden al cerrar.
        self._tab_filters: dict[str, BudgetFilters] = {}
        self._tab_filter_bars: dict[str, BudgetFilterBar] = {}
        self._filters_expanded: dict[str, bool] = {}
```

3c. En `_rebuild_tabs` y en `_show_empty_state`, junto a `self._tab_searches.clear()`, añadir `self._tab_filter_bars.clear()`.

3d. En `_rebuild_tabs`, sustituir

```python
            search_widget, search_ctrl = self._create_search_box(tab_widget, state_name)
            tab_layout.addWidget(search_widget)
            self._tab_searches[state_name] = search_ctrl
```

por

```python
            search_widget, search_ctrl = self._create_search_box(tab_widget, state_name)
            self._tab_searches[state_name] = search_ctrl
            if self._explorer_mode:
                tab_layout.addWidget(search_widget)
            else:
                bar = BudgetFilterBar(tab_widget, leading=search_widget)
                bar.set_filters(self._tab_filters.get(state_name, BudgetFilters()))
                bar.set_expanded(self._filters_expanded.get(state_name, False))
                bar.filters_changed.connect(
                    lambda f, sn=state_name: self._on_filters_changed(sn, f)
                )
                bar.expanded_changed.connect(
                    lambda on, sn=state_name: self._filters_expanded.__setitem__(sn, on)
                )
                tab_layout.addWidget(bar)
                self._tab_filter_bars[state_name] = bar
```

3e. Añadir tras `_filter_rows`:

```python
    def _visible_rows(self, state_name):
        """Filas que muestra la pestaña: búsqueda de texto + filtros (en ese orden)."""
        rows = self._tab_data.get(state_name, [])
        search_ctrl = self._tab_searches.get(state_name)
        query = search_ctrl.text() if search_ctrl else ""
        if self._explorer_mode:
            return self._filter_explorer_rows(rows, query)
        filtered = self._filter_rows(rows, query)
        return apply_filters(filtered, self._tab_filters.get(state_name, BudgetFilters()))

    def _on_filters_changed(self, state_name, filters):
        self._tab_filters[state_name] = filters
        selected = self._selected_rutas(state_name)
        self._populate_table(state_name)
        self._reselect_rutas(state_name, selected)
```

3f. `_get_row_data`: sustituir desde `rows = self._tab_data.get(state_name, [])` hasta `filtered = self._filter_rows(rows, query)` (incluido el `if/else`) por:

```python
        filtered = self._visible_rows(state_name)
```

3g. `_show_no_results_row(self, table, query)` pasa a recibir el mensaje completo:

```python
    def _show_no_results_row(self, table, message):
        """Si no hay filas que mostrar, muestra un aviso en vez de dejar la tabla en blanco."""
        table.setRowCount(1)
        table.setSpan(0, 0, 1, table.columnCount())
        item = QTableWidgetItem(message)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(0, 0, item)
```

y en `_populate_explorer_table` la llamada pasa a
`self._show_no_results_row(table, f"Sin resultados para «{query.strip()}» · Borra el texto de búsqueda para ver todo")`.

3h. En `_populate_table`, sustituir

```python
        rows = self._tab_data.get(state_name, [])
        search_ctrl = self._tab_searches.get(state_name)
        query = search_ctrl.text() if search_ctrl else ""
        filtered = self._filter_rows(rows, query)

        if not filtered and rows and query.strip():
            self._show_no_results_row(table, query)
            table.setSortingEnabled(True)
            self._update_buttons()
            return
```

por

```python
        rows = self._tab_data.get(state_name, [])
        search_ctrl = self._tab_searches.get(state_name)
        query = search_ctrl.text() if search_ctrl else ""
        filters = self._tab_filters.get(state_name, BudgetFilters())
        filtered = self._visible_rows(state_name)

        bar = self._tab_filter_bars.get(state_name)
        if bar is not None:
            bar.set_options(distinct_values(rows, "cliente"),
                            distinct_values(rows, "administracion_nombre"))
            bar.set_summary(*summarize(filtered))

        if not filtered and rows and (query.strip() or not filters.is_empty()):
            if not filters.is_empty():
                message = "Ningún presupuesto cumple los filtros · Pulsa «Limpiar filtros»"
            else:
                message = f"Sin resultados para «{query.strip()}» · Borra el texto de búsqueda para ver todo"
            self._show_no_results_row(table, message)
            table.setSortingEnabled(True)
            self._update_buttons()
            return
```

- [ ] **Step 4: Run the new and the existing dashboard tests**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_budget_dashboard_filters.py tests/test_budget_dashboard_search_selection.py tests/test_budget_dashboard_row_refresh.py tests/test_obra_planning_gui.py`
Expected: PASS. Si `test_budget_dashboard_search_selection.py` comprueba el texto «Sin resultados para…», debe seguir pasando sin cambios.

- [ ] **Step 5: Commit**

```bash
git add src/gui/budget_dashboard.py tests/test_budget_dashboard_filters.py
git commit -m "feat(dashboard): filtros por pestaña combinados con el buscador"
```

---

### Task 5: Botones nuevos, menú Columnas, Finalizar y atajos

**Files:**
- Modify: `src/gui/budget_dashboard.py` (`_build_ui` ~236-320; `_on_toggle_mode` ~332; `_on_toggle_extra_columns`/`_on_reset_columns` ~353-380; `_set_toolbar_enabled` ~538; `_on_context_menu` ~1163; `_update_buttons` ~1415; `_on_edit_menu` ~1523; `_on_open_menu` ~1654; `_on_export_pdf` ~1614)
- Test: `tests/test_budget_dashboard_toolbar.py`

**Interfaces:**
- Consumes: Task 2 (`show_toast`).
- Produces (dashboard):
  - Botones `_btn_columns`, `_btn_open_excel`, `_btn_open_folder`, `_btn_edit`, `_btn_reread`. Desaparecen `_btn_toggle_extra`, `_btn_reset_columns`, `_btn_open`, `_btn_regen_fields`, `_btn_refresh_selected` y `_on_open_menu`.
  - `_set_extra_columns(visible: bool) -> None`, `_build_columns_menu() -> QMenu`, `_build_edit_menu(parent) -> QMenu`.
  - `_notify(text: str, actions: list[tuple[str, Callable]] | None = None) -> None` — envuelve `show_toast`; si la ventana no está inicializada (tests con `__new__`) solo registra en el log.
  - `_on_finalize() -> None` y `_finalize_ruta(ruta: str, estado: str) -> None` (en segundo plano; éxito → `_refresh_rows([ruta])` + aviso «Presupuesto finalizado»; fallo → `QMessageBox.warning(self, "Finalizar presupuesto", "No se pudo finalizar el presupuesto con los datos del Excel.")`).
  - `_on_enter_shortcut() -> None`, `_focus_search() -> None`.

- [ ] **Step 1: Write the failing tests**

```python
"""Barra de botones de «Presupuestos existentes»: menos botones y directos."""

import os

import pytest

try:
    from src.core import folder_scanner, services
    from src.core.settings import Settings
    from src.gui import budget_dashboard as bd
    from src.gui.budget_dashboard import BudgetDashboardFrame
    from src.gui.widgets.toast import current_toast

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")

STATE = "PRESUPUESTADO"


def _row(numero, ruta):
    return {
        "numero": numero, "nombre_proyecto": f"{numero} obra", "cliente": "C",
        "administracion_nombre": "", "direccion": "", "localidad": "", "tipo_obra": "",
        "fecha": "", "subtotal": 0.0, "iva": 0.0, "total": 0.0, "fuente_datos": "scan",
        "es_finalizado": False, "calidad_datos": 100, "datos_completos": True,
        "ruta_excel": ruta, "ruta_carpeta": os.path.dirname(ruta),
    }


@pytest.fixture
def dash(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(Settings, "get_default_path", lambda self, key: "")
    monkeypatch.setattr(bd, "cleanup_orphaned_cache", lambda *a, **k: None)
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    monkeypatch.setattr(bd, "resolve_projects", lambda scanned, index, state: scanned)
    ruta = os.path.normpath(str(tmp_path / "1-26.xlsx"))
    open(ruta, "wb").close()
    monkeypatch.setattr(folder_scanner, "scan_projects", lambda d: [_row("1-26", ruta)])
    frame = BudgetDashboardFrame()
    frame._rebuild_tabs([STATE], str(tmp_path))
    yield frame, ruta
    frame.close()


def test_toolbar_buttons(dash):
    frame, _ = dash
    texts = [b.text() for b in (frame._btn_open_excel, frame._btn_open_folder,
                                frame._btn_edit, frame._btn_reread)]
    assert texts == ["Abrir Excel", "Abrir carpeta", "Editar ▼", "Releer del Excel"]
    for gone in ("_btn_toggle_extra", "_btn_reset_columns", "_btn_open",
                 "_btn_regen_fields", "_btn_refresh_selected"):
        assert not hasattr(frame, gone)


def test_buttons_disabled_without_selection_explain_why(dash):
    frame, _ = dash
    frame._tab_tables[STATE].clearSelection()
    frame._tab_tables[STATE].setCurrentCell(-1, -1)
    frame._update_buttons()
    assert not frame._btn_open_excel.isEnabled()
    assert frame._btn_open_excel.toolTip() == "Selecciona un presupuesto"


def test_buttons_enabled_with_selection(dash):
    frame, _ = dash
    frame._tab_tables[STATE].selectRow(0)
    frame._update_buttons()
    assert all(b.isEnabled() for b in (frame._btn_open_excel, frame._btn_open_folder,
                                       frame._btn_edit, frame._btn_reread))


def test_columns_menu_toggles_extra_and_restores(dash):
    frame, _ = dash
    table = frame._tab_tables[STATE]
    menu = frame._build_columns_menu()
    labels = [a.text() for a in menu.actions() if a.text()]
    assert "Datos extra (Origen, Finalizado, Calidad)" in labels
    assert "Restaurar columnas" in labels
    extra = next(a for a in menu.actions() if a.text().startswith("Datos extra"))
    extra.trigger()
    assert table.isColumnHidden(10) and table.isColumnHidden(12)
    table.setColumnHidden(2, True)
    restore = next(a for a in frame._build_columns_menu().actions() if a.text() == "Restaurar columnas")
    restore.trigger()
    assert not table.isColumnHidden(2) and not table.isColumnHidden(10)


def test_columns_menu_hides_a_single_column(dash):
    frame, _ = dash
    table = frame._tab_tables[STATE]
    menu = frame._build_columns_menu()
    cliente = next(a for a in menu.actions() if a.text() == "Cliente")
    assert cliente.isCheckable() and cliente.isChecked()
    cliente.trigger()
    assert table.isColumnHidden(2)


def test_edit_menu_has_regenerate_and_finalize(dash):
    frame, _ = dash
    frame._tab_tables[STATE].selectRow(0)
    labels = [a.text() for a in frame._build_edit_menu(frame).actions() if a.text()]
    assert labels == [
        "Regenerar campos", "Finalizar",
        "Regenerar todas las partidas (IA)", "Añadir más partidas (IA)",
        "Añadir partidas desde la biblioteca", "Exportar PDF",
    ]


def test_finalize_refreshes_row_and_notifies(monkeypatch, dash):
    frame, ruta = dash
    frame._tab_tables[STATE].selectRow(0)
    calls = []

    class _FakeService:
        def finalize_budget(self, r, estado=""):
            calls.append((r, estado))
            return True

    monkeypatch.setattr(services, "BudgetService", _FakeService)
    refreshed = []
    monkeypatch.setattr(frame, "_refresh_rows", lambda rutas, on_done=None: refreshed.append(list(rutas)))

    frame._on_finalize()

    assert calls == [(ruta, STATE)]
    assert refreshed == [[ruta]]
    assert current_toast(frame).text() == "Presupuesto finalizado: 1-26.xlsx"


def test_notify_survives_uninitialised_window():
    half = BudgetDashboardFrame.__new__(BudgetDashboardFrame)
    half._notify("hola")  # no lanza


def test_enter_opens_excel_unless_typing(monkeypatch, dash):
    frame, _ = dash
    opened = []
    monkeypatch.setattr(frame, "_on_open_excel", lambda: opened.append(1))
    monkeypatch.setattr(bd.QApplication, "focusWidget", staticmethod(lambda: frame._tab_tables[STATE]))
    frame._on_enter_shortcut()
    monkeypatch.setattr(bd.QApplication, "focusWidget", staticmethod(lambda: frame._tab_searches[STATE]))
    frame._on_enter_shortcut()
    assert opened == [1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_budget_dashboard_toolbar.py`
Expected: FAIL con `AttributeError: … '_btn_open_excel'`.

- [ ] **Step 3: Implement**

3a. Imports: añadir `QKeySequence, QShortcut` a `from PySide6.QtGui import QColor` → `from PySide6.QtGui import QColor, QKeySequence, QShortcut`, y `from src.gui.widgets.toast import show_toast`.

3b. Cabecera en `_build_ui`: sustituir los bloques de `self._btn_toggle_extra` y `self._btn_reset_columns` por:

```python
        self._btn_columns = QPushButton("Columnas ▼", header)
        self._btn_columns.setFont(theme.font_base())
        self._btn_columns.setFixedHeight(36)
        self._btn_columns.setToolTip("Mostrar u ocultar columnas")
        self._btn_columns.clicked.connect(
            lambda: self._build_columns_menu().exec(
                self._btn_columns.mapToGlobal(self._btn_columns.rect().bottomLeft())
            )
        )
        top_row.addWidget(self._btn_columns)
```

y en `btn_refresh` cambiar el tooltip a `"Recargar todas las carpetas (F5)"`.

3c. Barra inferior en `_build_ui`: sustituir desde `self._btn_open = self._tb_button(...)` hasta `tb_layout.addStretch()` por:

```python
        self._btn_open_excel = self._tb_button(toolbar, "Abrir Excel", self._on_open_excel, primary=True)
        self._btn_open_folder = self._tb_button(toolbar, "Abrir carpeta", self._on_open_folder)
        self._btn_edit = self._tb_button(toolbar, "Editar ▼", self._on_edit_menu)
        self._btn_reread = self._tb_button(toolbar, "Releer del Excel", self._on_refresh_selected)

        for btn in (self._btn_open_excel, self._btn_open_folder, self._btn_edit, self._btn_reread):
            tb_layout.addWidget(btn)
        tb_layout.addStretch()
```

y al final de `_build_ui`, antes de `self._update_buttons()`:

```python
        QShortcut(QKeySequence(Qt.Key.Key_Return), self, self._on_enter_shortcut)
        QShortcut(QKeySequence(Qt.Key.Key_Enter), self, self._on_enter_shortcut)
        QShortcut(QKeySequence.StandardKey.Find, self, self._focus_search)
        QShortcut(QKeySequence(Qt.Key.Key_F5), self, self._load_data)
```

3d. `_on_toggle_mode`: sustituir las líneas `self._btn_toggle_extra.setEnabled(...)` / `self._btn_reset_columns.setEnabled(...)` por `self._btn_columns.setEnabled(False)` (modo explorador) y `self._btn_columns.setEnabled(True)` (modo Excel).

3e. Sustituir `_on_toggle_extra_columns` y `_on_reset_columns` por:

```python
    def _set_extra_columns(self, visible: bool):
        self._show_extra_columns = bool(visible)
        for state_name, table in self._tab_tables.items():
            if not self._explorer_mode and state_name in self._state_names:
                self._apply_extra_columns_visibility(table)

    def _on_reset_columns(self):
        """Restaura columnas visibles del dashboard en todas las pestañas."""
        self._show_extra_columns = True
        for state_name, table in self._tab_tables.items():
            if self._explorer_mode or state_name not in self._state_names:
                continue
            for idx in range(table.columnCount()):
                table.setColumnHidden(idx, False)
            self._apply_extra_columns_visibility(table)

    def _build_columns_menu(self) -> QMenu:
        """Una casilla por columna de la pestaña actual, datos extra y restaurar."""
        menu = QMenu(self)
        table = self._tab_tables.get(self._current_state() or "")
        if table is not None and not self._explorer_mode:
            for col in range(table.columnCount()):
                if col in (10, 11, 12):
                    continue  # las gobierna «Datos extra»
                header = table.horizontalHeaderItem(col)
                act = menu.addAction(header.text() if header else f"Columna {col + 1}")
                act.setCheckable(True)
                act.setChecked(not table.isColumnHidden(col))
                act.toggled.connect(lambda on, c=col, t=table: t.setColumnHidden(c, not on))
            menu.addSeparator()
        extra = menu.addAction("Datos extra (Origen, Finalizado, Calidad)")
        extra.setCheckable(True)
        extra.setChecked(self._show_extra_columns)
        extra.toggled.connect(self._set_extra_columns)
        menu.addSeparator()
        menu.addAction("Restaurar columnas").triggered.connect(self._on_reset_columns)
        return menu
```

3f. `_set_toolbar_enabled`:

```python
    def _set_toolbar_enabled(self, enabled):
        for btn in (self._btn_open_excel, self._btn_open_folder, self._btn_edit, self._btn_reread):
            btn.setEnabled(enabled)
```

3g. `_update_buttons`: sustituir desde `for btn in (self._btn_edit, self._btn_regen_fields,` hasta el final del método por:

```python
        def _state(btn, enabled, reason, tip):
            btn.setEnabled(enabled)
            btn.setToolTip(tip if enabled else reason)

        no_sel = "Selecciona un presupuesto"
        _state(self._btn_open_excel, has_excel_any, no_sel if not has_sel else "El Excel no existe",
               "Abrir el Excel (Intro)")
        _state(self._btn_open_folder, has_folder_any, no_sel if not has_sel else "La carpeta no existe",
               "Abrir la carpeta del proyecto")
        _state(self._btn_edit, file_ok, no_sel if not has_sel else "El Excel no existe",
               "Regenerar campos, finalizar, partidas y PDF")
        if self._explorer_mode:
            _state(self._btn_reread, False, "Disponible en la vista de presupuestos", "")
        else:
            _state(self._btn_reread, has_sel, no_sel,
                   "Vuelve a leer los Excels seleccionados. "
                   "Para recargar todas las carpetas, usa ⟳ Actualizar")
```

3h. Menú Editar compartido. Sustituir `_on_edit_menu` por:

```python
    def _build_edit_menu(self, parent) -> QMenu:
        menu = QMenu("Editar", parent)
        selected_many = self._get_selected_many()
        selected = selected_many[0] if selected_many else {}
        ruta = os.path.normpath(selected.get("ruta_excel", "")) if selected else ""
        ok = bool(ruta) and os.path.exists(ruta)
        single = ok and len(selected_many) == 1

        act = menu.addAction("Regenerar campos")
        act.setEnabled(ok)
        act.triggered.connect(self._on_regen_fields)
        act = menu.addAction("Finalizar")
        act.setEnabled(single)
        act.setToolTip("Guarda en la base de datos los datos actuales del Excel")
        act.triggered.connect(self._on_finalize)
        menu.addSeparator()
        for label, handler in (
            ("Regenerar todas las partidas (IA)", self._edit_regen_all),
            ("Añadir más partidas (IA)", self._edit_add_partidas),
            ("Añadir partidas desde la biblioteca", self._edit_add_from_library),
        ):
            act = menu.addAction(label)
            act.setEnabled(ok)
            act.triggered.connect(lambda _=False, h=handler, r=ruta: h(r))
        menu.addSeparator()
        act = menu.addAction("Exportar PDF")
        act.setEnabled(ok)
        act.triggered.connect(self._on_export_pdf)
        return menu

    def _on_edit_menu(self):
        selected = self._get_selected()
        if not selected:
            return
        ruta = os.path.normpath(selected.get("ruta_excel", ""))
        if not os.path.exists(ruta):
            QMessageBox.warning(self, "Error", f"El archivo ya no existe:\n{ruta}")
            return
        self._build_edit_menu(self).exec(
            self._btn_edit.mapToGlobal(self._btn_edit.rect().bottomLeft())
        )
```

3i. Borrar el método `_on_open_menu` completo.

3j. `_on_context_menu`: justo antes de `menu.exec(table.viewport().mapToGlobal(pos))` añadir:

```python
        menu.addSeparator()
        edit_menu = self._build_edit_menu(menu)
        menu.addMenu(edit_menu)
        edit_menu.setEnabled(has_excel)
```

3k. `_on_export_pdf`: sustituir `self._btn_edit.setText("Generando PDF…")` y `self._btn_edit.setText("Editar ▼")` sin cambios de lógica (los nombres siguen valiendo). No tocar más en esta tarea.

3l. Añadir en la sección de acciones (tras `_on_regen_fields`):

```python
    def _notify(self, text, actions=None):
        """Aviso pasajero; en una ventana a medio crear (tests) solo se registra."""
        try:
            show_toast(self, text, actions=actions)
        except (RuntimeError, TypeError):  # QMainWindow sin __init__ (tests con __new__)
            logger.info("Aviso: %s", text)

    def _on_finalize(self):
        selected = self._get_selected()
        if not selected:
            return
        ruta = os.path.normpath(selected.get("ruta_excel", ""))
        if not os.path.exists(ruta):
            QMessageBox.warning(self, "Error", f"El archivo ya no existe:\n{ruta}")
            return
        self._finalize_ruta(ruta, self._current_state() or "")

    def _finalize_ruta(self, ruta, estado):
        def _work():
            from src.core.services import BudgetService

            return BudgetService().finalize_budget(ruta, estado=estado)

        def _done(ok, result):
            try:
                if ok and result:
                    self._refresh_rows([ruta])
                    self._notify(f"Presupuesto finalizado: {os.path.basename(ruta)}")
                else:
                    QMessageBox.warning(
                        self, "Finalizar presupuesto",
                        "No se pudo finalizar el presupuesto con los datos del Excel.",
                    )
            except RuntimeError:  # el dashboard se cerró
                return

        run_in_background(_work, _done)

    def _on_enter_shortcut(self):
        if isinstance(QApplication.focusWidget(), QLineEdit):
            return  # Intro en el buscador o en un filtro no abre nada
        if self._explorer_mode:
            self._on_explorer_dblclick()
        else:
            self._on_open_excel()

    def _focus_search(self):
        search = self._tab_searches.get(self._current_state() or "")
        if search is not None:
            search.setFocus()
            search.selectAll()
```

- [ ] **Step 4: Run tests**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_budget_dashboard_toolbar.py tests/test_budget_dashboard_open_excel.py tests/test_budget_dashboard_row_refresh.py tests/test_budget_dashboard_search_selection.py tests/test_regen_header_batch.py tests/test_partida_library_gui.py tests/test_obra_planning_gui.py`
Expected: PASS. `grep -n "_btn_open\b\|_btn_regen_fields\|_btn_refresh_selected\|_btn_toggle_extra\|_btn_reset_columns\|_on_open_menu" src tests -r` no debe devolver nada.

- [ ] **Step 5: Commit**

```bash
git add src/gui/budget_dashboard.py tests/test_budget_dashboard_toolbar.py
git commit -m "feat(dashboard): botones directos, menú Columnas, Editar con Finalizar y atajos"
```

---

### Task 6: Avisos pasajeros en lugar de ventanas de éxito

**Files:**
- Modify: `src/gui/budget_dashboard.py` (`_on_preview`, `_on_refresh_selected`, `_on_export_pdf`, `_on_open_excel`, `_edit_regen_all`, `_edit_add_from_library`, `_edit_add_partidas`, `_edit_regen_header_selected`, `_edit_regen_header`)
- Modify tests: `tests/test_budget_dashboard_open_excel.py`, `tests/test_budget_dashboard_row_refresh.py`, `tests/test_regen_header_batch.py`
- Test: `tests/test_budget_dashboard_notify.py`

**Interfaces:**
- Consumes: Task 5 (`_notify(text, actions)`).
- Produces: `_open_pdf_actions(pdf_path) -> list[tuple[str, Callable]]`; `_edit_regen_header(ruta, numero_proyecto="")` (sin parámetro `ask_confirmation`).

- [ ] **Step 1: Write the failing tests**

`tests/test_budget_dashboard_notify.py`:

```python
"""Los éxitos se notifican con un aviso pasajero, no con una ventana."""

import os

import pytest

try:
    from PySide6.QtWidgets import QMessageBox

    from src.core import folder_scanner, services
    from src.core.settings import Settings
    from src.gui import budget_dashboard as bd
    from src.gui.budget_dashboard import BudgetDashboardFrame

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")

STATE = "PRESUPUESTADO"


def _row(numero, ruta):
    return {
        "numero": numero, "nombre_proyecto": f"{numero} obra", "cliente": "C",
        "administracion_nombre": "", "direccion": "", "localidad": "", "tipo_obra": "",
        "fecha": "", "subtotal": 0.0, "iva": 0.0, "total": 0.0, "fuente_datos": "scan",
        "es_finalizado": False, "calidad_datos": 100, "datos_completos": True,
        "ruta_excel": ruta, "ruta_carpeta": os.path.dirname(ruta),
    }


@pytest.fixture
def dash(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(Settings, "get_default_path", lambda self, key: "")
    monkeypatch.setattr(bd, "cleanup_orphaned_cache", lambda *a, **k: None)
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    monkeypatch.setattr(bd, "resolve_projects", lambda scanned, index, state: scanned)
    ruta = os.path.normpath(str(tmp_path / "1-26.xlsx"))
    open(ruta, "wb").close()
    monkeypatch.setattr(folder_scanner, "scan_projects", lambda d: [_row("1-26", ruta)])
    frame = BudgetDashboardFrame()
    frame._rebuild_tabs([STATE], str(tmp_path))
    frame._tab_tables[STATE].selectRow(0)
    toasts, boxes = [], []
    monkeypatch.setattr(frame, "_notify", lambda text, actions=None: toasts.append(
        (text, [label for label, _cb in (actions or [])])))
    monkeypatch.setattr(frame, "_refresh_rows", lambda rutas, on_done=None: None)
    for name in ("information", "question", "warning"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(
            lambda *a, _n=name, **k: boxes.append(_n) or QMessageBox.StandardButton.Yes))
    yield frame, ruta, toasts, boxes
    frame.close()


def test_reread_without_failures_is_a_toast(monkeypatch, dash):
    frame, _, toasts, boxes = dash

    class _Svc:
        def refresh_budget_cache_entry(self, ruta, estado="", expected_numero=""):
            return True

    monkeypatch.setattr(services, "BudgetService", _Svc)
    frame._on_refresh_selected()
    assert toasts == [("Releídos 1", [])]
    assert boxes == []


def test_reread_with_failures_keeps_the_dialog(monkeypatch, dash):
    frame, _, toasts, boxes = dash

    class _Svc:
        def refresh_budget_cache_entry(self, ruta, estado="", expected_numero=""):
            return False

        def diagnose_read_failure(self, ruta, numero=""):
            return "Ninguna hoja coincide"

    monkeypatch.setattr(services, "BudgetService", _Svc)
    frame._on_refresh_selected()
    assert boxes == ["information"]
    assert toasts == []


def test_unreadable_excel_opens_without_asking(monkeypatch, dash):
    frame, ruta, toasts, boxes = dash
    opened = []

    class _Svc:
        def refresh_budget_cache_entry(self, r, estado="", expected_numero=""):
            return False

        def diagnose_read_failure(self, r, numero=""):
            return "E5 vacío en todas las hojas"

    monkeypatch.setattr(services, "BudgetService", _Svc)
    monkeypatch.setattr(BudgetDashboardFrame, "_open_file", staticmethod(lambda p: opened.append(p) or True))
    monkeypatch.setattr(frame, "_watch_excel_changes_and_refresh", lambda ruta_excel, estado: None)

    frame._on_open_excel()

    assert opened == [ruta]
    assert boxes == []
    assert toasts == [("No se pudo leer bien 1-26.xlsx: E5 vacío en todas las hojas. "
                       "Se ha abierto igualmente.", [])]


def test_regen_header_single_does_not_warn_first(monkeypatch, dash):
    frame, ruta, toasts, boxes = dash
    monkeypatch.setattr(frame, "_obtain_project_data", lambda preselect_numero="": ({"numero": "1-26"}, "1-26 obra"))
    monkeypatch.setattr(frame, "_write_regenerated_header", lambda *a: True)
    frame._edit_regen_header(ruta, "1-26")
    assert boxes == []
    assert toasts == [("Campos actualizados: 1-26.xlsx", [])]


def test_pdf_done_offers_open_and_folder(monkeypatch, dash, tmp_path):
    frame, _, toasts, boxes = dash

    class _Exporter:
        def is_available(self):
            return True

        def export(self, ruta):
            return True, str(tmp_path / "1-26.pdf")

    import src.core.pdf_exporter as pdf_mod
    monkeypatch.setattr(pdf_mod, "PDFExporter", _Exporter)
    frame._on_export_pdf()
    assert toasts == [("PDF generado: 1-26.pdf", ["Abrir", "Carpeta"])]
    assert boxes == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_budget_dashboard_notify.py`
Expected: FAIL (se abren ventanas en vez de avisos).

- [ ] **Step 3: Implement**

3a. `_on_preview`: sustituir el `QMessageBox.information(...)` de «Se abrieron 5 previsualizaciones…» por
`self._notify(f"Se abrieron 5 previsualizaciones de {len(rutas)} seleccionados.")`.

3b. `_on_refresh_selected`: el título «Escanear presupuestos» pasa a «Releer del Excel» en los dos `QMessageBox` que quedan; y en `_done` sustituir

```python
            ok_count, failures = payload
            self._refresh_rows([ruta for ruta, _numero in targets])
            QMessageBox.information(
                self, "Escanear presupuestos", _scan_summary(ok_count, failures)
            )
```

por

```python
            ok_count, failures = payload
            self._refresh_rows([ruta for ruta, _numero in targets])
            if failures:
                QMessageBox.information(self, "Releer del Excel", _scan_summary(ok_count, failures))
            else:
                self._notify(f"Releídos {ok_count}")
```

Cambiar también el docstring de `_scan_summary` a `"""Resumen de «Releer del Excel» con el motivo de cada fallo."""`.

3c. `_on_export_pdf`: en `_on_pdf_done`, sustituir el bloque `if ok: resp = QMessageBox.question(...) …` por:

```python
            if ok:
                self._notify(f"PDF generado: {os.path.basename(result)}", self._open_pdf_actions(result))
            else:
                QMessageBox.critical(self, "Error", f"Error al exportar PDF:\n{result}")
```

y añadir el método:

```python
    def _open_pdf_actions(self, pdf_path):
        return [
            ("Abrir", lambda: self._open_file(pdf_path)),
            ("Carpeta", lambda: self._open_file(os.path.dirname(pdf_path))),
        ]
```

3d. `_on_open_excel`: en `_work` devolver también el diagnóstico:

```python
        def _work():
            from src.core.services import BudgetService

            svc = BudgetService()
            # Refresco inmediato al abrir para no depender del mtime de cierre.
            # Esa misma lectura dice si el Excel se pudo leer: una por fichero.
            out = []
            for ruta, numero in targets:
                readable = svc.refresh_budget_cache_entry(ruta, estado=estado, expected_numero=numero)
                motivo = "" if readable else svc.diagnose_read_failure(ruta, numero)
                out.append((ruta, readable, motivo))
            return out
```

y sustituir `_done` por:

```python
        def _done(ok, payload):
            self._open_in_progress = False
            QApplication.restoreOverrideCursor()
            results = payload if ok else [(ruta, False, "") for ruta, _numero in targets]
            for ruta, _readable, _motivo in results:
                if self._open_file(ruta):
                    self._watch_excel_changes_and_refresh(ruta_excel=ruta, estado=estado)
            unreadable = [(ruta, motivo) for ruta, readable, motivo in results if not readable]
            if len(unreadable) == 1:
                ruta, motivo = unreadable[0]
                detalle = f": {motivo}" if motivo else ""
                self._notify(f"No se pudo leer bien {os.path.basename(ruta)}{detalle}. "
                             "Se ha abierto igualmente.")
            elif unreadable:
                self._notify(f"{len(unreadable)} Excels no se pudieron leer bien. "
                             "Se han abierto igualmente; usa «Releer del Excel» para ver el motivo.")
            self._refresh_rows([ruta for ruta, _readable, _motivo in results])
```

3e. `_edit_regen_all`: mantener la advertencia; sustituir
`QMessageBox.information(self, "Éxito", f"Partidas regeneradas ({len(selected_partidas)}).")` por
`self._notify(f"Partidas regeneradas ({len(selected_partidas)}).")`.

3f. `_edit_add_from_library`: sustituir `QMessageBox.information(self, "Éxito", f"{len(selected)} partidas añadidas.")` por `self._notify(f"{len(selected)} partidas añadidas.")` y el aviso «Todas las partidas elegidas ya están en el presupuesto.» por `self._notify("Todas las partidas elegidas ya están en el presupuesto.")`.

3g. `_edit_add_partidas`: sustituir el `QMessageBox.information(self, "Éxito", f"{len(selected_partidas)} partidas añadidas.")` por `self._notify(f"{len(selected_partidas)} partidas añadidas.")`.

3h. `_edit_regen_header_selected`: mantener la advertencia; sustituir `QMessageBox.information(self, "Regenerar campos", summary)` por:

```python
        if failed or pending:
            QMessageBox.information(self, "Regenerar campos", summary)
        else:
            self._notify(f"Campos regenerados en {len(ready)} presupuesto(s).")
```

3i. `_edit_regen_header`: quitar el parámetro `ask_confirmation` y el bloque `if ask_confirmation: …` entero (la ventana de la relación ya muestra los datos y tiene Cancelar). Firma: `def _edit_regen_header(self, ruta, numero_proyecto=""):`. Sustituir `QMessageBox.information(self, "Éxito", "Campos actualizados.")` por `self._notify(f"Campos actualizados: {os.path.basename(ruta)}")`.

3j. Ajustar tests existentes:
- `tests/test_budget_dashboard_open_excel.py`: en el fixture `spies`, `_FakeService` añade `def diagnose_read_failure(self, ruta, numero=""): return "motivo"`, y se añade `monkeypatch.setattr(dash, "_notify", lambda text, actions=None: calls.setdefault("toasts", []).append(text))`. Sustituir `test_unreadable_excel_asks_and_respects_no` por:

```python
def test_unreadable_excel_opens_and_notifies(monkeypatch, frame, spies):
    dash, ruta = frame
    calls, fake = spies
    fake.readable = False
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: pytest.fail("no debe preguntar")))

    dash._on_open_excel()

    assert calls["opened"] == [ruta]
    assert calls["rows"] == [[ruta]]
    assert calls["toasts"] == ["No se pudo leer bien 1-26.xlsx: motivo. Se ha abierto igualmente."]
```

  y revisar el resto de tests del fichero que dependan del `QMessageBox.question` de lectura incompleta: deben esperar la apertura directa.
- `tests/test_budget_dashboard_row_refresh.py::test_scan_selected_refreshes_rows_instead_of_full_reload`: añadir `monkeypatch.setattr(frame, "_notify", lambda *a, **k: None)`.
- `tests/test_regen_header_batch.py`: en el fixture `batch`, añadir `monkeypatch.setattr(frame, "_notify", lambda *a, **k: None)` tras crear `frame`. Si algún test cuenta las ventanas `information` del resumen de un lote sin fallos ni pendientes, cambiarlo para comprobar que no se muestra ninguna.

- [ ] **Step 4: Run tests**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_budget_dashboard_notify.py tests/test_budget_dashboard_open_excel.py tests/test_budget_dashboard_row_refresh.py tests/test_regen_header_batch.py tests/test_partida_library_gui.py`
Expected: PASS. Comprobar con `grep -n '"Éxito"' src/gui/budget_dashboard.py` que no queda ninguno.

- [ ] **Step 5: Commit**

```bash
git add src/gui/budget_dashboard.py tests/test_budget_dashboard_notify.py tests/test_budget_dashboard_open_excel.py tests/test_budget_dashboard_row_refresh.py tests/test_regen_header_batch.py
git commit -m "feat(dashboard): avisos pasajeros en vez de ventanas de éxito y menos confirmaciones"
```

---

### Task 7: Guardar un Excel ya no pregunta «¿Finalizar?»

**Files:**
- Modify: `src/gui/budget_dashboard.py` (`__init__`: quitar `_excel_no_finalize`; `_arm_excel_watch` ~1765)
- Modify tests: `tests/test_gui_late_results.py`

**Interfaces:**
- Consumes: Task 5 (`_notify`, `_finalize_ruta(ruta, estado)`).
- Produces: el vigilante refresca la caché y la fila y muestra `"Se guardó <nombre> · ¿finalizar?"` con la acción `("Finalizar", …)` que llama a `_finalize_ruta(ruta_excel, estado)`.

- [ ] **Step 1: Rewrite the tests**

En `tests/test_gui_late_results.py`, sustituir `test_guardar_excel_pregunta_antes_de_finalizar` por:

```python
def test_guardar_excel_refresca_sin_preguntar_y_ofrece_finalizar(qapp, monkeypatch):
    """Al guardar el Excel abierto desde el dashboard se refresca la fila sin
    ventanas y se ofrece «Finalizar» en un aviso pasajero."""
    import src.gui.budget_dashboard as bd
    from src.core import services

    llamadas, avisos, finalizados = [], [], []

    class _FakeService:
        def finalize_budget(self, ruta, estado=""):
            raise AssertionError("guardar no debe finalizar")

        def refresh_budget_cache_entry(self, ruta, estado=""):
            llamadas.append("refresh"); return True

    eventos = iter([True, True])

    def _fake_wait(ruta, stop, baseline):
        try:
            return next(eventos)
        except StopIteration:
            stop.set()
            return False

    monkeypatch.setattr(bd.os.path, "getmtime", lambda _p: 100.0)
    monkeypatch.setattr(bd, "_wait_for_excel_change", _fake_wait)
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    monkeypatch.setattr(services, "BudgetService", _FakeService)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: pytest.fail("no debe preguntar")))

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._excel_watchers = {}
    dash._load_data = lambda: llamadas.append("full-reload")
    dash._refresh_rows = lambda rutas, on_done=None: llamadas.append("reload")
    dash._notify = lambda text, actions=None: avisos.append((text, actions))
    dash._finalize_ruta = lambda ruta, estado: finalizados.append((ruta, estado))
    bd.BudgetDashboardFrame._watch_excel_changes_and_refresh(dash, "C:/obra/presupuesto.xlsx", "PRESUPUESTADO")

    assert llamadas == ["refresh", "reload", "refresh", "reload"]
    assert [t for t, _a in avisos] == ["Se guardó presupuesto.xlsx · ¿finalizar?"] * 2
    label, action = avisos[0][1][0]
    assert label == "Finalizar"
    action()
    assert finalizados == [("C:/obra/presupuesto.xlsx", "PRESUPUESTADO")]
```

Sustituir `test_vigilancia_excel_se_para_si_se_cierra_durante_la_finalizacion` por:

```python
def test_vigilancia_excel_se_para_si_se_cierra_durante_el_refresco(qapp, monkeypatch):
    """Cerrar el dashboard mientras se refresca el guardado detiene la vigilancia."""
    import src.gui.budget_dashboard as bd
    from src.core import services

    ruta = "C:/obra/presupuesto.xlsx"
    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._excel_watchers = {}
    dash._load_data = lambda: None
    dash._refresh_rows = lambda rutas, on_done=None: None
    dash._notify = lambda *a, **k: None
    bases = []
    mtimes = iter([100.0, 250.0])

    def _fake_wait(r, stop, baseline):
        bases.append(baseline)
        return len(bases) == 1  # solo el primer guardado

    class _FakeService:
        def refresh_budget_cache_entry(self, r, estado=""):
            dash._excel_watchers[ruta].set()  # el usuario cierra el dashboard aquí
            return True

    monkeypatch.setattr(bd.os.path, "getmtime", lambda _p: next(mtimes, 250.0))
    monkeypatch.setattr(bd, "_wait_for_excel_change", _fake_wait)
    monkeypatch.setattr(bd, "run_in_background", lambda work, cb: cb(True, work()))
    monkeypatch.setattr(services, "BudgetService", _FakeService)

    bd.BudgetDashboardFrame._watch_excel_changes_and_refresh(dash, ruta, "PRESUPUESTADO")

    assert bases == [100.0]  # no se re-arma tras cerrar
```

En `test_vigilancia_excel_rearma_con_el_mtime_del_guardado_detectado`: borrar la línea `dash._excel_no_finalize = set()` y la de `monkeypatch.setattr(QMessageBox, "question", …)`, y añadir `dash._notify = lambda *a, **k: None`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gui_late_results.py -k vigilancia_excel or guardar_excel`
Expected: FAIL («no debe preguntar»).

- [ ] **Step 3: Implement**

3a. En `__init__`, borrar las dos líneas:

```python
        # Excels en los que el usuario ya dijo "No" a finalizar al guardar.
        self._excel_no_finalize: set[str] = set()
```

3b. Docstring de `_watch_excel_changes_and_refresh`: sustituir «al detectar un cambio pregunta si finalizar (decisión E1), refresca el snapshot y vuelve a vigilar» por «al detectar un cambio refresca la fila, ofrece «Finalizar» en un aviso pasajero y vuelve a vigilar».

3c. En `_arm_excel_watch`, dentro de `_on_watch_done`, sustituir todo desde `# Decisión E1: al guardar ya no se finaliza sin preguntar.` hasta el final de `_on_watch_done` (incluidas `_apply` y `_applied`) por:

```python
            # Al guardar no se finaliza ni se pregunta: se refresca la fila y se
            # ofrece «Finalizar» en un aviso que no interrumpe.
            def _apply():
                from src.core.services import BudgetService

                return BudgetService().refresh_budget_cache_entry(ruta_excel, estado=estado)

            def _applied(ok_apply, result):
                if stop.is_set():
                    return
                try:
                    if ok_apply and result:
                        self._refresh_rows([ruta_excel])
                    self._notify(
                        f"Se guardó {os.path.basename(ruta_excel)} · ¿finalizar?",
                        [("Finalizar", lambda: self._finalize_ruta(ruta_excel, estado))],
                    )
                except RuntimeError:
                    return
                if not stop.is_set():
                    self._arm_excel_watch(ruta_excel, estado, stop, new_baseline)

            run_in_background(_apply, _applied)
```

- [ ] **Step 4: Run tests**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_gui_late_results.py tests/test_budget_dashboard_open_excel.py`
Expected: PASS. `grep -rn "_excel_no_finalize" src tests` no devuelve nada.

- [ ] **Step 5: Commit**

```bash
git add src/gui/budget_dashboard.py tests/test_gui_late_results.py
git commit -m "feat(dashboard): guardar un Excel refresca sin preguntar y ofrece Finalizar"
```

---

### Task 8: Mover sin preguntar y Deshacer

**Antes de empezar:** avisar a la sesión de planificación (dev-ab) de que se añade `restore_plan_snapshot` en `obra_planificacion_repository.py`. Si no está disponible, seguir y mencionarlo al usuario al terminar.

**Files:**
- Modify: `src/core/repositories/obra_planificacion_repository.py` (añadir al final)
- Modify: `src/gui/budget_dashboard.py` (`_move_project` ~1236)
- Modify tests: `tests/test_obra_planning_gui.py`
- Test: `tests/test_budget_dashboard_move_undo.py`

**Interfaces:**
- Consumes: Task 5 (`_notify`); repositorio existente (`get_planes(numeros) -> dict`, `record_state_change`).
- Produces:
  - `restore_plan_snapshot(numero: str, snapshot: dict | None) -> str | None` — `None` borra la fila; un dict (como lo devuelve `get_planes`) restaura todos los campos editables. Devuelve mensaje de error o `None`.
  - Dashboard: `_undo_move(moves: list[tuple[str, str, str]], snapshots: dict[str, dict | None]) -> None` con `moves = [(origen, destino, numero), …]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_budget_dashboard_move_undo.py`:

```python
"""Mover proyectos no pregunta; el aviso ofrece Deshacer (carpetas y planificación)."""

from datetime import date

import pytest

try:
    from PySide6.QtWidgets import QMessageBox

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


@pytest.fixture
def mover(qapp, tmp_path, monkeypatch):
    import src.gui.budget_dashboard as bd
    from src.core import database

    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "obras.db"))
    monkeypatch.setenv("CUBIAPP_BACKUP_DIR", str(tmp_path / "backups"))
    with database.get_connection():
        pass
    root = tmp_path / "PRESUPUESTOS"
    for estado in ("EJECUTAR", "EJECUTANDO"):
        (root / estado).mkdir(parents=True)
    boxes = []
    for name in ("question", "information", "warning"):
        monkeypatch.setattr(QMessageBox, name, staticmethod(
            lambda *a, _n=name, **k: boxes.append(_n) or QMessageBox.StandardButton.Yes))

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._root_path = str(root)
    dash._planning_duplicates = set()
    reloads, toasts = [], []
    dash._load_data = lambda: reloads.append(1)
    dash._notify = lambda text, actions=None: toasts.append((text, dict(actions or [])))

    def _obra(estado, numero):
        carpeta = root / estado / f"{numero} OBRA"
        carpeta.mkdir()
        return {"ruta_carpeta": str(carpeta), "numero": numero}

    return bd, dash, _obra, root, boxes, toasts, reloads


def test_move_does_not_ask_and_offers_undo(mover):
    bd, dash, obra, root, boxes, toasts, reloads = mover
    bd.BudgetDashboardFrame._move_project(dash, [obra("EJECUTAR", "114-26")], "EJECUTAR", "EJECUTANDO")
    assert boxes == []
    assert (root / "EJECUTANDO" / "114-26 OBRA").is_dir()
    text, actions = toasts[-1]
    assert text == "1 proyecto movido a EJECUTANDO"
    assert list(actions) == ["Deshacer"]
    assert reloads == [1]


def test_undo_moves_back_and_restores_planning(mover):
    from src.core.repositories.obra_planificacion_repository import get_planes, upsert_plan

    bd, dash, obra, root, boxes, toasts, reloads = mover
    upsert_plan("114-26", inicio_previsto=date(2026, 9, 1), estado_conocido="EJECUTAR")
    before = get_planes(["114-26"])["114-26"]

    bd.BudgetDashboardFrame._move_project(dash, [obra("EJECUTAR", "114-26")], "EJECUTAR", "EJECUTANDO")
    assert get_planes(["114-26"])["114-26"]["inicio_real"] == date.today()

    toasts[-1][1]["Deshacer"]()

    assert (root / "EJECUTAR" / "114-26 OBRA").is_dir()
    assert not (root / "EJECUTANDO" / "114-26 OBRA").exists()
    after = get_planes(["114-26"])["114-26"]
    for field in ("inicio_previsto", "inicio_real", "estado_conocido", "inicio_real_aproximado"):
        assert after[field] == before[field]
    assert toasts[-1][0] == "Movimiento deshecho"
    assert reloads == [1, 1]


def test_undo_removes_plan_row_that_did_not_exist(mover):
    from src.core.repositories.obra_planificacion_repository import get_planes

    bd, dash, obra, root, boxes, toasts, reloads = mover
    bd.BudgetDashboardFrame._move_project(dash, [obra("EJECUTAR", "200-26")], "EJECUTAR", "EJECUTANDO")
    assert "200-26" in get_planes(["200-26"])
    toasts[-1][1]["Deshacer"]()
    assert get_planes(["200-26"]) == {}


def test_failed_move_shows_dialog_with_failures(mover, monkeypatch):
    bd, dash, obra, root, boxes, toasts, reloads = mover

    def _boom(*a, **k):
        raise OSError("carpeta en uso")

    monkeypatch.setattr(bd.shutil, "move", _boom)
    bd.BudgetDashboardFrame._move_project(dash, [obra("EJECUTAR", "114-26")], "EJECUTAR", "EJECUTANDO")
    assert boxes == ["warning"]
    assert toasts == []


def test_restore_plan_snapshot_none_deletes(mover):
    from src.core.repositories.obra_planificacion_repository import (
        get_planes, restore_plan_snapshot, upsert_plan,
    )

    upsert_plan("1-26", notas="x")
    assert restore_plan_snapshot("1-26", None) is None
    assert get_planes(["1-26"]) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_budget_dashboard_move_undo.py`
Expected: FAIL (`boxes == ['question', 'information']` y `ImportError: restore_plan_snapshot`).

- [ ] **Step 3: Implement**

3a. Al final de `src/core/repositories/obra_planificacion_repository.py`:

```python
def restore_plan_snapshot(numero: str, snapshot: Optional[Dict]) -> Optional[str]:
    """Deja el plan de `numero` exactamente como en `snapshot` (para deshacer).

    `snapshot` es un plan tal como lo devuelve `get_planes`, o `None` si la obra
    no tenía fila: entonces se borra. Devuelve un mensaje de error o None.
    """
    numero = (numero or "").strip()
    if not numero:
        return "Falta el número de proyecto."
    with database.get_connection() as conn:
        try:
            if snapshot is None:
                conn.execute("DELETE FROM obra_planificacion WHERE numero_proyecto = ?", (numero,))
            else:
                _upsert(conn, numero, {f: snapshot.get(f) for f in sorted(_EDITABLE)})
            conn.commit()
            return None
        except sqlite3.Error as e:
            conn.rollback()
            return e.args[0] if e.args else "Error de base de datos."
```

3b. En `_move_project` (`src/gui/budget_dashboard.py`), sustituir desde `confirm = QMessageBox.question(` hasta el final del método por:

```python
        from src.core.repositories.obra_planificacion_repository import (
            get_planes, record_state_change,
        )

        duplicates = getattr(self, "_planning_duplicates", set())
        numeros = [n for _s, _d, n in valid_moves if n and n not in duplicates]
        try:
            existing = get_planes(numeros)
        except Exception:
            logger.exception("No se pudo leer la planificación antes de mover")
            existing = {}
        snapshots = {n: existing.get(n) for n in numeros}

        moved, failed = [], []
        for src_folder, dest_folder, numero in valid_moves:
            try:
                shutil.move(src_folder, dest_folder)
            except Exception as exc:
                failed.append((os.path.basename(src_folder), str(exc)))
                continue
            moved.append((src_folder, dest_folder, numero))
            # Planificación: al pasar a EJECUTANDO/TERMINADO queda la fecha real
            # (exacta, porque el movimiento lo hace la app ahora mismo).
            if numero and numero not in duplicates:
                err = record_state_change(numero, to_state.upper(), date.today(), aproximada=False)
                if err:
                    logger.warning("No se pudo registrar la fecha de %s: %s", numero, err)

        if failed:
            QMessageBox.warning(
                self, "Mover proyectos",
                f"No se pudieron mover {len(failed)} proyecto(s):\n"
                + "\n".join(f"· {n}: {m}" for n, m in failed[:10]),
            )
        if moved:
            noun = "proyecto movido" if len(moved) == 1 else "proyectos movidos"
            self._notify(
                f"{len(moved)} {noun} a {to_state}",
                [("Deshacer", lambda: self._undo_move(moved, snapshots))],
            )
        self._load_data()

    def _undo_move(self, moves, snapshots):
        """Devuelve las carpetas a su origen y la planificación a como estaba."""
        from src.core.repositories.obra_planificacion_repository import restore_plan_snapshot

        failed = []
        for src_folder, dest_folder, numero in reversed(moves):
            if os.path.exists(src_folder) or not os.path.isdir(dest_folder):
                failed.append((os.path.basename(src_folder), "la carpeta ya no está donde se movió"))
                continue
            try:
                shutil.move(dest_folder, src_folder)
            except Exception as exc:
                failed.append((os.path.basename(src_folder), str(exc)))
                continue
            if numero in snapshots:
                err = restore_plan_snapshot(numero, snapshots[numero])
                if err:
                    logger.warning("No se pudo restaurar la planificación de %s: %s", numero, err)
        if failed:
            QMessageBox.warning(
                self, "Deshacer",
                "No se pudieron devolver algunas carpetas:\n"
                + "\n".join(f"· {n}: {m}" for n, m in failed[:10]),
            )
        else:
            self._notify("Movimiento deshecho")
        self._load_data()
```

3c. `tests/test_obra_planning_gui.py`, fixture `mover`: sustituir `monkeypatch.setattr(QMessageBox, "question", …)` por `monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))` y añadir `dash._notify = lambda *a, **k: None` tras `dash._load_data = lambda: None`.

- [ ] **Step 4: Run tests**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_budget_dashboard_move_undo.py tests/test_obra_planning_gui.py tests/test_budget_dashboard_search_selection.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/core/repositories/obra_planificacion_repository.py src/gui/budget_dashboard.py tests/test_budget_dashboard_move_undo.py tests/test_obra_planning_gui.py
git commit -m "feat(dashboard): mover proyectos sin preguntar, con Deshacer que restaura la planificación"
```

---

### Task 9: Documentación y verificación completa

**Files:**
- Modify: `docs/README.md` (tabla «Planes pendientes»)
- Modify: `docs/planes/dashboard-filtros-estadisticas.md` (cabecera de estado)
- Modify: `CONTEXT.md` (si describe los botones o la pregunta de finalizar del dashboard)

- [ ] **Step 1: Suite completa**

Run: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider`
Expected: todo en verde. Anotar el número de tests.

- [ ] **Step 2: Restos de los flujos antiguos**

Run: `grep -n 'QMessageBox.information\|QMessageBox.question' src/gui/budget_dashboard.py`
Expected: solo quedan el resumen de «Releer del Excel» con fallos, «Esta acción está disponible en la vista de presupuestos», el aviso de «Regenerar campos» por lotes y los resúmenes con fallos o pendientes. Ninguna `question` (las advertencias de regenerar usan `QMessageBox.warning`).

- [ ] **Step 3: Docs**

En `docs/planes/dashboard-filtros-estadisticas.md`, sustituir la línea de estado por:

```markdown
> **Estado (2026-11-14):** Fases 1-2 (filtros) sustituidas por `docs/superpowers/specs/2026-11-14-dashboard-filtros-ux-design.md` (filtros por cliente/administración por nombre, no por id: la BD real no tiene administraciones ni comunidades). Fase 3 (estadísticas) y fase 4 pendientes.
```

En `docs/README.md`, añadir en «Planes pendientes» como primera fila:

```markdown
| [`superpowers/plans/2026-11-14-dashboard-filtros-ux.md`](superpowers/plans/2026-11-14-dashboard-filtros-ux.md) | Tanda 1 del pulido del circuito anterior a las partidas: filtros y limpieza de UX de «Presupuestos existentes». Implementada; falta la prueba manual. Tanda 2: «Crear presupuesto» y «Gestionar BD». Diseño: [`superpowers/specs/2026-11-14-dashboard-filtros-ux-design.md`](superpowers/specs/2026-11-14-dashboard-filtros-ux-design.md). |
```

y en la fila de `planes/dashboard-filtros-estadisticas.md` cambiar el estado a «Filtros hechos (ver 2026-11-14); faltan estadísticas.».

En `CONTEXT.md`, buscar `grep -n "Finalizar\|finalizar\|Escanear presupuestos\|Ocultar datos extra" CONTEXT.md` y actualizar las frases afectadas: guardar un Excel ya no pregunta (aviso con «Finalizar» y Editar → Finalizar); «Escanear presupuestos» se llama «Releer del Excel».

- [ ] **Step 4: Commit**

```bash
git add docs/README.md docs/planes/dashboard-filtros-estadisticas.md CONTEXT.md
git commit -m "docs: estado de los filtros y la limpieza de UX del dashboard"
```

- [ ] **Step 5: Prueba manual en la app (con el usuario)**

Run: `../ProyectoJose/.venv/Scripts/python.exe main.py` (o el lanzador que use el proyecto; comprobar `README.md`) desde la carpeta de trabajo, con la BD real.
Comprobar: filtro por cliente en PRESUPUESTADO; resumen; etiquetas y Limpiar; F5 conserva filtros; Columnas ▼; Intro abre Excel; guardar un Excel → aviso con Finalizar; mover un proyecto de prueba → Deshacer; exportar PDF → aviso con Abrir.
