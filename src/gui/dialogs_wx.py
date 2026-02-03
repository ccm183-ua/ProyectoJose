"""
Diálogos wxPython para cubiApp.
"""

import wx
from src.core.project_parser import ProjectParser
from src.utils.project_name_generator import ProjectNameGenerator


class ProjectNameDialogWx(wx.Dialog):
    """Diálogo para pegar una línea del Excel y obtener nombre del proyecto."""
    def __init__(self, parent):
        super().__init__(parent, title="Nombre del proyecto", size=(620, 380))
        self.parser = ProjectParser()
        self.name_generator = ProjectNameGenerator()
        self.project_data = None
        self.project_name = None
        self._build_ui()
        self._load_from_clipboard()

    def _build_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        inst = wx.StaticText(panel, label="Copia una fila completa (columnas A-I) desde tu Excel de presupuestos "
                                          "y pégalo en el campo de abajo, o haz clic en 'Cargar desde Portapapeles'.")
        inst.Wrap(560)
        sizer.Add(inst, 0, wx.ALL, 8)
        sizer.Add(wx.StaticText(panel, label="Datos del proyecto:"), 0, wx.LEFT | wx.TOP, 8)
        self._data_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(580, 80))
        try:
            self._data_text.SetHint("Pega aquí los datos del Excel (Ctrl+V). Formato: Nº\tFECHA\tCLIENTE\tMEDIACIÓN\tCALLE\tNUM\tC.P\tLOCALIDAD\tTIPO")
        except AttributeError:
            pass
        self._data_text.Bind(wx.EVT_TEXT, lambda e: self._validate_data())
        sizer.Add(self._data_text, 0, wx.ALL, 8)
        btn_load = wx.Button(panel, label="Cargar desde Portapapeles")
        btn_load.Bind(wx.EVT_BUTTON, lambda e: self._load_from_clipboard())
        sizer.Add(btn_load, 0, wx.LEFT, 8)
        sizer.Add(wx.StaticText(panel, label="Nombre del proyecto:"), 0, wx.LEFT | wx.TOP, 12)
        self._name_field = wx.TextCtrl(panel, style=wx.TE_READONLY, size=(580, -1))
        sizer.Add(self._name_field, 0, wx.ALL, 8)
        btn_sizer = wx.StdDialogButtonSizer()
        btn_sizer.AddButton(wx.Button(panel, wx.ID_CANCEL, "Cancelar"))
        btn_ok = wx.Button(panel, wx.ID_OK, "Validar y Continuar")
        btn_ok.SetDefault()
        btn_sizer.AddButton(btn_ok)
        btn_sizer.Realize()
        sizer.Add(btn_sizer, 0, wx.ALL | wx.ALIGN_RIGHT, 10)
        panel.SetSizer(sizer)
        self.Bind(wx.EVT_BUTTON, self._on_validate_ok, id=wx.ID_OK)

    def _load_from_clipboard(self):
        if wx.TheClipboard.Open():
            try:
                data = wx.TextDataObject()
                if wx.TheClipboard.GetData(data):
                    text = data.GetText()
                    if text:
                        self._data_text.SetValue(text)
                        self._validate_data()
                    else:
                        wx.MessageBox("No hay datos en el portapapeles. Copia una fila desde tu Excel.", "Portapapeles vacío", wx.OK)
                else:
                    wx.MessageBox("No hay datos en el portapapeles.", "Portapapeles vacío", wx.OK)
            finally:
                wx.TheClipboard.Close()

    def _validate_data(self):
        text = self._data_text.GetValue().strip()
        if not text:
            self._name_field.SetValue("")
            return
        project_data, error = self.parser.parse_clipboard_data(text)
        if error:
            self._name_field.SetValue(f"Error: {error}")
            return
        self.project_data = project_data
        self.project_name = self.name_generator.generate_project_name(project_data)
        self._name_field.SetValue(self.project_name)

    def _on_validate_ok(self, evt):
        text = self._data_text.GetValue().strip()
        if not text:
            wx.MessageBox("Por favor, ingresa los datos del proyecto.", "Datos vacíos", wx.OK)
            return
        project_data, error = self.parser.parse_clipboard_data(text)
        if error:
            wx.MessageBox(error, "Error de validación", wx.OK)
            return
        self.project_data = project_data
        self.project_name = self.name_generator.generate_project_name(project_data)
        self.EndModal(wx.ID_OK)

    def get_project_data(self):
        return self.project_data

    def get_project_name(self):
        return self.project_name
