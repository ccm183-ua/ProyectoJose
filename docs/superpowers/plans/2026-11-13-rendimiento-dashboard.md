# Rendimiento del dashboard «Presupuestos existentes» — Plan de implementación

> **Para agentes:** ejecutar tarea a tarea con TDD. Los pasos usan casillas (`- [ ]`).

**Objetivo:** que recargar, escanear y abrir presupuestos deje de cortar el ritmo de trabajo: recarga
completa de ~9–11 s → < 1 s con caché caliente, y acciones sobre filas sin recarga completa.

**Arquitectura:** (1) SQLite deja de reejecutar el esquema en cada conexión; (2) la caché de
`presupuesto` se lee en bloque y recuerda, por mtime, si la hoja coincide, de modo que un Excel sin
cambios no se vuelve a abrir; (3) el dashboard refresca solo las filas afectadas por una acción;
(4) «Abrir Excel» lee una vez y en segundo plano; (5) «Escanear» explica por qué falla cada uno.

**Tech stack:** Python 3, PySide6, SQLite (`sqlite3`), pytest (+ fixture `qapp` de `tests/conftest.py`).

## Medición de partida (13-11-2026, 234 proyectos, disco local)

| Medida | Valor |
|---|---|
| Recarga completa con caché caliente (`sync_presupuestos` de todos los estados) | 9,1–11,6 s |
| Lecturas completas de Excel por recarga (`has_matching_project_sheet` + `read`) | 305 + 7 |
| Conexiones SQLite por recarga | 380 (≈5,7 ms c/u → 2,2 s) |
| Excels cuyo E5 no coincide con el Nº de la carpeta | 43 de 230 |

## Restricciones globales

- No tocar vocabulario de clasificación ni lógica de precios de la IA.
- Mantener intactas las reglas de seguridad de datos: guard `WHERE es_finalizado = 0`, política
  «ninguna hoja coincide» (no guardar contenido), snapshot desactualizado de finalizados.
- Toda lectura de Excel fuera del hilo de interfaz (`run_in_background`).
- Comandos de test: `../ProyectoJose/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider <ruta>`
  desde el worktree `ProyectoJose-rendimiento` (rama `rendimiento-dashboard`, base `prueba-claude`).
- Commits en castellano con prefijo convencional (`perf(...)`, `fix(...)`, `test(...)`).

---

### Tarea 1: el esquema se aplica una vez por proceso y ruta

**Problema:** `database.connect()` llama a `init_schema()` en cada conexión (5 `executescript` +
commit). Afecta a toda la app.

**Ficheros:**
- Modificar: `src/core/database.py` (`connect`, nuevo `invalidate_schema_cache`)
- Modificar: `src/core/database_persistence.py` (`copy_database_as_active`)
- Test: `tests/test_database_schema_once.py`

**Interfaces:**
- Produce: `database.invalidate_schema_cache() -> None`; `database._SCHEMA_READY: set[str]`.

**Diseño:** tras un `init_schema` correcto se guarda la ruta resuelta en `_SCHEMA_READY`. En
conexiones siguientes a esa ruta solo se comprueba `get_schema_version(conn) == CURRENT_SCHEMA_VERSION`
(una consulta); si falla (tabla ausente, BD vaciada o sustituida) o la versión es menor, se vuelve a
ejecutar `init_schema`. `copy_database_as_active` invalida la caché antes de reconectar.

- [ ] Test: dos `get_connection()` sobre la misma ruta → `init_schema` llamado 1 vez (monkeypatch contador).
- [ ] Test: tras borrar el fichero `.db`, la siguiente conexión recrea tablas (`presupuesto` existe).
- [ ] Test: `invalidate_schema_cache()` fuerza `init_schema` en la siguiente conexión.
- [ ] Test: dos rutas distintas (`CUBIAPP_DB_PATH`) → cada una se inicializa.
- [ ] Implementar; pasar tests; suite completa verde; commit `perf(db): aplicar el esquema una vez por proceso`.

### Tarea 2: la caché de presupuestos se lee en bloque

**Problema:** `sync_presupuestos` hace `get_presupuesto_por_ruta` (una conexión + consulta) por proyecto.

**Ficheros:**
- Modificar: `src/core/repositories/presupuesto_cache_repository.py` (nuevo `get_presupuestos_por_rutas`)
- Modificar: `src/core/repositories/__init__.py`, `src/core/db_repository.py` (reexportar)
- Modificar: `src/core/budget_cache.py` (`sync_presupuestos` usa el mapa)
- Test: `tests/test_budget_cache_bulk.py`

**Interfaces:**
- Produce: `get_presupuestos_por_rutas(rutas: list[str]) -> dict[str, dict]` (clave `ruta_excel`;
  consulta por lotes de 500 parámetros; rutas vacías ignoradas).

- [ ] Test del repositorio: devuelve solo las rutas pedidas, mapa vacío con lista vacía, >500 rutas.
- [ ] Test: `sync_presupuestos` con N proyectos cacheados abre ≤ 2 conexiones (contador sobre `database.connect`).
- [ ] Implementar; tests existentes de `budget_cache` siguen verdes; commit `perf(cache): leer la caché de presupuestos en una consulta`.

### Tarea 3: un Excel sin cambios no se vuelve a abrir

**Problema:** con mtime igual, `sync_presupuestos` llama siempre a `has_matching_project_sheet`
(lee y descomprime el Excel entero) y reprocesa en cada recarga los presupuestos con «ninguna hoja
coincide» o total 0 (~75 por recarga, para siempre).

**Ficheros:**
- Modificar: `src/core/database.py` (migración v5: columnas `clave_verificacion TEXT`, `hoja_coincide INTEGER` en `presupuesto`; `CURRENT_SCHEMA_VERSION = 5`)
- Modificar: `src/core/repositories/presupuesto_cache_repository.py` (columnas en `_PRESUPUESTO_COLS` y `_row_to_presupuesto_cache`; `upsert_presupuesto` y `upsert_presupuesto_finalizado` ponen `clave_verificacion = NULL`; nuevo `marcar_verificacion_presupuesto(ruta, clave, coincide)`)
- Modificar: `src/core/budget_cache.py` (`READER_REVISION`, `_verification_key(mtime)`, uso en `sync_presupuestos`)
- Test: `tests/test_budget_cache_verification.py`

**Interfaces:**
- Produce: `budget_cache.READER_REVISION: str` (subirla cuando el lector mejore para forzar una revalidación);
  `budget_cache._verification_key(mtime_iso: str) -> str` = `f"{READER_REVISION}|{mtime_iso}"`;
  `marcar_verificacion_presupuesto(ruta_excel: str, clave: str, coincide: Optional[bool]) -> None`.

**Diseño:** en la rama «mtime coincide» de `sync_presupuestos`, si `cached["clave_verificacion"] ==
_verification_key(mtime)` se usa la caché tal cual (sin abrir el Excel, sin política). Si no, se
ejecuta la lógica actual (comprobación de hoja + posible refresco por política) y al final se llama a
`marcar_verificacion_presupuesto`. Tras leer y guardar un Excel nuevo/modificado también se marca. Como
cualquier upsert borra la clave, todo lo escrito por otra vía (escaneo manual, finalizar) se revalida
una vez. La clave incluye el mtime, así que un Excel editado se revalida solo.

- [ ] Test de migración: BD v4 → v5 añade columnas sin perder filas (patrón de `tests/test_database_migrations.py`).
- [ ] Test: segunda `sync_presupuestos` sobre Excels sin cambios → 0 llamadas a `BudgetReader._load_file_bytes`.
- [ ] Test: Excel con «ninguna hoja coincide» → segunda sync no lo reprocesa y sigue mostrando el aviso.
- [ ] Test: tocar el mtime del Excel → se vuelve a leer.
- [ ] Test: `upsert_presupuesto` posterior borra la clave → la siguiente sync revalida una vez.
- [ ] Tests H08 (`test_budget_cache_staleness.py`) siguen verdes.
- [ ] Commit `perf(cache): recordar la verificación de hoja por mtime`.

### Tarea 4: el dashboard refresca solo las filas afectadas

**Problema:** 9 llamadas a `_load_data()` tras acciones sobre filas concretas reconstruyen todas las
pestañas y bloquean la barra (incluido «Abrir») durante la recarga.

**Ficheros:**
- Modificar: `src/gui/budget_dashboard.py` (nuevo `_refresh_rows`; sustituir `_load_data()` en
  `_on_refresh_selected._done`, `_on_open_excel`, `_arm_excel_watch._applied`, `_edit_regen_all`,
  `_edit_add_partidas`, `_edit_regen_header_selected`, `_edit_regen_header`. `_move_project` y el
  botón «⟳ Actualizar» siguen con recarga completa).
- Test: `tests/test_budget_dashboard_row_refresh.py`

**Interfaces:**
- Produce: `BudgetDashboardFrame._refresh_rows(rutas: Iterable[str], on_done: Callable[[], None] | None = None) -> None`.
  En segundo plano reconstruye los dicts de escaneo de las filas cuya `ruta_excel` (normalizada) está en
  `rutas` (`nombre_carpeta←nombre_proyecto`, `numero_proyecto←numero`, `ruta_excel`, `ruta_carpeta`),
  llama a `resolve_projects(subset, self._relation_index, state)`, sustituye las entradas en
  `self._tab_data[state]` y repuebla solo esas pestañas conservando búsqueda y orden. Si ninguna fila
  coincide, no hace nada. No deshabilita la barra.

- [ ] Test: `_refresh_rows` sustituye solo la fila pedida y deja las demás (resolve_projects monkeypatched, `run_in_background` síncrono).
- [ ] Test: `_on_refresh_selected` ya no llama a `_load_data` y sí a `_refresh_rows` con las rutas escaneadas.
- [ ] Test: la búsqueda activa se conserva tras `_refresh_rows`.
- [ ] Sustituir el resto de llamadas; suite GUI verde; commit `perf(dashboard): refrescar solo las filas afectadas`.

### Tarea 5: «Abrir Excel» lee una vez y en segundo plano

**Problema:** `_on_open_excel` lee cada Excel dos veces en el hilo de interfaz antes de abrirlo y
luego recarga todo.

**Ficheros:**
- Modificar: `src/gui/budget_dashboard.py` (`_on_open_excel`)
- Test: `tests/test_budget_dashboard_open_excel.py`

**Diseño:** en segundo plano, por cada ruta, `svc.refresh_budget_cache_entry(...)`; su resultado
(`False` = no legible) sustituye a la segunda lectura con `read_budget`. En el callback: pregunta por
los ilegibles (mismo texto que hoy), abre, arma vigilantes y llama a `_refresh_rows(rutas_refrescadas)`.

- [ ] Test: abrir un Excel → `BudgetReader.read` se llama 1 vez por fichero; `_open_file` se llama; `_load_data` no.
- [ ] Test: fichero ilegible → se pregunta; con «No» no se abre.
- [ ] Commit `perf(dashboard): abrir el Excel sin doble lectura ni recarga completa`.

### Tarea 6: «Escanear presupuestos» explica cada fallo

**Problema:** el resumen solo dice «Con error: N»; el 19 % de los Excels falla porque su E5 trae el
número de otro presupuesto (copias sin actualizar) y el usuario no sabe cuáles.

**Ficheros:**
- Modificar: `src/core/services/budget_service.py` (nuevo `diagnose_read_failure`)
- Modificar: `src/gui/budget_dashboard.py` (`_on_refresh_selected` recoge motivos y los muestra)
- Test: `tests/test_budget_service_diagnose.py`

**Interfaces:**
- Produce: `BudgetService.diagnose_read_failure(file_path: str, expected_numero: str = "") -> str`.
  Mensajes: «No existe el fichero», «Ninguna hoja coincide con {numero}: E5 dice {lista}», «No se pudo
  leer el Excel (formato no reconocido o fichero dañado)».

- [ ] Tests de los tres mensajes con Excels mínimos generados (helpers de `tests/test_budget_reader.py`).
- [ ] El resumen lista hasta 15 fallos «· nombre: motivo» y «… y N más».
- [ ] Commit `fix(dashboard): explicar por qué falla el escaneo de cada presupuesto`.

### Tarea 7: medición final

**Ficheros:**
- Crear: `scripts/bench_dashboard_reload.py` (mide recarga completa, lecturas de Excel y conexiones con los datos configurados; solo lectura salvo la propia caché).

- [ ] Ejecutar y anotar resultados en este plan (tabla «Medición final»).
- [ ] Suite completa verde; commit `chore(bench): script de medición de la recarga del dashboard`.

## Medición final (13-11-2026, copia de la BD real, 234 proyectos)

`scripts/bench_dashboard_reload.py --veces 3`:

| Recarga | Tiempo | Lecturas de Excel | Conexiones SQLite |
|---|---|---|---|
| Antes (cualquiera, caché caliente) | 9,1–11,6 s | 312 | 380 |
| 1.ª tras actualizar (valida y marca cada Excel una vez; migración v5) | 4,9–6,2 s | 237 | 387 |
| 2.ª y siguientes | 0,11–0,16 s | 0 | 6 |

Además, escanear, abrir, guardar un Excel vigilado y editar ya no disparan la recarga completa:
solo se vuelve a resolver la fila tocada.
