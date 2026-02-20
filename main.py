#!/usr/bin/env python3
"""
Punto de entrada principal de cubiApp (app de escritorio con PySide6).
"""

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QLibraryInfo, QLocale, Qt, QTranslator
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication

from src.gui.main_frame_wx import MainFrame
from src.gui import theme

APP_BASE = Path(__file__).resolve().parent
APP_ID = "cubiApp.Presupuestos.1.0"


def setup_windows_app_id():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass


def get_logo_path():
    for name in ("resources/logo.png", "resources/icon.png", "logo.png", "icon.png"):
        p = APP_BASE / name
        if p.exists():
            return p
    return None


def get_or_create_ico():
    ico_in_resources = APP_BASE / "resources" / "icon.ico"
    if ico_in_resources.exists():
        return str(ico_in_resources)
    logo_path = get_logo_path()
    if not logo_path:
        return None
    try:
        from PIL import Image
        img = Image.open(str(logo_path)).convert("RGBA")
        ico_path = str(APP_BASE / "resources" / "icon.ico")
        sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
        img.save(ico_path, format='ICO', sizes=sizes)
        return ico_path
    except Exception as e:
        logging.getLogger(__name__).debug("Error creando .ico: %s", e)
        return None


def build_app_icon() -> QIcon:
    """Construye el QIcon de la aplicación."""
    icon = QIcon()
    if sys.platform == "win32":
        ico_path = get_or_create_ico()
        if ico_path and os.path.exists(ico_path):
            icon = QIcon(ico_path)
            if not icon.isNull():
                return icon
    logo_path = get_logo_path()
    if logo_path:
        try:
            pix = QPixmap(str(logo_path))
            if not pix.isNull():
                icon = QIcon(pix)
        except Exception as e:
            logging.getLogger(__name__).debug("Error cargando icono: %s", e)
    return icon


def _setup_logging():
    log_dir = APP_BASE / ".cubiapp_logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "cubiapp.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )


def main():
    _setup_logging()
    setup_windows_app_id()

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    app = QApplication(sys.argv)
    app.setApplicationName("cubiApp")
    app.setFont(theme.create_font(11))

    translator = QTranslator(app)
    translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if translator.load(QLocale(QLocale.Language.Spanish), "qtbase", "_", translations_path):
        app.installTranslator(translator)

    theme.load_stylesheet()

    app_icon = build_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    frame = MainFrame()
    frame.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
