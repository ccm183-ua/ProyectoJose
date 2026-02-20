"""
Resolutor de datos de proyecto para el dashboard de presupuestos.

Combina dos fuentes para rellenar las columnas de la lista:
  1. Excel de relación de presupuestos (cruce por número de proyecto).
  2. Lectura directa del Excel del presupuesto con BudgetReader (fallback).

BudgetReader carga los archivos completamente en memoria antes de parsearlos,
evitando así bloqueos de archivo que impedirían abrirlos con WPS/Excel.
"""

from typing import Dict, List, Optional

from src.core.budget_reader import BudgetReader
from src.core.excel_relation_reader import ExcelRelationReader
from src.core.settings import Settings


def resolve_projects(
    scanned: List[Dict],
    relation_index: Optional[Dict[str, Dict]] = None,
) -> List[Dict]:
    """Enriquece la lista de proyectos escaneados con datos del cliente, etc.

    Args:
        scanned: Lista de dicts provenientes de ``folder_scanner.scan_projects``.
        relation_index: Dict ``{numero_proyecto: datos}`` del Excel de relación.
            Si es ``None`` no se intenta cruce.

    Returns:
        Lista de dicts con campos unificados listos para la UI.
    """
    reader = BudgetReader()
    result: List[Dict] = []

    for proj in scanned:
        numero = proj.get("numero_proyecto", "")
        entry = _empty_entry(proj)

        if relation_index and numero and numero in relation_index:
            _fill_from_relation(entry, relation_index[numero])
        elif proj.get("ruta_excel"):
            _fill_from_budget(entry, reader, proj["ruta_excel"])

        result.append(entry)

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


def _empty_entry(proj: Dict) -> Dict:
    return {
        "nombre_proyecto": proj.get("nombre_carpeta", ""),
        "numero": proj.get("numero_proyecto", ""),
        "cliente": "",
        "localidad": "",
        "tipo_obra": "",
        "fecha": "",
        "total": None,
        "ruta_excel": proj.get("ruta_excel", ""),
        "ruta_carpeta": proj.get("ruta_carpeta", ""),
    }


def _fill_from_relation(entry: Dict, rel: Dict) -> None:
    entry["cliente"] = rel.get("cliente", "")
    entry["localidad"] = rel.get("localidad", "")
    entry["tipo_obra"] = rel.get("tipo", "")
    entry["fecha"] = rel.get("fecha", "")
    importe = rel.get("importe", "")
    if importe:
        try:
            entry["total"] = float(importe)
        except (ValueError, TypeError):
            pass


def _fill_from_budget(entry: Dict, reader: BudgetReader, ruta: str) -> None:
    data = reader.read(ruta)
    if not data:
        return
    cab = data.get("cabecera", {})
    entry["cliente"] = cab.get("cliente", "")
    entry["localidad"] = cab.get("direccion", "")
    entry["tipo_obra"] = cab.get("obra", "")
    entry["fecha"] = cab.get("fecha", "")
    if data.get("total") is not None:
        entry["total"] = data["total"]
