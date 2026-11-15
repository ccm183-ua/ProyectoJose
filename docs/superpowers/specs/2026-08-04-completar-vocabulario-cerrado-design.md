# Completar la revision del vocabulario cerrado de clasificacion (8 familias pendientes)

## Contexto y motivacion

El 22/07/2026 se reviso con el usuario, ejemplo real a ejemplo real, el
vocabulario cerrado de `_ACTION_SYNONYMS`/`_ELEMENT_SYNONYMS`
(`src/core/historical_partida_features.py`) para tres familias: pintura,
gestion de residuos y fachada. Las decisiones quedaron documentadas en
`docs/criterios-clasificacion-partidas.md` (Decision 1, Decision 2) con su
motivo y su test de regresion. El propio documento deja explicitamente
pendientes de ese mismo tratamiento **ocho familias**: cerrajeria,
impermeabilizacion, demolicion, alicatado, estructura, carpinteria,
albanileria, sustitucion de bajante.

Esa vocabulario incompleto es la causa raiz medida en esta sesion de que:

- `patrones.csv` solo produzca 117 patrones sobre 19.205 lineas historicas
  reales (386 presupuestos `INCLUDED`), con el mayor recorte del embudo en
  lineas atomicas sin `element` extraido (5.317 de 9.124, 58%).
- El importador de XML (`src/core/xml_budget_importer.py`, sesion actual)
  devolviera `sin_evidencia_ia` en 4 de 4 partidas "conocida" de una prueba
  real, incluidas dos de alicatado — el ejemplo concreto: `"DEMOLICION DE
  ALICATADO"` clasifica bien la accion (`demolish`) pero el elemento queda
  vacio porque "alicatado" no esta en `_ELEMENT_SYNONYMS`.

Este documento planifica **retomar y cerrar** esas ocho revisiones
pendientes, con el mismo metodo ya validado, no uno nuevo.

## Alcance

Las ocho familias nombradas arriba, todas en esta ronda. Orden no fijado de
antemano: se propone turno a turno segun el informe de impacto de cada
familia (ver Paso 1 abajo), y lo decide el usuario en ese momento.

**Fuera de alcance de este plan** (explicito, para no arrastrar scope):

- El validador formal del esquema IA mencionado en el roadmap
  (`docs/esquema-partidas-ia.md`) — es otro plan.
- La investigacion del problema de codificacion en `concepto_original`
  (acentos corruptos) detectado en esta sesion y ya anotado como "no
  investigado" en `criterios-clasificacion-partidas.md` desde el 22/07.
- Cualquier cambio estructural a `historical_partida_classifier.py`
  (`MODULE_RULES`, `pick_primary_module`) que no este directamente
  respaldado por una decision documentada de una de las ocho familias.
- Anadir vocabulario para familias o casos no listados en el documento
  original, aunque aparezcan de pasada durante la revision (se anotan como
  candidatos para una ronda futura, no se resuelven aqui).

## El bucle por familia (se repite 8 veces, una por turno, con cierre)

**Paso 1 — Informe de impacto (automatico, solo lectura).**
Consulta sobre `historical_partida` + `historical_partida_feature` filtrada
por la familia en curso (via `execution_module`/clasificacion existente),
agrupando por frase normalizada las lineas **sin ficha completa** (action o
element vacios, o `line_kind` distinto de `atomic`), ordenadas por
frecuencia real de aparicion. Solo lectura, sin escribir nada.

**Paso 2 — Presentacion de ejemplos.**
Se muestran los 5-10 patrones de mayor frecuencia con su texto original
completo (no solo la frase normalizada), agrupados de forma legible.

**Paso 3 — Decision del usuario.**
Para cada patron de ejemplo: accion, elemento, modulo principal (si
aplica), condicion que impida una coincidencia exacta si la hay, y el
motivo — mismo formato que Decision 1 y Decision 2 del documento existente.
Se propone una primera lectura, pero la decision y el motivo final son del
usuario. Si un caso es genuinamente ambiguo, no se fuerza: se anota "sin
decision, revisar mas adelante" y se continua con el resto de la familia.

**Paso 4 — Implementacion.**
Se anaden las entradas acordadas a `_ACTION_SYNONYMS`/`_ELEMENT_SYNONYMS`,
o a `MODULE_RULES` si el problema es de deteccion de modulo en vez de
elemento (como el caso de "tapado" en la Decision 2 ya existente). Un test
de regresion por decision en
`tests/test_historical_partida_classifier.py::TestReviewedHistoricalCases`,
usando el texto real del ejemplo revisado, no un caso inventado.

**Paso 5 — Verificacion medida.**
Se ejecuta `HistoricalBudgetAnalyzer().rebuild_features_and_patterns()`
contra la base real de produccion (con el backup automatico que ya crea
`rebuild_patterns()`) y se compara el numero de patrones y de lineas con
ficha completa antes/despues, solo para esa familia.

**Paso 6 — Cierre.**
Commit de la familia (documento + codigo + tests), y se pasa a proponer la
siguiente familia por impacto medido.

## Documentacion de decisiones

Las decisiones nuevas se anaden a `docs/criterios-clasificacion-partidas.md`
como continuacion de la seccion "Revision humana del histórico real",
numeradas a partir de la Decision 3, con el mismo formato que las dos ya
existentes (expresion habitual, accion, elemento, modulo principal,
condicion que impide coincidencia exacta, motivo, implementacion). No se
crea un documento nuevo por familia.

## Red de seguridad

- Tras cada commit de familia se corre la suite completa de tests (no solo
  los nuevos), para detectar regresiones cruzadas — p. ej. que una palabra
  clave nueva de alicatado capture sin querer texto que antes se
  clasificaba correctamente en otra familia.
- Si el numero total de patrones **baja** tras una familia (en vez de subir
  o mantenerse), se para antes de comitear y se revisa con el usuario en
  vez de darlo por bueno porque esa familia concreta mejoro.
- No hay una meta numerica de "X patrones mas" fijada de antemano. El
  criterio de cierre por familia es: informe de impacto revisado con el
  usuario (aunque la decision final sea no tocar esa familia), decisiones
  documentadas, tests anadidos, commit propio.

## Criterio de cierre del conjunto

Las ocho revisiones quedan cerradas cuando cada una tiene su informe de
impacto revisado, sus decisiones documentadas (incluyendo las que se
dejaron "sin decision" explicitamente), sus tests y su commit. Al terminar
la octava, un resumen unico con el antes/despues total de patrones y
lineas con ficha completa sobre la base real, para dejar constancia medida
del efecto conjunto.

## Testing

- Un test de regresion por decision documentada, con texto real del
  histórico (no sintetico), en `TestReviewedHistoricalCases`.
- Suite completa despues de cada commit de familia (actualmente 811
  passed, excluyendo `tests/api` por falta de `fastapi`/`uvicorn` en el
  venv — gap de entorno preexistente, no relacionado con este plan).
- Verificacion contra la base de datos real de produccion en cada Paso 5,
  no solo contra fixtures de test.
