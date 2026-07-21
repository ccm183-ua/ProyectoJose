# Boceto: estado de cubiApp y visión de presupuestos con IA

> Documento de contexto para elaborar un roadmap. Describe el estado observado en la rama `prueba-claude` (`6ed5b93`, 2026-07-21), las decisiones de producto ya tomadas y los huecos que aún existen. No es una especificación de implementación ni autoriza cambios por sí solo.

## 1. Idea principal

**cubiApp** es hoy una aplicación de escritorio en Python/PySide6 para crear, abrir, editar y organizar presupuestos de obra en Excel. Mantiene datos de clientes y de presupuestos en SQLite local y ha empezado a incorporar un sistema de aprendizaje histórico y generación de partidas asistida por IA.

La evolución deseada no es una app nativa: será una **aplicación web responsive**, de uso individual y protegida por autenticación. Su función central será transformar una descripción de obra, escrita o dictada, en un borrador de presupuesto que sea rápido de revisar y editar.

El agente deberá usar la información en este orden:

1. Datos privados validados: presupuestos anteriores, partidas y patrones históricos.
2. Catálogo propio de precios aprobado por el usuario (todavía no existe como entidad de datos).
3. Fuentes web autorizadas, solo cuando la cobertura privada sea insuficiente.

El resultado tiene dos vistas separadas:

- **Presupuesto limpio:** editable y exportable, sin ruido técnico ni fuentes internas; es el documento que se puede compartir con el cliente.
- **Informe privado de trazabilidad:** para el propietario de la aplicación. Explica de dónde procede cada partida y precio, qué se estimó, qué se obtuvo de web, cuándo se consultó y qué confianza tiene cada dato.

Una partida obtenida de web o inferida por IA puede formar parte del borrador, pero no debe convertirse en conocimiento privado reutilizable hasta que el usuario la confirme explícitamente.

## 2. Estado del repositorio

### Tecnología y ejecución

- Lenguaje: Python 3.8+ según README; entorno auditado con Python 3.11.
- UI actual: PySide6. `main.py` crea `QApplication` y abre `src/gui/main_frame.py`.
- Persistencia local: SQLite, resuelta desde `Settings`, `CUBIAPP_DB_PATH` o `~/Documents/CubiApp/datos.db`.
- Artefacto de presupuesto: fichero Excel `.xlsx`; se crean carpetas de proyecto y se modifica el Excel directamente, incluso mediante escritura XML para partidas.
- IA actual: Gemini o DeepSeek, con claves en variables de entorno o `~/.cubiapp/cubiapp_config.json`.
- Pruebas: pytest; existen 559 casos recogidos en el checkout actual.

La aplicación no tiene servidor HTTP, API pública, autenticación de usuarios, cola de trabajos, almacenamiento remoto ni cliente web. SQLite y los Excel viven en la máquina local. Por tanto, **aún no puede publicarse como web sin separar primero el núcleo de negocio de la UI de escritorio y centralizar datos y ficheros en servidor**.

### Mapa de módulos

| Área | Módulos principales | Responsabilidad actual |
|---|---|---|
| Arranque y UI | `main.py`, `src/gui/main_frame.py`, diálogos PySide6 | Navegación, formularios, dashboards y revisión manual. |
| Presupuestos Excel | `BudgetService`, `ExcelManager`, `BudgetReader`, `ExcelBudgetEditor`, `ExcelPartidasWriter/Extractor` | Crear Excel desde plantilla, leer cabecera/partidas, insertar partidas, editar y exportar PDF. |
| Datos de negocio | `database.py`, `repositories/*`, `DatabaseService` | Esquema SQLite y CRUD de comunidades, administraciones, contactos, historial y caché de presupuestos. |
| Histórico de aprendizaje | `HistoricalBudgetAnalyzer`, `HistoricalPatternBuilder`, `HistoricalSuggestionService`, clasificadores y diagnósticos | Analizar Excels pasados, normalizar conceptos, clasificarlos y construir patrones reutilizables. |
| IA | `BudgetOrchestrator`, `BudgetGenerator`, `PromptBuilder`, `AIService`, `ai_clients.py` | Combinar histórico e IA, construir prompts y pedir partidas en JSON a Gemini o DeepSeek. |
| Configuración | `Settings`, `AISettingsDialog`, `custom_templates.py` | Guardar claves locales, proveedor/modelo, rutas y plantillas personalizadas. |

## 3. Datos y fuentes de verdad actuales

El sistema actual es **híbrido**, no tiene una única fuente de verdad global. Los Excels son el artefacto operativo y SQLite mantiene datos de negocio, cachés y una memoria histórica derivada. Antes de publicar en web hay que definir qué entidad será canónica y cómo se sincroniza.

| Dato | Dónde se almacena | Cómo se crea/actualiza | Uso actual |
|---|---|---|---|
| Comunidad, administración y contacto | Tablas SQLite `comunidad`, `administracion`, `contacto` y relaciones N:M | Formularios de la app y repositorios | Rellenar y resolver la cabecera del presupuesto. |
| Presupuesto abierto/creado | Excel en carpeta del proyecto + `historial_presupuesto` | `BudgetService.create_budget()` u `open_budget()` | Mantener accesos y metadatos básicos. |
| Presupuesto cacheado/finalizado | `presupuesto` y `presupuesto_partida` | Escaneo de carpetas o `BudgetService.finalize_budget()` leyendo el Excel | Dashboard, búsqueda, estado, totales y detalle. `presupuesto` nació como caché, aunque el flujo finalizado lo trata también como snapshot persistente. |
| Presupuesto histórico analizado | `historical_budget`, `historical_partida`, módulos e incidencias | Análisis por lote de Excels | Alimentar la memoria de aprendizaje; conserva calidad, advertencias y decisión de inclusión. |
| Patrón reutilizable de partida | `suggested_partida_pattern` y `suggested_partida_pattern_source` | Reconstrucción desde históricos válidos e incluidos | Sugerir concepto, unidad y estadísticas de precio para módulos detectados. |
| Plantillas | `src/data/work_types.json` y `~/.cubiapp/custom_templates.json` | Catálogo predefinido o plantillas locales personalizadas | Contexto y fallback de generación IA. |
| Configuración y secretos | `~/.cubiapp/cubiapp_config.json` o variables de entorno | Diálogo de configuración | Proveedor IA, modelo, claves y rutas locales. |

No existe aún una tabla o servicio de **catálogo de precios propio**. Los precios reutilizables provienen indirectamente de patrones históricos, que calculan media, mediana, mínimo, máximo, frecuencia y confianza por concepto normalizado, unidad y módulo. Tampoco existe un repositorio de fuentes web, consulta, fecha de vigencia o evidencia de precios externos.

## 4. Flujos actuales

### 4.1 Crear y finalizar un presupuesto convencional

```text
Datos de proyecto + plantilla Excel
  -> BudgetService.create_budget()
  -> carpeta de proyecto + subcarpetas + Excel nuevo
  -> historial_presupuesto

Excel editado
  -> BudgetService.finalize_budget()
  -> lectura de cabecera y partidas del Excel
  -> resolución de comunidad/administración
  -> presupuesto + presupuesto_partida en SQLite
```

El Excel conserva una posición importante: los datos se vuelven a leer desde él para finalizar, escanear o refrescar el dashboard. Esto facilita compatibilidad con el proceso actual, pero hace que los cambios simultáneos, las versiones y la sincronización web no estén resueltos.

### 4.2 Aprendizaje desde presupuestos históricos

```text
Carpeta de Excels históricos
  -> HistoricalBudgetAnalyzer (sonda y lee cada archivo)
  -> historical_budget + historical_partida + incidencias/calidad
  -> clasificador por reglas y módulos de ejecución
  -> HistoricalPatternBuilder
  -> suggested_partida_pattern + fuentes de cada patrón
  -> HistoricalSuggestionService
```

El analizador intenta evitar archivos inválidos o no aptos para aprendizaje. El constructor de patrones usa solo históricos con estado válido y decisión de aprendizaje incluida. Cada patrón conserva las partidas históricas que justifican sus estadísticas, una base útil para la futura trazabilidad privada.

### 4.3 Generación de partidas con IA

Los cambios recientes incorporan un flujo unificado:

```text
Descripción libre o dictada
  -> VoiceBudgetDialog
  -> BudgetOrchestrator.generate()
  -> HistoricalSuggestionService: módulos y partidas históricas
  -> separar cobertura histórica suficiente e insuficiente
  -> BudgetGenerator: IA solo para módulos sin cobertura
  -> revisión combinada de partidas históricas y estimadas
  -> inserción en Excel y relectura/finalización
```

La cobertura histórica considera aptas las partidas con confianza mínima `0.60` y frecuencia histórica mínima `2`. Las restantes se generan con el proveedor de IA configurado. El resultado usa `fuente = historico` o `ia_estimado` en memoria, pero esta procedencia no está modelada de forma completa y durable en la tabla `presupuesto_partida` ni se presenta como un informe privado persistente.

El clasificador de módulos combina reglas, señales de texto y, como último recurso, una llamada IA que solo puede devolver nombres de un vocabulario controlado. Es un buen límite para no inventar categorías, aunque aún no resuelve precios ni fuentes externas.

## 5. Funcionalidad ya disponible

- Gestión local de comunidades, administraciones y contactos.
- Creación de un Excel desde plantilla y estructura de carpetas del proyecto.
- Apertura, escaneo, búsqueda y dashboard de presupuestos existentes.
- Inserción, añadido y regeneración de partidas; edición de cabecera; exportación PDF en Windows con Excel instalado.
- Plantillas predefinidas y personalizadas.
- Generación de partidas por Gemini/DeepSeek con fallback a plantilla cuando no hay IA.
- Análisis de un lote de Excels históricos, normalización, clasificación y generación de patrones de precios.
- Sugerencias de partidas históricas y combinación con IA para huecos de cobertura.
- Dictado opcional mediante `SpeechRecognition` y `PyAudio`.

## 6. Hallazgos de calidad y deuda técnica

### Bloqueadores verificados

1. Tras colocar la plantilla real y hacerla versionable, la suite sigue sin estar verde: **10 fallos, 541 éxitos y 9 omitidos** en 103,15 segundos (`python -m pytest -q --tb=short`). Los 30 fallos que ocultaba la ausencia de la plantilla han desaparecido.
2. La plantilla requerida `templates/122-20 PLANTILLA PRESUPUESTO.xlsx` ya existe y `.gitignore` contiene una excepción exclusiva para ella. Sigue siendo necesario incluirla en el próximo commit y comprobar que no contiene datos personales, vínculos externos ni contenido de un cliente real antes de considerarla un fixture distribuible.
3. Los 10 fallos restantes se agrupan en tres contratos: ocho por `historical_partida.orden`, uno por el catálogo `execution_module` sin inicializar y uno por el payload `thinking` de DeepSeek.
4. Hay documentación contradictoria o desactualizada: el README y planes antiguos mencionan wxPython, rutas antiguas y módulos que ya no existen, mientras el código de ejecución usa PySide6.

### Regresiones y riesgos observados en los últimos cambios

- En `BudgetDashboardFrame._edit_add_partidas()`, el nuevo flujo unificado no recibe las partidas existentes. Antes se enviaba a la IA un contexto explícito para no repetirlas; ahora puede proponer duplicados.
- `VoiceBudgetDialog` calcula el resumen de cobertura y acepta/cierra el diálogo de inmediato. El usuario no llega a ver ese resumen en esa pantalla.
- No hay pruebas directas de `BudgetOrchestrator`, `VoiceBudgetDialog`, `AIModuleClassifier` ni del nuevo flujo de edición del dashboard. El conjunto de cambios recientes no dispone de una red de seguridad específica.
- Una prueba aislada de DeepSeek falla porque espera el campo `thinking` en el payload, pero el código solo lo añade cuando el modelo es exactamente el predeterminado. Debe decidirse si el contrato es del cliente o de la prueba antes de cambiarlo.
- Algunos fallos de repositorio histórico indican desalineación entre validaciones actuales y fixtures de tests. No deben ocultarse: hay que reproducirlos en bases temporales limpias y corregir el contrato compartido.

### Limitaciones estructurales para la web

- La lógica de negocio está parcialmente acoplada a PySide6 y a rutas/Excels locales.
- La base SQLite está diseñada para un usuario local y no para acceso remoto concurrente.
- No hay API, modelo de sesión, almacenamiento de archivos, auditoría ni control de secretos de servidor.
- El estado de presupuesto se reparte entre Excel, tablas de caché/snapshot e histórico derivado.
- No existen versiones de presupuesto, cambios por partida, procedencia persistente por precio ni catálogo de precios aprobado.
- El prompt actual pide precios de mercado a la IA, pero el sistema no prueba ni registra de dónde salen esos precios.

## 7. Producto objetivo acordado

### Arquitectura de IA ya decidida

- **Patrón elegido: agente guiado por flujo.** Herramientas deterministas consultan BDD/histórico/catálogo/web y calculan cobertura; el modelo de IA solo clasifica, decide qué falta pedir y redacta el borrador y el informe. Se descartaron explícitamente: (a) un agente conversacional libre con acceso abierto a herramientas (peor control de coste y auditoría) y (b) plantillas/reglas con una única llamada IA final (no cubre obras nuevas ni búsqueda razonada).
- **Preferencia de proveedor:** no usar Claude/Anthropic como motor principal por coste; se prefiere una API de tipo "agente" más barata (p. ej. familia GPT) para el grueso del flujo (clasificación, estructuración, redacción), reservando un modelo más capaz solo para razonar sobre obras ambiguas. Proveedor y modelos concretos aún sin seleccionar.

### Usuario y acceso

- Un único propietario de la cuenta; sin roles de equipo ni portal de cliente en la primera etapa.
- Aplicación web responsive/PWA, usable desde iPhone en navegador.
- Autenticación obligatoria antes de consultar datos, generar borradores o ver informes.

### Caso de uso principal

1. El usuario describe una obra, por texto o voz, y aporta medidas, ubicación, materiales o documentos cuando los tenga.
2. El agente recupera evidencias privadas relevantes y calcula su cobertura.
3. Si faltan datos, consulta catálogo propio y, después, fuentes web permitidas.
4. Genera un borrador de presupuesto editable por partidas.
5. El usuario corrige por tabla o con instrucciones naturales; el agente actualiza solo las partidas afectadas y recalcula.
6. El usuario aprueba una versión y la exporta.
7. El sistema guarda, solo para el usuario, un informe de trazabilidad y la decisión de aceptar o no las nuevas referencias de precio.

### Requisitos funcionales clave

- Edición de concepto, unidad, cantidad, precio e importe sin pasar siempre por IA.
- Edición conversacional que produce un diff explícito antes de aplicar cambios.
- Procedencia por partida y, si es posible, por cada dato relevante: cantidad, precio y descripción.
- Informe privado conciso: fuente, fecha, cobertura, confianza, aviso de estimación y preguntas no resueltas.
- Separación estricta entre borrador interno y documento entregable al cliente.
- Reutilización solo de datos privados validados o de precios externos que el usuario haya aprobado.

## 8. Principios que debe respetar el futuro roadmap

1. **Primero calidad, después funcionalidad nueva.** Restablecer una suite fiable, versionar o provisionar fixtures y documentar el contrato real de Excel/SQLite antes de migrar nada.
2. **Una fuente de verdad definida por entidad.** El roadmap debe decidir qué es canónico para presupuesto, partidas, precios y documentos. No asumir que el Excel, una caché SQLite y el histórico son intercambiables.
3. **El modelo no escribe directamente la verdad.** La IA propone un cambio estructurado; validadores y reglas de negocio lo revisan; el usuario confirma los datos que vayan a convertirse en conocimiento reutilizable.
4. **La trazabilidad es un dato de dominio.** No puede limitarse a texto del prompt o logs. Debe persistir fuente, tipo de fuente, fecha, evidencia, confianza, versión del modelo y decisión del usuario.
5. **Las búsquedas web son herramientas controladas.** Definir proveedores/dominios permitidos, límite de consultas, tratamiento de datos privados, caducidad de precios y cómo citar o resumir la evidencia.
6. **Seguridad antes de exposición web.** Las claves de IA se quedan en el backend; el navegador nunca abre SQLite ni recibe secretos. Minimizar datos privados enviados al proveedor de IA o a búsquedas externas.
7. **Migración incremental.** Extraer servicios puros y contratos antes de sustituir UI, base de datos o formato Excel. Mantener importación/exportación de Excel mientras sea necesaria para operar.

## 9. Información que falta decidir antes del roadmap definitivo

- Qué fuentes web y qué tipo de precios son admisibles (fabricante, proveedor, bases de precios, buscador general, etc.).
- Política de vigencia: cuánto tiempo sirve un precio y cómo se avisa de que está desactualizado.
- Campos obligatorios para poder generar un presupuesto fiable y cuándo pedir aclaraciones en vez de estimar.
- Estructura del catálogo propio: precios por concepto/unidad/zona/proveedor, rango, fecha, evidencia y estado de aprobación.
- Formato definitivo del exportable y compatibilidad exigida con la plantilla Excel actual.
- Qué datos de obras y clientes pueden salir de la infraestructura privada y cuáles nunca pueden enviarse a un proveedor externo.
- Métricas de éxito: tiempo hasta primer borrador, partidas aceptadas sin edición, desviación frente a presupuesto final y tasa de precios sin evidencia privada.
- Proveedor y modelos de IA definitivos (económico para el flujo guiado, potente para casos ambiguos) — dirección tomada, elección concreta pendiente.

## 10. Encargo recomendado para el siguiente análisis

El roadmap amplio debe tener dos etapas separadas y con criterios de salida verificables:

1. **Estabilización de la aplicación existente:** incorporar y validar la plantilla versionable; resolver los 10 fallos restantes; alinear tests, documentación y contratos de datos; cubrir los flujos IA recién añadidos; corregir regresiones de edición y trazabilidad visible.
2. **Evolución hacia presupuestación asistida web:** definir dominio canónico, extraer un backend seguro, modelar catálogo/precio/procedencia/versiones, crear el flujo de borrador y edición, y solo después añadir consultas web y la interfaz responsive.

El orden es importante: una interfaz web no corrige los problemas de consistencia actuales; primero hay que hacer fiable el núcleo de datos y presupuesto que va a reutilizar.
