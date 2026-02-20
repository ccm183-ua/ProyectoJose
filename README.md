# cubiApp – Gestión de presupuestos (Excel)

Aplicación **de escritorio** en Python con **wxPython**. Abrir/crear presupuestos Excel y gestionar la base de datos (Administración, Comunidad, Contacto). Funciona en **Windows y macOS** sin plugins de Qt ni Tcl/Tk del sistema.

## Requisitos

- Python 3.8+
- pip

## Instalación (una vez)

```bash
cd ProyectoJose
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Windows:**

```cmd
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Ejecución

**macOS / Linux:** `./run.sh`  
**Windows:** `run.bat`

Se abre la ventana de la aplicación.

## Qué hace la app

- **Abrir presupuesto** y **Crear nuevo presupuesto** (desde plantilla, con datos y opción de carpetas).
- **Gestionar base de datos:** pestañas Administración, Comunidad, Contacto (añadir, editar, eliminar). Base de datos en `~/Documents/cubiApp/datos.db` (o variable de entorno `CUBIAPP_DB_PATH`).

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `CUBIAPP_GEMINI_KEY` | API key de Google Gemini para generar partidas con IA. También configurable desde la app. |
| `CUBIAPP_DB_PATH` | Ruta personalizada para la base de datos SQLite. Por defecto: `datos.db` en la raíz del proyecto. |

Consulta `.env.example` para ejemplos.

## Tests

```bash
# Ejecutar toda la suite
.venv/bin/python -m pytest

# Con cobertura
.venv/bin/python -m pytest --cov=src --cov-report=term-missing
```

**Windows:**

```cmd
.venv\Scripts\python -m pytest
```

## Si algo falla

- **"No se encontró .venv"** → Crea el entorno e instala: `python3 -m venv .venv` y `pip install -r requirements.txt`.
- **En macOS:** si wxPython da error al instalar, prueba con `pip install --upgrade pip` y luego `pip install wxPython`. Si usas Apple Silicon (M1/M2), asegúrate de tener una versión de wxPython compatible con tu Python.
