# Plan de implementación: sistema histórico de aprendizaje y sugerencia

## Objetivo

Implementar una capa histórica modular que permita sugerir partidas offline a partir de presupuestos reales, manteniendo el flujo IA actual como fallback.

## Fases y sprints

### Sprint 1 (Fase 1): DB + repositorio histórico

- Añadir tablas `historical_*`, `execution_module`, `suggestion_*`.
- Añadir índices de rendimiento.
- Crear `historical_repository.py` con CRUD base y resumen por módulo.
- Re-export en `src/core/repositories/__init__.py` y `src/core/db_repository.py`.

**Commit sugerido**
- `feat(db): add historical intelligence schema and repository`

### Sprint 2 (Fase 2): normalización + clasificador

- Crear `work_type_normalizer.py`.
- Crear `historical_partida_classifier.py` con clasificación multi-módulo por reglas.

**Commit sugerido**
- `feat(core): add work type normalizer and multi-module partida classifier`

### Sprint 3 (Fase 3): analizador de lote histórico

- Crear `historical_budget_analyzer.py`.
- Añadir skip por `ruta_excel + fecha_modificacion_excel`.
- Guardar errores por archivo sin parar el lote.

**Commit sugerido**
- `feat(core): add historical budget analyzer with mtime-based skipping`

### Sprint 4 (Fase 4): constructor de patrones

- Crear `historical_pattern_builder.py`.
- Agrupar por `concepto_normalizado + unidad + modulo`.
- Calcular media, mediana, min, max, frecuencia, confianza.

**Commit sugerido**
- `feat(core): build reusable partida patterns from historical data`

### Sprint 5 (Fase 5): servicio de sugerencias

- Crear `historical_suggestion_service.py`.
- Devolver formato compatible con inserción actual.

**Commit sugerido**
- `feat(core): add historical suggestion service for project bootstrap`

### Sprint 6 (Fase 6): GUI de análisis

- Crear `historical_analysis_dialog.py`.
- Añadir menú `Herramientas > Analizar presupuestos terminados`.

**Commit sugerido**
- `feat(gui): add historical analysis dialog and tools menu entry`

### Sprint 7 (Fase 7): GUI de sugerencias + integración en creación

- Crear `historical_suggestions_dialog.py`.
- Añadir `_offer_partidas(...)` en `main_frame.py`.
- Mantener `_offer_ai_partidas()` intacto como fallback.

**Commit sugerido**
- `feat(gui): integrate historical suggestions before AI fallback`

### Sprint 8 (Fase 8): IA enriquecida (posterior)

- Añadir contexto histórico opcional a `PromptBuilder` y `BudgetGenerator`.
- Usar histórico para priorizar partidas reales.

**Commit sugerido**
- `feat(ai): enrich prompt with historical context`

## Reglas de seguridad

- No romper flujo actual hasta terminar núcleo histórico.
- No cambiar formato de partidas usado por `insert_partidas()`.
- Análisis tolerante a errores por Excel.
- No reprocesar archivos sin cambios (`mtime`).
- Tests núcleo antes de conectar GUI.

## Tests mínimos obligatorios

- `test_normalize_work_type`
- `test_classify_partida_single_module`
- `test_classify_partida_multiple_modules`
- `test_analyzer_skips_unchanged_excel`
- `test_suggestion_service_returns_expected_format`
