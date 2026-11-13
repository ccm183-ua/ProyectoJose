# Decisiones pendientes

> Actualizado el 2026-11-11. Solo recoge lo que **sigue abierto**. Las
> decisiones ya tomadas el 2026-11-11 están documentadas en:
> - Vocabulario (Decisiones 30-37 y abreviaturas):
>   [`criterios-clasificacion-partidas.md`](criterios-clasificacion-partidas.md).
> - Retención de backups (D1), `datos.db` antiguo (D2) y finalización al
>   guardar el Excel (E1): mensajes de commit de la rama `fix/bugs-revision`.
>
> Las cifras están medidas sobre una **copia** de la base de datos real.

---

## 1. Subir `integracion-noviembre` a GitHub

- **Certificado arreglado (2026-11-11)**: el error SSL lo causaba el escudo
  web de Norton Antivirus, que firma las conexiones HTTPS con su propia raíz.
  git usa ahora el almacén de Windows (`http.sslBackend schannel`) y pip se ha
  actualizado a una versión que también lo usa.
- Al conectar apareció trabajo de septiembre que no estaba en este equipo (51
  commits en `origin/prueba-claude`), y los 13 commits de agosto de este
  equipo nunca se habían subido. Todo está integrado en la rama
  `integracion-noviembre`: suite completa en verde (incluidos los tests de la
  API) y los mismos 137 patrones sobre una copia de la BD real.
- **Recomendación**: hacer las pruebas manuales de abajo y, después, subir
  `integracion-noviembre` y fusionarla en `prueba-claude` (por pull request,
  como en septiembre).

## 2. Administraciones del `datos.db` antiguo

- El `datos.db` de la raíz del proyecto (febrero) se ha movido a
  `Documents/CubiApp/legacy/datos_raiz_proyecto_2026-02-27.db`, no borrado:
  contenía 3 administraciones que **no** están en la base de datos actual (que
  tiene 0): "MS FINCAS", "DIESAN" y "C.P. GABRIEL MIRÓ, 24". Las comunidades y
  el contacto que contenía eran datos de prueba.
- **Opciones**: (a) darlas de alta de nuevo a mano en la app; (b) importarlas
  con un script; (c) dejarlo así.

## 3. Vocabulario que ha quedado a la vista

- **"chapa" en cerrajería**: "Rampa de chapa lagrimada antideslizante" estaba
  en estructura solo por "garaje"; al corregirlo se queda sin módulo.
- **"muro", "solera", "losa", "cimentación"**: no se han evaluado como señales
  de estructura (de las partidas que dejaron de ser estructura, 46 contienen
  "muro", 29 "solera", 24 "losa", 9 "cimentación").
- **Recomendación**: revisarlas con el mismo método (muestra real → decisión →
  test → medir patrones) cuando haya tiempo; ninguna es urgente.
- **Biblioteca de partidas**: medir con el uso real si los grupos por concepto
  normalizado exacto se quedan cortos (variantes de redacción de la misma
  partida) antes de diseñar la mejora 2.

## 3b. Carpetas de obra a revisar (planificación de obras, 2026-11-13)

- **Números de proyecto repetidos** (no se pueden planificar hasta limpiarlos):
  109-26 (PRESUPUESTADO y TERMINADO), 127-25 (EJECUTAR y TERMINADO), 196-26
  (dos obras distintas en PRESUPUESTADO y PTE. PRESUPUESTAR), 228-24 (dos
  carpetas en TERMINADO) y 78-26 (una es "Prueba (Se puede borrar)").
  Probablemente carpetas copiadas en vez de movidas.
- **Obras de EJECUTAR con la fecha ya pasada en el nombre**: 114-26 (13/07),
  208-26 (25/06), 30-26 (julio) y 48-25 (19/05). Si ya se hicieron, conviene
  moverlas a EJECUTANDO o TERMINADO.

## 4. Seguridad de la API (H4)

- Pendiente: límite de intentos de login, rutas de salida arbitrarias en las
  exportaciones, cookie sin `secure`, email autorizado fijo en el código.
  Requiere instalar `fastapi` (bloqueado por el mismo error SSL).
- **Recomendación**: aparcarlo mientras la app siga siendo solo de escritorio.

## 5. Hallazgos de la revisión del trabajo de septiembre (sin corregir)

Ya corregidos en `integracion-noviembre`: descartar un borrador que había
sobrescrito otro Excel, la vigilancia del Excel tras cerrar el dashboard,
direcciones al principio del texto en el paquete de contexto y "No" por
defecto en las confirmaciones de borrado. Quedan:

| Gravedad | Dónde | Qué pasa |
|---|---|---|
| Alta | `budget_orchestrator._gap_resolved` | Si la IA rellena solo uno de varios huecos, todos se dan por resueltos y el resto se pierde sin aviso. Arreglarlo exige que el prompt de huecos devuelva el módulo de cada partida. |
| Media | `budget_orchestrator` + `voice_budget_dialog` | Resultado "parcial" sin módulos pendientes: "Reintentar" devuelve lo mismo y vuelve a preguntar. El reintento no tiene límite (el commit decía "acotado"). |
| Media | `export_context_pack._publish_files` | La publicación no es atómica entre ficheros; en Windows `os.replace` falla si un fichero está abierto y el rollback puede dejar una mezcla. Nombres `.tmp`/`.bak` fijos: dos publicaciones a la vez se pisan. |
| Media | `historical_analysis_results_dialog` (incluir/aplicar decisiones) | Si falla algo después de aprobar, no se reconstruyen patrones ni se publica el paquete. |
| Media | `budget_service.create_budget` | Si falla la plantilla queda una carpeta de obra vacía; el error de `registrar_presupuesto` se ignora. |
| Media | `budget_dashboard` (regeneración de cabeceras por lotes) | Síncrona en el hilo de la UI; ignora el resultado de `finalize_budget` y puede vaciar cliente/calle si la relación no los tiene. |
| Media | `historical_memory_dashboard` (descripciones con IA) | Hilos sin `_run_busy`: otras operaciones de escritura pueden ejecutarse a la vez; el resultado puede llegar con el diálogo cerrado. |
| Baja | `historical_memory_dashboard._reload` | El diagnóstico de integridad y los KPI siguen en el hilo de la UI tras cada operación (H10 a medias). |

El commit `8dfd117` ("wip: validacion completa pendiente antes de integrar")
está vacío.

---

## Pruebas manuales pendientes (no son decisiones, pero bloquean la fusión)

1. Generar partidas con DeepSeek (el alias retirado `deepseek-chat` ya se
   migra solo a `deepseek-v4-flash`).
2. Crear un presupuesto con 2 partidas y otro con 8, y regenerar uno: comprobar
   el pie de totales y las cabeceras de página con Excel.
3. Regenerar desde la plantilla los presupuestos 166-26 y 168-26 (generados con
   el pie roto).
4. Abrir un Excel desde el dashboard, guardarlo y comprobar que pregunta antes
   de finalizar.
