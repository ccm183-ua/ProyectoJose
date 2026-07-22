# Histórico estructurado y cruce fiable Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir los presupuestos Excel propios en evidencia trazable y estructurada, para que la aplicación solo proponga precios históricos comparables y explique siempre su grado de certeza.

**Architecture:** Se conserva la lectura existente de Excel y la tabla `historical_partida` como registro bruto inmutable. Una capa derivada clasifica cada partida en atributos comparables, con un módulo principal único y etiquetas secundarias; solo la clasificación principal alimenta referencias de precio. El comparador crea cuatro niveles de evidencia (exacta, comparable, relacionada y no utilizable) y el agente usa únicamente los dos primeros como fuente de precio.

**Tech Stack:** Python 3, SQLite, PySide6, `pytest`, `openpyxl` ya usado por `BudgetReader`.

## Global Constraints

- No añadir dependencias ni servicios externos en esta fase.
- El Excel original, la partida leída y su procedencia no se sobrescriben.
- Un presupuesto generado por IA no entra en la memoria reutilizable hasta que el usuario lo marque explícitamente como aprobado.
- Una partida solo puede tener un `primary_module_id`; las etiquetas secundarias no generan referencias de precio.
- Nunca presentar un precio como real/actual: mostrar origen, número de presupuestos, fechas y dispersión.
- Mantener compatibilidad con la plantilla Excel actual (`BudgetReader.PARTIDA_START_ROW = 17`).
- Toda migración debe incrementar `schema_version` y ser idempotente.
- Las tareas se implementan mediante TDD; no se reconstruye el histórico de producción sin copia SQLite y pantalla de previsualización.

---

## Resultado funcional y criterios de aceptación

Una partida importada debe conservar su texto y precio originales, y disponer de una ficha derivada con: acción, elemento, sistema, unidad, material/técnica, dimensiones/cantidad relevante, condiciones, tipo de línea, módulo principal, etiquetas secundarias, confianza y motivo de clasificación. Una misma línea compuesta no podrá duplicar su precio en varios módulos.

Al pedir un borrador, cada línea propuesta tendrá uno de estos dictámenes:

| Dictamen | Puede sugerir precio | Presentación |
| --- | --- | --- |
| `exact` | Sí | Precio mediano, rango, fuentes y confianza alta |
| `comparable` | Sí, con advertencia | Rango y diferencias detectadas |
| `related` | No | Antecedente consultable, sin copiar precio |
| `incompatible` | No | Se excluye y se indica el motivo si el usuario abre el informe |

Validación global: dos partidas con los mismos términos secundarios pero distinta acción, elemento, unidad, material o condición crítica no podrán ser `exact`; una línea multietiqueta solo podrá originar una referencia de precio.

## Estructura de archivos prevista

- Modificar: `src/core/database.py` — migración versionada y esquema de datos derivados.
- Modificar: `src/core/historical_budget_analyzer.py` — persistir la extracción, hash del archivo y estado de aprendizaje sin inferir aprobación.
- Modificar: `src/core/budget_reader.py` — añadir metadatos de fila y comprobaciones por partida, sin cambiar la interpretación de la plantilla.
- Modificar: `src/core/historical_partida_classifier.py` — separar clasificación primaria, etiquetas y ficha estructurada determinista.
- Crear: `src/core/historical_partida_features.py` — tipos, normalización de atributos y reglas de extracción explicables.
- Crear: `src/core/historical_comparator.py` — compatibilidad, nivel de evidencia y diferencias entre fichas.
- Modificar: `src/core/historical_pattern_builder.py` — construir patrones solo desde módulo principal y presupuestos aprobados.
- Modificar: `src/core/repositories/historical_repository.py` — leer/escribir fichas, fuentes y referencias explicables.
- Modificar: `src/core/historical_suggestion_service.py` — recuperar candidatos y aplicar el comparador antes de proponer.
- Modificar: `src/core/budget_orchestrator.py` — consumir resultados evidenciados y no aprender automáticamente de IA.
- Modificar: `src/gui/combined_partidas_review_dialog.py` — mostrar fuente, diferencias y permitir aprobar memoria de forma explícita.
- Modificar: `src/gui/historical_analysis_results_dialog.py` — previsualizar calidad, clasificación y exclusiones de una importación.
- Modificar: `tests/test_database_migrations.py`, `tests/test_budget_reader.py`, `tests/test_historical_budget_analyzer.py`, `tests/test_historical_partida_classifier.py`, `tests/test_historical_pattern_builder.py`, `tests/test_historical_suggestion_service.py`, `tests/test_budget_orchestrator.py`.
- Crear: `tests/test_historical_partida_features.py` y `tests/test_historical_comparator.py`.
- Crear: `docs/criterios-clasificacion-partidas.md` — catálogo editable por el usuario de acciones, elementos, sinónimos y condiciones críticas.

## Fase 0 — congelar la verdad actual

### Task 1: Inventario reproducible del histórico actual

**Files:**
- Create: `scripts/audit_historical_memory.py`
- Create: `tests/test_historical_memory_audit.py`
- Modify: `docs/criterios-clasificacion-partidas.md`

**Interfaces:**
- Consumes: ruta SQLite de solo lectura y las tablas `historical_budget`, `historical_partida`, `historical_partida_module`, `suggested_partida_pattern`.
- Produces: `build_audit_report(db_path: str) -> dict` con contadores, muestras y anomalías serializables.

- [x] **Step 1: Escribir el test de inventario con una base temporal**

```python
def test_build_audit_report_counts_unclassified_and_multimodule(tmp_path):
    report = build_audit_report(str(seed_history_db(tmp_path)))
    assert report["lines_total"] == 3
    assert report["lines_unclassified"] == 1
    assert report["lines_multimodule"] == 1
```

- [x] **Step 2: Ejecutar el test y confirmar fallo**

Run: `pytest tests/test_historical_memory_audit.py::test_build_audit_report_counts_unclassified_and_multimodule -v`

Expected: FAIL porque el módulo de auditoría no existe.

- [x] **Step 3: Implementar el informe de solo lectura**

```python
def build_audit_report(db_path: str) -> dict:
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        # consultas SELECT; nunca llamar a init_database ni a una migración
        return {"lines_total": total, "lines_unclassified": unclassified,
                "lines_multimodule": multimodule, "patterns": patterns}
```

- [x] **Step 4: Ejecutar el test y la auditoría sobre una copia de la base local**

Run: `pytest tests/test_historical_memory_audit.py -v; .\.venv\Scripts\python.exe scripts\audit_historical_memory.py --db "$env:USERPROFILE\Documents\CubiApp\datos.db"`

Expected: PASS; el script imprime JSON y no cambia el hash SHA-256 del fichero antes/después.

- [x] **Step 5: Registrar la línea base de negocio en el documento de criterios**

Incluir los resultados observados: 254 partidas, 33 sin módulo, 168 con más de un módulo, 424 patrones y 82 patrones con frecuencia al menos 2. Marcar estos números como línea base, no como objetivos.

## Fase 1 — adquisición fiable y origen de los datos

### Task 2: Validar cada fila extraída de la plantilla sin perderla

**Files:**
- Modify: `src/core/budget_reader.py`
- Test: `tests/test_budget_reader.py`

**Interfaces:**
- Produces por partida: `source_row: int`, `validation_issues: list[str]`, `raw_quantity`, `raw_unit_price`, `raw_total`.
- `BudgetReader.read()` sigue devolviendo las mismas claves existentes y añade estas claves opcionales.

- [ ] **Step 1: Añadir un Excel fixture con total incoherente y otro con unidad ausente**

```python
assert partida["source_row"] == 17
assert "LINE_TOTAL_MISMATCH" in partida["validation_issues"]
assert "MISSING_UNIT" in partida["validation_issues"]
```

- [ ] **Step 2: Ejecutar el test de lectura y confirmar fallo**

Run: `pytest tests/test_budget_reader.py -k "source_row or validation_issues" -v`

Expected: FAIL al no existir las claves.

- [ ] **Step 3: Calcular incidencias locales en `_extract_partidas`**

```python
issues = []
if not unidad:
    issues.append("MISSING_UNIT")
if cantidad > 0 and precio > 0 and total > 0 and not math.isclose(cantidad * precio, total, rel_tol=0.02, abs_tol=0.02):
    issues.append("LINE_TOTAL_MISMATCH")
```

No descartar filas aquí: el analizador decidirá después si son elegibles.

- [ ] **Step 4: Ejecutar los tests de lectura**

Run: `pytest tests/test_budget_reader.py -v`

Expected: PASS.

### Task 3: Versionar esquema y separar procedencia de aprobación

**Files:**
- Modify: `src/core/database.py`
- Test: `tests/test_database_migrations.py`

**Interfaces:**
- Nueva tabla `historical_partida_feature(partida_id INTEGER PRIMARY KEY, ...)`.
- Nuevos campos de `historical_budget`: `file_sha256 TEXT`, `source_kind TEXT NOT NULL DEFAULT 'external_excel'`, `learning_status TEXT NOT NULL DEFAULT 'PENDING_REVIEW'`, `approved_at TEXT`, `approved_by TEXT`.
- Valores permitidos: `external_excel`, `own_final_budget`, `ai_draft`, `template`; y `INCLUDED`, `PENDING_REVIEW`, `EXCLUDED`.

- [ ] **Step 1: Escribir pruebas de migración desde versión 1 e idempotencia**

```python
assert row["source_kind"] == "external_excel"
assert row["learning_status"] == "PENDING_REVIEW"
assert table_exists(conn, "historical_partida_feature")
assert schema_version(conn) == CURRENT_SCHEMA_VERSION
```

- [ ] **Step 2: Ejecutar las pruebas de migración y confirmar fallo**

Run: `pytest tests/test_database_migrations.py -k "historical_feature or schema_version" -v`

Expected: FAIL porque la migración no existe.

- [ ] **Step 3: Añadir migración incremental explícita**

```python
def migrate_v2(conn: sqlite3.Connection) -> None:
    conn.execute("ALTER TABLE historical_budget ADD COLUMN file_sha256 TEXT")
    conn.execute("CREATE TABLE IF NOT EXISTS historical_partida_feature (...)")
    conn.execute("UPDATE schema_metadata SET version = 2")
```

La función debe comprobar columnas existentes con `PRAGMA table_info` antes de cada `ALTER TABLE`.

- [ ] **Step 4: Ejecutar migraciones contra fixture legacy y una base ya migrada**

Run: `pytest tests/test_database_migrations.py -v`

Expected: PASS; una segunda apertura no produce excepción ni modifica registros existentes.

### Task 4: Impedir el aprendizaje implícito y detectar duplicados de archivo


**Files:**
- Modify: `src/core/historical_budget_analyzer.py`
- Modify: `src/core/repositories/historical_repository.py`
- Test: `tests/test_historical_budget_analyzer.py`

**Interfaces:**
- `analyze_file(path: str, source_kind: str = "external_excel") -> HistoricalAnalysisResult`.
- `approve_budget_for_learning(budget_id: int, approved_by: str) -> None`.
- `HistoricalAnalysisResult` expone `duplicate_of_budget_id: int | None` y `eligible_line_count: int`.

- [ ] **Step 1: Escribir tests de hash y de aprobación explícita**

```python
result = analyzer.analyze_file(str(workbook), source_kind="ai_draft")
assert result.learning_status == "PENDING_REVIEW"
assert repository.pattern_source_count() == 0
repository.approve_budget_for_learning(result.budget_id, "SERGIO")
assert repository.get_budget(result.budget_id)["learning_status"] == "INCLUDED"
```

- [ ] **Step 2: Ejecutar la prueba y confirmar fallo**

Run: `pytest tests/test_historical_budget_analyzer.py -k "approval or duplicate" -v`

Expected: FAIL porque actualmente se incorpora durante la finalización.

- [ ] **Step 3: Calcular SHA-256 al importar y mantener el presupuesto repetido fuera de aprendizaje**

```python
digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
existing_id = repository.find_budget_by_sha256(digest)
if existing_id is not None:
    return HistoricalAnalysisResult(duplicate_of_budget_id=existing_id, eligible_line_count=0)
```

Los archivos de tipo `ai_draft` y `template` quedan `PENDING_REVIEW`; solo el botón explícito cambia a `INCLUDED`.

- [ ] **Step 4: Ejecutar tests del analizador y patrón**

Run: `pytest tests/test_historical_budget_analyzer.py tests/test_historical_pattern_builder.py -v`

Expected: PASS; importar dos veces el mismo fichero no duplica partidas ni fuentes.

## Fase 2 — ficha estructurada y clasificación sin duplicar precios

### Task 5: Definir el contrato de la ficha derivada

**Files:**
- Create: `src/core/historical_partida_features.py`
- Create: `tests/test_historical_partida_features.py`
- Create: `docs/criterios-clasificacion-partidas.md`

**Interfaces:**
- `PartidaFeatures` dataclass: `action`, `element`, `system`, `unit`, `material`, `dimensions`, `conditions`, `line_kind`, `primary_module_id`, `secondary_module_ids`, `confidence`, `reasons`.
- `extract_partida_features(concept: str, unit: str, modules: list[dict]) -> PartidaFeatures`.

- [ ] **Step 1: Escribir ejemplos de aceptación concretos**

```python
features = extract_partida_features("Picado y reparación de revoco en fachada con mortero R4", "m2", modules)
assert features.action == "repair"
assert features.element == "facade_render"
assert features.material == "mortar_r4"
assert features.primary_module_id == "fachada"
assert set(features.secondary_module_ids) == {"demolicion", "albanileria"}
```

```python
features = extract_partida_features("Alquiler de plataforma elevadora", "ud", modules)
assert features.line_kind == "auxiliary"
assert features.primary_module_id == "medios_auxiliares"
```

- [ ] **Step 2: Ejecutar la prueba y confirmar fallo**

Run: `pytest tests/test_historical_partida_features.py -v`

Expected: FAIL porque no existe el módulo.

- [ ] **Step 3: Implementar vocabulario cerrado y razones**

```python
@dataclass(frozen=True)
class PartidaFeatures:
    action: str | None
    element: str | None
    system: str | None
    unit: str
    material: str | None
    dimensions: tuple[str, ...]
    conditions: tuple[str, ...]
    line_kind: Literal["atomic", "composite", "auxiliary", "unknown"]
    primary_module_id: str | None
    secondary_module_ids: tuple[str, ...]
    confidence: float
    reasons: tuple[str, ...]
```

Guardar sinónimos y condiciones críticas en el documento, y cargarlos en constantes Python; no usar LLM en esta fase.

- [ ] **Step 4: Ejecutar pruebas unitarias**

Run: `pytest tests/test_historical_partida_features.py tests/test_historical_partida_classifier.py -v`

Expected: PASS.

### Task 6: Elegir un módulo principal único y conservar etiquetas secundarias

**Files:**
- Modify: `src/core/historical_partida_classifier.py`
- Modify: `src/core/historical_partida_features.py`
- Test: `tests/test_historical_partida_classifier.py`

**Interfaces:**
- `HistoricalPartidaClassifier.classify(partida: dict) -> dict` devuelve `primary_module`, `secondary_modules`, `confidence`, `reasons`.
- Se mantiene una adaptación temporal `classify_text(text) -> list[dict]` para consumidores antiguos, ordenada con la principal primero.

- [ ] **Step 1: Escribir el caso de regresión de una partida de siete etiquetas**

```python
classification = classifier.classify({"concepto": composite_text, "unidad": "m2"})
assert classification["primary_module"]["id"] == "fachada"
assert len(classification["secondary_modules"]) == 6
assert classification["primary_module"]["id"] not in {m["id"] for m in classification["secondary_modules"]}
```

- [ ] **Step 2: Ejecutar el test y confirmar fallo**

Run: `pytest tests/test_historical_partida_classifier.py -k primary -v`

Expected: FAIL porque el clasificador actual devuelve solo una lista plana.

- [ ] **Step 3: Aplicar orden de decisión explícito**

```python
PRIMARY_PRIORITY = ("demolicion", "estructura", "fachada", "impermeabilizacion", "bajante", "albanileria", "pintura", "carpinteria", "cerrajeria", "medios_auxiliares")
primary = max(candidates, key=lambda c: (c["score"], -PRIMARY_PRIORITY.index(c["id"])))
```

Para una línea compuesta, la acción y elemento principal deben pesar más que simples palabras presentes en tareas auxiliares.

- [ ] **Step 4: Ejecutar clasificación existente y nueva**

Run: `pytest tests/test_historical_partida_classifier.py tests/test_ai_module_classifier.py -v`

Expected: PASS; la compatibilidad existente se mantiene.

### Task 7: Persistir ficha y reconstruirla sin tocar el bruto

**Files:**
- Modify: `src/core/repositories/historical_repository.py`
- Modify: `src/core/historical_budget_analyzer.py`
- Test: `tests/test_historical_budget_analyzer.py`

**Interfaces:**
- `upsert_partida_features(partida_id: int, features: PartidaFeatures) -> None`.
- `get_partida_features(partida_id: int) -> dict | None`.
- `rebuild_partida_features(budget_ids: Iterable[int]) -> int`.

- [ ] **Step 1: Escribir test de inmutabilidad del texto original**

```python
before = repository.get_partida(partida_id)["concepto"]
rebuild_partida_features([budget_id])
assert repository.get_partida(partida_id)["concepto"] == before
assert repository.get_partida_features(partida_id)["primary_module_id"] == "fachada"
```

- [ ] **Step 2: Ejecutar el test y confirmar fallo**

Run: `pytest tests/test_historical_budget_analyzer.py -k feature -v`

Expected: FAIL porque no hay ficha persistida.

- [ ] **Step 3: Insertar/actualizar solo la tabla derivada**

```sql
INSERT INTO historical_partida_feature(partida_id, action, element, system, unit, material,
    dimensions_json, conditions_json, line_kind, primary_module_id, secondary_module_ids_json,
    confidence, reasons_json, classifier_version)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(partida_id) DO UPDATE SET action=excluded.action, element=excluded.element,
    primary_module_id=excluded.primary_module_id, classifier_version=excluded.classifier_version;
```

- [ ] **Step 4: Ejecutar pruebas y comprobar idempotencia**

Run: `pytest tests/test_historical_budget_analyzer.py -v`

Expected: PASS; dos reconstrucciones dejan el mismo número de fichas.

## Fase 3 — comparador y referencias honestas

### Task 8: Definir compatibilidad determinista entre dos fichas

**Files:**
- Create: `src/core/historical_comparator.py`
- Create: `tests/test_historical_comparator.py`

**Interfaces:**
- `ComparisonResult(level: Literal["exact", "comparable", "related", "incompatible"], score: float, differences: tuple[str, ...], reasons: tuple[str, ...])`.
- `compare_partida_features(request: PartidaFeatures, evidence: PartidaFeatures) -> ComparisonResult`.

- [ ] **Step 1: Escribir matriz de seguridad**

```python
assert compare(request_m2_repair, evidence_m2_repair).level == "exact"
assert compare(request_m2_repair, evidence_ml_repair).level == "incompatible"
assert compare(request_repair, evidence_demolition).level == "incompatible"
assert compare(request_mortar_r4, evidence_mortar_generic).level == "comparable"
assert compare(request_facade, evidence_facade_with_scaffold).differences == ("condition:scaffold",)
```

- [ ] **Step 2: Ejecutar los tests y confirmar fallo**

Run: `pytest tests/test_historical_comparator.py -v`

Expected: FAIL porque no existe el comparador.

- [ ] **Step 3: Implementar reglas de exclusión antes de puntuación**

```python
if request.unit != evidence.unit:
    return incompatible("unit")
if request.action and evidence.action and request.action != evidence.action:
    return incompatible("action")
if request.line_kind == "composite" or evidence.line_kind == "composite":
    return related("composite_line")
```

Después comparar elemento, sistema, material, dimensiones y condiciones. Solo igualdad de los campos críticos puede producir `exact`.

- [ ] **Step 4: Ejecutar tests del comparador**

Run: `pytest tests/test_historical_comparator.py -v`

Expected: PASS.

### Task 9: Construir patrones por evidencia primaria y presupuestos distintos


**Files:**
- Modify: `src/core/historical_pattern_builder.py`
- Modify: `src/core/repositories/historical_repository.py`
- Test: `tests/test_historical_pattern_builder.py`

**Interfaces:**
- Patrón incluye `primary_module_id`, `distinct_budget_count`, `min_price`, `median_price`, `max_price`, `price_spread_ratio`, `latest_source_date`, `evidence_quality`.
- `rebuild_patterns() -> PatternBuildResult`.

- [ ] **Step 1: Escribir regresiones de duplicación y precio disperso**

```python
result = builder.rebuild_patterns()
assert repository.count_patterns_for_primary_line(partida_id) == 1
pattern = repository.find_pattern("repair", "facade_render", "m2")
assert pattern["distinct_budget_count"] == 2
assert pattern["median_price"] == Decimal("50.00")
assert pattern["price_spread_ratio"] == Decimal("0.40")
```

- [ ] **Step 2: Ejecutar tests de patrones y confirmar fallo**

Run: `pytest tests/test_historical_pattern_builder.py -k "primary or distinct or spread" -v`

Expected: FAIL porque los patrones actuales se crean por cada etiqueta.

- [ ] **Step 3: Agrupar solo partidas aprobadas, atómicas y con módulo principal**

```sql
WHERE hb.learning_status = 'INCLUDED'
  AND f.line_kind = 'atomic'
  AND f.primary_module_id IS NOT NULL
  AND hp.precio > 0
GROUP BY f.primary_module_id, f.action, f.element, f.system, f.unit, f.material
```

Usar `COUNT(DISTINCT hb.id)` para frecuencia. Calcular mediana en Python con `statistics.median` y dispersión `(max-min)/median` si mediana es positiva.

- [ ] **Step 4: Ejecutar reconstrucción en una copia y medir la corrección**

Ejecutado sobre una copia desechable de `Documents/CubiApp/datos.db` (117
presupuestos, 254 partidas reales), no sobre la base activa. Resultado
observado 2026-07-22:
- `rebuild_partida_features` sobre las 254 partidas: 54 `atomic`, 182
  `composite`, 10 `auxiliary`, 8 `unknown`; 8 sin `primary_module_id`.
- `rebuild_patterns()`: **424 → 41 patrones** (solo evidencia primaria
  atómica de presupuestos `INCLUDED`). De 41, solo 4 con frecuencia ≥ 2
  (antes 82) — confirma que la mayoría de los "82 patrones con frecuencia
  ≥ 2" de la línea base de Fase 0 eran el mismo precio duplicado entre
  módulos, no evidencia independiente real.
- Base real verificada intacta tras el ensayo (`schema_version=1`,
  424 patrones sin tocar); no se ha migrado ni reconstruido la base activa
  todavía — eso es explícitamente la Fase 5.

### Task 10: Recuperar evidencia y no precios por coincidencia textual simple

**Files:**
- Modify: `src/core/historical_suggestion_service.py`
- Modify: `src/core/repositories/historical_repository.py`
- Test: `tests/test_historical_suggestion_service.py`

**Interfaces:**
- `find_comparable_evidence(features: PartidaFeatures) -> list[EvidenceCandidate]`.
- `EvidenceCandidate` contiene `pattern`, `comparison`, `source_budget_ids`, `source_dates`, `price_range`.
- `suggest_for_project(...)` devuelve `evidence_report` además de `suggested_partidas`.


- [ ] **Step 1: Escribir los casos exacto, comparable y relacionado**

```python
suggestion = service.suggest_for_project(project, "Reparar revoco de fachada con mortero R4")
assert suggestion["evidence_report"][0]["level"] == "exact"
assert suggestion["suggested_partidas"][0]["precio"] == "50.00"
assert all(item["level"] != "related" for item in suggestion["priced_evidence"])
```

- [ ] **Step 2: Ejecutar tests y confirmar fallo**

Run: `pytest tests/test_historical_suggestion_service.py -k "evidence or comparable" -v`

Expected: FAIL porque actualmente se devuelve el patrón por módulo y texto normalizado.

- [ ] **Step 3: Aplicar el comparador a todos los candidatos del módulo principal**

```python
candidates = repository.find_patterns_by_primary_module(request.primary_module_id)
evidence = [to_evidence(candidate, compare_partida_features(request, candidate.features)) for candidate in candidates]
priced = [item for item in evidence if item.comparison.level in {"exact", "comparable"}]
```

Ordenar por nivel, número de presupuestos distintos, menor dispersión y fecha más reciente.

- [ ] **Step 4: Ejecutar tests del servicio**

Run: `pytest tests/test_historical_suggestion_service.py -v`

Expected: PASS; la evidencia relacionada no rellena precios.

## Fase 4 — uso responsable por el agente y revisión humana

### Task 11: Llevar evidencia al orquestador y eliminar el aprendizaje automático

**Files:**
- Modify: `src/core/budget_orchestrator.py`
- Modify: `tests/test_budget_orchestrator.py`

**Interfaces:**
- `GeneratedBudget` contiene `partidas`, `evidence_report`, `missing_private_data`, `needs_review`.
- Las partidas de fuente histórica llevan `source="historical_exact"` o `source="historical_comparable"`; las de IA llevan `source="ai_draft"`.

- [ ] **Step 1: Escribir test de trazabilidad y no aprendizaje de borrador**

```python
result = orchestrator.create_draft(project, "Reparar fachada")
assert result.evidence_report
assert all(p["source"] in {"historical_exact", "historical_comparable", "ai_draft"} for p in result.partidas)
orchestrator.finalize_draft(result)
assert repository.count_budgets_by_source_kind("ai_draft", "INCLUDED") == 0
```

- [ ] **Step 2: Ejecutar el test y confirmar fallo**

Run: `pytest tests/test_budget_orchestrator.py -k "evidence or ai_draft" -v`

Expected: FAIL por las claves de fuente actuales y la realimentación automática.

- [ ] **Step 3: Unificar las claves de fuente y retirar la incorporación automática**

```python
generated["source"] = "historical_exact"
generated["evidence_id"] = evidence.pattern_id
generated["evidence_level"] = evidence.comparison.level
# finalize_draft crea ai_draft PENDING_REVIEW; no llama a approve_budget_for_learning
```

La finalización conserva el Excel y el borrador, pero no reconstruye patrones hasta que se apruebe.

- [ ] **Step 4: Ejecutar tests del orquestador y regresión de generación**

Run: `pytest tests/test_budget_orchestrator.py tests/test_budget_generator.py -v`

Expected: PASS.

### Task 12: Hacer visible el informe de procedencia y la aprobación explícita

**Files:**
- Modify: `src/gui/combined_partidas_review_dialog.py`
- Modify: `src/gui/historical_analysis_results_dialog.py`
- Test: `tests/test_voice_budget_dialog.py`
- Test: `tests/test_historical_table_gui.py`

**Interfaces:**
- Cada fila muestra `Fuente`, `Nivel`, `Rango histórico` y `Diferencias`; los campos vacíos se muestran como `Sin evidencia privada comparable`.
- Acción explícita: `Aprobar presupuesto para memoria` solo sobre un presupuesto final guardado.

- [ ] **Step 1: Escribir prueba de modelo/tabla sin iniciar la GUI completa**

```python
row = dialog_model.row_for_partida({"source": "ai_draft", "evidence_level": None})
assert row["Fuente"] == "IA — borrador"
assert row["Rango histórico"] == "Sin evidencia privada comparable"
```

- [ ] **Step 2: Ejecutar el test y confirmar fallo**

Run: `pytest tests/test_historical_table_gui.py -k provenance -v`

Expected: FAIL porque no se crea el modelo de procedencia.

- [ ] **Step 3: Añadir columnas y acción de aprobación con confirmación**

La confirmación debe nombrar el presupuesto, explicar que pasará a alimentar referencias futuras y llamar únicamente a `approve_budget_for_learning`. Si faltan partidas válidas, no habilitar el botón.

- [ ] **Step 4: Ejecutar las pruebas GUI acotadas**

Run: `pytest tests/test_historical_table_gui.py tests/test_voice_budget_dialog.py -v`

Expected: PASS; no hay aprobación implícita al aceptar un borrador.

## Fase 5 — migración controlada del histórico existente

### Task 13: Añadir previsualización y reconstrucción reversible

**Files:**
- Create: `scripts/rebuild_historical_patterns.py`
- Modify: `src/gui/historical_analysis_results_dialog.py`
- Test: `tests/test_historical_integrity_diagnostics.py`

**Interfaces:**
- CLI: `python scripts/rebuild_historical_patterns.py --db PATH --dry-run` y `--apply`.
- Antes de `--apply`, crear copia `PATH.bak-YYYYMMDD-HHMMSS` y abortar si la copia no tiene el mismo SHA-256.

- [ ] **Step 1: Escribir test dry-run**

```python
before = sha256_file(db_path)
result = run_rebuild(["--db", str(db_path), "--dry-run"])
assert result.exit_code == 0
assert sha256_file(db_path) == before
assert "would_reclassify" in result.stdout
```

- [ ] **Step 2: Ejecutar el test y confirmar fallo**

Run: `pytest tests/test_historical_integrity_diagnostics.py -k dry_run -v`

Expected: FAIL porque el script no existe.

- [ ] **Step 3: Implementar copia, transacción y resumen de cambios**

```python
if args.apply:
    backup = db_path.with_suffix(db_path.suffix + f".bak-{timestamp}")
    shutil.copy2(db_path, backup)
    assert sha256_file(db_path) == sha256_file(backup)
    with transaction(conn):
        rebuild_partida_features(all_budget_ids)
        rebuild_patterns()
```

El resumen debe incluir: líneas sin clasificar, compuestas, pendientes de aprobación, patrones creados y patrones eliminados.

- [ ] **Step 4: Ejecutar prueba y ensayo en una copia de `datos.db`**

Run: `pytest tests/test_historical_integrity_diagnostics.py -v; Copy-Item "$env:USERPROFILE\Documents\CubiApp\datos.db" .\copia-datos.db; .\.venv\Scripts\python.exe scripts\rebuild_historical_patterns.py --db .\copia-datos.db --dry-run`

Expected: PASS; el original no se abre en modo escritura y el informe identifica las líneas compuestas.

### Task 14: Acordar y aplicar revisión humana del histórico actual

**Files:**
- Modify: `docs/criterios-clasificacion-partidas.md`
- Modify: `src/gui/historical_analysis_results_dialog.py`
- Test: `tests/test_historical_budget_analyzer.py`

**Interfaces:**
- Estados por partida: `accepted`, `needs_mapping`, `composite`, `excluded`.
- La interfaz permite filtrar por estado y guardar una decisión del usuario con fecha y motivo breve.

- [ ] **Step 1: Cargar una copia y generar informe de revisión**

Run: `.\.venv\Scripts\python.exe scripts\rebuild_historical_patterns.py --db .\copia-datos.db --dry-run > .\historico-a-revisar.json`

Expected: el informe contiene la lista exacta de 33 líneas sin módulo y las líneas multietiqueta a revisar.

- [ ] **Step 2: Documentar decisiones de clasificación reales**

Para cada familia de partidas repetida, añadir en `docs/criterios-clasificacion-partidas.md`: expresión habitual, acción, elemento, módulo principal, etiquetas secundarias y una condición que impida una coincidencia exacta.

- [ ] **Step 3: Escribir y ejecutar regresiones por cada decisión añadida**

```python
@pytest.mark.parametrize(("concept", "expected_primary"), REVIEWED_CASES)
def test_reviewed_historical_cases_keep_primary_module(concept, expected_primary):
    assert classifier.classify({"concepto": concept, "unidad": "m2"})["primary_module"]["id"] == expected_primary
```

Run: `pytest tests/test_historical_partida_classifier.py -v`

Expected: PASS; cada regla humana queda fijada por un test.

- [ ] **Step 4: Aplicar solo tras aprobación del informe**

Run: `.\.venv\Scripts\python.exe scripts\rebuild_historical_patterns.py --db .\copia-datos.db --apply`

Expected: se crea copia de seguridad, la auditoría posterior no tiene patrones duplicados por etiquetas, y los presupuestos `PENDING_REVIEW` continúan fuera de las referencias.

## Fase 6 — salida de hito y control de regresión

### Task 15: Prueba de extremo a extremo y umbrales de salida

**Files:**
- Create: `tests/test_historical_budget_flow_e2e.py`
- Modify: `docs/criterios-clasificacion-partidas.md`

**Interfaces:**
- Flujo probado: Excel válido → análisis → ficha → aprobación → patrón → solicitud → informe de evidencia → borrador → finalización sin aprendizaje automático.

- [ ] **Step 1: Escribir el escenario completo**

```python
def test_approved_atomic_history_can_price_a_matching_draft_but_ai_draft_is_not_learned(tmp_path):
    history_id = import_and_approve_atomic_facade_budget(tmp_path)
    result = BudgetOrchestrator(...).create_draft(project, "Reparar revoco de fachada con mortero R4")
    assert result.partidas[0]["source"] == "historical_exact"
    assert result.evidence_report[0]["source_budget_ids"] == [history_id]
    BudgetOrchestrator(...).finalize_draft(result)
    assert repository.count_budgets_by_source_kind("ai_draft", "INCLUDED") == 0
```

- [ ] **Step 2: Ejecutar la prueba y confirmar fallo antes de conectar todos los componentes**

Run: `pytest tests/test_historical_budget_flow_e2e.py -v`

Expected: FAIL hasta completar las tareas 2 a 14.

- [ ] **Step 3: Ejecutar el conjunto de regresión relevante**

Run: `pytest tests/test_database_migrations.py tests/test_budget_reader.py tests/test_historical_budget_analyzer.py tests/test_historical_partida_features.py tests/test_historical_partida_classifier.py tests/test_historical_comparator.py tests/test_historical_pattern_builder.py tests/test_historical_suggestion_service.py tests/test_budget_orchestrator.py tests/test_historical_budget_flow_e2e.py -v`

Expected: PASS.

- [ ] **Step 4: Validar criterios de salida con datos reales en copia**

Run: `.\.venv\Scripts\python.exe scripts\audit_historical_memory.py --db .\copia-datos.db; .\.venv\Scripts\python.exe scripts\rebuild_historical_patterns.py --db .\copia-datos.db --dry-run`

Expected: todos los patrones proceden de partidas `INCLUDED`, atómicas y con módulo principal; cada patrón informa de presupuestos distintos y dispersión; no hay patrones creados por etiquetas secundarias.

- [ ] **Step 5: Aceptación manual del hito**

Comprobar en la aplicación tres ejemplos: uno exacto, uno comparable con advertencia y uno sin evidencia privada. El informe debe identificar las fuentes de los dos primeros y declarar sin ambigüedad que el tercero requiere estimación/revisión.

## Orden de ejecución y dependencias

```mermaid
flowchart LR
  T1["1 Auditoría base"] --> T2["2 Validación Excel"]
  T2 --> T3["3 Migración"] --> T4["4 Origen y aprobación"]
  T4 --> T5["5 Ficha estructurada"] --> T6["6 Principal/secundarias"] --> T7["7 Persistencia"]
  T7 --> T8["8 Comparador"] --> T9["9 Patrones"] --> T10["10 Recuperación"]
  T10 --> T11["11 Orquestador"] --> T12["12 Interfaz"]
  T12 --> T13["13 Reconstrucción"] --> T14["14 Revisión del histórico"] --> T15["15 E2E y salida"]
```

## Validaciones mínimas para dar por cerrado el hito

- No se modifica el Excel ni el texto/importe bruto de una partida durante clasificación o reconstrucción.
- El mismo fichero no puede crear un segundo presupuesto histórico.
- Ningún presupuesto `ai_draft` o `PENDING_REVIEW` genera una referencia de precio.
- Ninguna partida puede alimentar dos patrones de precio por tener etiquetas secundarias.
- Unidades distintas, acciones contrarias y líneas compuestas no reciben dictamen `exact`.
- El usuario puede abrir la procedencia de cualquier precio propuesto: presupuestos fuente, fechas, rango, diferencias y nivel.
- La suite acotada de la tarea 15 pasa y el flujo manual de tres casos es satisfactorio.

## Fuera de este hito

- Búsqueda de precios en Internet y catálogo externo de precios.
- Clasificación semántica mediante LLM.
- API HTTPS, autenticación y acceso móvil.
- Reescritura del dominio `budget/budget_version` añadido en cambios recientes que aún no está integrado con el agente de escritorio.

Esos trabajos se abordarán una vez que el histórico local sea una fuente fiable: de otro modo, una IA o una API solo amplificarían clasificaciones y precios poco fiables.
