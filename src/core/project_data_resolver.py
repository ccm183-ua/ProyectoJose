"""
Resolutor de datos de proyecto para el dashboard de presupuestos.

Combina tres fuentes para rellenar las columnas de la lista:
  1. Cache de la base de datos (tabla ``presupuesto``): instantáneo.
  2. Excel de relación de presupuestos (cruce por número de proyecto).
  3. Lectura directa del Excel del presupuesto con BudgetReader (fallback).

La cache se usa siempre que el mtime del Excel no haya cambiado.
Si el mtime cambió o no hay cache, se re-lee y se actualiza la DB.
"""

from typing import Dict, List, Optional

from src.core.budget_cache import cleanup_orphaned_cache, sync_presupuestos
from src.core.excel_relation_reader import ExcelRelationReader
from src.core.settings import Settings


def resolve_projects(
    scanned: List[Dict],
    relation_index: Optional[Dict[str, Dict]] = None,
    state_name: str = "",
) -> List[Dict]:
    """Enriquece la lista de proyectos escaneados con datos del cliente, etc.

    Usa la cache de la DB para evitar re-leer Excels que no han cambiado.
    Solo abre un Excel si su mtime difiere del almacenado en la cache.

    Args:
        scanned: Lista de dicts provenientes de ``folder_scanner.scan_projects``.
        relation_index: Dict ``{numero_proyecto: datos}`` del Excel de relación.
            Si es ``None`` no se intenta cruce.
        state_name: Nombre de la carpeta de estado (para almacenar en cache).

    Returns:
        Lista de dicts con campos unificados listos para la UI.
    """
    return sync_presupuestos(scanned, relation_index, state_name)


def resolve_projects_all_states(
    states_scanned: Dict[str, List[Dict]],
    relation_index: Optional[Dict[str, Dict]] = None,
) -> Dict[str, List[Dict]]:
    """Resuelve proyectos para múltiples estados y limpia la cache huérfana.

    Args:
        states_scanned: Dict ``{estado: lista_de_proyectos_escaneados}``.
        relation_index: Índice del Excel de relación.

    Returns:
        Dict ``{estado: lista_de_proyectos_resueltos}``.
    """
    result: Dict[str, List[Dict]] = {}
    all_rutas: List[str] = []

    for state_name, scanned in states_scanned.items():
        resolved = sync_presupuestos(scanned, relation_index, state_name)
        result[state_name] = resolved
        # Recopilar rutas vigentes para limpieza
        for proj in scanned:
            ruta = proj.get("ruta_excel", "")
            if ruta:
                all_rutas.append(ruta)

    # Limpiar presupuestos huérfanos de la cache
    if all_rutas:
        cleanup_orphaned_cache(all_rutas)

    return result


def build_relation_index(relation_file: Optional[str] = None) -> Dict[str, Dict]:
    """Lee el Excel de relación y devuelve un dict indexado por número de proyecto.

    Si *relation_file* es ``None``, intenta obtener la ruta de Settings.
    Devuelve dict vacío si no se puede leer.
    """
    if relation_file is None:
        relation_file = Settings().get_default_path(Settings.PATH_RELATION_FILE)
    if not relation_file:
        return {}

    rows, err = ExcelRelationReader().read(relation_file)
    if err or not rows:
        return {}

    index: Dict[str, Dict] = {}
    for row in rows:
        num = row.get("numero", "").strip()
        if num:
            index[num] = row
    return index
