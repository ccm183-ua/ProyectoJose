# CONTEXT.md — Fuentes de verdad de cubiApp

> Generado para H2.1 del roadmap (`docs/ROADMAP_ESTABILIZACION_Y_EVOLUCION_IA.md`).
> Describe el estado real del código en la rama `prueba-claude`, no un diseño aspiracional.
> Las decisiones derivadas de este inventario están en `docs/adr/0001-fuentes-de-verdad.md`
> y `docs/adr/0002-excel-como-adaptador.md`.

## Por qué existe este documento

cubiApp tiene hoy tres almacenes de datos con solapamiento parcial: los ficheros Excel de
cada proyecto, la tabla `presupuesto`/`presupuesto_partida` (caché del dashboard) y la
tabla `historical_budget`/`historical_partida` (memoria de aprendizaje). Antes de tocar
contratos o migrar a un backend web, hace falta saber, para cada entidad: quién es su
dueño, quién puede escribirla, qué se puede reconstruir si se pierde, y qué pasa hoy si
Excel y SQLite no están de acuerdo.

## Entidades

### 1. `historial_presupuesto`

- **Identidad**: `ruta_excel` (UNIQUE).
- **Propietario**: `src/core/repositories/historial_repository.py`.
- **Quién escribe**: `BudgetService` (`create_budget`, `insert_partidas`, `open_budget`,
  `finalize_budget`) vía `registrar_presupuesto`/`actualizar_total`.
- **Estados**: ninguno explícito; es un registro de "último acceso".
- **Derivable**: sí, por completo. Todo su contenido existe en el Excel o es reconstruible
  escaneando carpetas (`folder_scanner` + `BudgetReader`).
- **Reconciliación**: ninguna necesaria — es *write-only*. `actualizar_acceso` y
  `eliminar_historial` no tienen ningún llamador en `src/gui/`; `get_historial_reciente` y
  `buscar_historial` tampoco alimentan ninguna pantalla actual. Es la candidata más clara
  a simplificar o retirar cuando se toque este área (fuera de alcance de H2.1).

### 2. `presupuesto` y `presupuesto_partida` (caché del dashboard de carpetas)

- **Identidad**: `ruta_excel` (UNIQUE) para `presupuesto`; `(presupuesto_id, orden)` para
  las partidas.
- **Propietario**: `src/core/repositories/presupuesto_cache_repository.py`, orquestado por
  `src/core/budget_cache.py` (`sync_presupuestos`).
- **Estados**: `es_finalizado` (0/1) es el campo que más importa. Con `es_finalizado=0`
  la fila es una caché de escaneo libre de sobrescribir; con `es_finalizado=1` pasa a ser
  un snapshot protegido — `upsert_presupuesto` tiene la cláusula
  `WHERE presupuesto.es_finalizado = 0` (`presupuesto_cache_repository.py:206`) que le
  impide tocar filas ya finalizadas. Solo `upsert_presupuesto_finalizado` (sin ese guard)
  puede modificarlas.
- **Quién escribe**:
  - Escaneo normal del dashboard → `upsert_presupuesto` (no toca finalizados).
  - `BudgetService.finalize_budget()` → `upsert_presupuesto_finalizado` (cabecera +
    reemplazo completo de `presupuesto_partida`).
  - `BudgetService.refresh_budget_cache_entry()` → decide entre ambas según el estado
    actual.
- **Derivable**: la cabecera (cliente, localidad, tipo de obra, fecha) se toma
  preferentemente del Excel de relación de presupuestos, no de la cabecera del Excel del
  proyecto — si el Excel de relación se pierde, esos campos concretos no son igual de
  reconstruibles solo con el Excel del proyecto. `presupuesto_partida` (finalizado) es un
  snapshot en teoría reconstruible releyendo el Excel, salvo que éste se edite después
  sin que la app lo detecte (ver sección de reconciliación).
- **Lectura real vs. muerta**: varias funciones de lectura (`get_presupuesto_detalle_por_ruta`,
  `get_partidas_de_presupuesto`, `get_presupuestos_para_tabla`, `get_all_presupuestos_cache`)
  están exportadas pero sin llamador actual en `src/gui/` — el dashboard construye su tabla
  escaneando disco + `project_data_resolver`, no consultando estas funciones directamente.

### 3. `historical_budget` y `historical_partida` (memoria de aprendizaje)

- **Identidad**: `ruta_excel` (UNIQUE) para `historical_budget`; autoincremental para
  `historical_partida`, ligado por `historical_budget_id`.
- **Propietario**: `src/core/repositories/historical_repository.py`, orquestado por
  `src/core/historical_budget_analyzer.py` (`HistoricalBudgetAnalyzer.analyze_budget`).
- **Estados**: `analysis_status` (calidad técnica del análisis) y `learning_status`
  (`INCLUDED`/`PENDING_REVIEW`/`EXCLUDED`/`NOT_ELIGIBLE`, decisión de negocio sobre si se
  usa para generar sugerencias).
- **Quién escribe**: solo acciones manuales explícitas del usuario — "Analizar carpeta"
  o "Reanalizar" (vía `historical_analysis_dialog.py`, `historical_analysis_results_dialog.py`,
  `historical_memory_dashboard.py`) y las decisiones de inclusión/exclusión en aprendizaje.
  No hay ningún disparador automático en background.
- **Derivable**: **no** de forma trivial. Contiene el resultado de un pipeline (clasificación
  por módulo de ejecución, normalización de conceptos, scoring de calidad, decisiones
  manuales de aprendizaje) que solo se reconstruye volviendo a ejecutar el análisis sobre
  los Excel originales. Si esos Excel ya no existen en disco (proyectos archivados o
  borrados), esta tabla es la **única fuente restante** — es la entidad más irrecuperable
  de las tres.
- **Protección explícita en el código**: `src/core/database.py` prioriza como ruta activa
  un `.db` legacy si es el único que "contiene históricos" (`_db_has_historical_data`);
  `src/core/database_persistence.py` hace backup automático antes de sobrescribir la BD
  activa; el docstring de `database.py` dice explícitamente "No se borra nunca desde la
  aplicación."
- **Reconciliación**: mismo patrón de mtime que el resto (`existing.fecha_modificacion_excel
  == mtime` → `skipped`), pero sin ningún trigger automático — solo se reevalúa si el
  usuario pulsa "Reanalizar".

### 4. Excel (vía `ExcelManager`)

`ExcelManager` es una fachada que delega en tres módulos:

| Escritura | Delega en | Qué toca | Llamador |
|---|---|---|---|
| `create_from_template` | `TemplateFiller` | Cabecera inicial desde la plantilla | `BudgetService.create_budget` |
| `insert_partidas_via_xml` | `PartidasWriter` | Reemplaza filas de ejemplo por partidas reales | `BudgetService.insert_partidas` |
| `update_header_fields` | `PartidasWriter` | Celdas de cabecera (número, fecha, cliente, dirección, total en letras) | `BudgetService.update_header_fields` |
| `append_partidas_via_xml` | `PartidasWriter` | Añade partidas al final | `BudgetService.append_partidas` (sin llamador GUI hoy) |
| `add/modify/delete_budget_row`, `recalculate_totals` | `BudgetEditor` | Edición de filas | **Código muerto**: sin llamador fuera de sí mismo |
| `load_budget` | `BudgetEditor` | Solo lectura | `BudgetService.open_budget` |

El Excel es el **artefacto operativo real**: es lo que el usuario abre, edita a mano y
entrega al cliente. Todas las tablas SQLite anteriores son proyecciones de este artefacto,
con la salvedad de `historical_budget`/`historical_partida` una vez que el Excel de origen
deja de existir.

## Reconciliación Excel ↔ SQLite hoy

No existe ningún hash de contenido en ningún punto de la sincronización — toda detección
de cambio se basa en `mtime` del fichero (`os.stat().st_mtime`) comparado contra
`fecha_modificacion_excel`. Mecanismos concretos, de más a menos automático:

1. **Escaneo del dashboard** (`budget_cache.sync_presupuestos`): mtime igual → usa caché;
   mtime distinto → relee y actualiza. Si `es_finalizado=1`, el escaneo automático **ignora
   el contenido del Excel por completo**, solo actualiza el campo `estado` (carpeta).
2. **Vigilancia tras abrir el Excel desde la app** (`budget_dashboard._watch_excel_changes_and_refresh`):
   hilo en background que compara mtime cada 2s durante ~6 minutos tras abrir un Excel
   desde dentro de cubiApp; si detecta cambio, llama a `finalize_budget()` y sobrescribe
   la caché. Es la única vía "automática" para detectar una edición manual — y solo
   funciona si el Excel se abrió desde la app y no pasaron más de ~6 minutos.
3. **Refresco manual** ("Escanear presupuestos"): relee incondicionalmente, ignorando mtime.
4. **Memoria histórica**: mismo patrón de mtime, sin ningún disparador automático.

**Gap real**: si el usuario edita un Excel ya finalizado fuera de la app (o la app no está
corriendo durante la edición), la discrepancia no se detecta salvo que el usuario pulse
"Escanear presupuestos" o vuelva a abrir ese Excel desde dentro de la app. No hay checksum
de contenido ni aviso en la UI de "Excel modificado externamente, ¿recargar?".

## Ver también

- `docs/adr/0001-fuentes-de-verdad.md` — declaración de fuente de verdad objetivo por entidad.
- `docs/adr/0002-excel-como-adaptador.md` — decisión sobre el rol de Excel durante la migración.
- `docs/ROADMAP_ESTABILIZACION_Y_EVOLUCION_IA.md` — plan completo de estabilización y evolución.
