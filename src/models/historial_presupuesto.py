"""
Modelo de datos para HistorialPresupuesto.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class HistorialPresupuesto:
    """Clase que representa un registro del historial de presupuestos."""

    nombre_proyecto: str
    ruta_excel: str
    id: Optional[int] = None
    ruta_carpeta: str = ""
    fecha_creacion: str = ""
    fecha_ultimo_acceso: str = ""
    cliente: str = ""
    localidad: str = ""
    tipo_obra: str = ""
    numero_proyecto: str = ""
    usa_partidas_ia: bool = False
    total_presupuesto: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict) -> "HistorialPresupuesto":
        """Crea una instancia desde un diccionario (claves faltantes usan valores por defecto)."""
        return cls(
            id=d.get("id"),
            nombre_proyecto=d.get("nombre_proyecto", ""),
            ruta_excel=d.get("ruta_excel", ""),
            ruta_carpeta=d.get("ruta_carpeta", ""),
            fecha_creacion=d.get("fecha_creacion", ""),
            fecha_ultimo_acceso=d.get("fecha_ultimo_acceso", ""),
            cliente=d.get("cliente", ""),
            localidad=d.get("localidad", ""),
            tipo_obra=d.get("tipo_obra", ""),
            numero_proyecto=d.get("numero_proyecto", ""),
            usa_partidas_ia=d.get("usa_partidas_ia", False),
            total_presupuesto=d.get("total_presupuesto"),
        )

    def to_dict(self) -> dict:
        """Convierte la instancia a diccionario."""
        return {
            "id": self.id,
            "nombre_proyecto": self.nombre_proyecto,
            "ruta_excel": self.ruta_excel,
            "ruta_carpeta": self.ruta_carpeta,
            "fecha_creacion": self.fecha_creacion,
            "fecha_ultimo_acceso": self.fecha_ultimo_acceso,
            "cliente": self.cliente,
            "localidad": self.localidad,
            "tipo_obra": self.tipo_obra,
            "numero_proyecto": self.numero_proyecto,
            "usa_partidas_ia": self.usa_partidas_ia,
            "total_presupuesto": self.total_presupuesto,
        }
