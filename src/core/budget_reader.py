"""
Lector de presupuestos Excel creados con cubiApp.

Extrae datos de cabecera, partidas y totales de un .xlsx generado con
la plantilla 122-20, trabajando directamente con el XML interno para
máxima compatibilidad (sin abrir con openpyxl, que puede alterar formato).
"""

import os
import re
import zipfile
from typing import Dict, List, Optional


SHEET_PRIMARY = "xl/worksheets/sheet1.xml"
SHEET_FALLBACK = "xl/worksheets/sheet2.xml"

HEADER_CELLS = {
    "E5": "numero",
    "H5": "fecha",
    "B7": "cliente",
    "H7": "cif_admin",
    "B9": "direccion",
    "H9": "codigo_postal",
    "B11": "email_admin",
    "H11": "telefono_admin",
    "A14": "obra",
}


class BudgetReader:
    """Lee un presupuesto .xlsx de cubiApp y extrae cabecera, partidas y totales."""

    def read(self, file_path: str) -> Optional[Dict]:
        """
        Lee un presupuesto completo.

        Args:
            file_path: Ruta al archivo .xlsx.

        Returns:
            Dict con 'cabecera', 'partidas', 'subtotal', 'iva', 'total',
            o None si no se puede leer.
        """
        if not file_path or not os.path.exists(file_path):
            return None

        try:
            sheet_xml = self._read_sheet(file_path)
            if not sheet_xml:
                return None

            shared_strings = self._read_shared_strings(file_path)
            rows = self._extract_rows(sheet_xml)

            cabecera = self._extract_header(rows, shared_strings)
            partidas = self._extract_partidas(rows, shared_strings)
            totals = self._extract_totals(partidas)

            return {
                "cabecera": cabecera,
                "partidas": partidas,
                "subtotal": totals["subtotal"],
                "iva": totals["iva"],
                "total": totals["total"],
            }
        except Exception:
            return None

    def _read_sheet(self, file_path: str) -> Optional[str]:
        try:
            with zipfile.ZipFile(file_path, "r") as z:
                names = z.namelist()
                for sheet in (SHEET_PRIMARY, SHEET_FALLBACK):
                    if sheet in names:
                        return z.read(sheet).decode("utf-8")
        except (zipfile.BadZipFile, IOError, OSError):
            pass
        return None

    def _read_shared_strings(self, file_path: str) -> List[str]:
        try:
            with zipfile.ZipFile(file_path, "r") as z:
                ss_path = "xl/sharedStrings.xml"
                if ss_path not in z.namelist():
                    return []
                ss_xml = z.read(ss_path).decode("utf-8")
                strings = []
                for si_match in re.finditer(r'<si>(.*?)</si>', ss_xml, re.DOTALL):
                    texts = re.findall(r'<t[^>]*>([^<]*)</t>', si_match.group(1))
                    strings.append(''.join(texts))
                return strings
        except (zipfile.BadZipFile, IOError, OSError):
            return []

    def _extract_rows(self, sheet_xml: str) -> Dict[int, Dict]:
        """Extrae filas como {row_num: {col: cell_info}}."""
        rows = {}
        for row_match in re.finditer(
            r'<row r="(\d+)"[^>]*?(?:/>|>(.*?)</row>)', sheet_xml, re.DOTALL
        ):
            row_num = int(row_match.group(1))
            row_content = row_match.group(2)
            if not row_content:
                continue
            cells = {}
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

    def _get_cell_value(self, cell_info: Dict, shared_strings: List[str]) -> str:
        attrs = cell_info.get("attrs", "")
        inner = cell_info.get("inner", "")

        # Rich text: concatenate all <t> inside <r> runs within <is>
        is_match = re.search(r'<is>(.*?)</is>', inner, re.DOTALL)
        if is_match:
            is_content = is_match.group(1)
            texts = re.findall(r'<t[^>]*>([^<]*)</t>', is_content)
            if texts:
                return ' '.join(t.strip() for t in texts if t.strip())

        # Shared string
        if 't="s"' in attrs:
            v_match = re.search(r'<v>(\d+)</v>', inner)
            if v_match:
                idx = int(v_match.group(1))
                if 0 <= idx < len(shared_strings):
                    return shared_strings[idx].strip()

        # Direct value
        v_match = re.search(r'<v>([^<]+)</v>', inner)
        if v_match:
            return v_match.group(1).strip()

        return ""

    def _get_cell_number(self, cell_info: Dict, shared_strings: List[str]) -> Optional[float]:
        value = self._get_cell_value(cell_info, shared_strings)
        if not value:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _extract_header(self, rows: Dict[int, Dict], shared_strings: List[str]) -> Dict:
        """Extrae los datos de cabecera de las celdas conocidas."""
        cabecera = {}
        for cell_ref, field_name in HEADER_CELLS.items():
            col = re.match(r'([A-Z]+)', cell_ref).group(1)
            row_num = int(re.search(r'(\d+)', cell_ref).group(1))
            row = rows.get(row_num, {})
            cell = row.get(col)
            if cell:
                cabecera[field_name] = self._get_cell_value(cell, shared_strings)
            else:
                cabecera[field_name] = ""
        return cabecera

    def _extract_partidas(self, rows: Dict[int, Dict], shared_strings: List[str]) -> List[Dict]:
        """Extrae partidas: filas con número en A (1.1, 1.2...) y concepto en C."""
        partidas = []
        for row_num in sorted(rows.keys()):
            if row_num < 17:
                continue
            cells = rows[row_num]
            if "A" not in cells or "C" not in cells:
                continue

            a_val = self._get_cell_value(cells["A"], shared_strings)
            c_val = self._get_cell_value(cells["C"], shared_strings)

            if not a_val or not re.match(r'^\d+\.?\d*$', a_val.strip()):
                continue
            if not c_val or len(c_val.strip()) < 2:
                continue

            unidad = ""
            if "B" in cells:
                unidad = self._get_cell_value(cells["B"], shared_strings)

            cantidad = 1.0
            if "G" in cells:
                num = self._get_cell_number(cells["G"], shared_strings)
                if num is not None:
                    cantidad = num

            precio = 0.0
            if "H" in cells:
                num = self._get_cell_number(cells["H"], shared_strings)
                if num is not None:
                    precio = num

            importe = round(cantidad * precio, 2)

            partidas.append({
                "numero": a_val.strip(),
                "concepto": c_val.strip(),
                "unidad": unidad.strip() if unidad else "ud",
                "cantidad": cantidad,
                "precio": precio,
                "importe": importe,
            })
        return partidas

    def _extract_totals(self, partidas: List[Dict]) -> Dict:
        """Calcula subtotal, IVA y total a partir de las partidas."""
        subtotal = sum(p["importe"] for p in partidas)
        iva = round(subtotal * 0.10, 2)
        total = round(subtotal + iva, 2)
        return {"subtotal": round(subtotal, 2), "iva": iva, "total": total}
