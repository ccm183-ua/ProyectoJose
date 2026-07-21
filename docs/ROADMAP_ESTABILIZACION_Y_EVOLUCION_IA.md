# Roadmap ejecutable de estabilización y evolución de cubiApp

> Auditoría realizada sobre `prueba-claude` en `6ed5b93` el 2026-07-21. Este documento define el orden de trabajo, las verificaciones y las puertas mínimas entre hitos. No implementa todavía las tareas.

## Objetivo final

Convertir cubiApp, hoy una aplicación local PySide6 + SQLite + Excel, en una web responsive de uso individual que permita:

1. Describir o dictar una obra.
2. Recuperar primero información privada validada.
3. Completar huecos con un catálogo propio de precios.
4. Consultar fuentes web autorizadas solo cuando siga faltando cobertura.
5. Generar un borrador de presupuesto editable.
6. Modificarlo manualmente o mediante instrucciones a la IA, mostrando un diff antes de aplicar.
7. Entregar un presupuesto limpio y conservar separadamente un informe privado de trazabilidad.

La IA será un **agente guiado por flujo**. Las consultas, filtros, cálculos, validaciones y escrituras serán deterministas. El modelo podrá clasificar, estructurar y proponer, pero nunca escribirá directamente la fuente de verdad.

## Restricciones globales

- Usuario único: no construir equipos, roles, invitaciones ni portal de cliente.
- Web responsive/PWA: no construir app nativa.
- Compatibilidad Excel durante toda la migración.
- Claves de IA y credenciales solo en backend.
- Ninguna prueba automática depende de Internet, claves reales o servicios de pago.
- Una referencia inferida o web no se reutiliza hasta ser aprobada expresamente.
- Presupuesto limpio e informe privado se generan desde los mismos datos, pero son proyecciones separadas.
- No añadir búsqueda web hasta que procedencia, vigencia y privacidad estén implementadas.
- No sustituir SQLite por Postgres por anticipación. SQLite server-side es válido para un usuario y un único proceso con disco persistente; Postgres se adopta si el alojamiento exige varias instancias, disco efímero o concurrencia real.

## Estado verificado de partida

### Últimos cambios auditados

Los commits `8e3919d`, `f4bae0d` y `6ed5b93` introducen el orquestador unificado y conectan el flujo a creación y edición. En conjunto modifican 17 archivos, con unas 1.466 líneas añadidas y 96 eliminadas.

Valor aportado:

- `BudgetOrchestrator` separa cobertura histórica y huecos para IA.
- `AIModuleClassifier` restringe la clasificación a módulos conocidos.
- `VoiceBudgetDialog` unifica texto, dictado y generación.
- El dashboard reutiliza el flujo para regenerar o añadir partidas.

Riesgos introducidos:

- `BudgetOrchestrator` produce `fuente`; el normalizador y `BudgetService` consumen `source`.
- “Añadir partidas” no entrega las partidas existentes y puede duplicarlas.
- `VoiceBudgetDialog` muestra cobertura e inmediatamente se cierra.
- Una excepción imprevista en el hilo de generación no emite finalización y puede dejar la pantalla bloqueada.
- No hay tests directos del orquestador, clasificador IA, diálogo nuevo ni sus dos entradas GUI.

### Suite actual

Comando:

```powershell
python -m pytest -q --tb=short
```

Resultado con la plantilla ya presente: **10 fallos, 541 pruebas superadas y 9 omitidas en 103,15 segundos**.

| Causa raíz | Fallos visibles | Contrato que debe cerrarse |
|---|---:|---|
| `historical_partida.orden` recibe `None` aunque la columna es `NOT NULL` | 8 | Quién asigna el orden cuando el llamador no lo conoce. |
| `execution_module` nace vacío | 1 | El vocabulario del clasificador debe inicializarse y migrarse de forma idempotente. |
| `thinking` de DeepSeek depende de un nombre de modelo | 1 | El payload debe depender de una capacidad documentada, no de un slug accidental. |

La plantilla `templates/122-20 PLANTILLA PRESUPUESTO.xlsx` ya está exceptuada de `.gitignore`. Antes de incorporarla definitivamente hay que verificar que es distribuible y que un clon limpio puede usarla.

## Cómo se ejecutará cada tarea

Todas las tareas siguen el mismo ciclo:

1. Escribir o ajustar un test que reproduzca el contrato deseado.
2. Ejecutar únicamente ese test y comprobar que falla por el motivo esperado.
3. Hacer el cambio mínimo en el punto compartido por todos los llamadores.
4. Ejecutar el test específico y después el grupo funcional relacionado.
5. Actualizar contrato, migración o documentación si cambió comportamiento observable.
6. Ejecutar la puerta completa del hito.

Una tarea no se considera terminada porque “funcione manualmente”. Debe dejar una prueba repetible o, si depende de Excel real/Safari/infraestructura, una evidencia manual fechada y reproducible.

## Vista general de hitos

| Hito | Resultado utilizable | Requisito mínimo para entrar | Puerta mínima para salir |
|---|---|---|---|
| H0 | Repositorio reproducible | Rama y plantilla disponibles | Clon limpio, plantilla válida y suite verde. |
| H1 | Flujo IA local fiable | H0 superado | Generar/añadir/regenerar/cancelar/fallar sin pérdida de procedencia ni duplicados. |
| H2 | Núcleo preparado para migración | H1 superado | Contratos, migraciones, runtime y seams documentados y probados. |
| Gate E1 | Aplicación de escritorio estable | H0–H2 superados | Cero regresiones conocidas y checklist real de Excel aprobado. |
| H3 | Dominio canónico versionado | Gate E1 superado | Presupuesto y trazabilidad persisten sin depender de Excel. |
| H4 | Backend privado desplegable | H3 superado | API autenticada, almacenamiento durable y restauración ensayada. |
| H5 | Catálogo y procedencia utilizables | H4 superado | Cada precio tiene estado, vigencia y evidencia; nada externo se autoaprueba. |
| H6 | Primer borrador guiado sin web | H5 superado | Descripción → borrador trazable con privado + catálogo y preguntas pendientes. |
| H7 | Edición conversacional segura | H6 superado | Diff, confirmación, versiones y rollback por instrucción. |
| H8 | Fallback web controlado | H7 superado | Solo consulta por falta de cobertura y conserva evidencia verificable. |
| H9 | Web móvil lista para piloto | H8 superado | Flujo completo en iPhone/escritorio, métricas y backup restaurable. |

# Etapa 1 — Estabilización de la aplicación existente

## H0 — Repositorio reproducible y suite verde

### H0.1 — Incorporar la plantilla de forma segura

**Problema:** la aplicación y 30 pruebas dependían de un binario local ausente. La excepción de `.gitignore` ya está aplicada, pero aún hay que validar el fichero y su presencia real en un clon.

**Archivos:** `.gitignore`, `templates/122-20 PLANTILLA PRESUPUESTO.xlsx`, `src/utils/helpers.py`, `src/core/template_manager.py`, `tests/test_excel_template.py`.

**Ejecución:**

1. Abrir la plantilla y retirar nombres, direcciones, CIF, teléfonos, comentarios, propiedades del autor, conexiones y vínculos externos que pertenezcan a un caso real.
2. Conservar hojas, celdas, fórmulas, estilos y áreas de impresión que forman el contrato operativo.
3. Mantener la excepción exacta `!templates/122-20 PLANTILLA PRESUPUESTO.xlsx`; no liberar globalmente todos los `.xlsx`.
4. Añadir un test que cargue el libro con `openpyxl`, valide las hojas/celdas mínimas y falle con un mensaje claro si el recurso no existe o está corrupto.
5. Documentar que la plantilla es un recurso de la aplicación y no un fichero generado.
6. Tras el futuro commit, clonar en un directorio temporal y ejecutar los tests de Excel sin copiar archivos manualmente.

**Verificación:**

```powershell
git check-ignore -v -- "templates/122-20 PLANTILLA PRESUPUESTO.xlsx"
python -m pytest tests/test_excel_template.py tests/test_data_validation.py -q
```

El primer comando debe señalar la regla de excepción y los tests deben terminar con código 0.

### H0.2 — Alinear el contrato de `historical_partida.orden`

**Problema:** ocho tests insertan partidas válidas sin `orden`; el repositorio pasa `None` a una columna `NOT NULL`.

**Archivos:** `src/core/repositories/historical_repository.py`, `src/core/historical_budget_analyzer.py`, `tests/test_historical_integrity_diagnostics.py`, `tests/test_historical_pattern_builder.py`, `tests/test_historical_suggestion_service.py`.

**Decisión recomendada:** el orden explícito se respeta. Si falta, el repositorio asigna el siguiente orden del mismo presupuesto dentro de la transacción. Así todos los llamadores comparten el mismo invariante y los tests no tienen que inventar un valor que no forma parte de su escenario.

**Ejecución:**

1. Añadir tests de repositorio para orden explícito, orden ausente y dos inserciones consecutivas.
2. Reproducir primero `Faltan datos obligatorios.` en el test de orden ausente.
3. Calcular `MAX(orden) + 1` únicamente cuando `orden` no esté presente; no sobrescribir valores explícitos.
4. Ejecutar lectura y reconstrucción de patrones para comprobar que el orden almacenado sigue siendo estable.
5. Añadir una restricción única `(historical_budget_id, orden)` solo si el análisis de datos existentes confirma que no hay duplicados; si los hay, limpiar/migrar antes de crearla.

**Verificación:**

```powershell
python -m pytest tests/test_historical_integrity_diagnostics.py tests/test_historical_pattern_builder.py tests/test_historical_suggestion_service.py -q
```

### H0.3 — Crear un catálogo único e inicializable de módulos

**Problema:** `MODULE_RULES` contiene 12 módulos que el clasificador usa, pero una BDD recién creada deja `execution_module` vacío. Además, el test ya presupone una descripción de módulo que el esquema base no modela.

**Archivos:** `src/core/historical_partida_classifier.py`, `src/core/database.py`, `src/core/repositories/historical_repository.py`, `src/core/historical_integrity_diagnostics.py`, `tests/test_historical_integrity_diagnostics.py`, `tests/test_historical_partida_classifier.py`.

**Ejecución:**

1. Sustituir la duplicación implícita por un catálogo único con nombre estable, etiqueta/descripción, categoría y palabras clave.
2. Añadir mediante migración las columnas de catálogo que falten; no confiar solo en el `CREATE TABLE` porque existen BDD antiguas.
3. Sembrar los 12 módulos con `INSERT ... ON CONFLICT/IGNORE` durante `init_schema()`.
4. No reactivar ni sobrescribir personalizaciones del usuario en cada arranque; el seed solo crea faltantes y la migración solo completa campos vacíos conocidos.
5. Hacer que clasificador, seed y diagnóstico lean el mismo catálogo.
6. Probar BDD nueva, BDD inicializada dos veces y BDD antigua sin columnas nuevas.

**Verificación:**

```powershell
python -m pytest tests/test_historical_integrity_diagnostics.py tests/test_historical_partida_classifier.py tests/test_database.py -q
```

### H0.4 — Cerrar el contrato del payload DeepSeek

**Problema:** el adapter añade `thinking` solo al modelo predeterminado, mientras el test lo exige a un slug personalizado. Ninguna de las dos reglas expresa una capacidad real.

**Archivos:** `src/core/ai_clients.py`, `src/core/settings.py`, `tests/test_ai_clients.py`.

**Ejecución:**

1. Revisar la documentación vigente del endpoint y de cada modelo permitido.
2. Representar explícitamente si un modelo acepta, exige o rechaza `thinking`.
3. Para un modelo desconocido, enviar únicamente el payload común seguro; no suponer capacidades.
4. Parametrizar tests para modelo estándar, modelo con capacidad de razonamiento y slug desconocido.
5. Mantener tests de redacción de secretos, timeout, error HTTP y JSON inválido.

**Verificación:**

```powershell
python -m pytest tests/test_ai_clients.py -q
```

### Puerta mínima H0

Todos los puntos son obligatorios:

- [ ] La plantilla está versionada, sanitizada y se abre con `openpyxl`.
- [ ] Una BDD nueva y una BDD migrada pasan los mismos tests de contrato.
- [ ] Los 10 fallos actuales tienen una prueba que demuestra su causa raíz.
- [ ] `python -m pytest -q` termina con código 0 desde un clon limpio.
- [ ] Todo `skip` restante tiene una razón explícita de plataforma o integración; ninguno oculta falta de fixture.

## H1 — Flujo IA local fiable y cubierto

### H1.1 — Unificar la procedencia en memoria

**Problema:** `fuente` se pierde al cruzar el seam de normalización porque el resto del flujo usa `source`.

**Archivos:** `src/core/budget_orchestrator.py`, `src/core/partida_normalizer.py`, `src/core/services/budget_service.py`, `src/gui/main_frame.py`, `src/gui/budget_dashboard.py`, `src/gui/combined_partidas_review_dialog.py`; crear `tests/test_budget_orchestrator.py`.

**Ejecución:**

1. Elegir `source` como clave canónica porque ya la consumen normalizador, generador y diálogos existentes.
2. Definir valores cerrados: `historical`, `ai_estimate`, `catalog`, `web` y `unknown`.
3. Aceptar temporalmente `fuente` solo en el adaptador de entrada; todo resultado interno sale con `source`.
4. Preservar también `confidence`, `historical_frequency`, módulo y referencia de evidencia disponibles.
5. Cambiar la separación histórica/IA de las GUI para leer el valor canónico.
6. Probar una mezcla de partida histórica e IA hasta el adapter Excel.

**Verificación mínima:** ninguna partida con origen conocido termina como `unknown`; un alias legado se normaliza una única vez.

### H1.2 — Restaurar la semántica de añadir frente a regenerar

**Problema:** `_edit_add_partidas()` lee el presupuesto existente, pero no entrega sus partidas al flujo unificado.

**Archivos:** `src/gui/budget_dashboard.py`, `src/core/budget_orchestrator.py`, `src/core/historical_suggestions_dedupe.py`; crear tests del caso de uso sin PySide6.

**Ejecución:**

1. Extraer del presupuesto existente la lista normalizada de partidas antes de generar.
2. Pasarla como exclusiones al caso de uso de “añadir”.
3. Reutilizar `dedupe_normalized_partidas()` y `dedupe_merged_review_partidas()`; no crear una tercera heurística.
4. Comparar concepto normalizado + unidad y usar precio solo como señal secundaria: una misma partida con precio actualizado sigue siendo posible duplicado.
5. Mostrar duplicados descartados o dudosos en la revisión; no descartarlos silenciosamente cuando la coincidencia no sea exacta.
6. Mantener “regenerar” como reemplazo total solo después de confirmación.
7. Probar cancelar antes y después de generar: Excel y BDD deben conservar hash y recuentos.

**Verificación mínima:** añadir no repite coincidencias exactas; regenerar reemplaza; cancelar no escribe.

### H1.3 — Hacer observable la cobertura y todos los finales del diálogo

**Problema:** la cobertura se dibuja y el diálogo se cierra en la misma llamada; una excepción inesperada en el worker no emite resultado.

**Archivos:** `src/gui/voice_budget_dialog.py`, `src/gui/combined_partidas_review_dialog.py`; crear `tests/test_voice_budget_dialog.py`.

**Ejecución:**

1. Envolver `_run_generation()` y convertir toda excepción en un resultado de error saneado.
2. Garantizar que éxito, error y cancelación rehabilitan controles y terminan el hilo.
3. Mover el resumen de cobertura al diálogo de revisión que sí permanece visible.
4. Mostrar cuatro estados: histórico suficiente, mezcla, solo estimación y resultado incompleto/error.
5. No mostrar “precios reales” como sinónimo automático de histórico; usar “referencias históricas” para no prometer vigencia.
6. Probar cierre de ventana mientras el worker está activo y evitar callbacks sobre widgets destruidos.

**Verificación mínima:** ninguna excepción deja controles deshabilitados; el usuario ve la cobertura antes de aprobar.

### H1.4 — Probar directamente el orquestador y el clasificador IA

**Archivos:** crear `tests/test_budget_orchestrator.py` y `tests/test_ai_module_classifier.py`; ampliar pruebas del dashboard solo en el seam del caso de uso.

**Escenarios obligatorios:**

1. Histórico cubre todos los módulos: cero llamadas al proveedor IA.
2. Cobertura parcial: IA recibe solo módulos gap.
3. Sin módulos ni histórico: fallback completo.
4. Sin API key: resultado incompleto y error accionable, no excepción sin tratar.
5. Error de BDD y error del proveedor.
6. Respuesta IA inválida o con módulo fuera del vocabulario.
7. Mezcla con duplicado histórico/IA.
8. Procedencia y confianza sobreviven al merge.
9. Partidas existentes se respetan en modo añadir.

Todos usan adapters falsos; no red, sleeps ni claves.

### Puerta mínima H1

- [ ] Crear, añadir, regenerar, cancelar y error de IA están cubiertos sin red.
- [ ] El resultado del orquestador tiene un contrato único documentado.
- [ ] No se pierden `source`, confianza ni módulo al normalizar.
- [ ] “Añadir” no introduce duplicados exactos y presenta los dudosos.
- [ ] La cobertura se ve antes de confirmar.
- [ ] `python -m pytest -q` sigue verde.
- [ ] Checklist manual en una copia temporal de Excel: crear, añadir, regenerar, cerrar sin guardar y finalizar.

## H2 — Contratos estables y núcleo preparado para web

### H2.1 — Definir una fuente de verdad por entidad

**Archivos:** crear `CONTEXT.md`, `docs/adr/0001-fuentes-de-verdad.md`, `docs/adr/0002-excel-como-adaptador.md`; revisar `src/core/database.py`, `budget_cache.py`, `BudgetService` y repositorios.

**Ejecución:**

1. Inventariar cada escritura a `historial_presupuesto`, `presupuesto`, `presupuesto_partida`, `historical_budget` y Excel.
2. Para cada entidad documentar identidad, propietario, estados, quién puede escribir, qué es derivable y cómo se reconcilia.
3. Declarar temporalmente Excel como artefacto operativo heredado y SQLite como índice/snapshot; no fingir todavía que existe un presupuesto canónico.
4. Registrar la decisión objetivo: presupuesto y versiones server-side serán canónicos; Excel será importación/exportación.
5. Definir qué sucede si Excel y BDD discrepan antes de migrar.

**Verificación mínima:** toda escritura actual aparece en la matriz y tiene una regla de precedencia; ningún término crítico conserva dos significados sin registrar.

### H2.2 — Concentrar el caso de uso de presupuesto fuera de PySide6

**Archivos:** `src/core/services/budget_service.py`, `src/core/budget_orchestrator.py`, `src/gui/main_frame.py`, `src/gui/budget_dashboard.py` y tests de flujo.

**Ejecución:**

1. Dibujar la secuencia crear → generar → revisar → aplicar → finalizar y localizar decisiones duplicadas en ambas GUI.
2. Mover únicamente reglas de negocio al módulo de presupuesto; los diálogos conservan presentación y confirmación.
3. Hacer que creación y dashboard llamen al mismo seam con un modo explícito (`create`, `append`, `replace`).
4. Inyectar acceso a histórico, IA, reloj y Excel para probar sin UI ni disco real.
5. Retirar el camino legacy solo cuando sus escenarios estén cubiertos por el nuevo.

**Verificación mínima:** los tests del caso de uso no importan PySide6; los dos puntos de entrada producen el mismo contrato.

### H2.3 — Unificar ejecución estructurada de IA

**Archivos:** `src/core/ai_service.py`, `src/core/ai_clients.py`, `src/core/budget_generator.py`, `src/core/ai_module_classifier.py`, `src/core/historical_budget_enrichment_service.py`.

**Ejecución:**

1. Inventariar llamadas directas a Gemini/DeepSeek y sus diferencias de timeout, reintento y JSON.
2. Mantener un único seam de ejecución estructurada: prompt del sistema, payload, esquema esperado, modelo, timeout y metadatos de uso.
3. Conservar Gemini y DeepSeek como adapters reales; eliminar la ruta duplicada cuando todos los llamadores estén migrados.
4. Normalizar errores en categorías estables: configuración, autenticación, límite, timeout, respuesta inválida y proveedor no disponible.
5. Registrar proveedor/modelo/latencia/tokens cuando estén disponibles, nunca claves ni texto privado completo.

**Verificación mínima:** ningún caso de uso importa un SDK de proveedor; los tests de contrato se ejecutan contra ambos adapters falsos.

### H2.4 — Introducir migraciones y recuperación de BDD

**Archivos:** `src/core/database.py`, `src/core/database_backup.py`, `src/core/database_persistence.py`; crear fixtures de snapshots en `tests/fixtures/` sin datos reales.

**Ejecución:**

1. Asignar versión explícita al esquema actual.
2. Convertir cada `ALTER TABLE` existente en una migración ordenada e idempotente.
3. Crear snapshots mínimos de cada versión soportada.
4. Ejecutar backup antes de migrar y conservar el original si algo falla.
5. Probar migración desde cada snapshot, doble ejecución y restauración.

**Verificación mínima:** BDD nueva y migrada terminan en la misma versión y preservan recuentos, totales y relaciones.

### H2.5 — Alinear runtime, documentación y política de pruebas

**Archivos:** `README.md`, `requirements.txt`, `.env.example`, `pytest.ini`, scripts de arranque y documentos antiguos.

**Ejecución:**

1. Fijar Python 3.10+ o retirar toda sintaxis incompatible; la recomendación es fijar 3.11, que es el entorno auditado.
2. Sustituir referencias activas a wxPython por PySide6.
3. Documentar prioridad real de rutas y variables para BDD, configuración y plantillas.
4. Clasificar los 9 skips restantes: plataforma Windows/Excel, dependencia opcional o integración.
5. Definir dos comandos: suite rápida sin integraciones y suite completa Windows/Excel.
6. Añadir CI para el conjunto portable y conservar checklist manual para COM/Excel.

**Verificación mínima:** una persona con un clon limpio puede instalar, arrancar y ejecutar tests siguiendo solo README.

### Puerta mínima H2 / Gate de Etapa 1

- [ ] H0 y H1 continúan verdes.
- [ ] `CONTEXT.md` y ADRs describen la realidad y el destino sin contradicciones.
- [ ] El flujo de presupuesto se prueba sin GUI.
- [ ] Existe una única interfaz de ejecución IA con al menos dos adapters reales.
- [ ] Las migraciones son versionadas, idempotentes y recuperables.
- [ ] README coincide con PySide6, Python y rutas reales.
- [ ] Suite portable verde en CI y checklist Windows/Excel aprobado.
- [ ] No queda ninguna regresión conocida de los commits auditados.

# Etapa 2 — Evolución hacia el producto web con IA

## H3 — Dominio canónico y versiones de presupuesto

**Objetivo:** dejar de usar Excel, caché e histórico como representaciones intercambiables.

**Modelo mínimo:**

- `budget`: identidad, proyecto, estado y versión activa.
- `budget_version`: snapshot inmutable de un borrador o aprobación.
- `budget_line`: identidad estable, orden, concepto, unidad, cantidad, precio e importe.
- `evidence`: tipo de fuente, referencia, fecha de consulta, modelo/herramienta y evidencia resumida.
- `field_evidence`: vínculo de evidencia al menos para precio, cantidad y descripción.
- `document`: metadatos y ubicación de Excel/PDF.
- `approval`: quién/qué/fecha y versión aprobada; en v1 siempre el propietario único.

**Ejecución:**

1. Escribir invariantes y estados (`draft`, `approved`, `superseded`) antes del esquema.
2. Diseñar migración desde `presupuesto`, `presupuesto_partida` y Excel sin borrar origen.
3. Importar cada presupuesto como versión inicial y registrar advertencias de reconciliación.
4. Calcular importes y totales en código determinista; no aceptar totales calculados por el modelo.
5. Convertir Excel en adapter de importación/exportación.
6. Ejecutar migración en una copia anonimizada y comparar número de presupuestos, partidas y totales.

**Puerta mínima H3:**

- [ ] Crear/editar/aprobar funciona sin abrir Excel.
- [ ] Cada edición crea versión recuperable.
- [ ] Importar y exportar conserva totales dentro de tolerancia de 0,01 €.
- [ ] Patrones derivados pueden reconstruirse sin cambiar presupuestos aprobados.
- [ ] Ninguna escritura canónica depende de `presupuesto` como caché.

## H4 — Backend privado, autenticación y almacenamiento durable

**Dirección mínima recomendada:** conservar Python y exponer los casos de uso mediante FastAPI. Para un solo usuario, servir HTML desde el mismo backend evita mantener una SPA y una API duplicadas. Empezar con SQLite en volumen persistente y un solo proceso; usar Postgres si el proveedor de alojamiento no garantiza estas condiciones.

**Ejecución:**

1. Exponer endpoints solo para iniciar borrador, consultar estado, editar, aprobar, exportar y consultar trazabilidad.
2. Colocar un gateway de autenticación administrado delante de la aplicación y limitarlo a un único correo. Si el alojamiento no lo permite, implementar sesión server-side con cookie `HttpOnly`, `Secure`, `SameSite=Lax`, contraseña robusta y segundo factor.
3. Deshabilitar registro público, recuperación pública, organizaciones y roles.
4. Mantener claves IA en variables/secret manager del servidor.
5. Guardar Excel/PDF en almacenamiento durable; la BDD solo conserva ubicación, hash, tamaño y propietario.
6. Aplicar límites de tamaño/tipo, nombres aleatorios y análisis de los ficheros subidos antes de procesarlos.
7. Añadir backup automático cifrado y probar restauración en entorno limpio.
8. Registrar auditoría mínima de login, generación, aprobación, exportación y error, sin prompts completos ni PII innecesaria.

**Puerta mínima H4:**

- [ ] Toda ruta privada responde 401/403 sin sesión.
- [ ] Solo la identidad configurada puede entrar.
- [ ] Ninguna clave aparece en HTML, JavaScript, logs o respuestas.
- [ ] Reiniciar/desplegar no pierde BDD ni documentos.
- [ ] Backup y restauración están ensayados y documentados.
- [ ] Los casos de uso se ejecutan igual por test directo y HTTP.

## H5 — Catálogo de precios, vigencia y procedencia persistente

**Objetivo:** que “precio” deje de ser un número sin contexto.

**Ejecución:**

1. Modelar `price_reference` con concepto normalizado, unidad, zona, importe, moneda, impuestos incluidos, proveedor/origen, fecha y evidencia.
2. Modelar estado `proposed`, `approved`, `rejected`, `expired`.
3. Importar patrones históricos como referencias históricas, no como precios actuales garantizados.
4. Normalizar unidades y rechazar combinaciones incompatibles antes de comparar precios.
5. Aplicar la política de vigencia acordada y marcar referencias caducadas sin borrarlas.
6. Hacer que aceptar una partida no implique automáticamente aprobar su precio para reutilización; ofrecer una confirmación separada.
7. Generar el informe privado desde `evidence` y `field_evidence`, no desde texto improvisado por el modelo.
8. Generar el presupuesto limpio omitiendo esos campos, sin eliminarlos de la BDD.

**Puerta mínima H5:**

- [ ] Todo precio del borrador tiene origen, fecha, estado y vigencia.
- [ ] Precio web/IA nunca entra aprobado por defecto.
- [ ] Referencias caducadas generan aviso visible.
- [ ] Unidades incompatibles no se agregan ni promedian.
- [ ] Presupuesto limpio e informe privado cuadran con la misma versión y total.

**Decisiones que deben estar cerradas antes:** fuentes admitidas, vigencia, impuestos, zona y nivel de desglose del catálogo.

## H6 — Agente guiado para primer borrador, todavía sin web

**Estados del flujo:** `intake` → `needs_clarification` → `private_retrieval` → `coverage` → `catalog_retrieval` → `proposal` → `validation` → `ready_for_review` o `incomplete`.

**Ejecución:**

1. Definir un esquema estructurado de entrada: descripción, ubicación, medidas, materiales, alcance y restricciones conocidas.
2. Ejecutar reglas deterministas de campos faltantes antes de llamar al modelo.
3. Usar IA económica para estructurar texto y clasificar módulos dentro del vocabulario permitido.
4. Buscar histórico validado con evidencia y calcular cobertura por módulo/campo.
5. Consultar catálogo aprobado solo para los huecos restantes.
6. Preguntar al usuario cuando un dato cambie sustancialmente cantidad, alcance o precio; no inventarlo silenciosamente.
7. Permitir estimaciones explícitas cuando la política lo autorice y marcarlas como `proposed`.
8. Validar unidades, cantidades positivas, precios, duplicados, totales y esquema antes de persistir.
9. Persistir ejecución, pasos, herramientas, modelos, latencia y coste; no persistir secretos.
10. Escalar a un modelo más capaz únicamente por regla observable: ambigüedad no resuelta, conflicto entre fuentes o esquema inválido tras un reintento.

**Pruebas doradas mínimas:** reforma cubierta por histórico, cobertura parcial, obra nueva sin catálogo, medidas ambiguas, unidades incompatibles, proveedor caído y respuesta IA inválida.

**Puerta mínima H6:**

- [ ] Ninguna salida del modelo escribe directamente presupuesto o catálogo.
- [ ] Histórico se consulta antes que catálogo y la web permanece desactivada.
- [ ] Cada hueco termina resuelto, preguntado o marcado como incompleto.
- [ ] Los escenarios dorados son deterministas con adapters falsos.
- [ ] Se miden tiempo, coste, cobertura y porcentaje de líneas editadas.

## H7 — Edición manual y conversacional con diff

**Ejecución:**

1. Mantener edición directa de concepto, unidad, cantidad y precio sin IA.
2. Convertir una instrucción natural en operaciones estructuradas: `add_line`, `update_line`, `remove_line`, `reorder_line`.
3. Referenciar líneas por ID estable, nunca por posición visual.
4. Validar las operaciones y calcular un diff antes de escribir.
5. Mostrar valor anterior, nuevo, motivo y efecto en el total.
6. Aplicar solo tras confirmación y crear una versión nueva.
7. Cancelar conserva íntegra la versión anterior.
8. Si una instrucción es ambigua, pedir selección de partida; no elegir por similitud débil.
9. Registrar qué cambios fueron manuales y cuáles propuestos por IA.

**Puerta mínima H7:**

- [ ] “Cambia PVC por zinc”, “son 18 m” y “elimina andamio” solo afectan las líneas previstas.
- [ ] Todo cambio IA muestra diff y requiere confirmación.
- [ ] Cancelar y deshacer recuperan exactamente la versión anterior.
- [ ] Totales se recalculan de forma determinista.
- [ ] Una edición manual nunca requiere disponibilidad del proveedor IA.

## H8 — Consulta web controlada como último recurso

**Ejecución:**

1. Aprobar una allowlist inicial de fuentes y comprobar sus condiciones de uso/licencia.
2. Separar consulta, extracción, normalización y aprobación en pasos auditables.
3. Redactar cliente, dirección exacta y cualquier dato no necesario antes de construir la consulta.
4. Ejecutar web solo si la cobertura privada + catálogo queda bajo el umbral acordado.
5. Limitar consultas, tiempo y coste por borrador; impedir bucles del modelo.
6. Tratar todo contenido web como no confiable y aislarlo de instrucciones del sistema.
7. Guardar URL, proveedor, fecha, moneda, impuestos, unidad, fragmento probatorio permitido y hash.
8. Aplicar caducidad y mostrar el dato como propuesta pendiente.
9. Si no hay fuente válida, devolver un borrador incompleto y una pregunta clara; nunca un precio inventado como si estuviera verificado.

**Puerta mínima H8:**

- [ ] Cero consultas cuando privado/catálogo cubren el caso.
- [ ] Dominio no autorizado se bloquea antes de descargar contenido.
- [ ] Cada precio externo conserva evidencia y fecha.
- [ ] Caída, rate limit o contenido malicioso no corrompen el borrador.
- [ ] Ningún precio web se reutiliza sin aprobación separada.

## H9 — Web responsive/PWA y piloto individual

**Dirección Ponytail:** empezar con vistas server-rendered y mejoras HTMX/JavaScript puntuales. No crear una SPA completa hasta que el flujo probado demuestre que la necesita. En iPhone, usar primero el dictado nativo del teclado en un `textarea`; grabación/subida de audio queda fuera salvo necesidad demostrada.

**Pantallas mínimas:** login, lista de presupuestos, nueva descripción, preguntas pendientes, revisión de partidas, diff, trazabilidad privada, aprobación y exportación.

**Ejecución:**

1. Diseñar primero el recorrido móvil con acciones primarias grandes y tabla convertida en tarjetas editables en pantallas estrechas.
2. Mostrar progreso por estados del agente; permitir abandonar y recuperar el borrador.
3. Mantener trazabilidad detrás de una vista privada y excluirla del PDF/Excel del cliente.
4. Añadir PWA instalable solo después de que Safari funcione correctamente como web normal.
5. Probar teclado, VoiceOver, foco, contraste, errores y sesión caducada.
6. Construir un conjunto piloto anonimizado de obras reales y registrar línea base manual.
7. Medir tiempo a primer borrador, aceptación de líneas, desviación, cobertura, coste y latencia.
8. Definir umbrales de uso habitual antes de retirar cualquier pantalla desktop.

**Puerta mínima H9 / salida del roadmap:**

- [ ] Flujo completo usable en Safari de iPhone y navegador de escritorio.
- [ ] Recarga o pérdida breve de conexión no pierde el borrador.
- [ ] Presupuesto limpio e informe privado nunca se mezclan.
- [ ] Exportación Excel/PDF conserva versión, totales y formato acordado.
- [ ] Restauración de backup y rotación de secretos probadas.
- [ ] Métricas del piloto alcanzan los umbrales acordados.
- [ ] La aplicación desktop se mantiene como fallback hasta completar una migración real verificada.

# Decisiones del propietario y momento límite

Estas decisiones no bloquean H0–H2. Deben cerrarse antes del hito indicado.

| Decisión | Opciones razonables | Información necesaria | Fecha límite |
|---|---|---|---|
| Fuentes de precios externas | Fabricantes/proveedores permitidos; base licenciada; buscador restringido | Proveedores usados, zona, suscripciones y licencia | Antes de H5/H8 |
| Vigencia | Global; por familia; por fuente; manual con alerta | Frecuencia de cambio y tolerancia de desviación | Antes de H5 |
| Campos mínimos | Bloqueo estricto; borrador incompleto; preguntas progresivas | Ejemplos reales y supuestos aceptables | Antes de H6 |
| Catálogo | Precio único; histórico temporal; desglose material/mano de obra | Datos actuales, unidades, impuestos, zona y proveedor | Antes de H5 |
| Exportable | Plantilla exacta + PDF; Excel normalizado + PDF; PDF externo | Quién edita, fórmulas y requisitos contractuales | Antes de H3/H9 |
| Privacidad | Redacción; proveedor empresarial; documentos nunca externos; procesamiento local | Sensibilidad, retención y alojamiento | Antes de H4/H6 |
| Métricas | Tiempo, aceptación, edición, desviación, cobertura y coste | Línea base manual y umbral rentable | Antes de H6/H9 |
| Proveedor/modelos IA | Un proveedor; router económico/capaz; varios adapters | Volumen, presupuesto, privacidad, latencia y calidad técnica en español | Antes de H6 |

# Orden práctico de trabajo

1. Ejecutar H0 completo. No comenzar refactors amplios con la suite roja.
2. Ejecutar H1 en orden: procedencia → semántica de edición → estados GUI → cobertura de tests.
3. Ejecutar H2 y aprobar el Gate de Etapa 1.
4. Cerrar decisiones de exportación y privacidad mientras se modela H3.
5. Construir H3 y H4 sin IA nueva: primero datos y seguridad.
6. Cerrar catálogo, vigencia y campos mínimos; ejecutar H5.
7. Construir H6 con web desactivada y medirlo con casos dorados.
8. Añadir edición H7, después web H8 y finalmente interfaz/piloto H9.

No se considera avance válido saltar a una pantalla web que invoque el orquestador actual: trasladaría a Internet los contratos rotos, la ambigüedad de fuentes y la falta de trazabilidad en vez de resolverlos.
