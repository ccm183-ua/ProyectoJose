"""
Diálogo para capturar el nombre del proyecto desde el portapapeles.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QMessageBox, QLineEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from src.core.project_parser import ProjectParser
from src.utils.project_name_generator import ProjectNameGenerator


class ProjectNameDialog(QDialog):
    """Diálogo para capturar y validar el nombre del proyecto desde el portapapeles."""
    
    def __init__(self, parent=None):
        """Inicializa el diálogo."""
        super().__init__(parent)
        self.parser = ProjectParser()
        self.name_generator = ProjectNameGenerator()
        self.project_data = None
        self.project_name = None
        
        self.setWindowTitle("Nombre del Proyecto")
        self.setModal(True)
        self.setMinimumWidth(600)
        # Asegurar contraste: texto oscuro en todo el diálogo (evita herencia de temas)
        self.setStyleSheet(
            "QDialog { background-color: #ffffff; } "
            "QLabel { color: #1a1a1a; } "
        )
        self.init_ui()
        
        # Intentar cargar automáticamente desde el portapapeles
        self.load_from_clipboard()
    
    def init_ui(self):
        """Inicializa la interfaz de usuario."""
        layout = QVBoxLayout()
        
        # Instrucciones
        instructions = QLabel(
            "Copia una fila completa (columnas A-I) desde tu Excel de presupuestos "
            "y pégalo en el campo de abajo, o haz clic en 'Cargar desde Portapapeles'."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; padding: 10px;")
        layout.addWidget(instructions)
        
        # Campo de texto para pegar datos
        self.data_text = QTextEdit()
        self.data_text.setPlaceholderText(
            "Pega aquí los datos del Excel (Ctrl+V)\n"
            "Formato esperado: Nº\tFECHA\tCLIENTE\tMEDIACIÓN\tCALLE\tNUM\tC.P\tLOCALIDAD\tTIPO"
        )
        self.data_text.setMaximumHeight(100)
        self.data_text.setStyleSheet(
            "QTextEdit { color: #1a1a1a; background-color: #ffffff; }"
        )
        layout.addWidget(QLabel("Datos del proyecto:"))
        layout.addWidget(self.data_text)
        
        # Botón para cargar desde portapapeles
        self.load_button = QPushButton("📋 Cargar desde Portapapeles")
        self.load_button.clicked.connect(self.load_from_clipboard)
        layout.addWidget(self.load_button)
        
        # Campo para mostrar el nombre del proyecto generado (texto oscuro sobre fondo claro)
        layout.addWidget(QLabel("Nombre del proyecto:"))
        self.name_field = QLineEdit()
        self.name_field.setReadOnly(True)
        self.name_field.setStyleSheet(
            "QLineEdit { color: #1a1a1a; background-color: #f0f0f0; padding: 8px; "
            "selection-color: #ffffff; selection-background-color: #2196f3; }"
        )
        layout.addWidget(self.name_field)
        
        # Botones
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        self.validate_button = QPushButton("Validar y Continuar")
        self.validate_button.clicked.connect(self.validate_and_accept)
        self.validate_button.setDefault(True)
        button_layout.addWidget(self.validate_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def load_from_clipboard(self):
        """Carga datos desde el portapapeles."""
        clipboard = QGuiApplication.clipboard()
        clipboard_text = clipboard.text()
        
        if clipboard_text:
            self.data_text.setPlainText(clipboard_text)
            self.validate_data()
        else:
            QMessageBox.information(
                self,
                "Portapapeles vacío",
                "No hay datos en el portapapeles. Por favor, copia una fila desde tu Excel."
            )
    
    def validate_data(self):
        """Valida los datos ingresados y genera el nombre del proyecto."""
        data_text = self.data_text.toPlainText().strip()
        
        if not data_text:
            self.name_field.clear()
            return
        
        # Parsear datos
        project_data, error = self.parser.parse_clipboard_data(data_text)
        
        if error:
            self.name_field.clear()
            self.name_field.setPlaceholderText(f"Error: {error}")
            return
        
        # Generar nombre del proyecto
        self.project_data = project_data
        self.project_name = self.name_generator.generate_project_name(project_data)
        self.name_field.setText(self.project_name)
    
    def validate_and_accept(self):
        """Valida los datos y acepta el diálogo si son válidos."""
        data_text = self.data_text.toPlainText().strip()
        
        if not data_text:
            QMessageBox.warning(
                self,
                "Datos vacíos",
                "Por favor, ingresa los datos del proyecto."
            )
            return
        
        # Parsear y validar
        project_data, error = self.parser.parse_clipboard_data(data_text)
        
        if error:
            QMessageBox.warning(
                self,
                "Error de validación",
                error
            )
            return
        
        # Generar nombre
        self.project_data = project_data
        self.project_name = self.name_generator.generate_project_name(project_data)
        
        # Aceptar diálogo
        self.accept()
    
    def get_project_data(self):
        """
        Obtiene los datos del proyecto parseados.
        
        Returns:
            dict: Datos del proyecto o None
        """
        return self.project_data
    
    def get_project_name(self):
        """
        Obtiene el nombre del proyecto generado.
        
        Returns:
            str: Nombre del proyecto o None
        """
        return self.project_name
