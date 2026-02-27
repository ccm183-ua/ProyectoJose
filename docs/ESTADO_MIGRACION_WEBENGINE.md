# Estado de la migración a Qt WebEngine

## Resumen

Este documento refleja el estado actual de la migración de la UI de cubiApp a Qt WebEngine. Las vistas principales se implementan como **vistas dentro del dashboard** (SPA), no como ventanas Qt separadas.

---

## Implementado

### Dashboard principal
- **Inicio**: Cards de acción (Crear presupuesto, Presupuestos existentes, Base de datos)
- **Configuración**: Rutas por defecto + API Key de Gemini (formularios inline)
- **Presupuestos**: Lista de presupuestos por estado (pestañas), tabla con columnas principales, botón Abrir Excel
- **Base de datos**: Tabs Administraciones y Comunidades, CRUD completo (añadir, editar, eliminar), búsqueda
- **Plantillas**: Placeholder con botón para abrir ventana Qt (fallback)
- **Ayuda**: Modal Acerca de en HTML

### Bridge (demo_webengine.py)
| Método | Descripción |
|--------|-------------|
| `ping` | Prueba de conectividad |
| `createBudget` | Crear nuevo presupuesto (abre flujo Qt) |
| `openDbManager` | Abrir ventana Base de datos Qt |
| `openTemplateManager` | Abrir ventana Plantillas Qt |
| `showAbout` | Modal Acerca de |
| `getDefaultPaths` / `saveDefaultPaths` | Rutas por defecto |
| `getApiKey` / `saveApiKey` | API Key Gemini |
| `selectDirectory` / `selectFile` | Diálogos de selección (Qt) |
| `getBudgets` | Lista de presupuestos por estado (JSON) |
| `openBudget(ruta_excel)` | Abrir presupuesto en Excel |
| `getAdministraciones` / `getAdministracionesList` | Lista administraciones (tabla / dropdown) |
| `getComunidades` | Lista comunidades |
| `getAdministracion(id)` / `getComunidad(id)` | Detalle para edición |
| `createAdministracion` / `updateAdministracion` / `deleteAdministracion` | CRUD administraciones |
| `createComunidad` / `updateComunidad` / `deleteComunidad` | CRUD comunidades |

### Navegación
- Sidebar con vistas: Inicio, Presupuestos, Base de datos, Plantillas, Configuración, Ayuda
- Cambio de vista sin recargar
- Subheader actualizado según vista activa

---

## Pendiente de implementar

### 1. Vista Base de datos — Contactos
- Tab Contactos (lista de contactos con administraciones/comunidades asociadas)
- CRUD de contactos
- Asignación de contactos a administraciones y comunidades (relación N:M)

### 2. Vista Plantillas (web)
- Lista de plantillas disponibles
- Añadir plantilla desde Excel
- Eliminar plantillas personalizadas
- Ver partidas de una plantilla
- Bridge: `getTemplates`, `addTemplate`, `deleteTemplate`, `getTemplatePartidas`

### 3. Crear presupuesto (flujo web)
- Formulario en HTML para datos del proyecto
- Llamada a `createBudget` con datos JSON (sin abrir MainFrame Qt)
- Bridge ampliado para recibir datos del formulario

### 4. Funcionalidades avanzadas del dashboard de presupuestos
- Búsqueda/filtro por texto
- Menú contextual (mover a otra carpeta de estado)
- Exportar PDF
- Vista previa
- Regenerar campos

### 5. Diálogos auxiliares
- Selección de comunidad (fuzzy)
- Confirmaciones (mover, eliminar)
- Vista previa de presupuesto

---

## Archivos clave

| Archivo | Rol |
|---------|-----|
| `demo_webengine.py` | Punto de entrada, AppBridge, _MainWindow |
| `web/ui/index.html` | Layout, sidebar, vistas |
| `web/ui/js/app.js` | Modales, initConfigView, initPresupuestosView |
| `run_webengine.bat` | Script de arranque |

---

## Cómo probar

```bash
run_webengine.bat
# o
python main_webengine.py
```

1. Configurar la ruta de presupuestos en **Configuración**
2. Ir a **Presupuestos** para ver la lista
3. Clic en una fila o en **Abrir** para abrir el Excel
