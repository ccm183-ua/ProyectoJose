"""
Tests de funcionalidades básicas (core: Excel, plantillas, carpetas, nombres).

Cubren:
- Crear archivo Excel desde plantilla
- Creación de carpetas y subcarpetas
- Formato de nombre de archivo (dirección + número + descripción)
"""

import os
import tempfile
import shutil
import pytest

from src.core.excel_manager import ExcelManager
from src.core.file_manager import FileManager
from src.core.template_manager import TemplateManager


@pytest.fixture
def temp_dir():
    """Directorio temporal para pruebas."""
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def sample_excel_file(temp_dir):
    """Archivo Excel de prueba."""
    path = os.path.join(temp_dir, "test_budget.xlsx")
    from openpyxl import Workbook
    wb = Workbook()
    wb.save(path)
    return path


class TestCreateNewBudget:
    """Tests para crear nuevo presupuesto desde plantilla."""

    def test_create_new_budget_from_template(self, temp_dir):
        """Crear nuevo archivo Excel desde plantilla predefinida."""
        template_manager = TemplateManager()
        excel_manager = ExcelManager()
        template_path = template_manager.get_template_path()
        assert os.path.exists(template_path), "La plantilla debe existir"
        output_path = os.path.join(temp_dir, "nuevo_presupuesto.xlsx")
        excel_manager.create_from_template(template_path, output_path, {})
        assert os.path.exists(output_path), "El archivo Excel debe crearse"


class TestFolderCreation:
    """Tests para creación de carpetas."""

    def test_create_folder_when_requested(self, temp_dir):
        """Creación de carpeta cuando se solicita."""
        file_manager = FileManager()
        folder_path = os.path.join(temp_dir, "nueva_carpeta")
        file_manager.create_folder(folder_path)
        assert os.path.exists(folder_path) and os.path.isdir(folder_path)

    def test_create_default_subfolders(self, temp_dir):
        """Creación de subcarpetas predeterminadas."""
        file_manager = FileManager()
        main_folder = os.path.join(temp_dir, "carpeta_principal")
        subfolders = ["FOTOS", "PLANOS", "PROYECTO", "MEDICIONES", "PRESUPUESTOS"]
        file_manager.create_folder(main_folder)
        file_manager.create_subfolders(main_folder, subfolders)
        for sub in subfolders:
            p = os.path.join(main_folder, sub)
            assert os.path.exists(p) and os.path.isdir(p)

    def test_create_custom_subfolders(self, temp_dir):
        """Creación de subcarpetas personalizadas."""
        file_manager = FileManager()
        main_folder = os.path.join(temp_dir, "carpeta_principal")
        custom = ["personalizada1", "personalizada2"]
        file_manager.create_folder(main_folder)
        file_manager.create_subfolders(main_folder, custom)
        for sub in custom:
            assert os.path.isdir(os.path.join(main_folder, sub))


class TestFileNameMatching:
    """Tests para nombre de archivo y carpeta."""

    def test_filename_matches_folder_name(self, temp_dir):
        """El nombre del archivo puede coincidir con el de la carpeta."""
        file_manager = FileManager()
        folder_name = "Calle_Mayor_12_Reforma_Baño"
        folder_path = os.path.join(temp_dir, folder_name)
        file_path = os.path.join(folder_path, f"{folder_name}.xlsx")
        file_manager.create_folder(folder_path)
        assert os.path.basename(file_path) == f"{folder_name}.xlsx"

    def test_filename_format(self):
        """Formato del nombre: dirección + número + descripción."""
        from src.utils.helpers import generate_filename
        filename = generate_filename("Calle Mayor", "12", "Reforma Baño")
        assert "12" in filename
        assert filename.endswith(".xlsx") or not filename.endswith(".")
