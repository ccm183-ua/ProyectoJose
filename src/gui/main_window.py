"""
Ventana principal de la aplicación.
Estilo app nativa: barra de menú y botones simples.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QPushButton, QMessageBox,
    QFileDialog, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
import os

from src.gui.dialogs.folder_config_dialog import FolderConfigDialog
from src.gui.dialogs.project_name_dialog import ProjectNameDialog
from src.core.database import open_db_folder, get_db_path_as_string
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
        self.setWindowTitle("cubiApp")
        self.setGeometry(100, 100, 400, 280)

        self._create_menu_bar()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 24)

        title_label = QLabel("cubiApp")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        open_btn = QPushButton("Abrir presupuesto existente")
        open_btn.setMinimumHeight(40)
        open_btn.clicked.connect(self.open_excel_file)
        layout.addWidget(open_btn)

        create_btn = QPushButton("Crear nuevo presupuesto")
        create_btn.setMinimumHeight(40)
        create_btn.clicked.connect(self.create_new_budget)
        layout.addWidget(create_btn)

        db_btn = QPushButton("Abrir carpeta de la base de datos")
        db_btn.setMinimumHeight(40)
        db_btn.clicked.connect(self._open_db_folder)
        layout.addWidget(db_btn)

        layout.addStretch()

    def _create_menu_bar(self):
        """Crea la barra de menú (Archivo, Ayuda)."""
        menubar = self.menuBar()

        # Menú Archivo
        file_menu = menubar.addMenu("&Archivo")

        act_open = QAction("&Abrir presupuesto...", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self.open_excel_file)
        file_menu.addAction(act_open)

        act_new = QAction("&Crear nuevo presupuesto...", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self.create_new_budget)
        file_menu.addAction(act_new)

        file_menu.addSeparator()

        act_open_db_folder = QAction("Abrir carpeta de la base de datos...", self)
        act_open_db_folder.triggered.connect(self._open_db_folder)
        file_menu.addAction(act_open_db_folder)

        file_menu.addSeparator()

        act_quit = QAction("&Salir", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        # Menú Base de datos (misma acción, por si prefieren buscarla aquí)
        db_menu = menubar.addMenu("Base de datos")
        act_open_db_folder2 = QAction("Abrir carpeta de la base de datos...", self)
        act_open_db_folder2.triggered.connect(self._open_db_folder)
        db_menu.addAction(act_open_db_folder2)

        # Menú Ayuda
        help_menu = menubar.addMenu("&Ayuda")

        act_about = QAction("&Acerca de...", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _show_about(self):
        """Muestra el diálogo Acerca de."""
        QMessageBox.about(
            self,
            "Acerca de",
            "cubiApp\n\n"
            "Abre o crea presupuestos desde plantilla Excel."
        )

    def _open_db_folder(self):
        """Abre la carpeta donde está la base de datos para editarla con un editor externo."""
        if open_db_folder():
            path = get_db_path_as_string()
            self.show_info(
                "Se ha abierto la carpeta de la base de datos.\n\n"
                f"Fichero: {path}\n\n"
                "Puedes abrirlo con un editor SQLite (p. ej. DB Browser for SQLite, DBeaver) "
                "para ver y editar los datos. Cierra la app si quieres evitar conflictos al guardar."
            )
        else:
            self.show_error("No se pudo abrir la carpeta de la base de datos.")

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
        project_dialog = ProjectNameDialog(self)
        if project_dialog.exec() != ProjectNameDialog.DialogCode.Accepted:
            return

        project_data = project_dialog.get_project_data()
        project_name = project_dialog.get_project_name()

        if not project_data or not project_name:
            self.show_error("No se pudo obtener los datos del proyecto.")
            return

        save_path = self.get_save_path()
        if not save_path:
            return

        folder_config_dialog = FolderConfigDialog(self)
        create_folder = folder_config_dialog.exec() == FolderConfigDialog.DialogCode.Accepted

        if create_folder:
            subfolders = folder_config_dialog.get_selected_subfolders()
            folder_name = sanitize_filename(project_name)
            save_dir = os.path.dirname(save_path)
            folder_path = os.path.join(save_dir, folder_name)

            if not self.file_manager.create_folder(folder_path):
                self.show_error("No se pudo crear la carpeta.")
                return

            if subfolders:
                self.file_manager.create_subfolders(folder_path, subfolders)

            save_path = os.path.join(folder_path, f"{folder_name}.xlsx")
        else:
            save_dir = os.path.dirname(save_path)
            file_name = sanitize_filename(project_name)
            save_path = os.path.join(save_dir, f"{file_name}.xlsx")

        template_path = self.template_manager.get_template_path()

        if not os.path.exists(template_path):
            self.show_error("No se encontró la plantilla.")
            return

        excel_data = {
            'nombre_obra': project_name,
            'direccion': project_data.get('calle', ''),
            'numero': project_data.get('num_calle', ''),
            'codigo_postal': project_data.get('codigo_postal', ''),
            'descripcion': project_data.get('tipo', ''),
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

    def show_error(self, message):
        """Muestra un mensaje de error."""
        QMessageBox.critical(self, "Error", message)

    def show_success(self, message):
        """Muestra un mensaje de éxito."""
        QMessageBox.information(self, "Éxito", message)

    def show_info(self, message):
        """Muestra un mensaje informativo."""
        QMessageBox.information(self, "Información", message)
