"""
Escáner de carpetas de presupuestos.

Recorre la estructura de carpetas de presupuestos existentes:
  root/
    ESTADO_1/           <- primer nivel: estados (pestañas)
      NNN-YY Proyecto/  <- segundo nivel: carpeta de proyecto
        NNN-YY *.xlsx   <- tercer nivel: Excel del presupuesto
"""

import os
import re
from typing import Dict, List, Optional

_PROJECT_NUMBER_RE = re.compile(r"(\d{1,4}-\d{2})")

_MIN_XLSX_SIZE = 4096


def _extract_project_number(name: str) -> Optional[str]:
    """Extrae el número de proyecto (ej: '122-20') de un nombre de carpeta o archivo."""
    m = _PROJECT_NUMBER_RE.search(name)
    return m.group(1) if m else None


def scan_root(root_path: str) -> List[str]:
    """Devuelve los nombres de las subcarpetas de primer nivel (estados),
    ordenados alfabéticamente.

    Args:
        root_path: Ruta raíz configurada en PATH_OPEN_BUDGETS.

    Returns:
        Lista de nombres de subcarpetas. Vacía si la ruta no existe.
    """
    root_path = os.path.normpath(root_path) if root_path else ""
    if not root_path or not os.path.isdir(root_path):
        return []
    try:
        entries = sorted(os.listdir(root_path))
        return [
            e for e in entries
            if os.path.isdir(os.path.join(root_path, e))
        ]
    except (OSError, PermissionError):
        return []


def scan_projects(state_folder: str) -> List[Dict]:
    """Escanea una carpeta de estado y devuelve los proyectos encontrados.

    Cada proyecto es una subcarpeta que contiene al menos un ``.xlsx``.
    El Excel correcto se identifica buscando el que contenga el mismo
    número de proyecto que la carpeta.

    Args:
        state_folder: Ruta absoluta a una carpeta de estado.

    Returns:
        Lista de dicts con claves:
        ``nombre_carpeta``, ``numero_proyecto``, ``ruta_excel``, ``ruta_carpeta``.
    """
    state_folder = os.path.normpath(state_folder) if state_folder else ""
    if not state_folder or not os.path.isdir(state_folder):
        return []

    projects: List[Dict] = []
    try:
        entries = sorted(os.listdir(state_folder))
    except (OSError, PermissionError):
        return []

    for entry in entries:
        project_dir = os.path.normpath(os.path.join(state_folder, entry))
        if not os.path.isdir(project_dir):
            continue

        numero = _extract_project_number(entry)
        ruta_excel = _find_best_excel(project_dir, numero)

        projects.append({
            "nombre_carpeta": entry,
            "numero_proyecto": numero or "",
            "ruta_excel": ruta_excel or "",
            "ruta_carpeta": project_dir,
        })

    return projects


def _is_valid_xlsx(filepath: str) -> bool:
    """Comprueba que el archivo sea un xlsx real (no temporal, no vacío)."""
    try:
        return os.path.isfile(filepath) and os.path.getsize(filepath) >= _MIN_XLSX_SIZE
    except OSError:
        return False


def _find_best_excel(
    project_dir: str, numero: Optional[str]
) -> Optional[str]:
    """Busca el Excel más adecuado dentro de la carpeta del proyecto.

    Prioridad:
    1. ``.xlsx`` cuyo nombre contenga el número de proyecto y NO sea copia.
    2. Si hay varios, el que tenga el nombre más corto.
    3. Si ninguno contiene el número, devuelve el primer ``.xlsx`` válido.

    Se excluyen archivos temporales (~$), copias (- copia) y archivos
    demasiado pequeños para ser xlsx reales.
    """
    try:
        files = os.listdir(project_dir)
    except (OSError, PermissionError):
        return None

    xlsx_files = []
    for f in files:
        if not f.lower().endswith(".xlsx"):
            continue
        if f.startswith("~$") or f.startswith("."):
            continue
        full = os.path.normpath(os.path.join(project_dir, f))
        if not _is_valid_xlsx(full):
            continue
        xlsx_files.append(f)

    if not xlsx_files:
        return None

    if numero:
        originals = [
            f for f in xlsx_files
            if numero in f and "copia" not in f.lower()
        ]
        if originals:
            originals.sort(key=len)
            return os.path.normpath(os.path.join(project_dir, originals[0]))

        matches = [f for f in xlsx_files if numero in f]
        if matches:
            matches.sort(key=len)
            return os.path.normpath(os.path.join(project_dir, matches[0]))

    non_copies = [f for f in xlsx_files if "copia" not in f.lower()]
    if non_copies:
        non_copies.sort(key=len)
        return os.path.normpath(os.path.join(project_dir, non_copies[0]))

    xlsx_files.sort(key=len)
    return os.path.normpath(os.path.join(project_dir, xlsx_files[0]))
