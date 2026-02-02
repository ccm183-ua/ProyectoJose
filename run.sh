#!/bin/bash
# Ejecutar la aplicación: ./run.sh

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "❌ No se encontró .venv."
    echo "   Crea uno: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# En macOS, que Qt encuentre el plugin "cocoa" (evita "Could not find the Qt platform plugin")
if [ "$(uname)" = "Darwin" ]; then
    PLUGIN_DIR=$(.venv/bin/python -c "
from pathlib import Path
try:
    import PySide6
    p = Path(PySide6.__file__).resolve().parent / 'Qt' / 'plugins' / 'platforms'
    print(p) if p.is_dir() else None
except Exception:
    pass
" 2>/dev/null | tr -d '\n')
    [ -n "$PLUGIN_DIR" ] && [ -d "$PLUGIN_DIR" ] && export QT_QPA_PLATFORM_PLUGIN_PATH="$PLUGIN_DIR"
fi

exec .venv/bin/python main.py
