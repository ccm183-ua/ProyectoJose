"""
Diálogo para configuración de carpeta y subcarpetas.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QLineEdit, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt


class FolderConfigDialog(QDialog):
    """Diálogo para configurar carpeta y subcarpetas."""
    
    DEFAULT_SUBFOLDERS = ["fotos", "planos", "documentos", "otros"]
    
    def __init__(self, parent=None):
        """Inicializa el diálogo."""
        super().__init__(parent)
        self.setWindowTitle("Configuración de Carpeta")
        self.setModal(True)
        self.custom_subfolders = []
        self.init_ui()
    
    def init_ui(self):
        """Inicializa la interfaz de usuario."""
        layout = QVBoxLayout()
        
        # Pregunta sobre crear carpeta
        question_label = QLabel("¿Desea crear una carpeta para este presupuesto?")
        layout.addWidget(question_label)
        
        # Checkboxes para subcarpetas predeterminadas
        subfolders_group = QGroupBox("Subcarpetas predeterminadas")
        subfolders_layout = QVBoxLayout()
        
        self.subfolder_checkboxes = {}
        for subfolder in self.DEFAULT_SUBFOLDERS:
            checkbox = QCheckBox(subfolder.capitalize())
            self.subfolder_checkboxes[subfolder] = checkbox
            subfolders_layout.addWidget(checkbox)
        
        subfolders_group.setLayout(subfolders_layout)
        layout.addWidget(subfolders_group)
        
        # Campo para subcarpetas personalizadas
        custom_label = QLabel("Subcarpetas personalizadas (separadas por comas):")
        layout.addWidget(custom_label)
        
        self.custom_subfolders_field = QLineEdit()
        self.custom_subfolders_field.setPlaceholderText("Ej: facturas, contratos")
        layout.addWidget(self.custom_subfolders_field)
        
        # Botones
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.ok_button = QPushButton("Aceptar")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def get_selected_subfolders(self):
        """
        Obtiene la lista de subcarpetas seleccionadas.
        
        Returns:
            list: Lista de nombres de subcarpetas
        """
        subfolders = []
        
        # Subcarpetas predeterminadas seleccionadas
        for name, checkbox in self.subfolder_checkboxes.items():
            if checkbox.isChecked():
                subfolders.append(name)
        
        # Subcarpetas personalizadas
        custom_text = self.custom_subfolders_field.text().strip()
        if custom_text:
            custom_list = [s.strip() for s in custom_text.split(',') if s.strip()]
            subfolders.extend(custom_list)
        
        return subfolders
    
    def add_custom_subfolder(self, subfolder_name):
        """
        Añade una subcarpeta personalizada.
        
        Args:
            subfolder_name: Nombre de la subcarpeta
        """
        if subfolder_name and subfolder_name not in self.custom_subfolders:
            self.custom_subfolders.append(subfolder_name)
            current_text = self.custom_subfolders_field.text()
            if current_text:
                self.custom_subfolders_field.setText(f"{current_text}, {subfolder_name}")
            else:
                self.custom_subfolders_field.setText(subfolder_name)
