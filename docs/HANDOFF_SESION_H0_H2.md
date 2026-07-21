# Traspaso de sesión — H0 a H2.5 completados

- **Rama:** `prueba-claude`
- **Estado de git:** NADA de esto está commiteado. Todo lo listado abajo son cambios en el árbol de trabajo (`git status` muestra ~26 ficheros modificados y ~14 nuevos). El usuario pidió explícitamente no commitear salvo que lo pida.
- **Roadmap seguido:** `docs/ROADMAP_ESTABILIZACION_Y_EVOLUCION_IA.md` (documento ya existente al empezar la sesión, no reescrito).
- **Suite de tests al cierre de esta sesión:** `python -m pytest -q` → **616 passed, 0 failed, 0 skipped**, ~85-100s.

## Qué se ha hecho, hito por hito

### H0 — Repositorio reproducible (COMPLETO)
- **H0.1** (plantilla Excel): ya estaba resuelto antes de esta sesión (plantilla versionada, 16/16 tests).
- **H0.2**: `insert_historical_partida` (`src/core/repositories/historical_repository.py`) calcula `MAX(orden)+1` cuando no se pasa `orden` explícito. Test nuevo: `tests/test_historical_repository.py`.
- **H0.3**: catálogo único de módulos derivado de `MODULE_RULES` (`src/core/historical_partida_classifier.py`, nuevo dict `MODULE_DESCRIPTIONS`), columna `execution_module.descripcion` + migración + seed idempotente en `src/core/database.py`. Tests nuevos en `tests/test_database.py` (`TestExecutionModuleCatalog`).
- **H0.4**: contrato del payload `thinking` de DeepSeek en `src/core/ai_clients.py` — tabla `DEEPSEEK_THINKING_CAPABLE_MODELS` en vez de comparar contra el modelo por defecto.
  - **⚠️ Hallazgo importante para el siguiente agente**: al revisar la documentación vigente de DeepSeek (vía WebFetch, fecha de la sesión 2026-07-21) se confirmó que los alias `deepseek-chat`/`deepseek-reasoner` **se retiran el 2026-07-24**. Se cambió `DEFAULT_DEEPSEEK_MODEL` en `src/core/settings.py` a `"deepseek-v4-flash"`. Si el usuario tiene configurado manualmente `deepseek-chat` en Ajustes de IA, debe cambiarlo. **Vuelve a comprobar la fecha actual contra esa fecha de retirada** si retomas el trabajo más adelante — puede que ya haya pasado.

### H1 — Flujo IA local fiable (COMPLETO salvo un punto)
- **H1.1**: `BudgetOrchestrator` unificado a `source` (valores `historical`/`ai_completion`, mismo vocabulario que `partida_normalizer`), eliminado el antiguo `fuente`/`historico`/`ia_estimado`. Tests: `tests/test_budget_orchestrator.py`.
- **H1.2**: modo "añadir" ahora excluye duplicados exactos frente a partidas existentes (`exclude_existing_from_candidates` en `src/core/historical_suggestions_dedupe.py`) y marca como dudosos los que coinciden en concepto+unidad con precio distinto (campo `reason`, que ahora sobrevive la normalización en `partida_normalizer.py`).
- **H1.3**: `VoiceBudgetDialog` ya no muere silenciosamente si el worker lanza una excepción (try/except en `_run_generation`), y la cobertura se movió al diálogo de revisión (`CombinedPartidasReviewDialog`, que sí permanece visible) con 4 estados de texto.
  - **⚠️ Bug de entorno de tests encontrado y corregido**: PySide6 no estaba instalado en el Python que ejecuta pytest en este entorno (pese a estar en `requirements.txt`) — se instaló para poder verificar de verdad. Al instalarlo aparecieron problemas reales preexistentes que estaban ocultos por los skips: cada fichero de test de GUI definía su propio fixture `qapp`, lo que colgaba el proceso al pasar de un módulo a otro. Se centralizó en un único fixture de sesión en `tests/conftest.py` (fuerza `QT_QPA_PLATFORM=offscreen`).
- **H1.4**: `BudgetOrchestrator.generate()` ahora envuelve su lógica en try/except propio (no solo la GUI) — cualquier excepción no tratada de histórico o IA se convierte en un resultado de error uniforme. Tests nuevos: `tests/test_ai_module_classifier.py`, ampliación de `tests/test_budget_orchestrator.py` (9 escenarios obligatorios del roadmap).
- **Punto pendiente de H1**: el checklist manual con Excel real (crear/añadir/regenerar/cancelar/finalizar) **no se ejecutó**. Se intentó automatizar con clics de ratón + `SendKeys` sobre el escritorio real del usuario y **salió mal**: el teclado automatizado se coló en el prompt de la propia terminal de Claude Code en vez de en el diálogo de la app (el clic de ratón sí llegaba bien, posicional; `SendKeys`/`SetForegroundWindow` sobre diálogos nativos de Windows no). El usuario decidió aceptar la cobertura automatizada (616 tests) como sustituto y seguir. **No hay evidencia manual real todavía** — existe `docs/CHECKLIST_MANUAL_EXCEL.md` con los pasos documentados, pendiente de que un humano lo ejecute.

### H2 — Contratos estables (COMPLETO)
- **H2.1**: `CONTEXT.md` (raíz) + `docs/adr/0001-fuentes-de-verdad.md` + `docs/adr/0002-excel-como-adaptador.md`. Documenta que hoy Excel es la fuente de verdad de un presupuesto activo, `presupuesto_partida` finalizado es snapshot congelado, y `historical_budget`/`historical_partida` es irrecuperable si se pierde el Excel de origen (protegido con backup automático).
- **H2.2**: nuevo `src/core/services/budget_partidas_flow.py` (sin PySide6) — `split_generated_partidas_for_review()` y `apply_reviewed_partidas()` con modo explícito `create`/`append`/`replace`, usado por `main_frame.py` y `budget_dashboard.py` en vez de lógica duplicada. Tests: `tests/test_budget_partidas_flow.py`.
- **H2.3**: `GeminiAIClient` (`src/core/ai_clients.py`) ahora soporta fallback entre modelos con reintento en 429. `AIService` (`src/core/ai_service.py`) ya no importa `google.genai` directamente — delega en `GeminiAIClient`. `ai_module_classifier.py` migrado a usar `GeminiAIClient`/`DeepSeekAIClient` uniformemente. Nueva categoría de error "proveedor no disponible" en `normalize_ai_error`. Logging mínimo de proveedor/modelo/latencia/tokens sin exponer secretos. Test de contrato que verifica que ningún caso de uso importa un SDK de proveedor directamente.
- **H2.4**: versión explícita de esquema (`CURRENT_SCHEMA_VERSION = 1`, tabla `schema_version`) en `src/core/database.py`; backup automático antes de migrar.
  - **⚠️ Bug real encontrado y corregido durante la verificación**: `create_database_backup()` registra un evento vía `log_historical_memory_event()`, que abre OTRA conexión y vuelve a llamar a `init_schema()` — sin guarda, esto recursionaba sin control. En una prueba aislada generó **más de 4000 ficheros de backup en la carpeta real del usuario** (`Documents/CubiApp/backups`) en pocos minutos, antes de que se detectara y corrigiera (guarda de reentrada `_MIGRATION_IN_PROGRESS`). Se limpiaron todos los ficheros espurios sin tocar los 175 backups reales preexistentes. Además, `get_backup_dir()` ahora respeta `CUBIAPP_BACKUP_DIR` y `tests/conftest.py` lo fija a una carpeta temporal de sesión para que ningún test futuro pueda volver a escribir ahí.
  - Snapshot legacy: `tests/fixtures/legacy_schema_v0.db` (datos ficticios) + `tests/fixtures/_generate_legacy_snapshot.py`. Tests: `tests/test_database_migrations.py` (migración, doble ejecución idempotente, backup+restauración, BDD nueva vs migrada misma versión).
  - **Corrección adicional hecha justo antes de este traspaso**: `.gitignore` tenía una regla `*.db` que también ignoraba el fixture nuevo — se añadió la excepción `!tests/fixtures/legacy_schema_v0.db`. Sin esto, un futuro commit habría dejado el fixture sin trackear y los 4 tests de migración habrían fallado en un clon limpio.
- **H2.5**: `README.md` reescrito (PySide6 no wxPython, Python 3.11 fijado, tabla completa de 5 variables de entorno), `.env.example` completado, `run.bat`/`run.sh` con comentario corregido, `.github/workflows/tests.yml` nuevo (CI en `windows-latest`, confirmado que ningún test depende de Excel/COM real — todo mockeado), `docs/CHECKLIST_MANUAL_EXCEL.md` nuevo.

## Qué falta

### Gate de Etapa 1 (inmediato)
- [ ] Checklist manual de Excel real ejecutado por un humano (ver arriba, y `docs/CHECKLIST_MANUAL_EXCEL.md`).
- [ ] Confirmar cero regresiones conocidas (la suite ya está verde; falta la confirmación humana del punto anterior).
- Con eso, la Etapa 1 completa (H0-H2 + Gate E1) queda cerrada.

### Etapa 2 (sin empezar — la mayor parte del trabajo restante)
H3 (dominio canónico) → H4 (backend privado FastAPI) → H5 (catálogo de precios) → H6 (agente guiado) → H7 (edición conversacional) → H8 (fallback web) → H9 (web móvil/PWA). Ver roadmap para detalle de cada uno.

**Bloqueante importante independiente del código**: hay decisiones del propietario (usuario) pendientes que bloquean H3 en adelante — fuentes de precios externas, política de vigencia, campos mínimos obligatorios, modelo de catálogo, formato exportable, política de privacidad, métricas objetivo, proveedor/modelos IA definitivo. Tabla completa al final de `docs/ROADMAP_ESTABILIZACION_Y_EVOLUCION_IA.md`. No se pueden inferir del código; hay que preguntárselas al usuario antes o durante H3/H5/H6.

## Notas operativas para el siguiente agente

1. **No hay nada commiteado.** Antes de tocar más código, decide con el usuario si quiere commitear H0-H2.5 primero (probablemente sí, es un buen punto de corte natural).
2. **PySide6 SÍ está instalado** en este entorno ahora (se instaló durante H1.3). Si trabajas en un entorno nuevo, puede que haga falta reinstalarlo — sin él, ~15-20 tests de GUI se omiten en vez de fallar (comportamiento correcto, documentado en el README).
3. **Nunca automatices clics/teclado sobre el escritorio real de este usuario sin extremo cuidado.** Ya se intentó una vez para el checklist manual y el teclado (`SendKeys`) se coló en la terminal en lugar de en la app — el usuario tiene su navegador y su terminal de Claude Code visibles en la misma pantalla que cualquier ventana que abras. Si hace falta repetirlo, usar solo clics de ratón (esos sí llegaban bien) o pedir al usuario que lo haga él mismo.
4. **`CUBIAPP_BACKUP_DIR` y `CUBIAPP_CONFIG_DIR`** son variables de entorno nuevas/reforzadas esta sesión — si escribes un script o test que conecte a la BDD fuera del arnés de pytest (que ya las fija vía `conftest.py`), fíjalas tú mismo para no escribir en las carpetas reales del usuario (`~/Documents/CubiApp/backups`, `~/.cubiapp`).
5. **Comando de verificación estándar usado toda la sesión:** `python -m pytest -q --tb=short` desde la raíz del repo. Tarda 85-110s. Ejecutarlo en background (vía el mecanismo de tareas del harness) y esperar la notificación en vez de bloquear, porque supera cómodamente timeouts cortos.
