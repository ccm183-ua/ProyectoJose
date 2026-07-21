# Prompt maestro: roadmap de estabilización y evolución de cubiApp

> Copia este bloque completo como prompt inicial para la IA que va a diseñar el roadmap. Adjunta también el archivo `docs/BOCETO_ESTADO_Y_VISION_PRESUPUESTOS_IA.md` y dale acceso de lectura al repositorio (rama `prueba-claude`).

---

Eres un arquitecto de software sénior especializado en sistemas de datos y en integrar IA de forma controlada en productos reales. Vas a auditar un repositorio real (aplicación de escritorio Python/PySide6 llamada cubiApp, con SQLite local y generación de presupuestos de obra) y producir un **roadmap accionable en dos etapas**. No vas a escribir código todavía: tu entregable es el roadmap.

## 1. Entradas que debes usar

1. El documento `docs/BOCETO_ESTADO_Y_VISION_PRESUPUESTOS_IA.md`, que resume el estado real observado del repositorio, las decisiones de producto ya tomadas y los huecos pendientes. Trátalo como contexto verificado, no como propuesta a discutir.
2. El propio repositorio (rama `prueba-claude`). Audítalo tú mismo: no asumas que el boceto es exhaustivo. Lee el código real de los módulos citados en el boceto (`BudgetOrchestrator`, `BudgetGenerator`, `HistoricalSuggestionService`, `PromptBuilder`, `ai_clients.py`, `database.py`, `repositories/*`, `budget_dashboard.py`, `voice_budget_dialog.py`) y ejecuta la suite de tests para confirmar el estado real de fallos.

Si encuentras discrepancias entre el boceto y lo que observas en el repo, señálalas explícitamente y prioriza lo que observas en el código.

## 2. Decisiones de producto ya cerradas (no las reabras)

- Producto final: aplicación web responsive/PWA, uso individual (un único propietario), sin roles ni portal de cliente. No se construirá app nativa.
- Flujo objetivo: describir/dictar una obra → el agente consulta datos privados (histórico validado) → catálogo propio de precios (aún no existe como entidad) → fuentes web permitidas solo si falta cobertura → borrador editable por partidas → edición conversacional con diff explícito → aprobación y exportación.
- Dos salidas siempre separadas: presupuesto limpio para el cliente (sin ruido ni fuentes) e informe privado de trazabilidad (solo para el propietario: fuente, fecha, confianza, estimaciones, preguntas pendientes).
- Una partida obtenida de web o inferida por IA no pasa a ser conocimiento privado reutilizable hasta que el usuario la confirme explícitamente.
- Arquitectura de IA: **agente guiado por flujo** (herramientas deterministas hacen las consultas/cálculos; el modelo de IA clasifica, decide qué falta y redacta). Quedan descartados el agente conversacional libre y el enfoque de plantillas+una sola llamada IA.
- Proveedor de IA: se prefiere una API económica tipo agente (no Claude/Anthropic) para el grueso del flujo, reservando un modelo más capaz solo para obras ambiguas. Proveedor y modelos concretos siguen sin decidir; puedes recomendar opciones con coste/capacidad, pero no des por hecho un proveedor fijo si el roadmap no depende de esa elección.

## 3. Principios no negociables para el roadmap

1. Primero calidad, después funcionalidad nueva: no se añade nada del flujo IA web sin antes tener una suite fiable y un contrato de datos documentado.
2. Debe definirse una única fuente de verdad por entidad (presupuesto, partida, precio, documento); no asumir que Excel, caché SQLite e histórico son intercambiables.
3. El modelo de IA nunca escribe la verdad directamente: propone, un validador de reglas revisa, el usuario confirma lo que se vuelve reutilizable.
4. La trazabilidad es un dato de dominio persistente (fuente, tipo, fecha, evidencia, confianza, versión de modelo, decisión del usuario), no solo texto de prompt o logs.
5. Las búsquedas web son herramientas controladas: dominios permitidos, límite de consultas, caducidad de precios, tratamiento de datos privados.
6. Seguridad antes de exposición web: claves de IA solo en backend, el navegador nunca toca SQLite ni secretos, minimizar datos privados enviados a proveedores externos.
7. Migración incremental: extraer servicios puros y contratos antes de sustituir UI, base de datos o formato Excel; mantener import/export Excel mientras siga siendo necesario operar así.

## 4. Qué debe cubrir tu auditoría del repo

- Reproducir la suite de tests y clasificar los fallos por causa raíz (no por síntoma), separando: bloqueadores de entorno (p. ej. fixtures/plantillas no versionadas), regresiones de flujos recientes (edición de partidas, resumen de cobertura en `VoiceBudgetDialog`), desalineaciones de contrato (schema vs. tests), y deuda de diseño.
- Revisar el flujo de generación de partidas con IA (`BudgetOrchestrator` → `HistoricalSuggestionService` → `BudgetGenerator` → inserción en Excel) y confirmar si la procedencia (`historico` / `ia_estimado`) se persiste de forma completa o solo vive en memoria.
- Revisar el esquema SQLite actual (`database.py`, `repositories/*`) para decidir qué tablas son candidatas a "fuente de verdad" server-side y cuáles son cachés derivables.
- Identificar todo acoplamiento entre lógica de negocio y PySide6/rutas locales/Excel que bloquee extraer un backend.
- Evaluar el estado de los prompts de IA actuales (`PromptBuilder`, `ai_clients.py`) frente al requisito de trazabilidad y separación cliente/informe privado.

## 5. Formato de salida esperado

Entrega el roadmap con esta estructura:

### Etapa 1 — Estabilización (criterio de salida: suite verde, contratos documentados, sin regresiones conocidas)
Lista de tareas priorizadas (P0/P1/P2), cada una con: problema (causa raíz, no síntoma), módulos/archivos afectados, criterio de aceptación verificable, y si es bug o deuda de diseño.

### Etapa 2 — Evolución del flujo de presupuestos con IA (criterio de salida: agente guiado por flujo funcionando con datos server-side y trazabilidad persistente)
Desglosa en sub-fases ordenadas por dependencia (p. ej.: modelar dominio canónico → extraer backend/API → modelar catálogo de precios y procedencia → construir el flujo de borrador/edición conversacional → añadir consultas web controladas → interfaz web responsive con autenticación). Cada sub-fase con: objetivo, qué debe existir al terminar, riesgos, y qué decisión pendiente de la sección 6 bloquea empezarla.

### Decisiones pendientes que debes señalar, no resolver por tu cuenta
Para cada punto de la sección "Información que falta decidir" del boceto (fuentes web admisibles, vigencia de precios, campos obligatorios, estructura del catálogo, formato exportable, datos que nunca salen de la infraestructura privada, métricas de éxito, proveedor/modelo de IA definitivo), indica qué opciones razonables existen y qué información necesitas del propietario del producto para cerrar cada una. No la decidas tú.

## 6. Reglas de calidad para tu propio roadmap

- Cada tarea debe ser verificable (test, comando, o criterio observable), no una aspiración.
- No mezcles Etapa 1 y Etapa 2: nada de Etapa 2 puede empezar antes de que Etapa 1 cumpla su criterio de salida, salvo que justifiques explícitamente una excepción.
- No prescribas código todavía; el resultado es un plan, no una implementación.
- Sé explícito sobre supuestos que estás haciendo y sobre cualquier discrepancia entre el boceto y lo que observas en el repo real.
