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

## 4. Seguridad de la API (H4)

- Pendiente: límite de intentos de login, rutas de salida arbitrarias en las
  exportaciones, cookie sin `secure`, email autorizado fijo en el código.
  Requiere instalar `fastapi` (bloqueado por el mismo error SSL).
- **Recomendación**: aparcarlo mientras la app siga siendo solo de escritorio.

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
