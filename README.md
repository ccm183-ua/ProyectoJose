# Aplicación de Gestión y Edición de Presupuestos (Excel)

Aplicación de escritorio desarrollada en Python con PySide6 (Qt) para la gestión y edición de presupuestos en formato Excel.

## 🚀 Características

- Creación de presupuestos desde plantilla predefinida
- Navegación completa por carpetas del sistema
- Gestión automática de carpetas y subcarpetas
- Validación de datos de entrada
- Rellenado automático de plantillas Excel
- Interfaz gráfica intuitiva
- **Funciona en macOS y Windows sin configuración adicional**

## 📋 Requisitos

- Python 3.10 o superior
- pip (gestor de paquetes de Python)

## 🔧 Instalación

### Paso 1: Clonar o descargar el repositorio

```bash
git clone <url-del-repositorio>
cd ProyectoJose
```

### Paso 2: Crear entorno virtual

**En macOS/Linux:**
```bash
python3 -m venv .venv
```

**En Windows:**
```bash
python -m venv .venv
```

### Paso 3: Activar el entorno virtual

**En macOS/Linux:**
```bash
source .venv/bin/activate
```

**En Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**En Windows (CMD):**
```cmd
.venv\Scripts\activate.bat
```

### Paso 4: Instalar dependencias

```bash
pip install -r requirements.txt
```

**Nota:** PySide6 se instala con `pip install -r requirements.txt` y funciona en macOS y Windows sin configuración adicional.

## ▶️ Ejecución

### En macOS/Linux

```bash
./run.sh
```

### En Windows

```cmd
run.bat
```

### Ejecución directa

```bash
python main.py
```

## 🛠️ Solución de Problemas

### Error: "ModuleNotFoundError" al ejecutar

Asegúrate de usar el script `run.sh` (macOS/Linux) o `run.bat` (Windows), o activa el entorno virtual antes de ejecutar.

### Error al instalar o al ejecutar (macOS / plugin Qt)

Si ves errores de Qt o "platform plugin", usa un entorno limpio:

```bash
# Borrar el entorno virtual anterior
rm -rf .venv

# Crear uno nuevo e instalar
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Ejecutar
./run.sh
```

Siempre ejecuta la app con `./run.sh` (no hace falta activar el venv a mano).

## 📁 Estructura del Proyecto

```
ProyectoJose/
├── src/              # Código fuente principal
│   ├── core/         # Lógica de negocio
│   ├── gui/          # Interfaz gráfica
│   ├── models/       # Modelos de datos
│   └── utils/        # Utilidades
├── tests/            # Tests unitarios e integración
├── templates/        # Plantillas Excel
├── main.py           # Punto de entrada
├── run.sh            # Script de ejecución (macOS/Linux)
└── run.bat           # Script de ejecución (Windows)
```

## 📝 Licencia

Este proyecto es de uso privado.
