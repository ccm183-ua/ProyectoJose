"""
Extractor de partidas desde archivos Excel de presupuesto existentes.

Lee un presupuesto .xlsx generado con la plantilla de cubiApp y extrae
las partidas (concepto, unidad, cantidad, precio unitario) para crear
una plantilla personalizada reutilizable.

Trabaja directamente con el XML de sheet2 para máxima compatibilidad
con la plantilla 122-20 PLANTILLA PRESUPUESTO.
"""

import logging
import re
import zipfile
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Hoja de datos en la plantilla (PRESUP FINAL = sheet2)
SHEET_12220 = "xl/worksheets/sheet2.xml"


class ExcelPartidasExtractor:
    """Extrae partidas de un presupuesto Excel existente."""

    def extract(self, file_path: str) -> List[Dict]:
        """
        Extrae las partidas de un archivo Excel de presupuesto.

        Busca filas con datos de partidas en sheet2 (PRESUP FINAL),
        identificándolas por la estructura: número en col A, unidad en col B,
        descripción en col C, cantidad en col G, precio en col H.

        Args:
            file_path: Ruta al archivo .xlsx.

        Returns:
            Lista de dicts con concepto, unidad, cantidad, precio_unitario.
            Lista vacía si no se encuentran partidas o hay error.
        """
        try:
            sheet_xml = self._read_sheet2(file_path)
            if not sheet_xml:
                return []

            shared_strings = self._read_shared_strings(file_path)
            rows = self._extract_rows(sheet_xml)
            return self._parse_partidas(rows, shared_strings)
        except Exception as e:
            logger.exception("Error al extraer partidas del Excel")
            return []

    def _read_sheet2(self, file_path: str) -> Optional[str]:
        """Lee el XML de sheet2 del archivo xlsx."""
        try:
            with zipfile.ZipFile(file_path, "r") as z:
                if SHEET_12220 in z.namelist():
                    return z.read(SHEET_12220).decode("utf-8")
                # Intentar con sheet1 si sheet2 no existe
                alt = "xl/worksheets/sheet1.xml"
                if alt in z.namelist():
                    return z.read(alt).decode("utf-8")
        except (zipfile.BadZipFile, IOError):
            pass
        return None

    def _read_shared_strings(self, file_path: str) -> List[str]:
        """Lee la tabla de shared strings del xlsx."""
        try:
            with zipfile.ZipFile(file_path, "r") as z:
                ss_path = "xl/sharedStrings.xml"
                if ss_path not in z.namelist():
                    return []
                ss_xml = z.read(ss_path).decode("utf-8")
                # Extraer todos los <t>...</t> dentro de <si>...</si>
                strings = []
                for si_match in re.finditer(r'<si>(.*?)</si>', ss_xml, re.DOTALL):
                    si_content = si_match.group(1)
                    # Concatenar todos los <t> dentro del <si>
                    texts = re.findall(r'<t[^>]*>([^<]*)</t>', si_content)
                    strings.append(''.join(texts))
                return strings
        except (zipfile.BadZipFile, IOError):
            return []

    def _extract_rows(self, sheet_xml: str) -> List[Dict]:
        """
        Extrae las filas del XML como lista de dicts {col: value}.

        Cada fila es un diccionario con las columnas (A, B, C, ...) como claves
        y los valores de celda como valores.
        """
        rows = []
        for row_match in re.finditer(r'<row r="(\d+)"[^>]*>(.*?)</row>', sheet_xml, re.DOTALL):
            row_num = int(row_match.group(1))
            row_content = row_match.group(2)
            cells = {}

            for cell_match in re.finditer(
                r'<c r="([A-Z]+)\d+"([^>]*)(?:/>|>(.*?)</c>)',
                row_content, re.DOTALL
            ):
                col = cell_match.group(1)
                attrs = cell_match.group(2)
                inner = cell_match.group(3) or ""

                cells[col] = {
                    'attrs': attrs,
                    'inner': inner,
                    'row': row_num,
                }

            if cells:
                rows.append({'num': row_num, 'cells': cells})

        return rows

    def _get_cell_value(self, cell_info: Dict, shared_strings: List[str]) -> str:
        """
        Extrae el valor textual de una celda.

        Maneja tres tipos:
        - inlineStr: <is><t>texto</t></is>
        - sharedString (t="s"): <v>index</v> → shared_strings[index]
        - valor directo: <v>valor</v>
        """
        attrs = cell_info.get('attrs', '')
        inner = cell_info.get('inner', '')

        # InlineStr
        is_match = re.search(r'<is><t[^>]*>(.*?)</t></is>', inner, re.DOTALL)
        if is_match:
            return is_match.group(1).strip()

        # Shared string
        if 't="s"' in attrs:
            v_match = re.search(r'<v>(\d+)</v>', inner)
            if v_match:
                idx = int(v_match.group(1))
                if 0 <= idx < len(shared_strings):
                    return shared_strings[idx].strip()

        # Valor directo
        v_match = re.search(r'<v>([^<]+)</v>', inner)
        if v_match:
            return v_match.group(1).strip()

        return ""

    def _get_cell_number(self, cell_info: Dict, shared_strings: List[str]) -> Optional[float]:
        """Extrae un valor numérico de una celda."""
        value = self._get_cell_value(cell_info, shared_strings)
        if not value:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _parse_partidas(self, rows: List[Dict], shared_strings: List[str]) -> List[Dict]:
        """
        Identifica y extrae partidas de las filas.

        Una fila se considera partida si:
        - Tiene un número en col A (ej: "1.1", "1.2", "2.1")
        - Tiene texto en col C (concepto/descripción)
        - Tiene datos en col G o H (cantidad o precio)

        Se ignoran filas de cabecera, separadores y subtotales.
        """
        partidas = []

        for row in rows:
            cells = row['cells']
            row_num = row['num']

            # Necesitamos al menos columnas A y C
            if 'A' not in cells or 'C' not in cells:
                continue

            a_val = self._get_cell_value(cells['A'], shared_strings)
            c_val = self._get_cell_value(cells['C'], shared_strings)

            # Verificar que A parece un número de partida (1.1, 2.3, etc.)
            if not a_val or not re.match(r'^\d+\.?\d*$', a_val.strip()):
                continue

            # Verificar que C tiene un concepto (no vacío ni solo números)
            if not c_val or len(c_val.strip()) < 3:
                continue

            # Extraer unidad (col B)
            unidad = ""
            if 'B' in cells:
                unidad = self._get_cell_value(cells['B'], shared_strings)

            # Extraer cantidad (col G)
            cantidad = 1.0
            if 'G' in cells:
                num = self._get_cell_number(cells['G'], shared_strings)
                if num is not None:
                    cantidad = num

            # Extraer precio unitario (col H)
            precio = 0.0
            if 'H' in cells:
                num = self._get_cell_number(cells['H'], shared_strings)
                if num is not None:
                    precio = num

            partidas.append({
                'concepto': c_val.strip(),
                'unidad': unidad.strip() if unidad else 'ud',
                'precio_ref': precio,
                'cantidad_ref': cantidad,
            })

        return partidas
