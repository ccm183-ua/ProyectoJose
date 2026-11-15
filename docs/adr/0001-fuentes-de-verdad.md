# ADR 0001 — Fuente de verdad por entidad

- **Estado**: Aceptada
- **Fecha**: 2026-07-21
- **Contexto del roadmap**: H2.1 (`docs/ROADMAP_ESTABILIZACION_Y_EVOLUCION_IA.md`)

## Contexto

El inventario en `CONTEXT.md` muestra tres almacenes con solapamiento parcial: Excel,
`presupuesto`/`presupuesto_partida`, y `historical_budget`/`historical_partida`. Antes de
migrar a un backend web (H3+) hace falta declarar, sin ambigüedad, cuál es la fuente de
verdad de cada entidad **hoy** y cuál será el destino, para no arrastrar el mismo término
con dos significados durante la migración.

## Decisión

### Fuente de verdad actual (mientras dure la app de escritorio)

| Entidad | Fuente de verdad hoy | Rol de SQLite |
|---|---|---|
| Cabecera y partidas de un presupuesto activo | **Excel** (`ruta_excel`) | `presupuesto`/`presupuesto_partida` es índice/caché de lectura rápida para el dashboard |
| Presupuesto finalizado | **`presupuesto_partida` con `es_finalizado=1`** | Es un snapshot congelado en el momento de finalizar; el Excel puede seguir existiendo pero ya no es la fuente que la app confía por defecto una vez finalizado |
| Memoria de aprendizaje (módulos, patrones, decisiones de inclusión) | **`historical_budget`/`historical_partida`** | No hay Excel equivalente una vez que el análisis ha corrido; si el Excel de origen desaparece, esta tabla es la única fuente restante |
| Historial de accesos recientes | Ninguna con impacto — write-only, sin consumidor en la GUI actual | N/A |

Esto formaliza lo que el código ya hace de facto (`WHERE presupuesto.es_finalizado = 0` en
`upsert_presupuesto`, protección explícita contra sobrescritura de históricos en
`database.py`/`database_persistence.py`): **no existe hoy un "presupuesto canónico"
único e independiente de Excel**. Excel sigue siendo el artefacto que el usuario edita y
entrega; SQLite es soporte, no sustituto.

### Fuente de verdad objetivo (tras H3)

Cuando se implemente el dominio canónico (H3 del roadmap):

- `budget` + `budget_version` en el backend serán la fuente de verdad; toda escritura de
  negocio (crear, editar, aprobar) pasa por ahí primero.
- Excel se convierte en **adaptador de importación/exportación** (ver ADR 0002): se
  importa una vez como versión inicial, y se exporta bajo demanda desde el dominio
  canónico — deja de ser el sitio donde "vive" el dato.
- La memoria histórica (`historical_budget`/`historical_partida`) migra su rol de
  "aprendizaje sobre Excel" a "aprendizaje sobre versiones aprobadas del dominio
  canónico", pero conserva su naturaleza de tabla irrecuperable: no se borra por
  migración, se re-vincula.

### Qué NO se decide aquí

- Vigencia de precios, catálogo o campos mínimos: quedan para H5/H6, según la tabla de
  decisiones del propietario en el roadmap.
- Retirada de `historial_presupuesto`: al no tener consumidor de lectura, es candidata a
  simplificar, pero tocarla no es parte de H2.1 (evitar over-engineering al margen del
  objetivo del hito).

## Consecuencias

- Ningún cambio de código en este hito: es una declaración explícita de un contrato ya
  vigente implícitamente, para poder auditar futuras violaciones (p. ej. un nuevo caso de
  uso que escriba en `presupuesto_partida` sin pasar por `es_finalizado`).
- H2.2 (caso de uso fuera de PySide6) y H3 (dominio canónico) deben respetar esta tabla:
  ninguna escritura nueva a `presupuesto`/`presupuesto_partida` debe saltarse el guard de
  `es_finalizado`, y ninguna migración debe borrar `historical_budget`/`historical_partida`
  sin backup previo (ya implementado en `database_persistence.py`, mantenerlo).
