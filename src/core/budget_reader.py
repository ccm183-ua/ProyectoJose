"""
Lector de presupuestos Excel creados con cubiApp.

Extrae datos de cabecera, partidas y totales de un .xlsx generado con
la plantilla 122-20, trabajando directamente con el XML interno para
máxima compatibilidad (sin abrir con openpyxl, que puede alterar formato).

Detección inteligente de hoja:
  Algunos archivos .xlsx contienen los datos reales en sheet2 (no en
  sheet1) porque sheet1 retiene los datos de la plantilla original.
  Cuando se proporciona ``expected_numero``, el lector compara el número
  de proyecto de la cabecera (celda E5) con el esperado en cada hoja y
  usa la que coincide.
"""

import io
import logging
import os
import re
import zipfile
from typing import Dict, List, Optional

from src.core.xlsx_cell_utils import (
    extract_rows,
    get_cell_number,
    get_cell_value,
    read_shared_strings_from_bytes,
)
from src.utils.budget_utils import normalize_project_num
from src.utils.spanish_number_parser import extract_total_from_asciende

logger = logging.getLogger(__name__)


SHEET_PRIMARY = "xl/worksheets/sheet1.xml"
SHEET_FALLBACK = "xl/worksheets/sheet2.xml"

# Primera fila (1-indexed) que puede contener partidas en la plantilla 122-20
PARTIDA_START_ROW = 17

# Tipo de IVA por defecto para el cálculo de totales
IVA_RATE = 0.10

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

    def read(
        self,
        file_path: str,
        expected_numero: str = "",
        include_diagnostics: bool = False,
    ) -> Optional[Dict]:
        """
        Lee un presupuesto completo.

        Si se proporciona *expected_numero* (ej: ``"71-26"``), el lector
        compara el número de proyecto de la cabecera en cada hoja del archivo
        y selecciona la que coincida.  Esto resuelve el caso habitual en que
        sheet1 contiene los datos de la plantilla 122-20 y sheet2 los datos
        reales del proyecto.

        Args:
            file_path: Ruta al archivo .xlsx.
            expected_numero: Número de proyecto esperado (formato ``NNN-YY``).
                Si está vacío se usa el comportamiento clásico (sheet1 primero).

        Returns:
            Dict con 'cabecera', 'partidas', 'subtotal', 'iva', 'total',
            o None si no se puede leer.
        """
        if not file_path or not os.path.exists(file_path):
            return None

        try:
            file_bytes = self._load_file_bytes(file_path)
            if file_bytes is None:
                return None

            shared_strings = self._read_shared_strings(file_bytes)

            # Elegir la hoja correcta
            selected = self._select_best_sheet_info(
                file_bytes, shared_strings, expected_numero
            )
            if not selected:
                return None
            sheet_xml = selected["sheet_xml"]

            rows = self._extract_rows(sheet_xml)

            cabecera = self._extract_header(rows, shared_strings)
            partidas = self._extract_partidas(rows, shared_strings)

            totals = self._read_totals_from_cells(rows, shared_strings)
            if totals is None:
                totals = self._calculate_totals(partidas)

            result = {
                "cabecera": cabecera,
                "partidas": partidas,
                "subtotal": totals["subtotal"],
                "iva": totals["iva"],
                "total": totals["total"],
            }
            if include_diagnostics:
                detected_numero = (cabecera.get("numero") or "").strip()
                norm_expected = normalize_project_num(expected_numero)
                norm_detected = normalize_project_num(detected_numero)
                result["diagnostics"] = {
                    "selected_sheet": selected.get("sheet_name", ""),
                    "selected_sheet_index": selected.get("sheet_index"),
                    "expected_numero": expected_numero or "",
                    "detected_numero": detected_numero,
                    "numero_matches": bool(
                        norm_expected and norm_detected and norm_expected == norm_detected
                    ),
                    "compatibility_score": 0,
                }
            return result
        except Exception:
            logger.exception("Error al leer presupuesto: %s", file_path)
            return None

    def probe(self, file_path: str, expected_numero: str = "") -> Dict:
        """Evalúa compatibilidad del Excel para aprendizaje histórico."""
        from src.core.budget_file_probe import BudgetFileProbe

        return BudgetFileProbe(self).probe(file_path, expected_numero=expected_numero)

    @staticmethod
    def _load_file_bytes(file_path: str) -> Optional[bytes]:
        """Lee el archivo completo en memoria y cierra el handle de inmediato."""
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except (IOError, OSError):
            return None

    @staticmethod
    def _read_sheet(file_bytes: bytes) -> Optional[str]:
        """Lee la primera hoja disponible (sheet1, luego sheet2)."""
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
                names = z.namelist()
                for sheet in (SHEET_PRIMARY, SHEET_FALLBACK):
                    if sheet in names:
                        return z.read(sheet).decode("utf-8")
        except (zipfile.BadZipFile, IOError, OSError):
            pass
        return None

    @staticmethod
    def _list_sheet_metadata(file_bytes: bytes) -> List[Dict]:
        """Lista metadatos de hojas (nombre visible + xml path)."""
        result: List[Dict] = []
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
                workbook_xml = z.read("xl/workbook.xml").decode("utf-8")
                rels_xml = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
                rel_map = {
                    rel_id: target
                    for rel_id, target in re.findall(r'Id="([^"]+)".*?Target="([^"]+)"', rels_xml)
                }
                sheets = re.findall(
                    r'<sheet[^>]*name="([^"]+)"[^>]*sheetId="([^"]+)"[^>]*r:id="([^"]+)"',
                    workbook_xml,
                )
                for idx, (name, sheet_id, rel_id) in enumerate(sheets, start=1):
                    target = rel_map.get(rel_id, "")
                    if not target:
                        continue
                    xml_path = f"xl/{target}" if not target.startswith("xl/") else target
                    xml_path = xml_path.replace("\\", "/")
                    if xml_path.startswith("xl//"):
                        xml_path = xml_path.replace("xl//", "xl/")
                    result.append(
                        {
                            "sheet_name": name or f"Hoja{sheet_id}",
                            "sheet_index": idx,
                            "xml_path": xml_path,
                        }
                    )
        except (zipfile.BadZipFile, IOError, OSError):
            pass
        return result

    @classmethod
    def _read_all_sheets(cls, file_bytes: bytes) -> List[Dict]:
        """Lee hojas disponibles con metadatos."""
        sheets: List[Dict] = []
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes), "r") as z:
                names = set(z.namelist())
                meta = cls._list_sheet_metadata(file_bytes)
                for item in meta:
                    if item["xml_path"] in names:
                        item["sheet_xml"] = z.read(item["xml_path"]).decode("utf-8")
                        sheets.append(item)
                if not sheets:
                    for idx, xml_path in enumerate((SHEET_PRIMARY, SHEET_FALLBACK), start=1):
                        if xml_path in names:
                            sheets.append(
                                {
                                    "sheet_name": f"Hoja{idx}",
                                    "sheet_index": idx,
                                    "xml_path": xml_path,
                                    "sheet_xml": z.read(xml_path).decode("utf-8"),
                                }
                            )
        except (zipfile.BadZipFile, IOError, OSError):
            pass
        return sheets

    def _select_best_sheet_info(
        self,
        file_bytes: bytes,
        shared_strings: List[str],
        expected_numero: str,
    ) -> Optional[Dict]:
        """Selecciona la hoja que contiene los datos reales del proyecto.

        Si ``expected_numero`` está vacío, devuelve la primera hoja disponible
        (comportamiento clásico).

        Si se proporciona, lee la cabecera de cada hoja y devuelve la que
        tenga un número de proyecto coincidente con el esperado.

        Si ninguna coincide y hay dos hojas, devuelve **sheet2** porque
        sheet1 suele ser la plantilla original (122-20) que el usuario
        no ha modificado. Sheet2, en cambio, fue añadida deliberadamente
        al copiar otro presupuesto, y contiene datos más relevantes
        aunque el número no coincida exactamente (ej: copia con número
        de otro proyecto o de otro año).
        """
        if not expected_numero:
            sheets = self._read_all_sheets(file_bytes)
            return sheets[0] if sheets else None

        sheets = self._read_all_sheets(file_bytes)
        if not sheets:
            return None
        if len(sheets) == 1:
            return sheets[0]

        # Normalizar el número esperado
        norm_expected = normalize_project_num(expected_numero)
        if not norm_expected:
            return sheets[-1]  # Preferir última hoja (sheet2)

        # Comparar cabeceras de cada hoja
        for sheet in sheets:
            rows = self._extract_rows(sheet["sheet_xml"])
            header = self._extract_header(rows, shared_strings)
            norm_sheet = normalize_project_num(header.get("numero", ""))
            if norm_sheet == norm_expected:
                return sheet

        # Ninguna hoja coincide: preferir sheet2 sobre sheet1 (plantilla)
        logger.debug(
            "Ninguna hoja coincide con el número esperado '%s', usando sheet2",
            expected_numero,
        )
        return sheets[-1]

    @staticmethod
    def _read_shared_strings(file_bytes: bytes) -> List[str]:
        return read_shared_strings_from_bytes(file_bytes)

    @staticmethod
    def _extract_rows(sheet_xml: str) -> Dict[int, Dict]:
        """Extrae filas como {row_num: {col: cell_info}}."""
        return extract_rows(sheet_xml)

    @staticmethod
    def _get_cell_value(cell_info: Dict, shared_strings: List[str]) -> str:
        return get_cell_value(cell_info, shared_strings)

    @staticmethod
    def _get_cell_number(cell_info: Dict, shared_strings: List[str]) -> Optional[float]:
        return get_cell_number(cell_info, shared_strings)

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

    # ------------------------------------------------------------------
    # Totales
    # ------------------------------------------------------------------

    def _read_totals_from_cells(
        self, rows: Dict[int, Dict], shared_strings: List[str]
    ) -> Optional[Dict]:
        """Lee subtotal, IVA y total directamente de las celdas del Excel.

        Busca filas cuyo texto contenga patrones reconocibles
        (``TOTAL PRESUPUESTO, I.V.A. INCLUIDO``, ``I.V.A.``, ``Total presupuesto``)
        y lee el valor numérico de la columna I (o H/J como fallback).

        Devuelve ``None`` si no encuentra al menos el total con IVA.
        """
        subtotal = None
        iva = None
        total = None

        for row_num in sorted(rows.keys()):
            if row_num < 15:
                continue
            cells = rows[row_num]

            row_text = ""
            for cell in cells.values():
                val = self._get_cell_value(cell, shared_strings)
                if val:
                    row_text += " " + val
            text_up = row_text.upper()

            num_val = None
            for col in ("I", "H", "J"):
                if col in cells:
                    num_val = self._get_cell_number(cells[col], shared_strings)
                    if num_val is not None:
                        break
            if num_val is None:
                continue

            if "TOTAL" in text_up and "I.V.A" in text_up and "INCLUIDO" in text_up:
                total = num_val
            elif "I.V.A" in text_up and "TOTAL" not in text_up and "INCLUIDO" not in text_up:
                iva = num_val
            elif ("TOTAL PRESUPUESTO" in text_up
                  and "PARCIAL" not in text_up
                  and "I.V.A" not in text_up):
                subtotal = num_val

        if total is None:
            return None

        if subtotal is None and iva is not None:
            subtotal = round(total - iva, 2)
        elif iva is None and subtotal is not None:
            iva = round(total - subtotal, 2)

        return {
            "subtotal": float(subtotal) if subtotal else 0.0,
            "iva": float(iva) if iva else 0.0,
            "total": float(total),
        }

    @staticmethod
    def _calculate_totals(partidas: List[Dict]) -> Dict:
        """Calcula subtotal, IVA y total a partir de las partidas (fallback)."""
        subtotal = sum((p["importe"] for p in partidas), 0.0)
        iva = round(subtotal * IVA_RATE, 2)
        total = round(subtotal + iva, 2)
        return {"subtotal": round(subtotal, 2), "iva": iva, "total": total}

    # ------------------------------------------------------------------
    # Lectura de total desde texto "Asciende..."
    # ------------------------------------------------------------------

    def read_total_from_text(
        self,
        file_path: str,
        expected_numero: str = "",
    ) -> Optional[float]:
        """Extrae el total del presupuesto desde la frase ``Asciende...``.

        Busca en todas las hojas del archivo la frase:

          *"Asciende el presupuesto de ejecución material a la expresada
          cantidad de ... EUROS ..."*

        **Solo** devuelve el total si lo encuentra en una hoja cuyo número
        de cabecera (celda E5) **coincide** con ``expected_numero``.
        Esto evita devolver importes de hojas copiadas de otros proyectos
        (sheet1 suele conservar los datos del proyecto original).

        Args:
            file_path: Ruta al archivo .xlsx.
            expected_numero: Número de proyecto esperado (``NNN-YY``).

        Returns:
            Importe total (float) o ``None`` si no se encuentra en una
            hoja verificada.
        """
        if not file_path or not os.path.exists(file_path):
            return None

        try:
            file_bytes = self._load_file_bytes(file_path)
            if file_bytes is None:
                return None

            shared_strings = self._read_shared_strings(file_bytes)
            sheets = self._read_all_sheets(file_bytes)
            if not sheets:
                return None

            norm_expected = normalize_project_num(expected_numero) if expected_numero else ""

            for sheet in sheets:
                rows = self._extract_rows(sheet["sheet_xml"])

                # Verificar que la hoja pertenece a ESTE proyecto
                if norm_expected:
                    header = self._extract_header(rows, shared_strings)
                    norm_sheet = normalize_project_num(header.get("numero", ""))
                    if norm_sheet and norm_sheet != norm_expected:
                        # Hoja de otro proyecto (copiada) → saltar
                        continue

                total = self._find_asciende_total(rows, shared_strings)
                if total is not None:
                    return total

            return None

        except Exception:
            logger.exception("Error al leer total por texto: %s", file_path)
            return None

    def _find_asciende_total(
        self,
        rows: Dict[int, Dict],
        shared_strings: List[str],
    ) -> Optional[float]:
        """Busca la frase 'Asciende...' en las filas y extrae el importe."""
        for row_num in sorted(rows.keys()):
            cells = rows[row_num]
            for cell_info in cells.values():
                text = self._get_cell_value(cell_info, shared_strings)
                if not text:
                    continue
                if "asciende" in text.lower():
                    total = extract_total_from_asciende(text)
                    if total is not None:
                        return total
        return None
