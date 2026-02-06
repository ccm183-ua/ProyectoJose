"""
Diálogos wxPython para cubiApp.
"""

import wx
from src.core.project_parser import ProjectParser
from src.utils.project_name_generator import ProjectNameGenerator
from src.gui import theme


class ProjectNameDialogWx(wx.Dialog):
    """Diálogo para pegar una línea del Excel y obtener nombre del proyecto."""
    def __init__(self, parent):
        super().__init__(parent, title="Nuevo Presupuesto", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.apply_theme_to_dialog(self)
        self.parser = ProjectParser()
        self.name_generator = ProjectNameGenerator()
        self.project_data = None
        self.project_name = None
        self._build_ui()
        self._load_from_clipboard()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.apply_theme_to_panel(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título
        title = theme.create_styled_title(panel, "Crear Presupuesto")
        sizer.Add(title, 0, wx.ALL, 20)
        
        # Instrucciones
        inst = wx.StaticText(panel, label="Copia una fila completa (columnas A-I) desde tu Excel de presupuestos "
                                          "y pégalo en el campo de abajo, o haz clic en 'Cargar desde Portapapeles'.")
        inst.SetForegroundColour(theme.TEXT_SECONDARY)
        inst.Wrap(540)
        sizer.Add(inst, 0, wx.LEFT | wx.RIGHT, 20)
        
        # Label datos
        lbl_datos = wx.StaticText(panel, label="Datos del proyecto:")
        lbl_datos.SetFont(theme.get_font_bold(10))
        sizer.Add(lbl_datos, 0, wx.LEFT | wx.TOP, 20)
        
        self._data_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 80))
        theme.style_textctrl(self._data_text)
        try:
            self._data_text.SetHint("Pega aquí los datos del Excel (Ctrl+V)")
        except AttributeError:
            pass
        self._data_text.Bind(wx.EVT_TEXT, lambda e: self._validate_data())
        sizer.Add(self._data_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 20)
        
        btn_load = wx.Button(panel, label="Cargar desde Portapapeles", size=(200, 36))
        btn_load.Bind(wx.EVT_BUTTON, lambda e: self._load_from_clipboard())
        sizer.Add(btn_load, 0, wx.LEFT | wx.TOP, 20)
        
        # Label nombre
        lbl_nombre = wx.StaticText(panel, label="Nombre del proyecto:")
        lbl_nombre.SetFont(theme.get_font_bold(10))
        sizer.Add(lbl_nombre, 0, wx.LEFT | wx.TOP, 20)
        
        self._name_field = wx.TextCtrl(panel, style=wx.TE_READONLY, size=(-1, 32))
        self._name_field.SetBackgroundColour(theme.BG_SECONDARY)
        sizer.Add(self._name_field, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 20)
        
        # Separador
        sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.ALL, 20)
        
        # Botones
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancelar", size=(120, 40))
        btn_ok = wx.Button(panel, wx.ID_OK, "Crear Presupuesto", size=(150, 40))
        theme.style_button_primary(btn_ok)
        btn_ok.SetDefault()
        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, 10)
        btn_sizer.Add(btn_ok, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, 20)
        
        panel.SetSizer(sizer)
        
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)
        
        self.SetMinSize((580, 450))
        self.SetSize((620, 500))
        self.CenterOnParent()
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
