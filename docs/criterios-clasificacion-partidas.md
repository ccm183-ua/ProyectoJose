# Criterios de clasificación de partidas históricas

## Línea base (Fase 0 — 2026-07-22)

Resultado de `scripts/audit_historical_memory.py` sobre `Documents/CubiApp/datos.db`
(solo lectura; hash SHA-256 del fichero verificado idéntico antes/después).
Estos números son la **verdad actual del sistema**, no un objetivo: sirven para
medir el efecto de las fases 1-5 del roadmap, no para justificarlas.

| Métrica | Valor |
| --- | --- |
| Partidas históricas totales | 254 |
| Partidas sin clasificar (0 módulos) | 33 |
| Partidas con más de un módulo | 168 |
| Asignaciones partida-módulo totales | 536 |
| Patrones de precio activos | 424 |
| Patrones con frecuencia ≥ 2 | 82 |
| Patrones con frecuencia ≥ 6 | 3 |
| Presupuestos históricos totales | 117 |
| Presupuestos `NOT_COMPATIBLE` | 54 |
| Presupuestos con `learning_status = INCLUDED` | 54 |
| Partidas con precio ≤ 0 | 26 |
| ...de las cuales en presupuestos `INCLUDED` | 3 |

### Lectura de la línea base

- Solo 3 de los 424 patrones alcanzan frecuencia 6, y corresponden a la misma
  partida duplicada entre varios módulos (168 partidas con más de un módulo
  generan hasta 536 asignaciones para 254 líneas) — no son evidencia
  independiente real.
- 33 partidas sin clasificar quedan fuera de cualquier sugerencia histórica.
- 54 de 117 presupuestos están marcados `NOT_COMPATIBLE` (plantilla no
  reconocida o sin partidas válidas) y no deberían alimentar patrones.
- 3 líneas con precio no positivo están dentro de presupuestos ya marcados
  como `INCLUDED` en la memoria de aprendizaje: candidatas a revisión en la
  Fase 5.

Reproducir en cualquier momento:

```
python scripts/audit_historical_memory.py --db "$env:USERPROFILE\Documents\CubiApp\datos.db"
```

## Ficha estructurada de partida (Fase 2, Tarea 5)

`src/core/historical_partida_features.py::extract_partida_features()` deriva una
`PartidaFeatures` por vocabulario cerrado de palabras clave sobre texto
normalizado (`work_type_normalizer.normalize_text`), **sin LLM**. No reclasifica
por módulo: reutiliza tal cual la salida ordenada por confianza de
`HistoricalPartidaClassifier.classify_text` — el primer módulo de esa lista es
`primary_module_id`, el resto son `secondary_module_ids`. Esto es exactamente lo
que evita que una partida multietiqueta duplique su precio en varios módulos
(línea base: 168 partidas con >1 módulo, 536 asignaciones para 254 líneas).

Cada tabla es una lista **ordenada** de `(categoría, keywords)`: gana la primera
categoría cuyo keyword aparece como substring en el texto normalizado, no "todas
las que matchean" (a diferencia de la clasificación de módulos). El orden
codifica la prioridad cuando dos categorías podrían aplicar a la vez.

**action** — prioridad: `repair` antes que `demolish`, porque "picado y
reparación de..." describe la intervención global, no el paso previo de picado.

| action | keywords |
| --- | --- |
| `repair` | reparacion, reparar |
| `demolish` | demolicion, demoler, picado, levantado, desmontaje |
| `install` | instalacion, instalar, colocacion, colocar, montaje |
| `paint` | pintura, pintado, pintar |
| `waterproof` | impermeabilizacion, impermeabilizar |
| `clean` | limpieza, limpiar |
| `rent` | alquiler, arrendamiento |

**element** — prioridad: formas compuestas (p.ej. "revoco en fachada") antes
que la genérica ("fachada") para no perder precisión cuando ambas aparecen.

| element | keywords |
| --- | --- |
| `facade_render` | revoco en fachada, revoco fachada, enfoscado fachada, enfoscado de fachada |
| `facade` | fachada |
| `downspout` | bajante |
| `roof` | cubierta, tejado |
| `structure` | estructura, viga, pilar, zuncho |
| `door` | puerta, portal |
| `railing` | barandilla, pasamanos |

**material**:

| material | keywords |
| --- | --- |
| `mortar_r4` | mortero r4 |
| `mortar` | mortero |
| `pvc` | pvc |
| `concrete` | hormigon |
| `steel` | acero, hierro, metalica |
| `wood` | madera |

**conditions** (no excluyentes entre sí, se acumulan todas las que matchean):

| condition | keywords |
| --- | --- |
| `scaffolding` | andamio |
| `elevated_platform` | plataforma elevadora, elevadora |
| `height_work` | altura |
| `difficult_access` | dificil acceso, acceso dificil, sin acceso |
| `urgent` | urgencia, urgente |

**line_kind** — orden de decisión: si el módulo principal es
`medios_auxiliares` → `auxiliary` (independientemente de cuántos módulos
matcheen); si no, más de un módulo → `composite`; exactamente un módulo →
`atomic`; ningún módulo → `unknown`.

**Fuera de alcance en esta fase** (YAGNI hasta que haga falta): `system` queda
siempre `None` (no hay vocabulario de sistemas todavía) y `dimensions` queda
siempre `()` (extraer magnitudes tipo "diámetro 100 mm" del texto libre
requeriría parsing numérico dedicado, no solo keywords).

## Revisión humana del histórico real (Fase 5, Tarea 14 — 2026-07-22)

Informe generado con `scripts/rebuild_historical_patterns.py --apply` sobre una
copia desechable de `Documents/CubiApp/datos.db` (254 partidas reales): 8 líneas
sin ningún módulo detectado, 182 líneas `composite` (más de un módulo). Revisadas
con el usuario las familias más repetidas (pintura 38, gestión de residuos 32,
fachada 24, cerrajería 20...); dos hallazgos confirmados y corregidos:

### Decisión 1 — demolición con retirada de escombros

- **Expresión habitual**: "Desmontaje/Demolición de X... retirada/carga sobre
  contenedor/vertedero" (p.ej. desmontaje de bajante, demolición de pavimento
  o falso techo con transporte de residuos).
- **Acción**: `demolish`. **Elemento**: el elemento demolido (bajante,
  pavimento, falso techo...). **Módulo principal**: `demolicion`.
  **Etiqueta secundaria**: `gestion_residuos`.
- **Condición que impide coincidencia exacta**: si la partida es *solo*
  transporte/vertido de residuos ya generados (sin verbo de demoler/desmontar
  en el texto), el módulo principal pasa a ser `gestion_residuos` — no es la
  misma evidencia de precio que una demolición con transporte incluido.
- **Motivo**: la acción que se factura es demoler; la gestión de residuos es
  casi siempre incidental. Como `gestion_residuos` tiene pocas palabras clave,
  dos menciones ahí ("residuo"+"contenedor") bastaban para superar en
  confianza a "desmontaje"+"retirada" en demolición.
- **Implementación**: `historical_partida_classifier.pick_primary_module()`
  excluye `gestion_residuos` del pool de candidatos a principal salvo que sea
  el único módulo detectado en la línea. Regresión:
  `tests/test_historical_partida_classifier.py::TestReviewedHistoricalCases`.

### Decisión 2 — protección/tapado durante obra en fachada

- **Expresión habitual**: "Protección de pavimentos y descuelgues. Tapado
  mediante mantas... durante la ejecución de los trabajos en fachada".
- **Acción**: `protect` (no cubierta por vocabulario de `action` todavía).
  **Módulo principal**: `medios_auxiliares`. **Etiqueta secundaria**:
  `fachada` (contexto de dónde ocurre, no el trabajo en sí).
- **Condición que impide coincidencia exacta**: si el texto describe
  reparación/intervención real sobre el paramento (grieta, fisura, revoco),
  el módulo principal es `fachada`, no `medios_auxiliares` — la sola mención
  de "fachada" como ubicación no basta.
- **Motivo**: "fachada" aparecía solo como contexto de ubicación, no como el
  trabajo facturado; la protección/tapado es una partida auxiliar
  independiente.
- **Implementación**: se añadió `"tapado"` a las palabras clave de
  `medios_auxiliares` en `MODULE_RULES`.
- **Hallazgo colateral corregido**: `"fachadas"` (plural) se normalizaba a
  `"fachada"` por la expansión de abreviaturas (`fachad→fachada`), así que
  contaba como un segundo acierto duplicado del mismo texto e inflaba
  artificialmente la confianza del módulo `fachada` cada vez que aparecía la
  palabra. Se retiró `"fachadas"` de `MODULE_RULES["fachada"]` (redundante,
  ya cubierta por `"fachada"` tras normalizar).

### Pendiente (no decidido en esta sesión)

- El mismo patrón de duplicado por abreviatura afecta también a
  `impermeabilizacion` (`"impermeabilizacion"`/`"imperm"` e
  `"filtracion"`/`"filtraciones"` normalizan igual) — no se ha tocado, no
  formaba parte de los hallazgos revisados con el usuario.
- De las 182 líneas `composite`, solo se revisaron ejemplos representativos
  de 3 familias (pintura, gestión de residuos, fachada). El resto
  (cerrajería, impermeabilización, demolición, alicatado, estructura,
  carpintería, albañilería, bajante) queda pendiente de revisión.
- Se observó un problema de codificación en `concepto_original` para varias
  partidas reales (acentos mostrados como `�`) — no es un problema de
  clasificación, es un problema de origen de datos; no investigado en esta
  sesión.
- No se ha ejecutado `--apply` sobre la base real de producción todavía
  (`Documents/CubiApp/datos.db` sigue en `schema_version=1`): solo sobre
  copias desechables. Migrar y reconstruir la base real requiere que el
  usuario decida explícitamente cuándo hacerlo.

## Cierre del hito: criterios de salida verificados (Fase 6, Tarea 15 — 2026-07-22)

`tests/test_historical_budget_flow_e2e.py` prueba el flujo completo con
`BudgetOrchestrator.generate()` real: Excel analizado → aprobación explícita
→ ficha derivada → patrones → evidencia `exact` trazable hasta el
presupuesto fuente → generar el borrador repetidamente nunca crea
presupuestos históricos nuevos. 111 tests de regresión relevantes en verde.

Validado con datos reales sobre una copia desechable de `datos.db` (117
presupuestos, 254 partidas): tras `rebuild_historical_patterns.py --apply`,
**40 patrones activos**, 0 con `distinct_budget_count` vacío, **0 fuentes de
patrón mal originadas** (todas trazables a partidas `INCLUDED` +
`analysis_status` válido + `line_kind='atomic'` + `primary_module_id` no
nulo). Base real de producción verificada intacta después de cada ensayo
(`schema_version=1` sin tocar).

Pendiente de aceptación manual (Step 5, requiere interacción humana con la
aplicación real, no ejecutable de forma automática): comprobar en la app tres
ejemplos — uno exacto, uno comparable con advertencia y uno sin evidencia
privada — y confirmar que el informe de evidencia identifica las fuentes de
los dos primeros y declara sin ambigüedad que el tercero requiere
estimación/revisión.

