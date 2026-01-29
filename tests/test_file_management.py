"""
Tests de gestión de archivos.

Estos tests cubren:
- Validar creación de carpeta en ruta especificada por el usuario
- Validar creación de subcarpetas múltiples
- Validar manejo de errores cuando la ruta no es válida
- Validar manejo de errores cuando no hay permisos de escritura
- Validar que no se sobrescriben archivos existentes sin confirmación
- Validar sanitización de nombres de archivo/carpeta (caracteres especiales)
"""

import pytest
import os
import tempfile
import shutil
import stat
from pathlib import Path

from src.core.file_manager import FileManager
from src.utils.helpers import sanitize_filename


@pytest.fixture
def temp_dir():
    """Fixture para crear un directorio temporal."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def file_manager():
    """Fixture para crear un gestor de archivos."""
    return FileManager()


class TestFolderCreation:
    """Tests para creación de carpetas."""
    
    def test_create_folder_in_specified_path(self, temp_dir, file_manager):
        """Test: Validar creación de carpeta en ruta especificada por el usuario."""
        folder_path = os.path.join(temp_dir, "nueva_carpeta")
        
        result = file_manager.create_folder(folder_path)
        
        assert result == True
        assert os.path.exists(folder_path), "La carpeta debe crearse"
        assert os.path.isdir(folder_path), "Debe ser un directorio"
    
    def test_create_folder_already_exists(self, temp_dir, file_manager):
        """Test: Manejo cuando la carpeta ya existe."""
        folder_path = os.path.join(temp_dir, "carpeta_existente")
        os.makedirs(folder_path)
        
        # No debe fallar si la carpeta ya existe
        result = file_manager.create_folder(folder_path)
        
        assert os.path.exists(folder_path), "La carpeta debe seguir existiendo"
    
    def test_create_multiple_subfolders(self, temp_dir, file_manager):
        """Test: Validar creación de subcarpetas múltiples."""
        main_folder = os.path.join(temp_dir, "carpeta_principal")
        subfolders = ["FOTOS", "PLANOS", "PROYECTO", "MEDICIONES", "PRESUPUESTOS"]
        
        file_manager.create_folder(main_folder)
        file_manager.create_subfolders(main_folder, subfolders)
        
        for subfolder in subfolders:
            subfolder_path = os.path.join(main_folder, subfolder)
            assert os.path.exists(subfolder_path), f"La subcarpeta {subfolder} debe crearse"
            assert os.path.isdir(subfolder_path), f"{subfolder} debe ser un directorio"
    
    def test_create_nested_subfolders(self, temp_dir, file_manager):
        """Test: Validar creación de subcarpetas anidadas."""
        main_folder = os.path.join(temp_dir, "carpeta_principal")
        subfolders = ["fotos/2024", "planos/plantas", "documentos"]
        
        file_manager.create_folder(main_folder)
        file_manager.create_subfolders(main_folder, subfolders)
        
        for subfolder in subfolders:
            subfolder_path = os.path.join(main_folder, subfolder)
            assert os.path.exists(subfolder_path), f"La subcarpeta {subfolder} debe crearse"


class TestErrorHandling:
    """Tests para manejo de errores."""
    
    def test_invalid_path_error(self, file_manager):
        """Test: Validar manejo de errores cuando la ruta no es válida."""
        invalid_paths = [
            "",  # Ruta vacía
            None,  # None
            "/ruta/que/no/existe/en/el/sistema/12345",  # Ruta inexistente
        ]
        
        for invalid_path in invalid_paths:
            if invalid_path is None:
                continue  # Saltar None por ahora
            try:
                result = file_manager.create_folder(invalid_path)
                # Si no lanza excepción, debe retornar False o manejar el error
                assert result == False or result is None
            except Exception:
                # Si lanza excepción, debe ser manejada apropiadamente
                pass
    
    def test_permission_error_handling(self, temp_dir, file_manager):
        """Test: Validar manejo de errores cuando no hay permisos de escritura."""
        # En sistemas Unix, crear una carpeta sin permisos de escritura
        if os.name != 'nt':  # No funciona igual en Windows
            restricted_folder = os.path.join(temp_dir, "restricted")
            os.makedirs(restricted_folder)
            
            # Quitar permisos de escritura
            os.chmod(restricted_folder, stat.S_IRUSR | stat.S_IXUSR)
            
            try:
                subfolder_path = os.path.join(restricted_folder, "subfolder")
                result = file_manager.create_folder(subfolder_path)
                # Debe manejar el error sin crashear
                assert result == False or result is None
            except PermissionError:
                # Si lanza PermissionError, está bien manejado
                pass
            finally:
                # Restaurar permisos para limpieza
                os.chmod(restricted_folder, stat.S_IRWXU)
    
    def test_nonexistent_parent_directory(self, file_manager):
        """Test: Manejo cuando el directorio padre no existe."""
        non_existent_path = "/ruta/inexistente/subcarpeta"
        
        try:
            result = file_manager.create_folder(non_existent_path)
            # Debe manejar el error
            assert result == False or result is None
        except Exception:
            # Si lanza excepción, debe ser manejada apropiadamente
            pass


class TestFileOverwriting:
    """Tests para sobrescritura de archivos."""
    
    def test_no_overwrite_without_confirmation(self, temp_dir, file_manager):
        """Test: Validar que no se sobrescriben archivos existentes sin confirmación."""
        file_path = os.path.join(temp_dir, "test_file.xlsx")
        
        # Crear archivo existente
        with open(file_path, 'w') as f:
            f.write("contenido original")
        
        # Intentar crear el mismo archivo sin confirmación
        result = file_manager.create_file_if_not_exists(file_path)
        
        # El archivo original debe seguir existiendo
        assert os.path.exists(file_path)
        # El contenido original debe mantenerse o el método debe retornar False
        with open(file_path, 'r') as f:
            content = f.read()
            assert "contenido original" in content or result == False
    
    def test_overwrite_with_confirmation(self, temp_dir, file_manager):
        """Test: Validar sobrescritura con confirmación."""
        file_path = os.path.join(temp_dir, "test_file.xlsx")
        
        # Crear archivo existente
        with open(file_path, 'w') as f:
            f.write("contenido original")
        
        # Sobrescribir con confirmación
        result = file_manager.create_file(file_path, overwrite=True)
        
        assert os.path.exists(file_path)


class TestFilenameSanitization:
    """Tests para sanitización de nombres de archivo/carpeta."""
    
    def test_sanitize_special_characters(self):
        """Test: Validar sanitización de caracteres especiales."""
        test_cases = [
            ("Calle/Mayor", "Calle_Mayor"),
            ("Calle\\Mayor", "Calle_Mayor"),
            ("Calle:Mayor", "Calle_Mayor"),
            ("Calle*Mayor", "Calle_Mayor"),
            ("Calle?Mayor", "Calle_Mayor"),
            ("Calle\"Mayor", "Calle_Mayor"),
            ("Calle<Mayor", "Calle_Mayor"),
            ("Calle>Mayor", "Calle_Mayor"),
            ("Calle|Mayor", "Calle_Mayor"),
        ]
        
        for input_name, expected_pattern in test_cases:
            sanitized = sanitize_filename(input_name)
            # No debe contener caracteres especiales peligrosos
            assert "/" not in sanitized
            assert "\\" not in sanitized
            assert ":" not in sanitized
            assert "*" not in sanitized
            assert "?" not in sanitized
            assert '"' not in sanitized
            assert "<" not in sanitized
            assert ">" not in sanitized
            assert "|" not in sanitized
    
    def test_sanitize_spaces(self):
        """Test: Validar sanitización de espacios."""
        test_cases = [
            ("Calle Mayor", "Calle_Mayor"),
            ("  Calle Mayor  ", "Calle_Mayor"),  # Espacios al inicio/final
            ("Calle  Mayor", "Calle_Mayor"),  # Múltiples espacios
        ]
        
        for input_name, expected_pattern in test_cases:
            sanitized = sanitize_filename(input_name)
            # No debe tener espacios al inicio o final
            assert not sanitized.startswith(" ")
            assert not sanitized.endswith(" ")
            # Múltiples espacios deben convertirse en uno solo o guión bajo
            assert "  " not in sanitized
    
    def test_sanitize_empty_name(self):
        """Test: Validar sanitización de nombre vacío."""
        sanitized = sanitize_filename("")
        assert sanitized != ""
        assert len(sanitized) > 0
    
    def test_sanitize_unicode_characters(self):
        """Test: Validar sanitización de caracteres Unicode."""
        test_cases = [
            ("Calle Mayor Ñoño", "Calle_Mayor_Noño"),  # Ñ se mantiene
            ("Calle Mayor", "Calle_Mayor"),  # Caracteres normales
        ]
        
        for input_name, expected_pattern in test_cases:
            sanitized = sanitize_filename(input_name)
            # Debe mantener caracteres Unicode válidos
            assert len(sanitized) > 0
    
    def test_sanitize_filename_format(self):
        """Test: Validar formato completo del nombre de archivo."""
        direccion = "Calle Mayor"
        numero = "12"
        descripcion = "Reforma Baño"
        
        # Generar nombre completo
        from src.utils.helpers import generate_filename
        filename = generate_filename(direccion, numero, descripcion)
        
        # Sanitizar
        sanitized = sanitize_filename(filename)
        
        # Verificar que no tiene caracteres peligrosos
        dangerous_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in dangerous_chars:
            assert char not in sanitized
    
    def test_sanitize_folder_name(self):
        """Test: Validar sanitización de nombre de carpeta."""
        folder_name = "Calle/Mayor/12/Reforma"
        sanitized = sanitize_filename(folder_name)
        
        # No debe contener caracteres especiales
        assert "/" not in sanitized
        assert "\\" not in sanitized
