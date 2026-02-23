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

from src.core.xlsx_cell_utils import (
    get_cell_number,
    get_cell_value,
    read_shared_strings_from_path,
)

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

    @staticmethod
    def _read_shared_strings(file_path: str) -> List[str]:
        """Lee la tabla de shared strings del xlsx."""
        return read_shared_strings_from_path(file_path)

    def _extract_rows(self, sheet_xml: str) -> List[Dict]:
        """Extrae filas como lista de dicts ``{num, cells}`` para compatibilidad."""
        from src.core.xlsx_cell_utils import extract_rows as _extract
        rows_dict = _extract(sheet_xml)
        return [{"num": num, "cells": cells} for num, cells in sorted(rows_dict.items())]

    @staticmethod
    def _get_cell_value(cell_info: Dict, shared_strings: List[str]) -> str:
        return get_cell_value(cell_info, shared_strings)

    @staticmethod
    def _get_cell_number(cell_info: Dict, shared_strings: List[str]) -> Optional[float]:
        return get_cell_number(cell_info, shared_strings)

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
