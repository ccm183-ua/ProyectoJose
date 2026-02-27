# Plan: Migración a Qt WebEngine (cubiApp)

## 1. Resumen ejecutivo

Este documento describe un plan completo para migrar la interfaz de cubiApp de **widgets Qt nativos** a **Qt WebEngine**, manteniendo la aplicación local y el backend Python intacto.

**Objetivos:**
- UI con comportamiento y estética de página web (HTML/CSS/JavaScript)
- **Diseño premium** con dashboard lateral, aspecto profesional y amigable
- **No replicar** el diseño actual — evolucionar a una presentación más moderna
- Plantilla Bootstrap como base (AdminLTE, Tabler, CoreUI, etc.)
- Assets optimizados (iconos, fuentes, ilustraciones)

---

## 1.1 Decisiones de arquitectura (lo que el usuario quiere)

**Resumen de lo acordado:**

| Decisión | Qué significa |
|----------|---------------|
| **Frontend = aplicación principal** | El usuario hace todo desde la UI web. Es la única interfaz que ve. |
| **Python no muestra nada** | Ni QFileDialog, ni QMessageBox, ni ningún widget Qt. Python es backend puro, invisible. |
| **La comunicación cambia** | Antes: llamadas directas en Python. Después: frontend llama al bridge con JSON, Python responde con JSON. |
| **La UI se reescribe** | De Python (Qt widgets) a HTML/CSS/JS. No es solo "cambiar cómo se ve" — es reemplazar la capa de interfaz. |
| **La lógica se mantiene** | BudgetService, PDFExporter, DatabaseService, etc. siguen igual. Solo cambia quién los llama (el bridge en lugar de MainFrame). |

**Flujo de comunicación:**

```
ANTES (Qt):                          DESPUÉS (WebEngine):
MainFrame (Python)                   Frontend (JS)
    │                                     │
    │  self._budget_svc.create_budget()   │  app.createBudget(JSON.stringify(data))
    │  (llamada directa, mismo proceso)   │  (vía QWebChannel, datos en JSON)
    ▼                                     ▼
BudgetService (Python)                 AppBridge (Python)
                                           │
                                           │  json.loads() → BudgetService.create_budget()
                                           ▼
                                       BudgetService (Python) — mismo código
                                           │
                                           │  return json.dumps({"success": True, ...})
                                           ▼
                                       Frontend recibe JSON y actualiza la UI
```

---

## 1.2 Arquitectura: frontend como aplicación principal

**Decisión clave:** El frontend (HTML/CSS/JS) es la **única interfaz** que ve el usuario. Python **no muestra nada** — ni QFileDialog, ni QMessageBox, ni ningún widget Qt. El usuario hace todo desde la UI web.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  LO QUE VE EL USUARIO                                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Ventana (QMainWindow)                                           │   │
│  │  ┌─────────────────────────────────────────────────────────────┐│   │
│  │  │  QWebEngineView = 100% HTML/CSS/JS                           ││   │
│  │  │  • Formularios, tablas, modales, toasts                      ││   │
│  │  │  • Selector de archivos (<input type="file">)                ││   │
│  │  │  • Todo lo que el usuario interactúa                         ││   │
│  │  └─────────────────────────────────────────────────────────────┘│   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │  QWebChannel (JSON)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  PYTHON (invisible para el usuario)                                       │
│  • AppBridge: recibe datos, ejecuta lógica, devuelve resultados          │
│  • BudgetService, PDFExporter, DatabaseService, etc.                    │
│  • Cero ventanas Qt, cero diálogos nativos                                │
└─────────────────────────────────────────────────────────────────────────┘
```

### Implicaciones

| Elemento | Antes (Qt) | Ahora (frontend) |
|----------|------------|------------------|
| Formularios | QLineEdit, QComboBox | `<input>`, `<select>`, etc. |
| Mensajes | QMessageBox | Modales o toasts HTML |
| Confirmaciones | QMessageBox.question | Modal HTML con botones Sí/No |
| Selección de archivo | QFileDialog | `<input type="file">` |
| Entrada de texto | QInputDialog | Campo en formulario HTML |

### Selección de archivos sin QFileDialog

El frontend usa `<input type="file">` de HTML5. Al hacer clic, el navegador (Chromium) muestra el selector de archivos del sistema. El flujo:

**Abrir presupuesto:**
```html
<input type="file" id="file-open" accept=".xlsx,.xls" />
```
```javascript
// Usuario selecciona archivo → leemos contenido y lo pasamos a Python
fileInput.addEventListener('change', async (e) => {
  const file = e.target.files[0];
  const arrayBuffer = await file.arrayBuffer();
  const base64 = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));
  const result = await app.openBudgetFromContent(base64, file.name);
  // Python recibe el contenido, lo guarda en temp, abre Excel, etc.
});
```

**Guardar presupuesto (crear nuevo):**
- El usuario rellena el formulario en el frontend.
- La **ruta de guardado** viene de Configuración (Settings): el usuario define "Carpeta de presupuestos" en la sección Config.
- Frontend llama `app.createBudget(projectData)` → Python crea carpeta + Excel en esa ruta.
- Python devuelve la ruta del archivo creado → frontend muestra "Presupuesto creado en X" con botón "Abrir carpeta".

**Exportar PDF:**
- El presupuesto ya existe en disco (ruta conocida).
- El frontend llama `app.exportPdf(ruta)` → Python exporta y devuelve la ruta del PDF.
- El frontend puede ofrecer "Abrir carpeta" o "Descargar" usando la ruta devuelta.

### Resumen

- **Frontend:** Toda la UI, formularios, modales, toasts, selector de archivos.
- **Python:** Backend puro. Recibe datos, ejecuta lógica, devuelve JSON. No muestra nada.

---

## 1.3 Múltiples ventanas: ¿se puede?

**Sí.** Puedes seguir teniendo varias ventanas abiertas como hasta ahora.

### Cómo funciona

Cada ventana es un `QMainWindow` con su propio `QWebEngineView`. Python crea y muestra tantas ventanas como necesites:

```
┌─────────────────────────┐  ┌─────────────────────────┐
│  Ventana 1              │  │  Ventana 2              │
│  Presupuestos existentes│  │  Datos Administración X  │
│  ┌───────────────────┐  │  │  ┌───────────────────┐  │
│  │ QWebEngineView    │  │  │  │ QWebEngineView    │  │
│  │ (HTML: lista       │  │  │  │ (HTML: ficha      │  │
│  │  presupuestos)    │  │  │  │  administración)  │  │
│  └───────────────────┘  │  │  └───────────────────┘  │
└─────────────────────────┘  └─────────────────────────┘
```

### Opciones de implementación

| Opción | Descripción | Uso típico |
|--------|-------------|------------|
| **A: Ventanas independientes** | Cada vista (Presupuestos, BD, Ficha) en su propia ventana | Como ahora: DBManagerFrame, BudgetDashboardFrame separados |
| **B: Abrir en nueva ventana** | Botón "Abrir en nueva ventana" que crea un `QMainWindow` adicional | Ver administración en una ventana y presupuestos en otra |
| **C: Split view** | Una ventana con paneles divididos (izq: lista, der: detalle) | Consultar datos de ambos lados sin cambiar de ventana |
| **D: Combinación** | Ventana principal con sidebar + ventanas auxiliares bajo demanda | Lo más flexible |

### Recomendación

**Combinar A + B:** La ventana principal tiene el dashboard con sidebar. Al hacer clic en "Presupuestos" o "Base de datos" se puede:
- Mostrar el contenido en el área principal (navegación SPA), o
- Ofrecer "Abrir en nueva ventana" para tener ambas vistas visibles a la vez.

El bridge expondría algo como:
```python
@pyqtSlot(str, result=bool)
def openInNewWindow(self, view_name: str) -> bool:
    """Abre 'presupuestos', 'db', 'ficha-123' en una ventana nueva."""
    window = WebWindow(view=view_name, parent=self)
    window.show()
    return True
```

**Conclusión:** Sí podrás tener administración en una ventana y presupuestos en otra, igual que ahora.

---

## 1.4 Garantía de funcionalidad: todo sigue igual

**Importante:** La migración a Qt WebEngine **solo afecta a la capa de presentación** (qué se ve en pantalla). Todo el código que hace el trabajo real —escaneo, PDF, IA, Excel, base de datos— **es Python y no cambia**:

```
┌─────────────────────────────────────────────────────────────────┐
│  ANTES (Qt Widgets)          │  DESPUÉS (Qt WebEngine)          │
├──────────────────────────────┼──────────────────────────────────┤
│  Usuario clica botón Qt      │  Usuario clica botón HTML        │
│         ↓                    │         ↓                         │
│  MainFrame._create_budget()  │  AppBridge.createBudget()        │
│         ↓                    │         ↓                         │
│  BudgetService.create_budget()  ←  MISMO CÓDIGO PYTHON          │
│  PDFExporter.export()          ←  MISMO CÓDIGO PYTHON           │
│  BudgetGenerator.generate()    ←  MISMO CÓDIGO PYTHON           │
│  folder_scanner.scan_root()     ←  MISMO CÓDIGO PYTHON           │
│  ...                           ←  ...                            │
└─────────────────────────────────────────────────────────────────┘
```

El `AppBridge` es un **puente** que recibe llamadas desde JavaScript y ejecuta exactamente la misma lógica que hoy ejecuta `MainFrame` o `BudgetDashboardFrame`. No se reescribe ni se sustituye ningún servicio.

### Inventario de funcionalidades: garantía de equivalencia

| Funcionalidad | Dónde está (Python) | ¿Cambia? | Cómo funciona tras migración |
|---------------|---------------------|----------|------------------------------|
| **Escaneo de carpetas** | `folder_scanner.scan_root()`, `scan_projects()`, `scan_explorer()` | ❌ No | AppBridge llama a los mismos módulos; la UI web solo muestra los datos devueltos |
| **Export PDF** | `PDFExporter.export()` (win32com + Excel COM) | ❌ No | Botón "Exportar PDF" en HTML → `app.exportPdf(ruta)` → Python ejecuta `PDFExporter.export()` igual que ahora |
| **Presupuestos con IA** | `BudgetGenerator.generate()` → `AIService` (Gemini) | ❌ No | Formulario HTML envía tipo obra/descripción → bridge llama a `BudgetGenerator.generate()` → misma API, mismo resultado |
| **Crear presupuesto** | `BudgetService.create_budget()` | ❌ No | Misma orquestación: plantilla, carpeta, Excel, historial |
| **Insertar partidas IA** | `BudgetService.insert_partidas()` + `PartidasWriter` | ❌ No | Usuario selecciona partidas en tabla HTML → bridge pasa lista a `insert_partidas()` |
| **Abrir Excel** | `BudgetService.open_budget()` + `subprocess` (Excel/excel.exe) | ❌ No | Python sigue abriendo el archivo con el comando del SO |
| **Base de datos** | `db_repository`, `DatabaseService`, SQLite | ❌ No | Todas las operaciones CRUD se hacen desde Python |
| **Gestión plantillas** | `TemplateManager`, `TemplateManagerDialog` | ❌ No | Bridge expone `getTemplates()`, `addTemplate()`, etc.; la lógica es igual |
| **Búsqueda comunidad** | `DatabaseService.buscar_comunidad()` | ❌ No | Se llama desde Python cuando el flujo lo requiere |
| **Vista previa presupuesto** | `BudgetReader`, `BudgetPreviewDialog` | ❌ No | Bridge devuelve datos JSON al frontend; la vista previa se muestra en HTML |
| **Mover entre carpetas** | `shutil.move` + `folder_scanner` | ❌ No | Menú contextual HTML → `app.moveProject(ruta, destino)` → Python mueve el archivo |
| **Configuración** (rutas, API key) | `Settings`, `get_default_path` | ❌ No | Formularios HTML guardan vía bridge; `Settings` sigue usando el mismo archivo |
| **Abrir carpeta BD** | `subprocess.run(["explorer", folder])` | ❌ No | Python ejecuta el mismo comando |
| **Cache de presupuestos** | `budget_cache.sync_presupuestos()`, `resolve_projects` | ❌ No | Se invoca al cargar el dashboard; los datos se devuelven como JSON |
| **Validaciones** | `db_validations`, `validators` | ❌ No | Se ejecutan en Python antes de guardar |

### Diálogos: todo en el frontend

| Elemento | Enfoque frontend-first |
|----------|------------------------|
| Selección de archivos | `<input type="file">` — el navegador muestra el selector nativo |
| Mensajes / errores | Modales o toasts HTML |
| Confirmaciones | Modal HTML con botones |
| Entrada de texto | Formularios HTML |

### Resumen técnico

- **win32com** (Excel COM para PDF): ✅ Sigue en Python, sin cambios.
- **openpyxl, pandas**: ✅ Siguen en Python, sin cambios.
- **sqlite3**: ✅ Sigue en Python, sin cambios.
- **subprocess** (abrir Excel, explorer, etc.): ✅ Sigue en Python, sin cambios.
- **google-genai** (Gemini): ✅ Sigue en Python, sin cambios.

Todo lo que hoy hace tu app lo seguirá haciendo **exactamente igual**. Solo cambia la interfaz que el usuario ve y con la que interactúa.

---

## 2. Visión de diseño: premium con dashboard lateral

### 2.1 Objetivo

**No replicar** el diseño actual. Pasar a una presentación **más profesional**, con:
- Dashboard con **sidebar lateral** (navegación fija)
- Aspecto **premium** (sombras, espaciado, tipografía cuidada)
- Experiencia **amigable** (empty states, feedback visual, iconografía clara)

### 2.2 Layout objetivo

```
┌─────────────────────────────────────────────────────────────────────┐
│  [Logo]  cubiApp                              [Usuario]  [Config]   │
├────────────┬────────────────────────────────────────────────────────┤
│            │  Breadcrumb: Inicio > Presupuestos                     │
│  Inicio    │  ┌──────────────────────────────────────────────────┐ │
│  Presup.   │  │  Contenido principal (cards, tablas, formularios)  │ │
│  Base d.   │  │                                                    │ │
│  Plantillas│  │                                                    │ │
│  Config    │  └──────────────────────────────────────────────────┘ │
│  ───────  │                                                         │
│  Ayuda    │                                                         │
└────────────┴────────────────────────────────────────────────────────┘
```

### 2.3 Plantilla base

Usar una plantilla Bootstrap con dashboard y sidebar:
- **AdminLTE 3**, **Tabler**, **CoreUI**, **Volt**, **Argon Dashboard**, etc.
- Bootstrap 5 preferible
- Incluir iconos (Bootstrap Icons, Lucide, Heroicons)

### 2.4 Paleta de colores (especificación centralizada)

**Objetivo:** Colores corporativos, sobrios y profesionales. Esta es la **única fuente de verdad** para la paleta. Para cambiar el tema, modifica estos valores y aplícalos en `app.css` como variables CSS.

#### Variables CSS (copiar a `web/ui/css/variables.css` o `:root` en `app.css`)

```css
:root {
  /* === SIDEBAR === */
  --sidebar-bg:           #1a2332;
  --sidebar-hover:         #243447;
  --sidebar-active-bg:     #0d47a1;
  --sidebar-active-fg:     #ffffff;
  --sidebar-text:          #e8eef4;
  --sidebar-text-muted:    #94a3b8;

  /* === HEADER === */
  --header-bg:             #1a2332;
  --header-text:           #ffffff;

  /* === ÁREA PRINCIPAL === */
  --main-bg:               #e8eef4;
  --card-bg:               #ffffff;
  --card-border:           #d1dbe6;
  --card-shadow:           0 1px 3px rgba(26, 35, 50, 0.08);

  /* === ACENTOS === */
  --accent-primary:        #1565c0;
  --accent-primary-hover:  #0d47a1;
  --accent-primary-light:   #e3f2fd;

  /* === TEXTO === */
  --text-primary:          #1a2332;
  --text-secondary:       #546e7a;
  --text-muted:            #78909c;

  /* === ESTADOS (badges, alertas) === */
  --state-success:         #2e7d32;
  --state-success-bg:      #e8f5e9;
  --state-warning:         #f57c00;
  --state-warning-bg:      #fff3e0;
  --state-error:           #c62828;
  --state-error-bg:        #ffebee;
  --state-pending:         #546e7a;
  --state-pending-bg:      #eceff1;

  /* === BORDES Y LÍNEAS === */
  --border-light:          #e2e8f0;
  --border-default:        #d1dbe6;
}
```

#### Tabla de referencia rápida

| Variable | Valor | Uso |
|----------|-------|-----|
| `--sidebar-bg` | #1a2332 | Fondo sidebar |
| `--sidebar-hover` | #243447 | Hover items sidebar |
| `--sidebar-active-bg` | #0d47a1 | Item activo sidebar |
| `--main-bg` | #e8eef4 | Fondo área contenido |
| `--card-bg` | #ffffff | Fondo cards |
| `--accent-primary` | #1565c0 | Botones, links, acentos |
| `--accent-primary-hover` | #0d47a1 | Hover botones |
| `--text-primary` | #1a2332 | Texto principal |
| `--text-secondary` | #546e7a | Texto secundario |
| `--state-success` | #2e7d32 | Badge TERMINADO |
| `--state-warning` | #f57c00 | Badge PTE., avisos |
| `--state-error` | #c62828 | Badge ANULADOS, errores |

#### Cómo cambiar la paleta

1. Editar las variables en `app.css` (bloque `:root`).
2. Todos los componentes que usen `var(--accent-primary)`, etc., se actualizarán automáticamente.
3. Para un tema alternativo (ej. teal), sustituir solo las variables `--accent-*` y `--sidebar-active-bg`.

### 2.5 Mapa de secciones

| Sección | Contenido |
|---------|-----------|
| **Inicio** | Resumen, estadísticas rápidas, accesos directos |
| **Presupuestos** | Lista con filtros, pestañas por estado, acciones |
| **Base de datos** | Tabs: Administraciones, Comunidades, Contactos |
| **Plantillas** | Gestión de plantillas Excel |
| **Configuración** | Rutas, API key, preferencias |
| **Ayuda** | Acerca de |

### 2.6 Disposición de pantallas (decisiones acordadas)

#### Dashboard de presupuestos: flexible

El usuario podrá **elegir** cómo ver la lista de presupuestos. Las tres vistas tienen sentido y se ofrecerán como opciones intercambiables sin romper el estilo:

| Vista | Descripción | Cuándo usar |
|-------|-------------|-------------|
| **Pestañas arriba** | Tabs horizontales (PTE. PRESUP., PRESUPUESTADO, etc.) con tabla debajo | Vista actual, familiar |
| **Sidebar + tabla** | Lista de estados a la izquierda, tabla a la derecha | Navegación por estados |
| **Cards por estado** | Bloques/cards agrupados por estado con preview de proyectos | Vista general, resumen |

**Implementación:** Selector de vista (iconos o dropdown) en la barra del dashboard. La preferencia se guarda en Configuración o localStorage. Los tres componentes comparten la misma paleta y componentes (cards, botones, badges) para mantener la coherencia visual.

#### Base de datos: igual que ahora

Se mantiene la disposición actual:
- Tabs: **Administraciones** | **Comunidades** | **Contactos**
- Cada tab con su tabla y formularios (CRUD)
- Sin cambios de estructura

##### Directrices UX/UI obligatorias (calidad escritorio)

Estas directrices son **obligatorias** para la migración web y aplican a Administraciones y Comunidades:

1. **Responsive real de tabla**
   - Cabeceras y columnas deben reajustarse al redimensionar ventana.
   - No se aceptan desalineaciones entre cabecera y cuerpo.
   - Evitar efectos visuales que parezcan bugs (saltos, solapes, columnas cortadas sin control).

2. **Navegación de datos tipo escritorio**
   - Preferir scroll vertical continuo para listados largos.
   - Evitar depender de paginación para operación diaria.
   - Mantener búsqueda, orden y scroll sin romper anchuras de columna.

3. **Acciones consistentes por iconografía**
   - Acciones por fila con iconos estándar:
     - Ver: ojo
     - Editar: libreta/bolígrafo
     - Eliminar: papelera
   - Las acciones deben existir en **ambas pestañas** (Administraciones y Comunidades).

4. **Vista de detalle profesional**
   - El detalle no puede ser un formulario “simulado” de solo lectura.
   - Debe usar layout limpio, legible y corporativo.
   - Debe incluir acción de **Editar** desde el propio detalle (paridad funcional con escritorio).

5. **Paridad funcional y visual**
   - No se considera cerrada una pantalla si solo una pestaña cumple los requisitos.
   - Criterio de aceptación: Administraciones y Comunidades con el mismo nivel de calidad.

#### Pantalla principal (Main)

**Definido:**
- **Opción A:** Cards de acción (Crear presupuesto, Presupuestos existentes, Base de datos) + resumen de últimos presupuestos.
- **Gráficos:** Sí — estadísticas en Inicio (ApexCharts).
- **Sidebar:** Siempre colapsable.
- **Logo:** `resources/logo.png` (gris, rojo, azul; estilo corporativo).

---

## 3. Assets y recursos para diseño premium

### 3.1 Iconografía

| Tipo | Recomendación | Uso |
|------|---------------|-----|
| Acciones | Lucide Icons, Heroicons, Bootstrap Icons | Botones, menús, estados |
| Estados | Mismo set | PTE. PRESUPUESTAR, TERMINADO, ANULADOS |
| Categorías | Iconos para obra, cliente, admin | Dashboard, filtros |

### 3.2 Logo y branding

| Asset | Especificaciones |
|-------|------------------|
| Logo principal | SVG + PNG @2x |
| Favicon / App icon | 16, 32, 48, 192, 512 px |
| Logo dark mode | Versión para sidebar oscuro |

### 3.3 Ilustraciones (empty states)

| Situación | Uso |
|-----------|-----|
| Sin presupuestos | unDraw, Storyset — "No hay presupuestos aún" |
| Sin resultados búsqueda | Ilustración + mensaje |
| Error | Ilustración amigable + acción sugerida |

### 3.4 Tipografía

| Uso | Sugerencia |
|-----|------------|
| Títulos | Plus Jakarta Sans, DM Sans |
| Cuerpo | Inter, Source Sans 3 |
| Tablas/números | Tabular nums o JetBrains Mono |

### 3.5 Compatibilidad con Python

**Los assets web son archivos estáticos.** No dependen de Python. Si funcionan en Chrome, funcionan en Qt WebEngine. La plantilla Bootstrap es 100% compatible.

---

## 4. Compatibilidad de Qt WebEngine con assets y recursos

### 4.1 ¿Qué soporta Qt WebEngine?

| Recurso | Compatibilidad | Cómo usarlo |
|---------|----------------|-------------|
| **Imágenes (PNG, JPG, SVG, ICO)** | ✅ Total | Rutas relativas con `baseUrl`, o `qrc://` |
| **CSS** | ✅ Total | `<link href="styles/main.css">` con baseUrl correcto |
| **JavaScript** | ✅ Total | `<script src="app.js">` o inline |
| **Fuentes (TTF, OTF, WOFF)** | ✅ Total | `@font-face` en CSS |
| **Iconos (favicon, app icon)** | ✅ Total | `<link rel="icon">` en HTML |
| **Archivos locales (file://)** | ⚠️ Con restricciones | Requiere `baseUrl` en `setHtml()` o `QUrl::fromLocalFile()` |
| **Qt Resource System (qrc)** | ✅ Total | `qrc:///path/to/resource` — ideal para empaquetado |
| **Web fonts (Google Fonts, etc.)** | ✅ Total | Requiere conexión a internet |

### 4.2 Carga correcta de assets locales

**Problema común**: Las rutas relativas (`./images/logo.png`) fallan si no se especifica la base URL.

**Solución recomendada**:

```python
from pathlib import Path
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtCore import QUrl

# Opción A: setHtml con baseUrl (para HTML generado o cargado desde disco)
html_dir = Path(__file__).parent / "web" / "ui"
html_content = (html_dir / "index.html").read_text(encoding="utf-8")
base_url = QUrl.fromLocalFile(str(html_dir) + "/")
view.page().setHtml(html_content, base_url)
# Ahora <img src="images/logo.png"> y <link href="css/app.css"> funcionan
```

**Opción B: Cargar URL directa** (para desarrollo):

```python
index_path = html_dir / "index.html"
view.setUrl(QUrl.fromLocalFile(str(index_path)))
# Las rutas relativas en index.html se resuelven respecto al directorio del archivo
```

### 4.3 Qt Resource System (qrc) — máximo aprovechamiento

Para **empaquetar** la app (PyInstaller, etc.) y que los assets viajen dentro del ejecutable:

1. Crear `resources.qrc`:

```xml
<RCC>
    <qresource prefix="/">
        <file>web/ui/index.html</file>
        <file>web/ui/css/app.css</file>
        <file>web/ui/js/app.js</file>
        <file>web/ui/images/logo.png</file>
        <file>resources/icon.ico</file>
    </qresource>
</RCC>
```

2. Compilar: `pyside6-rcc resources.qrc -o resources_rc.py`

3. Cargar en la app:

```python
import resources_rc  # Registra qrc:// en Qt
view.setUrl(QUrl("qrc:/web/ui/index.html"))
```

**Ventajas**: Todo empaquetado, sin dependencia de rutas externas, funciona en cualquier SO.

### 4.4 Comunicación Python ↔ JavaScript (QWebChannel)

Para que el HTML/JS llame a la lógica Python (crear presupuesto, abrir Excel, etc.):

```python
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtCore import QObject, pyqtSlot

class AppBridge(QObject):
    @pyqtSlot(str, result=str)
    def createBudget(self, project_name):
        # Lógica Python existente
        return json.dumps({"success": True, "path": "..."})

bridge = AppBridge()
channel = QWebChannel(view.page())
channel.registerObject("app", bridge)
view.page().setWebChannel(channel)
```

En JavaScript (dentro del HTML):

```javascript
new QWebChannel(qt.webChannelTransport, (channel) => {
    const app = channel.objects.app;
    app.createBudget("Proyecto X").then(result => {
        const data = JSON.parse(result);
        console.log(data.path);
    });
});
```

**Requisito**: Inyectar el script de QWebChannel en la página. Qt lo proporciona en `qrc:///qtwebchannel/qwebchannel.js` (incluido en PySide6-WebEngine).

---

## 5. Inventario actual de la aplicación

### 5.1 Componentes de UI

| Componente | Tipo | Complejidad | Prioridad migración |
|------------|------|-------------|---------------------|
| `MainFrame` | Ventana principal | Media | 1 (primera) |
| `BudgetDashboardFrame` | Dashboard con tablas, pestañas, menús | Alta | 4 |
| `DBManagerFrame` | Gestión BD (admins, comunidades) | Alta | 5 |
| `ComunidadConfirmDialog` | Diálogo simple | Baja | 2 |
| `ComunidadFuzzySelectDialog` | Selección con lista | Media | 2 |
| `ComunidadFormDialog` | Formulario CRUD | Media | 3 |
| `AdminFormDialog` | Formulario CRUD | Media | 3 |
| `AIBudgetDialog` | Formulario + lista + IA | Alta | 4 |
| `SuggestedPartidasDialog` | Tabla + selección | Media | 3 |
| `BudgetPreviewDialog` | Vista previa + export PDF | Alta | 4 |
| `TemplateManagerDialog` | Lista + tabla + archivos | Alta | 4 |
| `DefaultPathsDialog` | Formulario rutas | Baja | 2 |
| `FichaDialog` | Vista detalle | Media | 3 |
| `_SearchSelectDialog` | Búsqueda + lista | Media | 3 |
| `_CheckSelectDialog` | Checkboxes + lista | Media | 3 |

### 5.2 Assets actuales

| Asset | Ubicación | Uso |
|-------|-----------|-----|
| `logo.png` / `icon.png` | `resources/` o raíz | Icono de ventana, branding |
| `icon.ico` | `resources/` (generado) | Windows taskbar |
| `styles.qss` | `src/gui/` | Estilos Qt (no reutilizable en Web) |
| `theme.py` | `src/gui/` | Colores, fuentes, helpers (reutilizable como variables CSS) |

### 5.3 Elementos que NO cambian (backend)

| Elemento | Motivo |
|----------|--------|
| `QMenuBar` | Se migra a HTML (header del dashboard) |
| PDF export (pywin32) | Backend Python, sin cambios |
| Excel (openpyxl, pandas) | Backend Python, sin cambios |
| SQLite / `db_repository` | Backend Python, sin cambios |
| `BudgetService`, `DatabaseService` | Lógica de negocio, sin cambios |

---

## 6. Estrategia de migración

### 6.1 Enfoque: Híbrido gradual

No migrar todo de golpe. Mantener **coexistencia** temporal de:
- **Vistas WebEngine** (donde ya se migró)
- **Código Qt antiguo** (se elimina cuando la vista equivalente esté lista)

**Objetivo final:** 100% frontend. Ningún diálogo Qt. Durante la migración, algunas vistas pueden seguir en Qt hasta tener su versión HTML.

### 6.2 Fases del plan

#### Fase 0: Preparación y plantilla (2–3 días)

| Tarea | Descripción |
|-------|-------------|
| Añadir dependencia | `PySide6-WebEngine>=6.6.0` en `requirements.txt` |
| Integrar plantilla Bootstrap | Copiar/adaptar plantilla con sidebar (AdminLTE, Tabler, CoreUI, etc.) a `web/ui/` |
| Estructura carpetas | `web/ui/css/`, `js/`, `img/`, `fonts/`, `icons/` |
| Variables CSS | Paleta premium (sidebar oscuro, acentos, estados) en `app.css` |
| PoC mínimo | Una ventana con `QWebEngineView` mostrando la plantilla con sidebar |
| QWebChannel | Verificar carga de `qwebchannel.js` y comunicación básica |

#### Fase 1: Dashboard principal y bridge (3–5 días)

| Tarea | Descripción |
|-------|-------------|
| Implementar `WebMainFrame` | `QMainWindow` con `QWebEngineView` como central widget |
| Layout dashboard | Sidebar con navegación (Inicio, Presupuestos, Base datos, etc.) |
| Implementar `AppBridge` | Métodos: `createBudget`, `openDashboard`, `openDbManager`, `openInNewWindow`, etc. |
| Conectar navegación | Clic en sidebar → mostrar vista correspondiente o abrir en nueva ventana |
| Soporte multi-ventana | `openInNewWindow(view)` crea `QMainWindow` adicional con WebEngine |

#### Fase 2: Diálogos simples en HTML (2–3 días)

| Tarea | Descripción |
|-------|-------------|
| Modal HTML | Crear sistema de modales en JS (overlay + div) |
| `ComunidadConfirmDialog` | Versión HTML que llama a `app.confirmComunidad()` |
| `DefaultPathsDialog` | Formulario HTML, guarda vía bridge |
| Mensajes y confirmaciones | Toasts y modales HTML (sin QMessageBox) |

#### Fase 3: Dashboard y diálogos complejos (1–2 semanas)

| Tarea | Descripción |
|-------|-------------|
| `BudgetDashboardFrame` | Tabla HTML (o DataTables, AG-Grid, etc.), pestañas, filtros |
| API de datos | `AppBridge.getBudgets(folder?)` → JSON con presupuestos |
| `AIBudgetDialog` | Formulario HTML + llamada a `app.generatePartidasIA(params)` |
| `BudgetPreviewDialog` | iframe o nueva pestaña WebEngine con vista previa |
| `TemplateManagerDialog` | Lista + tabla HTML, `app.getTemplates()`, `app.addTemplate(path)` |

#### Fase 4: DB Manager y pulido (1 semana)

| Tarea | Descripción |
|-------|-------------|
| `DBManagerFrame` | Tabs HTML (Admins, Comunidades), tablas, formularios |
| Validaciones | Reutilizar `db_validations` desde Python |
| Assets finales | qrc para empaquetado, iconos, fuentes |
| Tests | Verificar flujos completos |

#### Fase 5: Empaquetado y documentación (2–3 días)

| Tarea | Descripción |
|-------|-------------|
| qrc y PyInstaller | Incluir `web/`, `resources/` en el ejecutable |
| WebEngine en PyInstaller | Añadir `--collect-all PySide6` o datos de WebEngine |
| Documentación | README actualizado, guía de desarrollo UI |

---

## 7. Consideraciones técnicas

### 7.1 Seguridad

- **Content Security Policy**: Opcional para restringir scripts externos.
- **Orígenes**: Las páginas cargadas desde `file://` o `qrc://` tienen acceso a `QWebChannel`; no exponer datos sensibles sin validar.
- **No cargar HTML de fuentes no confiables** (solo archivos locales o qrc).

### 7.2 Rendimiento

- **Chromium embebido**: Aumenta el tamaño del ejecutable (~50–100 MB adicionales).
- **Memoria**: WebEngine usa más RAM que widgets Qt puros.
- **Inicio**: Puede ser 1–2 s más lento la primera vez.

### 7.3 Limitaciones conocidas

| Limitación | Mitigación |
|------------|------------|
| Selección de archivos | `<input type="file">` en el frontend; contenido en base64 al bridge |
| Arrastrar archivos al navegador | `QWebEngineView` puede recibir drops; configurar `acceptDrops` |
| Impresión nativa | `QWebEnginePage.print()` o `QPrinter` |
| Clipboard | Funciona igual que en navegador estándar |

### 7.4 Dependencias adicionales

```
# requirements.txt
PySide6>=6.6.0
PySide6-WebEngine>=6.6.0  # Añadir
# ... resto igual
```

---

## 8. Estructura de carpetas propuesta

```
ProyectoJose/
├── main.py
├── src/
│   ├── gui/
│   │   ├── main_frame.py          # Fallback Qt (eliminar al final)
│   │   ├── web_main_frame.py     # NUEVO: MainFrame con WebEngine
│   │   ├── web_window.py         # NUEVO: Ventana auxiliar (multi-window)
│   │   ├── app_bridge.py         # NUEVO: QObject para QWebChannel
│   │   ├── theme.py              # Mantener (diálogos Qt)
│   │   ├── styles.qss            # Mantener (diálogos Qt)
│   │   └── ...
│   └── core/                     # Sin cambios
├── web/                          # NUEVO — UI premium
│   └── ui/
│       ├── index.html            # Dashboard principal (sidebar + contenido)
│       ├── css/
│       │   ├── variables.css    # Paleta centralizada (única fuente de verdad)
│       │   ├── bootstrap.min.css
│       │   ├── bootstrap-icons.css
│       │   ├── app.css          # Importa variables, overrides
│       │   └── components.css
│       ├── js/
│       │   ├── qwebchannel.js    # Copia o qrc
│       │   ├── app.js            # Navegación, bridge, lógica
│       │   └── views/            # Por sección si se usa SPA
│       ├── img/
│       │   ├── logo.svg
│       │   ├── empty-state.svg
│       │   └── ...
│       ├── icons/                # SVG o sprite
│       └── fonts/                # Si no se usan Google Fonts
├── resources/
│   ├── icon.ico
│   └── logo.png
└── resources.qrc                 # Para empaquetado
```

---

## 9. Ejemplo de código: PoC Fase 0

### `web/ui/index.html`

```html
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>cubiApp</title>
    <link rel="stylesheet" href="css/app.css">
</head>
<body>
    <div class="container">
        <header>
            <img src="images/logo.png" alt="cubiApp" class="logo">
            <h1>cubiApp</h1>
            <p class="subtitle">Gestión de presupuestos</p>
        </header>
        <div class="actions">
            <button id="btn-create" class="btn-primary">+ Crear nuevo presupuesto</button>
            <button id="btn-dashboard" class="btn-secondary">Presupuestos existentes</button>
            <button id="btn-db" class="btn-secondary">Gestionar base de datos</button>
        </div>
        <footer>versión 1.0</footer>
    </div>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <script src="js/app.js"></script>
</body>
</html>
```

### `web/ui/js/app.js`

```javascript
document.addEventListener("DOMContentLoaded", () => {
    new QWebChannel(qt.webChannelTransport, (channel) => {
        const app = channel.objects.app;

        document.getElementById("btn-create").onclick = () => {
            app.createBudget().then(result => {
                const data = JSON.parse(result);
                if (data.success) alert("Presupuesto creado: " + data.path);
                else alert("Error: " + data.error);
            });
        };

        document.getElementById("btn-dashboard").onclick = () => app.openDashboard();
        document.getElementById("btn-db").onclick = () => app.openDbManager();
    });
});
```

### `src/gui/web_main_frame.py` (esqueleto)

```python
from pathlib import Path
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel

from src.gui.app_bridge import AppBridge

WEB_UI_DIR = Path(__file__).parent.parent.parent / "web" / "ui"

class WebMainFrame(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("cubiApp")
        self.resize(520, 520)

        self._view = QWebEngineView()
        self._view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False
        )

        bridge = AppBridge(self)
        channel = QWebChannel(self._view.page())
        channel.registerObject("app", bridge)
        self._view.page().setWebChannel(channel)

        index_path = WEB_UI_DIR / "index.html"
        self._view.setUrl(QUrl.fromLocalFile(str(index_path)))

        self.setCentralWidget(self._view)
```

---

## 10. Estado del plan: cerrado vs pendiente

### ✅ Cerrado (definido y acordado)

| Tema | Decisión |
|------|----------|
| Arquitectura | Frontend = app principal. Python = backend puro. Sin Qt dialogs. |
| Comunicación | JSON vía QWebChannel. Frontend envía, Python responde. |
| Archivos | `<input type="file">` para abrir. Ruta por defecto (Config) para crear. |
| Mensajes/errores | Modales y toasts HTML (no QMessageBox). |
| Multi-ventana | Sí. Botón "Abrir en nueva ventana" opcional. |
| Dashboard presupuestos | Flexible: 3 vistas (pestañas, sidebar+tabla, cards). Usuario elige. |
| Base de datos | Igual que ahora + directrices UX obligatorias: responsive real, scroll continuo, iconos de acción y detalle profesional con editar. |
| Paleta | Empresarial: sidebar #1a2332, acento #1565c0, fondo #e8eef4. |
| Main/Inicio | Cards de acción + resumen + gráficos. Sidebar siempre colapsable. Logo: resources/logo.png. |
| Estructura carpetas | `web/ui/` con css, js, img, icons, fonts. |

### ⏳ Pendiente (por cerrar)

| Tema | Opciones | Cuándo |
|------|----------|--------|
| **Plantilla Bootstrap** | AdminLTE, Tabler, CoreUI, la que descargues | Antes de Fase 0 |
| **Pantalla Main** | ✅ Cerrado: cards de acción + gráficos + resumen. Sidebar siempre colapsable. Logo en resources/logo.png. |
| **Manejo de errores** | Toast vs modal para errores | Fase 2 (bajo impacto) |
| **Estados de carga** | Spinner, skeleton, texto | Fase 3 (bajo impacto) |
| **Preferencia vista dashboard** | localStorage vs Settings (bridge) | Fase 3 |

### 📋 Checklist antes de empezar

- [ ] Plantilla Bootstrap elegida e integrada
- [ ] Aceptar aumento de tamaño ejecutable (~50–100 MB)
- [ ] Aceptar migración gradual (coexistencia temporal)
- [ ] qrc para empaquetado o cargar desde disco en desarrollo

---

## 11. Referencias

- [Qt WebEngine Overview](https://doc.qt.io/qt-6/qtwebengine-overview.html)
- [QWebChannel](https://doc.qt.io/qt-6/qwebchannel.html) — comunicación Python ↔ JS
- [PySide6-WebEngine](https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineWidgets/)
- [Proper way to display local images in QtWebEngineView](https://forum.qt.io/topic/119534/) — baseUrl y assets
