#!/bin/bash
# Script simple para ejecutar la aplicación (macOS/Linux)
# La configuración de Qt se hace automáticamente en main.py

cd "$(dirname "$0")"

# Verificar entorno virtual
if [ ! -d ".venv" ]; then
    echo "❌ Error: No se encontró el entorno virtual (.venv)"
    echo "   Ejecuta: python3 -m venv .venv"
    exit 1
fi

# Ejecutar aplicación (todo se configura automáticamente)
.venv/bin/python main.py
