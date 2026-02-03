#!/bin/bash
# cubiApp - App de escritorio (wxPython). macOS y Windows.

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "❌ No se encontró .venv."
    echo "   Crea uno: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

exec .venv/bin/python main.py
