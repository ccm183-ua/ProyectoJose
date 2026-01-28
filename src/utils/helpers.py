"""
Funciones auxiliares y utilidades.
"""

import re
import os


def sanitize_filename(filename):
    """
    Sanitiza un nombre de archivo eliminando caracteres peligrosos.
    
    Args:
        filename: Nombre de archivo a sanitizar
        
    Returns:
        str: Nombre de archivo sanitizado
    """
    if not filename:
        return "archivo_sin_nombre"
    
    # Reemplazar caracteres peligrosos
    dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    sanitized = filename
    
    for char in dangerous_chars:
        sanitized = sanitized.replace(char, '_')
    
    # Eliminar espacios al inicio y final
    sanitized = sanitized.strip()
    
    # Reemplazar múltiples espacios/guiones bajos con uno solo
    sanitized = re.sub(r'[\s_]+', '_', sanitized)
    
    # Si quedó vacío después de sanitizar, usar nombre por defecto
    if not sanitized:
        sanitized = "archivo_sin_nombre"
    
    return sanitized


def generate_filename(direccion, numero, descripcion):
    """
    Genera un nombre de archivo a partir de dirección, número y descripción.
    
    Args:
        direccion: Dirección de la obra
        numero: Número de la calle
        descripcion: Descripción breve
        
    Returns:
        str: Nombre de archivo generado (sin extensión)
    """
    # Sanitizar cada parte
    dir_sanitized = sanitize_filename(direccion)
    num_sanitized = sanitize_filename(str(numero))
    desc_sanitized = sanitize_filename(descripcion)
    
    # Combinar
    filename = f"{dir_sanitized}_{num_sanitized}_{desc_sanitized}"
    
    return filename


def get_template_path():
    """
    Obtiene la ruta absoluta de la plantilla.
    
    Returns:
        str: Ruta absoluta de la plantilla
    """
    # Obtener directorio del proyecto
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    template_path = os.path.join(project_root, 'templates', 'budget_template.xlsx')
    
    return template_path
