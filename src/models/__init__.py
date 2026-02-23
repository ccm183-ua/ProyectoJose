"""
Módulo de modelos de datos.
"""

from src.models.administracion import Administracion
from src.models.budget import Budget
from src.models.comunidad import Comunidad
from src.models.contacto import Contacto
from src.models.historial_presupuesto import HistorialPresupuesto

__all__ = [
    "Administracion",
    "Budget",
    "Comunidad",
    "Contacto",
    "HistorialPresupuesto",
]
