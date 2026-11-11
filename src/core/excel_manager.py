"""
Gestor de archivos Excel. Facade que delega en módulos especializados.
"""

from src.core.template_manager import TemplateManager
from src.core.excel_template_filler import TemplateFiller
from src.core.excel_partidas_writer import PartidasWriter
from src.core.excel_budget_editor import BudgetEditor


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
