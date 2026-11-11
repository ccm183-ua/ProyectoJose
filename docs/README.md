# Documentación de cubiApp

Índice de toda la documentación, con el estado de cada documento a 2026-11-11.
Si añades un documento nuevo, apúntalo aquí.

## Para decidir ahora

| Documento | Para qué sirve |
|---|---|
| [`decisiones-pendientes.md`](decisiones-pendientes.md) | **Todas las decisiones abiertas**, con datos medidos, opciones y recomendación. |

## Referencia (vigente)

| Documento | Para qué sirve |
|---|---|
| [`../README.md`](../README.md) | Instalación, arranque y estructura general. |
| [`../CONTEXT.md`](../CONTEXT.md) | Fuentes de verdad: quién es dueño de cada tabla y qué se puede reconstruir. |
| [`adr/0001-fuentes-de-verdad.md`](adr/0001-fuentes-de-verdad.md) | Decisión: qué almacén manda en cada entidad. |
| [`adr/0002-excel-como-adaptador.md`](adr/0002-excel-como-adaptador.md) | Decisión: Excel como adaptador de entrada/salida. |
| [`criterios-clasificacion-partidas.md`](criterios-clasificacion-partidas.md) | Vocabulario cerrado y todas las decisiones de clasificación de partidas. |
| [`esquema-partidas-ia.md`](esquema-partidas-ia.md) | Contrato del XML de partidas que redacta Claude. |
| [`skill-presupuestos/SKILL.md`](skill-presupuestos/SKILL.md) | Skill para redactar presupuestos con Claude a partir del paquete de contexto. |

## Hoja de ruta

| Documento | Estado |
|---|---|
| [`ROADMAP_ESTABILIZACION_Y_EVOLUCION_IA.md`](ROADMAP_ESTABILIZACION_Y_EVOLUCION_IA.md) | **Vigente.** H0–H2 hechos (falta el gate manual de Excel). H3–H5 a medias (dominio canónico, API, catálogo de precios: sin interfaz). H6–H9 sin empezar. La versión web (H9) está aparcada: se sigue como app de escritorio. |

## Planes pendientes

| Documento | Estado |
|---|---|
| [`planes/dashboard-filtros-estadisticas.md`](planes/dashboard-filtros-estadisticas.md) | A medias: hay datos, falta toda la interfaz. |
| [`planes/sugerir-comunidad.md`](planes/sugerir-comunidad.md) | A medias (mínimo): solo el prefill de dirección. |
| [`superpowers/plans/2026-07-22-historico-estructurado-y-cruce-fiable.md`](superpowers/plans/2026-07-22-historico-estructurado-y-cruce-fiable.md) | 54/63 pasos. |
| [`superpowers/plans/2026-07-22-fixes-historico-evidenciado.md`](superpowers/plans/2026-07-22-fixes-historico-evidenciado.md) | 30/35 pasos; faltan E2E y aceptación manual. |
| [`superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md`](superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md) | 7/8 familias revisadas; falta `estructura`. |

## Pruebas manuales

| Documento | Estado |
|---|---|
| [`checklists/manual-excel.md`](checklists/manual-excel.md) | Sin ejecutar. Es el gate de cierre de la Etapa 1. |
| [`checklists/validacion-presupuestos.md`](checklists/validacion-presupuestos.md) | Sin ejecutar. |

## Archivo (hecho, superado u obsoleto)

Se conservan como historia; cada uno lleva una cabecera con su estado.

| Documento | Estado |
|---|---|
| [`archivo/plan-historical-intelligence.md`](archivo/plan-historical-intelligence.md) | Hecho. |
| [`archivo/plan-ia-mejora-global.md`](archivo/plan-ia-mejora-global.md) | Superado por el ROADMAP. |
| [`archivo/plan-mejora-plantillas-ia.md`](archivo/plan-mejora-plantillas-ia.md) | Obsoleto (GUI wxPython). |
| [`archivo/boceto-estado-y-vision.md`](archivo/boceto-estado-y-vision.md) | Insumo del ROADMAP. |
| [`archivo/prompt-maestro-roadmap.md`](archivo/prompt-maestro-roadmap.md) | Insumo del ROADMAP. |
| [`archivo/handoff-sesion-h0-h2.md`](archivo/handoff-sesion-h0-h2.md) | Histórico. |
| `superpowers/plans/2026-08-04-paquete-contexto-ia.md`, `superpowers/specs/*` | Hechos. |

## Ramas del repositorio

| Rama | Estado |
|---|---|
| `prueba-claude` | Rama de trabajo principal. |
| `fix/bugs-revision` | Arreglos de la revisión de noviembre de 2026 (pendiente de fusionar en `prueba-claude`). |
| `Develop`, `main`, `sistema_Aprendizaje_Presupuestos`, `Funcionalidades-(AbrirPresupuestoExistente)` | Ya contenidas en `prueba-claude`. |
| `IA-BuscadorPlantillasPresupuestos` | Su contenido ya está en `prueba-claude` (reimplementado). |
| `Plantillas-IA` | Botones de plantillas para la GUI wxPython; no se fusionó (habría que rehacerlo en Qt). |
| `Interfaz` | Prototipo web (plantilla HTML de 4.105 ficheros); no se fusionó. |
