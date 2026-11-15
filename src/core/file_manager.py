"""
Gestor de archivos y carpetas.
"""

import os


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
    