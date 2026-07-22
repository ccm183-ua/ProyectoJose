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

