"""
Diálogos wxPython para cubiApp.
"""

import wx
from src.core.project_parser import ProjectParser
from src.core import db_repository
from src.utils.project_name_generator import ProjectNameGenerator
from src.gui import theme


# ---------------------------------------------------------------------------
# Diálogos de confirmación / selección de administración
# ---------------------------------------------------------------------------

ID_BTN_NUEVA_ADMIN = wx.NewIdRef()


class NuevaAdminDialog(wx.Dialog):
    """Formulario para crear una nueva administración desde el flujo de presupuesto."""

    def __init__(self, parent, nombre_prefill: str = ""):
        super().__init__(parent, title="Nueva Administración",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        self._nombre_prefill = nombre_prefill
        self._admin_creada = None
        self._build_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = theme.create_title(panel, "Añadir administración", "xl")
        sizer.Add(title, 0, wx.ALL, theme.SPACE_XL)

        msg = theme.create_text(
            panel,
            "Rellene los datos de la nueva administración.\n"
            "Los campos marcados con (*) son obligatorios."
        )
        msg.Wrap(440)
        sizer.Add(msg, 0, wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        sizer.AddSpacer(theme.SPACE_LG)

        grid = wx.FlexGridSizer(cols=2, vgap=8, hgap=12)
        grid.AddGrowableCol(1, 1)

        campos_def = [
            ("Nombre (*):", "_nombre"),
            ("CIF:", "_cif"),
            ("Correo:", "_email"),
            ("Teléfono:", "_telefono"),
            ("Dirección:", "_direccion"),
        ]
        for label_text, attr in campos_def:
            lbl = wx.StaticText(panel, label=label_text)
            lbl.SetFont(theme.get_font_medium())
            lbl.SetForegroundColour(theme.TEXT_PRIMARY)
            grid.Add(lbl, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)

            txt = wx.TextCtrl(panel, size=(280, -1))
            txt.SetFont(theme.font_base())
            setattr(self, attr, txt)
            grid.Add(txt, 1, wx.EXPAND)

        self._nombre.SetValue(self._nombre_prefill)

        sizer.Add(grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        sizer.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.ALL, theme.SPACE_XL)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancelar", size=(130, 44))
        btn_cancel.SetFont(theme.font_base())
        btn_ok = wx.Button(panel, wx.ID_OK, "Guardar y usar", size=(160, 44))
        btn_ok.SetFont(theme.get_font_medium())
        btn_ok.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_ok.SetForegroundColour(theme.TEXT_INVERSE)
        btn_ok.SetDefault()
        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_ok, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, theme.SPACE_XL)

        panel.SetSizer(sizer)
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)

        self.Fit()
        size = self.GetSize()
        self.SetMinSize((max(560, size.x), max(470, size.y)))
        self.SetSize((max(560, size.x), max(470, size.y)))
        self.CenterOnParent()

        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

    def _on_ok(self, event):
        nombre = self._nombre.GetValue().strip()
        if not nombre:
            wx.MessageBox("El nombre de la administración es obligatorio.", "Aviso", wx.OK)
            return

        cif = self._cif.GetValue().strip()
        email = self._email.GetValue().strip()
        telefono = self._telefono.GetValue().strip()
        direccion = self._direccion.GetValue().strip()

        new_id, err = db_repository.create_administracion(
            nombre, cif=cif, email=email, telefono=telefono, direccion=direccion,
        )
        if err:
            wx.MessageBox(f"Error al crear la administración:\n{err}", "Error", wx.OK | wx.ICON_ERROR)
            return

        self._admin_creada = {
            "id": new_id, "nombre": nombre, "cif": cif,
            "email": email, "telefono": telefono, "direccion": direccion,
        }
        self.EndModal(wx.ID_OK)

    def get_admin_data(self) -> dict | None:
        return self._admin_creada

class AdminConfirmDialog(wx.Dialog):
    """Diálogo que muestra los datos de una administración encontrada y pide confirmación."""

    def __init__(self, parent, admin_data: dict, nombre_buscado: str):
        super().__init__(parent, title="Administración encontrada",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        self._admin = admin_data
        self._nombre_buscado = nombre_buscado
        self._build_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = theme.create_title(panel, "Administración encontrada", "xl")
        sizer.Add(title, 0, wx.ALL, theme.SPACE_XL)

        msg = theme.create_text(
            panel,
            f'Se ha encontrado una administración con el nombre "{self._nombre_buscado}".\n'
            "¿Desea rellenar automáticamente los datos del presupuesto con esta información?"
        )
        msg.Wrap(440)
        sizer.Add(msg, 0, wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        sizer.AddSpacer(theme.SPACE_LG)

        # Mostrar datos de la administración en un grid
        grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=12)
        grid.AddGrowableCol(1, 1)

        campos = [
            ("Nombre:", self._admin.get("nombre", "")),
            ("CIF:", self._admin.get("cif", "") or "(vacío)"),
            ("Correo:", self._admin.get("email", "") or "(vacío)"),
            ("Teléfono:", self._admin.get("telefono", "") or "(vacío)"),
            ("Dirección:", self._admin.get("direccion", "") or "(vacío)"),
        ]
        for label_text, value_text in campos:
            lbl = wx.StaticText(panel, label=label_text)
            lbl.SetFont(theme.get_font_medium())
            lbl.SetForegroundColour(theme.TEXT_PRIMARY)
            grid.Add(lbl, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)

            val = wx.StaticText(panel, label=value_text)
            val.SetFont(theme.font_base())
            val.SetForegroundColour(theme.TEXT_PRIMARY)
            grid.Add(val, 0, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        sizer.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.ALL, theme.SPACE_XL)

        # Botones
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_no = wx.Button(panel, wx.ID_CANCEL, "No, continuar sin datos", size=(200, 44))
        btn_no.SetFont(theme.font_base())
        btn_yes = wx.Button(panel, wx.ID_OK, "Sí, rellenar datos", size=(180, 44))
        btn_yes.SetFont(theme.get_font_medium())
        btn_yes.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_yes.SetForegroundColour(theme.TEXT_INVERSE)
        btn_yes.SetDefault()
        btn_sizer.Add(btn_no, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_yes, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, theme.SPACE_XL)

        panel.SetSizer(sizer)

        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)

        self.Fit()
        size = self.GetSize()
        self.SetMinSize((max(580, size.x), max(460, size.y)))
        self.SetSize((max(580, size.x), max(460, size.y)))
        self.CenterOnParent()

    def get_admin_data(self) -> dict:
        return self._admin


class AdminFuzzySelectDialog(wx.Dialog):
    """Diálogo que muestra coincidencias fuzzy y permite al usuario elegir una administración."""

    def __init__(self, parent, resultados: list, nombre_buscado: str):
        super().__init__(parent, title="Coincidencias aproximadas",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        self._resultados = resultados
        self._nombre_buscado = nombre_buscado
        self._selected_admin = None
        self._build_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = theme.create_title(panel, "Coincidencias aproximadas", "xl")
        sizer.Add(title, 0, wx.ALL, theme.SPACE_XL)

        msg = theme.create_text(
            panel,
            f'No se encontró una administración exacta con "{self._nombre_buscado}", '
            "pero se encontraron las siguientes coincidencias.\n"
            "Seleccione una para rellenar los datos del presupuesto:"
        )
        msg.Wrap(520)
        sizer.Add(msg, 0, wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        sizer.AddSpacer(theme.SPACE_MD)

        # Lista de resultados
        self._list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self._list.SetFont(theme.font_base())
        self._list.InsertColumn(0, "Nombre", width=200)
        self._list.InsertColumn(1, "CIF", width=100)
        self._list.InsertColumn(2, "Correo", width=160)
        self._list.InsertColumn(3, "Similitud", width=80)

        for idx, admin in enumerate(self._resultados):
            pos = self._list.InsertItem(idx, admin.get("nombre", ""))
            self._list.SetItem(pos, 1, admin.get("cif", "") or "")
            self._list.SetItem(pos, 2, admin.get("email", "") or "")
            similitud_pct = f"{admin.get('similitud', 0) * 100:.0f}%"
            self._list.SetItem(pos, 3, similitud_pct)

        if self._resultados:
            self._list.Select(0)

        sizer.Add(self._list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        sizer.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.ALL, theme.SPACE_XL)

        # Botones
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_skip = wx.Button(panel, wx.ID_CANCEL, "Continuar sin datos", size=(170, 44))
        btn_skip.SetFont(theme.font_base())
        btn_new = wx.Button(panel, ID_BTN_NUEVA_ADMIN, "Añadir nueva", size=(150, 44))
        btn_new.SetFont(theme.font_base())
        btn_ok = wx.Button(panel, wx.ID_OK, "Usar seleccionada", size=(170, 44))
        btn_ok.SetFont(theme.get_font_medium())
        btn_ok.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_ok.SetForegroundColour(theme.TEXT_INVERSE)
        btn_ok.SetDefault()
        btn_sizer.Add(btn_skip, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_new, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_ok, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, theme.SPACE_XL)

        panel.SetSizer(sizer)

        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)

        self.Fit()
        size = self.GetSize()
        self.SetMinSize((max(720, size.x), max(500, size.y)))
        self.SetSize((max(720, size.x), max(500, size.y)))
        self.CenterOnParent()

        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._on_nueva_admin, id=ID_BTN_NUEVA_ADMIN)

    def _on_ok(self, event):
        sel = self._list.GetFirstSelected()
        if sel < 0:
            wx.MessageBox("Seleccione una administración de la lista.", "Aviso", wx.OK)
            return
        self._selected_admin = self._resultados[sel]
        self.EndModal(wx.ID_OK)

    def _on_nueva_admin(self, event):
        dlg = NuevaAdminDialog(self, nombre_prefill=self._nombre_buscado)
        if dlg.ShowModal() == wx.ID_OK:
            self._selected_admin = dlg.get_admin_data()
            dlg.Destroy()
            self.EndModal(wx.ID_OK)
        else:
            dlg.Destroy()

    def get_admin_data(self) -> dict:
        return self._selected_admin


class ProjectNameDialogWx(wx.Dialog):
    """Diálogo para pegar una línea del Excel y obtener nombre del proyecto."""
    def __init__(self, parent):
        super().__init__(parent, title="Nuevo Presupuesto", style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        self.parser = ProjectParser()
        self.name_generator = ProjectNameGenerator()
        self.project_data = None
        self.project_name = None
        self._build_ui()
        self._load_from_clipboard()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título
        title = theme.create_title(panel, "Crear Presupuesto", "xl")
        sizer.Add(title, 0, wx.ALL, theme.SPACE_XL)
        
        # Instrucciones
        inst = theme.create_text(panel, "Copia una fila completa (columnas A-I) desde tu Excel de presupuestos "
                                        "y pégalo en el campo de abajo, o haz clic en 'Cargar desde Portapapeles'.")
        inst.Wrap(540)
        sizer.Add(inst, 0, wx.LEFT | wx.RIGHT, theme.SPACE_XL)
        
        # Label datos
        lbl_datos = wx.StaticText(panel, label="Datos del proyecto:")
        lbl_datos.SetFont(theme.get_font_medium())
        lbl_datos.SetForegroundColour(theme.TEXT_PRIMARY)
        sizer.Add(lbl_datos, 0, wx.LEFT | wx.TOP, theme.SPACE_XL)
        
        self._data_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 90))
        theme.style_textctrl(self._data_text)
        try:
            self._data_text.SetHint("Pega aquí los datos del Excel (Ctrl+V)")
        except AttributeError:
            pass
        self._data_text.Bind(wx.EVT_TEXT, lambda e: self._validate_data())
        sizer.Add(self._data_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_XL)
        
        btn_load = wx.Button(panel, label="Cargar desde Portapapeles", size=(220, 40))
        btn_load.SetFont(theme.font_base())
        btn_load.Bind(wx.EVT_BUTTON, lambda e: self._load_from_clipboard())
        sizer.Add(btn_load, 0, wx.LEFT | wx.TOP, theme.SPACE_XL)
        
        # Label nombre
        lbl_nombre = wx.StaticText(panel, label="Nombre del proyecto:")
        lbl_nombre.SetFont(theme.get_font_medium())
        lbl_nombre.SetForegroundColour(theme.TEXT_PRIMARY)
        sizer.Add(lbl_nombre, 0, wx.LEFT | wx.TOP, theme.SPACE_XL)
        
        self._name_field = wx.TextCtrl(panel, style=wx.TE_READONLY, size=(-1, 36))
        self._name_field.SetBackgroundColour(theme.BG_SECONDARY)
        self._name_field.SetFont(theme.font_base())
        sizer.Add(self._name_field, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_XL)
        
        # Separador
        sizer.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.ALL, theme.SPACE_XL)
        
        # Botones
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancelar", size=(130, 44))
        btn_cancel.SetFont(theme.font_base())
        
        btn_ok = wx.Button(panel, wx.ID_OK, "Crear Presupuesto", size=(160, 44))
        btn_ok.SetFont(theme.get_font_medium())
        btn_ok.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_ok.SetForegroundColour(theme.TEXT_INVERSE)
        btn_ok.SetDefault()
        
        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_ok, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, theme.SPACE_XL)
        
        panel.SetSizer(sizer)
        
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)
        
        self.SetMinSize((600, 560))
        self.SetSize((660, 600))
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
