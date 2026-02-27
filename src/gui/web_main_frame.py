"""
Ventana principal de cubiApp con Qt WebEngine.
Muestra la UI web (Metronic) y delega acciones al bridge.
"""

import json
import logging
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtWidgets import QMainWindow, QMessageBox
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings

log = logging.getLogger(__name__)
WEB_UI_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "ui"


class _SimpleBridge(QObject):
    """Bridge mínimo (como demo) para evitar crash al cargar."""
    @Slot(result=str)
    def ping(self) -> str:
        return json.dumps({"ok": True, "message": "QWebChannel funciona"})


class WebMainFrame(QMainWindow):
    """Ventana principal con UI web. Sustituye a MainFrame en modo WebEngine."""

    def __init__(self, parent=None, title="cubiApp"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1200, 800)
        self._db_frame = None
        self._dashboard_frame = None

        self._view = QWebEngineView()
        self._view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False
        )

        bridge = _SimpleBridge()
        channel = QWebChannel(self._view.page())
        channel.registerObject("app", bridge)
        self._view.page().setWebChannel(channel)

        index_path = WEB_UI_DIR / "index.html"
        if index_path.exists():
            self._view.setUrl(QUrl.fromLocalFile(str(index_path)))
        else:
            log.error("No existe web/ui/index.html")
            self._view.setHtml("<h1>Error: web/ui/index.html no encontrado</h1>")

        self.setCentralWidget(self._view)
        self._center()

    def _center(self):
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
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

            self._db_frame = DBManagerFrame(parent=None)
            self._db_frame.destroyed.connect(lambda: setattr(self, '_db_frame', None))
            self._db_frame.show()
            self._db_frame.raise_()
        except Exception as ex:
            log.exception("Error al abrir la base de datos")
            QMessageBox.critical(None, "Error", f"Error al abrir la base de datos: {ex}")

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

            self._dashboard_frame = BudgetDashboardFrame(parent=None)
            self._dashboard_frame.destroyed.connect(lambda: setattr(self, '_dashboard_frame', None))
            self._dashboard_frame.show()
            self._dashboard_frame.raise_()
        except Exception as ex:
            log.exception("Error al abrir el dashboard")
            QMessageBox.critical(None, "Error", f"Error al abrir el dashboard: {ex}")

    def _open_in_new_window(self, view: str):
        """Crea una nueva ventana WebMainFrame."""
        win = WebMainFrame(parent=None, title=f"cubiApp - {view}")
        win.show()
        win.raise_()
        win.activateWindow()

    def _create_budget(self):
        """Abre el flujo de crear presupuesto. Reutiliza MainFrame para los diálogos Qt."""
        try:
            from src.gui.main_frame import MainFrame
            # parent=None evita conflictos con QWebEngineView como padre
            helper = MainFrame(parent=None, title="")
            helper.hide()
            helper._create_budget()
        except Exception as ex:
            log.exception("Error al crear presupuesto")
            QMessageBox.critical(None, "Error", f"Error al crear presupuesto: {ex}")

    def _open_template_manager(self):
        try:
            from src.gui.template_manager_dialog import TemplateManagerDialog
            dlg = TemplateManagerDialog(parent=None)
            dlg.exec()
        except Exception as ex:
            log.exception("Error al abrir gestor de plantillas")
            QMessageBox.critical(None, "Error", f"Error: {ex}")

    def _open_default_paths(self):
        try:
            from src.gui.dialogs import DefaultPathsDialog
            dlg = DefaultPathsDialog(parent=None)
            dlg.exec()
        except Exception as ex:
            log.exception("Error al abrir rutas por defecto")
            QMessageBox.critical(None, "Error", f"Error: {ex}")

    def _open_ai_settings(self):
        try:
            from src.core.settings import Settings
            from PySide6.QtWidgets import QInputDialog
            settings = Settings()
            current_key = settings.get_api_key() or ""
            new_key, ok = QInputDialog.getText(
                None, "Configuración IA - API Key",
                "Introduce tu API key de Google Gemini.\n"
                "Puedes obtenerla gratis en: https://aistudio.google.com/apikey\n\n"
                "La clave se guardará de forma local y segura.",
                text=current_key,
            )
            if ok:
                settings.save_api_key(new_key.strip())
                QMessageBox.information(None, "Configuración IA",
                    "API key guardada correctamente." if new_key.strip() else "API key eliminada.")
        except Exception as ex:
            log.exception("Error al abrir configuración IA")
            QMessageBox.critical(None, "Error", f"Error: {ex}")

    def _show_about(self):
        QMessageBox.information(
            None, "Acerca de",
            "cubiApp\n\nGestión de presupuestos. Versión con UI web (Qt WebEngine).",
        )
