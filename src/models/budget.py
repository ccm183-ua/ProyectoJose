"""
Modelo de datos para presupuestos.
"""

from datetime import datetime
from typing import Optional, List, Dict


class Budget:
    """Clase que representa un presupuesto."""
    
    def __init__(self):
        """Inicializa un presupuesto vacío."""
        self.nombre_obra: Optional[str] = None
        self.direccion: Optional[str] = None
        self.numero: Optional[str] = None
        self.codigo_postal: Optional[str] = None
        self.descripcion: Optional[str] = None
        self.fecha_creacion: Optional[datetime] = None
        self.items: List[Dict] = []
        self.subtotal: float = 0.0
        self.iva: float = 0.0
        self.total: float = 0.0
    
    def to_dict(self) -> Dict:
        """
        Convierte el presupuesto a diccionario.
        
        Returns:
            dict: Diccionario con los datos del presupuesto
        """
        return {
            'nombre_obra': self.nombre_obra,
            'direccion': self.direccion,
            'numero': self.numero,
            'codigo_postal': self.codigo_postal,
            'descripcion': self.descripcion,
            'fecha_creacion': self.fecha_creacion.strftime('%d/%m/%Y') if self.fecha_creacion else None,
            'items': self.items,
            'subtotal': self.subtotal,
            'iva': self.iva,
            'total': self.total
        }
    
    def from_dict(self, data: Dict):
        """
        Carga datos desde un diccionario.
        
        Args:
            data: Diccionario con los datos del presupuesto
        """
        self.nombre_obra = data.get('nombre_obra')
        self.direccion = data.get('direccion')
        self.numero = data.get('numero')
        self.codigo_postal = data.get('codigo_postal')
        self.descripcion = data.get('descripcion')
        self.items = data.get('items', [])
        self.subtotal = data.get('subtotal', 0.0)
        self.iva = data.get('iva', 0.0)
        self.total = data.get('total', 0.0)
