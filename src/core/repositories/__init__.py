"""
Repositorios de acceso a datos por entidad.

Re-exporta todo para uso como:
  from src.core.repositories import get_administraciones, create_comunidad, ...
  from src.core import db_repository as repo  # facade en db_repository.py
"""

from src.core.repositories._common import (
    FUZZY_MATCH_THRESHOLD,
    HISTORIAL_DEFAULT_LIMIT,
)
from src.core.repositories.admin_repository import (
    get_administracion_por_id,
    get_administraciones,
    get_administraciones_para_tabla,
    buscar_administracion_por_nombre,
    buscar_administraciones_fuzzy,
    create_administracion,
    update_administracion,
    delete_administracion,
)
from src.core.repositories.comunidad_repository import (
    get_comunidad_por_id,
    get_comunidades,
    get_comunidades_para_tabla,
    buscar_comunidad_por_nombre,
    buscar_comunidades_fuzzy,
    create_comunidad,
    update_comunidad,
    delete_comunidad,
)
from src.core.repositories.contacto_repository import (
    get_contactos,
    get_contactos_para_tabla,
    get_contactos_por_administracion_id,
    get_contactos_por_comunidad_id,
    get_administracion_ids_para_contacto,
    get_comunidad_ids_para_contacto,
    set_administracion_contacto,
    set_comunidad_contacto,
    set_contactos_para_administracion,
    set_contactos_para_comunidad,
    create_contacto,
    update_contacto,
    delete_contacto,
)
from src.core.repositories.historial_repository import (
    registrar_presupuesto,
    get_historial_reciente,
    actualizar_acceso,
    actualizar_total,
    eliminar_historial,
    buscar_historial,
)
from src.core.repositories.presupuesto_cache_repository import (
    get_presupuesto_por_ruta,
    get_presupuestos_por_estado,
    upsert_presupuesto,
    actualizar_estado_presupuesto,
    limpiar_presupuestos_huerfanos,
    get_all_presupuestos_cache,
)

__all__ = [
    "FUZZY_MATCH_THRESHOLD",
    "HISTORIAL_DEFAULT_LIMIT",
    "get_administracion_por_id",
    "get_administraciones",
    "get_administraciones_para_tabla",
    "buscar_administracion_por_nombre",
    "buscar_administraciones_fuzzy",
    "create_administracion",
    "update_administracion",
    "delete_administracion",
    "get_comunidad_por_id",
    "get_comunidades",
    "get_comunidades_para_tabla",
    "buscar_comunidad_por_nombre",
    "buscar_comunidades_fuzzy",
    "create_comunidad",
    "update_comunidad",
    "delete_comunidad",
    "get_contactos",
    "get_contactos_para_tabla",
    "get_contactos_por_administracion_id",
    "get_contactos_por_comunidad_id",
    "get_administracion_ids_para_contacto",
    "get_comunidad_ids_para_contacto",
    "set_administracion_contacto",
    "set_comunidad_contacto",
    "set_contactos_para_administracion",
    "set_contactos_para_comunidad",
    "create_contacto",
    "update_contacto",
    "delete_contacto",
    "registrar_presupuesto",
    "get_historial_reciente",
    "actualizar_acceso",
    "actualizar_total",
    "eliminar_historial",
    "buscar_historial",
    "get_presupuesto_por_ruta",
    "get_presupuestos_por_estado",
    "upsert_presupuesto",
    "actualizar_estado_presupuesto",
    "limpiar_presupuestos_huerfanos",
    "get_all_presupuestos_cache",
]
