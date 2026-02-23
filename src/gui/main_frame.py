"""
Ventana principal de cubiApp (PySide6).
"""

import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QInputDialog, QMainWindow, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from src.core import database as db_module
from src.core.services import BudgetService, DatabaseService
from src.gui import theme


class MainFrame(QMainWindow):
    def __init__(self, parent=None, title="cubiApp", **kwargs):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 520)
        self._budget_svc = BudgetService()
        self._db_svc = DatabaseService()
        self._db_frame = None
        self._dashboard_frame = None
        self._build_ui()
        self._center()

    def _center(self):
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === HEADER ===
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 60, 0, 0)
        header_layout.setSpacing(8)

        title = theme.create_title(header, "cubiApp", "display")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        header_layout.addWidget(title)

        subtitle = theme.create_subtitle(header, "Gestión de presupuestos")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        header_layout.addWidget(subtitle)

        main_layout.addWidget(header)
        main_layout.addSpacing(50)

        # === BOTONES ===
        btn_container = QWidget()
        btn_layout = QVBoxLayout(btn_container)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        btn_layout.setSpacing(theme.SPACE_MD)

        btn_create = QPushButton("+ Crear nuevo presupuesto")
        btn_create.setFixedSize(320, 50)
        btn_create.setFont(theme.get_font_medium(12))
        btn_create.setProperty("class", "primary")
        btn_create.clicked.connect(self._create_budget)
        btn_layout.addWidget(btn_create, alignment=Qt.AlignmentFlag.AlignHCenter)

        btn_open = QPushButton("Presupuestos existentes")
        btn_open.setFixedSize(320, 46)
        btn_open.setFont(theme.font_base())
        btn_open.clicked.connect(self._open_dashboard)
        btn_layout.addWidget(btn_open, alignment=Qt.AlignmentFlag.AlignHCenter)

        btn_db = QPushButton("Gestionar base de datos")
        btn_db.setFixedSize(320, 46)
        btn_db.setFont(theme.font_base())
        btn_db.clicked.connect(self._open_db_manager)
        btn_layout.addWidget(btn_db, alignment=Qt.AlignmentFlag.AlignHCenter)

        main_layout.addWidget(btn_container, 1)

        # === FOOTER ===
        footer = theme.create_caption(central, "versión 1.0")
        footer.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        main_layout.addWidget(footer)
        main_layout.addSpacing(theme.SPACE_XL)

        self.setCentralWidget(central)
        self._create_menu()

    def _create_menu(self):
        menubar = self.menuBar()

        m_archivo = menubar.addMenu("&Archivo")
        act_open = m_archivo.addAction("Abrir presupuesto...\tCtrl+O")
        act_open.triggered.connect(self._open_excel)
        act_new = m_archivo.addAction("Crear nuevo presupuesto...\tCtrl+N")
        act_new.triggered.connect(self._create_budget)
        m_archivo.addSeparator()
        act_exit = m_archivo.addAction("Salir\tCtrl+Q")
        act_exit.triggered.connect(self.close)

        m_bd = menubar.addMenu("Base de &datos")
        act_db = m_bd.addAction("Gestionar base de datos...")
        act_db.triggered.connect(self._open_db_manager)
        act_folder = m_bd.addAction("Abrir carpeta de la base de datos")
        act_folder.triggered.connect(self._open_db_folder)

        m_config = menubar.addMenu("&Configuración")
        act_ai = m_config.addAction("Configuración IA (API Key)...")
        act_ai.triggered.connect(self._open_ai_settings)
        act_templates = m_config.addAction("Gestionar plantillas...")
        act_templates.triggered.connect(self._open_template_manager)
        act_paths = m_config.addAction("Rutas por defecto...")
        act_paths.triggered.connect(self._open_default_paths)

        m_ayuda = menubar.addMenu("&Ayuda")
        act_about = m_ayuda.addAction("Acerca de...")
        act_about.triggered.connect(
            lambda: QMessageBox.information(
                self, "Acerca de",
                "cubiApp\n\nAbre o crea presupuestos desde plantilla Excel.",
            )
        )

    def _open_db_manager(self):
        try:
            from src.gui.db_manager import DBManagerFrame
            if self._db_frame is not None:
                try:
                    if self._db_frame.isVisible():
                        self._db_frame.raise_()
                        self._db_frame.activateWindow()
                        return
                except RuntimeError:
                    self._db_frame = None

            self._db_frame = DBManagerFrame(self)
            self._db_frame.destroyed.connect(lambda: setattr(self, '_db_frame', None))
            self._db_frame.show()
            self._db_frame.raise_()
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Error al abrir la base de datos: {ex}")

    def _open_dashboard(self, refresh=False):
        try:
            from src.gui.budget_dashboard import BudgetDashboardFrame
            if self._dashboard_frame is not None:
                try:
                    if self._dashboard_frame.isVisible():
                        if refresh:
                            self._dashboard_frame._load_data()
                        self._dashboard_frame.raise_()
                        self._dashboard_frame.activateWindow()
                        return
                except RuntimeError:
                    self._dashboard_frame = None

            self._dashboard_frame = BudgetDashboardFrame(self)
            self._dashboard_frame.destroyed.connect(lambda: setattr(self, '_dashboard_frame', None))
            self._dashboard_frame.show()
            self._dashboard_frame.raise_()
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Error al abrir el dashboard: {ex}")

    def _open_db_folder(self):
        try:
            path = db_module.get_db_path()
            db_module.ensure_db_directory(path)
            conn = db_module.connect()
            try:
                pass
            finally:
                conn.close()
            folder = str(path.parent)
            if sys.platform == "darwin":
                subprocess.run(["open", folder], check=True)
            elif sys.platform == "win32":
                subprocess.run(["explorer", folder], check=True)
            else:
                subprocess.run(["xdg-open", folder], check=True)
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Error: {ex}")

    def _open_excel(self):
        from src.core.settings import Settings
        default_dir = Settings().get_default_path(Settings.PATH_OPEN_BUDGETS) or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Presupuesto", default_dir,
            "Excel (*.xlsx *.xls);;Todos (*.*)",
        )
        if not path:
            return
        try:
            if self._budget_svc.open_budget(path):
                QMessageBox.information(self, "Éxito", f"Presupuesto abierto: {os.path.basename(path)}")
            else:
                QMessageBox.critical(self, "Error", "No se pudo abrir el archivo Excel.")
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Error: {ex}")

    def _create_budget(self):
        project_data, project_name = self._obtain_project_data()
        if not project_data or not project_name:
            return

        from src.core.settings import Settings
        from src.utils.helpers import sanitize_filename
        save_default_dir = Settings().get_default_path(Settings.PATH_SAVE_BUDGETS) or ""
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Presupuesto",
            os.path.join(save_default_dir, f"{sanitize_filename(project_name)}.xlsx"),
            "Excel (*.xlsx);;Todos (*.*)",
        )
        if not save_path:
            return

        template_path = self._budget_svc.get_template_path()
        save_dir = os.path.dirname(save_path)

        partes_dir = [
            p for p in [
                project_data.get("calle", ""),
                project_data.get("num_calle", ""),
                project_data.get("codigo_postal", ""),
                project_data.get("localidad", ""),
            ] if p
        ]
        direccion_proyecto = ", ".join(partes_dir)

        comunidad_data = self._buscar_comunidad_para_presupuesto(
            project_data.get("cliente", ""), direccion=direccion_proyecto,
        )
        admin_data = self._db_svc.get_admin_para_comunidad(comunidad_data)

        result = self._budget_svc.create_budget(
            project_data, project_name, save_dir, template_path,
            comunidad_data=comunidad_data, admin_data=admin_data,
        )
        if not result.success:
            QMessageBox.critical(self, "Error", result.error)
            return

        self._offer_ai_partidas(result.excel_path, project_data)
        self._open_dashboard(refresh=True)

    def _obtain_project_data(self):
        from src.gui.dialogs import obtain_project_data
        return obtain_project_data(self)

    def _open_default_paths(self):
        from src.gui.dialogs import DefaultPathsDialog
        dlg = DefaultPathsDialog(self)
        dlg.exec()

    def _buscar_comunidad_para_presupuesto(self, nombre_cliente: str, direccion: str = "") -> dict | None:
        from src.gui.dialogs import (
            ComunidadConfirmDialog, ComunidadFuzzySelectDialog,
            crear_comunidad_con_formulario,
        )

        exacta, fuzzy = self._db_svc.buscar_comunidad(nombre_cliente)

        if exacta:
            dlg = ComunidadConfirmDialog(self, exacta, nombre_cliente.strip())
            if dlg.exec() == QMessageBox.DialogCode.Accepted.value:
                return dlg.get_comunidad_data()
            return None

        if fuzzy:
            dlg = ComunidadFuzzySelectDialog(
                self, fuzzy, nombre_cliente.strip(), direccion_prefill=direccion,
            )
            if dlg.exec() == QMessageBox.DialogCode.Accepted.value:
                return dlg.get_comunidad_data()
            return None

        if not nombre_cliente or not nombre_cliente.strip():
            return None

        resp = QMessageBox.question(
            self,
            "Comunidad no encontrada",
            f'No se encontró ninguna comunidad con el nombre "{nombre_cliente.strip()}".\n\n'
            "¿Desea añadir una nueva comunidad a la base de datos?",
        )
        if resp == QMessageBox.StandardButton.Yes:
            return crear_comunidad_con_formulario(
                self, nombre_prefill=nombre_cliente.strip(), direccion_prefill=direccion,
            )

        return None

    def _offer_ai_partidas(self, excel_path, project_data):
        from src.gui.ai_budget_dialog import AIBudgetDialog
        from src.gui.partidas_dialog import SuggestedPartidasDialog

        ai_dlg = AIBudgetDialog(self, datos_proyecto=project_data)
        if ai_dlg.exec() != 1:
            QMessageBox.information(
                self, "Éxito",
                f"Presupuesto creado (sin partidas IA):\n{excel_path}",
            )
            return

        result = ai_dlg.get_result()

        if not result or not result.get('partidas'):
            QMessageBox.information(
                self, "Éxito",
                f"Presupuesto creado (sin partidas IA):\n{excel_path}",
            )
            return

        partidas_dlg = SuggestedPartidasDialog(self, result)
        if partidas_dlg.exec() != 1:
            QMessageBox.information(
                self, "Éxito",
                f"Presupuesto creado (sin partidas IA):\n{excel_path}",
            )
            return

        selected = partidas_dlg.get_selected_partidas()

        if selected:
            if self._budget_svc.insert_partidas(excel_path, selected, project_data):
                QMessageBox.information(
                    self, "Éxito",
                    f"Presupuesto creado con {len(selected)} partidas:\n{excel_path}",
                )
            else:
                QMessageBox.warning(
                    self, "Aviso",
                    f"Presupuesto creado pero hubo un error al insertar las partidas.\n{excel_path}",
                )
        else:
            QMessageBox.information(
                self, "Éxito",
                f"Presupuesto creado (sin partidas):\n{excel_path}",
            )

    def _open_template_manager(self):
        from src.gui.template_manager_dialog import TemplateManagerDialog
        dlg = TemplateManagerDialog(self)
        dlg.exec()

    def _open_ai_settings(self):
        from src.core.settings import Settings
        settings = Settings()
        current_key = settings.get_api_key() or ""

        new_key, ok = QInputDialog.getText(
            self,
            "Configuración IA - API Key",
            "Introduce tu API key de Google Gemini.\n"
            "Puedes obtenerla gratis en: https://aistudio.google.com/apikey\n\n"
            "La clave se guardará de forma local y segura.",
            text=current_key,
        )
        if not ok:
            return
        new_key = new_key.strip()
        if new_key and (len(new_key) < 10 or not new_key.startswith("AI")):
            confirm = QMessageBox.warning(
                self,
                "Formato sospechoso",
                "La clave introducida no parece tener el formato esperado "
                "(las claves de Gemini suelen empezar por 'AI' y tener ~39 caracteres).\n\n"
                "¿Guardar de todas formas?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
        settings.save_api_key(new_key)
        if new_key:
            QMessageBox.information(self, "Configuración IA", "API key guardada correctamente.")
        else:
            QMessageBox.information(self, "Configuración IA", "API key eliminada.")
