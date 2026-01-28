"""
Gestor de archivos y carpetas.
"""

import os
import shutil
from pathlib import Path


class FileManager:
    """Clase para gestionar archivos y carpetas."""
    
    def create_folder(self, folder_path):
        """
        Crea una carpeta en la ruta especificada.
        
        Args:
            folder_path: Ruta donde crear la carpeta
            
        Returns:
            bool: True si se creó correctamente, False en caso contrario
        """
        if not folder_path:
            return False
        
        try:
            # Crear carpeta si no existe
            os.makedirs(folder_path, exist_ok=True)
            return True
        except (OSError, PermissionError, ValueError) as e:
            return False
    
    def create_subfolders(self, parent_folder, subfolders):
        """
        Crea subcarpetas dentro de una carpeta padre.
        
        Args:
            parent_folder: Carpeta padre
            subfolders: Lista de nombres de subcarpetas
            
        Returns:
            bool: True si se crearon correctamente, False en caso contrario
        """
        if not parent_folder or not subfolders:
            return False
        
        try:
            for subfolder in subfolders:
                subfolder_path = os.path.join(parent_folder, subfolder)
                os.makedirs(subfolder_path, exist_ok=True)
            return True
        except (OSError, PermissionError) as e:
            return False
    
    def create_file_if_not_exists(self, file_path):
        """
        Crea un archivo solo si no existe.
        
        Args:
            file_path: Ruta del archivo
            
        Returns:
            bool: True si se creó o ya existía, False en caso contrario
        """
        if not file_path:
            return False
        
        if os.path.exists(file_path):
            return False  # No sobrescribir sin confirmación
        
        try:
            # Crear directorio padre si no existe
            parent_dir = os.path.dirname(file_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            
            # Crear archivo vacío
            with open(file_path, 'w') as f:
                pass
            
            return True
        except (OSError, PermissionError) as e:
            return False
    
    def create_file(self, file_path, overwrite=False):
        """
        Crea un archivo.
        
        Args:
            file_path: Ruta del archivo
            overwrite: Si True, sobrescribe archivos existentes
            
        Returns:
            bool: True si se creó correctamente, False en caso contrario
        """
        if not file_path:
            return False
        
        if os.path.exists(file_path) and not overwrite:
            return False
        
        try:
            # Crear directorio padre si no existe
            parent_dir = os.path.dirname(file_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            
            # Crear archivo vacío
            with open(file_path, 'w') as f:
                pass
            
            return True
        except (OSError, PermissionError) as e:
            return False
    
    def search_files(self, directory, pattern):
        """
        Busca archivos en un directorio que coincidan con un patrón.
        
        Args:
            directory: Directorio donde buscar
            pattern: Patrón de búsqueda
            
        Returns:
            list: Lista de archivos encontrados
        """
        if not directory or not os.path.exists(directory):
            return []
        
        results = []
        try:
            for filename in os.listdir(directory):
                if pattern.lower() in filename.lower():
                    file_path = os.path.join(directory, filename)
                    if os.path.isfile(file_path):
                        results.append(file_path)
        except (OSError, PermissionError):
            pass
        
        return results
    
    def filter_files(self, directory, pattern):
        """
        Filtra archivos en un directorio por patrón.
        
        Args:
            directory: Directorio donde buscar
            pattern: Patrón de filtrado
            
        Returns:
            list: Lista de archivos filtrados
        """
        return self.search_files(directory, pattern)
    
    def get_statistics(self, directory):
        """
        Obtiene estadísticas básicas de un directorio.
        
        Args:
            directory: Directorio a analizar
            
        Returns:
            dict: Diccionario con estadísticas
        """
        if not directory or not os.path.exists(directory):
            return {}
        
        try:
            files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
            excel_files = [f for f in files if f.endswith('.xlsx') or f.endswith('.xls')]
            
            return {
                'total_files': len(files),
                'excel_files': len(excel_files),
                'directory': directory
            }
        except (OSError, PermissionError):
            return {}
