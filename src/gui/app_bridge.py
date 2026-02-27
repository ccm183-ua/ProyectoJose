"""
Puente QWebChannel: expone métodos de la aplicación al frontend (HTML/JS).
El frontend llama a estos métodos y Python ejecuta la lógica existente.

IMPORTANTE: Las llamadas desde JavaScript pueden ejecutarse en el hilo de Chromium.
Todas las operaciones GUI deben ejecutarse en el hilo principal de Qt.
Usamos QTimer.singleShot(0, ...) para diferir al event loop principal.
"""

import json
import logging

from PySide6.QtCore import QObject, QTimer, Slot

log = logging.getLogger(__name__)


def _defer_to_main(callback):
    """Ejecuta callback en el hilo principal de Qt (evita crash por hilo incorrecto)."""
    QTimer.singleShot(0, callback)


class AppBridge(QObject):
    """
    Objeto publicado en QWebChannel como "app".
    El frontend accede vía: channel.objects.app
    """

    def __init__(self, web_main_frame, parent=None):
        super().__init__(parent)
        self._frame = web_main_frame

    @Slot(result=str)
    def ping(self) -> str:
        """Prueba de comunicación: el frontend llama y Python responde."""
        return json.dumps({"ok": True, "message": "QWebChannel funciona correctamente"})

    @Slot(result=str)
    def getVersion(self) -> str:
        """Devuelve la versión de la aplicación."""
        return json.dumps({"version": "1.0", "name": "cubiApp"})

    @Slot()
    def openDashboard(self):
        """Abre la ventana de presupuestos existentes (BudgetDashboardFrame)."""
        if self._frame:
            _defer_to_main(self._frame._open_dashboard)

    @Slot()
    def openDbManager(self):
        """Abre la ventana de gestión de base de datos (DBManagerFrame)."""
        if self._frame:
            _defer_to_main(self._frame._open_db_manager)

    @Slot(str)
    def openInNewWindow(self, view: str):
        """Abre una nueva ventana WebEngine con la vista indicada."""
        if self._frame:
            _defer_to_main(lambda: self._frame._open_in_new_window(view))

    @Slot()
    def createBudget(self):
        """Abre el flujo de crear presupuesto (usa diálogos Qt por ahora)."""
        if self._frame:
            _defer_to_main(self._frame._create_budget)

    @Slot()
    def openTemplateManager(self):
        """Abre el gestor de plantillas."""
        if self._frame:
            _defer_to_main(self._frame._open_template_manager)

    @Slot()
    def openDefaultPaths(self):
        """Abre la configuración de rutas por defecto."""
        if self._frame:
            _defer_to_main(self._frame._open_default_paths)

    @Slot()
    def openAiSettings(self):
        """Abre la configuración de API Key."""
        if self._frame:
            _defer_to_main(self._frame._open_ai_settings)

    @Slot()
    def showAbout(self):
        """Muestra el diálogo Acerca de."""
        if self._frame:
            _defer_to_main(self._frame._show_about)
