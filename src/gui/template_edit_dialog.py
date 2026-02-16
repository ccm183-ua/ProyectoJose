"""
Diálogo para editar una plantilla personalizada.

Permite editar todos los campos de una plantilla: nombre, categoría,
descripción, contexto_ia y las partidas_base individualmente
(añadir, editar, eliminar partidas).
"""

import wx

from src.core.template_validator import TemplateValidator
from src.gui import theme


class PartidaEditDialog(wx.Dialog):
    """Mini-diálogo para añadir o editar una partida individual."""

    def __init__(self, parent, partida=None):
        """
        Args:
            parent: Ventana padre.
            partida: Diccionario con la partida a editar (None = nueva).
        """
        title = "Editar partida" if partida else "Añadir partida"
        super().__init__(
            parent, title=title,
            style=wx.DEFAULT_DIALOG_STYLE,
        )
        theme.style_dialog(self)
        self._partida = partida or {}
        self._result = None
        self._build_ui()
        self.CenterOnParent()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Concepto
        lbl_concepto = wx.StaticText(panel, label="Concepto:")
        lbl_concepto.SetFont(theme.get_font_medium())
        lbl_concepto.SetForegroundColour(theme.TEXT_PRIMARY)
        sizer.Add(lbl_concepto, 0, wx.LEFT | wx.TOP, theme.SPACE_LG)

        self._txt_concepto = wx.TextCtrl(panel, size=(350, -1))
        theme.style_textctrl(self._txt_concepto)
        self._txt_concepto.SetValue(self._partida.get('concepto', ''))
        sizer.Add(self._txt_concepto, 0, wx.EXPAND | wx.ALL, theme.SPACE_SM)

        # Unidad
        lbl_unidad = wx.StaticText(panel, label="Unidad (m2, ml, ud, kg...):")
        lbl_unidad.SetFont(theme.get_font_medium())
        lbl_unidad.SetForegroundColour(theme.TEXT_PRIMARY)
        sizer.Add(lbl_unidad, 0, wx.LEFT | wx.TOP, theme.SPACE_SM)

        self._txt_unidad = wx.TextCtrl(panel, size=(100, -1))
        theme.style_textctrl(self._txt_unidad)
        self._txt_unidad.SetValue(self._partida.get('unidad', 'ud'))
        sizer.Add(self._txt_unidad, 0, wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_SM)

        # Precio
        lbl_precio = wx.StaticText(panel, label="Precio de referencia (€):")
        lbl_precio.SetFont(theme.get_font_medium())
        lbl_precio.SetForegroundColour(theme.TEXT_PRIMARY)
        sizer.Add(lbl_precio, 0, wx.LEFT | wx.TOP, theme.SPACE_SM)

        self._txt_precio = wx.TextCtrl(panel, size=(120, -1))
        theme.style_textctrl(self._txt_precio)
        precio = self._partida.get('precio_ref', '')
        self._txt_precio.SetValue(str(precio) if precio else '')
        sizer.Add(self._txt_precio, 0, wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_SM)

        # Botones
        sizer.AddSpacer(theme.SPACE_LG)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancelar", size=(100, 36))
        btn_cancel.SetFont(theme.font_base())

        btn_ok = wx.Button(panel, wx.ID_OK, "Aceptar", size=(100, 36))
        btn_ok.SetFont(theme.get_font_medium())
        btn_ok.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_ok.SetForegroundColour(theme.TEXT_INVERSE)

        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, theme.SPACE_SM)
        btn_sizer.Add(btn_ok, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, theme.SPACE_LG)

        panel.SetSizer(sizer)

        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)
        self.Fit()

        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

    def _on_ok(self, event):
        """Valida y devuelve la partida."""
        concepto = self._txt_concepto.GetValue().strip()
        unidad = self._txt_unidad.GetValue().strip()
        precio_str = self._txt_precio.GetValue().strip()

        if not concepto:
            wx.MessageBox("El concepto es obligatorio.", "Error", wx.OK | wx.ICON_WARNING)
            return
        if not unidad:
            wx.MessageBox("La unidad es obligatoria.", "Error", wx.OK | wx.ICON_WARNING)
            return

        try:
            precio = float(precio_str.replace(',', '.'))
            if precio <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            wx.MessageBox(
                "El precio debe ser un número positivo.",
                "Error", wx.OK | wx.ICON_WARNING,
            )
            return

        self._result = {
            'concepto': concepto,
            'unidad': unidad,
            'precio_ref': round(precio, 2),
        }
        self.EndModal(wx.ID_OK)

    def get_result(self):
        """Devuelve la partida editada o None si se canceló."""
        return self._result


class TemplateEditDialog(wx.Dialog):
    """Diálogo para editar una plantilla personalizada."""

    def __init__(self, parent, plantilla: dict):
        """
        Args:
            parent: Ventana padre.
            plantilla: Plantilla a editar (dict completo).
                       Puede estar vacía para crear una nueva.
        """
        title = "Editar Plantilla" if plantilla.get('nombre') else "Crear Plantilla"
        super().__init__(
            parent, title=title,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        theme.style_dialog(self)

        self._original = plantilla
        self._result = None
        self._build_ui()
        self._populate(plantilla)
        self.CenterOnParent()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Título ---
        title_text = "Editar Plantilla" if self._original.get('nombre') else "Crear Plantilla"
        title = theme.create_title(panel, title_text, "xl")
        main_sizer.Add(title, 0, wx.ALL, theme.SPACE_XL)

        # --- Campos básicos ---
        fields_sizer = wx.FlexGridSizer(3, 2, theme.SPACE_SM, theme.SPACE_MD)
        fields_sizer.AddGrowableCol(1, 1)

        # Nombre
        lbl_nombre = wx.StaticText(panel, label="Nombre:")
        lbl_nombre.SetFont(theme.get_font_medium())
        lbl_nombre.SetForegroundColour(theme.TEXT_PRIMARY)
        self._txt_nombre = wx.TextCtrl(panel, size=(350, -1))
        theme.style_textctrl(self._txt_nombre)
        fields_sizer.Add(lbl_nombre, 0, wx.ALIGN_CENTER_VERTICAL)
        fields_sizer.Add(self._txt_nombre, 1, wx.EXPAND)

        # Categoría
        lbl_cat = wx.StaticText(panel, label="Categoría:")
        lbl_cat.SetFont(theme.get_font_medium())
        lbl_cat.SetForegroundColour(theme.TEXT_PRIMARY)
        self._txt_categoria = wx.TextCtrl(panel, size=(350, -1))
        theme.style_textctrl(self._txt_categoria)
        fields_sizer.Add(lbl_cat, 0, wx.ALIGN_CENTER_VERTICAL)
        fields_sizer.Add(self._txt_categoria, 1, wx.EXPAND)

        # Descripción
        lbl_desc = wx.StaticText(panel, label="Descripción:")
        lbl_desc.SetFont(theme.get_font_medium())
        lbl_desc.SetForegroundColour(theme.TEXT_PRIMARY)
        self._txt_descripcion = wx.TextCtrl(panel, size=(350, -1))
        theme.style_textctrl(self._txt_descripcion)
        fields_sizer.Add(lbl_desc, 0, wx.ALIGN_CENTER_VERTICAL)
        fields_sizer.Add(self._txt_descripcion, 1, wx.EXPAND)

        main_sizer.Add(
            fields_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL
        )

        main_sizer.AddSpacer(theme.SPACE_MD)

        # --- Contexto IA ---
        lbl_contexto = wx.StaticText(panel, label="Contexto para la IA:")
        lbl_contexto.SetFont(theme.get_font_medium())
        lbl_contexto.SetForegroundColour(theme.TEXT_PRIMARY)
        main_sizer.Add(lbl_contexto, 0, wx.LEFT, theme.SPACE_XL)

        hint_contexto = theme.create_text(
            panel,
            "Este texto se envía directamente a la IA como contexto. "
            "Cuanto más detallado, mejor será el resultado.",
            muted=True,
        )
        hint_contexto.Wrap(500)
        main_sizer.Add(hint_contexto, 0, wx.LEFT | wx.TOP, theme.SPACE_SM)

        self._txt_contexto = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE, size=(-1, 90)
        )
        theme.style_textctrl(self._txt_contexto)
        main_sizer.Add(
            self._txt_contexto, 0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_SM
        )

        main_sizer.AddSpacer(theme.SPACE_MD)

        # --- Partidas de referencia ---
        lbl_partidas = wx.StaticText(panel, label="Partidas de referencia:")
        lbl_partidas.SetFont(theme.get_font_medium())
        lbl_partidas.SetForegroundColour(theme.TEXT_PRIMARY)
        main_sizer.Add(lbl_partidas, 0, wx.LEFT, theme.SPACE_XL)

        self._partidas_list = wx.ListCtrl(
            panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(-1, 160)
        )
        self._partidas_list.SetFont(theme.font_sm())
        self._partidas_list.SetBackgroundColour(theme.BG_CARD)
        self._partidas_list.InsertColumn(0, "Concepto", width=260)
        self._partidas_list.InsertColumn(1, "Ud.", width=50)
        self._partidas_list.InsertColumn(2, "Precio ref.", width=90)
        main_sizer.Add(
            self._partidas_list, 1,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_SM
        )

        # Botones de partidas
        partida_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        btn_add_partida = wx.Button(panel, label="+ Añadir partida", size=(130, 32))
        btn_add_partida.SetFont(theme.font_sm())
        btn_add_partida.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_add_partida.SetForegroundColour(theme.TEXT_INVERSE)

        self._btn_edit_partida = wx.Button(panel, label="Editar", size=(80, 32))
        self._btn_edit_partida.SetFont(theme.font_sm())
        self._btn_edit_partida.Enable(False)

        self._btn_del_partida = wx.Button(panel, label="Eliminar partida", size=(120, 32))
        self._btn_del_partida.SetFont(theme.font_sm())
        self._btn_del_partida.Enable(False)

        partida_btn_sizer.Add(btn_add_partida, 0, wx.RIGHT, theme.SPACE_SM)
        partida_btn_sizer.Add(self._btn_edit_partida, 0, wx.RIGHT, theme.SPACE_SM)
        partida_btn_sizer.Add(self._btn_del_partida, 0)

        main_sizer.Add(
            partida_btn_sizer, 0,
            wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_SM
        )

        # Contador
        self._lbl_partida_count = theme.create_text(panel, "", muted=True)
        main_sizer.Add(self._lbl_partida_count, 0, wx.LEFT | wx.TOP, theme.SPACE_SM)

        # --- Separador + Botones principales ---
        main_sizer.AddSpacer(theme.SPACE_LG)
        main_sizer.Add(
            theme.create_divider(panel), 0,
            wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL
        )
        main_sizer.AddSpacer(theme.SPACE_LG)

        action_sizer = wx.BoxSizer(wx.HORIZONTAL)

        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancelar", size=(100, 40))
        btn_cancel.SetFont(theme.font_base())

        btn_save = wx.Button(panel, wx.ID_OK, "Guardar", size=(120, 40))
        btn_save.SetFont(theme.get_font_medium())
        btn_save.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_save.SetForegroundColour(theme.TEXT_INVERSE)

        action_sizer.Add(btn_cancel, 0, wx.RIGHT, theme.SPACE_MD)
        action_sizer.Add(btn_save, 0)
        main_sizer.Add(
            action_sizer, 0,
            wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, theme.SPACE_XL
        )

        panel.SetSizer(main_sizer)

        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)

        self.SetMinSize((600, 620))
        self.SetSize((640, 700))

        # Eventos
        btn_add_partida.Bind(wx.EVT_BUTTON, self._on_add_partida)
        self._btn_edit_partida.Bind(wx.EVT_BUTTON, self._on_edit_partida)
        self._btn_del_partida.Bind(wx.EVT_BUTTON, self._on_del_partida)
        self._partidas_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_partida_select)
        self._partidas_list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_partida_deselect)
        self._partidas_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_edit_partida)
        self.Bind(wx.EVT_BUTTON, self._on_save, id=wx.ID_OK)

    def _populate(self, plantilla: dict):
        """Rellena los campos con los datos de la plantilla."""
        self._txt_nombre.SetValue(plantilla.get('nombre', ''))
        self._txt_categoria.SetValue(plantilla.get('categoria', ''))
        self._txt_descripcion.SetValue(plantilla.get('descripcion', ''))
        self._txt_contexto.SetValue(plantilla.get('contexto_ia', ''))

        self._partidas = list(plantilla.get('partidas_base', []))
        self._refresh_partidas_list()

    def _refresh_partidas_list(self):
        """Recarga la lista visual de partidas."""
        self._partidas_list.DeleteAllItems()
        for i, p in enumerate(self._partidas):
            idx = self._partidas_list.InsertItem(i, p.get('concepto', ''))
            self._partidas_list.SetItem(idx, 1, p.get('unidad', 'ud'))
            precio = p.get('precio_ref', 0)
            self._partidas_list.SetItem(idx, 2, f"{precio:.2f} €")

        count = len(self._partidas)
        self._lbl_partida_count.SetLabel(
            f"{count} partida{'s' if count != 1 else ''}"
        )
        self._btn_edit_partida.Enable(False)
        self._btn_del_partida.Enable(False)

    def _on_partida_select(self, event):
        """Habilita botones al seleccionar una partida."""
        self._btn_edit_partida.Enable(True)
        self._btn_del_partida.Enable(True)

    def _on_partida_deselect(self, event):
        """Deshabilita botones al deseleccionar."""
        sel = self._partidas_list.GetFirstSelected()
        if sel == -1:
            self._btn_edit_partida.Enable(False)
            self._btn_del_partida.Enable(False)

    def _on_add_partida(self, event):
        """Abre el mini-diálogo para añadir una partida."""
        dlg = PartidaEditDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            result = dlg.get_result()
            if result:
                self._partidas.append(result)
                self._refresh_partidas_list()
        dlg.Destroy()

    def _on_edit_partida(self, event):
        """Abre el mini-diálogo para editar la partida seleccionada."""
        sel = self._partidas_list.GetFirstSelected()
        if sel == -1:
            return

        partida = self._partidas[sel]
        dlg = PartidaEditDialog(self, partida=dict(partida))
        if dlg.ShowModal() == wx.ID_OK:
            result = dlg.get_result()
            if result:
                self._partidas[sel] = result
                self._refresh_partidas_list()
        dlg.Destroy()

    def _on_del_partida(self, event):
        """Elimina la partida seleccionada."""
        sel = self._partidas_list.GetFirstSelected()
        if sel == -1:
            return

        concepto = self._partidas[sel].get('concepto', '')
        confirm = wx.MessageBox(
            f"¿Eliminar la partida '{concepto[:50]}'?",
            "Confirmar", wx.YES_NO | wx.ICON_QUESTION,
        )
        if confirm == wx.YES:
            del self._partidas[sel]
            self._refresh_partidas_list()

    def _on_save(self, event):
        """Valida y guarda la plantilla editada."""
        plantilla = {
            'nombre': self._txt_nombre.GetValue().strip(),
            'categoria': self._txt_categoria.GetValue().strip(),
            'descripcion': self._txt_descripcion.GetValue().strip(),
            'contexto_ia': self._txt_contexto.GetValue().strip(),
            'partidas_base': list(self._partidas),
        }

        # Conservar el flag personalizada si existía
        if self._original.get('personalizada'):
            plantilla['personalizada'] = True

        # Validar
        validator = TemplateValidator()
        is_valid, errors = validator.validate(plantilla)
        if not is_valid:
            error_text = "Errores de validación:\n\n" + "\n".join(f"• {e}" for e in errors)
            wx.MessageBox(error_text, "Plantilla no válida", wx.OK | wx.ICON_WARNING)
            return

        self._result = plantilla
        self.EndModal(wx.ID_OK)

    def get_result(self):
        """Devuelve la plantilla editada o None si se canceló."""
        return self._result
