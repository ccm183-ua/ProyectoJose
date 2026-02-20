#!/usr/bin/env python3
"""
Punto de entrada principal de cubiApp (app de escritorio con wxPython).
"""

import io
import logging
import os
import sys
import tempfile
from pathlib import Path

import wx
from src.gui.main_frame_wx import MainFrame


# Ruta base de la aplicación
APP_BASE = Path(__file__).resolve().parent

# ID único de la aplicación para Windows
APP_ID = "cubiApp.Presupuestos.1.0"


def setup_windows_app_id():
    """Configura el AppUserModelID para que Windows muestre el icono correcto."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception:
            pass


def get_logo_path():
    """Obtiene la ruta del logo."""
    for name in ("resources/logo.png", "resources/icon.png", "logo.png", "icon.png"):
        p = APP_BASE / name
        if p.exists():
            return p
    return None


def get_or_create_ico():
    """Obtiene o crea el archivo .ico para Windows."""
    # Primero buscar si ya existe un .ico
    ico_in_resources = APP_BASE / "resources" / "icon.ico"
    if ico_in_resources.exists():
        return str(ico_in_resources)
    
    # Si no, crear uno desde el PNG
    logo_path = get_logo_path()
    if not logo_path:
        return None
    
    try:
        from PIL import Image
        img = Image.open(str(logo_path)).convert("RGBA")
        
        # Guardar en resources para no recrearlo cada vez
        ico_path = str(APP_BASE / "resources" / "icon.ico")
        
        # Crear múltiples tamaños para el .ico
        sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
        img.save(ico_path, format='ICO', sizes=sizes)
        
        return ico_path
    except Exception as e:
        logging.getLogger(__name__).debug("Error creando .ico: %s", e)
        return None


def set_window_icon(frame):
    """Establece el icono de la ventana y barra de tareas."""
    if sys.platform == "win32":
        ico_path = get_or_create_ico()
        if ico_path and os.path.exists(ico_path):
            try:
                # Cargar como IconBundle para mejor compatibilidad
                bundle = wx.IconBundle()
                bundle.AddIcon(ico_path, wx.BITMAP_TYPE_ICO)
                if bundle.GetIconCount() > 0:
                    frame.SetIcons(bundle)
                    return
            except Exception:
                pass
            
            # Intento alternativo
            try:
                icon = wx.Icon(ico_path, wx.BITMAP_TYPE_ICO)
                if icon.IsOk():
                    frame.SetIcon(icon)
                    return
            except Exception:
                pass
    
    # Método alternativo para otros sistemas: cargar PNG
    logo_path = get_logo_path()
    if logo_path:
        try:
            from PIL import Image
            pil_img = Image.open(str(logo_path)).convert("RGBA")
            pil_img = pil_img.resize((32, 32), Image.Resampling.LANCZOS)
            
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            buf.seek(0)
            
            img = wx.Image(buf, wx.BITMAP_TYPE_PNG)
            if img.IsOk():
                bmp = wx.Bitmap(img)
                if bmp.IsOk():
                    icon = wx.Icon()
                    icon.CopyFromBitmap(bmp)
                    frame.SetIcon(icon)
        except Exception as e:
            logging.getLogger(__name__).debug("Error cargando icono: %s", e)


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

    # Configurar AppID de Windows ANTES de crear la app
    setup_windows_app_id()
    
    # Configuración de alta DPI para Windows
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    
    app = wx.App()
    
    # Crear ventana principal
    frame = MainFrame(None, title="cubiApp")
    
    # Establecer icono
    set_window_icon(frame)
    
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()
