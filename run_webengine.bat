@echo off
REM cubiApp - Qt WebEngine (UI web con Metronic).

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo No se encontro .venv. Ejecuta: python -m venv .venv
    echo Luego: .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

.venv\Scripts\python.exe main_webengine.py
pause
