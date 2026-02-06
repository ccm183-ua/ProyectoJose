"""
Tema visual moderno para cubiApp (wxPython).
Diseño minimalista, limpio y profesional.
"""

import wx
import sys

# === COLORES - Paleta moderna tipo Notion/Linear ===
# Fondos
BG_PRIMARY = wx.Colour(255, 255, 255)      # Blanco puro
BG_SECONDARY = wx.Colour(247, 247, 248)    # Gris muy sutil
BG_CARD = wx.Colour(255, 255, 255)         # Blanco para cards
BG_HOVER = wx.Colour(243, 244, 246)        # Hover sutil

# Texto
TEXT_PRIMARY = wx.Colour(17, 24, 39)       # Negro suave
TEXT_SECONDARY = wx.Colour(107, 114, 128)  # Gris medio
TEXT_MUTED = wx.Colour(156, 163, 175)      # Gris claro

# Acentos - Azul profesional
ACCENT_PRIMARY = wx.Colour(79, 70, 229)    # Indigo moderno
ACCENT_LIGHT = wx.Colour(238, 242, 255)    # Indigo muy claro
ACCENT_HOVER = wx.Colour(67, 56, 202)      # Indigo oscuro

# Estados
SUCCESS = wx.Colour(16, 185, 129)          # Verde esmeralda
WARNING = wx.Colour(245, 158, 11)          # Ámbar
ERROR = wx.Colour(239, 68, 68)             # Rojo

# Bordes
BORDER_LIGHT = wx.Colour(229, 231, 235)    # Borde sutil
BORDER_DEFAULT = wx.Colour(209, 213, 219)  # Borde normal
BORDER_FOCUS = wx.Colour(79, 70, 229)      # Borde focus (accent)


# === FUENTES ===
def get_font_family():
    """Obtiene la mejor fuente disponible según el sistema."""
    if sys.platform == "win32":
        return "Segoe UI"
    elif sys.platform == "darwin":
        return "SF Pro Display"
    return "sans-serif"

def get_font_normal(size=10):
    """Fuente normal."""
    font = wx.Font(size, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
    font.SetFaceName(get_font_family())
    return font

def get_font_medium(size=10):
    """Fuente medium weight."""
    font = wx.Font(size, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_MEDIUM)
    font.SetFaceName(get_font_family())
    return font

def get_font_bold(size=10):
    """Fuente en negrita."""
    font = wx.Font(size, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
    font.SetFaceName(get_font_family())
    return font

def get_font_title(size=20):
    """Fuente para títulos."""
    font = wx.Font(size, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
    font.SetFaceName(get_font_family())
    return font

def get_font_subtitle(size=13):
    """Fuente para subtítulos."""
    font = wx.Font(size, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
    font.SetFaceName(get_font_family())
    return font


# === APLICAR TEMA ===
def apply_theme_to_panel(panel):
    """Aplica el tema a un panel."""
    panel.SetBackgroundColour(BG_PRIMARY)
    panel.SetForegroundColour(TEXT_PRIMARY)
    panel.SetFont(get_font_normal(10))

def apply_theme_to_frame(frame):
    """Aplica el tema a un frame completo."""
    frame.SetBackgroundColour(BG_PRIMARY)
    frame.SetForegroundColour(TEXT_PRIMARY)
    frame.SetFont(get_font_normal(10))

def apply_theme_to_dialog(dialog):
    """Aplica el tema a un diálogo."""
    dialog.SetBackgroundColour(BG_PRIMARY)
    dialog.SetForegroundColour(TEXT_PRIMARY)
    dialog.SetFont(get_font_normal(10))


def style_button_primary(btn):
    """Estilo para botón principal (acento)."""
    btn.SetBackgroundColour(ACCENT_PRIMARY)
    btn.SetForegroundColour(wx.WHITE)
    btn.SetFont(get_font_medium(10))

def style_button_secondary(btn):
    """Estilo para botón secundario."""
    btn.SetBackgroundColour(BG_PRIMARY)
    btn.SetForegroundColour(TEXT_PRIMARY)
    btn.SetFont(get_font_normal(10))

def style_button_ghost(btn):
    """Estilo para botón fantasma (solo texto)."""
    btn.SetBackgroundColour(BG_PRIMARY)
    btn.SetForegroundColour(ACCENT_PRIMARY)
    btn.SetFont(get_font_medium(10))

def style_title(label):
    """Estilo para etiqueta de título."""
    label.SetFont(get_font_title(22))
    label.SetForegroundColour(TEXT_PRIMARY)

def style_subtitle(label):
    """Estilo para subtítulo."""
    label.SetFont(get_font_subtitle(13))
    label.SetForegroundColour(TEXT_SECONDARY)

def style_listctrl(listctrl):
    """Estilo para ListCtrl."""
    listctrl.SetBackgroundColour(BG_CARD)
    listctrl.SetForegroundColour(TEXT_PRIMARY)
    listctrl.SetFont(get_font_normal(10))

def style_notebook(notebook):
    """Estilo para Notebook (pestañas)."""
    notebook.SetBackgroundColour(BG_SECONDARY)
    notebook.SetForegroundColour(TEXT_PRIMARY)
    notebook.SetFont(get_font_medium(10))

def style_textctrl(textctrl):
    """Estilo para campos de texto."""
    textctrl.SetBackgroundColour(BG_CARD)
    textctrl.SetForegroundColour(TEXT_PRIMARY)
    textctrl.SetFont(get_font_normal(10))


# === CREAR WIDGETS CON ESTILO ===
def create_styled_button(parent, label, size=(200, 42), primary=False):
    """Crea un botón con estilo moderno."""
    btn = wx.Button(parent, label=label, size=size)
    if primary:
        style_button_primary(btn)
    else:
        style_button_secondary(btn)
    return btn

def create_styled_title(parent, text):
    """Crea un título con estilo."""
    label = wx.StaticText(parent, label=text)
    style_title(label)
    return label

def create_styled_subtitle(parent, text):
    """Crea un subtítulo con estilo."""
    label = wx.StaticText(parent, label=text)
    style_subtitle(label)
    return label

def create_section_header(parent, text):
    """Crea un header de sección."""
    label = wx.StaticText(parent, label=text)
    label.SetFont(get_font_bold(11))
    label.SetForegroundColour(TEXT_PRIMARY)
    return label

def create_separator(parent):
    """Crea una línea separadora sutil."""
    line = wx.StaticLine(parent, style=wx.LI_HORIZONTAL)
    return line

def create_card_panel(parent):
    """Crea un panel tipo card con fondo blanco."""
    panel = wx.Panel(parent)
    panel.SetBackgroundColour(BG_CARD)
    return panel
