"""
Tema visual premium para cubiApp (PySide6).
Diseño moderno, limpio y profesional estilo app de escritorio.
"""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

# === PALETA DE COLORES (hex strings) ===

BG_DARK = "#0f172a"
BG_PRIMARY = "#f8fafc"
BG_SECONDARY = "#f1f5f9"
BG_CARD = "#ffffff"
BG_ELEVATED = "#ffffff"
BG_HOVER = "#ecf0f5"

TEXT_PRIMARY = "#0f172a"
TEXT_SECONDARY = "#475569"
TEXT_TERTIARY = "#94a3b8"
TEXT_INVERSE = "#f8fafc"
TEXT_MUTED = TEXT_TERTIARY

ACCENT_PRIMARY = "#6366f1"
ACCENT_DARK = "#4f46e5"
ACCENT_LIGHT = "#eef2ff"

SUCCESS = "#10b981"
SUCCESS_BG = "#ecfdf5"
WARNING = "#f59e0b"
WARNING_BG = "#fffbeb"
ERROR = "#ef4444"
ERROR_BG = "#fef2f2"

BORDER_LIGHT = "#e2e8f0"
BORDER_DEFAULT = "#cbd5e1"

# === COLORES COMO QColor (para uso programático) ===

def qcolor(hex_str: str) -> QColor:
    return QColor(hex_str)

# === CONFIGURACIÓN DE FUENTES ===

def _system_font_family() -> str:
    if sys.platform == "win32":
        return "Segoe UI"
    if sys.platform == "darwin":
        return "Helvetica Neue"
    return "Ubuntu"

FONT_FAMILY = _system_font_family()


def create_font(size: int = 10, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont(FONT_FAMILY, size)
    f.setWeight(weight)
    return f

def font_xs()   : return create_font(9)
def font_sm()   : return create_font(10)
def font_base() : return create_font(11)
def font_lg()   : return create_font(13)
def font_xl()   : return create_font(16, QFont.Weight.Medium)
def font_2xl()  : return create_font(20, QFont.Weight.Bold)
def font_3xl()  : return create_font(26, QFont.Weight.Bold)
def font_display(): return create_font(32, QFont.Weight.Bold)

def get_font_normal(size=11):  return create_font(size)
def get_font_medium(size=11):  return create_font(size, QFont.Weight.Medium)
def get_font_bold(size=11):    return create_font(size, QFont.Weight.Bold)
def get_font_title(size=20):   return create_font(size, QFont.Weight.Bold)
def get_font_subtitle(size=13):return create_font(size)

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

# === CARGAR HOJA DE ESTILOS ===

def load_stylesheet():
    qss_path = Path(__file__).parent / "styles.qss"
    if qss_path.exists():
        qss = qss_path.read_text(encoding="utf-8")
        QApplication.instance().setStyleSheet(qss)

# === WIDGET HELPERS ===

def create_title(parent: QWidget, text: str, size: str = "2xl") -> QLabel:
    label = QLabel(text, parent)
    fonts = {
        "display": font_display, "3xl": font_3xl, "2xl": font_2xl,
        "xl": font_xl, "lg": font_lg,
    }
    label.setFont(fonts.get(size, font_lg)())
    label.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
    return label

def create_subtitle(parent: QWidget, text: str) -> QLabel:
    label = QLabel(text, parent)
    label.setFont(font_lg())
    label.setStyleSheet(f"color: {TEXT_SECONDARY}; background: transparent;")
    return label

def create_text(parent: QWidget, text: str, muted: bool = False) -> QLabel:
    label = QLabel(text, parent)
    label.setFont(font_base())
    color = TEXT_TERTIARY if muted else TEXT_SECONDARY
    label.setStyleSheet(f"color: {color}; background: transparent;")
    return label

def create_form_label(parent: QWidget, text: str) -> QLabel:
    label = QLabel(text, parent)
    label.setFont(create_font(10, QFont.Weight.Medium))
    label.setStyleSheet(f"color: {TEXT_PRIMARY}; background: transparent;")
    return label

def create_caption(parent: QWidget, text: str) -> QLabel:
    label = QLabel(text, parent)
    label.setFont(font_sm())
    label.setStyleSheet(f"color: {TEXT_TERTIARY}; background: transparent;")
    return label

def create_divider(parent: QWidget) -> QFrame:
    line = QFrame(parent)
    line.setProperty("class", "divider")
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line

def create_input(parent: QWidget, value: str = "") -> "QLineEdit":
    from PySide6.QtWidgets import QLineEdit
    le = QLineEdit(value, parent)
    le.setFont(font_base())
    le.setMinimumHeight(28)
    return le


class Card(QFrame):
    """Panel tipo tarjeta con estilo moderno via QSS."""

    def __init__(self, parent: QWidget = None, padding: int = SPACE_LG):
        super().__init__(parent)
        self.setProperty("class", "card")
        self._inner_layout = QVBoxLayout()
        self._inner_layout.setContentsMargins(padding, padding, padding, padding)
        self._inner_layout.setSpacing(SPACE_XS)
        self.setLayout(self._inner_layout)

    def get_inner_layout(self) -> QVBoxLayout:
        return self._inner_layout


# === APLICAR ESTILOS (compat con código antiguo que llama style_*) ===

def style_frame(frame):  pass
def style_panel(panel, elevated=False): pass
def style_dialog(dialog): pass
def style_listctrl(listctrl): pass
def style_textctrl(textctrl): pass
def style_notebook(notebook): pass
def style_button_primary(btn):
    btn.setProperty("class", "primary")
    btn.setFont(get_font_medium())
    btn.style().unpolish(btn)
    btn.style().polish(btn)

def apply_theme_to_frame(frame): pass
def apply_theme_to_panel(panel): pass
def apply_theme_to_dialog(dialog): pass
def create_styled_title(parent, text):
    return create_title(parent, text, "xl")

def create_toolbar_panel(parent):
    w = QWidget(parent)
    w.setProperty("class", "toolbar")
    return w

def fit_dialog(dialog, min_w=400, min_h=300):
    dialog.adjustSize()
    w = max(dialog.width() + 20, min_w)
    h = max(dialog.height() + 10, min_h)
    screen = QApplication.primaryScreen()
    if screen:
        avail = screen.availableGeometry()
        w = min(w, avail.width() - 40)
        h = min(h, avail.height() - 40)
    dialog.resize(w, h)
    dialog.setMinimumSize(min(min_w, w), min(min_h, h))
    if dialog.parentWidget():
        parent_geo = dialog.parentWidget().geometry()
        dialog.move(
            parent_geo.x() + (parent_geo.width() - w) // 2,
            parent_geo.y() + (parent_geo.height() - h) // 2,
        )
