"""
Exportador de presupuestos Excel a PDF.

Usa win32com.client (Microsoft Excel COM automation) para generar un PDF
idéntico al "Imprimir como PDF" desde Excel. Requiere Microsoft Excel instalado.
"""

import os
from typing import Tuple


class PDFExporter:
    """Exporta un .xlsx a PDF usando Excel COM (Windows)."""

    @staticmethod
    def is_available() -> bool:
        """True si Microsoft Excel está disponible en el sistema."""
        try:
            import win32com.client  # noqa: F401
            return True
        except ImportError:
            return False

    def export(self, xlsx_path: str, pdf_path: str = None) -> Tuple[bool, str]:
        """
        Exporta un xlsx a PDF.

        Args:
            xlsx_path: Ruta al archivo xlsx.
            pdf_path: Ruta destino del PDF (default: mismo directorio, mismo nombre .pdf).

        Returns:
            (True, ruta_pdf) si éxito, (False, mensaje_error) si falla.
        """
        if not os.path.exists(xlsx_path):
            return (False, f"El archivo no existe: {xlsx_path}")

        xlsx_path = os.path.abspath(xlsx_path)

        if not pdf_path:
            base, _ = os.path.splitext(xlsx_path)
            pdf_path = base + ".pdf"
        pdf_path = os.path.abspath(pdf_path)

        if not self.is_available():
            return (False, "win32com no está disponible. Instala pywin32.")

        excel = None
        wb = None
        try:
            import win32com.client
            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False

            wb = excel.Workbooks.Open(xlsx_path)
            wb.ExportAsFixedFormat(0, pdf_path)  # 0 = xlTypePDF

            return (True, pdf_path)
        except Exception as e:
            return (False, f"Error al exportar: {e}")
        finally:
            if wb:
                try:
                    wb.Close(SaveChanges=False)
                except Exception:
                    pass
            if excel:
                try:
                    excel.Quit()
                except Exception:
                    pass
