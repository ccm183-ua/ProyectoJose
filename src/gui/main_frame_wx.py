"""
Ventana principal de cubiApp (wxPython).
"""

import os
import subprocess
import sys

import wx

from src.core.excel_manager import ExcelManager
from src.core.file_manager import FileManager
from src.core.template_manager import TemplateManager
from src.core import database as db_module
from src.core import db_repository
from src.utils.helpers import sanitize_filename
from src.gui import theme


class MainFrame(wx.Frame):
    def __init__(self, parent, title="cubiApp", **kwargs):
        super().__init__(parent, title=title, size=(520, 520), 
                         style=wx.DEFAULT_FRAME_STYLE, **kwargs)
        self.excel_manager = ExcelManager()
        self.file_manager = FileManager()
        self.template_manager = TemplateManager()
        self._db_frame = None
        self._dashboard_frame = None
        self._build_ui()
        self.Centre()

    def _build_ui(self):
        # Panel principal
        panel = wx.Panel(self)
        panel.SetBackgroundColour(theme.BG_PRIMARY)
        theme.style_frame(self)
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # === HEADER ===
        header = wx.Panel(panel)
        header.SetBackgroundColour(theme.BG_PRIMARY)
        header_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Logo/Título
        title = theme.create_title(header, "cubiApp", "display")
        header_sizer.Add(title, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 60)
        
        # Subtítulo
        subtitle = theme.create_subtitle(header, "Gestión de presupuestos")
        header_sizer.Add(subtitle, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 8)
        
        header.SetSizer(header_sizer)
        main_sizer.Add(header, 0, wx.EXPAND)
        
        main_sizer.AddSpacer(50)
        
        # === BOTONES ===
        btn_container = wx.Panel(panel)
        btn_container.SetBackgroundColour(theme.BG_PRIMARY)
        btn_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Botón crear (primario) - Botón nativo estilizado
        btn_create = wx.Button(btn_container, label="+ Crear nuevo presupuesto", size=(320, 50))
        btn_create.SetFont(theme.get_font_medium(12))
        btn_create.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_create.SetForegroundColour(theme.TEXT_INVERSE)
        btn_create.Bind(wx.EVT_BUTTON, lambda e: self._create_budget())
        btn_sizer.Add(btn_create, 0, wx.ALIGN_CENTER | wx.BOTTOM, theme.SPACE_LG)
        
        # Botón presupuestos existentes - Botón nativo estilizado
        btn_open = wx.Button(btn_container, label="Presupuestos existentes", size=(320, 46))
        btn_open.SetFont(theme.font_base())
        btn_open.SetBackgroundColour(theme.BG_SECONDARY)
        btn_open.SetForegroundColour(theme.TEXT_PRIMARY)
        btn_open.Bind(wx.EVT_BUTTON, lambda e: self._open_dashboard())
        btn_sizer.Add(btn_open, 0, wx.ALIGN_CENTER | wx.BOTTOM, theme.SPACE_MD)

        # Botón base de datos - Botón nativo estilizado
        btn_db = wx.Button(btn_container, label="Gestionar base de datos", size=(320, 46))
        btn_db.SetFont(theme.font_base())
        btn_db.SetBackgroundColour(theme.BG_SECONDARY)
        btn_db.SetForegroundColour(theme.TEXT_PRIMARY)
        btn_db.Bind(wx.EVT_BUTTON, lambda e: self._open_db_manager())
        btn_sizer.Add(btn_db, 0, wx.ALIGN_CENTER)
        
        btn_container.SetSizer(btn_sizer)
        main_sizer.Add(btn_container, 1, wx.EXPAND)
        
        # === FOOTER ===
        footer = theme.create_caption(panel, "versión 1.0")
        main_sizer.Add(footer, 0, wx.ALIGN_CENTER | wx.BOTTOM, theme.SPACE_XL)
        
        panel.SetSizer(main_sizer)
        self._create_menu()

    def _create_menu(self):
        menubar = wx.MenuBar()
        # Archivo
        m_archivo = wx.Menu()
        m_archivo.Append(wx.ID_OPEN, "Abrir presupuesto...\tCtrl+O")
        m_archivo.Append(wx.ID_NEW, "Crear nuevo presupuesto...\tCtrl+N")
        m_archivo.AppendSeparator()
        m_archivo.Append(wx.ID_EXIT, "Salir\tCtrl+Q")
        self.Bind(wx.EVT_MENU, lambda e: self._open_excel(), id=wx.ID_OPEN)
        self.Bind(wx.EVT_MENU, lambda e: self._create_budget(), id=wx.ID_NEW)
        self.Bind(wx.EVT_MENU, lambda e: self.Close(), id=wx.ID_EXIT)
        menubar.Append(m_archivo, "&Archivo")

        m_bd = wx.Menu()
        item_db = m_bd.Append(wx.ID_ANY, "Gestionar base de datos...")
        self.Bind(wx.EVT_MENU, lambda e: self._open_db_manager(), item_db)
        item_folder = m_bd.Append(wx.ID_ANY, "Abrir carpeta de la base de datos")
        self.Bind(wx.EVT_MENU, lambda e: self._open_db_folder(), item_folder)
        menubar.Append(m_bd, "Base de &datos")

        # Configuración
        m_config = wx.Menu()
        item_ai = m_config.Append(wx.ID_ANY, "Configuración IA (API Key)...")
        self.Bind(wx.EVT_MENU, lambda e: self._open_ai_settings(), item_ai)
        item_templates = m_config.Append(wx.ID_ANY, "Gestionar plantillas...")
        self.Bind(wx.EVT_MENU, lambda e: self._open_template_manager(), item_templates)
        item_paths = m_config.Append(wx.ID_ANY, "Rutas por defecto...")
        self.Bind(wx.EVT_MENU, lambda e: self._open_default_paths(), item_paths)
        menubar.Append(m_config, "&Configuración")

        m_ayuda = wx.Menu()
        m_ayuda.Append(wx.ID_ABOUT, "Acerca de...")
        self.Bind(wx.EVT_MENU, lambda e: wx.MessageBox("cubiApp\n\nAbre o crea presupuestos desde plantilla Excel.", "Acerca de", wx.OK), id=wx.ID_ABOUT)
        menubar.Append(m_ayuda, "&Ayuda")

        self.SetMenuBar(menubar)

    def _open_db_manager(self):
        try:
            from src.gui.db_manager_wx import DBManagerFrame
            # Comprobar si el frame anterior fue destruido (C++ deleted)
            try:
                if self._db_frame is not None and self._db_frame.IsShown():
                    self._db_frame.Raise()
                    return
            except RuntimeError:
                # El objeto C++ ya fue destruido; crear uno nuevo
                self._db_frame = None

            self._db_frame = DBManagerFrame(self)
            self._db_frame.Bind(wx.EVT_CLOSE, self._on_db_frame_closed)
            self._db_frame.Show()
            self._db_frame.Raise()
        except Exception as ex:
            wx.MessageBox(f"Error al abrir la base de datos: {ex}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_db_frame_closed(self, event):
        """Limpiar la referencia cuando se cierra la ventana de BD."""
        self._db_frame = None
        event.Skip()

    def _open_dashboard(self):
        try:
            from src.gui.budget_dashboard_wx import BudgetDashboardFrame
            try:
                if self._dashboard_frame is not None and self._dashboard_frame.IsShown():
                    self._dashboard_frame.Raise()
                    return
            except RuntimeError:
                self._dashboard_frame = None

            self._dashboard_frame = BudgetDashboardFrame(self)
            self._dashboard_frame.Bind(wx.EVT_CLOSE, self._on_dashboard_closed)
            self._dashboard_frame.Show()
            self._dashboard_frame.Raise()
        except Exception as ex:
            wx.MessageBox(f"Error al abrir el dashboard: {ex}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_dashboard_closed(self, event):
        self._dashboard_frame = None
        event.Skip()

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
            wx.MessageBox(f"Error: {ex}", "Error", wx.OK | wx.ICON_ERROR)

    def _open_excel(self):
        from src.core.settings import Settings
        default_dir = Settings().get_default_path(Settings.PATH_OPEN_BUDGETS) or ""
        with wx.FileDialog(self, "Abrir Presupuesto", defaultDir=default_dir, wildcard="Excel (*.xlsx;*.xls)|*.xlsx;*.xls|Todos (*.*)|*.*", style=wx.FD_OPEN) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        if not path:
            return
        try:
            budget = self.excel_manager.load_budget(path)
            if budget:
                budget.close()
                db_repository.registrar_presupuesto({
                    "nombre_proyecto": os.path.splitext(os.path.basename(path))[0],
                    "ruta_excel": path,
                    "ruta_carpeta": os.path.dirname(path),
                })
                wx.MessageBox(f"Presupuesto abierto: {os.path.basename(path)}", "Éxito", wx.OK)
            else:
                wx.MessageBox("No se pudo abrir el archivo Excel.", "Error", wx.OK | wx.ICON_ERROR)
        except Exception as ex:
            wx.MessageBox(f"Error: {ex}", "Error", wx.OK | wx.ICON_ERROR)

    def _create_budget(self):
        project_data, project_name = self._obtain_project_data()
        if not project_data or not project_name:
            return

        from src.core.settings import Settings
        save_default_dir = Settings().get_default_path(Settings.PATH_SAVE_BUDGETS) or ""
        with wx.FileDialog(self, "Guardar Presupuesto", defaultDir=save_default_dir, defaultFile=f"{sanitize_filename(project_name)}.xlsx", wildcard="Excel (*.xlsx)|*.xlsx|Todos (*.*)|*.*", style=wx.FD_SAVE) as fd:
            if fd.ShowModal() != wx.ID_OK:
                return
            save_path = fd.GetPath()
        if not save_path:
            return

        subfolders = ["FOTOS", "PLANOS", "PROYECTO", "MEDICIONES", "PRESUPUESTOS"]
        folder_name = sanitize_filename(project_name)
        save_dir = os.path.dirname(save_path)
        folder_path = os.path.join(save_dir, folder_name)
        if not self.file_manager.create_folder(folder_path):
            wx.MessageBox("No se pudo crear la carpeta.", "Error", wx.OK | wx.ICON_ERROR)
            return
        self.file_manager.create_subfolders(folder_path, subfolders)
        save_path = os.path.join(folder_path, f"{folder_name}.xlsx")

        template_path = self.template_manager.get_template_path()
        if not os.path.exists(template_path):
            wx.MessageBox("No se encontró la plantilla.", "Error", wx.OK | wx.ICON_ERROR)
            return

        # Buscar comunidad en la BDD a partir del campo "cliente"
        comunidad_data = self._buscar_comunidad_para_presupuesto(project_data.get("cliente", ""))

        excel_data = {
            "nombre_obra": project_name,
            "direccion": project_data.get("calle", ""),
            "numero": project_data.get("num_calle", ""),
            "codigo_postal": project_data.get("codigo_postal", ""),
            "descripcion": project_data.get("tipo", ""),
            "numero_proyecto": project_data.get("numero", ""),
            "fecha": project_data.get("fecha", ""),
            "cliente": project_data.get("cliente", ""),
            "mediacion": project_data.get("mediacion", ""),
            "calle": project_data.get("calle", ""),
            "num_calle": project_data.get("num_calle", ""),
            "localidad": project_data.get("localidad", ""),
            "tipo": project_data.get("tipo", ""),
            "admin_cif": comunidad_data.get("cif", "") if comunidad_data else "",
            "admin_email": comunidad_data.get("email", "") if comunidad_data else "",
            "admin_telefono": comunidad_data.get("telefono", "") if comunidad_data else "",
        }
        if not self.excel_manager.create_from_template(template_path, save_path, excel_data):
            wx.MessageBox("Error al crear el presupuesto.", "Error", wx.OK | wx.ICON_ERROR)
            return

        # Registrar en historial
        db_repository.registrar_presupuesto({
            "nombre_proyecto": project_name,
            "ruta_excel": save_path,
            "ruta_carpeta": folder_path,
            "cliente": project_data.get("cliente", ""),
            "localidad": project_data.get("localidad", ""),
            "tipo_obra": project_data.get("tipo", ""),
            "numero_proyecto": project_data.get("numero", ""),
        })

        # --- Flujo de generación de partidas con IA ---
        self._offer_ai_partidas(save_path, project_data)

    def _obtain_project_data(self):
        """Obtiene ``(project_data, project_name)`` intentando primero el Excel de relación."""
        from src.gui.dialogs_wx import obtain_project_data
        return obtain_project_data(self)

    def _open_default_paths(self):
        from src.gui.dialogs_wx import DefaultPathsDialog
        dlg = DefaultPathsDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

    def _buscar_comunidad_para_presupuesto(self, nombre_cliente: str) -> dict | None:
        """
        Busca una comunidad en la BDD cuyo nombre coincida con el campo
        'cliente' del proyecto. Muestra un diálogo de confirmación si se
        encuentra (exacta o fuzzy).

        Args:
            nombre_cliente: Nombre del cliente/comunidad a buscar.

        Returns:
            Dict con los datos de la comunidad confirmada, o None.
        """
        from src.gui.dialogs_wx import (
            ComunidadConfirmDialog, ComunidadFuzzySelectDialog,
            crear_comunidad_con_formulario,
        )

        if not nombre_cliente or not nombre_cliente.strip():
            return None

        nombre = nombre_cliente.strip()

        # 1. Búsqueda exacta (case-insensitive)
        comunidad = db_repository.buscar_comunidad_por_nombre(nombre)
        if comunidad:
            dlg = ComunidadConfirmDialog(self, comunidad, nombre)
            resultado = dlg.ShowModal()
            datos = dlg.get_comunidad_data() if resultado == wx.ID_OK else None
            dlg.Destroy()
            return datos

        # 2. Búsqueda fuzzy
        fuzzy = db_repository.buscar_comunidades_fuzzy(nombre)
        if fuzzy:
            dlg = ComunidadFuzzySelectDialog(self, fuzzy, nombre)
            resultado = dlg.ShowModal()
            datos = dlg.get_comunidad_data() if resultado == wx.ID_OK else None
            dlg.Destroy()
            return datos

        # 3. No se encontró nada → ofrecer crear nueva comunidad
        resp = wx.MessageBox(
            f'No se encontró ninguna comunidad con el nombre "{nombre}".\n\n'
            "¿Desea añadir una nueva comunidad a la base de datos?",
            "Comunidad no encontrada",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if resp == wx.YES:
            return crear_comunidad_con_formulario(self, nombre_prefill=nombre)

        return None

    def _offer_ai_partidas(self, excel_path, project_data):
        """
        Ofrece al usuario generar partidas con IA tras crear el presupuesto.

        Args:
            excel_path: Ruta del Excel recién creado.
            project_data: Datos del proyecto (localidad, cliente, etc.).
        """
        from src.gui.ai_budget_dialog_wx import AIBudgetDialog
        from src.gui.partidas_dialog_wx import SuggestedPartidasDialog

        # Paso 1: Diálogo de configuración IA
        ai_dlg = AIBudgetDialog(self, datos_proyecto=project_data)
        if ai_dlg.ShowModal() != wx.ID_OK:
            ai_dlg.Destroy()
            wx.MessageBox(
                f"Presupuesto creado (sin partidas IA):\n{excel_path}",
                "Éxito", wx.OK,
            )
            return

        result = ai_dlg.get_result()
        ai_dlg.Destroy()

        if not result or not result.get('partidas'):
            wx.MessageBox(
                f"Presupuesto creado (sin partidas IA):\n{excel_path}",
                "Éxito", wx.OK,
            )
            return

        # Paso 2: Diálogo de revisión de partidas
        partidas_dlg = SuggestedPartidasDialog(self, result)
        if partidas_dlg.ShowModal() != wx.ID_OK:
            partidas_dlg.Destroy()
            wx.MessageBox(
                f"Presupuesto creado (sin partidas IA):\n{excel_path}",
                "Éxito", wx.OK,
            )
            return

        selected = partidas_dlg.get_selected_partidas()
        partidas_dlg.Destroy()

        # Paso 3: Insertar partidas seleccionadas en el Excel via XML
        if selected:
            if self.excel_manager.insert_partidas_via_xml(excel_path, selected):
                db_repository.registrar_presupuesto({
                    "nombre_proyecto": project_data.get("nombre_obra", os.path.basename(excel_path)),
                    "ruta_excel": excel_path,
                    "usa_partidas_ia": True,
                })
                from src.core.budget_reader import BudgetReader
                data = BudgetReader().read(excel_path)
                if data:
                    db_repository.actualizar_total(excel_path, data["total"])
                wx.MessageBox(
                    f"Presupuesto creado con {len(selected)} partidas:\n{excel_path}",
                    "Éxito", wx.OK,
                )
            else:
                wx.MessageBox(
                    f"Presupuesto creado pero hubo un error al insertar las partidas.\n{excel_path}",
                    "Aviso", wx.OK | wx.ICON_WARNING,
                )
        else:
            wx.MessageBox(
                f"Presupuesto creado (sin partidas):\n{excel_path}",
                "Éxito", wx.OK,
            )

    def _open_template_manager(self):
        """Abre el diálogo de gestión de plantillas de presupuesto."""
        from src.gui.template_manager_dialog import TemplateManagerDialog
        dlg = TemplateManagerDialog(self)
        dlg.ShowModal()
        dlg.Destroy()

    def _open_ai_settings(self):
        """Abre el diálogo de configuración de API key para la IA."""
        from src.core.settings import Settings
        settings = Settings()
        current_key = settings.get_api_key() or ""

        dlg = wx.TextEntryDialog(
            self,
            "Introduce tu API key de Google Gemini.\n"
            "Puedes obtenerla gratis en: https://aistudio.google.com/apikey\n\n"
            "La clave se guardará de forma local y segura.",
            "Configuración IA - API Key",
            value=current_key,
        )
        if dlg.ShowModal() == wx.ID_OK:
            new_key = dlg.GetValue().strip()
            if new_key and (len(new_key) < 10 or not new_key.startswith("AI")):
                confirm = wx.MessageBox(
                    "La clave introducida no parece tener el formato esperado "
                    "(las claves de Gemini suelen empezar por 'AI' y tener ~39 caracteres).\n\n"
                    "¿Guardar de todas formas?",
                    "Formato sospechoso",
                    wx.YES_NO | wx.ICON_WARNING,
                )
                if confirm != wx.YES:
                    dlg.Destroy()
                    return
            settings.save_api_key(new_key)
            if new_key:
                wx.MessageBox("API key guardada correctamente.", "Configuración IA", wx.OK)
            else:
                wx.MessageBox("API key eliminada.", "Configuración IA", wx.OK)
        dlg.Destroy()
