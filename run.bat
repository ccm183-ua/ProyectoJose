@echo off
REM Script simple para ejecutar la aplicación (Windows)
REM La configuración de Qt se hace automáticamente en main.py

cd /d "%~dp0"

REM Verificar entorno virtual
if not exist ".venv\Scripts\python.exe" (
    echo ❌ Error: No se encontró el entorno virtual (.venv)
    echo    Ejecuta: python -m venv .venv
    pause
    exit /b 1
)

REM Ejecutar aplicación (todo se configura automáticamente)
.venv\Scripts\python.exe main.py

pause
