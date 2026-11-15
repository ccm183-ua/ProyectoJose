# Calendario de obras (pieza C) — diseño

> Pieza C de la batería «obras» (D imprimir directo → A planificación →
> B avisos y correo → C calendario y métricas). Se adelanta a B a petición del
> usuario (2026-11-15). Usa los datos de la pieza A
> (`docs/superpowers/specs/2026-11-13-planificacion-obras-design.md`).
> Retomada por esta sesión porque la sesión de la pieza A está desconectada.

## Problema

La pieza A guarda fechas previstas y reales por obra, pero solo se ven como
columnas sueltas en cada pestaña del dashboard. No hay forma de ver qué obras
empiezan cada semana ni de repartir las de EJECUTAR en el tiempo.

## Datos reales (BD del usuario, 2026-11-15)

- `obra_planificacion`: 221 filas, **0** con alguna fecha (prevista o real).
- Cartera: 23 obras en EJECUTAR, 22 en EJECUTANDO, 51 en TERMINADO.
- 7 carpetas traen una fecha en el nombre que `date_from_folder_name` ya
  entiende (5 de ellas en EJECUTAR).

Consecuencia: el calendario sirve sobre todo para **poner** fechas; las
métricas tendrán pocos datos durante meses y deben decir en cuántas obras se
basan.

## Objetivo y criterio de éxito

- Ver en un mes qué obras empiezan y terminan, de todas las fases con fechas.
- Poner y mover fechas previstas arrastrando, sin preguntas y con Deshacer.
- Que ninguna fecha real se cambie por accidente y que nada se invente: las
  propuestas leídas del nombre solo se guardan al pulsar «Poner esta fecha».

## 1. Qué se ve

**Ventana «Calendario de obras»** (no modal, una sola instancia), abierta desde
un cuarto botón «Calendario de obras» en la pantalla de inicio y desde
Herramientas → «Calendario de obras…».

```
┌ ◀  Noviembre 2026  ▶  [Hoy]  [⟳] ──────────────────────────┐ ┌ Sin fecha (18) ──────────┐
│ Este mes: 4 empiezan · 3 terminan · 2 con retraso ·        │ │ 114-26 Rafael Asín       │
│           duración media 12 días (5 obras)                  │ │   ≈ 13/07 según el nombre│
├──────┬──────┬──────┬──────┬──────┬──────┬──────────────────┤ │   [Poner esta fecha]     │
│ L 16 │ M 17 │ X 18 │ J 19 │ V 20 │ S 21 │ D 22             │ │ 127-25 Tte. Llorca       │
│      │▶208-26│      │▶030-26│     │      │                  │ │  Arrastra una a un día   │
│      │■117-26│      │      │      │      │                  │ │                          │
└──────┴──────┴──────┴──────┴──────┴──────┴──────────────────┘ └──────────────────────────┘
```

### Cuadrícula del mes

- Semanas de lunes a domingo; los días de los meses vecinos que completan la
  primera y la última semana se ven atenuados y sin etiquetas.
- El día de hoy, resaltado. «◀ ▶» cambian de mes; «Hoy» vuelve al mes actual.

### Etiquetas

Cada obra aparece en su fecha de inicio y en la de fin; en cada extremo se
usa la fecha real si existe y, si no, la prevista:

| Fase | Inicio | Fin |
|---|---|---|
| EJECUTAR | ▶ `inicio_previsto` | ■ `fin_previsto` (si lo hay) |
| EJECUTANDO | ▶ `inicio_real` (o `inicio_previsto` si no hay real) | ■ `fin_previsto` |
| TERMINADO | ▶ `inicio_real` | ✔ `fin_real` |

- Una obra sin fecha para un extremo no muestra ese extremo.
- Prevista: borde discontinuo. Real: relleno. Aproximada: prefijo «≈».
- Texto: número de proyecto + nombre corto (lo que va tras el número en el
  nombre de la carpeta, recortado a 18 caracteres). Ayuda emergente: nombre
  completo de la carpeta, fase y «previsto»/«real»/«aproximado».
- Colores, siempre con un indicador de texto además del color:
  - EJECUTAR, inicio dentro del margen (`color_category == "warning"`): ámbar.
  - EJECUTAR, inicio ya pasado (`"late"`): rojo y «(pasada)» en la ayuda.
  - EJECUTANDO, fin previsto ya pasado: rojo y «(con retraso)» en la ayuda.
- Más de 3 etiquetas en un día: se muestran 3 y un «+N más» que despliega la
  lista completa del día en un menú con las mismas acciones.

### «Sin fecha»

- Obras de EJECUTAR sin `inicio_previsto`, ordenadas por número de proyecto.
- Si `planificacion_propuesta` existe (fecha leída del nombre), se muestra
  «≈ dd/mm según el nombre» y un botón «Poner esta fecha».

### Franja de resumen (mes visible)

«N empiezan · N terminan · N con retraso · duración media N días (N obras)»:

- **empiezan**: etiquetas de inicio con fecha en el mes.
- **terminan**: etiquetas de fin con fecha en el mes.
- **con retraso**: obras EJECUTANDO con fin previsto < hoy, más obras EJECUTAR
  con inicio previsto < hoy (a día de hoy, sin depender del mes).
- **duración media**: obras TERMINADO con `fin_real` en el mes e inicio y fin
  reales; con menos de 3 obras se escribe «duración media: sin datos
  suficientes».

### Origen de las obras

- La caché del dashboard (`get_all_presupuestos_cache`), filas de EJECUTAR,
  EJECUTANDO y TERMINADO, con la planificación añadida por
  `enrich_with_planning(..., reconcile=False)`. Abre al instante, sin escanear.
- «⟳» relee la caché y la planificación (no escanea carpetas; eso lo sigue
  haciendo «⟳ Actualizar» del dashboard). Ayuda: «Para detectar carpetas
  movidas fuera de la app, actualiza el dashboard».
- Números repetidos o vacíos (`planificacion_duplicado`): no salen; pie
  «N obras con número repetido, no se pueden planificar».
- Si la ventana se abre con la caché vacía: aviso «Abre "Presupuestos
  existentes" una vez para cargar las obras».

## 2. Poner y mover fechas

Ningún cambio pregunta; todos muestran `show_toast` con «Deshacer», que
restaura la instantánea previa con `restore_plan_snapshot`.

| Arrastrar… | Efecto | Aviso |
|---|---|---|
| obra de «Sin fecha» → día | `inicio_previsto` = día | «114-26: inicio previsto el 17/11» |
| ▶ previsto → otro día | nuevo `inicio_previsto`; si hay `fin_previsto`, se desplaza los mismos días | «…: inicio previsto movido al 19/11» |
| ■ previsto → otro día | nuevo `fin_previsto`; si queda antes del inicio (real o previsto), no se cambia | «…: fin previsto el 30/11» / «El fin no puede ser antes del inicio (17/11)» sin Deshacer |
| ▶ previsto → «Sin fecha» | `inicio_previsto` y `fin_previsto` a vacío | «…: fechas previstas quitadas» |

- Las fechas previstas guardadas al arrastrar son exactas. Se arrastran el
  ▶ previsto de EJECUTAR y el ■ previsto de EJECUTAR y EJECUTANDO.
- Las etiquetas de fecha real no se arrastran (cursor normal; ayuda «Fecha
  real: se cambia con doble clic»).
- Soltar en un día atenuado de otro mes o fuera de la cuadrícula no hace nada.
- **Doble clic** en una etiqueta: `ObraPlanningDialog`, igual que en el
  dashboard; al guardar, se actualiza la obra.
- **Clic derecho** en una etiqueta: Planificación… · Abrir Excel · Abrir
  carpeta · Quitar fechas previstas (con Deshacer; desactivado si no tiene).
- **«Poner esta fecha»**: guarda la propuesta como `inicio_previsto`. Toast
  con Deshacer.

**Decisión — previstas aproximadas**: la pieza A solo tiene marca de
aproximada para las fechas reales, no para las previstas, y no se añade
columna nueva. Una propuesta de solo mes («EN JULIO'26») ya llega como día 1
(`date_from_folder_name` → `(date(2026, 7, 1), True)`). Al guardarla, la
fecha es ese día 1 y, si las notas de la obra están vacías, se escriben
«Fecha prevista aproximada (solo el mes en el nombre de la carpeta)». En el
calendario se ve como prevista exacta; el «≈» de las previstas solo aparece
en la propuesta de «Sin fecha». Así no se toca el esquema de la pieza A.

### Calendario y dashboard al día

- `src/gui/planning_events.py`: objeto único con la señal
  `planning_changed(list[str])` (números de proyecto).
- La emiten: el calendario al guardar o deshacer; el dashboard en
  `_on_planning`, `_move_project` y `_undo_move`.
- Al recibirla, el dashboard vuelve a leer con `get_planes` solo esas obras y
  repinta sus filas; el calendario hace lo mismo con sus etiquetas. Ninguno
  escanea carpetas. Cada ventana ignora la señal que emitió ella misma.

### Errores

- Escritura fallida: ventana de error con el motivo; la etiqueta vuelve a su
  sitio; no hay toast.
- Lectura de la planificación fallida: las obras se muestran sin fechas (todas
  las de EJECUTAR en «Sin fecha») con aviso «No se pudo leer la
  planificación» sobre la cuadrícula; se puede seguir poniendo fechas.
- Excel o carpeta que ya no existen: el mismo aviso que el dashboard.

## 3. Código

- `src/core/obra_calendar.py` (sin Qt):
  - `CalendarEvent` (dataclass congelada): `numero`, `texto`, `ayuda`,
    `fase`, `tipo` ("inicio" | "fin"), `fecha`, `real` (bool), `aproximada`
    (bool), `color` ("" | "warning" | "late"), `arrastrable` (bool),
    `ruta_excel`, `ruta_carpeta`.
  - `build_events(filas_por_estado, hoy, margen_general) -> list[CalendarEvent]`.
  - `month_weeks(año, mes) -> list[list[date]]`.
  - `events_by_day(eventos) -> dict[date, list[CalendarEvent]]` (ordenados:
    inicio antes que fin, luego número).
  - `unscheduled(filas_ejecutar) -> list[dict]` (número, texto, ayuda,
    propuesta).
  - `month_summary(eventos, planes_por_obra, año, mes, hoy) -> MonthSummary`
    y `summary_text(MonthSummary) -> str`.
  - `drop_fields(plan, tipo, nueva_fecha) -> tuple[dict | None, str]`
    (campos a guardar o motivo del rechazo).
- `src/core/obra_calendar_service.py`: `load_calendar_data(hoy)` → filas por
  estado enriquecidas + números repetidos + error de lectura (si lo hay).
- `src/gui/obra_calendar_window.py`: `ObraCalendarWindow` (cabecera, franja,
  cuadrícula, lista «Sin fecha», pie), `_DayCell`, `_EventChip`; arrastre con
  `QMimeData` de tipo `application/x-cubiapp-obra` (número + tipo).
  Carga con `run_in_background`.
- `src/gui/planning_events.py`: señal compartida.
- `src/gui/main_frame.py`: botón y entrada de menú; una sola ventana.
- `src/gui/budget_dashboard.py`: emitir y escuchar `planning_changed`.

## Pruebas

- `tests/test_obra_calendar.py`: cada fase con fechas reales/previstas/
  aproximadas y extremos vacíos; colores; `month_weeks` de un mes que empieza
  en domingo y de febrero bisiesto; «Sin fecha» con y sin propuesta; resumen
  con 0, 2 y 3 terminadas; `drop_fields` (desplazar fin, fin antes del inicio,
  real no arrastrable, quitar).
- `tests/test_obra_calendar_window.py` (offscreen): etiquetas en su día, «+N
  más», soltar guarda y muestra toast, Deshacer restaura, real no arrastrable,
  «Poner esta fecha», error de escritura deja la etiqueta.
- `tests/test_planning_events.py`: el dashboard refresca filas al recibir la
  señal y emite al guardar/mover/deshacer; ignora la suya.
- Suite completa en verde con el Python del venv.

## Fuera de alcance

- Pieza B: panel de avisos al abrir, correo en Gmail, marcar como avisada.
- Vista por semanas o Gantt; arrastrar entre meses; pestaña de métricas.
- Escanear carpetas desde el calendario.

## Rama

`calendario-obras`, creada desde `dashboard-filtros-ux` (462374f), que ya
trae la planificación, el toast con Deshacer y `restore_plan_snapshot`. Se
integra después de `dashboard-filtros-ux`.
