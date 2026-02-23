"""
Servicio de base de datos: orquesta las consultas y operaciones
de la BDD desacoplando la GUI de los repositorios.
"""

import logging
from typing import Dict, List, Optional, Tuple

from src.core import db_repository

logger = logging.getLogger(__name__)


class DatabaseService:
    """Orquesta las operaciones de base de datos con lógica de negocio.

    Encapsula las consultas compuestas que antes la GUI hacía directamente
    contra db_repository (búsqueda de comunidad con fallback fuzzy,
    resolución de admin para comunidad, etc.).
    """

    @staticmethod
    def buscar_comunidad(nombre_cliente: str) -> Tuple[
        Optional[Dict], List[Dict]
    ]:
        """Busca una comunidad por nombre exacto y luego fuzzy.

        Returns:
            Tupla (comunidad_exacta, coincidencias_fuzzy).
            Si se encuentra match exacto, fuzzy estará vacío.
            Si no hay match exacto, se devuelven las candidatas fuzzy.
        """
        if not nombre_cliente or not nombre_cliente.strip():
            return None, []

        nombre = nombre_cliente.strip()

        exacta = db_repository.buscar_comunidad_por_nombre(nombre)
        if exacta:
            return exacta, []

        fuzzy = db_repository.buscar_comunidades_fuzzy(nombre)
        return None, fuzzy

    @staticmethod
    def get_admin_para_comunidad(comunidad_data: Optional[Dict]) -> Optional[Dict]:
        """Obtiene los datos de administración para una comunidad."""
        if not comunidad_data or not comunidad_data.get("administracion_id"):
            return None
        return db_repository.get_administracion_por_id(
            comunidad_data["administracion_id"],
        )

    @staticmethod
    def get_administraciones() -> List[Dict]:
        return db_repository.get_administraciones()

    @staticmethod
    def get_comunidades_para_tabla() -> List[Dict]:
        return db_repository.get_comunidades_para_tabla()

    @staticmethod
    def get_administraciones_para_tabla() -> List[Dict]:
        return db_repository.get_administraciones_para_tabla()

    @staticmethod
    def get_historial_reciente(limit: int = 50) -> List[Dict]:
        return db_repository.get_historial_reciente(limit=limit)

    @staticmethod
    def registrar_presupuesto(data: Dict) -> Tuple[Optional[int], Optional[str]]:
        return db_repository.registrar_presupuesto(data)

    @staticmethod
    def get_comunidad_por_id(id_: int) -> Optional[Dict]:
        return db_repository.get_comunidad_por_id(id_)

    @staticmethod
    def get_administracion_por_id(id_: int) -> Optional[Dict]:
        return db_repository.get_administracion_por_id(id_)

    @staticmethod
    def crear_comunidad(
        nombre: str,
        administracion_id: int,
        cif: str = "",
        direccion: str = "",
        email: str = "",
        telefono: str = "",
    ) -> Tuple[Optional[int], Optional[str]]:
        return db_repository.create_comunidad(
            nombre, administracion_id,
            cif=cif, direccion=direccion, email=email, telefono=telefono,
        )

    @staticmethod
    def crear_administracion(
        nombre: str, email: str = "", telefono: str = "", direccion: str = "",
    ) -> Tuple[Optional[int], Optional[str]]:
        return db_repository.create_administracion(nombre, email, telefono, direccion)
