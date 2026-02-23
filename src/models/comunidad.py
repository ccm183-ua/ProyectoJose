"""
Modelo de datos para Comunidad.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Comunidad:
    """Clase que representa una comunidad."""

    nombre: str
    id: Optional[int] = None
    cif: str = ""
    direccion: str = ""
    email: str = ""
    telefono: str = ""
    administracion_id: int = 0

    @classmethod
    def from_dict(cls, d: dict) -> "Comunidad":
        """Crea una instancia desde un diccionario (claves faltantes usan valores por defecto)."""
        return cls(
            id=d.get("id"),
            nombre=d.get("nombre", ""),
            cif=d.get("cif", ""),
            direccion=d.get("direccion", ""),
            email=d.get("email", ""),
            telefono=d.get("telefono", ""),
            administracion_id=d.get("administracion_id", 0),
        )

    def to_dict(self) -> dict:
        """Convierte la instancia a diccionario."""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "cif": self.cif,
            "direccion": self.direccion,
            "email": self.email,
            "telefono": self.telefono,
            "administracion_id": self.administracion_id,
        }
