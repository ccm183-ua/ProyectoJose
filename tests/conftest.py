"""
Fixtures compartidas para toda la suite de tests de cubiApp.
"""

import shutil
import tempfile

import pytest

from src.core.excel_manager import ExcelManager
from src.core.template_manager import TemplateManager
from src.core.validators import DataValidator


@pytest.fixture
def temp_dir():
    """Directorio temporal que se limpia al acabar el test."""
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def excel_manager():
    """Instancia de ExcelManager."""
    return ExcelManager()


@pytest.fixture
def template_manager():
    """Instancia de TemplateManager."""
    return TemplateManager()


@pytest.fixture
def validator():
    """Instancia de DataValidator."""
    return DataValidator()
