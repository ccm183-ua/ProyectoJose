# Plan: Sugerir Comunidad desde Dirección y Contexto

## 1. Contexto de la aplicación

### 1.1 Flujo actual de selección de comunidad

**Ubicación**: `src/gui/main_frame.py` → `_buscar_comunidad_para_presupuesto(nombre_cliente, direccion)`

**Flujo**:
1. `DatabaseService.buscar_comunidad(nombre_cliente)` → (exacta, fuzzy)
2. Si **exacta**: `ComunidadConfirmDialog` → confirmar o rechazar
3. Si **fuzzy**: `ComunidadFuzzySelectDialog` → elegir entre candidatas o "Añadir nueva"
4. Si **ninguna**: preguntar si crear nueva → `crear_comunidad_con_formulario`

**Entrada**: Solo `nombre_cliente` (y `direccion` como prefill al crear nueva comunidad).

### 1.2 Búsqueda actual de comunidades

| Función | Archivo | Descripción |
|---------|---------|-------------|
| `buscar_comunidad_por_nombre` | `comunidad_repository.py` | Match exacto (case-insensitive) + normalización (C.P., etc.) |
| `buscar_comunidades_fuzzy` | `comunidad_repository.py` | `SequenceMatcher` sobre nombre normalizado, umbral 0.55 |

**Campos de comunidad en BD**: `id`, `nombre`, `cif`, `direccion`, `email`, `telefono`, `administracion_id`

### 1.3 Dónde se usa

- **Crear presupuesto**: `_create_budget` → `_buscar_comunidad_para_presupuesto(cliente, direccion_proyecto)`
- **Regenerar campos**: `_edit_regen_header` en dashboard → mismo flujo

### 1.4 Problema a resolver

Hoy la búsqueda es **solo por nombre de cliente**. Si el usuario escribe "C.P. Edificio XYZ" y en BD está "Comunidad de Propietarios Edificio XYZ", el fuzzy puede encontrarlo. Pero si:

- El cliente en el presupuesto es "Juan Pérez" (presidente) y la comunidad es "C.P. Calle Mayor 5"
- La dirección es "Calle Mayor 5, 3ºB" y hay una comunidad con `direccion` "Calle Mayor 5"

… no hay forma de sugerir esa comunidad por dirección. La idea es **sugerir comunidades también por dirección** (y otros criterios contextuales).

---

## 2. Objetivos

1. **Búsqueda por dirección**: Encontrar comunidades cuya `direccion` coincida (exacta o fuzzy) con la dirección del proyecto
2. **Combinar criterios**: Si hay nombre Y dirección, combinar resultados (priorizar coincidencias en ambos)
3. **Sugerir proactivamente**: Antes de "no encontrada", mostrar candidatas por dirección
4. **Mantener flujo actual**: No romper el flujo existente; añadir una capa de sugerencias

---

## 3. Diseño de la solución

### 3.1 Nueva función de búsqueda: `buscar_comunidades_por_direccion`

**Ubicación**: `src/core/repositories/comunidad_repository.py` (o `db_repository` si se usa el facade)

**Lógica**:
- Normalizar dirección de entrada (quitar tildes, mayúsculas, espacios extra)
- Extraer "calle + número" o "localidad" como tokens significativos
- Buscar comunidades donde `direccion` contenga esos tokens (LIKE) o coincida por fuzzy
- Devolver lista ordenada por relevancia

**Consideraciones**:
- Las direcciones son libres: "Calle Mayor 5", "C/ Mayor 5", "Mayor 5 03001"
- Normalizar variantes: C/, Calle, Ctra., Av., etc.
- Evitar falsos positivos (ej. "5" solo)

### 3.2 Función combinada: `sugerir_comunidades`

**Entrada**: `nombre_cliente`, `direccion` (y opcionalmente `localidad`, `codigo_postal`)

**Salida**: Lista de candidatas con `origen`: `"nombre_exacto"` | `"nombre_fuzzy"` | `"direccion"` | `"nombre_y_direccion"`

**Lógica**:
1. Buscar por nombre (exacto + fuzzy) → resultados con `origen`
2. Si hay dirección, buscar por dirección → resultados con `origen="direccion"`
3. Si hay coincidencias en ambos (misma comunidad por nombre y por dirección) → `origen="nombre_y_direccion"`, mayor prioridad
4. Unificar y ordenar: `nombre_y_direccion` > `nombre_exacto` > `nombre_fuzzy` > `direccion`
5. Eliminar duplicados por `comunidad.id`

### 3.3 Cambios en la UI

**Opción A**: Reutilizar `ComunidadFuzzySelectDialog`

- Ampliar para aceptar también candidatas por dirección
- Mostrar columna "Origen" (Nombre, Dirección, Ambos)
- El usuario elige igual que ahora

**Opción B**: Nuevo diálogo `ComunidadSugeridaDialog`

- Similar a `ComunidadFuzzySelectDialog` pero con más columnas (Nombre, Dirección, Origen)
- Agrupar por origen si hay muchas

**Recomendación**: Opción A para no duplicar código. Añadir columna "Origen" a la tabla.

### 3.4 Flujo actualizado

```
_buscar_comunidad_para_presupuesto(nombre_cliente, direccion)
  │
  ├─► sugerir_comunidades(nombre_cliente, direccion)
  │     ├─► buscar por nombre (exacto + fuzzy)
  │     └─► buscar por dirección (si hay)
  │
  ├─► Si hay 1 exacta por nombre → ComunidadConfirmDialog (como ahora)
  │
  ├─► Si hay varias (fuzzy + dirección) → ComunidadFuzzySelectDialog ampliado
  │     └─► Mostrar todas con columna Origen
  │
  └─► Si ninguna → preguntar crear nueva (como ahora)
```

---

## 4. Implementación técnica

### 4.1 Normalización de direcciones

Crear `src/utils/address_utils.py` (o dentro de `budget_utils.py`):

```python
def normalize_address_for_search(addr: str) -> str:
    """Normaliza dirección para búsqueda: minúsculas, sin tildes, abreviaturas expandidas."""
    # C/ -> calle, Av. -> avenida, etc.
    # Quitar CP si está al final
    ...

def extract_address_tokens(addr: str) -> list[str]:
    """Extrae tokens significativos (número de portal, nombre de vía, localidad)."""
    ...
```

### 4.2 Búsqueda por dirección en SQL

**Opción 1 - LIKE**:
```sql
SELECT ... FROM comunidad 
WHERE LOWER(direccion) LIKE '%' || LOWER(?) || '%'
```

**Opción 2 - FTS (Full-Text Search)**: Si SQLite tiene FTS5, más potente pero más complejo.

**Opción 3 - Fuzzy en Python**: Cargar todas las comunidades con dirección no vacía y aplicar `SequenceMatcher` o similar. Menos eficiente pero más flexible.

**Recomendación inicial**: Opción 1 con tokens normalizados. Si hay muchas comunidades, considerar FTS o índice.

### 4.3 Nuevas funciones en repositorio

```python
# comunidad_repository.py

def buscar_comunidades_por_direccion(direccion: str, limit: int = 20) -> List[Dict]:
    """Busca comunidades cuya dirección coincida con la dada (tokens)."""
    ...

def sugerir_comunidades(
    nombre_cliente: str,
    direccion: str = "",
    localidad: str = "",
) -> List[Dict]:
    """Combina búsqueda por nombre y dirección, devuelve candidatas ordenadas."""
    ...
```

### 4.4 Cambios en DatabaseService

```python
# database_service.py

@staticmethod
def sugerir_comunidades(nombre_cliente: str, direccion: str = "", localidad: str = "") -> List[Dict]:
    """Sugiere comunidades por nombre y/o dirección."""
    return db_repository.sugerir_comunidades(nombre_cliente, direccion, localidad)
```

### 4.5 Cambios en MainFrame

Sustituir llamada a `buscar_comunidad` por `sugerir_comunidades` y adaptar el flujo:

- Si `len(resultados) == 1` y `origen == "nombre_exacto"` → confirmación (como ahora)
- Si `len(resultados) > 1` → diálogo de selección (ampliado con columna Origen)
- Si `len(resultados) == 0` → crear nueva

---

## 5. Tareas ordenadas

### Fase 1: Búsqueda por dirección

| # | Tarea | Archivos | Riesgo |
|---|-------|----------|--------|
| 1.1 | Crear `normalize_address_for_search` y `extract_address_tokens` | `utils/address_utils.py` o `budget_utils.py` | Bajo |
| 1.2 | Implementar `buscar_comunidades_por_direccion` en repositorio | `comunidad_repository.py` | Medio |
| 1.3 | Tests unitarios para normalización y búsqueda | `tests/test_comunidad_sugerida.py` | Bajo |

### Fase 2: Función combinada

| # | Tarea | Archivos | Riesgo |
|---|-------|----------|--------|
| 2.1 | Implementar `sugerir_comunidades` en repositorio | `comunidad_repository.py` | Medio |
| 2.2 | Exponer en `DatabaseService` y `db_repository` | `database_service.py`, `db_repository.py` | Bajo |
| 2.3 | Tests para `sugerir_comunidades` (solo nombre, solo dir, ambos) | `tests/test_comunidad_sugerida.py` | Bajo |

### Fase 3: Integración en flujo

| # | Tarea | Archivos | Riesgo |
|---|-------|----------|--------|
| 3.1 | Modificar `_buscar_comunidad_para_presupuesto` para usar `sugerir_comunidades` | `main_frame.py` | Medio |
| 3.2 | Ampliar `ComunidadFuzzySelectDialog` con columna "Origen" | `dialogs.py` | Bajo |
| 3.3 | Pasar `direccion` (y `localidad` si existe) desde `_create_budget` y `_edit_regen_header` | `main_frame.py`, `budget_dashboard.py` | Bajo |
| 3.4 | Ajustar `ComunidadConfirmDialog` si el único resultado viene por dirección | `dialogs.py` | Bajo |

### Fase 4: Refinamientos

| # | Tarea | Archivos | Riesgo |
|---|-------|----------|--------|
| 4.1 | Añadir búsqueda por localidad (comunidades en misma localidad) | `comunidad_repository.py` | Bajo |
| 4.2 | Ordenar por número de presupuestos asociados (comunidades más usadas primero) | `comunidad_repository.py` | Bajo |

---

## 6. Consideraciones

- **Privacidad**: No se usan datos externos; todo es local (BD + datos del presupuesto)
- **Rendimiento**: Con cientos de comunidades, la búsqueda por dirección con LIKE puede ser suficiente
- **Direcciones vacías**: Muchas comunidades pueden tener `direccion` vacía; la búsqueda por dirección solo aplica cuando hay datos
- **Compatibilidad**: El flujo actual debe seguir funcionando si `direccion` está vacía (solo búsqueda por nombre)

---

## 7. Dependencias

- Sin dependencias externas nuevas
- Reutiliza `buscar_comunidad_por_nombre`, `buscar_comunidades_fuzzy`, `ComunidadFuzzySelectDialog`, `ComunidadConfirmDialog`
