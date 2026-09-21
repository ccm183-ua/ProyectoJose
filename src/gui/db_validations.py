"""
Funciones de validación para formularios de la base de datos.
"""

import re

from PySide6.QtWidgets import QMessageBox, QWidget

_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_RE_PHONE_CHARS = re.compile(r"^[\d\s+\-().]+$")
_RE_CIF = re.compile(r"^[A-Za-z]\d{7}[\dA-Za-z]$|^\d{8}[A-Za-z]$")


def validate_phone(value: str) -> str | None:
    """Devuelve mensaje de error o None si válido. Acepta vacío."""
    if not value:
        return None
    if not _RE_PHONE_CHARS.match(value):
        return "El teléfono contiene caracteres no válidos."
    digits = re.sub(r"\D", "", value)
    if len(digits) < 9:
        return "El teléfono debe tener al menos 9 dígitos."
    return None


def validate_email(value: str) -> str | None:
    if not value:
        return None
    if not _RE_EMAIL.match(value):
        return "El formato de email no es válido (ej: usuario@dominio.com)."
    return None


def validate_cif(value: str) -> str | None:
    if not value:
        return None
    clean = value.replace("-", "").replace(" ", "")
    if not _RE_CIF.match(clean):
        return "El CIF/NIF no parece válido (ej: B12345678 o 12345678A)."
    return None


def _set_error(widget: QWidget, error: str | None):
    """Marca o limpia el control como inválido (borde rojo + tooltip)."""
    widget.setProperty("error", bool(error))
    widget.setToolTip(error or "")
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def run_validations(dialog, checks: list[tuple[QWidget, str, str | None]]) -> bool:
    """Valida todos los checks (control, etiqueta, error_o_none) de una vez.

    Marca cada control inválido con la propiedad ``error`` y su tooltip, muestra
    un único resumen con todos los errores y enfoca el primero. Devuelve False si
    hay algún error y True si todo es válido.
    """
    invalid: list[tuple[QWidget, str, str]] = []
    for widget, label, err in checks:
        _set_error(widget, err)
        if err:
            invalid.append((widget, label, err))
    if not invalid:
        return True
    body = "Corrige estos campos antes de guardar:\n" + "\n".join(
        f"• {label}: {err}" for _, label, err in invalid
    )
    QMessageBox.warning(dialog, "Validación", body)
    invalid[0][0].setFocus()
    return False
