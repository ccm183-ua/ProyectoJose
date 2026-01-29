#!/bin/bash
# Script para reinstalar PySide6 correctamente

echo "🔧 Reinstalando PySide6..."

# Activar entorno virtual
cd "$(dirname "$0")"
source .venv/bin/activate

# Limpiar instalaciones anteriores
echo "🧹 Limpiando instalaciones anteriores..."
pip uninstall -y PySide6 PySide6_Essentials PySide6_Addons shiboken6 2>/dev/null
rm -rf .venv/lib/python3.9/site-packages/PySide6* 
rm -rf .venv/lib/python3.9/site-packages/shiboken6*
rm -rf .venv/lib/python3.9/site-packages/*pyside6*

# Instalar con encoding correcto
echo "📦 Instalando PySide6..."
export PYTHONIOENCODING=utf-8
pip install --no-compile --no-cache-dir PySide6

# Verificar instalación
echo "✅ Verificando instalación..."
if [ -f ".venv/lib/python3.9/site-packages/PySide6/Qt/plugins/platforms/libqcocoa.dylib" ]; then
    echo "✓ PySide6 instalado correctamente"
    echo "✓ Plugin cocoa encontrado"
else
    echo "❌ Error: Plugin cocoa no encontrado"
    exit 1
fi

echo ""
echo "✅ PySide6 reinstalado correctamente. Puedes ejecutar ./run.sh"
