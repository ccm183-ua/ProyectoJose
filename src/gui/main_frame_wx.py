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
from src.utils.helpers import sanitize_filename
from src.gui import theme


class MainFrame(wx.Frame):
    def __init__(self, parent, title="cubiApp", **kwargs):
        super().__init__(parent, title=title, size=(500, 450), 
                         style=wx.DEFAULT_FRAME_STYLE, **kwargs)
        self.excel_manager = ExcelManager()
        self.file_manager = FileManager()
        self.template_manager = TemplateManager()
        self._db_frame = None
        self._build_ui()
        self.Centre()

    def _build_ui(self):
        # Panel principal
        panel = wx.Panel(self)
        theme.apply_theme_to_panel(panel)
        theme.apply_theme_to_frame(self)
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Header con título
        header_panel = wx.Panel(panel)
        header_panel.SetBackgroundColour(theme.BG_PRIMARY)
        header_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título principal
        title = wx.StaticText(header_panel, label="cubiApp")
        title.SetFont(theme.get_font_title(28))
        title.SetForegroundColour(theme.TEXT_PRIMARY)
        header_sizer.Add(title, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 50)
        
        # Subtítulo
        subtitle = wx.StaticText(header_panel, label="Gestión de presupuestos")
        subtitle.SetFont(theme.get_font_subtitle(13))
        subtitle.SetForegroundColour(theme.TEXT_SECONDARY)
        header_sizer.Add(subtitle, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 8)
        
        header_panel.SetSizer(header_sizer)
        main_sizer.Add(header_panel, 0, wx.EXPAND)
        
        # Espaciador
        main_sizer.AddSpacer(40)
        
        # Contenedor de botones
        btn_panel = wx.Panel(panel)
        btn_panel.SetBackgroundColour(theme.BG_PRIMARY)
        btn_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Botón crear (primario - destacado)
        btn_create = wx.Button(btn_panel, label="+ Crear nuevo presupuesto", size=(300, 48))
        btn_create.SetFont(theme.get_font_medium(11))
        btn_create.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_create.SetForegroundColour(wx.WHITE)
        btn_create.Bind(wx.EVT_BUTTON, lambda e: self._create_budget())
        btn_sizer.Add(btn_create, 0, wx.ALIGN_CENTER | wx.BOTTOM, 16)
        
        # Botón abrir (secundario)
        btn_open = wx.Button(btn_panel, label="Abrir presupuesto existente", size=(300, 44))
        btn_open.SetFont(theme.get_font_normal(11))
        btn_open.SetBackgroundColour(theme.BG_SECONDARY)
        btn_open.SetForegroundColour(theme.TEXT_PRIMARY)
        btn_open.Bind(wx.EVT_BUTTON, lambda e: self._open_excel())
        btn_sizer.Add(btn_open, 0, wx.ALIGN_CENTER | wx.BOTTOM, 12)

        # Botón base de datos (terciario)
        btn_db = wx.Button(btn_panel, label="Gestionar base de datos", size=(300, 44))
        btn_db.SetFont(theme.get_font_normal(11))
        btn_db.SetBackgroundColour(theme.BG_SECONDARY)
        btn_db.SetForegroundColour(theme.TEXT_PRIMARY)
        btn_db.Bind(wx.EVT_BUTTON, lambda e: self._open_db_manager())
        btn_sizer.Add(btn_db, 0, wx.ALIGN_CENTER)
        
        btn_panel.SetSizer(btn_sizer)
        main_sizer.Add(btn_panel, 1, wx.EXPAND)
        
        # Footer con versión
        footer = wx.StaticText(panel, label="v1.0")
        footer.SetFont(theme.get_font_normal(9))
        footer.SetForegroundColour(theme.TEXT_MUTED)
        main_sizer.Add(footer, 0, wx.ALIGN_CENTER | wx.BOTTOM, 20)
        
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

        m_ayuda = wx.Menu()
        m_ayuda.Append(wx.ID_ABOUT, "Acerca de...")
        self.Bind(wx.EVT_MENU, lambda e: wx.MessageBox("cubiApp\n\nAbre o crea presupuestos desde plantilla Excel.", "Acerca de", wx.OK), id=wx.ID_ABOUT)
        menubar.Append(m_ayuda, "&Ayuda")

        self.SetMenuBar(menubar)

    def _open_db_manager(self):
        try:
            from src.gui.db_manager_wx import DBManagerFrame
            if self._db_frame is None or not self._db_frame.IsShown():
                self._db_frame = DBManagerFrame(self)
            self._db_frame.Show()
            self._db_frame.Raise()
        except Exception as ex:
            wx.MessageBox(f"Error al abrir la base de datos: {ex}", "Error", wx.OK | wx.ICON_ERROR)

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
        with wx.FileDialog(self, "Abrir Presupuesto", wildcard="Excel (*.xlsx;*.xls)|*.xlsx;*.xls|Todos (*.*)|*.*", style=wx.FD_OPEN) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        if not path:
            return
        try:
            budget = self.excel_manager.load_budget(path)
            if budget:
                wx.MessageBox(f"Presupuesto abierto: {os.path.basename(path)}", "Éxito", wx.OK)
            else:
                wx.MessageBox("No se pudo abrir el archivo Excel.", "Error", wx.OK | wx.ICON_ERROR)
        except Exception as ex:
            wx.MessageBox(f"Error: {ex}", "Error", wx.OK | wx.ICON_ERROR)

    def _create_budget(self):
        from src.gui.dialogs_wx import ProjectNameDialogWx
        dlg = ProjectNameDialogWx(self)
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        project_data = dlg.get_project_data()
        project_name = dlg.get_project_name()
        dlg.Destroy()
        if not project_data or not project_name:
            return

        with wx.FileDialog(self, "Guardar Presupuesto", defaultFile=f"{sanitize_filename(project_name)}.xlsx", wildcard="Excel (*.xlsx)|*.xlsx|Todos (*.*)|*.*", style=wx.FD_SAVE) as fd:
            if fd.ShowModal() != wx.ID_OK:
                return
            save_path = fd.GetPath()
        if not save_path:
            return

        create_folder = wx.MessageBox("¿Crear carpeta con el nombre del proyecto y subcarpetas (FOTOS, PLANOS, etc.)?", "Carpeta", wx.YES_NO | wx.ICON_QUESTION) == wx.YES
        # Subcarpetas que se crean dentro de la carpeta del proyecto (src/core/file_manager.create_subfolders)
        subfolders = ["FOTOS", "PLANOS", "PROYECTO", "MEDICIONES", "PRESUPUESTOS"]

        if create_folder:
            folder_name = sanitize_filename(project_name)
            save_dir = os.path.dirname(save_path)
            folder_path = os.path.join(save_dir, folder_name)
            if not self.file_manager.create_folder(folder_path):
                wx.MessageBox("No se pudo crear la carpeta.", "Error", wx.OK | wx.ICON_ERROR)
                return
            self.file_manager.create_subfolders(folder_path, subfolders)
            save_path = os.path.join(folder_path, f"{folder_name}.xlsx")
        else:
            save_dir = os.path.dirname(save_path)
            save_path = os.path.join(save_dir, f"{sanitize_filename(project_name)}.xlsx")

        template_path = self.template_manager.get_template_path()
        if not os.path.exists(template_path):
            wx.MessageBox("No se encontró la plantilla.", "Error", wx.OK | wx.ICON_ERROR)
            return

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
        }
        if self.excel_manager.create_from_template(template_path, save_path, excel_data):
            wx.MessageBox(f"Presupuesto creado:\n{save_path}", "Éxito", wx.OK)
        else:
            wx.MessageBox("Error al crear el presupuesto.", "Error", wx.OK | wx.ICON_ERROR)
