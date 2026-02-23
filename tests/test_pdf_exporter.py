"""
Tests para PDFExporter.

- Detección de filas: usa archivos xlsx reales creados con openpyxl.
- Inyección XML: verifica que rowBreaks y definedNames se insertan.
- apply_page_config: verifica modificación in-place del xlsx.
- Export: usa mocks COM (no requiere Excel instalado).
"""

import os
import re
import zipfile
import pytest
from unittest.mock import MagicMock, patch

from openpyxl import Workbook

from src.core.pdf_exporter import PDFExporter


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _create_test_xlsx(path, obra_rows=None):
    """Crea un xlsx mínimo con "Obra:" en las filas indicadas de columna A."""
    wb = Workbook()
    ws = wb.active
    ws.title = "PRESUP FINAL"
    for r in (obra_rows or []):
        ws.cell(row=r, column=1, value=f"Obra: TEST FILA {r}.")
    wb.save(str(path))
    return str(path)


def _make_com_mocks(mock_excel):
    """Crea los módulos mock de win32com + pythoncom."""
    import types
    mock_win32com = types.ModuleType("win32com")
    mock_client = types.ModuleType("win32com.client")
    mock_client.Dispatch = MagicMock(return_value=mock_excel)
    mock_win32com.client = mock_client
    mock_pythoncom = types.ModuleType("pythoncom")
    mock_pythoncom.CoInitialize = MagicMock()
    mock_pythoncom.CoUninitialize = MagicMock()
    return mock_win32com, mock_client, mock_pythoncom


def _read_zip_entry(xlsx_path, entry_name):
    """Lee y decodifica un archivo XML dentro de un xlsx."""
    with zipfile.ZipFile(xlsx_path, "r") as z:
        return z.read(entry_name).decode("utf-8")


# ------------------------------------------------------------------
# _find_obra_rows
# ------------------------------------------------------------------

class TestFindObraRows:
    """Detección de filas Obra: con openpyxl read-only."""

    def test_header_y_summary(self, tmp_path):
        xlsx = _create_test_xlsx(tmp_path / "t.xlsx", obra_rows=[14, 51])
        h, s = PDFExporter._find_obra_rows(xlsx)
        assert h == 14
        assert s == 51

    def test_solo_header(self, tmp_path):
        xlsx = _create_test_xlsx(tmp_path / "t.xlsx", obra_rows=[14])
        h, s = PDFExporter._find_obra_rows(xlsx)
        assert h == 14
        assert s is None

    def test_sin_obra(self, tmp_path):
        xlsx = _create_test_xlsx(tmp_path / "t.xlsx", obra_rows=[])
        h, s = PDFExporter._find_obra_rows(xlsx)
        assert h is None
        assert s is None

    def test_obra_fuera_de_cabecera(self, tmp_path):
        """Obra: solo en fila > 20: no se detecta header, sí summary."""
        xlsx = _create_test_xlsx(tmp_path / "t.xlsx", obra_rows=[51])
        h, s = PDFExporter._find_obra_rows(xlsx)
        assert h is None
        assert s == 51

    def test_multiples_obras(self, tmp_path):
        xlsx = _create_test_xlsx(tmp_path / "t.xlsx", obra_rows=[14, 40, 60])
        h, s = PDFExporter._find_obra_rows(xlsx)
        assert h == 14
        assert s == 60


# ------------------------------------------------------------------
# _inject_row_breaks / _inject_print_titles
# ------------------------------------------------------------------

class TestInjectRowBreaks:

    def test_inserta_despues_de_headerFooter(self):
        xml = '<worksheet><headerFooter>content</headerFooter><drawing r:id="rId1"/></worksheet>'
        result = PDFExporter._inject_row_breaks(xml, 51)
        assert '<rowBreaks count="1"' in result
        assert '<brk id="50"' in result
        assert result.index("</headerFooter>") < result.index("<rowBreaks")
        assert result.index("</rowBreaks>") < result.index("<drawing")

    def test_inserta_despues_de_headerFooter_autocerrado(self):
        xml = '<worksheet><headerFooter/><drawing r:id="rId1"/></worksheet>'
        result = PDFExporter._inject_row_breaks(xml, 51)
        assert '<brk id="50"' in result
        assert result.index("<headerFooter/>") < result.index("<rowBreaks")

    def test_inserta_antes_de_drawing_sin_headerFooter(self):
        xml = '<worksheet><drawing r:id="rId1"/></worksheet>'
        result = PDFExporter._inject_row_breaks(xml, 30)
        assert '<brk id="29"' in result
        assert result.index("<rowBreaks") < result.index("<drawing")

    def test_fallback_antes_de_cierre_worksheet(self):
        xml = "<worksheet><sheetData/></worksheet>"
        result = PDFExporter._inject_row_breaks(xml, 10)
        assert '<brk id="9"' in result
        assert result.index("</rowBreaks>") < result.index("</worksheet>")

    def test_reemplaza_rowBreaks_existente(self):
        xml = (
            '<worksheet><headerFooter/>'
            '<rowBreaks count="1" manualBreakCount="1">'
            '<brk id="99" max="16383" man="1"/>'
            '</rowBreaks>'
            '</worksheet>'
        )
        result = PDFExporter._inject_row_breaks(xml, 51)
        assert 'id="99"' not in result
        assert 'id="50"' in result


class TestInjectPrintTitles:

    def test_inserta_despues_de_sheets(self):
        xml = '<workbook><sheets><sheet name="PRESUP FINAL" sheetId="1"/></sheets><calcPr/></workbook>'
        result = PDFExporter._inject_print_titles(xml, 14)
        assert "_xlnm.Print_Titles" in result
        assert "'PRESUP FINAL'!$14:$16" in result
        assert result.index("</sheets>") < result.index("<definedNames>")

    def test_usa_nombre_de_hoja_real(self):
        xml = '<workbook><sheets><sheet name="Mi Hoja"/></sheets></workbook>'
        result = PDFExporter._inject_print_titles(xml, 5)
        assert "'Mi Hoja'!$5:$7" in result

    def test_reemplaza_definedNames_existente(self):
        xml = (
            '<workbook><sheets><sheet name="S1"/></sheets>'
            '<definedNames><definedName name="old">x</definedName></definedNames>'
            '</workbook>'
        )
        result = PDFExporter._inject_print_titles(xml, 14)
        assert "old" not in result
        assert "_xlnm.Print_Titles" in result


# ------------------------------------------------------------------
# apply_page_config (modifica el xlsx original in-place)
# ------------------------------------------------------------------

class TestApplyPageConfig:
    """apply_page_config solo inyecta rowBreaks (NO PrintTitles).

    Los PrintTitles se gestionan exclusivamente vía COM durante export,
    para poder excluir la última página (resumen).
    """

    def test_aplica_rowBreaks_sin_printTitles(self, tmp_path):
        xlsx = _create_test_xlsx(tmp_path / "t.xlsx", obra_rows=[14, 51])
        result = PDFExporter.apply_page_config(xlsx, header_row=14, summary_row=51)
        assert result is True

        sheet_xml = _read_zip_entry(xlsx, "xl/worksheets/sheet1.xml")
        assert '<brk id="50"' in sheet_xml

        wb_xml = _read_zip_entry(xlsx, "xl/workbook.xml")
        assert "_xlnm.Print_Titles" not in wb_xml

    def test_solo_header_sin_summary_retorna_false(self, tmp_path):
        """Sin summary_row no hay nada que modificar."""
        xlsx = _create_test_xlsx(tmp_path / "t.xlsx", obra_rows=[14])
        result = PDFExporter.apply_page_config(xlsx, header_row=14, summary_row=None)
        assert result is False

    def test_solo_summary_sin_header(self, tmp_path):
        xlsx = _create_test_xlsx(tmp_path / "t.xlsx", obra_rows=[51])
        result = PDFExporter.apply_page_config(xlsx, header_row=None, summary_row=51)
        assert result is True

        sheet_xml = _read_zip_entry(xlsx, "xl/worksheets/sheet1.xml")
        assert '<brk id="50"' in sheet_xml

    def test_retorna_false_sin_datos(self, tmp_path):
        xlsx = _create_test_xlsx(tmp_path / "t.xlsx")
        result = PDFExporter.apply_page_config(xlsx, header_row=None, summary_row=None)
        assert result is False

    def test_idempotente(self, tmp_path):
        """Aplicar dos veces no duplica rowBreaks."""
        xlsx = _create_test_xlsx(tmp_path / "t.xlsx", obra_rows=[14, 51])
        PDFExporter.apply_page_config(xlsx, header_row=14, summary_row=51)
        PDFExporter.apply_page_config(xlsx, header_row=14, summary_row=51)

        sheet_xml = _read_zip_entry(xlsx, "xl/worksheets/sheet1.xml")
        assert sheet_xml.count("<rowBreaks") == 1


# ------------------------------------------------------------------
# is_available
# ------------------------------------------------------------------

class TestIsAvailable:

    @patch.dict("sys.modules", {"win32com": MagicMock(), "win32com.client": MagicMock()})
    def test_available_with_win32com(self):
        assert PDFExporter.is_available() is True

    @patch.dict("sys.modules", {"win32com": None, "win32com.client": None})
    def test_not_available_without_win32com(self):
        import importlib
        from src.core import pdf_exporter
        importlib.reload(pdf_exporter)
        assert pdf_exporter.PDFExporter.is_available() is False


# ------------------------------------------------------------------
# export (COM mockeado)
# ------------------------------------------------------------------

class TestExport:

    def test_ruta_por_defecto(self, tmp_path):
        xlsx = _create_test_xlsx(tmp_path / "presupuesto.xlsx")
        expected_pdf = str(tmp_path / "presupuesto.pdf")

        mock_wb = MagicMock()
        mock_excel = MagicMock()
        mock_excel.Workbooks.Open.return_value = mock_wb
        mock_w32, mock_cl, mock_pycom = _make_com_mocks(mock_excel)

        with patch.object(PDFExporter, "is_available", return_value=True), \
             patch.dict("sys.modules", {
                 "win32com": mock_w32,
                 "win32com.client": mock_cl,
                 "pythoncom": mock_pycom,
             }):
            ok, result = PDFExporter().export(xlsx)

        assert ok is True
        assert result == expected_pdf
        mock_wb.ExportAsFixedFormat.assert_called_once_with(0, expected_pdf)
        mock_wb.Close.assert_called_once_with(SaveChanges=False)

    def test_ruta_personalizada(self, tmp_path):
        xlsx = _create_test_xlsx(tmp_path / "presupuesto.xlsx")
        pdf = str(tmp_path / "output" / "custom.pdf")

        mock_wb = MagicMock()
        mock_excel = MagicMock()
        mock_excel.Workbooks.Open.return_value = mock_wb
        mock_w32, mock_cl, mock_pycom = _make_com_mocks(mock_excel)

        with patch.object(PDFExporter, "is_available", return_value=True), \
             patch.dict("sys.modules", {
                 "win32com": mock_w32,
                 "win32com.client": mock_cl,
                 "pythoncom": mock_pycom,
             }):
            ok, result = PDFExporter().export(xlsx, pdf)

        assert ok is True
        assert result == os.path.abspath(pdf)

    def test_archivo_no_existe(self):
        ok, msg = PDFExporter().export("/no/existe.xlsx")
        assert ok is False
        assert "no existe" in msg

    def test_win32com_no_disponible(self, tmp_path):
        xlsx = _create_test_xlsx(tmp_path / "test.xlsx")
        with patch.object(PDFExporter, "is_available", return_value=False):
            ok, msg = PDFExporter().export(xlsx)
        assert ok is False
        assert "win32com" in msg.lower() or "disponible" in msg.lower()

    def test_error_excel(self, tmp_path):
        xlsx = _create_test_xlsx(tmp_path / "test.xlsx")

        mock_excel = MagicMock()
        mock_excel.Workbooks.Open.side_effect = Exception("Excel error")
        mock_w32, mock_cl, mock_pycom = _make_com_mocks(mock_excel)

        with patch.object(PDFExporter, "is_available", return_value=True), \
             patch.dict("sys.modules", {
                 "win32com": mock_w32,
                 "win32com.client": mock_cl,
                 "pythoncom": mock_pycom,
             }):
            ok, msg = PDFExporter().export(xlsx)

        assert ok is False
        assert "error" in msg.lower()

    def test_export_no_modifica_xlsx(self, tmp_path):
        """export() ya no modifica el xlsx; solo abre y exporta."""
        xlsx = _create_test_xlsx(tmp_path / "test.xlsx", obra_rows=[14, 51])

        mock_wb = MagicMock()
        mock_excel = MagicMock()
        mock_excel.Workbooks.Open.return_value = mock_wb
        mock_w32, mock_cl, mock_pycom = _make_com_mocks(mock_excel)

        with patch.object(PDFExporter, "is_available", return_value=True), \
             patch.dict("sys.modules", {
                 "win32com": mock_w32,
                 "win32com.client": mock_cl,
                 "pythoncom": mock_pycom,
             }):
            ok, _ = PDFExporter().export(xlsx)

        assert ok is True
        sheet_xml = _read_zip_entry(xlsx, "xl/worksheets/sheet1.xml")
        assert "rowBreaks" not in sheet_xml

    def test_coinitialize_called(self, tmp_path):
        xlsx = _create_test_xlsx(tmp_path / "test.xlsx")

        mock_wb = MagicMock()
        mock_excel = MagicMock()
        mock_excel.Workbooks.Open.return_value = mock_wb
        mock_w32, mock_cl, mock_pycom = _make_com_mocks(mock_excel)

        with patch.object(PDFExporter, "is_available", return_value=True), \
             patch.dict("sys.modules", {
                 "win32com": mock_w32,
                 "win32com.client": mock_cl,
                 "pythoncom": mock_pycom,
             }):
            PDFExporter().export(xlsx)

        mock_pycom.CoInitialize.assert_called_once()
