"""
Ventana principal de la aplicación.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QPushButton, QMessageBox,
    QFileDialog, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
import os

from src.gui.dialogs.create_budget_dialog import CreateBudgetDialog
from src.gui.dialogs.folder_config_dialog import FolderConfigDialog
from src.gui.dialogs.data_input_dialog import DataInputDialog
from src.gui.dialogs.project_name_dialog import ProjectNameDialog
from src.core.excel_manager import ExcelManager
from src.core.file_manager import FileManager
from src.core.template_manager import TemplateManager
from src.utils.helpers import sanitize_filename


class MainWindow(QMainWindow):
    """Ventana principal de la aplicación."""
    
    def __init__(self):
        """Inicializa la ventana principal."""
        super().__init__()
        self.excel_manager = ExcelManager()
        self.file_manager = FileManager()
        self.template_manager = TemplateManager()
        self.init_ui()
    
    def init_ui(self):
        """Inicializa la interfaz de usuario."""
        self.setWindowTitle("Gestión de Presupuestos")
        self.setGeometry(100, 100, 400, 300)
        
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Título
        title_label = QLabel("GESTIÓN DE PRESUPUESTOS")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 20px;")
        layout.addWidget(title_label)
        
        # Botón: Abrir Presupuesto Existente
        open_button = QPushButton("📁 Abrir Presupuesto Existente")
        open_button.clicked.connect(self.open_excel_file)
        layout.addWidget(open_button)
        
        # Botón: Crear Nuevo Presupuesto
        create_button = QPushButton("➕ Crear Nuevo Presupuesto")
        create_button.clicked.connect(self.create_new_budget)
        layout.addWidget(create_button)
        
        # Botón: Navegar Carpetas
        navigate_button = QPushButton("📂 Navegar Carpetas")
        navigate_button.clicked.connect(self.navigate_folders)
        layout.addWidget(navigate_button)
        
        # Espaciador
        layout.addStretch()
    
    def open_excel_file(self):
        """
        Abre un diálogo para seleccionar y abrir un archivo Excel existente.
        
        Returns:
            str: Ruta del archivo seleccionado o None si se cancela
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir Presupuesto",
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )
        
        if file_path:
            try:
                # Cargar el presupuesto
                budget = self.excel_manager.load_budget(file_path)
                if budget:
                    self.show_success(f"Presupuesto abierto: {os.path.basename(file_path)}")
                    return file_path
                else:
                    self.show_error("No se pudo abrir el archivo Excel.")
            except Exception as e:
                self.show_error(f"Error al abrir el archivo: {str(e)}")
        
        return None if not file_path else file_path
    
    def create_new_budget(self):
        """Crea un nuevo presupuesto siguiendo el flujo completo."""
        # Paso 1: Obtener nombre del proyecto desde el portapapeles
        project_dialog = ProjectNameDialog(self)
        if project_dialog.exec() != ProjectNameDialog.DialogCode.Accepted:
            return  # Usuario canceló
        
        project_data = project_dialog.get_project_data()
        project_name = project_dialog.get_project_name()
        
        if not project_data or not project_name:
            self.show_error("No se pudo obtener los datos del proyecto.")
            return
        
        # Paso 2: Seleccionar ubicación de guardado
        save_path = self.get_save_path()
        if not save_path:
            return  # Usuario canceló
        
        # Paso 3: Preguntar si crear carpeta
        folder_config_dialog = FolderConfigDialog(self)
        create_folder = folder_config_dialog.exec() == FolderConfigDialog.DialogCode.Accepted
        
        folder_path = None
        if create_folder:
            # Obtener subcarpetas seleccionadas
            subfolders = folder_config_dialog.get_selected_subfolders()
            
            # Generar nombre de carpeta y archivo desde el nombre del proyecto
            folder_name = sanitize_filename(project_name)
            
            # Crear carpeta en el directorio padre del archivo seleccionado
            save_dir = os.path.dirname(save_path)
            folder_path = os.path.join(save_dir, folder_name)
            
            # Crear carpeta principal
            if not self.file_manager.create_folder(folder_path):
                self.show_error("No se pudo crear la carpeta.")
                return
            
            # Crear subcarpetas
            if subfolders:
                self.file_manager.create_subfolders(folder_path, subfolders)
            
            # Actualizar ruta del archivo para guardarlo en la carpeta
            save_path = os.path.join(folder_path, f"{folder_name}.xlsx")
        else:
            # No crear carpeta, usar el nombre del proyecto para el archivo
            save_dir = os.path.dirname(save_path)
            file_name = sanitize_filename(project_name)
            save_path = os.path.join(save_dir, f"{file_name}.xlsx")
        
        # Paso 4: Crear archivo Excel desde plantilla
        template_path = self.template_manager.get_template_path()
        
        if not os.path.exists(template_path):
            self.show_error("No se encontró la plantilla.")
            return
        
        # Preparar datos para el Excel (usar todos los datos del proyecto)
        excel_data = {
            # Campos originales (para compatibilidad)
            'nombre_obra': project_name,
            'direccion': project_data.get('calle', ''),
            'numero': project_data.get('num_calle', ''),
            'codigo_postal': project_data.get('codigo_postal', ''),
            'descripcion': project_data.get('tipo', ''),
            # Nuevos campos del proyecto
            'numero_proyecto': project_data.get('numero', ''),
            'fecha': project_data.get('fecha', ''),
            'cliente': project_data.get('cliente', ''),
            'mediacion': project_data.get('mediacion', ''),
            'calle': project_data.get('calle', ''),
            'num_calle': project_data.get('num_calle', ''),
            'localidad': project_data.get('localidad', ''),
            'tipo': project_data.get('tipo', '')
        }
        
        if self.excel_manager.create_from_template(template_path, save_path, excel_data):
            self.show_success(f"Presupuesto creado exitosamente:\n{save_path}")
        else:
            self.show_error("Error al crear el presupuesto.")
    
    def get_save_path(self):
        """
        Muestra un diálogo para seleccionar dónde guardar el archivo.
        
        Returns:
            str: Ruta donde guardar el archivo o None si se cancela
        """
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Presupuesto",
            "",
            "Excel Files (*.xlsx);;All Files (*)"
        )
        
        return file_path if file_path else None
    
    def select_folder(self):
        """
        Muestra un diálogo para seleccionar una carpeta.
        
        Returns:
            str: Ruta de la carpeta seleccionada o None si se cancela
        """
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar Carpeta"
        )
        
        return folder_path if folder_path else None
    
    def navigate_folders(self):
        """Abre el diálogo de navegación de carpetas."""
        folder_path = self.select_folder()
        if folder_path:
            self.show_info(f"Carpeta seleccionada: {folder_path}")
    
    def show_error(self, message):
        """Muestra un mensaje de error."""
        QMessageBox.critical(self, "Error", message)
    
    def show_success(self, message):
        """Muestra un mensaje de éxito."""
        QMessageBox.information(self, "Éxito", message)
    
    def show_info(self, message):
        """Muestra un mensaje informativo."""
        QMessageBox.information(self, "Información", message)
