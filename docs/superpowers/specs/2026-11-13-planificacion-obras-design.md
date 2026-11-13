# Planificación de obras (pieza A) — diseño

> Pieza A de la batería "obras" acordada el 2026-11-13 (opción 1): D imprimir
> directo (hecha) → **A planificación** → B avisos y correo → C calendario y
> métricas. B y C usarán los datos de A.

## Problema

Las obras de la carpeta EJECUTAR no tienen fecha de comienzo en la app. Hoy
se escribe a mano en el nombre de la carpeta ("… EJECUTAR EL 13-07-26",
"… SE EJECUTARÁ EN JULIO'26"), sin avisos ni forma de ver en qué fecha
empezó o terminó cada obra.

## Objetivo y criterio de éxito

- Poner y ver la fecha prevista de inicio (y fin) de cada obra de EJECUTAR en
  su tabla, sin tocar el Excel.
- Registrar sin esfuerzo las fechas reales de inicio (al pasar a EJECUTANDO)
  y de fin (al pasar a TERMINADO).
- Ninguna fecha se inventa: lo deducido se marca como aproximado y lo
  propuesto no se guarda sin confirmación.

## Datos medidos (2026-11-13)

- Estados: PTE. PRESUPUESTAR 69, PRESUPUESTADO 67, EJECUTAR 25,
  EJECUTANDO 23, TERMINADO 51, ANULADOS 5.
- El número de proyecto ("114-26") es estable al mover la carpeta, pero no
  único: PRESUPUESTADO 67 filas / 65 números, TERMINADO 51 / 49.

## Parte 1 — Datos e identidad

Tabla nueva `obra_planificacion` (migración de esquema v4 → v5, con backup
previo como las anteriores). No se guarda nada en el Excel.

| Campo | Tipo | Notas |
|---|---|---|
| `numero_proyecto` | TEXT PK | "114-26" |
| `inicio_previsto` | TEXT (ISO) | editable |
| `fin_previsto` | TEXT (ISO) | editable, opcional |
| `inicio_real` | TEXT (ISO) | automático al mover a EJECUTANDO; editable |
| `inicio_real_aproximado` | INTEGER 0/1 | deducido en un escaneo |
| `fin_real` | TEXT (ISO) | automático al mover a TERMINADO; editable |
| `fin_real_aproximado` | INTEGER 0/1 | deducido en un escaneo |
| `margen_aviso_dias` | INTEGER | NULL = usar el general |
| `avisado_en` | TEXT (ISO) | lo usará la pieza B |
| `notas` | TEXT | opcional |
| `estado_conocido` | TEXT | último estado visto (para detectar movimientos externos) |
| `actualizado_en` | TEXT | marca de tiempo |

**Identidad**: `numero_proyecto`. Si en el escaneo dos carpetas comparten
número, ninguna de ellas lee ni escribe planificación: la tabla muestra
"nº repetido" en sus celdas de fecha. Una carpeta sin número no se planifica.

**Fecha propuesta desde el nombre de la carpeta** (no se guarda sola):

- `dd-mm-aa`, `dd/mm/aa`, `dd.mm.aaaa` → esa fecha.
- "EN <MES>'aa", "<MES> aa", "<MES> 20aa" → día 1 de ese mes, aproximada.
- Solo se propone si la obra está en EJECUTAR y no tiene `inicio_previsto`.

## Parte 2 — Tabla

| Pestaña | Columnas añadidas (detrás de "Proyecto") |
|---|---|
| EJECUTAR | Inicio previsto · Fin previsto · Aviso |
| EJECUTANDO | Inicio real · Fin previsto · Retraso |
| TERMINADO | Inicio real · Fin real · Duración |

- Se añaden al final (índices lógicos) y se mueven visualmente detrás de
  "Proyecto": no cambia nada del código que oculta columnas por índice.
- Ordenables por fecha (clave ISO).
- **Aviso**: "en N días" si el inicio cae dentro del margen; "hoy"; vacío si
  queda lejos; "avisada el dd/mm" si hay `avisado_en`.
- **Retraso**: "N días" si hoy > fin previsto; vacío si no.
- **Duración**: días entre inicio y fin reales.
- Aproximadas con "≈"; propuestas en gris y cursiva.
- Colores en EJECUTAR (con texto, no solo color): ámbar = dentro del margen;
  rojo = inicio previsto ya pasado y la obra sigue en EJECUTAR.
- **Edición**: doble clic en una celda de fecha → diálogo de planificación;
  doble clic en el resto de la fila → abre el Excel como hoy. Clic derecho →
  "Planificación…" (una o varias obras; con varias se aplica la misma fecha
  prevista a todas).

## Parte 3 — Fechas reales automáticas

1. **Mover con la app** (`_move_project`): por cada carpeta movida con éxito
   y con número único:
   - a EJECUTANDO: si no tiene `inicio_real`, se pone hoy (exacta);
   - a TERMINADO: si no tiene `fin_real`, se pone hoy (exacta);
   - se actualiza `estado_conocido`.
   Volver atrás (p. ej. EJECUTANDO → EJECUTAR) no borra fechas.
2. **Movimientos fuera de la app** (Explorador, Drive): en cada escaneo, para
   cada obra con número único:
   - si no tiene fila o `estado_conocido` vacío: se anota el estado, sin
     fechas (primer escaneo: no se inventa nada);
   - si `estado_conocido` difiere del estado actual: se aplica la regla de 1
     con la fecha del escaneo y marcada como aproximada; se actualiza
     `estado_conocido`.

## Parte 4 — Margen, diálogo, errores y pruebas

- **Margen general**: `Settings.get_obra_margen_aviso_dias()` (por defecto 7,
  rango 0-365), editable en Configuración → "Avisos de obras…".
- **Diálogo de planificación** (`ObraPlanningDialog`): inicio previsto, fin
  previsto, inicio real (+ aproximada), fin real (+ aproximada), margen propio
  (vacío = general), notas; botones Guardar / Quitar fechas / Cancelar; muestra
  el nombre de la carpeta como referencia. Valida fin ≥ inicio.
- **Errores**: si falla la lectura de planificación, la tabla se muestra sin
  esas columnas rellenas y con aviso en el log; si falla una escritura, aviso
  y no se cambia la tabla. Nada de esto impide usar el dashboard.
- **Pruebas**: núcleo (parseo de fechas del nombre, textos de aviso, retraso,
  duración, colores); repositorio (CRUD, transiciones, reconciliación del
  escaneo, números repetidos); migración v5; interfaz offscreen (columnas por
  pestaña, diálogo, mover registra fechas, varias obras a la vez).

## Fuera de alcance (piezas B y C)

Panel de avisos al abrir la app, correo en Gmail, marcar como avisada,
calendario y métricas.
