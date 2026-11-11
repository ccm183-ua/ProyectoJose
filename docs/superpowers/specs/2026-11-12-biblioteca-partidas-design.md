# Biblioteca de partidas — diseño

> Mejora 1 de 4 de la batería "redactar partidas" (opción A, acordada el
> 2026-11-12): **1. biblioteca del histórico** → 2. partir de un presupuesto
> anterior → 3. catálogo de precios propio (interfaz de H5) → 4. consulta web
> controlada (H8). Las mejoras 2-4 reutilizarán la búsqueda, la vista de
> evidencia y la inserción sin duplicados de esta.

## Problema

Las partidas se redactan casi siempre a mano: se rescatan de presupuestos
anteriores y se ajustan, o se consultan webs de precios. La IA de la app
apenas se usa. Hoy no hay forma de buscar en las ~17.000 partidas con precio
del histórico desde la app: hay que acordarse de en qué presupuesto estaba
cada una y abrir su Excel.

## Objetivo y criterio de éxito

Desde la app, encontrar una partida ya presupuestada, ver qué precio se ha
puesto en otras obras y con qué respaldo, e insertarla en un presupuesto
(nuevo o existente) sin duplicados, en menos tiempo que abriendo Excels
antiguos.

- Una búsqueda responde en < 200 ms con el histórico cargado.
- La biblioteca carga las ~17.000 partidas en < 3 s sin congelar la ventana.
- Ninguna partida no aprobada se hace pasar por evidencia de precio.

## Datos de partida (medidos el 2026-11-11 sobre la BD real)

- 17.172 partidas con precio > 0 en 2.331 presupuestos; solo 1.161 de
  presupuestos aprobados (`INCLUDED`, 386 presupuestos); 875 presupuestos
  pendientes de revisión y 1.070 no aptos (casi sin partidas con precio).
- 5.853 conceptos normalizados distintos con precio.
- 33 variantes de unidad para pocas unidades reales; 56 % de las partidas con
  precio son partida alzada (`p.a.`).
- `fecha_presupuesto` mezcla "dd/mm/aa" con número de serie de Excel
  ("46036" = 14/01/2026) y contiene basura ("%", nombres de calle).

## Decisiones tomadas con el usuario

1. Se muestran **todas** las partidas con precio, cada una etiquetada como
   aprobada, sin revisar o no apta.
2. Se accede **al crear** un presupuesto (alternativa a la IA) y **al
   editar** uno existente desde el dashboard.
3. Las líneas iguales se **agrupan**; se propone la mediana (de las aprobadas
   si las hay) y se puede elegir el precio de una obra concreta.

## Arquitectura

| Pieza | Fichero | Responsabilidad | Depende de |
|---|---|---|---|
| `PartidaLibrary` | `src/core/partida_library.py` (nuevo) | Cargar, buscar, agrupar, calcular cifras y convertir la selección en candidatas. Sin PySide6. | BD en solo lectura, `normalize_text`, `keyword_in_text` |
| `PartidaLibraryDialog` | `src/gui/partida_library_dialog.py` (nuevo) | Buscador, filtros, tabla agrupada, detalle por obra, cesta. Nunca escribe en el Excel. | `PartidaLibrary`, `run_in_background` |
| Revisión | `src/gui/combined_partidas_review_dialog.py` | Nueva lista opcional `library_partidas` y etiqueta de origen "Biblioteca · …". | — |
| Al crear | `src/gui/main_frame.py` | Elegir "Biblioteca", "IA" o "Dejar vacío" antes de generar partidas. | Diálogo, revisión, `apply_reviewed_partidas` |
| Al editar | `src/gui/budget_dashboard.py` | Acción "Añadir partidas desde la biblioteca" en el menú de edición. | Ídem + `exclude_existing_from_candidates` |

Flujo: buscar → elegir (y opcionalmente el precio de una obra) → tabla de
revisión existente → `apply_reviewed_partidas` (en "añadir", tras
`exclude_existing_from_candidates`).

## Núcleo: `PartidaLibrary`

### Carga

Una consulta de solo lectura: `historical_partida` con `precio_unitario > 0`
JOIN `historical_budget` LEFT JOIN `historical_partida_feature`. Por línea:
id, presupuesto, nombre del proyecto, `concepto_original`,
`concepto_normalizado`, unidad, precio, `learning_status`, `analysis_status`,
`fecha_presupuesto`, `primary_module_id`.

Se descartan al cargar, contándolas: precio no finito, concepto normalizado
vacío. Las líneas de presupuestos con `analysis_status` distinto de `VALID` /
`VALID_WITH_WARNINGS` se cargan como **no aptas**.

### Estado de cada línea

| `learning_status` | Estado |
|---|---|
| `INCLUDED` | `approved` (aprobada) |
| `PENDING_REVIEW` | `unreviewed` (sin revisar) |
| `NOT_ELIGIBLE` u otro, o análisis no válido | `ineligible` (no apta) |

### Unidad canónica (solo para agrupar)

`p.a.` ← p.a., P.A., p.a, pa, P.a., Partida · `ud` ← ud, Ud, UD, ud. ·
`m2` ← m2, M2, m² · `m` ← m, M, ml · `m3` · `kg` · `día` ← dia, días, DIAS.
Cualquier otra → `?` (grupo propio, marcado). Comparación sin tildes ni
mayúsculas. La unidad que se inserta es la original de la línea elegida (o la
más frecuente del grupo).

### Fecha

Se acepta "dd/mm/aa", "dd/mm/aaaa" y número de serie de Excel entre 30000 y
60000 (≈1982-2064). Cualquier otro valor → sin fecha. No se usa la fecha de
modificación del fichero como fecha del presupuesto.

### Búsqueda

- La consulta se normaliza con `normalize_text`; se parte en palabras.
- Una línea casa si **todas** las palabras aparecen en su concepto
  normalizado con `keyword_in_text` (desde inicio de palabra).
- Filtros opcionales: módulo principal, unidad canónica, estado
  (`todas` / `solo aprobadas` / `sin no aptas`).
- Consulta vacía + sin filtros → sin resultados (no se listan 17.000).

### Agrupación y cifras

Clave: (`concepto_normalizado`, unidad canónica). Por grupo:

- líneas, obras distintas;
- mínimo, mediana y máximo de todas las líneas;
- mediana de las aprobadas (si hay);
- estado = mejor de sus líneas (aprobada > sin revisar > no apta);
- fecha más reciente válida;
- módulo = el más frecuente entre sus líneas con módulo.

**Precio propuesto**: mediana de aprobadas si existe (`median_approved`);
si no, mediana de todas (`median_all`) con aviso "sin evidencia aprobada".
En `p.a.`, aviso adicional "partida alzada: revisa el alcance".

**Orden**: con evidencia aprobada primero → nº de obras desc. → fecha más
reciente desc. → concepto. Se devuelven como máximo 200 grupos, indicando si
había más.

### Conversión a candidata

```
{
  "titulo": <primera línea del concepto original>,
  "descripcion": <resto del concepto original>,
  "concepto": <concepto original>,
  "unidad": <unidad original>,
  "cantidad": 1.0,
  "precio_unitario": <precio elegido>,
  "source": "library",
  "library_status": "approved" | "unreviewed" | "ineligible",
  "library_price_basis": "median_approved" | "median_all" | "instance",
  "library_partida_ids": [...],
  "library_budget_ids": [...],
}
```

`source` nunca empieza por `historical`: `split_generated_partidas_for_review`
y el resto del flujo no la tratan como evidencia.

## Interfaz: `PartidaLibraryDialog`

- Buscador con espera de 300 ms; filtros de módulo, unidad y estado.
- Tabla de grupos: concepto, unidad, módulo, precio propuesto, rango, obras,
  estado (texto + color), fecha. Aviso "afina la búsqueda" si hay más de 200.
- Detalle del grupo: sus líneas (obra, fecha, precio, estado, texto) y
  "Usar este precio"; avisos del grupo.
- Cesta: doble clic o "Añadir a la selección"; quitar; nº de partidas e
  importe a cantidad 1.
- "Continuar a la revisión (N)" / "Cancelar". Devuelve candidatas; no escribe.
- Carga en segundo plano con `run_in_background`; si falla, aviso y tabla
  vacía. Avisa de cuántas líneas se ignoraron al cargar.

## Integración

- **Revisión**: `CombinedPartidasReviewDialog(..., library_partidas=...)`.
  Origen "Biblioteca · aprobada / sin revisar / no apta"; en el detalle, la
  base del precio.
- **Al crear** (`main_frame`): antes del flujo de partidas, pregunta
  "¿Cómo quieres añadir las partidas?" → Biblioteca / IA / Dejar vacío. "IA"
  es el flujo actual; "Dejar vacío" equivale al "Saltar" actual. Biblioteca →
  revisión → `apply_reviewed_partidas(MODE_CREATE)`.
- **Al editar** (`budget_dashboard`): acción "Añadir partidas desde la
  biblioteca" → `exclude_existing_from_candidates` frente a las partidas del
  Excel → revisión → `apply_reviewed_partidas(MODE_APPEND)`, con el mismo
  cierre que "Añadir partidas" hoy.

## Errores

| Situación | Comportamiento |
|---|---|
| Falla la carga (BD bloqueada, esquema antiguo) | Aviso en el diálogo, tabla vacía; la app sigue. |
| Líneas inválidas al cargar | Se ignoran y se cuentan en un aviso discreto. |
| Búsqueda sin resultados | Mensaje "sin resultados" con sugerencia de quitar filtros. |
| Cancelar en la biblioteca o en la revisión | Sin efectos en el Excel ni en la BD. |
| Falla la escritura en el Excel | Mismo aviso que el flujo actual de añadir. |

## Pruebas

- **Núcleo** (sin interfaz, BD temporal): búsqueda multipalabra desde inicio
  de palabra; unidades canónicas y `?`; agrupación; mediana de aprobadas frente
  a la de todas; precio propuesto y avisos; orden; fechas dd/mm/aa, serie de
  Excel y basura; límite de 200; conversión a candidata con las tres bases.
- **Flujo**: las candidatas `library` no se clasifican como históricas;
  en "añadir", duplicados exactos descartados y dudosos marcados.
- **Interfaz** (offscreen): cesta, "usar este precio", el diálogo no escribe,
  cancelar sin efectos, etiqueta de origen en la revisión, los dos puntos de
  entrada.
- **Validación con datos reales** (copia de la BD): búsquedas de referencia
  ("bajante pvc", "impermeabilización cubierta", "picado fachada", "tirar
  tabique") con nº de grupos y tiempos de carga y de búsqueda.

## Fuera de alcance

- Editar o aprobar partidas desde la biblioteca (eso es la mejora 3).
- Partir de un presupuesto entero (mejora 2) y consulta web (mejora 4).
- Ajuste de precios por antigüedad o IPC.
- Cambios en la memoria histórica o en los patrones: la biblioteca es solo
  lectura.
