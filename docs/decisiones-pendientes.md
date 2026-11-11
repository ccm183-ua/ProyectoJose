# Decisiones pendientes

> Preparado el 2026-11-11 tras la revisión general y los arreglos de la rama
> `fix/bugs-revision`. Todas las cifras están medidas sobre una **copia** de la
> base de datos real (19.205 partidas; 6.799 conceptos distintos), nunca sobre
> la original. Cuando se decida algo, se mueve a
> [`criterios-clasificacion-partidas.md`](criterios-clasificacion-partidas.md)
> (vocabulario) o al documento que corresponda, y se borra de aquí.

Cómo leer las cifras:
- **Sin acción hoy**: partidas a las que el extractor no asigna ninguna acción
  (`repair`, `demolish`...). Sin acción, una partida no es apta para precio y
  no alimenta patrones.
- **INCLUDED**: de esas, cuántas son de presupuestos aprobados para
  aprendizaje (las únicas que generan patrones).

---

## A. Vocabulario de acciones

### A1. "reposición" / "reponer": ¿cuenta como reparación?

- **Contexto**: hasta ahora "reposición" se convertía en "reparación" por un
  fallo de la expansión de abreviaturas (prefijo "rep"), ya corregido. Al
  corregirlo, "reposición" se queda sin acción.
- **Datos**: 25 partidas sin acción hoy (1 INCLUDED). Ejemplos reales:
  "Reposición de gresite desprendido", "Retirada y reposición de elementos de
  fachada", "Reposición monocapa fachada" (este último era un patrón de 42 €/m2
  que se pierde).
- **Opciones**: (a) `repair`; (b) `install` (se pone una pieza nueva);
  (c) sin acción.
- **Recomendación**: **(a) `repair`**. En los ejemplos se repone lo dañado en
  la misma obra de reparación, y era el comportamiento de facto hasta ahora.

### A2. "formación de…": ¿acción propia?

- **Contexto**: "formación" recibía `repair` por un falso positivo
  ("p**reparación**" contiene "reparación"), ya corregido.
- **Datos**: 276 partidas sin acción hoy (11 INCLUDED). Ejemplos: "Formación de
  rampa y muro de bloque", "Formación de base de mostrador de pladur",
  "Formación en fachada de capa de acabado…" (patrón de albañilería de 65,75 €/m2
  que se pierde).
- **Opciones**: (a) nueva acción `build` (construir/ejecutar); (b) `install`;
  (c) sin acción.
- **Recomendación**: **(a) `build`**. "Formación" describe ejecutar un elemento
  de obra nueva, no instalar una pieza ni reparar.

### A3. "tirar" como sinónimo de `demolish`

- **Contexto**: se descartó en la Decisión 3 porque "tirar" casaba dentro de
  "re**tirar**". Desde que los keywords casan desde inicio de palabra, esa
  colisión ya no existe.
- **Datos**: 14 partidas sin acción hoy (3 INCLUDED). "Tirar tabiques
  existentes…", "Tirar techo de escayola…", "Tirar muebles existentes…".
- **Recomendación**: **sí**, añadir.

### A4. "saneado" / "repaso" como `repair`

- **Datos**: 5 y 3 partidas sin acción hoy (0 INCLUDED). "Saneado de fisuras en
  escayola", "Repaso de grietas y saneado de la escalera".
- **Recomendación**: **sí**, impacto bajo pero sin riesgo aparente.

### A5. "repicado" como demolición

- **Datos**: 0 partidas sin acción (todas tienen ya otra acción).
- **Recomendación**: **no hace falta**; se cierra sin cambio.

---

## B. Familia `estructura` (la única de las 8 sin revisar)

Solo 23 partidas atómicas INCLUDED y 5 sin ficha completa: es la familia más
pequeña. El problema real está en sus keywords:

| Keyword | Aparece en | Única señal de estructura en |
|---|---:|---:|
| `hormigon` | 925 | 498 |
| `estructura` | 883 | 460 |
| `refuerzo` | 178 | 113 |
| `garaje` | 114 | 91 |
| `pilar` | 342 | 76 |
| `viga` | 194 | 73 |
| `parking` | 15 | 8 |
| `zuncho` | 11 | 3 |
| `atado` | 8 | 1 |
| `vigas`, `pilares`, `estructural`, `dados` | — | 0 |

### B1. Quitar "garaje" y "parking"

- Son lugares, no elementos estructurales. Muestra de partidas donde son la
  única señal: "Pintura puerta vehículos garaje", "Puerta cortafuegos en
  parking", "Sust. chapa ondulada techo parking", "Sellado de junta de
  dilatación pavimento".
- **Recomendación**: **quitar ambos** (99 partidas dejan de marcarse como
  estructura).

### B2. "hormigón" y "refuerzo" como única señal

- Mezcla de aciertos ("Reparación de frente de forjado de hormigón armado",
  "Saneado frente forjado… picado de hormigón") y falsos ("Pintura al silicato…
  sobre hormigón", "Refuerzo en rejilla suelta al final de rampa",
  "Levantado de bolardos… picado").
- **Opciones**: (a) mantener; (b) exigir otra señal estructural (forjado, viga,
  pilar…) para que cuenten; (c) quitar.
- **Recomendación**: **(b)**, pero es la decisión más delicada: conviene ver una
  muestra más amplia antes. Si prefieres no complicarlo, (a).

### B3. Plurales redundantes ("vigas", "pilares", "estructural", "dados")

- Nunca son la única señal (los casan ya "viga", "pilar", "estructura",
  "dado" desde inicio de palabra) y cuentan dos veces, inflando la confianza
  del módulo (mismo caso que "fachadas" en la familia fachada).
- **Recomendación**: **quitarlos**.

### B4. "entrevigado"

- 1 partida. **Recomendación**: añadir como keyword de estructura.

---

## C. Expansión de abreviaturas

### C1. "impermeable(s)" e "Impermor" → impermeabilización

- **Contexto**: la expansión antigua ya las llevaba a impermeabilización. Al
  corregirla se han mantenido de forma explícita para no cambiar resultados
  (58 + 4 partidas).
- **Recomendación**: **confirmar** que se queda así.

---

## D. Datos y mantenimiento

### D1. Retención de backups de la base de datos

- **Datos**: 89 copias, **1,2 GB** en `Documents/CubiApp/backups`. 64 son
  "antes de reconstruir patrones", 24 "antes de analizar un lote" y 1 de
  migración. 72 son de agosto. Nunca se purgan (la función `prune_old_backups`
  existe pero nadie la llama).
- **Opciones**: (a) guardar las últimas N (p. ej. 15) y purgar al crear una
  nueva; (b) además, conservar siempre la de migración y la de antes del
  borrado total; (c) no purgar nunca.
- **Recomendación**: **(b) con N = 15** (≈ 450 MB).

### D2. `datos.db` antiguo en la raíz del proyecto

- 280 KB, de febrero. Solo se usaría como *fallback* si la base de datos de
  `Documents/CubiApp` estuviera vacía. Está fuera de git.
- **Recomendación**: **borrarlo** (o moverlo a la carpeta de backups).

### D3. Reconstruir los patrones en la base de datos real

- Necesario para que los arreglos del clasificador y del normalizador lleguen a
  las sugerencias. Hace backup antes.
- **Recomendación**: hacerlo **después** de decidir los bloques A y B, para
  reconstruir una sola vez.

---

## E. Producto

### E1. Finalización automática a los 6 minutos

- Hoy, 6 minutos después de abrir un Excel desde el dashboard, si su fecha de
  modificación cambió, la app lo finaliza (Excel + SQLite) sin preguntar.
- **Opciones**: (a) dejarlo así; (b) preguntar antes de finalizar; (c) solo
  refrescar la caché y finalizar a mano.
- **Recomendación**: **(b)**.

### E2. Fusionar `fix/bugs-revision` en `prueba-claude` y subir a GitHub

- 17 commits; 879 tests (39 retirados que probaban código muerto), todos en
  verde. El push está bloqueado por el error de certificado SSL de este equipo
  (afecta también a `pip`).
- **Recomendación**: fusionar cuando hayas probado la app; arreglar el
  certificado para poder subir y para instalar `fastapi` (tests de la API).

### E3. Seguridad de la API (H4)

- Pendiente: límite de intentos de login, rutas de salida arbitrarias en
  exportaciones, cookie sin `secure`, email autorizado fijo en el código.
- **Recomendación**: aparcarlo mientras la app siga siendo solo de escritorio.
