#!/usr/bin/env python3
"""
Punto de entrada principal de la aplicación de gestión de presupuestos.
"""

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    """Función principal que inicia la aplicación."""
    app = QApplication(sys.argv)
    app.setApplicationName("Gestión de Presupuestos")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
