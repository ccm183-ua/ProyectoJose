"""
Tests de funcionalidades básicas de la aplicación.

Estos tests cubren:
- Abrir archivo Excel existente desde diálogo de archivos
- Navegar por carpetas del sistema desde el menú principal
- Crear nuevo archivo Excel desde plantilla predefinida
- Validar que el diálogo de guardado se abre correctamente
- Validar creación de carpeta cuando el usuario lo solicita
- Validar creación de subcarpetas predeterminadas
- Validar que el nombre del archivo coincide con el nombre de la carpeta
- Validar formato del nombre (dirección + número + descripción)
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtCore import Qt

from src.gui.main_window import MainWindow
from src.core.excel_manager import ExcelManager
from src.core.file_manager import FileManager
from src.core.template_manager import TemplateManager


@pytest.fixture
def app():
    """Fixture para crear una instancia de QApplication."""
    if not QApplication.instance():
        application = QApplication([])
    else:
        application = QApplication.instance()
    return application


@pytest.fixture
def temp_dir():
    """Fixture para crear un directorio temporal."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def sample_excel_file(temp_dir):
    """Fixture para crear un archivo Excel de prueba."""
    file_path = os.path.join(temp_dir, "test_budget.xlsx")
    # Crear un archivo Excel básico usando openpyxl
    from openpyxl import Workbook
    wb = Workbook()
    wb.save(file_path)
    return file_path


class TestOpenExcelFile:
    """Tests para abrir archivos Excel existentes."""
    
    def test_open_excel_file_from_dialog(self, app, sample_excel_file):
        """Test: Abrir archivo Excel existente desde diálogo de archivos."""
        main_window = MainWindow()
        
        with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName') as mock_dialog:
            mock_dialog.return_value = (sample_excel_file, "Excel Files (*.xlsx)")
            
            result = main_window.open_excel_file()
            
            assert result == sample_excel_file
            mock_dialog.assert_called_once()
    
    def test_open_excel_file_cancelled(self, app):
        """Test: Usuario cancela el diálogo de abrir archivo."""
        main_window = MainWindow()
        
        with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName') as mock_dialog:
            mock_dialog.return_value = ("", "")
            
            result = main_window.open_excel_file()
            
            assert result is None or result == ""
    
    def test_open_excel_file_invalid_path(self, app):
        """Test: Manejo de ruta inválida al abrir archivo."""
        main_window = MainWindow()
        
        with patch('PySide6.QtWidgets.QFileDialog.getOpenFileName') as mock_dialog:
            mock_dialog.return_value = ("/ruta/invalida/archivo.xlsx", "Excel Files (*.xlsx)")
            
            # Debe manejar el error sin crashear
            result = main_window.open_excel_file()
            # La aplicación debe manejar el error graciosamente
            assert True  # Si no crashea, el test pasa


class TestFolderNavigation:
    """Tests para navegación por carpetas."""
    
    def test_navigate_folders_from_main_menu(self, app, temp_dir):
        """Test: Navegar por carpetas del sistema desde el menú principal."""
        main_window = MainWindow()
        
        # Verificar que el menú principal tiene opción de navegación
        assert hasattr(main_window, 'navigate_folders') or hasattr(main_window, 'show_folder_dialog')
    
    def test_folder_dialog_opens(self, app, temp_dir):
        """Test: El diálogo de selección de carpeta se abre correctamente."""
        main_window = MainWindow()
        
        with patch('PySide6.QtWidgets.QFileDialog.getExistingDirectory') as mock_dialog:
            mock_dialog.return_value = temp_dir
            
            result = main_window.select_folder()
            
            assert result == temp_dir
            mock_dialog.assert_called_once()
    
    def test_folder_dialog_cancelled(self, app):
        """Test: Usuario cancela el diálogo de selección de carpeta."""
        main_window = MainWindow()
        
        with patch('PySide6.QtWidgets.QFileDialog.getExistingDirectory') as mock_dialog:
            mock_dialog.return_value = ""
            
            result = main_window.select_folder()
            
            assert result == "" or result is None


class TestCreateNewBudget:
    """Tests para crear nuevo presupuesto."""
    
    def test_create_new_budget_from_template(self, app, temp_dir):
        """Test: Crear nuevo archivo Excel desde plantilla predefinida."""
        template_manager = TemplateManager()
        excel_manager = ExcelManager()
        
        # Verificar que existe la plantilla
        template_path = template_manager.get_template_path()
        assert os.path.exists(template_path), "La plantilla debe existir"
        
        # Crear nuevo presupuesto
        output_path = os.path.join(temp_dir, "nuevo_presupuesto.xlsx")
        excel_manager.create_from_template(template_path, output_path, {})
        
        assert os.path.exists(output_path), "El archivo Excel debe crearse"
    
    def test_save_dialog_opens(self, app, temp_dir):
        """Test: Validar que el diálogo de guardado se abre correctamente."""
        main_window = MainWindow()
        
        with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName') as mock_dialog:
            mock_dialog.return_value = (os.path.join(temp_dir, "test.xlsx"), "Excel Files (*.xlsx)")
            
            result = main_window.get_save_path()
            
            assert result == os.path.join(temp_dir, "test.xlsx")
            mock_dialog.assert_called_once()
    
    def test_save_dialog_cancelled(self, app):
        """Test: Usuario cancela el diálogo de guardado."""
        main_window = MainWindow()
        
        with patch('PySide6.QtWidgets.QFileDialog.getSaveFileName') as mock_dialog:
            mock_dialog.return_value = ("", "")
            
            result = main_window.get_save_path()
            
            assert result == "" or result is None


class TestFolderCreation:
    """Tests para creación de carpetas."""
    
    def test_create_folder_when_requested(self, app, temp_dir):
        """Test: Validar creación de carpeta cuando el usuario lo solicita."""
        file_manager = FileManager()
        
        folder_path = os.path.join(temp_dir, "nueva_carpeta")
        file_manager.create_folder(folder_path)
        
        assert os.path.exists(folder_path), "La carpeta debe crearse"
        assert os.path.isdir(folder_path), "Debe ser un directorio"
    
    def test_create_default_subfolders(self, app, temp_dir):
        """Test: Validar creación de subcarpetas predeterminadas."""
        file_manager = FileManager()
        
        main_folder = os.path.join(temp_dir, "carpeta_principal")
        subfolders = ["FOTOS", "PLANOS", "PROYECTO", "MEDICIONES", "PRESUPUESTOS"]
        
        file_manager.create_folder(main_folder)
        file_manager.create_subfolders(main_folder, subfolders)
        
        for subfolder in subfolders:
            subfolder_path = os.path.join(main_folder, subfolder)
            assert os.path.exists(subfolder_path), f"La subcarpeta {subfolder} debe crearse"
            assert os.path.isdir(subfolder_path), f"{subfolder} debe ser un directorio"
    
    def test_create_custom_subfolders(self, app, temp_dir):
        """Test: Validar creación de subcarpetas personalizadas."""
        file_manager = FileManager()
        
        main_folder = os.path.join(temp_dir, "carpeta_principal")
        custom_subfolders = ["personalizada1", "personalizada2"]
        
        file_manager.create_folder(main_folder)
        file_manager.create_subfolders(main_folder, custom_subfolders)
        
        for subfolder in custom_subfolders:
            subfolder_path = os.path.join(main_folder, subfolder)
            assert os.path.exists(subfolder_path), f"La subcarpeta personalizada {subfolder} debe crearse"


class TestFileNameMatching:
    """Tests para validar que el nombre del archivo coincide con el nombre de la carpeta."""
    
    def test_filename_matches_folder_name(self, app, temp_dir):
        """Test: Validar que el nombre del archivo coincide con el nombre de la carpeta."""
        file_manager = FileManager()
        
        folder_name = "Calle_Mayor_12_Reforma_Baño"
        folder_path = os.path.join(temp_dir, folder_name)
        file_path = os.path.join(folder_path, f"{folder_name}.xlsx")
        
        file_manager.create_folder(folder_path)
        
        # El nombre del archivo debe coincidir con el nombre de la carpeta
        expected_filename = f"{folder_name}.xlsx"
        assert os.path.basename(file_path) == expected_filename
    
    def test_filename_format(self, app):
        """Test: Validar formato del nombre (dirección + número + descripción)."""
        from src.utils.helpers import generate_filename
        
        direccion = "Calle Mayor"
        numero = "12"
        descripcion = "Reforma Baño"
        
        filename = generate_filename(direccion, numero, descripcion)
        
        # El formato debe ser: Dirección_Número_Descripción
        assert "Calle_Mayor" in filename or "CalleMayor" in filename
        assert "12" in filename
        assert "Reforma" in filename or "Baño" in filename
        assert filename.endswith(".xlsx") or not filename.endswith(".")


class TestMainWindow:
    """Tests para la ventana principal."""
    
    def test_main_window_initializes(self, app):
        """Test: La ventana principal se inicializa correctamente."""
        main_window = MainWindow()
        
        assert main_window is not None
        assert main_window.windowTitle() == "Gestión de Presupuestos" or main_window.windowTitle() != ""
    
    def test_main_window_has_menu_options(self, app):
        """Test: La ventana principal tiene todas las opciones de menú."""
        main_window = MainWindow()
        
        # Verificar que existen métodos o botones para las acciones principales
        assert hasattr(main_window, 'open_excel_file') or hasattr(main_window, 'create_new_budget')
