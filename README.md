# cubiApp – Gestión de presupuestos (Excel)

Aplicación **de escritorio** en Python con **PySide6**. Abrir/crear presupuestos Excel, gestionar la base de datos (Administración, Comunidad, Contacto) y generar partidas con IA (Gemini o DeepSeek) apoyándose en memoria histórica. Funciona en **Windows** (entorno auditado) y macOS.

## Requisitos

- **Python 3.11** (fijado: el código usa sintaxis de unión de tipos `X | None`, que requiere 3.10+; 3.11 es el entorno auditado y recomendado).
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

- **Abrir presupuesto** y **Crear nuevo presupuesto** (desde la plantilla en `templates/`, con datos y opción de carpetas).
- **Describir la obra en lenguaje natural** (texto o dictado) y dejar que el orquestador combine partidas del histórico con generación por IA para los huecos.
- **Gestionar base de datos:** pestañas Administración, Comunidad, Contacto (añadir, editar, eliminar).
- **Memoria histórica:** analizar carpetas de presupuestos antiguos para alimentar sugerencias futuras.

## Rutas y variables de entorno

La plantilla Excel (`templates/122-20 PLANTILLA PRESUPUESTO.xlsx`) está versionada en el repositorio; no requiere configuración.

| Variable | Descripción | Prioridad / valor por defecto |
|---|---|---|
| `CUBIAPP_GEMINI_KEY` | API key de Google Gemini. | Variable de entorno > configuración local guardada desde la app. |
| `CUBIAPP_DEEPSEEK_KEY` | API key de DeepSeek (proveedor alternativo). | Igual que Gemini. |
| `CUBIAPP_DB_PATH` | Ruta absoluta a la base de datos SQLite. | Ruta guardada en Settings > `CUBIAPP_DB_PATH` > `~/Documents/CubiApp/datos.db` > `datos.db` en la raíz del proyecto (solo si la ruta estable no existe y ese fichero legacy contiene memoria histórica ya analizada). |
| `CUBIAPP_CONFIG_DIR` | Carpeta de configuración local (claves, rutas por defecto). | `~/.cubiapp` |
| `CUBIAPP_BACKUP_DIR` | Carpeta de backups automáticos de la BDD. | `~/Documents/CubiApp/backups` |

Consulta `.env.example` para ejemplos.

## Tests

```bash
# Suite completa
.venv/bin/python -m pytest

# Con cobertura
.venv/bin/python -m pytest --cov=src --cov-report=term-missing
```

**Windows:**

```cmd
.venv\Scripts\python -m pytest
```

La suite es portable: la automatización de Excel vía COM (`pywin32`, usada solo en exportación a PDF) está siempre mockeada en los tests, así que no requiere Windows real ni Excel instalado para pasar. Se ejecuta igual en CI (`.github/workflows/tests.yml`, `windows-latest`) que en local.

**Dependencias opcionales de tests:**

- `PySide6` es obligatoria (está en `requirements.txt`); sin ella, los tests de diálogos se omiten (`PySide6 no disponible`) en vez de fallar.
- `SpeechRecognition` + `PyAudio` (dictado por voz) son opcionales: si no están instaladas o no hay micrófono, el test de disponibilidad pasa comprobando el mensaje de error correcto; si SÍ hay micrófono y dependencias, ese test se omite a propósito (transcribir audio real no es automatizable) y queda cubierto por el checklist manual.
- Un par de tests de plantilla se omiten solo si `templates/122-20 PLANTILLA PRESUPUESTO.xlsx` no está presente (protección ante clon incompleto o LFS sin descargar); en un clon normal del repositorio no deberían omitirse nunca.

**Checklist manual** (lo que la suite automática no puede cubrir: diálogos nativos de guardar/abrir, Excel real abierto por el usuario): ver `docs/CHECKLIST_MANUAL_EXCEL.md`.

## Si algo falla

- **"No se encontró .venv"** → Crea el entorno e instala: `python3 -m venv .venv` y `pip install -r requirements.txt`.
- **PySide6 no arranca en Linux/CI sin pantalla** → los tests fuerzan `QT_QPA_PLATFORM=offscreen` automáticamente; para ejecutar la app real necesitas una sesión gráfica.
- **Dictado por voz no disponible** → instala `SpeechRecognition` y `PyAudio` en el mismo Python que ejecuta la app; ver el aviso de la propia app (Ajustes > IA) para el detalle exacto del error.
