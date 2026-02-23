"""
Modelo de datos para Administración.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Administracion:
    """Clase que representa una administración."""

    nombre: str
    id: Optional[int] = None
    email: str = ""
    telefono: str = ""
    direccion: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Administracion":
        """Crea una instancia desde un diccionario (claves faltantes usan valores por defecto)."""
        return cls(
            id=d.get("id"),
            nombre=d.get("nombre", ""),
            email=d.get("email", ""),
            telefono=d.get("telefono", ""),
            direccion=d.get("direccion", ""),
        )

    def to_dict(self) -> dict:
        """Convierte la instancia a diccionario."""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "email": self.email,
            "telefono": self.telefono,
            "direccion": self.direccion,
        }
