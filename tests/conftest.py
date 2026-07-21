"""
Fixtures compartidas para toda la suite de tests de cubiApp.
"""

import os
import shutil
import tempfile

import pytest

from src.core.excel_manager import ExcelManager
from src.core.template_manager import TemplateManager
from src.core.validators import DataValidator

# Forzar plataforma offscreen antes de que cualquier test importe PySide6: evita
# crear ventanas nativas y, sobre todo, evita crear/destruir varias instancias
# de QApplication con backends distintos si cada módulo definiera su propio
# fixture qapp (eso provoca cuelgues intermitentes al pasar de un módulo a otro).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Los tests nunca deben escribir backups de BDD en la carpeta real del
# usuario (Documents/CubiApp/backups): cualquier test que conecte una BDD
# nueva dispara la migración/backup de H2.4. Redirigir a un directorio
# temporal de la sesión evita contaminar datos reales del usuario.
os.environ.setdefault("CUBIAPP_BACKUP_DIR", tempfile.mkdtemp(prefix="cubiapp_test_backups_"))

try:
    from PySide6.QtWidgets import QApplication

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False


@pytest.fixture(scope="session")
def qapp():
    """Instancia única de QApplication para toda la sesión de tests."""
    if not _HAS_PYSIDE6:
        pytest.skip("PySide6 no disponible")
    app = QApplication.instance() or QApplication([])
    return app


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
