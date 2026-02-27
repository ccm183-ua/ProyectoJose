# Análisis de la plantilla Metronic (cubiApp)

## 1. Identificación

| Campo | Valor |
|-------|-------|
| **Plantilla** | Metronic |
| **Autor** | KeenThemes |
| **Framework** | Bootstrap 4 |
| **Ubicación** | `web/templates/` |
| **Versión** | HTML estático (dist/) |

---

## 2. Estructura actual

```
web/templates/
├── dist/                    # Versión compilada (la que usaremos)
│   ├── index.html          # Dashboard principal
│   ├── assets/
│   │   ├── plugins/        # jQuery, Bootstrap, plugins (bundle)
│   │   │   ├── global/     # plugins.bundle.css, plugins.bundle.js
│   │   │   └── custom/     # fullcalendar, prismjs, datatables, etc.
│   │   ├── css/
│   │   │   ├── style.bundle.css
│   │   │   └── themes/layout/   # header, aside, brand (light/dark)
│   │   └── media/          # logos, iconos SVG
│   ├── features/           # Ejemplos: tables, modals, cards, etc.
│   └── layout/             # Variantes de layout
└── src/                    # Fuentes SASS (para compilar)
    └── sass/
```

---

## 3. Layout que trae

- **Aside (sidebar):** Fijo, 265px, colapsable. Tema dark por defecto (#1e1e2d).
- **Header:** Fijo, 65px. Tema light.
- **Brand:** Logo arriba del aside. Tema dark.
- **Subheader:** Barra bajo el header (breadcrumbs, acciones).
- **Content:** Área principal.
- **Footer:** Opcional.

**Clases clave:** `aside`, `aside-menu`, `menu-nav`, `menu-item`, `menu-link`, `menu-submenu`.

---

## 4. Temas de layout (archivos CSS)

| Archivo | Uso |
|---------|-----|
| `header/base/light.css` | Header blanco |
| `header/menu/light.css` | Menú del header |
| `brand/dark.css` | Logo/barra lateral oscura |
| `aside/dark.css` | Sidebar oscuro (#1e1e2d) |

Alternativas: `aside/light.css`, `header/base/dark.css`, etc.

---

## 5. Colores por defecto (Metronic)

| Elemento | Color |
|----------|-------|
| Aside dark | #1e1e2d |
| Hover aside | #1b1b28 |
| Page background | #EEF0F8 |
| Texto aside | #a2a3b7 |
| Acento ($primary) | Definido en Bootstrap (suele ser púrpura/azul) |

---

## 6. Qué encaja con cubiApp

| Necesidad cubiApp | Metronic ofrece |
|-------------------|-----------------|
| Sidebar lateral | ✅ Aside fijo, colapsable |
| Dashboard | ✅ index.html con estructura |
| Tablas | ✅ features/bootstrap/tables.html |
| Cards | ✅ features/cards/ |
| Modales | ✅ Bootstrap modal |
| Formularios | ✅ Bootstrap forms |
| Iconos | ✅ SVG inline, Flaticon, FontAwesome |

---

## 7. Qué no necesitamos (peso innecesario)

| Plugin | Motivo |
|--------|--------|
| Fullcalendar | No usamos calendario |
| TinyMCE | No usamos editor WYSIWYG |
| Uppy | Subida de archivos — usamos `<input type="file">` |
| PrismJS | Sintaxis de código — no |
| ApexCharts/AmCharts | Solo si usamos gráficos en Inicio |
| DataTables | Útil para presupuestos — valorar |
| Google Maps | No |

---

## 8. Decisiones de diseño

### 8.1 Pantalla principal (Main)

**Opciones con Metronic:**

- **A)** Usar el `index.html` actual como Inicio: reemplazar widgets por los de cubiApp (crear presupuesto, abrir, BD).
- **B)** Crear una página de Inicio más simple: logo + 3–4 cards de acción.
- **C)** Ir directo a Presupuestos: Inicio = primera vista del dashboard.

**Recomendación:** Opción A o B: una página de Inicio con cards de acción principales (Crear presupuesto, Presupuestos existentes, Base de datos) y, si se quiere, un breve resumen de últimos presupuestos.

### 8.2 Aplicar nuestra paleta empresarial

Metronic usa CSS compilado. Para nuestra paleta (#1a2332, #1565c0, #e8eef4):

1. **Capa de override:** Crear `variables.css` o `cubi-override.css` que cargue **después** de los temas de Metronic.
2. **Sobrescribir:** Usar variables CSS o selectores específicos para cambiar el aside, acentos y fondos.

```css
/* cubi-override.css - carga después de aside/dark.css */
.aside {
  background-color: var(--sidebar-bg) !important; /* #1a2332 */
}
.aside-menu .menu-link.menu-link-active {
  background-color: var(--sidebar-active-bg) !important; /* #0d47a1 */
}
```

### 8.3 Menú del sidebar

Metronic tiene menú anidado (menu-item-submenu).

**Para cubiApp:**

```
- Inicio
- Presupuestos
- Base de datos
  - Administraciones
  - Comunidades
  - Contactos
- Plantillas
- Configuración
- Ayuda
```

Estructura similar a la actual, solo cambiar textos y enlaces.

### 8.4 Dependencias mínimas

**Archivos mínimos a copiar a `web/ui/`:**

- `plugins.bundle.css` (o un subset si se puede)
- `style.bundle.css`
- `themes/layout/` (header, aside, brand)
- `plugins.bundle.js` (jQuery + Bootstrap)
- `assets/media/logos/` (para sustituir por logo cubiApp)
- `assets/media/svg/icons/` (iconos que usemos)

---

## 9. Próximos pasos

1. **Decidir:** ¿Inicio tipo A, B o C?
2. **Paleta:** Crear `cubi-override.css` con la paleta empresarial.
3. **Menú:** Crear HTML del sidebar con las secciones de cubiApp.
4. **Simplificar:** Quitar o no cargar plugins que no usemos.
5. **PoC:** Montar una página mínima (layout + menú + área de contenido vacía) con QWebEngine.

---

## 10. Decisiones acordadas

| Pregunta | Decisión |
|----------|----------|
| **Pantalla Inicio** | **A** — Cards de acción (Crear presupuesto, Presupuestos existentes, Base de datos) + resumen |
| **Gráficos en Inicio** | **Sí** — Estadísticas/gráficos (ApexCharts de Metronic) |
| **Sidebar colapsable** | **Siempre** — Colapsable en cualquier tamaño de pantalla |
| **Logo** | **Sí** — `resources/logo.png` (gris, rojo, azul; estilo corporativo) |

### Logo cubiApp

- **Ubicación:** `resources/logo.png`
- **Estilo:** Geométrico, minimalista. Gris (estructura), rojo (línea punteada central), azul (punto superior). Fondo blanco.
- **Uso:** Sidebar (versión clara sobre fondo oscuro o invertida), header, favicon.
