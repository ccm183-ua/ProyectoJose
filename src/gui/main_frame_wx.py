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


class MainFrame(wx.Frame):
    def __init__(self, parent, title="cubiApp", **kwargs):
        super().__init__(parent, title=title, size=(420, 320), **kwargs)
        self.excel_manager = ExcelManager()
        self.file_manager = FileManager()
        self.template_manager = TemplateManager()
        self._db_frame = None
        self._build_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(panel, label="cubiApp", style=wx.ALIGN_CENTER), 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 12)

        btn_open = wx.Button(panel, label="Abrir presupuesto existente", size=(280, 36))
        btn_open.Bind(wx.EVT_BUTTON, lambda e: self._open_excel())
        sizer.Add(btn_open, 0, wx.ALL, 6)

        btn_create = wx.Button(panel, label="Crear nuevo presupuesto", size=(280, 36))
        btn_create.Bind(wx.EVT_BUTTON, lambda e: self._create_budget())
        sizer.Add(btn_create, 0, wx.ALL, 6)

        btn_db = wx.Button(panel, label="Gestionar base de datos", size=(280, 36))
        btn_db.Bind(wx.EVT_BUTTON, lambda e: self._open_db_manager())
        sizer.Add(btn_db, 0, wx.ALL, 6)

        panel.SetSizer(sizer)
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
