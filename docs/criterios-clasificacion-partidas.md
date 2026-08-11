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
- **(2026-08-04, tras la Decisión 20) Hallazgo sistémico sin corregir,
  fuera del alcance de esta familia**: al investigar la colisión de
  `"cub"→"cubierta"` que motivó la Decisión 20, se comprobó que el mismo
  problema de coincidencia por **prefijo** en `ABBREVIATIONS`
  (`work_type_normalizer.py`) afecta también a otras entradas, con
  volumen bastante mayor que "cub" en algunos casos. Verificado contra el
  histórico real:
  - `"baj"→"bajante"` captura **"baja"** (572 líneas) y **"bajo"** (421
    líneas) — palabras normalísimas del castellano ("planta baja", "por
    bajo de"), sin relación con bajantes. **993 líneas afectadas.**
  - `"rep"→"reparacion"` captura "reposición" (196), "replanteo" (79) y
    "repaso" (37) — conceptos de construcción distintos de reparación.
    **312 líneas afectadas.**
  - `"sust"→"sustitucion"` captura "sustancia"/"sustancias" (56) —
    término químico sin relación.
  - `"imper"→"impermeabilizacion"` captura "imperfecciones" (23).
  - `"filt"→"filtracion"` captura "filtro"/"filtros" (16) — un
    dispositivo, no una filtración/gotera.
  - `"rehab"` y `"fachad"` no mostraron colisión en esta comprobación.

  **~1.400 líneas reales** potencialmente mal normalizadas en total, en
  clasificaciones ya existentes de TODA la aplicación, no solo de esta
  familia. Deliberadamente **no corregido** en esta sesión (decisión
  explícita del usuario): es un hallazgo que se ganó su propio plan, con
  el mismo cuidado que `docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md`,
  no un parche de paso dentro de la revisión de impermeabilización.
- De las 182 líneas `composite`, solo se revisaron ejemplos representativos
  de 3 familias (pintura, gestión de residuos, fachada). El resto
  (~~demolición~~, ~~alicatado~~, ~~albañilería~~, ~~impermeabilización~~
  y ~~carpintería~~ ya revisadas (ver abajo), cerrajería, estructura,
  bajante) queda pendiente de revisión.
- Se observó un problema de codificación en `concepto_original` para varias
  partidas reales (acentos mostrados como `�`) — no es un problema de
  clasificación, es un problema de origen de datos; no investigado en esta
  sesión.
- No se ha ejecutado `--apply` sobre la base real de producción todavía
  (`Documents/CubiApp/datos.db` sigue en `schema_version=1`): solo sobre
  copias desechables. Migrar y reconstruir la base real requiere que el
  usuario decida explícitamente cuándo hacerlo.
- **(2026-08-04, tras la Decisión 3)** "quitar" tiene prioridad de
  `demolish` sobre `paint`/`waterproof`/`clean` en `_ACTION_SYNONYMS`, igual
  que ya la tenía sobre ellos con las palabras clave anteriores de
  `demolish`. Esto reproduce, para pintura/impermeabilización, el mismo
  problema que ya se resolvió para `repair` (por eso `repair` va antes que
  `demolish`: un paso previo de picado no debe eclipsar la intervención
  global). Medido contra la base real: **2 líneas** de pintura ("PINTURA
  PUERTA PEATONAL Y BOMBEROS...", "PINTURA DE AZULEJOS EN COCINA Y
  BAÑO...") pasan de `action=paint` a `action=demolish` porque mencionan
  "quitar" como paso previo. Volumen aceptado como caso conocido (2 de
  3.217 líneas con ficha completa) en vez de tocar la prioridad compartida
  de `classify_line_kind`/`_match_first`, que afectaría a las 7 familias
  todavía sin revisar. Revisar si se repite el patrón al llegar a la
  familia `pintura` (ya revisada el 22/07, pero antes de esta decisión) o
  `impermeabilizacion` (todavía pendiente).

## Revisión del vocabulario cerrado por familias pendientes (2026-08-04)

Retoma las ocho familias que quedaron sin revisar el 22/07 (ver "Pendiente"
arriba), siguiendo el plan
`docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md`: por
cada familia, un informe de impacto (`src/core/historical_vocabulary_gap_report.py`)
trae los patrones reales de mayor frecuencia sin ficha completa
(`action`/`element` vacíos), y el usuario decide categoría y motivo sobre
esos ejemplos reales, nunca inventados.

Ranking inicial de impacto (líneas atómicas sin ficha completa / total,
sobre la base real de producción): demolición 75/80 (94%), alicatado 71/74
(96%), albañilería 42/46 (91%), impermeabilización 40/62 (65%), carpintería
32/61 (52%), sustitución de bajante 32/72 (44%), cerrajería 29/66 (44%),
estructura 7/25 (28%).

### Familia: demolición (turno 1 de 8)

10 patrones de mayor frecuencia revisados con el usuario. Hallazgo
principal: 8 de los 10 usaban el verbo **"quitar"**, ausente por completo
del vocabulario de acciones pese a ser el verbo mayoritario de
demolición/retirada en el histórico real (1.418 líneas).

### Decisión 3 — "quitar" como sinónimo de `demolish`

- **Expresión habitual**: "Quitar WC y mueble de lavabo, con retirada a
  contenedor de escombros." / "QUITAR SUELO LAMINADO..." / "QUITAR
  PUERTAS DE PASO..." (8 de los 10 patrones de mayor frecuencia de la
  familia).
- **Acción**: `demolish` (nuevo sinónimo: `quitar`). **Elemento**: el
  elemento retirado en cada caso (ver Decisiones 5-8). **Módulo
  principal**: sin cambios — estas líneas ya tenían `primary_module_id =
  demolicion` asignado por el clasificador; esta decisión no toca
  detección de módulo, solo completa la ficha de acción/elemento.
- **Condición que impide coincidencia exacta**: ninguna adicional a las ya
  existentes.
- **Motivo**: "quitar" es, con diferencia, el verbo más frecuente para
  demolición/retirada en el histórico real y no estaba cubierto. Se
  descarta explícitamente añadir **"tirar"** en la misma pasada aunque
  aparece en uno de los 10 patrones revisados ("Tirar tabiques
  existentes..."): "tirar" es substring literal de "retirar" (13 líneas
  reales, sentido distinto — retirada de escombros ya generados, no
  demolición — mismo tipo de matiz que la Decisión 1), y el motor de
  coincidencia actual es por substring sin límite de palabra. Se deja
  "tirar" **sin decisión**, pendiente de una detección más precisa (por
  palabra completa) si llega a compensar.
- **Implementación**: se añade `"quitar"` a `_ACTION_SYNONYMS["demolish"]`
  en `historical_partida_features.py`. Verificado contra la base real: 0
  falsos positivos de "quitar" como substring de otra palabra en las 1.418
  líneas reales que lo contienen.

### Decisión 4 — enfoscado sobre "paramento vertical exterior" es `facade_render`

- **Expresión habitual**: "Picado de enfoscado de cemento, aplicado sobre
  paramento vertical exterior de hasta 3 m de altura, con medios
  manuales, y carga manual de escombros sobre camión o contenedor."
  (frecuencia 8 — el patrón más repetido sin ficha de toda la familia
  demolición).
- **Acción**: `demolish` (ya cubierto por "picado"). **Elemento**:
  `facade_render` — misma evidencia que "revoco de fachada", descrita sin
  usar la palabra "fachada". **Módulo principal**: sin cambios
  (`demolicion`, ya asignado).
- **Condición que impide coincidencia exacta**: ninguna adicional.
- **Motivo**: el texto describe literalmente un enfoscado de cemento sobre
  el paramento exterior — mismo elemento facturable que "revoco de
  fachada", solo que redactado sin la palabra clave que ya cubría el
  vocabulario.
- **Implementación**: se añaden `"paramento vertical exterior"` y
  `"enfoscado de cemento"` a los sinónimos existentes de `facade_render`.

### Decisión 5 — "tabique" es `partition_wall` (elemento nuevo)

- **Expresión habitual**: "Tirar tabiques existentes de pasillo, cocina,
  galería y estudio, con retirada de escombros a contenedor."
- **Acción**: sin decisión (usa "tirar", ver Decisión 3 — esta línea
  concreta queda con `element` completo pero `action` vacío hasta que se
  revise "tirar"). **Elemento**: `partition_wall` (nuevo). **Módulo
  principal**: sin cambios.
- **Condición que impide coincidencia exacta**: ninguna.
- **Motivo**: "tabique" no tenía elemento propio; es un elemento
  facturable claramente distinto de `structure` (que cubre viga/pilar/
  zuncho, elementos estructurales, no tabiquería de partición).
- **Implementación**: nueva categoría `("partition_wall", ("tabique",))`
  en `_ELEMENT_SYNONYMS`, con entrada correspondiente en
  `_ELEMENT_FAMILIES`. Verificado: 0 falsos positivos contra la base real.

### Decisión 6 — WC/lavabo/sanitario es `sanitary_ware` (elemento nuevo)

- **Expresión habitual**: "Quitar WC y mueble de lavabo, con retirada a
  contenedor de escombros."
- **Acción**: `demolish` (vía "quitar", Decisión 3). **Elemento**:
  `sanitary_ware` (nuevo). **Módulo principal**: sin cambios.
- **Condición que impide coincidencia exacta**: ninguna.
- **Motivo**: aparatos sanitarios (WC, lavabo) son un elemento facturable
  propio, sin representación previa en el vocabulario.
- **Implementación**: nueva categoría `("sanitary_ware", ("wc", "lavabo",
  "sanitario"))`. Verificado: 0 falsos positivos contra la base real.

### Decisión 7 — suelo/solado es `flooring` (elemento nuevo)

- **Expresión habitual**: "QUITAR SUELO LAMINADO. Quitar solado laminado
  existente en vivienda y rodapié, con retirada de escombros a
  vertedero."
- **Acción**: `demolish` (vía "quitar", Decisión 3). **Elemento**:
  `flooring` (nuevo, vía "suelo" o "solado"). **Módulo principal**: sin
  cambios.
- **Condición que impide coincidencia exacta**: ninguna.
- **Motivo**: pavimento/solado es un elemento facturable propio. Se
  verificó una colisión de "suelo" con "entresuelo" (6 líneas reales, es
  una planta/piso, no el elemento suelo) frente a 485 líneas reales
  genuinas de suelo/pavimento — se acepta ese riesgo medido (1.2% de falsos
  positivos) porque la ganancia es sustancialmente mayor, a diferencia de
  "tirar" en la Decisión 3 donde la proporción no compensaba. "solado" no
  tiene ese problema.
- **Implementación**: nueva categoría `("flooring", ("suelo", "solado"))`.

### Decisión 8 — muebles de cocina/electrodomésticos es `kitchen_furniture` (elemento nuevo)

- **Expresión habitual**: "QUITAR MUEBLES DE COCINA. Quitar muebles de
  cocina existentes, con retirada a vertedero de escombros."
- **Acción**: `demolish` (vía "quitar", Decisión 3). **Elemento**:
  `kitchen_furniture` (nuevo). **Módulo principal**: sin cambios.
- **Condición que impide coincidencia exacta**: ninguna.
- **Motivo**: mobiliario y electrodomésticos de cocina son un elemento
  facturable propio en las reformas de vivienda de esta empresa.
- **Implementación**: nueva categoría `("kitchen_furniture", ("mueble de
  cocina", "muebles de cocina", "electrodomestico"))` — variantes
  singular/plural necesarias porque el motor compara substrings completos,
  no por token. Verificado: 0 falsos positivos contra la base real.

### Familia: alicatado (turno 2 de 8)

10 patrones de mayor frecuencia revisados con el usuario. Hallazgo
principal: "azulejo"/"alicatado" no tenían elemento propio pese a ser el
núcleo de esta familia — es el caso concreto que originó la revisión
completa del vocabulario cerrado (el XML de prueba de esta sesión daba
`sin_evidencia_ia` en dos partidas de alicatado).

### Decisión 9 — azulejo/alicatado es `tile` (elemento nuevo)

- **Expresión habitual**: "Quitar azulejo existente en baño, cocina y
  galería, con retirada de escombros a contenedor." / "COLOCACIÓN DE
  ALICATADO. Suministro y colocación de alicatado en paredes de cocina y
  galería..." (4 de los 10 patrones de mayor frecuencia de la familia,
  12 apariciones combinadas).
- **Acción**: `demolish` (vía "quitar"/"demolicion") o `install` (vía
  "colocacion"/"colocar"), según el patrón. **Elemento**: `tile` (nuevo).
  **Módulo principal**: sin cambios.
- **Condición que impide coincidencia exacta**: ninguna.
- **Motivo**: era el hueco más grande de toda la revisión — el elemento
  que da nombre al módulo no tenía representación en el vocabulario de
  elementos.
- **Implementación**: nueva categoría `("tile", ("azulejo",
  "alicatado"))`. Verificado: 0 falsos positivos en 577 (azulejo) y 1257
  (alicatado) líneas reales.

### Decisión 10 — rodapié es `skirting` (elemento nuevo, distinto de tile)

- **Expresión habitual**: "Demolición de rodapié cerámico con medios
  manuales y carga manual de escombros..." / "Rodapié cerámico de gres
  rústico, de 9 cm..." (3 de los 10 patrones, 8 apariciones combinadas).
- **Acción**: `demolish` o ninguna decidida (las líneas de suministro
  técnicas del rodapié no llevan verbo de acción reconocido). **Elemento**:
  `skirting` (nuevo). **Módulo principal**: sin cambios.
- **Condición que impide coincidencia exacta**: ninguna.
- **Motivo**: el rodapié es una partida facturable propia y distinta del
  alicatado de pared, aunque a menudo aparezcan en la misma obra — no se
  fusiona con `tile` a propósito.
- **Implementación**: nueva categoría `("skirting", ("rodapie",))`.
  Verificado: 0 falsos positivos en 540 líneas reales.

### Decisión 11 — pavimento/baldosa se añaden a `flooring`

- **Expresión habitual**: "DEMOLICIÓN PAVIMENTO CERÁMICO. Demolición de
  pavimento de baldosas cerámicas con medios manuales..."
- **Acción**: `demolish`. **Elemento**: `flooring` (ya existente,
  Decisión 7 — mismo elemento que suelo/solado). **Módulo principal**:
  sin cambios.
- **Condición que impide coincidencia exacta**: ninguna.
- **Motivo**: "pavimento" y "baldosa" son sinónimos reales de suelo/solado
  en este histórico, y no estaban cubiertos.
- **Implementación**: se añaden `"pavimento"` y `"baldosa"` a los
  sinónimos existentes de `flooring`. Verificado: 0 falsos positivos en
  1085 (pavimento) y 177 (baldosa) líneas reales.

### Descartado a propósito en esta familia

- **"revestimiento"** (903 líneas, 554 de ellas en el módulo `pintura`):
  demasiado genérico para mapearlo a `tile` — contaminaría elementos de
  pintura, impermeabilización, albañilería, etc. No se añade como palabra
  suelta.
- **"vierteaguas"** (frecuencia 2) y **"piezas de gran formato"**
  (frecuencia 2, patrón que solo aparecía bajo la palabra genérica
  "revestimiento"): volumen demasiado bajo para decidir con criterio en
  esta ronda. Quedan **sin decisión**, revisar más adelante si aparecen
  con más frecuencia.

### Familia: albañilería (turno 3 de 8)

10 patrones de mayor frecuencia revisados con el usuario. Hallazgo
distinto de las dos familias anteriores: varias líneas de especificación
técnica de materiales (p.ej. "Solado de baldosas cerámicas de gres
rústico, de 20x20 cm...") no contienen ningún verbo de acción reconocible
en absoluto — no hay palabra clave que lo arregle, quedan sin decisión
por diseño (no por falta de revisión).

### Decisión 12 — yeso es `plaster` (elemento nuevo)

- **Expresión habitual**: "REMATES DE YESO EN PAREDES Y TECHOS..." /
  "REMATE DE YESO EN PAREDES, al derribar tabiques..." (5 apariciones
  combinadas).
- **Acción**: variable según el patrón. **Elemento**: `plaster` (nuevo).
  **Módulo principal**: sin cambios.
- **Motivo**: el yeso de acabado/remate es un elemento facturable propio
  sin representación previa.
- **Implementación**: nueva categoría `("plaster", ("yeso",))`.
  Verificado: 0 falsos positivos en 750 líneas reales.

### Decisión 13 — roza(s) es `wall_channel` (elemento nuevo)

- **Expresión habitual**: "ROZAS EN VIVIENDA PARA INSTAL. ELECTRICIDAD.
  Abrir rozas y tapar, para nueva instalación de electricidad."
- **Acción**: `install` (vía "instalacion"). **Elemento**: `wall_channel`
  (nuevo). **Módulo principal**: sin cambios.
- **Motivo**: una roza (canal abierto en pared/muro para alojar
  instalaciones de electricidad o fontanería) es una partida facturable
  propia, distinta de `partition_wall`.
- **Implementación**: nueva categoría `("wall_channel", ("roza",))`.
  Verificado: 0 falsos positivos en 262 líneas reales.

### Decisión 14 — "derribar" como sinónimo de `demolish`

- **Expresión habitual**: "REMATE DE YESO EN PAREDES, al derribar
  tabiques y hacer rozas de electricidad en la vivienda."
- **Motivo**: verbo de demolición no cubierto por "demoler"
  (`demolicion`/`demoler` no son substring de `derribar`).
- **Implementación**: se añade `"derribar"` a `_ACTION_SYNONYMS["demolish"]`.
  Verificado: 0 falsos positivos en 10 líneas reales.

### Decisión 15 — "quitan" (forma conjugada) como sinónimo de `demolish`

- **Expresión habitual**: "REMATES DE YESO EN PAREDES Y TECHOS... donde
  se quitan los tabique o se realiza alguna actuación."
- **Motivo**: el infinitivo "quitar" (Decisión 3) no cubre por substring
  las formas conjugadas ("quitan", "quita", etc.) — se añade la forma
  real observada con mayor frecuencia en el histórico (45 líneas totales).
  No se generaliza a un stem corto tipo "quit" para no arriesgar
  colisiones no verificadas con otras formas.
- **Implementación**: se añade `"quitan"` a `_ACTION_SYNONYMS["demolish"]`.
  Verificado: 0 falsos positivos en 45 líneas reales.

### Descartado a propósito en esta familia

- Tres patrones de especificación técnica de solado/baldosas (frecuencia 2
  cada uno) no contienen ningún verbo de acción reconocible — quedan sin
  decisión porque no hay una palabra clave concreta que los resuelva, no
  por falta de revisión.
- Tres patrones de frecuencia 1 (zaguán/rampa, vallado de parcela,
  reparación monocapa) se descartan por volumen insuficiente para decidir
  con criterio en esta ronda.

### Familia: impermeabilización (turno 4 de 8)

10 patrones de mayor frecuencia revisados con el usuario. Esta familia
tuvo más candidatas descartadas que aceptadas: "galería", "balcón" y
"formación" resultaron, al comprobar su reparto por módulo, tan genéricas
como "revestimiento" (familia alicatado) — usadas como nombre de
habitación o verbo genérico en contextos sin relación entre sí, no como
señal fiable de un elemento o acción concreto. También se descartó
"retirada" pese a aparecer en uno de los 10 patrones.

### Decisión 16 — "desmontar" como sinónimo de `demolish`

- **Expresión habitual**: "SUBIR ENFRIADORA A/A A CUBIERTA. Desmontar
  enfriadora de Split de Aire Acondicionado..."
- **Motivo**: forma verbal no cubierta por el sustantivo "desmontaje"
  (mismo tipo de hueco que "derribar"/"quitan").
- **Implementación**: se añade `"desmontar"` a
  `_ACTION_SYNONYMS["demolish"]`. Verificado: 0 falsos positivos en 253
  líneas reales.

### Decisión 17 — "arranque" como sinónimo de `demolish`

- **Expresión habitual**: "Arranque de albardilla cerámica para
  cubrición de muros, con medios manuales, y carga manual de escombros..."
- **Motivo**: sinónimo claro de arrancar/demoler no cubierto.
- **Implementación**: se añade `"arranque"` a
  `_ACTION_SYNONYMS["demolish"]`. Verificado: 0 falsos positivos en 15
  líneas reales.

### Decisión 18 — "sellado"/"sellar" como acción nueva `seal`

- **Expresión habitual**: "SELLADO CON CAUCHO. Sellado con caucho con
  fibras los remates de chapa con encuentro de paredes para su
  impermeabilización."
- **Motivo**: no encajaba en ninguna acción existente. Repartido entre
  varios módulos (impermeabilización, fachada, pintura,
  sustitución_bajante) pero significa siempre lo mismo — a diferencia de
  "revestimiento"/"galería"/"formación" (descartados en esta misma
  familia), que cambian de sentido según el contexto.
- **Implementación**: nueva categoría `("seal", ("sellado", "sellar"))`.
  Verificado: 0 falsos positivos en 323+24 líneas reales.

### Decisión 19 — chapa es `sheet_metal` (elemento nuevo)

- **Expresión habitual**: "SELLADO CON CAUCHO... los remates de chapa
  con encuentro de paredes..."
- **Motivo**: chapa/flashing metálico de remates es un elemento
  facturable propio.
- **Implementación**: nueva categoría `("sheet_metal", ("chapa",))`. Un
  falso positivo minoritario aceptado: "rechapado" (de puertas de madera,
  sentido distinto) en 1 de 230 líneas reales — volumen insuficiente para
  descartar la palabra.

### Decisión 20 — albardilla es `coping` (elemento nuevo)

- **Expresión habitual**: "Arranque de albardilla cerámica para
  cubrición de muros..." / "Albardilla cerámica para cubrición de muros,
  en piezas de 40x20x4 cm."
- **Motivo**: albardilla (remate superior de un muro) es un elemento
  facturable propio.
- **Implementación**: nueva categoría `("coping", ("albardilla",))`.
  Verificado: 0 falsos positivos en 21 líneas reales.
- **Bug descubierto y corregido de paso**: 8 de las 21 líneas reales de
  albardilla (38%) usan "cubrición de muros", y `ABBREVIATIONS["cub"]` =
  "cubierta" en `work_type_normalizer.py` se aplicaba por **prefijo**, así
  que "cubrición" se normalizaba (incorrectamente) a "cubierta" y ganaba
  el elemento `roof` en vez de `coping`. Se corrigió excluyendo `"cub"`
  del matching por prefijo (`_PREFIX_MATCH_EXCLUDED` en
  `work_type_normalizer.py`) — sigue funcionando como abreviatura si
  aparece exacta (token `"cub"` solo), pero ya no captura "cubrición",
  "cubrir", "cubo", "cubanita"... Tests:
  `tests/test_work_type_normalizer.py::TestNormalizeText`.

### Descartado a propósito en esta familia

- **"galería"** (795 líneas, repartidas sin dominancia clara: demolición
  182, alicatado 129, carpintería 56...) y **"balcón"** (305 líneas,
  repartidas entre pintura, cerrajería, impermeabilización, fachada sin
  dominancia): se usan como nombre de habitación/ubicación en contextos
  muy distintos, igual que "fachada como ubicación" ya documentado en la
  Decisión 2 original. No se añaden como elemento.
- **"formación"** (559 líneas, repartidas entre alicatado, bajante,
  pintura, albañilería, impermeabilización): verbo genérico ("formación
  de pendientes", "formación de rampa", "formación de juntas") sin
  relación fiable con una acción concreta. Colisiona además con
  "transformación" (3 líneas, sentido distinto). No se añade.
- **"retirada"**: aparece en el patrón "Retirada de material de relleno
  en junta de pavimentación..." pero se descarta como palabra clave —
  3.221 líneas reales la contienen, de las cuales 1.977 coinciden con otra
  acción ya cubierta (mismo riesgo que "tirar"/"retirar" de la Decisión 3,
  a una escala mucho mayor: podría reproducir el problema de prioridad
  pintura/impermeabilización-vs-demolish documentado tras la Decisión 3,
  pero para cientos de líneas en vez de 2). El patrón concreto queda sin
  decisión.

### Familia: carpintería (turno 5 de 8)

10 patrones de mayor frecuencia revisados con el usuario. Hallazgo
principal: **"sustitución"** (629 líneas reales, 0 falsos positivos) no
tenía ninguna acción propia, pese a dar nombre al módulo
`sustitucion_bajante` — el mayor hueco de acción encontrado hasta ahora
en toda la revisión.

### Decisión 21 — "sustitucion" dentro de `install`

- **Expresión habitual**: "SUSTITUCIÓN PUERTA EXTERIOR Nº 2. Suministro y
  sustitución de puerta abatible..." / "SUSTITUCIÓN PUERTA ENTRADA.
  Suministro y sustitución de puerta de entrada a zaguán..."
- **Motivo**: sustituir implica instalar lo nuevo — consistente con como
  ya funcionan las líneas de `sustitucion_bajante` que evidencian precio
  vía "colocación" mencionada aparte. No se crea una acción `replace`
  separada para no fragmentar la evidencia entre dos categorías que en la
  práctica se solapan casi siempre.
- **Implementación**: se añade `"sustitucion"` a
  `_ACTION_SYNONYMS["install"]`. Verificado: 0 falsos positivos en 629
  líneas reales.
- **Mismo patrón ya conocido, de nuevo**: en la prueba de regresión
  contra la base real, 6 líneas cambiaron de `paint` a `install`. 4 son
  correcciones reales (el `paint` anterior venía de cláusulas negadas del
  tipo "no incluida la pintura"/"no contemplada la pintura", el mismo
  problema de menciones boilerplate ya visto en la Decisión 3). Pero
  **2 líneas tituladas explícitamente "PINTURA..."** ("PINTURA NATURAL AL
  SILICATO", "SUSTITUCIÓN PUERTA ENTRADA... y pintura de la puerta")
  pasan a `install` solo por mencionar "sustitución" de pasada — mismo
  problema de prioridad ya documentado tras la Decisión 3 (pintura/
  impermeabilización vs. demolish), esta vez con install. Volumen
  igualmente mínimo (2 líneas): aceptado como caso conocido, no se toca
  la lógica compartida de prioridad.

### Decisión 22 — mueble (genérico) es `furniture` (elemento nuevo)

- **Expresión habitual**: "Suministro y colocación de mueble laminado
  gris de 0,90x,83x0,54 para descalcificador, formado por módulo y
  encimera de laminado de madera."
- **Motivo**: mobiliario genérico, distinto de `kitchen_furniture`
  (Decisión 8, específicamente "mueble de cocina"). Al ir `kitchen_furniture`
  antes en la tabla, un texto que diga "mueble de cocina" sigue
  coincidiendo con esa categoría más específica primero.
- **Implementación**: nueva categoría `("furniture", ("mueble",))`. Dos
  falsos positivos menores aceptados (error de OCR "lmueble") de 693
  líneas reales.

### Decisión 23 — esmalte/esmaltado y barnizado/barnizar dentro de `paint`

- **Expresión habitual**: "PUERTAS DE ASCENSOR. Lijado superficial y
  aplicación de imprimación multiadherente... esmalte..." / "BARNIZADO
  PASAMANOS ESCALERA MADERA. Barnizado de pasamanos de escalera..."
- **Motivo**: esmaltar y barnizar son variantes del mismo concepto de
  acabado/pintura de superficie — no se separan en categorías propias
  para no fragmentar evidencia de conceptos que en la práctica son el
  mismo tipo de partida. **"lijado" deliberadamente NO se añade como
  acción**: es un paso de preparación previo (como "picado" antes de
  "reparación"), no la intervención global — si ganara prioridad,
  reproduciría el mismo problema ya documentado tras la Decisión 3.
- **Implementación**: se añaden `"esmalte"`, `"esmaltado"`, `"barnizado"`,
  `"barnizar"` a `_ACTION_SYNONYMS["paint"]`. Un falso positivo
  minoritario aceptado: "termoesmaltado" (ficha técnica de material, 3 de
  34 líneas).

### Decisión 24 — enlucido/maestreado como acción nueva `render`

- **Expresión habitual**: "Maestreado y enlucido en liso, las paredes de
  la cocina, estudio y pasillo hasta puerta existente."
- **Motivo**: maestrear y enlucir son la misma técnica de acabado de
  paramentos (maestrear prepara, enlucir remata) — mismo término "render"
  que ya usa `_SYSTEM_BY_ELEMENT` internamente para `facade_render`.
- **Implementación**: nueva categoría `("render", ("enlucido",
  "maestreado"))`. Verificado: 0 falsos positivos en 644+155 líneas
  reales.

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

