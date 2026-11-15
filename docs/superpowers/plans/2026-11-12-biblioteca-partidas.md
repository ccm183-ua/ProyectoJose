# Biblioteca de partidas — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Buscar entre las ~17.000 partidas con precio del histórico, ver su respaldo y
insertarlas sin duplicados en un presupuesto nuevo o existente.

**Architecture:** Un módulo de núcleo sin PySide6 (`src/core/partida_library.py`) carga las
partidas en memoria, busca, agrupa y convierte la selección en candidatas con
`source="library"`. Un diálogo (`src/gui/partida_library_dialog.py`) las presenta y
devuelve las elegidas. Las candidatas entran en el flujo unificado que ya existe
(tabla de revisión `CombinedPartidasReviewDialog` + `apply_reviewed_partidas`).

**Tech Stack:** Python 3.10, SQLite (`src.core.database`), PySide6, pytest.

**Spec:** `docs/superpowers/specs/2026-11-12-biblioteca-partidas-design.md`.

## Global Constraints

- Núcleo sin PySide6: `src/core/partida_library.py` no importa nada de `PySide6` ni de `src.gui`.
- La biblioteca es **solo lectura** sobre la BD (`database.get_connection(read_only=True)`) y **nunca escribe en el Excel**.
- Las candidatas llevan `source = "library"`: nunca un `source` que empiece por `historical`.
- Estados: `approved` (aprobada), `unreviewed` (sin revisar), `ineligible` (no apta).
- Unidades canónicas: `p.a.`, `ud`, `m2`, `m`, `m3`, `kg`, `día`; cualquier otra → `?`.
- Fechas válidas: "dd/mm/aa", "dd/mm/aaaa" y número de serie de Excel en [30000, 60000]; el resto → sin fecha.
- Máximo 200 grupos por búsqueda.
- Rendimiento: carga < 3 s y búsqueda < 200 ms sobre la BD real.
- Tests: `QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider <ruta>`; ningún test toca la BD real (cada uno fija `CUBIAPP_DB_PATH` en `tmp_path`).
- Textos de interfaz y mensajes de commit en castellano con tildes.

---

## Mapa de ficheros

| Fichero | Acción | Responsabilidad |
|---|---|---|
| `src/core/partida_library.py` | Crear | Normalizadores, carga, búsqueda, agrupación, conversión a candidata |
| `src/gui/partida_library_dialog.py` | Crear | Diálogo de biblioteca (buscador, filtros, detalle, cesta) |
| `src/gui/combined_partidas_review_dialog.py` | Modificar | Lista opcional `library_partidas` y etiqueta "Biblioteca · …" |
| `src/gui/budget_dashboard.py` | Modificar | Acción "Añadir partidas desde la biblioteca" |
| `src/gui/main_frame.py` | Modificar | Elegir Biblioteca / IA / Dejar vacío al crear |
| `scripts/library_benchmark.py` | Crear | Validación de solo lectura con la BD real (tiempos y búsquedas de referencia) |
| `tests/test_partida_library.py` | Crear | Tests del núcleo |
| `tests/test_partida_library_gui.py` | Crear | Tests de diálogo, revisión e integraciones (offscreen) |

## Hitos

| Hito | Entregable | Validación de cierre |
|---|---|---|
| H1 | Normalizadores puros (unidad, fecha, estado) | Tests unitarios |
| H2 | Carga desde la BD | Tests con BD temporal |
| H3 | Búsqueda, agrupación, cifras y orden | Tests unitarios |
| H4 | Conversión a candidata y paso por el flujo unificado | Tests de flujo |
| H5 | Revisión acepta partidas de biblioteca | Tests offscreen |
| H6 | Diálogo de biblioteca | Tests offscreen |
| H7 | Integración en el dashboard | Test offscreen + suite completa |
| H8 | Integración al crear | Test offscreen + suite completa |
| H9 | Validación con datos reales y documentación | Script de benchmark + prueba manual |

---

### Task 1 (H1): normalizadores puros

**Files:**
- Create: `src/core/partida_library.py`
- Test: `tests/test_partida_library.py`

**Interfaces:**
- Produces:
  - `canonical_unit(raw: str) -> str`
  - `parse_budget_date(raw) -> Optional[datetime.date]`
  - `line_status(learning_status: str, analysis_status: str) -> str` (devuelve `"approved"|"unreviewed"|"ineligible"`)
  - `STATUS_RANK: Dict[str, int]` = `{"approved": 0, "unreviewed": 1, "ineligible": 2}`
  - `STATUS_LABELS: Dict[str, str]` = `{"approved": "aprobada", "unreviewed": "sin revisar", "ineligible": "no apta"}`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests del núcleo de la biblioteca de partidas (sin PySide6)."""

from datetime import date

import pytest

from src.core.partida_library import canonical_unit, line_status, parse_budget_date


@pytest.mark.parametrize("raw,esperada", [
    ("p.a.", "p.a."), ("P.A.", "p.a."), ("p.a", "p.a."), ("pa", "p.a."), ("P.a.", "p.a."), ("Partida", "p.a."),
    ("ud", "ud"), ("Ud", "ud"), ("UD", "ud"), ("ud.", "ud"),
    ("m2", "m2"), ("M2", "m2"), ("m²", "m2"),
    ("m", "m"), ("M", "m"), ("ml", "m"),
    ("m3", "m3"), ("kg", "kg"), ("DIAS", "día"), ("día", "día"),
    ("65807DC0", "?"), ("1650", "?"), ("", "?"), (None, "?"),
])
def test_canonical_unit(raw, esperada):
    assert canonical_unit(raw) == esperada


@pytest.mark.parametrize("raw,esperada", [
    ("13/02/26", date(2026, 2, 13)),
    ("13/02/2026", date(2026, 2, 13)),
    ("46036", date(2026, 1, 14)),
    ("46041", date(2026, 1, 19)),
    ("%", None), ("SAN VICENTE", None), ("", None), (None, None),
    ("31/02/26", None),      # fecha imposible
    ("12345", None),         # serie fuera de [30000, 60000]
])
def test_parse_budget_date(raw, esperada):
    assert parse_budget_date(raw) == esperada


@pytest.mark.parametrize("learning,analysis,esperado", [
    ("INCLUDED", "VALID", "approved"),
    ("INCLUDED", "VALID_WITH_WARNINGS", "approved"),
    ("PENDING_REVIEW", "VALID", "unreviewed"),
    ("NOT_ELIGIBLE", "VALID", "ineligible"),
    ("INCLUDED", "READ_ERROR", "ineligible"),
    ("PENDING_REVIEW", "EXCLUDED_INCOMPLETE_DATA", "ineligible"),
    ("", "", "ineligible"),
])
def test_line_status(learning, analysis, esperado):
    assert line_status(learning, analysis) == esperado
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library.py`
Expected: ERROR `ModuleNotFoundError: No module named 'src.core.partida_library'`

- [ ] **Step 3: Write minimal implementation**

```python
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
    match = _DATE_RE.fullmatch(text)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library.py`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add src/core/partida_library.py tests/test_partida_library.py
git commit -m "feat(biblioteca): normalizadores de unidad, fecha y estado"
```

**Validación H1:** los tres normalizadores cubren todas las variantes medidas en la BD real (33 unidades, fechas dd/mm/aa y serie de Excel, estados de aprendizaje y de análisis).

---

### Task 2 (H2): carga desde la BD

**Files:**
- Modify: `src/core/partida_library.py`
- Test: `tests/test_partida_library.py`

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `@dataclass(frozen=True) class LibraryLine` con campos `partida_id: int, budget_id: int, proyecto: str, concepto: str, concepto_norm: str, unidad: str, unidad_canon: str, precio: float, status: str, fecha: Optional[date], module: str`.
  - `class PartidaLibrary` con `__init__(self, lines: List[LibraryLine], ignored: int = 0)`, atributos `lines`, `ignored`, y `@classmethod load(cls) -> "PartidaLibrary"`.

- [ ] **Step 1: Write the failing tests** (añadir a `tests/test_partida_library.py`)

```python
from datetime import datetime

from src.core.partida_library import PartidaLibrary
from src.core.repositories import (
    approve_budget_for_learning,
    insert_historical_partida,
    upsert_historical_budget,
)


def _budget(tmp_path, nombre, *, aprobado=False, analysis="VALID", fecha="13/02/26"):
    bid, err = upsert_historical_budget({
        "ruta_excel": str(tmp_path / f"{nombre}.xlsx"),
        "ruta_carpeta": str(tmp_path),
        "nombre_proyecto": nombre,
        "fecha_modificacion_excel": datetime.now().isoformat(),
        "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fecha_presupuesto": fecha,
        "analisis_ok": True,
        "analysis_status": analysis,
        "file_sha256": f"sha-{nombre}",
    })
    assert err is None
    if aprobado:
        assert approve_budget_for_learning(bid, "TEST") is None
    return bid


def _partida(bid, concepto, unidad, precio, orden=1):
    pid, err = insert_historical_partida(bid, {
        "orden": orden,
        "titulo": concepto.split("\n")[0],
        "concepto_original": concepto,
        "unidad": unidad,
        "precio_unitario": precio,
        "cantidad": 1,
        "total_linea": precio,
    })
    assert err is None
    return pid


@pytest.fixture
def db_biblioteca(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "biblioteca.db"))
    monkeypatch.setenv("CUBIAPP_BACKUP_DIR", str(tmp_path / "backups"))
    aprobado = _budget(tmp_path, "001-26 Aprobado", aprobado=True)
    pendiente = _budget(tmp_path, "002-26 Pendiente", fecha="46036")
    roto = _budget(tmp_path, "003-26 Roto", analysis="READ_ERROR", fecha="%")
    _partida(aprobado, "SUSTITUCIÓN BAJANTE PVC.\nSustitución de bajante de PVC de 110 mm", "ml", 30.0, 1)
    _partida(aprobado, "Pintura de escalera", "p.a.", 0, 2)            # sin precio: no se carga
    _partida(pendiente, "SUSTITUCIÓN BAJANTE PVC.\nSustitución de bajante de PVC de 110 mm", "m", 34.0, 1)
    _partida(pendiente, "Impermeabilización de cubierta", "M2", 22.5, 2)
    _partida(roto, "Impermeabilización de cubierta", "m2", 50.0, 1)
    return tmp_path


def test_load_carga_solo_partidas_con_precio_y_su_estado(db_biblioteca):
    lib = PartidaLibrary.load()

    assert len(lib.lines) == 4
    por_proyecto = {(l.proyecto, l.precio): l for l in lib.lines}
    bajante_ok = por_proyecto[("001-26 Aprobado", 30.0)]
    assert bajante_ok.status == "approved"
    assert bajante_ok.unidad == "ml" and bajante_ok.unidad_canon == "m"
    assert bajante_ok.concepto.startswith("SUSTITUCIÓN BAJANTE PVC.")
    assert bajante_ok.concepto_norm  # normalizado no vacío
    assert por_proyecto[("002-26 Pendiente", 34.0)].status == "unreviewed"
    assert por_proyecto[("002-26 Pendiente", 34.0)].fecha == date(2026, 1, 14)
    roto = por_proyecto[("003-26 Roto", 50.0)]
    assert roto.status == "ineligible" and roto.fecha is None


def test_load_ignora_lineas_invalidas_y_las_cuenta(db_biblioteca, monkeypatch):
    from src.core import database

    with database.get_connection() as conn:
        conn.execute("UPDATE historical_partida SET concepto_original='', titulo='', concepto_normalizado='' "
                     "WHERE precio_unitario = 22.5")
        conn.commit()

    lib = PartidaLibrary.load()

    assert len(lib.lines) == 3
    assert lib.ignored == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library.py -k load`
Expected: FAIL `ImportError: cannot import name 'PartidaLibrary'`

- [ ] **Step 3: Write minimal implementation** (añadir a `src/core/partida_library.py`)

```python
import math
from dataclasses import dataclass
from typing import List

from src.core import database
from src.core.work_type_normalizer import normalize_text


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
```

Mueve los `import` nuevos (`math`, `dataclass`, `List`, `database`, `normalize_text`) al bloque de imports de la cabecera del módulo.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library.py`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add src/core/partida_library.py tests/test_partida_library.py
git commit -m "feat(biblioteca): cargar en memoria las partidas con precio del histórico"
```

**Validación H2:** la carga es de solo lectura (`read_only=True`), descarta precios no positivos y líneas sin texto, y etiqueta cada línea con su estado.

---

### Task 3 (H3): búsqueda, agrupación, cifras y orden

**Files:**
- Modify: `src/core/partida_library.py`
- Test: `tests/test_partida_library.py`

**Interfaces:**
- Consumes: Tasks 1-2.
- Produces:
  - `@dataclass class LibraryGroup` con campos `concepto_norm: str, unidad_canon: str, lines: List[LibraryLine], n_budgets: int, price_min: float, price_median: float, price_max: float, approved_median: Optional[float], status: str, fecha: Optional[date], module: str, proposed_price: float, price_basis: str, warnings: Tuple[str, ...]` y propiedad `representative -> LibraryLine`.
  - `@dataclass class SearchResult` con `groups: List[LibraryGroup], total_groups: int` y propiedad `truncated -> bool`.
  - `PartidaLibrary.search(self, query: str = "", module: str = "", unit: str = "", status_filter: str = "all", limit: int = 200) -> SearchResult` (`status_filter` ∈ `"all" | "approved" | "no_ineligible"`).
  - Constantes `WARNING_NO_APPROVED = "sin evidencia aprobada"`, `WARNING_LUMP_SUM = "partida alzada: revisa el alcance"`, `WARNING_UNKNOWN_UNIT = "unidad no reconocida"`.

- [ ] **Step 1: Write the failing tests**

```python
from src.core.partida_library import (
    WARNING_LUMP_SUM,
    WARNING_NO_APPROVED,
    LibraryLine,
)


def _line(pid, concepto_norm, precio, status="approved", unidad="m2", budget=None, fecha=None, module="fachada"):
    return LibraryLine(
        partida_id=pid, budget_id=budget if budget is not None else pid, proyecto=f"obra {pid}",
        concepto=concepto_norm.upper(), concepto_norm=concepto_norm, unidad=unidad,
        unidad_canon=canonical_unit(unidad), precio=precio, status=status, fecha=fecha, module=module,
    )


def test_busqueda_exige_todas_las_palabras_desde_inicio_de_palabra():
    lib = PartidaLibrary([
        _line(1, "impermeabilizacion de cubierta plana", 20),
        _line(2, "alicatado de bano", 30, module="alicatado"),
        _line(3, "impermeabilizacion de terraza", 25),
    ])
    conceptos = [g.concepto_norm for g in lib.search("imperm cubierta").groups]
    assert conceptos == ["impermeabilizacion de cubierta plana"]
    assert lib.search("atado").groups == []       # no casa dentro de "alicatado"


def test_consulta_vacia_sin_filtros_no_devuelve_nada():
    lib = PartidaLibrary([_line(1, "bajante pvc", 30)])
    assert lib.search("").groups == []
    assert [g.concepto_norm for g in lib.search("", module="fachada").groups] == ["bajante pvc"]


def test_agrupa_por_concepto_y_unidad_canonica_con_cifras():
    lib = PartidaLibrary([
        _line(1, "bajante pvc", 30, unidad="ml", fecha=date(2026, 1, 10)),
        _line(2, "bajante pvc", 34, unidad="m", status="unreviewed", fecha=date(2026, 3, 1)),
        _line(3, "bajante pvc", 50, unidad="M", status="unreviewed"),
        _line(4, "bajante pvc", 90, unidad="ud"),          # otra unidad: otro grupo
    ])
    grupos = {g.unidad_canon: g for g in lib.search("bajante").groups}
    g = grupos["m"]
    assert len(g.lines) == 3 and g.n_budgets == 3
    assert (g.price_min, g.price_median, g.price_max) == (30, 34, 50)
    assert g.approved_median == 30
    assert g.status == "approved"
    assert g.fecha == date(2026, 3, 1)
    assert (g.proposed_price, g.price_basis) == (30, "median_approved")
    assert g.warnings == ()


def test_sin_aprobadas_propone_la_mediana_de_todas_con_aviso():
    lib = PartidaLibrary([
        _line(1, "picado fachada", 10, status="unreviewed", unidad="p.a."),
        _line(2, "picado fachada", 20, status="unreviewed", unidad="P.A."),
    ])
    g = lib.search("picado").groups[0]
    assert (g.proposed_price, g.price_basis, g.approved_median) == (15, "median_all", None)
    assert WARNING_NO_APPROVED in g.warnings and WARNING_LUMP_SUM in g.warnings


def test_filtros_de_estado_unidad_y_modulo():
    lib = PartidaLibrary([
        _line(1, "pintura escalera", 100, status="approved", unidad="p.a.", module="pintura"),
        _line(2, "pintura fachada", 200, status="ineligible", unidad="m2", module="pintura"),
        _line(3, "pintura techo", 50, status="unreviewed", unidad="m2", module="pintura"),
    ])
    assert {g.concepto_norm for g in lib.search("pintura", status_filter="approved").groups} == {"pintura escalera"}
    assert {g.concepto_norm for g in lib.search("pintura", status_filter="no_ineligible").groups} == {
        "pintura escalera", "pintura techo"}
    assert {g.concepto_norm for g in lib.search("pintura", unit="m2").groups} == {"pintura fachada", "pintura techo"}
    assert lib.search("pintura", module="fachada").groups == []


def test_orden_aprobadas_primero_luego_obras_y_fecha():
    lib = PartidaLibrary([
        _line(1, "sellado junta a", 10, status="unreviewed", budget=1),
        _line(2, "sellado junta a", 11, status="unreviewed", budget=2),
        _line(3, "sellado junta b", 12, status="approved", budget=3),
        _line(4, "sellado junta c", 13, status="unreviewed", budget=4, fecha=date(2026, 5, 1)),
    ])
    assert [g.concepto_norm for g in lib.search("sellado").groups] == [
        "sellado junta b",   # evidencia aprobada
        "sellado junta a",   # 2 obras
        "sellado junta c",   # 1 obra, con fecha
    ]


def test_limite_de_grupos():
    lib = PartidaLibrary([_line(i, f"partida {i:03d}", 10) for i in range(250)])
    result = lib.search("partida")
    assert len(result.groups) == 200 and result.total_groups == 250 and result.truncated
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library.py`
Expected: FAIL `ImportError: cannot import name 'WARNING_LUMP_SUM'`

- [ ] **Step 3: Write minimal implementation** (añadir a `src/core/partida_library.py`; los imports nuevos van a la cabecera)

```python
import statistics
from collections import Counter, defaultdict
from dataclasses import field
from typing import Tuple

from src.core.work_type_normalizer import keyword_in_text

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
```

Y el método de `PartidaLibrary`:

```python
    def search(self, query: str = "", module: str = "", unit: str = "",
               status_filter: str = "all", limit: int = MAX_GROUPS) -> SearchResult:
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library.py`
Expected: PASS (todos)

- [ ] **Step 5: Commit**

```bash
git add src/core/partida_library.py tests/test_partida_library.py
git commit -m "feat(biblioteca): búsqueda multipalabra, agrupación con mediana y orden por evidencia"
```

**Validación H3:** la búsqueda usa las mismas reglas que el clasificador (inicio de palabra), y el precio propuesto nunca da prioridad a la mediana de no aprobadas cuando hay aprobadas.

---

### Task 4 (H4): conversión a candidata y paso por el flujo unificado

**Files:**
- Modify: `src/core/partida_library.py`
- Test: `tests/test_partida_library.py`

**Interfaces:**
- Consumes: Task 3.
- Produces: `to_candidate(group: LibraryGroup, line: Optional[LibraryLine] = None) -> Dict` con las claves `titulo, descripcion, concepto, unidad, cantidad, precio_unitario, source ("library"), library_status, library_price_basis ("median_approved"|"median_all"|"instance"), library_partida_ids, library_budget_ids`.

- [ ] **Step 1: Write the failing tests**

```python
from src.core.partida_library import to_candidate
from src.core.services.budget_partidas_flow import MODE_APPEND, split_generated_partidas_for_review


def _grupo_bajante():
    lines = [
        LibraryLine(1, 10, "001-26", "SUSTITUCIÓN BAJANTE PVC.\nSustitución de bajante de PVC de 110 mm",
                    "sustitucion bajante pvc", "ml", "m", 30.0, "approved", date(2026, 1, 1), "sustitucion_bajante"),
        LibraryLine(2, 11, "002-26", "Bajante PVC", "sustitucion bajante pvc", "m", "m", 34.0, "unreviewed",
                    date(2026, 3, 1), "sustitucion_bajante"),
    ]
    return PartidaLibrary(lines).search("bajante").groups[0]


def test_candidata_con_la_mediana_del_grupo():
    c = to_candidate(_grupo_bajante())
    assert c["titulo"] == "SUSTITUCIÓN BAJANTE PVC."
    assert c["descripcion"] == "Sustitución de bajante de PVC de 110 mm"
    assert c["unidad"] == "ml" and c["cantidad"] == 1.0
    assert c["precio_unitario"] == 30.0
    assert c["source"] == "library"
    assert c["library_status"] == "approved"
    assert c["library_price_basis"] == "median_approved"
    assert c["library_partida_ids"] == [1, 2] and c["library_budget_ids"] == [10, 11]


def test_candidata_con_el_precio_de_una_obra_concreta():
    grupo = _grupo_bajante()
    obra = [l for l in grupo.lines if l.partida_id == 2][0]
    c = to_candidate(grupo, obra)
    assert c["precio_unitario"] == 34.0
    assert c["library_price_basis"] == "instance"
    assert c["library_status"] == "unreviewed"
    assert c["titulo"] == "Bajante PVC" and c["descripcion"] == ""
    assert c["library_partida_ids"] == [2]


def test_candidatas_de_biblioteca_no_cuentan_como_historicas():
    historicas, otras = split_generated_partidas_for_review([to_candidate(_grupo_bajante())], "create")
    assert historicas == [] and len(otras) == 1


def test_en_modo_anadir_se_descarta_el_duplicado_exacto():
    candidata = to_candidate(_grupo_bajante())
    existente = dict(candidata)
    historicas, otras = split_generated_partidas_for_review(
        [candidata], MODE_APPEND, existing_partidas=[existente]
    )
    assert historicas == [] and otras == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library.py -k candidat`
Expected: FAIL `ImportError: cannot import name 'to_candidate'`

- [ ] **Step 3: Write minimal implementation**

```python
def to_candidate(group: LibraryGroup, line: Optional[LibraryLine] = None) -> Dict:
    """Partida candidata para la revisión. Nunca lleva un source 'historical*'."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library.py tests/test_historical_suggestions_dedupe.py tests/test_budget_partidas_flow.py`
Expected: PASS. Si `test_en_modo_anadir_se_descarta_el_duplicado_exacto` falla porque la clave de duplicado usa campos que la candidata no rellena, revisa `dedupe_key` en `src/core/historical_suggestions_dedupe.py` y ajusta **la candidata** (no la deduplicación) para que rellene esos campos.

- [ ] **Step 5: Commit**

```bash
git add src/core/partida_library.py tests/test_partida_library.py
git commit -m "feat(biblioteca): convertir grupos en candidatas con procedencia propia"
```

**Validación H4:** el núcleo está completo y probado sin interfaz; ninguna candidata se clasifica como evidencia histórica.

---

### Task 5 (H5): la revisión acepta partidas de biblioteca

**Files:**
- Modify: `src/gui/combined_partidas_review_dialog.py` (constructor, `_build_rows`, tooltip de `_populate`)
- Test: `tests/test_partida_library_gui.py`

**Interfaces:**
- Consumes: Task 4 (`to_candidate`, `STATUS_LABELS`).
- Produces: `CombinedPartidasReviewDialog(parent, historical_partidas=None, ai_partidas=None, merge_duplicates_note="", cobertura=None, library_partidas=None)`; las filas de biblioteca tienen `row["origin"] == "Biblioteca · <estado>"`.

- [ ] **Step 1: Write the failing test**

```python
"""Tests offscreen de la biblioteca de partidas en la interfaz."""

from datetime import date

import pytest

try:
    from PySide6.QtWidgets import QMessageBox

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")

from src.core.partida_library import LibraryLine, PartidaLibrary, to_candidate


def _library():
    return PartidaLibrary([
        LibraryLine(1, 10, "001-26 Obra A", "SUSTITUCIÓN BAJANTE PVC.\nSustitución de bajante de 110 mm",
                    "sustitucion bajante pvc", "ml", "m", 30.0, "approved", date(2026, 1, 1), "sustitucion_bajante"),
        LibraryLine(2, 11, "002-26 Obra B", "Bajante PVC", "sustitucion bajante pvc", "m", "m", 34.0,
                    "unreviewed", None, "sustitucion_bajante"),
        LibraryLine(3, 12, "003-26 Obra C", "Pintura escalera", "pintura escalera", "p.a.", "p.a.", 700.0,
                    "unreviewed", None, "pintura"),
    ])


def test_revision_etiqueta_las_partidas_de_biblioteca(qapp):
    from src.gui.combined_partidas_review_dialog import CombinedPartidasReviewDialog

    grupo = _library().search("bajante").groups[0]
    dlg = CombinedPartidasReviewDialog(None, library_partidas=[to_candidate(grupo)])

    assert [r["origin"] for r in dlg._rows] == ["Biblioteca · aprobada"]
    assert dlg._rows[0]["raw"]["source"] == "library"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library_gui.py`
Expected: FAIL `TypeError: ... unexpected keyword argument 'library_partidas'`

- [ ] **Step 3: Implement**

En el constructor, añade el parámetro y guárdalo:

```python
    def __init__(
        self,
        parent,
        historical_partidas=None,
        ai_partidas=None,
        merge_duplicates_note: str = "",
        cobertura=None,
        library_partidas=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Revisión final de partidas")
        self._historical_partidas = historical_partidas or []
        self._ai_partidas = ai_partidas or []
        self._library_partidas = library_partidas or []
```

Al final de `_build_rows`, añade:

```python
        from src.core.partida_library import STATUS_LABELS

        for partida in self._library_partidas:
            raw = dict(partida or {})
            raw.setdefault("source", "library")
            estado = STATUS_LABELS.get(raw.get("library_status", ""), "sin revisar")
            self._rows.append(
                {"origin": f"Biblioteca · {estado}", "raw": raw, "partida": normalize_partida_for_excel(raw)}
            )
```

En `_populate`, sustituye la construcción del `tooltip` por:

```python
                base = {
                    "median_approved": "mediana de obras aprobadas",
                    "median_all": "mediana de todas las obras (sin evidencia aprobada)",
                    "instance": "precio de una obra concreta",
                }.get(row["raw"].get("library_price_basis", ""), "")
                tooltip = (
                    f"Título: {concepto or '-'}\n"
                    f"Descripción: {descripcion or '-'}\n"
                    f"Origen: {origin}\n"
                    + (f"Base del precio: {base}\n" if base else "")
                    + "Usa «Ver procedencia» para el detalle."
                )
```

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library_gui.py tests/test_combined_partidas_review_dialog.py`
Expected: PASS (los tests existentes de la revisión siguen en verde).

- [ ] **Step 5: Commit**

```bash
git add src/gui/combined_partidas_review_dialog.py tests/test_partida_library_gui.py
git commit -m "feat(revisión): aceptar partidas de la biblioteca con su estado y base de precio"
```

**Validación H5:** la revisión existente no cambia para las listas histórica e IA (sus tests siguen en verde).

---

### Task 6 (H6): diálogo de biblioteca

**Files:**
- Create: `src/gui/partida_library_dialog.py`
- Test: `tests/test_partida_library_gui.py`

**Interfaces:**
- Consumes: Tasks 3-4 (`PartidaLibrary`, `SearchResult`, `to_candidate`, `STATUS_LABELS`).
- Produces: `class PartidaLibraryDialog(QDialog)` con `__init__(self, parent=None, library: Optional[PartidaLibrary] = None)`, métodos públicos `set_query(text: str) -> None` (busca sin esperar), `add_group_to_basket(row: int, line: Optional[LibraryLine] = None) -> None`, `get_candidates() -> List[Dict]`, y atributos `_result: SearchResult`, `_basket: List[Dict]`. Si `library` es `None`, se carga con `PartidaLibrary.load()` en segundo plano.

- [ ] **Step 1: Write the failing tests** (añadir a `tests/test_partida_library_gui.py`)

```python
def test_dialogo_busca_y_devuelve_la_cesta(qapp):
    from src.gui.partida_library_dialog import PartidaLibraryDialog

    dlg = PartidaLibraryDialog(None, library=_library())
    dlg.set_query("bajante")
    assert len(dlg._result.groups) == 1

    dlg.add_group_to_basket(0)
    dlg.accept()
    candidatas = dlg.get_candidates()
    assert len(candidatas) == 1 and candidatas[0]["precio_unitario"] == 30.0
    assert candidatas[0]["library_price_basis"] == "median_approved"


def test_dialogo_usar_precio_de_una_obra(qapp):
    from src.gui.partida_library_dialog import PartidaLibraryDialog

    dlg = PartidaLibraryDialog(None, library=_library())
    dlg.set_query("bajante")
    obra_b = [l for l in dlg._result.groups[0].lines if l.partida_id == 2][0]
    dlg.add_group_to_basket(0, obra_b)
    dlg.accept()
    assert dlg.get_candidates()[0]["precio_unitario"] == 34.0


def test_dialogo_no_escribe_ni_devuelve_nada_al_cancelar(qapp):
    from src.gui.partida_library_dialog import PartidaLibraryDialog

    dlg = PartidaLibraryDialog(None, library=_library())
    dlg.set_query("bajante")
    dlg.add_group_to_basket(0)
    dlg.reject()
    assert dlg.get_candidates() == []


def test_dialogo_avisa_si_falla_la_carga(qapp, monkeypatch):
    import src.gui.partida_library_dialog as mod

    def _boom():
        raise RuntimeError("database is locked")

    monkeypatch.setattr(mod.PartidaLibrary, "load", staticmethod(_boom))
    monkeypatch.setattr(mod, "run_in_background", lambda work, cb: cb(*_safe(work)))
    dlg = mod.PartidaLibraryDialog(None)
    assert "database is locked" in dlg._status.text()
    assert dlg._result.groups == []


def _safe(work):
    try:
        return True, work()
    except Exception as exc:  # noqa: BLE001
        return False, exc
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library_gui.py -k dialogo`
Expected: FAIL `ModuleNotFoundError: No module named 'src.gui.partida_library_dialog'`

- [ ] **Step 3: Implement** `src/gui/partida_library_dialog.py`

```python
"""Diálogo de la biblioteca de partidas: buscar en el histórico y elegir partidas.

No escribe en el Excel ni en la BD: devuelve candidatas para la revisión.
"""

from typing import Dict, List, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.core.partida_library import (
    STATUS_LABELS, LibraryLine, PartidaLibrary, SearchResult, to_candidate,
)
from src.gui import theme
from src.utils.helpers import run_in_background

_STATUS_COLORS = {"approved": "#2e7d32", "unreviewed": "#b26a00", "ineligible": "#9e9e9e"}
_GROUP_HEADERS = ["Concepto", "Unidad", "Módulo", "Precio propuesto", "Rango", "Obras", "Estado", "Fecha"]
_LINE_HEADERS = ["Obra", "Fecha", "Precio", "Estado", "Texto"]


def _money(value: float) -> str:
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


class PartidaLibraryDialog(QDialog):
    def __init__(self, parent=None, library: Optional[PartidaLibrary] = None):
        super().__init__(parent)
        self.setWindowTitle("Biblioteca de partidas")
        self.resize(1200, 720)
        self._library: Optional[PartidaLibrary] = library
        self._result = SearchResult([], 0)
        self._basket: List[Dict] = []
        self._accepted = False
        self._build_ui()
        if library is None:
            self._status.setText("Cargando partidas del histórico…")
            run_in_background(PartidaLibrary.load, self._on_loaded)
        else:
            self._on_loaded(True, library)

    # ── Construcción ────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        filtros = QHBoxLayout()
        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Buscar partida (p. ej. «bajante pvc», «imperm cubierta»)")
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._run_search)
        self._search.textChanged.connect(lambda _t: self._timer.start())
        filtros.addWidget(self._search, 3)
        self._module = QComboBox(self)
        self._module.addItem("Todos los módulos", "")
        self._unit = QComboBox(self)
        self._unit.addItem("Todas las unidades", "")
        for u in ("p.a.", "ud", "m2", "m", "m3", "kg", "día", "?"):
            self._unit.addItem(u, u)
        self._estado = QComboBox(self)
        self._estado.addItem("Todas", "all")
        self._estado.addItem("Solo aprobadas", "approved")
        self._estado.addItem("Sin las no aptas", "no_ineligible")
        for combo in (self._module, self._unit, self._estado):
            combo.currentIndexChanged.connect(lambda _i: self._run_search())
            filtros.addWidget(combo, 1)
        lay.addLayout(filtros)

        self._status = QLabel("", self)
        lay.addWidget(self._status)

        split = QSplitter(Qt.Orientation.Vertical, self)
        self._groups = QTableWidget(0, len(_GROUP_HEADERS), split)
        self._groups.setHorizontalHeaderLabels(_GROUP_HEADERS)
        self._groups.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._groups.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._groups.currentCellChanged.connect(lambda r, *_: self._show_detail(r))
        self._groups.cellDoubleClicked.connect(lambda r, _c: self.add_group_to_basket(r))
        detalle = QWidget(split)
        dlay = QVBoxLayout(detalle)
        self._warnings = QLabel("", detalle)
        self._warnings.setWordWrap(True)
        dlay.addWidget(self._warnings)
        self._lines = QTableWidget(0, len(_LINE_HEADERS), detalle)
        self._lines.setHorizontalHeaderLabels(_LINE_HEADERS)
        self._lines.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._lines.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        dlay.addWidget(self._lines)
        botones_detalle = QHBoxLayout()
        btn_grupo = QPushButton("Añadir a la selección", detalle)
        btn_grupo.clicked.connect(lambda: self.add_group_to_basket(self._groups.currentRow()))
        btn_obra = QPushButton("Usar el precio de esta obra", detalle)
        btn_obra.clicked.connect(self._add_selected_line)
        botones_detalle.addWidget(btn_grupo)
        botones_detalle.addWidget(btn_obra)
        botones_detalle.addStretch(1)
        dlay.addLayout(botones_detalle)
        lay.addWidget(split, 1)

        cesta = QHBoxLayout()
        self._basket_list = QListWidget(self)
        self._basket_list.setMaximumHeight(110)
        cesta.addWidget(self._basket_list, 3)
        col = QVBoxLayout()
        btn_quitar = QPushButton("Quitar", self)
        btn_quitar.clicked.connect(self._remove_from_basket)
        self._basket_total = QLabel("", self)
        col.addWidget(btn_quitar)
        col.addWidget(self._basket_total)
        col.addStretch(1)
        cesta.addLayout(col, 1)
        lay.addLayout(cesta)

        acciones = QHBoxLayout()
        acciones.addStretch(1)
        btn_cancel = QPushButton("Cancelar", self)
        btn_cancel.clicked.connect(self.reject)
        self._btn_ok = QPushButton("Continuar a la revisión (0)", self)
        self._btn_ok.setProperty("class", "primary")
        self._btn_ok.setEnabled(False)
        self._btn_ok.clicked.connect(self.accept)
        acciones.addWidget(btn_cancel)
        acciones.addWidget(self._btn_ok)
        lay.addLayout(acciones)

    # ── Carga y búsqueda ────────────────────────────────────────────────

    def _on_loaded(self, ok, payload):
        if not ok:
            self._library = PartidaLibrary([])
            self._status.setText(f"No se pudo cargar el histórico: {payload}")
            return
        self._library = payload
        modules = sorted({l.module for l in payload.lines if l.module})
        for m in modules:
            self._module.addItem(m, m)
        aviso = f" ({payload.ignored} líneas ignoradas por datos incompletos)" if payload.ignored else ""
        self._status.setText(f"{len(payload.lines)} partidas con precio cargadas{aviso}. Escribe para buscar.")

    def set_query(self, text: str) -> None:
        self._search.blockSignals(True)
        self._search.setText(text)
        self._search.blockSignals(False)
        self._run_search()

    def _run_search(self):
        if self._library is None:
            return
        self._result = self._library.search(
            self._search.text(),
            module=self._module.currentData() or "",
            unit=self._unit.currentData() or "",
            status_filter=self._estado.currentData() or "all",
        )
        self._fill_groups()
        if self._result.truncated:
            self._status.setText(
                f"Se muestran {len(self._result.groups)} de {self._result.total_groups} grupos: afina la búsqueda."
            )
        elif not self._result.groups and (self._search.text().strip() or self._module.currentData()):
            self._status.setText("Sin resultados. Prueba con menos palabras o quitando filtros.")
        else:
            self._status.setText(f"{len(self._result.groups)} grupos.")

    def _fill_groups(self):
        self._groups.setRowCount(len(self._result.groups))
        for i, g in enumerate(self._result.groups):
            rango = _money(g.price_min) if g.price_min == g.price_max else f"{_money(g.price_min)} – {_money(g.price_max)}"
            valores = [
                g.representative.concepto.split("\n")[0], g.unidad_canon, g.module, _money(g.proposed_price),
                rango, str(g.n_budgets), STATUS_LABELS[g.status], g.fecha.strftime("%d/%m/%Y") if g.fecha else "",
            ]
            for c, v in enumerate(valores):
                item = QTableWidgetItem(v)
                if c == 6:
                    item.setForeground(QColor(_STATUS_COLORS[g.status]))
                self._groups.setItem(i, c, item)
        self._lines.setRowCount(0)
        self._warnings.setText("")

    def _show_detail(self, row: int):
        if not (0 <= row < len(self._result.groups)):
            return
        g = self._result.groups[row]
        self._warnings.setText(" · ".join(g.warnings))
        self._lines.setRowCount(len(g.lines))
        for i, l in enumerate(g.lines):
            valores = [l.proyecto, l.fecha.strftime("%d/%m/%Y") if l.fecha else "", _money(l.precio),
                       STATUS_LABELS[l.status], l.concepto.replace("\n", " ")]
            for c, v in enumerate(valores):
                self._lines.setItem(i, c, QTableWidgetItem(v))

    # ── Cesta ───────────────────────────────────────────────────────────

    def add_group_to_basket(self, row: int, line: Optional[LibraryLine] = None) -> None:
        if not (0 <= row < len(self._result.groups)):
            return
        candidata = to_candidate(self._result.groups[row], line)
        self._basket.append(candidata)
        self._basket_list.addItem(
            f"{candidata['titulo'] or candidata['concepto']} — {_money(candidata['precio_unitario'])} / {candidata['unidad']}"
        )
        self._refresh_basket()

    def _add_selected_line(self):
        row, line_row = self._groups.currentRow(), self._lines.currentRow()
        if 0 <= row < len(self._result.groups) and 0 <= line_row < len(self._result.groups[row].lines):
            self.add_group_to_basket(row, self._result.groups[row].lines[line_row])

    def _remove_from_basket(self):
        i = self._basket_list.currentRow()
        if 0 <= i < len(self._basket):
            self._basket.pop(i)
            self._basket_list.takeItem(i)
            self._refresh_basket()

    def _refresh_basket(self):
        total = sum(c["precio_unitario"] for c in self._basket)
        self._basket_total.setText(f"{len(self._basket)} partidas · {_money(total)} (cantidad 1)")
        self._btn_ok.setText(f"Continuar a la revisión ({len(self._basket)})")
        self._btn_ok.setEnabled(bool(self._basket))

    # ── Resultado ───────────────────────────────────────────────────────

    def accept(self):
        self._accepted = True
        super().accept()

    def get_candidates(self) -> List[Dict]:
        return list(self._basket) if self._accepted else []
```

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library_gui.py`
Expected: PASS (el contrato es: sin aceptar, `get_candidates()` devuelve `[]`).

- [ ] **Step 5: Commit**

```bash
git add src/gui/partida_library_dialog.py tests/test_partida_library_gui.py
git commit -m "feat(biblioteca): diálogo de búsqueda con detalle por obra y cesta"
```

**Validación H6:** abrir el diálogo con la BD real (`.venv/Scripts/python.exe -c "from PySide6.QtWidgets import QApplication; app=QApplication([]); from src.gui.partida_library_dialog import PartidaLibraryDialog; d=PartidaLibraryDialog(); d.exec()"`), buscar "bajante pvc", ver el detalle, añadir dos partidas y comprobar que "Cancelar" no devuelve nada.

---

### Task 7 (H7): integración en el dashboard

**Files:**
- Modify: `src/gui/budget_dashboard.py` (menú de edición ~línea 1239; nuevo método junto a `_edit_add_partidas`)
- Test: `tests/test_partida_library_gui.py`

**Interfaces:**
- Consumes: Tasks 5-6; `BudgetService.read_budget`, `split_generated_partidas_for_review`, `apply_reviewed_partidas`, `MODE_APPEND`.
- Produces: `BudgetDashboardFrame._edit_add_from_library(self, ruta: str) -> None`.

- [ ] **Step 1: Write the failing test**

```python
def test_dashboard_anade_desde_la_biblioteca_sin_duplicados(qapp, monkeypatch):
    import src.gui.budget_dashboard as bd
    from src.core import services

    grupo = _library().search("bajante").groups[0]
    candidata = to_candidate(grupo)
    otra = to_candidate(_library().search("pintura").groups[0])
    escritas = []

    class _FakeService:
        def read_budget(self, ruta):
            return {"partidas": [dict(candidata)]}          # la bajante ya está en el Excel

        def append_partidas(self, ruta, partidas):
            escritas.extend(partidas); return True

        def finalize_budget(self, ruta, estado=""):
            return True

    class _FakeLibraryDialog:
        def __init__(self, parent=None, library=None): pass
        def exec(self): return 1
        def get_candidates(self): return [candidata, otra]

    class _FakeReview:
        def __init__(self, parent, library_partidas=None, **kw):
            self._p = library_partidas
        def exec(self): return 1
        def get_selected_partidas(self): return self._p

    monkeypatch.setattr(services, "BudgetService", _FakeService)
    monkeypatch.setattr("src.gui.partida_library_dialog.PartidaLibraryDialog", _FakeLibraryDialog)
    monkeypatch.setattr("src.gui.combined_partidas_review_dialog.CombinedPartidasReviewDialog", _FakeReview)
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    dash = bd.BudgetDashboardFrame.__new__(bd.BudgetDashboardFrame)
    dash._current_state = lambda: "PRESUPUESTADO"
    dash._load_data = lambda: None
    bd.BudgetDashboardFrame._edit_add_from_library(dash, "C:/obra/p.xlsx")

    assert [p["titulo"] for p in escritas] == ["Pintura escalera"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library_gui.py -k dashboard`
Expected: FAIL `AttributeError: ... '_edit_add_from_library'`

- [ ] **Step 3: Implement**

En el menú de edición, tras `act_add = menu.addAction("Añadir más partidas (IA)")`:

```python
        act_lib = menu.addAction("Añadir partidas desde la biblioteca")
        act_lib.triggered.connect(lambda: self._edit_add_from_library(ruta))
```

Nuevo método, junto a `_edit_add_partidas`:

```python
    def _edit_add_from_library(self, ruta):
        """Añade partidas elegidas en la biblioteca, sin duplicados, tras revisarlas."""
        from src.core.services import BudgetService
        from src.core.services.budget_partidas_flow import (
            MODE_APPEND, apply_reviewed_partidas, split_generated_partidas_for_review,
        )
        from src.gui import combined_partidas_review_dialog as review_mod
        from src.gui import partida_library_dialog as library_mod

        svc = BudgetService()
        existing_partidas = (svc.read_budget(ruta) or {}).get("partidas", []) or []
        dlg = library_mod.PartidaLibraryDialog(self)
        if dlg.exec() != 1 or not dlg.get_candidates():
            return
        _hist, candidatas = split_generated_partidas_for_review(
            dlg.get_candidates(), MODE_APPEND, existing_partidas=existing_partidas
        )
        if not candidatas:
            QMessageBox.information(self, "Biblioteca", "Todas las partidas elegidas ya están en el presupuesto.")
            return
        review = review_mod.CombinedPartidasReviewDialog(self, library_partidas=candidatas)
        if review.exec() != 1:
            return
        selected = review.get_selected_partidas()
        if not selected:
            return
        if apply_reviewed_partidas(svc, ruta, selected, MODE_APPEND):
            svc.finalize_budget(ruta, estado=self._current_state() or "")
            QMessageBox.information(self, "Éxito", f"{len(selected)} partidas añadidas.")
            self._load_data()
        else:
            QMessageBox.critical(self, "Error", "Error al añadir partidas.")
```

Nota: se accede a las clases a través del módulo (`review_mod.CombinedPartidasReviewDialog`) para que el test pueda sustituirlas.

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library_gui.py tests/test_gui_late_results.py tests/test_gui_module_syntax.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/gui/budget_dashboard.py tests/test_partida_library_gui.py
git commit -m "feat(dashboard): añadir partidas desde la biblioteca sin duplicados"
```

**Validación H7:** suite completa en verde (`QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider`).

---

### Task 8 (H8): integración al crear un presupuesto

**Files:**
- Modify: `src/gui/main_frame.py` (`_create_budget`, línea con `outcome = self._offer_partidas_unified(...)`; nuevo método `_offer_partidas_from_library`)
- Test: `tests/test_partida_library_gui.py`

**Interfaces:**
- Consumes: Tasks 5-6; `MainFrame._insert_final_partidas_once(excel_path, selected, project_data) -> str`; constantes `OUTCOME_*`.
- Produces: `MainFrame._choose_partidas_source(self) -> str` (`"library" | "ai" | "empty"`) y `MainFrame._offer_partidas_from_library(self, excel_path: str, project_data: dict) -> str` (devuelve un `OUTCOME_*`).

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.parametrize("eleccion,esperado", [("library", "lib"), ("ai", "ai"), ("empty", "cancelled")])
def test_crear_elige_biblioteca_ia_o_vacio(qapp, monkeypatch, eleccion, esperado):
    import src.gui.main_frame as mf

    frame = mf.MainFrame.__new__(mf.MainFrame)
    frame._choose_partidas_source = lambda: eleccion
    frame._offer_partidas_from_library = lambda excel, pd: "lib"
    frame._offer_partidas_unified = lambda excel, pd: "ai"

    assert mf.MainFrame._offer_partidas_for_new_budget(frame, "C:/obra/p.xlsx", {}) == esperado


def test_biblioteca_al_crear_pasa_por_la_revision_y_escribe(qapp, monkeypatch):
    import src.gui.main_frame as mf

    candidata = to_candidate(_library().search("bajante").groups[0])

    class _FakeLibraryDialog:
        def __init__(self, parent=None, library=None): pass
        def exec(self): return 1
        def get_candidates(self): return [candidata]

    class _FakeReview:
        def __init__(self, parent, library_partidas=None, **kw): self._p = library_partidas
        def exec(self): return 1
        def get_selected_partidas(self): return self._p

    monkeypatch.setattr("src.gui.partida_library_dialog.PartidaLibraryDialog", _FakeLibraryDialog)
    monkeypatch.setattr("src.gui.combined_partidas_review_dialog.CombinedPartidasReviewDialog", _FakeReview)
    escritas = []
    frame = mf.MainFrame.__new__(mf.MainFrame)
    frame._insert_final_partidas_once = lambda excel, sel, pd: escritas.extend(sel) or "applied"

    assert mf.MainFrame._offer_partidas_from_library(frame, "C:/obra/p.xlsx", {}) == "applied"
    assert escritas == [candidata]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library_gui.py -k crear`
Expected: FAIL `AttributeError: ... '_offer_partidas_for_new_budget'`

- [ ] **Step 3: Implement** en `src/gui/main_frame.py`

Sustituye `outcome = self._offer_partidas_unified(result.excel_path, project_data)` por:

```python
        outcome = self._offer_partidas_for_new_budget(result.excel_path, project_data)
```

Y añade los tres métodos junto a `_offer_partidas_unified`:

```python
    def _choose_partidas_source(self) -> str:
        """Pregunta cómo añadir las partidas: biblioteca, IA o dejar vacío."""
        box = QMessageBox(self)
        box.setWindowTitle("Partidas del presupuesto")
        box.setText("¿Cómo quieres añadir las partidas?")
        btn_lib = box.addButton("Elegir de la biblioteca", QMessageBox.ButtonRole.AcceptRole)
        btn_ai = box.addButton("Generar con IA", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Dejar vacío", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(btn_lib)
        box.exec()
        clicked = box.clickedButton()
        if clicked is btn_lib:
            return "library"
        if clicked is btn_ai:
            return "ai"
        return "empty"

    def _offer_partidas_for_new_budget(self, excel_path, project_data) -> str:
        source = self._choose_partidas_source()
        if source == "library":
            return self._offer_partidas_from_library(excel_path, project_data)
        if source == "ai":
            return self._offer_partidas_unified(excel_path, project_data)
        return OUTCOME_CANCELLED

    def _offer_partidas_from_library(self, excel_path, project_data) -> str:
        from src.gui import combined_partidas_review_dialog as review_mod
        from src.gui import partida_library_dialog as library_mod

        dlg = library_mod.PartidaLibraryDialog(self)
        if dlg.exec() != 1 or not dlg.get_candidates():
            return OUTCOME_CANCELLED
        review = review_mod.CombinedPartidasReviewDialog(self, library_partidas=dlg.get_candidates())
        if review.exec() != 1:
            return OUTCOME_CANCELLED
        selected = review.get_selected_partidas()
        if not selected:
            return OUTCOME_EMPTY
        return self._insert_final_partidas_once(excel_path, selected, project_data)
```

`OUTCOME_CANCELLED` y `OUTCOME_EMPTY` ya se importan en `main_frame.py` desde `budget_partidas_flow`. "Dejar vacío" devuelve `OUTCOME_CANCELLED`, el mismo resultado que hoy da "Saltar" en el flujo de IA, así que `_handle_unfinished_budget` sigue ofreciendo conservar o descartar el borrador.

- [ ] **Step 4: Run tests**

Run: `QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider tests/test_partida_library_gui.py tests/test_budget_destination_contract.py tests/test_gui_late_results.py`
Expected: PASS. Si `tests/test_budget_destination_contract.py` falla porque su `_build_gui_frame` no espera la nueva pregunta, añade en ese helper `frame._choose_partidas_source = lambda: "ai"` para conservar el comportamiento que prueba.

- [ ] **Step 5: Commit**

```bash
git add src/gui/main_frame.py tests/test_partida_library_gui.py tests/test_budget_destination_contract.py
git commit -m "feat(crear): elegir biblioteca, IA o dejar vacío al crear un presupuesto"
```

**Validación H8:** suite completa en verde.

---

### Task 9 (H9): validación con datos reales y documentación

**Files:**
- Create: `scripts/library_benchmark.py`
- Modify: `docs/README.md`, `docs/decisiones-pendientes.md`

**Interfaces:**
- Consumes: `PartidaLibrary.load`, `PartidaLibrary.search`.

- [ ] **Step 1: Crear el script de validación (solo lectura)**

```python
"""Validación de la biblioteca de partidas con una BD real, en solo lectura.

Uso: .venv/Scripts/python.exe scripts/library_benchmark.py --db <ruta a datos.db>
"""

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REFERENCIAS = ("bajante pvc", "impermeabilizacion cubierta", "picado fachada", "tirar tabique")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    args = parser.parse_args(argv)
    os.environ["CUBIAPP_DB_PATH"] = str(Path(args.db).resolve())
    from src.core.partida_library import PartidaLibrary

    t0 = time.perf_counter()
    lib = PartidaLibrary.load()
    carga = time.perf_counter() - t0
    print(f"carga: {len(lib.lines)} líneas, {lib.ignored} ignoradas, {carga:.2f} s")
    ok = carga < 3.0
    for q in REFERENCIAS:
        t0 = time.perf_counter()
        res = lib.search(q)
        ms = (time.perf_counter() - t0) * 1000
        top = res.groups[0] if res.groups else None
        resumen = f"{top.concepto_norm[:60]} | {top.proposed_price:.2f} ({top.price_basis})" if top else "-"
        print(f"{q!r}: {res.total_groups} grupos, {ms:.0f} ms | primero: {resumen}")
        ok = ok and ms < 200 and res.total_groups > 0
    print("OK" if ok else "FALLA: revisar tiempos o búsquedas sin resultados")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Ejecutarlo sobre una copia de la BD real**

```bash
cp "C:/Users/cayet/Documents/CubiApp/datos.db" "$SCRATCH/biblioteca.db"
.venv/Scripts/python.exe scripts/library_benchmark.py --db "$SCRATCH/biblioteca.db"
```

Expected: `carga: ~17000 líneas ... < 3 s`, cada referencia con > 0 grupos y < 200 ms, y `OK`. Si algún tiempo se pasa, perfila `PartidaLibrary.search` antes de seguir (la causa probable es `keyword_in_text` sobre todas las líneas; se puede precalcular un índice de palabras por línea).

- [ ] **Step 3: Prueba manual en la app**

1. Crear un presupuesto → "Elegir de la biblioteca" → buscar "bajante pvc" → añadir el grupo y el precio de una obra concreta → revisión → aceptar. Abrir el Excel: dos partidas con esos precios.
2. Dashboard → presupuesto existente → "Añadir partidas desde la biblioteca" → elegir una partida que ya esté en el Excel y otra nueva: solo se añade la nueva.
3. Cancelar en la biblioteca y en la revisión: el Excel no cambia.

- [ ] **Step 4: Documentación**

En `docs/README.md`, en "Planes pendientes", añade:

```markdown
| [`superpowers/plans/2026-11-12-biblioteca-partidas.md`](superpowers/plans/2026-11-12-biblioteca-partidas.md) | Mejora 1 de 4 de la batería de redacción (biblioteca de partidas). |
```

En `docs/decisiones-pendientes.md`, añade al final de la sección 3 ("Vocabulario que ha quedado a la vista"):

```markdown
- **Biblioteca de partidas**: medir con el uso real si los grupos por concepto
  normalizado exacto se quedan cortos (variantes de redacción de la misma
  partida) antes de diseñar la mejora 2.
```

- [ ] **Step 5: Commit**

```bash
git add scripts/library_benchmark.py docs/README.md docs/decisiones-pendientes.md
git commit -m "test(biblioteca): validación con datos reales y documentación"
```

**Validación H9:** el benchmark imprime `OK` sobre la copia de la BD real, la prueba manual sale bien y la suite completa está en verde.
