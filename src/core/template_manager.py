"""
Gestor de plantillas Excel.
"""

import os
from src.utils.helpers import get_template_path


class TemplateManager:
    """Clase para gestionar plantillas Excel."""
    
    def __init__(self):
        """Inicializa el gestor de plantillas."""
        self._template_path = None
    
    def get_template_path(self, template_name=None):
        """
        Obtiene la ruta de la plantilla.
        
        Args:
            template_name: Nombre de la plantilla (opcional, por defecto usa la principal)
            
        Returns:
            str: Ruta de la plantilla
        """
        if template_name is None:
            if self._template_path is None:
                self._template_path = get_template_path()
            return self._template_path
        else:
            # Para múltiples plantillas en el futuro
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            template_path = os.path.join(project_root, 'templates', f"{template_name}.xlsx")
            return template_path
    
    def get_available_templates(self):
        """
        Obtiene lista de plantillas disponibles.
        
        Returns:
            list: Lista de nombres de plantillas disponibles
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        templates_dir = os.path.join(project_root, 'templates')
        
        if not os.path.exists(templates_dir):
            return []
        
        templates = []
        for filename in os.listdir(templates_dir):
            if filename.endswith('.xlsx') and not filename.startswith('~'):
                templates.append(filename.replace('.xlsx', ''))
        
        return templates if templates else ['budget_template']
