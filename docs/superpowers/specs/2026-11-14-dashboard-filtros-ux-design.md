# Filtros y limpieza de UX en «Presupuestos existentes» — diseño

> Tanda 1 de 2 del pulido del circuito anterior a las partidas (acordado el
> 2026-11-14). Tanda 2: «Crear presupuesto» y «Gestionar base de datos».
> Sustituye las fases 1-2 de `docs/planes/dashboard-filtros-estadisticas.md`;
> sus estadísticas (fase 3) quedan fuera.

## Problema

- No hay forma de acotar la tabla salvo el buscador de texto.
- La pantalla tiene 8 botones con solapes (dos para columnas, «Actualizar» y
  «Escanear presupuestos» se confunden, «Abrir ▼» es un menú de dos opciones).
- Muchas ventanas bloquean para avisar de un éxito o preguntan antes de algo
  que se puede deshacer (mover carpetas) o que ya tiene otro paso de
  confirmación (regenerar campos).

## Datos reales (BD del usuario, 2026-11-14)

- 230 presupuestos en caché; 0 administraciones y 0 comunidades dadas de alta,
  así que `administracion_nombre`, `comunidad_id` y `administracion_id` están
  vacíos en todas las filas.
- 162 filas tienen `cliente` (123 distintos).
- `fecha`: 162 con formato `dd-mm-yy` (p. ej. `16-01-26`), 68 vacías.
- `total`: 75 vacíos o a cero.

## 1. Filtros

### Interfaz

En cada pestaña de estado, a la derecha del buscador, un botón
**«Filtros»** (con el número de filtros activos: «Filtros (2)») que despliega
una fila bajo el buscador:

| Control | Detalle |
|---|---|
| Cliente | Combo editable con autocompletado; opciones = clientes distintos de las filas de esa pestaña, ordenados; vacío = todos. |
| Administración | Igual, con los `administracion_nombre` de las filas. Desactivado (con ayuda «No hay administraciones en estos presupuestos») si no hay ninguno. |
| Fecha desde / hasta | Dos campos de fecha opcionales (casilla para activarlos). Límites inclusivos. |
| Importe mín. / máx. | Dos campos numéricos opcionales, en euros, sobre `total` (con IVA). Límites inclusivos. |
| Limpiar filtros | Quita todos los filtros de la pestaña. |

- Plegada, la fila deja ver los filtros activos como etiquetas («Fincas Sol ×»,
  «desde 01/01/26 ×», «≥ 5.000 € ×»); la × quita solo ese filtro.
- Siempre visible, a la derecha: resumen de lo que muestra la tabla:
  «12 presupuestos · 84.300 €» (suma de `total` de las filas visibles; las
  filas sin total cuentan en el número pero no suman).
- Si la combinación deja la tabla vacía y la pestaña tiene filas: fila de aviso
  «Ningún presupuesto cumple los filtros» y botón «Limpiar filtros».

### Comportamiento

- Estado de filtros **por pestaña**, en memoria; se combinan con el buscador
  de texto (ambos deben cumplirse).
- Se mantienen al refrescar filas, al pulsar «Actualizar» y al cambiar de
  pestaña; se pierden al cerrar el dashboard.
- Tras recargar, las opciones de los combos se recalculan; si el cliente
  elegido ya no está en la pestaña, el filtro se conserva (la tabla queda
  vacía con el aviso anterior).
- Con un filtro de fecha activo, las filas sin fecha o con fecha ilegible se
  ocultan; con un filtro de importe activo, las filas sin total se ocultan.
- La comparación de cliente/administración es exacta tras normalizar
  (espacios y mayúsculas).
- Modo Explorador: el botón «Filtros» y el resumen se ocultan.

### Código

- `src/core/budget_filters.py` (sin Qt):
  - `BudgetFilters` (dataclass): `cliente`, `administracion` (str, "" = todos),
    `fecha_desde`, `fecha_hasta` (`date | None`), `importe_min`, `importe_max`
    (`float | None`); `is_empty()`, `active_count()`.
  - `parse_budget_date(value) -> date | None`: `dd-mm-yy`, `dd/mm/yy`,
    `dd-mm-yyyy`, `dd/mm/yyyy`, ISO `yyyy-mm-dd`; otro → `None`.
  - `apply_filters(rows, filters) -> list`.
  - `summarize(rows) -> (count, total_eur)`.
  - `distinct_values(rows, key) -> list[str]`.
- `src/gui/widgets/budget_filter_bar.py`: widget con botón, fila plegable,
  etiquetas y resumen; emite `filters_changed(BudgetFilters)`; métodos
  `set_options(clientes, administraciones)` y `set_summary(count, total)`.
- `budget_dashboard.py`: `_tab_filters[state]`, una barra por pestaña;
  `_populate_table` aplica texto + filtros y actualiza el resumen.

## 2. Botones

### Cabecera

`Explorador` · `⟳ Actualizar` · **`Columnas ▼`**

`Columnas ▼` sustituye a «Ocultar datos extra» y «Restaurar columnas»: una
casilla por columna, «Datos extra (Origen, Finalizado, Calidad)» y
«Restaurar columnas». Usa el mismo estado que el menú contextual de la
cabecera de la tabla, que se mantiene.

### Barra de acciones

| Botón | Acción |
|---|---|
| **Abrir Excel** (principal) | Lo que hoy es Abrir ▼ → Abrir Excel. |
| **Abrir carpeta** | Lo que hoy es Abrir ▼ → Abrir carpeta. |
| **Editar ▼** | Regenerar campos · Finalizar (nuevo) · ─ · Regenerar todas las partidas (IA) · Añadir más partidas (IA) · Añadir partidas desde la biblioteca · ─ · Exportar PDF |
| **Releer del Excel** | Lo que hoy es «Escanear presupuestos». Ayuda: «Vuelve a leer los Excels seleccionados. Para recargar todas las carpetas, usa ⟳ Actualizar». |

- **Finalizar**: llama a `BudgetService.finalize_budget(ruta, estado=…)` sobre
  el seleccionado y refresca su fila. Solo con un único Excel existente
  seleccionado.
- «Regenerar campos» con varios seleccionados conserva el comportamiento por
  lotes actual.
- Cada botón desactivado lleva en su ayuda el motivo («Selecciona un
  presupuesto», «El Excel no existe»).
- Menú contextual de fila: se mantiene lo actual y se añade un submenú
  **Editar ▸** con las mismas entradas que el botón.
- Atajos: Intro = Abrir Excel; Ctrl+F = foco en el buscador de la pestaña;
  F5 = Actualizar.
- Las acciones de partidas no cambian de comportamiento, solo de sitio.

## 3. Confirmaciones y avisos

**Regla**: solo se pregunta antes de algo irreversible que borra o sustituye
contenido del Excel. Los éxitos se notifican con un aviso pasajero. Los
errores siguen en ventana.

### Aviso pasajero

`src/gui/widgets/toast.py`: barra en la parte inferior de la ventana que lo
muestra, con texto y hasta dos botones de acción; se cierra sola a los 5 s
(8 s si tiene botones), al pulsar una acción o con su ×. Un aviso nuevo
sustituye al anterior. No roba el foco. API:
`show_toast(parent, text, actions=[(label, callback)], timeout_ms=None)`.

### Cambios

| Caso | Antes | Después |
|---|---|---|
| Mover proyectos | Pregunta + ventana de resultado | Sin pregunta. Toast «N proyecto(s) movidos a X · [Deshacer]». Con fallos: ventana con la lista de fallos (y el toast para los movidos). |
| Deshacer mover | — | Devuelve cada carpeta movida a su origen (si el origen no existe ya) y restaura la planificación de la obra a la instantánea tomada antes de mover. Toast con el resultado; ventana solo si algo falla. Recarga como hoy. |
| Guardar un Excel abierto (vigilante) | Pregunta «¿Finalizar?» | Refresca la fila sin preguntar y muestra toast «Se guardó X · [Finalizar]». Se elimina `_excel_no_finalize`. |
| Abrir Excel ilegible | Pregunta «¿Abrir igualmente?» | Abre sin preguntar; la fila queda con ⚠ y el motivo (diagnóstico existente). |
| Releer del Excel | Ventana de resumen | Sin fallos: toast «Releídos N». Con fallos: la ventana actual con motivos. |
| Exportar PDF | Pregunta «¿Abrirlo?» | Toast «PDF generado · [Abrir] [Carpeta]». |
| Regenerar campos (uno) | Advertencia + diálogo de relación | Sin advertencia: el diálogo de relación ya muestra los datos y tiene Cancelar. Éxito → toast. |
| Regenerar campos (varios) | Advertencia + resumen | Se mantiene la advertencia (no hay otro paso de confirmación por fila); resumen sin fallos → toast. |
| Regenerar todas las partidas (IA) | Advertencia | **Se mantiene** (borra partidas). Éxito → toast. |
| Añadir partidas (IA / biblioteca) | Ventana «Éxito» | Toast. |
| Vista previa de más de 5 | Ventana | Toast. |
| «El archivo ya no existe», errores | Ventana | Se mantienen. |

### Planificación al deshacer

Antes de mover se lee el registro de planificación de cada obra
(`obra_planificacion`); deshacer lo restaura tal cual (incluido no tener
fila). Requiere una función nueva en
`src/core/repositories/obra_planificacion_repository.py`
(`restore_plan_snapshot(numero, snapshot)`), módulo de la otra sesión: se le
avisa antes de tocarlo.

## Pruebas

- `tests/test_budget_filters.py`: fechas en todos los formatos y vacías,
  totales vacíos, límites inclusivos, combinación con texto, `summarize`,
  `distinct_values`, normalización de cliente.
- Tests de interfaz (patrón de `test_budget_dashboard_row_refresh.py`): barra
  de filtros por pestaña, filtros conservados tras `_refresh_rows`, etiquetas
  y limpiar, botón Columnas, mover sin pregunta + deshacer (carpetas y
  planificación), vigilante sin pregunta, PDF y releer con toast.
- Ajustar los tests que hoy simulan `QMessageBox.question`/`information` en
  estos flujos.
- Suite completa en verde con el Python del venv.

## Fuera de alcance

- Pestaña de estadísticas.
- «Crear presupuesto» y «Gestionar base de datos» (tanda 2; reutilizarán el
  toast).
- Cualquier cambio en el módulo de generar partidas.
- Persistir filtros entre sesiones.

## Rama

`dashboard-filtros-ux`, creada desde `planificacion-obras` (ff6188c), porque
la planificación añadió columnas y acciones en el mismo dashboard.
