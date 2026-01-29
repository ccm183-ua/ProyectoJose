"""
Generador de nombres de proyecto según el formato especificado.
"""

from src.core.project_parser import ProjectParser


class ProjectNameGenerator:
    """Clase para generar nombres de proyecto."""
    
    def __init__(self):
        """Inicializa el generador."""
        self.parser = ProjectParser()
    
    def generate_project_name(self, project_data: dict) -> str:
        """
        Genera el nombre del proyecto según el formato:
        [Nº-(últimos dos dígitos de) FECHA CLIENTE - LOCALIDAD (TIPO)]
        
        Ejemplo: 3-26 C.P. SAN SALVADOR Nº5 - ALICANTE (REHABILITACIÓN ZAGUÁN)
        
        Args:
            project_data: Diccionario con los datos del proyecto
            
        Returns:
            str: Nombre del proyecto generado
        """
        numero = project_data.get('numero', '').strip()
        fecha = project_data.get('fecha', '').strip()
        cliente = project_data.get('cliente', '').strip()
        localidad = project_data.get('localidad', '').strip()
        tipo = project_data.get('tipo', '').strip()
        
        # Extraer año (últimos dos dígitos)
        year = self.parser.extract_year_from_date(fecha)
        
        # Construir nombre base: Nº-YY CLIENTE
        if year:
            project_name = f"{numero}-{year} {cliente}".strip()
        else:
            project_name = f"{numero} {cliente}".strip()
        
        # Añadir localidad si existe
        if localidad:
            project_name += f" - {localidad}"
        
        # Añadir tipo si existe
        if tipo:
            project_name += f" ({tipo})"
        
        return project_name.strip()
