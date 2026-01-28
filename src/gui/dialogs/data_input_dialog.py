"""
Diálogo para entrada de datos del presupuesto.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFormLayout
)
from PyQt6.QtCore import Qt
from src.core.validators import DataValidator


class DataInputDialog(QDialog):
    """Diálogo para ingresar datos del presupuesto."""
    
    def __init__(self, parent=None):
        """Inicializa el diálogo."""
        super().__init__(parent)
        self.validator = DataValidator()
        self.setWindowTitle("Datos del Presupuesto")
        self.setModal(True)
        self.init_ui()
    
    def init_ui(self):
        """Inicializa la interfaz de usuario."""
        layout = QVBoxLayout()
        
        form_layout = QFormLayout()
        
        # Campo de dirección
        self.direccion_field = QLineEdit()
        self.direccion_field.setPlaceholderText("Ej: Calle Mayor")
        form_layout.addRow("Dirección:", self.direccion_field)
        
        # Campo de número
        self.numero_field = QLineEdit()
        self.numero_field.setPlaceholderText("Ej: 12")
        form_layout.addRow("Número:", self.numero_field)
        
        # Campo de código postal
        self.codigo_postal_field = QLineEdit()
        self.codigo_postal_field.setPlaceholderText("Ej: 28001")
        form_layout.addRow("Código Postal:", self.codigo_postal_field)
        
        # Campo de descripción
        self.descripcion_field = QLineEdit()
        self.descripcion_field.setPlaceholderText("Ej: Reforma Baño")
        form_layout.addRow("Descripción:", self.descripcion_field)
        
        layout.addLayout(form_layout)
        
        # Botones
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.create_button = QPushButton("Crear")
        self.create_button.clicked.connect(self.accept)
        button_layout.addWidget(self.create_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def get_data(self):
        """
        Obtiene los datos ingresados validados.
        
        Returns:
            dict: Diccionario con los datos o None si hay error
        """
        direccion = self.direccion_field.text().strip()
        numero = self.numero_field.text().strip()
        codigo_postal = self.codigo_postal_field.text().strip()
        descripcion = self.descripcion_field.text().strip()
        
        data = {
            'direccion': direccion,
            'numero': numero,
            'codigo_postal': codigo_postal,
            'descripcion': descripcion
        }
        
        # Validar datos
        is_valid, errors = self.validator.validate_all(data)
        
        if not is_valid:
            QMessageBox.warning(
                self,
                "Error de validación",
                "\n".join(errors)
            )
            return None
        
        return data
    
    def set_data(self, data):
        """
        Establece los datos en los campos.
        
        Args:
            data: Diccionario con los datos
        """
        self.direccion_field.setText(data.get('direccion', ''))
        self.numero_field.setText(data.get('numero', ''))
        self.codigo_postal_field.setText(data.get('codigo_postal', ''))
        self.descripcion_field.setText(data.get('descripcion', ''))
