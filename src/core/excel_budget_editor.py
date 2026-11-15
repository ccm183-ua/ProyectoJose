"""
Carga de presupuestos Excel con openpyxl.

(La edición de filas sueltas y el recálculo de totales de la versión 1 se
retiraron: la app escribe las partidas por XML en excel_partidas_writer.)
"""

import logging
import os

from openpyxl import load_workbook

logger = logging.getLogger(__name__)

class BudgetEditor:
    """Carga de presupuestos Excel."""

    def load_budget(self, file_path):
        """
        Carga un presupuesto desde un archivo Excel.

        Args:
            file_path: Ruta del archivo Excel

        Returns:
            Workbook: Objeto Workbook o None si hay error.
                      El llamante debe cerrar el workbook con wb.close().
        """
        try:
            if not os.path.exists(file_path):
                return None

            wb = load_workbook(file_path)
            return wb
        except Exception:
            logger.debug("No se pudo cargar el workbook: %s", file_path)
            return None
