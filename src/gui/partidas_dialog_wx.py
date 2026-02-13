"""
Diálogo de revisión de partidas sugeridas por la IA.

Muestra las partidas generadas en una tabla editable donde el usuario puede:
- Seleccionar/deseleccionar partidas con checkboxes
- Editar cantidades y precios
- Aplicar las seleccionadas al presupuesto
- Regenerar con la IA
- Cancelar sin añadir partidas
"""

import wx
import wx.lib.mixins.listctrl as listmix

from src.gui import theme


class SuggestedPartidasDialog(wx.Dialog):
    """Diálogo para revisar y seleccionar partidas sugeridas."""

    def __init__(self, parent, result):
        """
        Args:
            parent: Ventana padre.
            result: Diccionario con 'partidas', 'error', 'source' del BudgetGenerator.
        """
        super().__init__(
            parent,
            title="Partidas Sugeridas",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        theme.style_dialog(self)

        self._partidas = result.get('partidas', [])
        self._source = result.get('source', 'ia')
        self._selected_partidas = []  # Resultado final

        self._build_ui()
        self._populate_list()
        self.CenterOnParent()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Título ---
        title = theme.create_title(panel, "Partidas Sugeridas", "xl")
        main_sizer.Add(title, 0, wx.ALL, theme.SPACE_XL)

        # --- Indicador de fuente ---
        source_sizer = wx.BoxSizer(wx.HORIZONTAL)
        if self._source == 'ia':
            source_label = "Generado con IA"
            source_color = theme.SUCCESS
        else:
            source_label = "Desde plantilla offline"
            source_color = theme.WARNING

        source_text = wx.StaticText(panel, label=source_label)
        source_text.SetFont(theme.font_sm())
        source_text.SetForegroundColour(source_color)
        source_sizer.Add(source_text, 0, wx.ALIGN_CENTER_VERTICAL)

        source_sizer.AddSpacer(theme.SPACE_LG)

        count_text = wx.StaticText(
            panel, label=f"{len(self._partidas)} partidas generadas"
        )
        count_text.SetFont(theme.font_sm())
        count_text.SetForegroundColour(theme.TEXT_SECONDARY)
        source_sizer.Add(count_text, 0, wx.ALIGN_CENTER_VERTICAL)

        main_sizer.Add(source_sizer, 0, wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        # --- Aviso de precios orientativos ---
        warning_sizer = wx.BoxSizer(wx.HORIZONTAL)
        warning_icon = wx.StaticText(panel, label="ℹ")
        warning_icon.SetFont(theme.font_lg())
        warning_icon.SetForegroundColour(theme.ACCENT_PRIMARY)
        warning_sizer.Add(warning_icon, 0, wx.RIGHT, theme.SPACE_SM)

        warning_text = theme.create_text(
            panel,
            "Los precios son orientativos. Revise y ajuste antes de enviar al cliente.",
        )
        warning_text.SetForegroundColour(theme.TEXT_SECONDARY)
        warning_sizer.Add(warning_text, 1, wx.ALIGN_CENTER_VERTICAL)

        main_sizer.AddSpacer(theme.SPACE_MD)
        main_sizer.Add(warning_sizer, 0, wx.LEFT | wx.RIGHT, theme.SPACE_XL)
        main_sizer.AddSpacer(theme.SPACE_LG)

        # --- Tabla de partidas ---
        self._list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE,
        )
        theme.style_listctrl(self._list)

        self._list.InsertColumn(0, "", width=30)  # Checkbox visual
        self._list.InsertColumn(1, "Concepto", width=320)
        self._list.InsertColumn(2, "Cantidad", width=80)
        self._list.InsertColumn(3, "Unidad", width=70)
        self._list.InsertColumn(4, "Precio Unit.", width=100)
        self._list.InsertColumn(5, "Importe", width=100)

        main_sizer.Add(
            self._list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL
        )

        # --- Botones de selección ---
        sel_sizer = wx.BoxSizer(wx.HORIZONTAL)

        btn_select_all = wx.Button(panel, label="Seleccionar todas", size=(150, 34))
        btn_select_all.SetFont(theme.font_sm())
        btn_select_all.Bind(wx.EVT_BUTTON, self._on_select_all)

        btn_deselect_all = wx.Button(panel, label="Deseleccionar todas", size=(150, 34))
        btn_deselect_all.SetFont(theme.font_sm())
        btn_deselect_all.Bind(wx.EVT_BUTTON, self._on_deselect_all)

        btn_toggle = wx.Button(panel, label="Invertir selección", size=(140, 34))
        btn_toggle.SetFont(theme.font_sm())
        btn_toggle.Bind(wx.EVT_BUTTON, self._on_toggle_selection)

        sel_sizer.Add(btn_select_all, 0, wx.RIGHT, theme.SPACE_SM)
        sel_sizer.Add(btn_deselect_all, 0, wx.RIGHT, theme.SPACE_SM)
        sel_sizer.Add(btn_toggle, 0)

        main_sizer.AddSpacer(theme.SPACE_MD)
        main_sizer.Add(sel_sizer, 0, wx.LEFT, theme.SPACE_XL)

        # --- Separador ---
        main_sizer.AddSpacer(theme.SPACE_LG)
        main_sizer.Add(
            theme.create_divider(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL
        )
        main_sizer.AddSpacer(theme.SPACE_LG)

        # --- Botones de acción ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancelar", size=(120, 44))
        btn_cancel.SetFont(theme.font_base())
        btn_cancel.SetToolTip("Crear presupuesto sin partidas")

        btn_apply = wx.Button(
            panel, wx.ID_OK, "Aplicar seleccionadas", size=(200, 44)
        )
        btn_apply.SetFont(theme.get_font_medium())
        btn_apply.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_apply.SetForegroundColour(theme.TEXT_INVERSE)
        btn_apply.SetDefault()

        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_apply, 0)

        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, theme.SPACE_XL)

        panel.SetSizer(main_sizer)

        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)

        self.SetMinSize((780, 520))
        self.SetSize((820, 600))

        # Eventos
        self._list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_item_toggle)
        self.Bind(wx.EVT_BUTTON, self._on_apply, id=wx.ID_OK)

        # Track de selección: todas seleccionadas por defecto
        self._selected = [True] * len(self._partidas)

    def _populate_list(self):
        """Rellena la tabla con las partidas."""
        self._list.DeleteAllItems()
        for i, partida in enumerate(self._partidas):
            cantidad = partida.get('cantidad', 1)
            precio = partida.get('precio_unitario', 0)
            importe = cantidad * precio

            idx = self._list.InsertItem(i, "✓")
            self._list.SetItem(idx, 1, str(partida.get('concepto', '')))
            self._list.SetItem(idx, 2, str(cantidad))
            self._list.SetItem(idx, 3, str(partida.get('unidad', 'ud')))
            self._list.SetItem(idx, 4, f"{precio:.2f} €")
            self._list.SetItem(idx, 5, f"{importe:.2f} €")

    def _on_item_toggle(self, event):
        """Toggle selección al hacer doble clic."""
        idx = event.GetIndex()
        if 0 <= idx < len(self._selected):
            self._selected[idx] = not self._selected[idx]
            self._update_check_mark(idx)

    def _update_check_mark(self, idx):
        """Actualiza el indicador visual de selección."""
        mark = "✓" if self._selected[idx] else ""
        self._list.SetItem(idx, 0, mark)

    def _on_select_all(self, event):
        """Selecciona todas las partidas."""
        for i in range(len(self._selected)):
            self._selected[i] = True
            self._update_check_mark(i)

    def _on_deselect_all(self, event):
        """Deselecciona todas las partidas."""
        for i in range(len(self._selected)):
            self._selected[i] = False
            self._update_check_mark(i)

    def _on_toggle_selection(self, event):
        """Invierte la selección."""
        for i in range(len(self._selected)):
            self._selected[i] = not self._selected[i]
            self._update_check_mark(i)

    def _on_apply(self, event):
        """Aplica las partidas seleccionadas."""
        self._selected_partidas = []
        for i, partida in enumerate(self._partidas):
            if i < len(self._selected) and self._selected[i]:
                self._selected_partidas.append(partida)

        if not self._selected_partidas:
            dlg = wx.MessageBox(
                "No hay partidas seleccionadas. ¿Desea continuar sin partidas?",
                "Sin selección",
                wx.YES_NO | wx.ICON_QUESTION,
            )
            if dlg == wx.NO:
                return

        self.EndModal(wx.ID_OK)

    def get_selected_partidas(self):
        """Devuelve las partidas seleccionadas por el usuario."""
        return self._selected_partidas
