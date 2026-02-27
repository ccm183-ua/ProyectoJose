#!/usr/bin/env python3
"""
cubiApp con Qt WebEngine - UI web con Metronic.
Ejecutar: python demo_webengine.py  o  run_webengine.bat
"""

import json
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Slot
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings

APP_BASE = Path(__file__).resolve().parent
WEB_UI_DIR = APP_BASE / "web" / "ui"


def _defer(callback):
    """Ejecuta en el hilo principal de Qt."""
    QTimer.singleShot(0, callback)


class AppBridge(QObject):
    """Puente QWebChannel: frontend llama a Python."""

    def __init__(self, window):
        super().__init__()
        self._window = window

    @Slot(result=str)
    def ping(self) -> str:
        return json.dumps({"ok": True, "message": "QWebChannel funciona correctamente"})

    @Slot()
    def openDashboard(self):
        _defer(self._window._open_dashboard)

    @Slot()
    def openDbManager(self):
        _defer(self._window._open_db_manager)

    @Slot()
    def createBudget(self):
        _defer(self._window._create_budget)

    @Slot()
    def openTemplateManager(self):
        _defer(self._window._open_template_manager)

    @Slot()
    def openDefaultPaths(self):
        _defer(self._window._open_default_paths)

    @Slot(result=str)
    def getDefaultPaths(self) -> str:
        """Devuelve JSON con las rutas configuradas."""
        from src.core.settings import Settings
        s = Settings()
        paths = s.get_all_default_paths()
        return json.dumps(paths)

    @Slot(str, result=str)
    def saveDefaultPaths(self, json_str: str) -> str:
        """Guarda las rutas. Devuelve {ok:true} o {ok:false, error:...}."""
        try:
            from src.core.settings import Settings
            import os
            data = json.loads(json_str)
            s = Settings()
            for key in (Settings.PATH_SAVE_BUDGETS, Settings.PATH_OPEN_BUDGETS, Settings.PATH_RELATION_FILE):
                val = data.get(key, "")
                s.set_default_path(key, (val or "").strip())
            return json.dumps({"ok": True})
        except Exception as ex:
            return json.dumps({"ok": False, "error": str(ex)})

    @Slot(str, result=str)
    def selectDirectory(self, current_path: str) -> str:
        """Abre diálogo para seleccionar carpeta. Devuelve ruta o vacío."""
        from PySide6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(None, "Selecciona una carpeta", current_path or "")
        return path or ""

    @Slot(str, str, result=str)
    def selectFile(self, current_dir: str, filter_str: str) -> str:
        """Abre diálogo para seleccionar archivo. Devuelve ruta o vacío."""
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            None, "Selecciona archivo", current_dir or "",
            "Archivos Excel (*.xlsx);;Todos (*.*)"
        )
        return path or ""

    @Slot()
    def openAiSettings(self):
        _defer(self._window._open_ai_settings)

    @Slot()
    def showAbout(self):
        _defer(self._window._show_about)

    @Slot(result=str)
    def getApiKey(self) -> str:
        """Devuelve la API key actual (o vacío)."""
        from src.core.settings import Settings
        key = Settings().get_api_key() or ""
        return key

    @Slot(str, result=str)
    def saveApiKey(self, key: str) -> str:
        """Guarda la API key. Devuelve {ok:true} o {ok:false, error:...}."""
        try:
            from src.core.settings import Settings
            Settings().save_api_key(key.strip())
            return json.dumps({"ok": True})
        except Exception as ex:
            return json.dumps({"ok": False, "error": str(ex)})

    @Slot(result=str)
    def getBudgets(self) -> str:
        """Devuelve JSON con presupuestos por estado: {root_path, states: {estado: [proyectos]}, error?}."""
        try:
            import os
            from src.core import folder_scanner
            from src.core.project_data_resolver import build_relation_index, resolve_projects_all_states
            from src.core.settings import Settings

            root_path = Settings().get_default_path(Settings.PATH_OPEN_BUDGETS) or ""
            if not root_path or not os.path.isdir(root_path):
                return json.dumps({"root_path": "", "states": {}, "error": "Ruta no configurada o no existe"})

            rel_index = build_relation_index()
            state_names = folder_scanner.scan_root(root_path)
            if not state_names:
                return json.dumps({"root_path": root_path, "states": {}, "error": "No se encontraron carpetas de estado"})

            tab_order = [
                "PTE. PRESUPUESTAR", "PRESUPUESTADO", "EJECUTAR", "EJECUTANDO",
                "TERMINADO", "ANULADOS", "MODELO INFORME", "MODELOS DE PRESUPUESTOS",
            ]
            order_map = {n.upper(): i for i, n in enumerate(tab_order)}
            state_names = sorted(state_names, key=lambda s: order_map.get(s.upper(), 999))

            states_scanned = {}
            for name in state_names:
                state_dir = os.path.join(root_path, name)
                scanned = folder_scanner.scan_projects(state_dir)
                states_scanned[name] = scanned

            states_resolved = resolve_projects_all_states(states_scanned, rel_index)

            out = {"root_path": root_path, "states": {}}
            for state_name, projects in states_resolved.items():
                rows = []
                for p in projects:
                    total = p.get("total")
                    subtotal = p.get("subtotal")
                    iva = p.get("iva")
                    rows.append({
                        "numero": p.get("numero", ""),
                        "nombre_proyecto": p.get("nombre_proyecto", ""),
                        "cliente": p.get("cliente", ""),
                        "administracion_nombre": p.get("administracion_nombre", ""),
                        "direccion": p.get("direccion", ""),
                        "tipo_obra": p.get("tipo_obra", ""),
                        "fecha": p.get("fecha", ""),
                        "total": total if total is not None else None,
                        "subtotal": subtotal if subtotal is not None else None,
                        "iva": iva if iva is not None else None,
                        "ruta_excel": p.get("ruta_excel", ""),
                        "ruta_carpeta": p.get("ruta_carpeta", ""),
                        "estado": p.get("estado", ""),
                        "es_finalizado": bool(p.get("es_finalizado", False)),
                    })
                out["states"][state_name] = rows
            return json.dumps(out, default=str)
        except Exception as ex:
            return json.dumps({"root_path": "", "states": {}, "error": str(ex)})

    @Slot(str, result=str)
    def openBudget(self, ruta_excel: str) -> str:
        """Abre el presupuesto en Excel. Devuelve {ok:true} o {ok:false, error}."""
        try:
            from src.core.services.budget_service import BudgetService
            svc = BudgetService()
            svc.open_budget(ruta_excel)
            return json.dumps({"ok": True})
        except Exception as ex:
            return json.dumps({"ok": False, "error": str(ex)})

    # ── Base de datos ─────────────────────────────────────────────────

    @Slot(result=str)
    def getAdministraciones(self) -> str:
        """Lista administraciones para la tabla."""
        try:
            from src.core import db_repository as repo
            rows = repo.get_administraciones_para_tabla()
            return json.dumps(rows, default=str)
        except Exception as ex:
            return json.dumps([], default=str)

    @Slot(result=str)
    def getAdministracionesList(self) -> str:
        """Lista simple {id, nombre} para dropdowns."""
        try:
            from src.core import db_repository as repo
            rows = repo.get_administraciones()
            return json.dumps([{"id": r["id"], "nombre": r["nombre"]} for r in rows], default=str)
        except Exception as ex:
            return json.dumps([], default=str)

    @Slot(result=str)
    def getComunidades(self) -> str:
        """Lista comunidades para la tabla."""
        try:
            from src.core import db_repository as repo
            rows = repo.get_comunidades_para_tabla()
            return json.dumps(rows, default=str)
        except Exception as ex:
            return json.dumps([], default=str)

    @Slot(int, result=str)
    def getAdministracion(self, id_: int) -> str:
        """Obtiene una administración por id."""
        try:
            from src.core import db_repository as repo
            r = repo.get_administracion_por_id(id_)
            return json.dumps(r if r else {}, default=str)
        except Exception as ex:
            return json.dumps({}, default=str)

    @Slot(int, result=str)
    def getComunidad(self, id_: int) -> str:
        """Obtiene una comunidad por id."""
        try:
            from src.core import db_repository as repo
            r = repo.get_comunidad_por_id(id_)
            return json.dumps(r if r else {}, default=str)
        except Exception as ex:
            return json.dumps({}, default=str)

    @Slot(str, result=str)
    def createAdministracion(self, json_str: str) -> str:
        """Crea administración. json: {nombre, email?, telefono?, direccion?}. Devuelve {ok, id?} o {ok:false, error}."""
        try:
            from src.core import db_repository as repo
            data = json.loads(json_str)
            nombre = (data.get("nombre") or "").strip()
            if not nombre:
                return json.dumps({"ok": False, "error": "El nombre es obligatorio"})
            id_, err = repo.create_administracion(
                nombre,
                (data.get("email") or "").strip(),
                (data.get("telefono") or "").strip(),
                (data.get("direccion") or "").strip(),
            )
            if err:
                return json.dumps({"ok": False, "error": err})
            return json.dumps({"ok": True, "id": id_})
        except Exception as ex:
            return json.dumps({"ok": False, "error": str(ex)})

    @Slot(str, result=str)
    def updateAdministracion(self, json_str: str) -> str:
        """Actualiza administración. json: {id, nombre, email?, telefono?, direccion?}."""
        try:
            from src.core import db_repository as repo
            data = json.loads(json_str)
            id_ = int(data.get("id", 0))
            if not id_:
                return json.dumps({"ok": False, "error": "ID inválido"})
            nombre = (data.get("nombre") or "").strip()
            if not nombre:
                return json.dumps({"ok": False, "error": "El nombre es obligatorio"})
            err = repo.update_administracion(
                id_,
                nombre,
                (data.get("email") or "").strip(),
                (data.get("telefono") or "").strip(),
                (data.get("direccion") or "").strip(),
            )
            if err:
                return json.dumps({"ok": False, "error": err})
            return json.dumps({"ok": True})
        except Exception as ex:
            return json.dumps({"ok": False, "error": str(ex)})

    @Slot(int, result=str)
    def deleteAdministracion(self, id_: int) -> str:
        """Elimina una administración."""
        try:
            from src.core import db_repository as repo
            err = repo.delete_administracion(id_)
            if err:
                return json.dumps({"ok": False, "error": err})
            return json.dumps({"ok": True})
        except Exception as ex:
            return json.dumps({"ok": False, "error": str(ex)})

    @Slot(str, result=str)
    def createComunidad(self, json_str: str) -> str:
        """Crea comunidad. json: {nombre, administracion_id, cif?, direccion?, email?, telefono?}."""
        try:
            from src.core import db_repository as repo
            data = json.loads(json_str)
            nombre = (data.get("nombre") or "").strip()
            admin_id = int(data.get("administracion_id") or 0)
            if not nombre:
                return json.dumps({"ok": False, "error": "El nombre es obligatorio"})
            if not admin_id:
                return json.dumps({"ok": False, "error": "La administración es obligatoria"})
            id_, err = repo.create_comunidad(
                nombre,
                admin_id,
                cif=(data.get("cif") or "").strip(),
                direccion=(data.get("direccion") or "").strip(),
                email=(data.get("email") or "").strip(),
                telefono=(data.get("telefono") or "").strip(),
            )
            if err:
                return json.dumps({"ok": False, "error": err})
            return json.dumps({"ok": True, "id": id_})
        except Exception as ex:
            return json.dumps({"ok": False, "error": str(ex)})

    @Slot(str, result=str)
    def updateComunidad(self, json_str: str) -> str:
        """Actualiza comunidad. json: {id, nombre, administracion_id, cif?, direccion?, email?, telefono?}."""
        try:
            from src.core import db_repository as repo
            data = json.loads(json_str)
            id_ = int(data.get("id", 0))
            admin_id = int(data.get("administracion_id") or 0)
            if not id_:
                return json.dumps({"ok": False, "error": "ID inválido"})
            nombre = (data.get("nombre") or "").strip()
            if not nombre:
                return json.dumps({"ok": False, "error": "El nombre es obligatorio"})
            if not admin_id:
                return json.dumps({"ok": False, "error": "La administración es obligatoria"})
            err = repo.update_comunidad(
                id_,
                nombre,
                admin_id,
                cif=(data.get("cif") or "").strip(),
                direccion=(data.get("direccion") or "").strip(),
                email=(data.get("email") or "").strip(),
                telefono=(data.get("telefono") or "").strip(),
            )
            if err:
                return json.dumps({"ok": False, "error": err})
            return json.dumps({"ok": True})
        except Exception as ex:
            return json.dumps({"ok": False, "error": str(ex)})

    @Slot(int, result=str)
    def deleteComunidad(self, id_: int) -> str:
        """Elimina una comunidad."""
        try:
            from src.core import db_repository as repo
            err = repo.delete_comunidad(id_)
            if err:
                return json.dumps({"ok": False, "error": err})
            return json.dumps({"ok": True})
        except Exception as ex:
            return json.dumps({"ok": False, "error": str(ex)})


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log = logging.getLogger(__name__)

    if not (WEB_UI_DIR / "index.html").exists():
        log.error("No existe web/ui/index.html")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setApplicationName("cubiApp")

    view = QWebEngineView()
    view.settings().setAttribute(
        QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False
    )

    window = _MainWindow()
    bridge = AppBridge(window)
    channel = QWebChannel(view.page())
    channel.registerObject("app", bridge)
    view.page().setWebChannel(channel)

    window.setCentralWidget(view)
    window._view = view

    url = QUrl.fromLocalFile(str(WEB_UI_DIR / "index.html"))
    view.setUrl(url)

    window.show()
    sys.exit(app.exec())


class _MainWindow(QMainWindow):
    """Ventana principal con métodos para el bridge (todo inline, sin imports src)."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("cubiApp")
        self.resize(1200, 800)
        self._view = None
        self._db_frame = None
        self._dashboard_frame = None
        self._center()

    def _center(self):
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(geo.x() + (geo.width() - self.width()) // 2,
                     geo.y() + (geo.height() - self.height()) // 2)

    def _open_dashboard(self):
        try:
            from src.gui.budget_dashboard import BudgetDashboardFrame
            if self._dashboard_frame:
                try:
                    if self._dashboard_frame.isVisible():
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
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Error", f"Error al abrir el dashboard: {ex}")

    def _open_db_manager(self):
        try:
            from src.gui.db_manager import DBManagerFrame
            if self._db_frame:
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
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Error", f"Error al abrir la base de datos: {ex}")

    def _create_budget(self):
        try:
            from src.gui.main_frame import MainFrame
            helper = MainFrame(parent=None, title="")
            helper.hide()
            helper._create_budget()
        except Exception as ex:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Error", f"Error al crear presupuesto: {ex}")

    def _open_template_manager(self):
        try:
            from src.gui.template_manager_dialog import TemplateManagerDialog
            TemplateManagerDialog(parent=None).exec()
        except Exception as ex:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Error", f"Error: {ex}")

    def _open_default_paths(self):
        """Navega a la vista Configuración del dashboard."""
        if self._view:
            self._view.page().runJavaScript(
                "if(window.showConfigView)window.showConfigView();"
            )

    def _open_ai_settings(self):
        """Navega a la vista Configuración del dashboard."""
        if self._view:
            self._view.page().runJavaScript(
                "if(window.showConfigView)window.showConfigView();"
            )

    def _show_about(self):
        """Muestra el modal HTML Acerca de (Fase 2)."""
        if self._view:
            self._view.page().runJavaScript(
                "if(window.appModals)window.appModals.showAbout();"
            )


if __name__ == "__main__":
    main()
