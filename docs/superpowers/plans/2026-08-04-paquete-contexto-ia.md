# Paquete de contexto para presupuestos con IA — Implementation Plan

**Goal:** Que la aplicación exporte automáticamente, a una carpeta sincronizada, un paquete de contexto con el que Claude (aplicación de consumo, con una skill personalizada) pueda redactar borradores de presupuesto **sin poder inventar precios, módulos, unidades ni cantidades**.

**Architecture:** Un exportador determinista y de solo lectura vuelca cuatro ficheros desde SQLite. El paquete exportado **es** el vocabulario permitido: exportador y (más adelante) validador leen la misma fuente, así que no pueden desincronizarse. Claude queda fuera del sistema; el único contrato es el esquema del fichero de salida. La importación de ese fichero queda **fuera del alcance de este plan** — se aborda solo si la puerta de evaluación pasa.

**Tech Stack:** Python 3.11, SQLite, PySide6, `pytest`. Sin dependencias nuevas.

## Global Constraints

- El exportador **nunca** escribe en la base de datos. Conexión en modo `ro`, como `audit_historical_memory.py`.
- Ningún fichero del paquete contiene datos de cliente: ni nombres de comunidad, ni direcciones, ni CIF, ni teléfonos.
- Solo se exportan partidas de presupuestos con `learning_status='INCLUDED'` y `precio_unitario > 0`.
- **El esquema de salida no tiene campo de precio.** La imposibilidad de que el modelo fije precios es estructural, no una instrucción del prompt.
- El exportador es determinista: la misma base produce el mismo paquete, byte a byte (orden estable, sin marcas de tiempo dentro de los ficheros de datos).
- Las reglas anti-alucinación son responsabilidad del esquema y del futuro validador. La skill orienta; el validador decide.

## Decisiones cerradas (2026-08-04)

| Decisión | Valor |
|---|---|
| Quién fija los precios | La aplicación, cruzando contra evidencia histórica. Claude nunca. |
| Contenido del paquete | Patrones evidenciados + repertorio completo + vocabulario + estructura de ejemplo |
| Partidas fuera del repertorio | Permitidas, con marca obligatoria de "sin precedente histórico" |
| Cantidades sin medida | Claude pregunta; si no hay dato, estado explícito `pendiente` |
| Formato de intercambio | XML |
| Catálogo `price_reference` | Fuera de alcance — hoy no tiene datos aprobados |

## Datos verificados de partida (2026-08-04, sobre `Documents/CubiApp/datos.db`)

- `suggested_partida_pattern`: **33 patrones**, 32 conceptos distintos → precio evidenciado.
- Partidas de presupuestos `INCLUDED` con precio: **226 líneas, 179 conceptos distintos** → repertorio.
  - 123 atómicas, 91 compuestas, 8 desconocidas, 4 auxiliares.
- Tamaño de presupuesto real: media 4,2 partidas (mín. 1, máx. 67).
- Rastreo de datos personales en el texto de esas 226 líneas: 4 con vía, 1 con "comunidad", 7 con `nº`+dígitos, 13 con número de 5 cifras (mayoría falsos positivos: importes y medidas), **0 con CIF/NIF**.

## Estructura de archivos

- Crear: `scripts/export_context_pack.py` — exportador y filtro de datos personales.
- Crear: `docs/esquema-partidas-ia.md` — el contrato del fichero de salida.
- Crear: `docs/skill-presupuestos/SKILL.md` — la skill para Claude.
- Modificar: `src/core/settings.py` — nueva ruta por defecto del paquete.
- Modificar: `src/core/historical_budget_analyzer.py` — disparo tras reconstruir patrones.
- Modificar: `src/gui/main_frame.py` — acción manual de exportación.
- Crear tests: `tests/test_export_context_pack.py`.

---

## Task 1: Filtro de datos personales

**Files:**
- Create: `scripts/export_context_pack.py`
- Test: `tests/test_export_context_pack.py`

**Interfaces:**
- `scrub_text(text: str) -> tuple[str, list[str]]` — devuelve el texto limpio y la lista de razones por las que se tocó. Devolver las razones permite auditar qué se eliminó, en vez de confiar en que el filtro acertó.

- [ ] **Step 1: Escribir los tests del filtro primero**

Casos mínimos, tomados de las señales reales encontradas en la base:

```python
assert scrub_text("Reparacion de fachada en C/ Mayor 12")[0] == "Reparacion de fachada"
assert scrub_text("Pintura Comunidad de Propietarios Los Olivos")[0] == "Pintura"
# No debe romper conceptos legitimos que contienen numeros o palabras parecidas:
assert scrub_text("Suministro de 12 ud de bajante")[0] == "Suministro de 12 ud de bajante"
assert scrub_text("Mortero R4 espesor 15 mm")[0] == "Mortero R4 espesor 15 mm"
```

El segundo bloque importa tanto como el primero: un filtro que mutila conceptos legítimos degrada el paquete en silencio.

- [ ] **Step 2: Ejecutar y confirmar el fallo**

- [ ] **Step 3: Implementar el filtro**

Eliminar por patrón: vía (`C/`, `Calle`, `Avda`, `Avenida`, `Plaza`, `Paseo`, `Urb.`) y su cola hasta fin de texto o separador; `Comunidad de Propietarios X`; CIF/NIF. **No** eliminar números sueltos ni códigos de cinco cifras: en este dominio son casi siempre importes o medidas, y borrarlos destruye información útil.

- [ ] **Step 4: Pasar el filtro sobre las 226 líneas reales y revisar la salida a mano**

Ejecutar contra una copia de solo lectura y volcar solo las líneas que el filtro modifica. Revisarlas una vez: confirmar que lo eliminado sobraba y que nada legítimo se perdió. Ajustar los patrones si hace falta. Este paso es de aceptación humana; no se automatiza.

---

## Task 2: Exportar los cuatro ficheros

**Files:**
- Modify: `scripts/export_context_pack.py`
- Test: `tests/test_export_context_pack.py`

**Interfaces:**
- `export_context_pack(db_path: str, out_dir: str) -> dict` — escribe los ficheros y devuelve un resumen con los recuentos por fichero.

- [ ] **Step 1: `patrones.csv` — precio evidenciado**

Columnas: `concepto`, `modulo`, `unidad`, `precio_mediana`, `precio_min`, `precio_max`, `frecuencia`, `presupuestos_distintos`, `calidad_evidencia`. Origen: `suggested_partida_pattern`. Orden estable por `(modulo, concepto)`.

- [ ] **Step 2: `repertorio.csv` — cómo se redacta y qué se cobró**

Columnas: `concepto`, `unidad`, `precio_unitario`, `tipo_linea`, `modulo_principal`. Origen: partidas `INCLUDED` con precio, pasadas por `scrub_text`. Incluye las compuestas: son líneas reales que se facturaron, y su valor aquí es de redacción y alcance, no de precio evidenciado. Orden estable por `(concepto, unidad)`.

- [ ] **Step 3: `vocabulario.md` — las listas cerradas**

Módulos de ejecución (`execution_module`), acciones y elementos del vocabulario cerrado (`historical_partida_features`), unidades observadas, y el criterio de línea atómica frente a compuesta. Este fichero es la fuente de verdad de lo que el validador aceptará más adelante.

- [ ] **Step 4: `estructura.md` — un presupuesto real anonimizado**

Un `historical_budget` `INCLUDED` representativo (preferir uno con varias partidas, no de una línea), con sus partidas en orden, pasado por el filtro. Muestra el orden de ejecución de obra y cómo se agrupa.

- [ ] **Step 5: Tests del exportador**

```python
summary = export_context_pack(db_path, out_dir)
assert summary["patrones"] == 33
assert summary["repertorio"] > 0
# Determinismo: dos ejecuciones producen ficheros identicos
assert hash_dir(out_dir_a) == hash_dir(out_dir_b)
# Ningun fichero contiene datos de cliente
for f in Path(out_dir).iterdir():
    assert not RE_DIRECCION.search(f.read_text(encoding="utf-8"))
```

Los recuentos exactos se fijan contra una base sembrada por el test, no contra producción.

---

## Task 3: Exportación automática y manual

**Files:**
- Modify: `src/core/settings.py`
- Modify: `src/core/historical_budget_analyzer.py`
- Modify: `src/gui/main_frame.py`
- Test: `tests/test_export_context_pack.py`

- [ ] **Step 1: Ruta configurable**

Añadir `PATH_CONTEXT_PACK` a `Settings`, siguiendo el patrón de `PATH_HISTORICAL_FOLDER`. Sin ruta configurada, la exportación automática no hace nada (no adivinar una carpeta de sincronización).

- [ ] **Step 2: Disparo tras reconstruir patrones**

En `analyze_files()`, después de `HistoricalPatternBuilder().rebuild_patterns()`, exportar si hay ruta configurada. Es el momento exacto en que el conocimiento cambia; no hace falta ningún planificador. Un fallo al exportar **no** puede tumbar el análisis: capturar y reflejarlo en el resumen.

- [ ] **Step 3: Acción manual en el menú**

Entrada junto a "Analizar presupuestos terminados". Al terminar, informar de la ruta y los recuentos.

- [ ] **Step 4: Prueba del disparo automático**

Verificar que analizar un Excel deja el paquete actualizado, y que sin ruta configurada no se escribe nada ni se lanza error.

---

## Task 4: El esquema de salida (el contrato)

**Files:**
- Create: `docs/esquema-partidas-ia.md`

- [ ] **Step 1: Definir el esquema**

```xml
<presupuesto>
  <partida>
    <concepto>Reparacion de revoco de fachada con mortero R4</concepto>
    <unidad>m2</unidad>
    <cantidad estado="conocida">120</cantidad>
    <modulo>fachada</modulo>
    <nueva>false</nueva>
  </partida>
  <partida>
    <concepto>Sellado de junta estructural</concepto>
    <unidad>ml</unidad>
    <cantidad estado="pendiente"/>
    <modulo>fachada</modulo>
    <nueva>true</nueva>
  </partida>
</presupuesto>
```

Reglas que el esquema impone por construcción:

- **No existe elemento de precio.** No hay forma de expresarlo.
- `cantidad` lleva `estado` obligatorio: `conocida` (con valor) o `pendiente` (sin valor). No hay tercer estado — una cantidad estimada no se puede representar.
- `modulo` debe pertenecer a la lista de `vocabulario.md`.
- `unidad` debe pertenecer a la lista observada en el repertorio.
- `nueva` es obligatorio: `true` marca una partida sin precedente en el repertorio.

- [ ] **Step 2: Documentar qué hará el validador con cada violación**

Módulo o unidad fuera de lista → rechazo de esa partida, con el motivo. Falta `nueva` o falta `estado` → rechazo. Elemento desconocido → rechazo. Se documenta ahora aunque el validador se implemente después, para que la skill se escriba contra un contrato firme.

---

## Task 5: La skill

**Files:**
- Create: `docs/skill-presupuestos/SKILL.md`

- [ ] **Step 1: Escribir la skill contra el esquema**

Debe cubrir: cómo leer los cuatro ficheros y qué papel tiene cada uno; que el repertorio sirve para saber qué partidas existen y cómo se redactan, **no** para fijar precios; que preguntar por una medida que falta es preferible a estimarla; que una partida sin precedente se marca `nueva="true"` siempre; y el esquema exacto de salida.

Redactar en positivo y sin gritar: describir el comportamiento correcto en vez de acumular prohibiciones en mayúsculas. Las prohibiciones de verdad ya están en el esquema.

- [ ] **Step 2: Prueba manual del ciclo completo**

Subir el paquete y la skill a Claude, describir tres o cuatro obras conocidas y comprobar la salida contra el esquema a mano.

---

## Puerta de evaluación (criterio de salida de este plan)

No se empieza el validador ni el importador hasta que, sobre obras reales conocidas:

- [ ] Los borradores incluyen las partidas que un presupuestista habría puesto, sin olvidos evidentes.
- [ ] Los conceptos se parecen a cómo se redacta de verdad, no a lenguaje genérico de construcción.
- [ ] Ninguna salida trae precios (el esquema lo impide; se verifica que en la práctica se respeta).
- [ ] Las partidas sin precedente vienen marcadas `nueva="true"` de forma fiable.
- [ ] Las cantidades no dadas salen como `pendiente`, no inventadas.

Si algo falla, se corrige el **paquete o la skill** — que es barato — antes de escribir una línea del importador.

## Fuera de alcance

Validador, importador, cruce de precios contra evidencia, `price_reference` (H5), edición conversacional (H7), consulta web (H8) e interfaz web (H9). El importador reutilizará `extract_partida_features` + `compare_partida_features` para el precio y `CombinedPartidasReviewDialog` para la revisión — ambos ya existen y ya muestran procedencia — pero eso es otro plan.
