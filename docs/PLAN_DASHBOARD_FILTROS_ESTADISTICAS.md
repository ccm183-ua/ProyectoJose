# Plan: Mejoras en el Dashboard — Filtros y Estadísticas por Administración/Comunidad

## 1. Contexto de la aplicación

### 1.1 Estado actual del dashboard

- **Ubicación**: `src/gui/budget_dashboard.py`
- **Estructura de datos**: `_tab_data[state_name]` → lista de dicts por pestaña (estado)
- **Fuente de datos**: `resolve_projects()` → `sync_presupuestos()` → tabla `presupuesto` en SQLite

### 1.2 Campos disponibles por presupuesto (en `_tab_data`)

| Campo | Origen | Uso actual |
|-------|--------|------------|
| `numero` | carpeta / relación | Columna Nº |
| `nombre_proyecto` | carpeta | Columna Proyecto |
| `cliente` | relación / Excel | Columna Cliente |
| `administracion_nombre` | DB (comunidad→admin) | Columna Administración |
| `direccion` | relación / Excel | Columna Dirección |
| `localidad` | relación / Excel | Búsqueda |
| `tipo_obra` | relación / Excel | Columna Tipo obra |
| `fecha` | relación / Excel | Columna Fecha |
| `subtotal`, `iva`, `total` | Excel | Columnas Bruto, IVA, Total+IVA |
| `ruta_excel`, `ruta_carpeta` | escaneo | Acciones Abrir |
| `estado` | carpeta padre | Pestaña |
| `comunidad_id`, `administracion_id` | DB cache | **No expuestos actualmente** |

### 1.3 Búsqueda actual

- `_filter_rows()`: filtra por `_SEARCH_KEYS` (nombre_proyecto, cliente, administracion_nombre, direccion, localidad, tipo_obra, numero, fuente_datos)
- Una caja de búsqueda por pestaña
- Sin filtros por rango de fechas, importe ni por entidad (comunidad/admin)

### 1.4 Alcance requerido (definido)

- **Filtros**: alcance **por pestaña** (cada carpeta tiene sus propios filtros)
- **Estadísticas**: en **pestaña separada** del notebook (ej. "Estadísticas" como última pestaña)

---

## 2. Objetivos

1. **Filtros avanzados**: por administración, comunidad, rango de fechas, rango de importe
2. **Alcance de filtros**: siempre sobre la **pestaña actual** (cada carpeta filtra sus propios datos)
3. **Estadísticas**: en **nueva pestaña** del notebook, con métricas por administración y comunidad

---

## 3. Cambios necesarios en datos

### 3.1 Exponer IDs en los datos del dashboard

**Problema**: `_fill_entry_from_cache()` en `budget_cache.py` no incluye `comunidad_id` ni `administracion_id` en la entrada.

**Solución**: Añadir en `_fill_entry_from_cache()`:

```python
entry["comunidad_id"] = cached.get("comunidad_id")
entry["administracion_id"] = cached.get("administracion_id")
```

**Archivos**: `src/core/budget_cache.py`

### 3.2 Cargar catálogos para filtros

Para desplegables de administración/comunidad necesitamos:

- `DatabaseService.get_administraciones()` 
- `DatabaseService.get_comunidades_para_tabla()` (o similar)

**Archivos**: `src/core/services/database_service.py` (ya existe)

---

## 4. Diseño de la UI

### 4.1 Panel de filtros (nuevo)

**Ubicación**: Junto a la barra de búsqueda (dentro de cada pestaña, cerca del search box).

**Problema de espacio**: El header ya tiene varios botones (Explorador, Actualizar, Ocultar datos extra, Restaurar columnas). Añadir filtros completos puede saturar la interfaz.

**Controles** (alcance: siempre pestaña actual):

| Filtro | Tipo |
|--------|------|
| Administración | QComboBox (vacío = todas) |
| Comunidad | QComboBox (vacío = todas) |
| Fecha desde | QDateEdit (opcional) |
| Fecha hasta | QDateEdit (opcional) |
| Importe mín. | QSpinBox/QDoubleSpinBox (opcional) |
| Importe máx. | QSpinBox/QDoubleSpinBox (opcional) |
| Limpiar filtros | QPushButton |

**Opción elegida: B. Fila colapsable**

- Fila debajo de la barra de búsqueda que se expande/colapsa con un chevron (▼/▶)
- Al expandir: todos los controles de filtro visibles
- Al colapsar: solo ocupa una línea mínima (ej. "Filtros: Admin X, Comunidad Y" o botón "Mostrar filtros")

### 4.2 Pestaña de estadísticas

**Ubicación**: Nueva pestaña en el `QTabWidget`, "  Estadísticas  " (al final, tras las carpetas de estado). **Separada de los filtros** — no comparte espacio con ellos.

**Selector de alcance** (dentro de la pestaña Estadísticas):

- **Combo o radio**: "Por carpeta" (elegir cuál) | "Todas las carpetas"
- Las estadísticas se recalculan según la selección

**Contenido**:

| Métrica | Descripción |
|---------|-------------|
| Nº presupuestos | Total según alcance elegido |
| Importe total | Suma de `total` (con IVA) |
| Por administración | Tabla: Admin \| Nº \| Importe total |
| Por comunidad | Tabla: Comunidad \| Nº \| Importe total |

---

## 5. Flujo de filtrado

### 5.1 Integración con `_filter_rows`

Actualmente `_filter_rows(rows, query)` solo usa texto. Hay que extender a:

```python
def _filter_rows(self, rows, query, filters=None):
    # 1. Filtro de texto (actual)
    filtered = self._filter_rows_by_text(rows, query)
    # 2. Aplicar filtros avanzados
    if filters:
        filtered = self._apply_advanced_filters(filtered, filters)
    return filtered
```

### 5.2 Filtros avanzados

```python
def _apply_advanced_filters(self, rows, filters):
    if filters.get("administracion_id"):
        rows = [r for r in rows if r.get("administracion_id") == filters["administracion_id"]]
    if filters.get("comunidad_id"):
        rows = [r for r in rows if r.get("comunidad_id") == filters["comunidad_id"]]
    if filters.get("fecha_desde"):
        # parsear fecha y comparar
    if filters.get("fecha_hasta"):
        ...
    if filters.get("importe_min"):
        rows = [r for r in rows if (r.get("total") or 0) >= filters["importe_min"]]
    if filters.get("importe_max"):
        ...
    return rows
```

### 5.3 Alcance de filtros

Los filtros se aplican **solo a la pestaña actual**. No hay modo "todas las carpetas" para el filtrado. Cada pestaña mantiene su propio estado de filtros (`_tab_filters[state_name]`).

---

## 6. Tareas ordenadas

### Fase 1: Datos y filtrado básico

| # | Tarea | Archivos | Riesgo |
|---|-------|----------|--------|
| 1.1 | Añadir `comunidad_id` y `administracion_id` a las entradas en `_fill_entry_from_cache` | `budget_cache.py` | Bajo |
| 1.2 | Crear `_apply_advanced_filters(rows, filters)` en dashboard | `budget_dashboard.py` | Bajo |
| 1.3 | Integrar filtros en `_filter_rows` (mantener búsqueda por texto) | `budget_dashboard.py` | Bajo |
| 1.4 | Añadir estado `_tab_filters[state_name]` (filtros por pestaña) | `budget_dashboard.py` | Bajo |

### Fase 2: UI de filtros

| # | Tarea | Archivos | Riesgo |
|---|-------|----------|--------|
| 2.1 | Crear panel de filtros (combo admin, combo comunidad, fechas, importes) | `budget_dashboard.py` | Medio |
| 2.2 | Conectar filtros a `_current_filters` y recalcular `_populate_table` | `budget_dashboard.py` | Medio |
| 2.3 | Implementar fila colapsable para filtros (expandir/colapsar con chevron) | `budget_dashboard.py` | Medio |

### Fase 3: Estadísticas

| # | Tarea | Archivos | Riesgo |
|---|-------|----------|--------|
| 3.1 | Crear función `_compute_stats(rows)` → dict con totales | `budget_dashboard.py` | Bajo |
| 3.2 | Añadir pestaña "Estadísticas" al notebook | `budget_dashboard.py` | Bajo |
| 3.3 | Contenido: Nº presupuestos, Importe total, tablas por admin/comunidad | `budget_dashboard.py` | Bajo |
| 3.4 | Añadir selector de alcance en pestaña Estadísticas: "Por carpeta" (combo) \| "Todas las carpetas" | `budget_dashboard.py` | Bajo |

### Fase 4: Refinamientos

| # | Tarea | Archivos | Riesgo |
|---|-------|----------|--------|
| 4.1 | Persistir filtros en sesión (opcional) | `budget_dashboard.py`, `settings` | Bajo |
| 4.2 | Exportar estadísticas a CSV/Excel (opcional) | `budget_dashboard.py` | Bajo |

---

## 7. Consideraciones

- **Rendimiento**: Los filtros y estadísticas se calculan en memoria sobre `_tab_data`; con muchos presupuestos puede ser aceptable. Si crece, valorar agregaciones en SQLite.
- **Comunidades sin administración**: Presupuestos con `comunidad_id` pero sin `administracion_id` deben incluirse en "Sin administración" o similar.
- **Fechas**: El campo `fecha` puede venir en formatos distintos; usar `normalize_date` y un parser robusto.
- **Tests**: Añadir tests para `_apply_advanced_filters` y `_compute_stats` con datos de prueba.

---

## 8. Dependencias

- Ninguna nueva dependencia externa
- Reutiliza `DatabaseService`, `_tab_data`, `_filter_rows`, `_populate_table`
