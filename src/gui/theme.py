"""
Tema visual premium para cubiApp (wxPython).
Diseño moderno, limpio y profesional estilo app de escritorio.
"""

import wx
import sys

# === PALETA DE COLORES PREMIUM ===

# Fondos
BG_DARK = wx.Colour(15, 23, 42)           # Slate 900 - fondo oscuro
BG_PRIMARY = wx.Colour(248, 250, 252)      # Slate 50 - fondo principal claro
BG_SECONDARY = wx.Colour(241, 245, 249)    # Slate 100 - fondo secundario
BG_CARD = wx.Colour(255, 255, 255)         # Blanco puro
BG_ELEVATED = wx.Colour(255, 255, 255)     # Para elementos elevados
BG_HOVER = wx.Colour(236, 240, 245)        # Hover

# Texto
TEXT_PRIMARY = wx.Colour(15, 23, 42)       # Slate 900
TEXT_SECONDARY = wx.Colour(71, 85, 105)    # Slate 600
TEXT_TERTIARY = wx.Colour(148, 163, 184)   # Slate 400
TEXT_INVERSE = wx.Colour(248, 250, 252)    # Para fondos oscuros

# Colores de acento - Violet/Indigo moderno
ACCENT_PRIMARY = wx.Colour(99, 102, 241)   # Indigo 500
ACCENT_DARK = wx.Colour(79, 70, 229)       # Indigo 600
ACCENT_LIGHT = wx.Colour(238, 242, 255)    # Indigo 50
ACCENT_GRADIENT_START = wx.Colour(99, 102, 241)
ACCENT_GRADIENT_END = wx.Colour(139, 92, 246)  # Violet 500

# Estados
SUCCESS = wx.Colour(16, 185, 129)          # Emerald 500
SUCCESS_BG = wx.Colour(236, 253, 245)      # Emerald 50
WARNING = wx.Colour(245, 158, 11)          # Amber 500
WARNING_BG = wx.Colour(255, 251, 235)      # Amber 50
ERROR = wx.Colour(239, 68, 68)             # Red 500
ERROR_BG = wx.Colour(254, 242, 242)        # Red 50

# Bordes
BORDER_LIGHT = wx.Colour(226, 232, 240)    # Slate 200
BORDER_DEFAULT = wx.Colour(203, 213, 225)  # Slate 300
BORDER_FOCUS = ACCENT_PRIMARY

# Sombras (simuladas con colores)
SHADOW_COLOR = wx.Colour(15, 23, 42, 25)   # Slate 900 con transparencia


# === CONFIGURACIÓN DE FUENTES ===

def get_system_font():
    """Obtiene la mejor fuente del sistema."""
    if sys.platform == "win32":
        return "Segoe UI"
    elif sys.platform == "darwin":
        return "-apple-system"
    return "Ubuntu"

FONT_FAMILY = get_system_font()

def create_font(size=10, weight=wx.FONTWEIGHT_NORMAL):
    """Crea una fuente con la familia del sistema."""
    font = wx.Font(size, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, weight)
    font.SetFaceName(FONT_FAMILY)
    return font

def font_xs():
    return create_font(9)

def font_sm():
    return create_font(10)

def font_base():
    return create_font(11)

def font_lg():
    return create_font(13)

def font_xl():
    return create_font(16, wx.FONTWEIGHT_MEDIUM)

def font_2xl():
    return create_font(20, wx.FONTWEIGHT_BOLD)

def font_3xl():
    return create_font(26, wx.FONTWEIGHT_BOLD)

def font_display():
    return create_font(32, wx.FONTWEIGHT_BOLD)


# === ESPACIADO ===
SPACE_XS = 4
SPACE_SM = 8
SPACE_MD = 12
SPACE_LG = 16
SPACE_XL = 24
SPACE_2XL = 32
SPACE_3XL = 48


# === BORDES REDONDEADOS ===
RADIUS_SM = 4
RADIUS_MD = 8
RADIUS_LG = 12
RADIUS_XL = 16


# === APLICAR ESTILOS BASE ===

def style_frame(frame):
    """Aplica estilo base a un frame."""
    frame.SetBackgroundColour(BG_PRIMARY)
    frame.SetFont(font_base())

def style_panel(panel, elevated=False):
    """Aplica estilo a un panel."""
    panel.SetBackgroundColour(BG_ELEVATED if elevated else BG_PRIMARY)
    panel.SetFont(font_base())

def style_dialog(dialog):
    """Aplica estilo a un diálogo."""
    dialog.SetBackgroundColour(BG_PRIMARY)
    dialog.SetFont(font_base())


# === BOTONES ===

class ModernButton(wx.Panel):
    """Botón moderno con efectos hover."""
    
    def __init__(self, parent, label, size=(-1, 44), variant="default", on_click=None):
        super().__init__(parent, size=size)
        self.label = label
        self.variant = variant
        self.on_click = on_click
        self.hovered = False
        self.pressed = False
        
        self._setup_colors()
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_mouse_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_mouse_up)
    
    def _setup_colors(self):
        if self.variant == "primary":
            self.bg_normal = ACCENT_PRIMARY
            self.bg_hover = ACCENT_DARK
            self.fg_color = TEXT_INVERSE
        elif self.variant == "success":
            self.bg_normal = SUCCESS
            self.bg_hover = wx.Colour(5, 150, 105)
            self.fg_color = TEXT_INVERSE
        elif self.variant == "ghost":
            self.bg_normal = BG_PRIMARY
            self.bg_hover = BG_HOVER
            self.fg_color = ACCENT_PRIMARY
        else:  # default
            self.bg_normal = BG_CARD
            self.bg_hover = BG_HOVER
            self.fg_color = TEXT_PRIMARY
    
    def _on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        if not gc:
            return
        
        w, h = self.GetSize()
        
        # Color de fondo según estado
        if self.pressed:
            bg = self.bg_hover
        elif self.hovered:
            bg = self.bg_hover
        else:
            bg = self.bg_normal
        
        # Dibujar fondo redondeado - sin bordes
        gc.SetBrush(wx.Brush(bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        
        path = gc.CreatePath()
        path.AddRoundedRectangle(0, 0, w, h, RADIUS_MD)
        gc.DrawPath(path)
        
        # Dibujar texto
        gc.SetFont(font_base(), self.fg_color)
        tw, th = gc.GetTextExtent(self.label)
        gc.DrawText(self.label, (w - tw) / 2, (h - th) / 2)
    
    def _on_enter(self, event):
        self.hovered = True
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.Refresh()
    
    def _on_leave(self, event):
        self.hovered = False
        self.pressed = False
        self.Refresh()
    
    def _on_mouse_down(self, event):
        self.pressed = True
        self.Refresh()
    
    def _on_mouse_up(self, event):
        if self.pressed and self.hovered:
            if self.on_click:
                self.on_click()
        self.pressed = False
        self.Refresh()


def create_button(parent, label, size=(-1, 44), variant="default", on_click=None):
    """Crea un botón moderno."""
    return ModernButton(parent, label, size, variant, on_click)


# === CARDS ===

class Card(wx.Panel):
    """Panel tipo tarjeta con sombra sutil."""
    
    def __init__(self, parent, padding=SPACE_LG):
        super().__init__(parent)
        self.padding = padding
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        
        # Sizer interno con padding
        self.inner_sizer = wx.BoxSizer(wx.VERTICAL)
        outer_sizer = wx.BoxSizer(wx.VERTICAL)
        outer_sizer.Add(self.inner_sizer, 1, wx.EXPAND | wx.ALL, padding)
        self.SetSizer(outer_sizer)
    
    def _on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        if not gc:
            return
        
        w, h = self.GetSize()
        
        # Sombra sutil
        gc.SetBrush(wx.Brush(wx.Colour(0, 0, 0, 8)))
        gc.SetPen(wx.TRANSPARENT_PEN)
        path = gc.CreatePath()
        path.AddRoundedRectangle(2, 3, w-4, h-4, RADIUS_LG)
        gc.DrawPath(path)
        
        # Fondo blanco
        gc.SetBrush(wx.Brush(BG_CARD))
        gc.SetPen(wx.Pen(BORDER_LIGHT, 1))
        path = gc.CreatePath()
        path.AddRoundedRectangle(0, 0, w-1, h-2, RADIUS_LG)
        gc.DrawPath(path)
    
    def GetInnerSizer(self):
        return self.inner_sizer


# === TEXTOS ===

def create_title(parent, text, size="2xl"):
    """Crea un título estilizado."""
    label = wx.StaticText(parent, label=text)
    if size == "display":
        label.SetFont(font_display())
    elif size == "3xl":
        label.SetFont(font_3xl())
    elif size == "2xl":
        label.SetFont(font_2xl())
    elif size == "xl":
        label.SetFont(font_xl())
    else:
        label.SetFont(font_lg())
    label.SetForegroundColour(TEXT_PRIMARY)
    return label

def create_subtitle(parent, text):
    """Crea un subtítulo."""
    label = wx.StaticText(parent, label=text)
    label.SetFont(font_lg())
    label.SetForegroundColour(TEXT_SECONDARY)
    return label

def create_text(parent, text, muted=False):
    """Crea texto normal."""
    label = wx.StaticText(parent, label=text)
    label.SetFont(font_base())
    label.SetForegroundColour(TEXT_TERTIARY if muted else TEXT_SECONDARY)
    return label

def create_caption(parent, text):
    """Crea texto pequeño."""
    label = wx.StaticText(parent, label=text)
    label.SetFont(font_sm())
    label.SetForegroundColour(TEXT_TERTIARY)
    return label


# === LISTAS ===

def style_listctrl(listctrl):
    """Aplica estilo a un ListCtrl."""
    listctrl.SetBackgroundColour(BG_CARD)
    listctrl.SetForegroundColour(TEXT_PRIMARY)
    listctrl.SetFont(font_base())


# === INPUTS ===

def style_textctrl(textctrl):
    """Aplica estilo a un TextCtrl."""
    textctrl.SetBackgroundColour(BG_CARD)
    textctrl.SetForegroundColour(TEXT_PRIMARY)
    textctrl.SetFont(font_base())


# === SEPARADORES ===

def create_divider(parent, vertical=False):
    """Crea un separador."""
    style = wx.LI_VERTICAL if vertical else wx.LI_HORIZONTAL
    line = wx.StaticLine(parent, style=style)
    return line


# === BADGES ===

class Badge(wx.Panel):
    """Badge/etiqueta pequeña."""
    
    def __init__(self, parent, text, variant="default"):
        super().__init__(parent)
        self.text = text
        self.variant = variant
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        
        # Calcular tamaño
        dc = wx.ClientDC(self)
        dc.SetFont(font_xs())
        tw, th = dc.GetTextExtent(text)
        self.SetMinSize((tw + 16, th + 8))
    
    def _on_paint(self, event):
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        if not gc:
            return
        
        w, h = self.GetSize()
        
        # Colores según variante
        if self.variant == "success":
            bg, fg = SUCCESS_BG, SUCCESS
        elif self.variant == "warning":
            bg, fg = WARNING_BG, WARNING
        elif self.variant == "error":
            bg, fg = ERROR_BG, ERROR
        elif self.variant == "primary":
            bg, fg = ACCENT_LIGHT, ACCENT_PRIMARY
        else:
            bg, fg = BG_SECONDARY, TEXT_SECONDARY
        
        # Fondo
        gc.SetBrush(wx.Brush(bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        path = gc.CreatePath()
        path.AddRoundedRectangle(0, 0, w, h, h/2)
        gc.DrawPath(path)
        
        # Texto
        gc.SetFont(font_xs(), fg)
        tw, th = gc.GetTextExtent(self.text)
        gc.DrawText(self.text, (w - tw) / 2, (h - th) / 2)


# === NOTEBOOK/TABS ===

def style_notebook(notebook):
    """Aplica estilo a un Notebook."""
    notebook.SetBackgroundColour(BG_SECONDARY)
    notebook.SetForegroundColour(TEXT_PRIMARY)
    notebook.SetFont(font_base())


# === TOOLBAR ===

def create_toolbar_panel(parent):
    """Crea un panel de toolbar."""
    toolbar = wx.Panel(parent)
    toolbar.SetBackgroundColour(BG_SECONDARY)
    return toolbar


# === HELPERS / COMPATIBILIDAD ===

def get_font_normal(size=11):
    """Compatibilidad con código antiguo."""
    return create_font(size)

def get_font_medium(size=11):
    """Compatibilidad con código antiguo."""
    return create_font(size, wx.FONTWEIGHT_MEDIUM)

def get_font_bold(size=11):
    """Compatibilidad con código antiguo."""
    return create_font(size, wx.FONTWEIGHT_BOLD)

def get_font_title(size=20):
    """Compatibilidad con código antiguo."""
    return create_font(size, wx.FONTWEIGHT_BOLD)

def get_font_subtitle(size=13):
    """Compatibilidad con código antiguo."""
    return create_font(size)

# Funciones de compatibilidad para código antiguo
def apply_theme_to_frame(frame):
    """Alias para style_frame."""
    style_frame(frame)

def apply_theme_to_panel(panel):
    """Alias para style_panel."""
    style_panel(panel)

def apply_theme_to_dialog(dialog):
    """Alias para style_dialog."""
    style_dialog(dialog)

def create_styled_title(parent, text):
    """Alias para create_title con tamaño xl."""
    return create_title(parent, text, "xl")

def style_button_primary(btn):
    """Estiliza un botón como primario."""
    btn.SetBackgroundColour(ACCENT_PRIMARY)
    btn.SetForegroundColour(TEXT_INVERSE)
    btn.SetFont(get_font_medium())

# Color de texto para compatibilidad
TEXT_MUTED = TEXT_TERTIARY
