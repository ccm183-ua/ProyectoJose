# Completar la revision del vocabulario cerrado (8 familias) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task (NOT subagent-driven-development — Task 3 requires a live, synchronous decision from the human user that a background subagent cannot obtain). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar las ocho revisiones de vocabulario cerrado que
`docs/criterios-clasificacion-partidas.md` dejo pendientes (cerrajeria,
impermeabilizacion, demolicion, alicatado, estructura, carpinteria,
albanileria, sustitucion_bajante), con el mismo metodo ya usado para
pintura/gestion_residuos/fachada: ejemplo real -> decision del usuario con
motivo -> codigo -> test de regresion -> verificacion medida -> commit.

**Architecture:** Un script de solo lectura (`scripts/historical_vocabulary_gap_report.py`)
identifica, por familia, que lineas reales del historico no tienen ficha
completa (`action`/`element` vacios) y con que frecuencia se repiten. Con
ese informe, el usuario decide categoria por categoria en conversacion
directa (Task 3 no es automatizable: requiere una decision humana por
patron, ver spec). Las decisiones se documentan en el mismo fichero que ya
existe y se prueban con el texto real, nunca inventado.

**Tech Stack:** Python 3.10, sqlite3 (via `src.core.database`), pytest.

## Global Constraints

- Las ocho familias son: `cerrajeria`, `impermeabilizacion`, `demolicion`,
  `alicatado`, `estructura`, `carpinteria`, `albanileria`,
  `sustitucion_bajante` (nombres exactos de `execution_module.nombre`).
- Una familia por turno, con cierre completo (documento + codigo + test +
  commit) antes de pasar a la siguiente.
- Orden no fijado de antemano: se decide con el informe de impacto de cada
  turno (Task 2 da el orden inicial; se puede re-priorizar tras cada
  cierre).
- Ningun caso ambiguo se fuerza: se anota "sin decision, revisar mas
  adelante" y se continua.
- Cada decision se prueba con el texto real de un ejemplo del historico
  (columna `concepto_original`), nunca un caso inventado.
- Tras cada commit de familia: suite completa de tests, y comparacion del
  numero total de patrones antes/despues contra la base real de
  produccion. Si el total baja, se para y se revisa con el usuario antes
  de comitear.
- Sin meta numerica de patrones fijada de antemano.
- Fuera de alcance: el validador formal del esquema IA, la investigacion
  de la corrupcion de codificacion en `concepto_original`, cualquier
  cambio a `historical_partida_classifier.py` no respaldado por una
  decision documentada de una de las ocho familias.

---

### Task 1: Informe de impacto por familia (script de solo lectura)

**Files:**
- Create: `src/core/historical_vocabulary_gap_report.py`
- Test: `tests/test_historical_vocabulary_gap_report.py`

**Interfaces:**
- Produces: `rank_families_by_gap(families: List[str]) -> List[Dict]` — cada
  dict `{"familia": str, "total_atomicas": int, "sin_ficha_completa": int}`,
  ordenado por `sin_ficha_completa` descendente.
- Produces: `top_unmatched_phrases_for_family(family: str, limit: int = 10) -> List[Dict]`
  — cada dict `{"concepto_normalizado": str, "ejemplo_original": str, "frecuencia": int}`,
  ordenado por `frecuencia` descendente.

- [ ] **Step 1: Escribir el test de `rank_families_by_gap` (falla primero)**

```python
# tests/test_historical_vocabulary_gap_report.py
"""
Tests del informe de impacto por familia (Task 1 del plan
docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md).
"""

from datetime import datetime

from src.core.repositories import (
    assign_partida_module,
    get_or_create_execution_module,
    insert_historical_partida,
    upsert_historical_budget,
    upsert_partida_features,
)
from src.core.historical_vocabulary_gap_report import (
    rank_families_by_gap,
    top_unmatched_phrases_for_family,
)


def _seed(tmp_path, monkeypatch):
    db_path = tmp_path / "datos_gap_test.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))

    mod_alicatado, err = get_or_create_execution_module("alicatado")
    assert err is None
    mod_fachada, err = get_or_create_execution_module("fachada")
    assert err is None

    bid, berr = upsert_historical_budget(
        {
            "ruta_excel": str(tmp_path / "obra.xlsx"),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": "obra",
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "analisis_ok": True,
            "analysis_status": "VALID",
            "usable_for_learning": True,
            "learning_status": "INCLUDED",
        }
    )
    assert berr is None

    def _partida(concepto, unidad, orden):
        pid, perr = insert_historical_partida(
            bid,
            {
                "orden": orden,
                "titulo": concepto[:40],
                "concepto_original": concepto,
                "concepto_normalizado": concepto.lower(),
                "unidad": unidad,
                "precio_unitario": 30.0,
                "cantidad": 1,
                "total_linea": 30.0,
            },
        )
        assert perr is None
        return pid

    # Dos lineas de "alicatado" sin element (misma frase repetida = frecuencia 2).
    for orden in (1, 2):
        pid = _partida("Demolicion de alicatado existente", "m2", orden)
        assign_partida_module(pid, mod_alicatado, 0.9, "rules")
        upsert_partida_features(
            pid,
            {
                "action": "demolish", "element": None, "system": None, "unit": "m2",
                "material": None, "dimensions": (), "conditions": (),
                "line_kind": "atomic", "primary_module_id": "alicatado",
                "secondary_module_ids": (), "confidence": 0.9, "reasons": (),
                "classifier_version": "test",
            },
        )

    # Una linea de "fachada" YA con ficha completa (no debe contar como hueco).
    pid = _partida("Reparacion de grieta en fachada", "m2", 3)
    assign_partida_module(pid, mod_fachada, 0.9, "rules")
    upsert_partida_features(
        pid,
        {
            "action": "repair", "element": "facade", "system": None, "unit": "m2",
            "material": None, "dimensions": (), "conditions": (),
            "line_kind": "atomic", "primary_module_id": "fachada",
            "secondary_module_ids": (), "confidence": 0.9, "reasons": (),
            "classifier_version": "test",
        },
    )

    return db_path


def test_rank_families_by_gap_orders_by_missing_feature_count(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)

    ranking = rank_families_by_gap(["alicatado", "fachada"])

    assert ranking[0]["familia"] == "alicatado"
    assert ranking[0]["sin_ficha_completa"] == 2
    assert ranking[1]["familia"] == "fachada"
    assert ranking[1]["sin_ficha_completa"] == 0


def test_top_unmatched_phrases_groups_by_normalized_text(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)

    phrases = top_unmatched_phrases_for_family("alicatado")

    assert len(phrases) == 1
    assert phrases[0]["frecuencia"] == 2
    assert phrases[0]["ejemplo_original"] == "Demolicion de alicatado existente"


def test_top_unmatched_phrases_excludes_complete_features(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)

    phrases = top_unmatched_phrases_for_family("fachada")

    assert phrases == []
```

- [ ] **Step 2: Ejecutar y comprobar que falla (el modulo no existe todavia)**

Run: `.venv/Scripts/python.exe -m pytest tests/test_historical_vocabulary_gap_report.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'src.core.historical_vocabulary_gap_report'`

- [ ] **Step 3: Implementar el modulo**

```python
# src/core/historical_vocabulary_gap_report.py
"""
Informe de impacto por familia (Task 1 del plan
docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md).

Solo lectura. Identifica, por familia de execution_module, cuantas lineas
atomicas reales del historico no tienen ficha completa (action o element
vacios) y con que frecuencia se repite cada frase normalizada, para
priorizar que familia revisar primero y que ejemplos traer a la revision.
"""

from typing import Dict, List

from src.core import database


def rank_families_by_gap(families: List[str]) -> List[Dict]:
    """Ordena las familias dadas por numero de lineas atomicas sin ficha
    completa (action o element vacios), de mayor a menor impacto."""
    with database.get_connection(read_only=True) as conn:
        rows = conn.execute(
            """SELECT f.primary_module_id,
                      COUNT(*) AS total,
                      SUM(
                          CASE WHEN (f.action IS NULL OR f.action = '')
                                 OR (f.element IS NULL OR f.element = '')
                               THEN 1 ELSE 0 END
                      ) AS sin_ficha_completa
               FROM historical_partida_feature f
               JOIN historical_partida hp ON hp.id = f.partida_id
               JOIN historical_budget hb ON hb.id = hp.historical_budget_id
               WHERE f.primary_module_id IN ({placeholders})
                 AND hb.learning_status = 'INCLUDED'
                 AND hb.analysis_status IN ('VALID', 'VALID_WITH_WARNINGS')
                 AND f.line_kind = 'atomic'
               GROUP BY f.primary_module_id""".format(
                placeholders=",".join("?" for _ in families)
            ),
            tuple(families),
        ).fetchall()

    by_family = {
        row[0]: {"familia": row[0], "total_atomicas": int(row[1]), "sin_ficha_completa": int(row[2] or 0)}
        for row in rows
    }
    ranking = [
        by_family.get(f, {"familia": f, "total_atomicas": 0, "sin_ficha_completa": 0})
        for f in families
    ]
    ranking.sort(key=lambda r: r["sin_ficha_completa"], reverse=True)
    return ranking


def top_unmatched_phrases_for_family(family: str, limit: int = 10) -> List[Dict]:
    """Frases normalizadas mas frecuentes de `family` sin ficha completa,
    con un ejemplo de texto original real por frase."""
    with database.get_connection(read_only=True) as conn:
        rows = conn.execute(
            """SELECT hp.concepto_normalizado,
                      MIN(hp.concepto_original) AS ejemplo_original,
                      COUNT(*) AS frecuencia
               FROM historical_partida_feature f
               JOIN historical_partida hp ON hp.id = f.partida_id
               JOIN historical_budget hb ON hb.id = hp.historical_budget_id
               WHERE f.primary_module_id = ?
                 AND hb.learning_status = 'INCLUDED'
                 AND hb.analysis_status IN ('VALID', 'VALID_WITH_WARNINGS')
                 AND f.line_kind = 'atomic'
                 AND ((f.action IS NULL OR f.action = '')
                      OR (f.element IS NULL OR f.element = ''))
               GROUP BY hp.concepto_normalizado
               ORDER BY frecuencia DESC
               LIMIT ?""",
            (family, limit),
        ).fetchall()

    return [
        {
            "concepto_normalizado": row[0],
            "ejemplo_original": row[1],
            "frecuencia": int(row[2]),
        }
        for row in rows
    ]
```

- [ ] **Step 4: Ejecutar y comprobar que pasa**

Run: `.venv/Scripts/python.exe -m pytest tests/test_historical_vocabulary_gap_report.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/historical_vocabulary_gap_report.py tests/test_historical_vocabulary_gap_report.py
git commit -m "feat(historico): informe de impacto por familia de vocabulario cerrado

Task 1 de docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md.
Solo lectura: rank_families_by_gap ordena familias por lineas atomicas sin
ficha completa; top_unmatched_phrases_for_family trae las frases reales mas
frecuentes de una familia para priorizar la revision con el usuario."
```

---

### Task 2: Ranking inicial de las 8 familias contra la base real

**Files:** ninguno (ejecucion puntual del script de Task 1 contra la base real).

**Interfaces:**
- Consumes: `rank_families_by_gap` de Task 1.

- [ ] **Step 1: Ejecutar el ranking contra `Documents/CubiApp/datos.db`**

```bash
.venv/Scripts/python.exe -c "
from src.core.historical_vocabulary_gap_report import rank_families_by_gap
familias = ['cerrajeria', 'impermeabilizacion', 'demolicion', 'alicatado', 'estructura', 'carpinteria', 'albanileria', 'sustitucion_bajante']
for r in rank_families_by_gap(familias):
    print(r)
"
```

- [ ] **Step 2: Presentar el ranking al usuario y confirmar cual familia se revisa primero**

No es un paso automatizable: se muestra el resultado y se espera
confirmacion explicita del usuario (puede aceptar el orden por impacto o
elegir otra, segun el spec). Esto fija la primera iteracion de Task 3.

---

### Task 3: Turno de familia (procedimiento repetible — una vez por cada una de las 8 familias)

**Se ejecuta 8 veces**, una por familia, en el orden que confirme el
usuario en Task 2 (y se puede re-priorizar tras cada cierre, re-ejecutando
`rank_families_by_gap` sobre las familias que queden). Cada ejecucion
completa de este task es su propio commit.

**Files (por ejecucion):**
- Modify: `src/core/historical_partida_features.py` (`_ACTION_SYNONYMS`,
  `_ELEMENT_SYNONYMS`) o `src/core/historical_partida_classifier.py`
  (`MODULE_RULES`) si el hueco es de deteccion de modulo, no de elemento.
- Modify: `docs/criterios-clasificacion-partidas.md` (nueva Decision N).
- Test: `tests/test_historical_partida_classifier.py::TestReviewedHistoricalCases`
  (anadir un metodo de test por decision).

**Interfaces:**
- Consumes: `top_unmatched_phrases_for_family(family, limit=10)` de Task 1.
- Consumes: `HistoricalBudgetAnalyzer.rebuild_features_and_patterns()`
  (`src/core/historical_budget_analyzer.py`, ya existe).

- [ ] **Step 1: Generar el informe de la familia en curso**

```bash
.venv/Scripts/python.exe -c "
from src.core.historical_vocabulary_gap_report import top_unmatched_phrases_for_family
for p in top_unmatched_phrases_for_family('<FAMILIA>'):
    print(p['frecuencia'], '|', p['ejemplo_original'])
"
```

- [ ] **Step 2: Presentar los patrones al usuario**

Mostrar cada `ejemplo_original` con su frecuencia, agrupados de forma
legible (no solo la lista cruda).

- [ ] **Step 3 (PUNTO DE PARADA — requiere al usuario, no continuar sin esto):**
  **Obtener, para cada patron, la decision del usuario**: accion, elemento,
  modulo principal (si aplica), condicion que impide coincidencia exacta si
  la hay, y el motivo. Si un patron es ambiguo, registrar explicitamente
  "sin decision, revisar mas adelante" en vez de forzar una categoria — y
  excluirlo de los pasos siguientes.

  Este paso no tiene contenido pre-escribible: el codigo de los pasos 4-7
  depende literalmente de lo que decida el usuario aqui. No es un
  placeholder por pereza — es el nucleo de "interaccion humana" que pidio
  el usuario en el spec, y solo puede resolverse en conversacion directa
  con el, dentro de la misma sesion (por eso este plan exige
  `executing-plans`, no `subagent-driven-development`: un subagente en
  background no puede sostener esta conversacion).

- [ ] **Step 4: Anadir la(s) Decision(es) N a `docs/criterios-clasificacion-partidas.md`**

Insertar, a continuacion de la ultima decision existente (Decision 2, en la
seccion "Revision humana del histórico real"), una entrada por cada patron
decidido, con el mismo formato que las dos ya existentes:

```markdown
### Decision N — <resumen corto de la decision>

- **Expresión habitual**: "<ejemplo_original real del Step 1>"
- **Acción**: `<accion decidida>`. **Elemento**: `<elemento decidido>`.
  **Módulo principal**: `<modulo>`.
- **Condición que impide coincidencia exacta**: <la que haya acordado el
  usuario, o "ninguna" si no aplica>.
- **Motivo**: <el motivo tal y como lo dio el usuario en el Step 3>.
- **Implementación**: <que entrada exacta se anadio a que tabla, ver Step 5>.
```

- [ ] **Step 5: Anadir la entrada al vocabulario cerrado**

Si el hueco es de `element` (caso mas comun, ver diagnostico de
`alicatado` en el spec), anadir una tupla a `_ELEMENT_SYNONYMS` en
`src/core/historical_partida_features.py` (respetar el orden: formas
compuestas antes que la generica, igual que `facade_render` antes que
`facade`):

```python
_ELEMENT_SYNONYMS: _KeywordTable = (
    ("facade_render", ("revoco en fachada", "revoco de fachada", "revoco fachada", "enfoscado fachada", "enfoscado de fachada")),
    ("facade", ("fachada",)),
    ("downspout", ("bajante",)),
    ("roof", ("cubierta", "tejado")),
    ("structure", ("estructura", "viga", "pilar", "zuncho")),
    ("door", ("puerta", "portal")),
    ("railing", ("barandilla", "pasamanos")),
    ("<elemento_decidido>", ("<keyword1>", "<keyword2>")),  # <- nueva entrada
)
```

Si el hueco es de `action`, mismo patron sobre `_ACTION_SYNONYMS`. Si el
hueco es de deteccion de **modulo** (el clasificador no asigna ningun
modulo o asigna el equivocado, no que le falte accion/elemento), anadir la
palabra clave a `MODULE_RULES` en
`src/core/historical_partida_classifier.py` siguiendo el patron ya usado
para `"tapado"` en la Decision 2.

- [ ] **Step 6: Escribir el test de regresion con el texto real**

```python
# En tests/test_historical_partida_classifier.py, dentro de
# class TestReviewedHistoricalCases:

def test_decision_n_<resumen_corto>(self):
    classifier = HistoricalPartidaClassifier()
    text = "<ejemplo_original real, tal cual, del Step 1>"
    features = extract_partida_features(text, "<unidad real>", classifier.classify_text(text))
    assert features.action == "<accion decidida>"
    assert features.element == "<elemento decidido>"
    assert features.primary_module_id == "<modulo>"
```

- [ ] **Step 7: Ejecutar el test nuevo**

Run: `.venv/Scripts/python.exe -m pytest tests/test_historical_partida_classifier.py::TestReviewedHistoricalCases -v`
Expected: PASS (incluidos los tests de las Decisiones 1 y 2 ya existentes — no deben romperse)

- [ ] **Step 8: Verificar el impacto medido contra la base real**

```bash
.venv/Scripts/python.exe -c "
from src.core import database
from src.core.historical_budget_analyzer import HistoricalBudgetAnalyzer
with database.get_connection(read_only=True) as conn:
    antes = conn.execute('SELECT COUNT(*) FROM suggested_partida_pattern').fetchone()[0]
result = HistoricalBudgetAnalyzer().rebuild_features_and_patterns()
with database.get_connection(read_only=True) as conn:
    despues = conn.execute('SELECT COUNT(*) FROM suggested_partida_pattern').fetchone()[0]
print('patrones antes:', antes, '| despues:', despues, '| resultado:', result)
"
```

Si `despues < antes`: **no continuar** — parar y revisar con el usuario
antes del Step 9. Esto no deberia pasar si el Step 5 solo anadio entradas
nuevas sin tocar las existentes, pero es la comprobacion que exige la red
de seguridad del spec.

- [ ] **Step 9: Suite completa**

Run: `.venv/Scripts/python.exe -m pytest -q --ignore=tests/api`
Expected: todos los tests pasan (0 failed)

- [ ] **Step 10: Commit de la familia**

```bash
git add docs/criterios-clasificacion-partidas.md src/core/historical_partida_features.py tests/test_historical_partida_classifier.py
git commit -m "feat(historico): revisar vocabulario cerrado de la familia <FAMILIA>

Decision(es) N<->N+k de docs/criterios-clasificacion-partidas.md, revisadas
con el usuario sobre <n> patrones reales de mayor frecuencia (informe de
Task 1). Patrones: <antes> -> <despues>.

Task 3 (turno <k> de 8) de
docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md."
```

(Si el Step 5 toco `historical_partida_classifier.py` en vez de
`historical_partida_features.py`, ajustar el `git add` en consecuencia.)

---

### Task 4: Cierre del conjunto

**Files:** ninguno (verificacion y resumen final, tras las 8 ejecuciones de Task 3).

- [ ] **Step 1: Confirmar que las 8 familias tienen su commit**

```bash
git log --oneline --grep="Task 3 (turno"
```

Expected: 8 commits (uno por familia, puede haber menos de 8 "Decision N"
si alguna familia se cerro con todos sus patrones marcados "sin decision").

- [ ] **Step 2: Medir el efecto conjunto contra la base real**

```bash
.venv/Scripts/python.exe -c "
from src.core import database
with database.get_connection(read_only=True) as conn:
    patrones = conn.execute('SELECT COUNT(*) FROM suggested_partida_pattern').fetchone()[0]
    con_ficha = conn.execute(\"SELECT COUNT(*) FROM historical_partida_feature WHERE line_kind='atomic' AND action IS NOT NULL AND action<>'' AND element IS NOT NULL AND element<>''\").fetchone()[0]
print('patrones totales:', patrones, '| lineas atomicas con ficha completa:', con_ficha)
"
```

- [ ] **Step 3: Presentar el resumen antes/despues al usuario**

Comparar contra la linea base de esta sesion (117 patrones, 2.669 lineas
atomicas con ficha completa) y cerrar el plan.

---

## Self-Review

- **Cobertura del spec:** Paso 1 (informe de impacto) -> Task 1. Paso 2
  (presentacion) -> Task 3 Step 2. Paso 3 (decision del usuario) -> Task 3
  Step 3. Paso 4 (implementacion + test) -> Task 3 Steps 4-7. Paso 5
  (verificacion medida) -> Task 3 Step 8. Paso 6 (cierre/commit) -> Task 3
  Step 10. Red de seguridad (suite completa, no bajar el total de
  patrones) -> Task 3 Steps 8-9. Criterio de cierre del conjunto -> Task 4.
  Documentacion de decisiones -> Task 3 Step 4. Todo cubierto.
- **Placeholders:** Task 1 y Task 2 tienen codigo completo y comandos
  exactos, sin placeholders. Task 3 Steps 4-6 usan `<...>` deliberadamente
  porque su contenido depende de la decision del usuario en el Step 3 (ver
  nota en ese step) — no son placeholders por pereza, son las unicas
  partes de este plan que dependen de una entrada humana que no existe
  todavia. El resto de Task 3 (Steps 1, 2, 7, 8, 9, 10) es mecanico y
  esta completo.
- **Consistencia de tipos:** `rank_families_by_gap` y
  `top_unmatched_phrases_for_family` se usan con la misma firma en Task 2
  y Task 3 que la definida en Task 1. `rebuild_features_and_patterns()` es
  el metodo ya existente de `HistoricalBudgetAnalyzer` (sesion anterior,
  commit `4dea80c`), no uno nuevo.
