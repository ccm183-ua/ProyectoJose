"""
Gestor de archivos Excel. Facade que delega en módulos especializados.
"""

from src.core.template_manager import TemplateManager
from src.core.excel_template_filler import TemplateFiller, SHEET_12220
from src.core.excel_partidas_writer import PartidasWriter, IVA_RATE
from src.core.excel_budget_editor import (
    BudgetEditor,
    DATA_START_ROW,
    IVA_ROW,
    SUBTOTAL_ROW,
    TOTAL_ROW,
)


class ExcelManager:
    """Clase para gestionar archivos Excel. Delega en TemplateFiller, PartidasWriter y BudgetEditor."""

    def __init__(self):
        """Inicializa el gestor de Excel."""
        self.template_manager = TemplateManager()
        self._template_filler = TemplateFiller()
        self._partidas_writer = PartidasWriter()
        self._budget_editor = BudgetEditor()

    def create_from_template(self, template_path, output_path, data):
        """Crea un archivo Excel desde una plantilla rellenando los datos."""
        return self._template_filler.create_from_template(template_path, output_path, data)

    def insert_partidas_via_xml(self, file_path, partidas):
        """Inserta partidas en el Excel usando manipulación XML directa en sheet2."""
        return self._partidas_writer.insert_partidas_via_xml(file_path, partidas)

    def update_header_fields(self, file_path, data):
        """Actualiza los campos de cabecera de un presupuesto existente."""
        return self._partidas_writer.update_header_fields(file_path, data)

    def append_partidas_via_xml(self, file_path, new_partidas):
        """Añade partidas al final de las existentes en un presupuesto."""
        return self._partidas_writer.append_partidas_via_xml(file_path, new_partidas)

    def load_budget(self, file_path):
        """Carga un presupuesto desde un archivo Excel."""
        return self._budget_editor.load_budget(file_path)

    def add_budget_row(self, file_path, budget_row):
        """Añade una fila de presupuesto al archivo Excel."""
        return self._budget_editor.add_budget_row(file_path, budget_row)

    def modify_budget_row(self, file_path, row_index, new_data):
        """Modifica una fila de presupuesto."""
        return self._budget_editor.modify_budget_row(file_path, row_index, new_data)

    def delete_budget_row(self, file_path, row_index):
        """Elimina una fila de presupuesto."""
        return self._budget_editor.delete_budget_row(file_path, row_index)

    def recalculate_totals(self, file_path):
        """Recalcula los totales del presupuesto."""
        return self._budget_editor.recalculate_totals(file_path)

    def save_budget(self, file_path):
        """Guarda un presupuesto."""
        return self._budget_editor.save_budget(file_path)
