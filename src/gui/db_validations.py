"""
Funciones de validación para formularios de la base de datos.
"""

import re

from PySide6.QtWidgets import QMessageBox

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


def run_validations(dialog, checks: list[tuple[str, str | None]]) -> bool:
    """Ejecuta una lista de (campo, error_o_none). Muestra el primer error y retorna False, o True si todo OK."""
    for field_name, err in checks:
        if err:
            QMessageBox.warning(dialog, "Validación", f"{field_name}: {err}")
            return False
    return True
