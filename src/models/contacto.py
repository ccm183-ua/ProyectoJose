"""
Modelo de datos para Contacto.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Contacto:
    """Clase que representa un contacto."""

    nombre: str
    telefono: str
    id: Optional[int] = None
    telefono2: str = ""
    email: str = ""
    notas: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Contacto":
        """Crea una instancia desde un diccionario (claves faltantes usan valores por defecto)."""
        return cls(
            id=d.get("id"),
            nombre=d.get("nombre", ""),
            telefono=d.get("telefono", ""),
            telefono2=d.get("telefono2", ""),
            email=d.get("email", ""),
            notas=d.get("notas", ""),
        )

    def to_dict(self) -> dict:
        """Convierte la instancia a diccionario."""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "telefono": self.telefono,
            "telefono2": self.telefono2,
            "email": self.email,
            "notas": self.notas,
        }
