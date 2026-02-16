# Plan de Mejora del Sistema de Plantillas para IA — cubiApp

## Contexto del Proyecto

**cubiApp** es una aplicación de escritorio (Python + wxPython) para gestión de presupuestos de construcción. Utiliza Google Gemini para generar partidas presupuestarias, apoyándose en un sistema de **plantillas** que proporcionan contexto y partidas de referencia a la IA.

### Objetivo de este plan

Mejorar el sistema de plantillas para la IA sin romper el funcionamiento actual. Cada tarea está clasificada con un **sistema de semáforo** que indica el nivel de riesgo:

- 🟢 **VERDE** — Riesgo bajo. Funcionalidad nueva o aditiva. No toca código existente o lo toca mínimamente. Se puede implementar y probar de forma aislada.
- 🟡 **AMARILLO** — Riesgo medio. Modifica código existente pero con impacto acotado. Requiere actualizar tests. Probar bien antes de avanzar.
- 🔴 **ROJO** — Riesgo alto. Modifica flujos críticos (generación IA, persistencia de datos). Requiere tests exhaustivos y validación manual.

---

## Arquitectura Actual (NO modificar estos contratos)

### Archivos clave y sus responsabilidades

| Archivo | Rol | Contrato que NO debe romperse |
|---------|-----|-------------------------------|
| `src/data/work_types.json` | Plantillas predefinidas (6) | Formato JSON: `{"plantillas": [{nombre, categoria, descripcion, contexto_ia, partidas_base: [{concepto, unidad, precio_ref}]}]}` |
| `src/core/custom_templates.py` | Persistencia de plantillas personalizadas en `~/.cubiapp/custom_templates.json` | Métodos públicos: `load_all()`, `save_all()`, `add()`, `remove()`, `get_by_name()`, `count()` |
| `src/core/work_type_catalog.py` | Catálogo unificado (predefinidas + personalizadas) | Métodos públicos: `get_all()`, `get_all_names()`, `get_predefined_names()`, `get_custom_names()`, `get_by_name()`, `add_custom()`, `remove_custom()` |
| `src/core/prompt_builder.py` | Construye el prompt para Gemini | Dos caminos: A (con plantilla) y B (sin plantilla). Usa `contexto_ia` y `partidas_base` |
| `src/core/budget_generator.py` | Orquesta la generación: IA → fallback offline | Método `generate()` devuelve `{partidas, error, source}` |
| `src/core/ai_service.py` | Llamada a Google Gemini con fallback entre modelos | Método `generate_partidas(prompt)` devuelve `(partidas, error)` |
| `src/gui/template_manager_dialog.py` | GUI de gestión de plantillas | Funciones: ver, añadir desde Excel, eliminar personalizadas |
| `src/gui/ai_budget_dialog_wx.py` | GUI de generación de partidas con IA | Funciones: tipo obra, descripción, selección plantilla, generar |
| `src/core/excel_partidas_extractor.py` | Extrae partidas de un Excel existente | Método `extract(file_path)` devuelve lista de partidas |

### Formato de una plantilla (esquema obligatorio)

```json
{
  "nombre": "string (identificador único, obligatorio)",
  "categoria": "string (clasificación temática)",
  "descripcion": "string (descripción legible para humanos)",
  "contexto_ia": "string (CRÍTICO: texto que se inyecta en el prompt de Gemini)",
  "partidas_base": [
    {
      "concepto": "string (descripción de la partida)",
      "unidad": "string (m2, ml, ud, kg...)",
      "precio_ref": "number (precio de referencia en euros, > 0)"
    }
  ]
}
```

Las plantillas personalizadas añaden además: `"personalizada": true`

### Tests existentes que DEBEN seguir pasando

- `tests/test_work_type_catalog.py` — Carga, esquema, búsqueda por nombre
- `tests/test_custom_templates.py` — CRUD de plantillas, persistencia, catálogo unificado, extracción Excel
- `tests/test_prompt_builder.py` — Construcción de prompt con/sin plantilla, contenido del prompt

**REGLA DE ORO**: Antes de cada tarea, ejecutar `pytest tests/` y verificar que todo pasa. Después de cada tarea, ejecutar de nuevo y verificar que no se ha roto nada.

---

## Tareas ordenadas por prioridad y riesgo

---

### TAREA 1 🟢 — Validación de esquema de plantillas

**Objetivo**: Crear un validador que compruebe que una plantilla tiene todos los campos obligatorios y tipos correctos antes de guardarla.

**Archivos a crear/modificar**:
- **CREAR** `src/core/template_validator.py`
- **CREAR** `tests/test_template_validator.py`

**Especificación**:

```python
# src/core/template_validator.py

class TemplateValidator:
    """Valida el esquema de una plantilla antes de guardarla."""

    def validate(self, plantilla: dict) -> tuple[bool, list[str]]:
        """
        Valida una plantilla completa.

        Returns:
            (es_valida, lista_de_errores)
            Si es_valida es True, lista_de_errores estará vacía.
        """
        # Validar:
        # - nombre: str, no vacío, longitud <= 100
        # - categoria: str, no vacío
        # - descripcion: str, no vacío
        # - contexto_ia: str, no vacío, longitud >= 20 (debe ser descriptivo)
        # - partidas_base: list, no vacía, al menos 1 partida
        #   - cada partida: concepto (str, no vacío), unidad (str, no vacío),
        #     precio_ref (number, > 0)
```

**Tests a escribir**:
- Plantilla válida completa → True, []
- Plantilla sin nombre → False, ["El nombre es obligatorio"]
- Plantilla con partidas_base vacío → False, ["Debe tener al menos 1 partida"]
- Plantilla con precio_ref negativo → False, ["El precio debe ser positivo"]
- Plantilla con contexto_ia muy corto → False, ["El contexto IA debe ser descriptivo (mín. 20 caracteres)"]

**Verificación**: `pytest tests/test_template_validator.py -v` debe pasar al 100%. Los tests existentes no deben verse afectados.

---

### TAREA 2 🟢 — Método `update_custom()` en el catálogo

**Objetivo**: Añadir un método para actualizar campos de una plantilla personalizada existente sin tener que borrarla y recrearla.

**Archivos a modificar**:
- `src/core/custom_templates.py` — Añadir método `update()`
- `src/core/work_type_catalog.py` — Añadir método `update_custom()`
- `tests/test_custom_templates.py` — Añadir tests para update

**Especificación**:

```python
# En CustomTemplateStore, AÑADIR (no modificar métodos existentes):

def update(self, nombre: str, changes: dict) -> bool:
    """
    Actualiza campos de una plantilla personalizada existente.

    Args:
        nombre: Nombre de la plantilla a actualizar.
        changes: Diccionario con los campos a actualizar.
                 Solo se actualizan los campos presentes en 'changes'.
                 No se permite cambiar 'personalizada' ni eliminar campos obligatorios.

    Returns:
        True si se actualizó, False si no existe o es inválida.
    """
```

```python
# En WorkTypeCatalog, AÑADIR:

def update_custom(self, nombre: str, changes: dict) -> bool:
    """Actualiza una plantilla personalizada. No permite modificar predefinidas."""
    if any(p['nombre'] == nombre for p in self._predefined):
        return False
    return self._custom_store.update(nombre, changes)
```

**Tests a escribir**:
- `test_update_descripcion` — Cambiar solo la descripción, verificar que el resto no cambia
- `test_update_contexto_ia` — Cambiar el contexto_ia
- `test_update_partidas_base` — Reemplazar lista de partidas_base
- `test_update_nonexistent` — Intentar actualizar plantilla que no existe → False
- `test_update_cannot_modify_predefined` — No se pueden modificar predefinidas
- `test_update_nombre_changes_key` — Si se cambia el nombre, se actualiza correctamente

**Verificación**: Ejecutar `pytest tests/test_custom_templates.py tests/test_work_type_catalog.py -v`. Todos los tests anteriores + los nuevos deben pasar.

---

### TAREA 3 🟡 — Integrar validador en `CustomTemplateStore.add()` y `update()`

**Objetivo**: Que `add()` y `update()` validen la plantilla antes de guardarla usando el `TemplateValidator` de la Tarea 1.

**Archivos a modificar**:
- `src/core/custom_templates.py` — Importar y usar `TemplateValidator`

**Cambios específicos**:

En el método `add()`, ANTES de la línea `plantilla['personalizada'] = True`, añadir:

```python
validator = TemplateValidator()
is_valid, errors = validator.validate(plantilla)
if not is_valid:
    return False
```

Hacer lo mismo en `update()` — validar el resultado final antes de guardar.

**PRECAUCIÓN**: El método `add()` actualmente acepta plantillas sin validación. Al añadir validación, asegurarse de que las plantillas que se importan desde Excel (que tienen campos autogenerados) siguen siendo válidas. Revisar el flujo en `template_manager_dialog.py` líneas 284-294 para verificar que el `contexto_ia` autogenerado cumple la longitud mínima de 20 caracteres.

**Verificación**: `pytest tests/ -v` — TODOS los tests deben seguir pasando. Probar manualmente el flujo de importar desde Excel.

---

### TAREA 4 🟡 — Diálogo de edición de plantilla personalizada

**Objetivo**: Crear un diálogo GUI que permita editar los campos de una plantilla personalizada existente: `nombre`, `categoria`, `descripcion`, `contexto_ia`, y las `partidas_base` individualmente.

**Archivos a crear/modificar**:
- **CREAR** `src/gui/template_edit_dialog.py`
- **MODIFICAR** `src/gui/template_manager_dialog.py` — Añadir botón "Editar" junto a "Eliminar"

**Especificación del diálogo de edición**:

```python
# src/gui/template_edit_dialog.py

class TemplateEditDialog(wx.Dialog):
    """Diálogo para editar una plantilla personalizada."""

    def __init__(self, parent, plantilla: dict):
        """
        Args:
            parent: Ventana padre.
            plantilla: Plantilla a editar (dict completo).
        """
        # Layout del diálogo:
        #
        # ┌─────────────────────────────────────────────────────┐
        # │  Editar Plantilla                                   │
        # │                                                     │
        # │  Nombre:     [___________________________]          │
        # │  Categoría:  [___________________________]          │
        # │  Descripción:[___________________________]          │
        # │                                                     │
        # │  Contexto para la IA:                               │
        # │  ┌───────────────────────────────────────────┐      │
        # │  │ (TextCtrl multilínea, 4-5 líneas)        │      │
        # │  │ Este texto se envía directamente a la IA │      │
        # │  │ como contexto. Cuanto más detallado,     │      │
        # │  │ mejor será el resultado.                  │      │
        # │  └───────────────────────────────────────────┘      │
        # │  ℹ️ Tip: describe materiales, consideraciones...    │
        # │                                                     │
        # │  Partidas de referencia:                            │
        # │  ┌──────────────────────┬──────┬──────────┐        │
        # │  │ Concepto             │ Ud.  │ Precio   │        │
        # │  ├──────────────────────┼──────┼──────────┤        │
        # │  │ Desmontaje bajante   │ ml   │ 18.50 €  │        │
        # │  │ ...                  │ ...  │ ...      │        │
        # │  └──────────────────────┴──────┴──────────┘        │
        # │  [+ Añadir partida]  [Editar]  [Eliminar partida]  │
        # │                                                     │
        # │  ───────────────────────────────────────────        │
        # │                       [Cancelar]  [Guardar]         │
        # └─────────────────────────────────────────────────────┘
```

**Funcionalidades del diálogo**:
1. Campos de texto editables para: nombre, categoría, descripción
2. TextCtrl multilínea para `contexto_ia` con hint/tooltip explicativo
3. ListCtrl para `partidas_base` con posibilidad de:
   - Añadir nueva partida (mini-diálogo con concepto, unidad, precio)
   - Editar partida seleccionada (doble-clic o botón)
   - Eliminar partida seleccionada
4. Botón "Guardar" que:
   - Recoge todos los campos
   - Valida con `TemplateValidator`
   - Si hay errores, muestra `wx.MessageBox` con la lista
   - Si es válida, devuelve la plantilla editada
5. Botón "Cancelar" que cierra sin guardar

**Estilo visual**: Usar `src/gui/theme.py` para mantener la coherencia visual (mismas funciones que usa `template_manager_dialog.py`): `theme.style_dialog()`, `theme.style_panel()`, `theme.create_title()`, `theme.create_text()`, `theme.get_font_medium()`, `theme.font_base()`, `theme.BG_CARD`, `theme.TEXT_PRIMARY`, `theme.ACCENT_PRIMARY`, etc.

**Integración en `template_manager_dialog.py`**:
- Añadir un botón "Editar" (`self._btn_edit`) al lado de "Eliminar"
- Solo habilitado cuando se selecciona una plantilla personalizada (igual que Eliminar)
- Al hacer clic, abre `TemplateEditDialog` con la plantilla seleccionada
- Si el usuario guarda, llama a `self._catalog.update_custom()` o `self._catalog.add_custom()` con la plantilla editada y refresca la lista

**Verificación**: Abrir la app, ir a Configuración > Gestionar plantillas, seleccionar una personalizada, hacer clic en Editar, modificar campos, guardar. Verificar que los cambios persisten al cerrar y reabrir. Ejecutar `pytest tests/ -v` para confirmar que no se ha roto nada.

---

### TAREA 5 🟡 — Diálogo de creación manual de plantilla (sin Excel)

**Objetivo**: Permitir crear una plantilla personalizada desde cero, sin necesidad de importar desde Excel.

**Archivos a modificar**:
- `src/gui/template_manager_dialog.py` — Añadir botón "+ Crear nueva"
- Reutilizar `src/gui/template_edit_dialog.py` de la Tarea 4 (pasando plantilla vacía)

**Especificación**:

Añadir un segundo botón en `template_manager_dialog.py` junto al existente "+ Añadir desde Excel":

```python
btn_create = wx.Button(panel, label="+ Crear nueva", size=(130, 38))
# Estilo similar al botón de añadir
```

Al hacer clic:
1. Crear una plantilla vacía con valores por defecto:
   ```python
   nueva = {
       'nombre': '',
       'categoria': 'personalizada',
       'descripcion': '',
       'contexto_ia': '',
       'partidas_base': [],
   }
   ```
2. Abrir `TemplateEditDialog(self, nueva)`
3. Si el usuario guarda, verificar que el nombre no está duplicado
4. Llamar a `self._catalog.add_custom(plantilla)` y refrescar la lista

**Verificación**: Crear una plantilla desde cero con nombre, contexto_ia detallado y al menos 3 partidas. Verificar que aparece en la lista, que se puede seleccionar en el diálogo de generación IA, y que genera partidas correctamente. Ejecutar `pytest tests/ -v`.

---

### TAREA 6 🟡 — Duplicar plantilla predefinida como personalizada

**Objetivo**: Permitir duplicar cualquier plantilla (incluidas las predefinidas) como nueva plantilla personalizada editable.

**Archivos a modificar**:
- `src/gui/template_manager_dialog.py` — Añadir botón "Duplicar"

**Especificación**:

Añadir botón "Duplicar" (`self._btn_duplicate`) que:
1. Esté siempre habilitado cuando hay una plantilla seleccionada (tanto predefinidas como personalizadas)
2. Al hacer clic:
   - Copiar la plantilla seleccionada (deep copy)
   - Pedir nuevo nombre al usuario: `wx.TextEntryDialog` con valor por defecto `"Copia de {nombre_original}"`
   - Verificar que el nombre no existe ya
   - Marcar como personalizada
   - Abrir `TemplateEditDialog` con la copia para que el usuario pueda editarla
   - Si guarda, añadirla al catálogo

**Verificación**: Duplicar la plantilla "Reparación de bajante", cambiar nombre y contexto_ia, guardar. Verificar que la original no se ha modificado y que la copia aparece como personalizada.

---

### TAREA 7 🔴 — Mejora del `contexto_ia` autogenerado al importar desde Excel

**Objetivo**: Al importar una plantilla desde Excel, generar un `contexto_ia` rico y detallado usando la propia IA (Gemini), en vez del texto genérico actual.

**Archivos a modificar**:
- `src/gui/template_manager_dialog.py` — Modificar el método `_on_add()` (flujo de importación)
- `src/core/ai_service.py` — Añadir método para generar contexto_ia

**PRECAUCIÓN MÁXIMA**: Esta tarea modifica un flujo existente (importar desde Excel) y depende de la disponibilidad de la IA. Si la IA no está disponible, DEBE funcionar igual que antes (fallback al texto genérico actual).

**Especificación**:

1. En `ai_service.py`, AÑADIR un nuevo método (NO modificar los existentes):

```python
def generate_contexto_ia(self, nombre: str, partidas: list) -> str | None:
    """
    Genera un contexto_ia descriptivo a partir del nombre y las partidas.

    Args:
        nombre: Nombre de la plantilla.
        partidas: Lista de partidas extraídas del Excel.

    Returns:
        String con el contexto generado, o None si la IA no está disponible.
    """
    # Construir un prompt corto pidiendo a Gemini que genere
    # un párrafo descriptivo (3-5 líneas) sobre este tipo de obra
    # basándose en las partidas proporcionadas.
    #
    # Ejemplo de prompt:
    # "Genera un párrafo descriptivo (3-5 líneas) para un contexto de
    #  presupuesto de obra de tipo '{nombre}'. Las partidas incluidas son:
    #  {lista de conceptos}. Describe qué incluye este tipo de obra,
    #  materiales habituales y consideraciones técnicas importantes.
    #  Responde solo con el texto descriptivo, sin formato JSON."
```

2. En `template_manager_dialog.py`, modificar `_on_add()` entre los pasos 4 y 5:

```python
# DESPUÉS de confirmar la importación (paso 4) y ANTES de guardar (paso 5):

# Intentar generar contexto_ia con IA
contexto_ia_generado = None
api_key = Settings().get_api_key()
if api_key:
    ai_service = AIService(api_key=api_key)
    if ai_service.is_available():
        wx.BeginBusyCursor()
        contexto_ia_generado = ai_service.generate_contexto_ia(nombre, partidas)
        wx.EndBusyCursor()

# Construir plantilla con contexto_ia mejorado o genérico (fallback)
plantilla = {
    'nombre': nombre,
    'categoria': 'personalizada',
    'descripcion': f"Plantilla importada desde {os.path.basename(excel_path)}",
    'contexto_ia': contexto_ia_generado or (
        f"Presupuesto de tipo '{nombre}'. "
        f"Partidas de referencia importadas de un presupuesto real. "
        f"Usar como base para generar partidas similares adaptadas al caso concreto."
    ),
    'partidas_base': partidas,
}
```

**IMPORTANTE**: El fallback (`or texto_genérico`) garantiza que si la IA falla o no está disponible, el comportamiento es IDÉNTICO al actual. Esto es clave para no romper funcionalidad.

**Verificación**:
1. Con API key configurada: Importar Excel, verificar que el `contexto_ia` es descriptivo y específico
2. Sin API key: Importar Excel, verificar que el `contexto_ia` es el genérico (mismo comportamiento que antes)
3. Ejecutar `pytest tests/ -v`

---

### TAREA 8 🟢 — Previsualización del prompt antes de generar

**Objetivo**: Añadir un botón "Ver prompt" en el diálogo de generación IA que muestre el prompt completo que se enviará a Gemini, para que el usuario pueda verificar que la plantilla seleccionada aporta el contexto esperado.

**Archivos a modificar**:
- `src/gui/ai_budget_dialog_wx.py` — Añadir botón "Vista previa del prompt"

**Especificación**:

Añadir un botón discreto (estilo link o botón pequeño sin acento) debajo de la lista de plantillas:

```python
btn_preview = wx.Button(panel, label="👁 Ver prompt que se enviará", size=(220, 30))
btn_preview.SetFont(theme.font_sm())
# Sin color de acento, estilo secundario
```

Al hacer clic:
1. Recoger los valores actuales (tipo_obra, descripción, plantilla seleccionada)
2. Construir el prompt con `PromptBuilder().build_prompt(...)`
3. Mostrar en un diálogo de solo lectura:
   ```python
   dlg = wx.Dialog(self, title="Prompt para la IA", size=(600, 500),
                   style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
   text = wx.TextCtrl(dlg, style=wx.TE_MULTILINE | wx.TE_READONLY)
   text.SetValue(prompt)
   ```

**Verificación**: Abrir diálogo IA, escribir tipo de obra, seleccionar plantilla, clic en "Ver prompt". Verificar que se muestra el prompt completo con el contexto_ia y las partidas_base de la plantilla seleccionada. Ejecutar `pytest tests/ -v`.

---

### TAREA 9 🟢 — Exportar/Importar plantillas personalizadas como JSON

**Objetivo**: Permitir exportar plantillas personalizadas a un archivo JSON e importarlas, facilitando compartir entre usuarios o hacer backups.

**Archivos a modificar**:
- `src/gui/template_manager_dialog.py` — Añadir botones "Exportar" e "Importar JSON"

**Especificación**:

**Exportar**: Botón que guarda la plantilla seleccionada (personalizada) como archivo `.json`:
```python
# Al hacer clic en "Exportar":
plantilla = self._catalog.get_by_name(nombre)
file_dlg = wx.FileDialog(self, "Guardar plantilla",
                         wildcard="JSON (*.json)|*.json",
                         style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
                         defaultFile=f"{nombre}.json")
# Guardar como: {"plantillas": [plantilla]}
# (mismo formato que custom_templates.json para compatibilidad)
```

**Importar JSON**: Botón que carga una plantilla desde un archivo `.json`:
```python
# Al hacer clic en "Importar JSON":
# 1. Abrir FileDialog para seleccionar .json
# 2. Leer y parsear el JSON
# 3. Validar con TemplateValidator
# 4. Si es válida, añadir con self._catalog.add_custom()
# 5. Refrescar lista
```

**Formato del archivo JSON exportado**: Mismo formato que `work_types.json`, con una o más plantillas dentro de `{"plantillas": [...]}`. Al importar, se importan TODAS las plantillas del archivo.

**Verificación**: Exportar una plantilla, verificar que el archivo JSON es legible. Eliminar la plantilla. Importar desde el JSON. Verificar que se restaura correctamente.

---

## Orden de ejecución recomendado

```
TAREA 1 🟢 Validador ──────────────────┐
                                         ├──> TAREA 3 🟡 Integrar validador
TAREA 2 🟢 Método update() ────────────┘         │
                                                   ▼
                                         TAREA 4 🟡 Diálogo de edición
                                                   │
                                          ┌────────┼────────┐
                                          ▼        ▼        ▼
                                  TAREA 5 🟡   TAREA 6 🟡   TAREA 8 🟢
                                  Crear nueva  Duplicar    Ver prompt
                                                   │
                                                   ▼
                                         TAREA 7 🔴 contexto_ia con IA
                                                   │
                                                   ▼
                                         TAREA 9 🟢 Export/Import JSON
```

**Flujo**:
1. Tareas 1 y 2 en paralelo (independientes entre sí) → base sólida
2. Tarea 3 integra el validador → seguridad en la persistencia
3. Tarea 4 crea el diálogo de edición → funcionalidad central
4. Tareas 5, 6 y 8 en paralelo (usan el diálogo de la 4 o son independientes)
5. Tarea 7 al final (mayor riesgo, depende de IA)
6. Tarea 9 al final (funcionalidad complementaria)

---

## Reglas de ejecución (OBLIGATORIAS)

### Antes de cada tarea:
1. `pytest tests/ -v` — Verificar que todo pasa ✅
2. Leer los archivos que vas a modificar con la herramienta Read
3. Identificar las líneas exactas que cambiarán

### Durante cada tarea:
4. NO eliminar ni renombrar métodos públicos existentes
5. NO cambiar las firmas de métodos existentes (puedes añadir parámetros opcionales con valor por defecto)
6. NO modificar `src/data/work_types.json` (plantillas predefinidas son inmutables)
7. NO modificar el flujo de `budget_generator.py` ni `ai_service.py` (excepto en Tarea 7, con extremo cuidado)
8. Usar SIEMPRE los estilos de `src/gui/theme.py` para componentes GUI
9. Seguir el patrón de código existente (docstrings, type hints, estructura)

### Después de cada tarea:
10. `pytest tests/ -v` — TODOS los tests deben pasar (incluyendo los nuevos)
11. Verificar que no hay errores de linter en los archivos modificados
12. Si la tarea incluye GUI, verificar visualmente que el diálogo se muestra correctamente

### Si algo se rompe:
13. **STOP**. No avanzar a la siguiente tarea.
14. Revertir los cambios de la tarea actual
15. Diagnosticar qué test falló y por qué
16. Corregir y volver a verificar antes de continuar

---

## Resumen del semáforo

| Tarea | Semáforo | Descripción | Archivos afectados |
|-------|----------|-------------|-------------------|
| 1 | 🟢 VERDE | Validador de plantillas | Nuevos: `template_validator.py`, test |
| 2 | 🟢 VERDE | Método `update_custom()` | `custom_templates.py`, `work_type_catalog.py`, test |
| 3 | 🟡 AMARILLO | Integrar validador en add/update | `custom_templates.py` |
| 4 | 🟡 AMARILLO | Diálogo de edición | Nuevo: `template_edit_dialog.py`, modifica `template_manager_dialog.py` |
| 5 | 🟡 AMARILLO | Crear plantilla desde cero | `template_manager_dialog.py` |
| 6 | 🟡 AMARILLO | Duplicar plantilla | `template_manager_dialog.py` |
| 7 | 🔴 ROJO | contexto_ia con IA | `ai_service.py`, `template_manager_dialog.py` |
| 8 | 🟢 VERDE | Ver prompt | `ai_budget_dialog_wx.py` |
| 9 | 🟢 VERDE | Export/Import JSON | `template_manager_dialog.py` |
