# Aplicación de Gestión y Edición de Presupuestos (Excel)

Aplicación de escritorio desarrollada en Python con PyQt6 para la gestión y edición de presupuestos en formato Excel.

## 🚀 Características

- Creación de presupuestos desde plantilla predefinida
- Navegación completa por carpetas del sistema
- Gestión automática de carpetas y subcarpetas
- Validación de datos de entrada
- Rellenado automático de plantillas Excel
- Interfaz gráfica intuitiva

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

**En macOS/Linux:**
```bash
pip install -r requirements.txt
# O si pip no está disponible:
python3 -m pip install -r requirements.txt
```

**En Windows:**
```bash
pip install -r requirements.txt
# O si pip no está disponible:
python -m pip install -r requirements.txt
```

## ▶️ Ejecución

### En macOS/Linux

**Opción 1: Con el entorno virtual activado**
```bash
source .venv/bin/activate
python main.py
```

**Opción 2: Usando la ruta completa**
```bash
.venv/bin/python main.py
```

### En Windows

**Opción 1: Con el entorno virtual activado (PowerShell)**
```powershell
.venv\Scripts\Activate.ps1
python main.py
```

**Opción 2: Con el entorno virtual activado (CMD)**
```cmd
.venv\Scripts\activate.bat
python main.py
```

**Opción 3: Usando la ruta completa**
```bash
.venv\Scripts\python main.py
```

## 🧪 Ejecutar Tests

### En macOS/Linux

**Opción 1: Con el entorno virtual activado**
```bash
source .venv/bin/activate
pytest tests/ -v
```

**Opción 2: Usando la ruta completa**
```bash
.venv/bin/python -m pytest tests/ -v
```

### En Windows

**Opción 1: Con el entorno virtual activado**
```bash
# Después de activar el entorno virtual
pytest tests/ -v
```

**Opción 2: Usando la ruta completa**
```bash
.venv\Scripts\python -m pytest tests/ -v
```

### Ejecutar tests con cobertura

**En macOS/Linux:**
```bash
.venv/bin/python -m pytest tests/ --cov=src --cov-report=html
```

**En Windows:**
```bash
.venv\Scripts\python -m pytest tests/ --cov=src --cov-report=html
```

## 📁 Estructura del Proyecto

```
presupuestos_app/
├── src/              # Código fuente principal
├── tests/            # Tests unitarios e integración
├── templates/        # Plantillas Excel
└── docs/            # Documentación
```

## 📝 Licencia

Este proyecto es de uso privado.
