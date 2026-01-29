#!/bin/bash
# Script para instalar PySide6 correctamente en el orden adecuado

echo "🔧 Instalando PySide6 correctamente..."
echo ""

cd "$(dirname "$0")"

# Activar entorno virtual si no está activado
if [ -z "$VIRTUAL_ENV" ]; then
    source .venv/bin/activate
fi

# Limpiar instalaciones anteriores
echo "🧹 Limpiando instalaciones anteriores..."
pip uninstall -y PySide6 PySide6_Essentials PySide6_Addons shiboken6 2>/dev/null
rm -rf .venv/lib/python3.9/site-packages/PySide6* 
rm -rf .venv/lib/python3.9/site-packages/shiboken6*

# Instalar en el orden correcto con encoding
echo "📦 Instalando PySide6_Essentials primero (contiene los plugins)..."
export PYTHONIOENCODING=utf-8
pip install --no-compile --no-cache-dir PySide6_Essentials==6.10.1

echo "📦 Instalando PySide6..."
pip install --no-compile --no-cache-dir PySide6==6.10.1

# Verificar instalación
echo ""
echo "✅ Verificando instalación..."
PLUGIN_PATH=".venv/lib/python3.9/site-packages/PySide6/Qt/plugins/platforms/libqcocoa.dylib"
if [ -f "$PLUGIN_PATH" ]; then
    echo "✓ PySide6 instalado correctamente"
    echo "✓ Plugin cocoa encontrado en: $PLUGIN_PATH"
    echo ""
    echo "✅ Instalación completada. Puedes ejecutar ./run.sh"
else
    echo "❌ Error: Plugin cocoa NO encontrado"
    echo "   Ruta esperada: $PLUGIN_PATH"
    exit 1
fi
