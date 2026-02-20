"""
Tests para PDFExporter.

Usa mocks para simular win32com.client sin requerir Excel real instalado.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from src.core.pdf_exporter import PDFExporter


class TestIsAvailable:
    """is_available: detecta si win32com está disponible."""

    @patch.dict("sys.modules", {"win32com": MagicMock(), "win32com.client": MagicMock()})
    def test_available_with_win32com(self):
        assert PDFExporter.is_available() is True

    @patch.dict("sys.modules", {"win32com": None, "win32com.client": None})
    def test_not_available_without_win32com(self):
        import importlib
        from src.core import pdf_exporter
        importlib.reload(pdf_exporter)
        assert pdf_exporter.PDFExporter.is_available() is False


class TestExport:
    """export: genera PDF a partir de xlsx."""

    def test_ruta_por_defecto(self, tmp_path):
        xlsx = str(tmp_path / "presupuesto.xlsx")
        with open(xlsx, "w") as f:
            f.write("fake")

        exporter = PDFExporter()
        expected_pdf = str(tmp_path / "presupuesto.pdf")

        mock_wb = MagicMock()
        mock_excel = MagicMock()
        mock_excel.Workbooks.Open.return_value = mock_wb

        import types
        mock_win32com = types.ModuleType("win32com")
        mock_client = types.ModuleType("win32com.client")
        mock_client.Dispatch = MagicMock(return_value=mock_excel)
        mock_win32com.client = mock_client

        with patch.object(PDFExporter, "is_available", return_value=True):
            with patch.dict("sys.modules", {
                "win32com": mock_win32com,
                "win32com.client": mock_client,
            }):
                ok, result = exporter.export(xlsx)

        assert ok is True
        assert result == expected_pdf
        mock_wb.ExportAsFixedFormat.assert_called_once_with(0, expected_pdf)
        mock_wb.Close.assert_called_once_with(SaveChanges=False)

    def test_ruta_personalizada(self, tmp_path):
        xlsx = str(tmp_path / "presupuesto.xlsx")
        pdf = str(tmp_path / "output" / "custom.pdf")
        with open(xlsx, "w") as f:
            f.write("fake")

        exporter = PDFExporter()
        mock_wb = MagicMock()
        mock_excel = MagicMock()
        mock_excel.Workbooks.Open.return_value = mock_wb

        import types
        mock_win32com = types.ModuleType("win32com")
        mock_client = types.ModuleType("win32com.client")
        mock_client.Dispatch = MagicMock(return_value=mock_excel)
        mock_win32com.client = mock_client

        with patch.object(PDFExporter, "is_available", return_value=True):
            with patch.dict("sys.modules", {
                "win32com": mock_win32com,
                "win32com.client": mock_client,
            }):
                ok, result = exporter.export(xlsx, pdf)

        assert ok is True
        assert result == os.path.abspath(pdf)

    def test_archivo_no_existe(self):
        exporter = PDFExporter()
        ok, msg = exporter.export("/no/existe.xlsx")
        assert ok is False
        assert "no existe" in msg

    def test_win32com_no_disponible(self, tmp_path):
        xlsx = str(tmp_path / "test.xlsx")
        with open(xlsx, "w") as f:
            f.write("fake")

        exporter = PDFExporter()
        with patch.object(PDFExporter, "is_available", return_value=False):
            ok, msg = exporter.export(xlsx)
        assert ok is False
        assert "win32com" in msg.lower() or "disponible" in msg.lower()

    def test_error_excel(self, tmp_path):
        xlsx = str(tmp_path / "test.xlsx")
        with open(xlsx, "w") as f:
            f.write("fake")

        exporter = PDFExporter()
        mock_excel = MagicMock()
        mock_excel.Workbooks.Open.side_effect = Exception("Excel error")

        import types
        mock_win32com = types.ModuleType("win32com")
        mock_client = types.ModuleType("win32com.client")
        mock_client.Dispatch = MagicMock(return_value=mock_excel)
        mock_win32com.client = mock_client

        with patch.object(PDFExporter, "is_available", return_value=True):
            with patch.dict("sys.modules", {
                "win32com": mock_win32com,
                "win32com.client": mock_client,
            }):
                ok, msg = exporter.export(xlsx)

        assert ok is False
        assert "error" in msg.lower()
