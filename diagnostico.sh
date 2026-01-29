#!/bin/bash
# Script de diagnóstico para identificar problemas con PySide6

echo "🔍 DIAGNÓSTICO DE PYSIDE6"
echo "=========================="
echo ""

cd "$(dirname "$0")"

# 1. Verificar Python
echo "1. Versión de Python:"
echo "   Sistema: $(python3 --version 2>&1)"
echo "   Venv:    $(.venv/bin/python --version 2>&1)"
echo ""

# 2. Verificar si está activado el venv
echo "2. Entorno virtual:"
if [ -z "$VIRTUAL_ENV" ]; then
    echo "   ⚠️  NO está activado"
    echo "   Ejecuta: source .venv/bin/activate"
else
    echo "   ✓ Activado: $VIRTUAL_ENV"
fi
echo ""

# 3. Verificar PySide6
echo "3. Instalación de PySide6:"
if .venv/bin/python -c "import PySide6" 2>/dev/null; then
    echo "   ✓ PySide6 está instalado"
    PYSIDE6_PATH=$(.venv/bin/python -c "import PySide6; import os; print(os.path.dirname(PySide6.__file__))" 2>/dev/null)
    echo "   Ubicación: $PYSIDE6_PATH"
else
    echo "   ❌ PySide6 NO está instalado"
fi
echo ""

# 4. Verificar plugins
echo "4. Plugins de plataforma:"
PLUGIN_PATH="$PYSIDE6_PATH/Qt/plugins/platforms"
if [ -d "$PLUGIN_PATH" ]; then
    echo "   ✓ Directorio existe: $PLUGIN_PATH"
    if [ -f "$PLUGIN_PATH/libqcocoa.dylib" ]; then
        echo "   ✓ Plugin cocoa encontrado"
    else
        echo "   ❌ Plugin cocoa NO encontrado"
        echo "   Archivos en platforms:"
        ls -la "$PLUGIN_PATH" 2>/dev/null | head -5
    fi
else
    echo "   ❌ Directorio NO existe: $PLUGIN_PATH"
fi
echo ""

# 5. Verificar variable de entorno
echo "5. Variable QT_PLUGIN_PATH:"
if [ -z "$QT_PLUGIN_PATH" ]; then
    echo "   ⚠️  NO está configurada"
else
    echo "   ✓ Configurada: $QT_PLUGIN_PATH"
fi
echo ""

# 6. Test de importación
echo "6. Test de importación:"
.venv/bin/python -c "from PySide6.QtWidgets import QApplication; print('   ✓ Importación exitosa')" 2>&1 | head -3
echo ""

echo "=========================="
echo "FIN DEL DIAGNÓSTICO"
