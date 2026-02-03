#!/usr/bin/env python3
"""
Punto de entrada principal de cubiApp (app de escritorio con wxPython).
"""

import io
from pathlib import Path

import wx
from src.gui.main_frame_wx import MainFrame


def _pil_to_wx_icon(pil_image, size):
    """Convierte PIL Image a wx.Icon vía PNG en memoria."""
    try:
        pil = pil_image.convert("RGBA").resize((size, size))
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        buf.seek(0)
        img = wx.ImageFromStream(buf, wx.BITMAP_TYPE_PNG)
        if not img.IsOk():
            return None
        bmp = wx.Bitmap(img)
        if not bmp.IsOk():
            return None
        icon = wx.Icon()
        icon.CopyFromBitmap(bmp)
        return icon
    except Exception:
        return None


def _set_icon_safe(frame, base):
    """Carga el icono con Pillow y lo asigna al frame."""
    try:
        if hasattr(wx, "PNGHandler"):
            wx.Image.AddHandler(wx.PNGHandler())
    except Exception:
        pass
    for name in ("resources/logo.png", "resources/icon.png", "logo.png", "icon.png"):
        p = base / name
        if not p.exists():
            continue
        try:
            from PIL import Image
            pil = Image.open(str(p))
        except Exception:
            continue
        if hasattr(wx, "IconBundle"):
            bundle = wx.IconBundle()
            for size in (16, 32, 48):
                icon = _pil_to_wx_icon(pil, size)
                if icon:
                    bundle.AddIcon(icon)
            if bundle.GetIconCount() > 0 and hasattr(frame, "SetIcons"):
                frame.SetIcons(bundle)
                return
        icon = _pil_to_wx_icon(pil, 32)
        if icon and hasattr(frame, "SetIcon"):
            frame.SetIcon(icon)
            return
    return None


def main():
    app = wx.App()
    base = Path(__file__).resolve().parent
    frame = MainFrame(None, title="cubiApp")
    frame.Show()
    _set_icon_safe(frame, base)
    app.MainLoop()


if __name__ == "__main__":
    main()
