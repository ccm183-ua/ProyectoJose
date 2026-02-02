#!/usr/bin/env python3
"""
Punto de entrada principal de la aplicación cubiApp.
En macOS ejecuta siempre con: ./run.sh
"""

import os
import sys
from pathlib import Path

# En macOS, forzar ruta de plugins de Qt para que encuentre "cocoa" (antes de cargar Qt)
if sys.platform == "darwin":
    try:
        import PySide6
        plugin_dir = Path(PySide6.__file__).resolve().parent / "Qt" / "plugins" / "platforms"
        if plugin_dir.is_dir():
            os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(plugin_dir))
    except Exception:
        pass

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from src.gui.main_window import MainWindow


def main():
    """Función principal que inicia la aplicación."""
    app = QApplication(sys.argv)
    app.setApplicationName("cubiApp")

    # Icono de la app: guarda tu logo como icon.png o logo.png en la raíz o en resources/
    base = Path(__file__).resolve().parent
    for name in ("icon.png", "logo.png", "icon.ico", "icon.icns", "resources/icon.png", "resources/logo.png"):
        path = base / name
        if path.exists():
            app.setWindowIcon(QIcon(str(path)))
            break

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
