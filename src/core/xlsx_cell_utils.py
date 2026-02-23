"""
Utilidades compartidas para lectura de XML interno de archivos .xlsx.

Centraliza la lógica de parsing de sharedStrings.xml, resolución de
valores de celda (inlineStr, shared string, valor directo) y extracción
de filas del XML de una hoja, evitando duplicación entre BudgetReader,
ExcelPartidasExtractor y ExcelManager.
"""

import io
import re
import zipfile
from typing import Dict, List, Optional

SHARED_STRINGS_PATH = "xl/sharedStrings.xml"


def parse_shared_strings_xml(ss_xml: str) -> List[str]:
    """Parsea el contenido XML de sharedStrings.xml y devuelve la lista indexada."""
    strings: List[str] = []
    for si_match in re.finditer(r'<si>(.*?)</si>', ss_xml, re.DOTALL):
        texts = re.findall(r'<t[^>]*?>([^<]*)</t>', si_match.group(1))
        strings.append("".join(texts))
    return strings


def read_shared_strings_from_bytes(file_bytes: bytes) -> List[str]:
    """Lee sharedStrings.xml desde bytes de un archivo .xlsx en memoria."""
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
            if SHARED_STRINGS_PATH not in z.namelist():
                return []
            ss_xml = z.read(SHARED_STRINGS_PATH).decode("utf-8")
            return parse_shared_strings_xml(ss_xml)
    except (zipfile.BadZipFile, IOError, OSError):
        return []


def read_shared_strings_from_path(file_path: str) -> List[str]:
    """Lee sharedStrings.xml directamente desde la ruta de un archivo .xlsx."""
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            if SHARED_STRINGS_PATH not in z.namelist():
                return []
            ss_xml = z.read(SHARED_STRINGS_PATH).decode("utf-8")
            return parse_shared_strings_xml(ss_xml)
    except (zipfile.BadZipFile, IOError, OSError):
        return []


def read_shared_strings_from_dict(zip_contents: dict) -> List[str]:
    """Lee sharedStrings desde un dict {nombre_archivo: bytes} ya extraído."""
    if SHARED_STRINGS_PATH not in zip_contents:
        return []
    ss_xml = zip_contents[SHARED_STRINGS_PATH].decode("utf-8")
    return parse_shared_strings_xml(ss_xml)


def get_cell_value(cell_info: Dict, shared_strings: List[str]) -> str:
    """Extrae el valor textual de una celda parsed como dict con 'attrs' e 'inner'.

    Maneja tres tipos de contenido:
    - Rich text / inlineStr: ``<is>`` con uno o más ``<r>`` o ``<t>``
    - Shared string (``t="s"``): índice en shared_strings via ``<v>``
    - Valor directo: ``<v>valor</v>``
    """
    attrs = cell_info.get("attrs", "")
    inner = cell_info.get("inner", "")

    is_match = re.search(r'<is>(.*?)</is>', inner, re.DOTALL)
    if is_match:
        is_content = is_match.group(1)
        texts = re.findall(r'<t[^>]*>([^<]*)</t>', is_content)
        if texts:
            return ' '.join(t.strip() for t in texts if t.strip())

    if 't="s"' in attrs:
        v_match = re.search(r'<v>(\d+)</v>', inner)
        if v_match:
            idx = int(v_match.group(1))
            if 0 <= idx < len(shared_strings):
                return shared_strings[idx].strip()

    v_match = re.search(r'<v>([^<]+)</v>', inner)
    if v_match:
        return v_match.group(1).strip()

    return ""


def get_cell_number(cell_info: Dict, shared_strings: List[str]) -> Optional[float]:
    """Extrae un valor numérico de una celda, o None si no es numérica."""
    value = get_cell_value(cell_info, shared_strings)
    if not value:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def extract_rows(sheet_xml: str) -> Dict[int, Dict]:
    """Extrae filas del XML de una hoja como ``{row_num: {col: cell_info}}``."""
    rows: Dict[int, Dict] = {}
    for row_match in re.finditer(
        r'<row r="(\d+)"[^>]*?(?:/>|>(.*?)</row>)', sheet_xml, re.DOTALL
    ):
        row_num = int(row_match.group(1))
        row_content = row_match.group(2)
        if not row_content:
            continue
        cells: Dict[str, Dict] = {}
        for cell_match in re.finditer(
            r'<c r="([A-Z]+)\d+"([^>]*?)(?:/>|>(.*?)</c>)',
            row_content, re.DOTALL,
        ):
            col = cell_match.group(1)
            cells[col] = {
                "attrs": cell_match.group(2),
                "inner": cell_match.group(3) or "",
            }
        if cells:
            rows[row_num] = cells
    return rows


def resolve_cell_text(cell_xml: str, shared_strings: List[str]) -> str:
    """Resuelve el texto de una celda dada como fragmento XML completo ``<c ...>...</c>``."""
    if 't="inlineStr"' in cell_xml or "<is>" in cell_xml:
        parts = re.findall(r'<t[^>]*?>([^<]*)</t>', cell_xml)
        return "".join(parts)
    if 't="s"' in cell_xml:
        vm = re.search(r'<v>(\d+)</v>', cell_xml)
        if vm:
            idx = int(vm.group(1))
            if 0 <= idx < len(shared_strings):
                return shared_strings[idx]
    return ""
