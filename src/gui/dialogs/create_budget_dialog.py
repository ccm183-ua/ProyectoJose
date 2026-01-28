"""
Diálogo completo para creación de presupuesto.
"""

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QMessageBox
from PyQt6.QtCore import Qt
from src.gui.dialogs.folder_config_dialog import FolderConfigDialog
from src.gui.dialogs.data_input_dialog import DataInputDialog


class CreateBudgetDialog(QDialog):
    """Diálogo que guía al usuario a través del proceso de creación de presupuesto."""
    
    def __init__(self, parent=None):
        """Inicializa el diálogo."""
        super().__init__(parent)
        self.setWindowTitle("Crear Nuevo Presupuesto")
        self.setModal(True)
        self.folder_config = None
        self.budget_data = None
        self.save_path = None
        self.init_ui()
    
    def init_ui(self):
        """Inicializa la interfaz de usuario."""
        layout = QVBoxLayout()
        
        # Este diálogo coordinará los pasos:
        # 1. Seleccionar ubicación (se hace desde la ventana principal)
        # 2. Configurar carpeta (opcional)
        # 3. Ingresar datos
        # 4. Crear presupuesto
        
        # Por ahora, el diálogo está vacío y se usará desde la ventana principal
        # para coordinar los pasos
        
        self.setLayout(layout)
    
    def get_folder_config(self):
        """
        Muestra el diálogo de configuración de carpeta.
        
        Returns:
            FolderConfigDialog: Diálogo de configuración o None si se cancela
        """
        dialog = FolderConfigDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog
        return None
    
    def get_budget_data(self):
        """
        Muestra el diálogo de entrada de datos.
        
        Returns:
            dict: Datos del presupuesto o None si se cancela
        """
        dialog = DataInputDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.get_data()
        return None
