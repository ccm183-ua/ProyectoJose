"""
Diálogo para gestionar plantillas de presupuesto personalizadas.

Permite al usuario:
- Ver la lista de plantillas (predefinidas y personalizadas)
- Añadir nuevas plantillas importando partidas desde un Excel existente
- Eliminar plantillas personalizadas (no las predefinidas)
- Ver las partidas de una plantilla seleccionada
"""

import os

import wx

from src.core.work_type_catalog import WorkTypeCatalog
from src.core.excel_partidas_extractor import ExcelPartidasExtractor
from src.gui import theme


class TemplateManagerDialog(wx.Dialog):
    """Diálogo para gestionar plantillas de presupuesto."""

    def __init__(self, parent):
        super().__init__(
            parent,
            title="Gestionar Plantillas de Presupuesto",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        theme.style_dialog(self)

        self._catalog = WorkTypeCatalog()
        self._extractor = ExcelPartidasExtractor()

        self._build_ui()
        self._refresh_list()
        self.CenterOnParent()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Título ---
        title = theme.create_title(panel, "Gestionar Plantillas", "xl")
        main_sizer.Add(title, 0, wx.ALL, theme.SPACE_XL)

        subtitle = theme.create_text(
            panel,
            "Gestiona tu biblioteca de plantillas de presupuesto. "
            "Las plantillas personalizadas se crean importando las partidas "
            "desde un presupuesto Excel ya existente."
        )
        subtitle.Wrap(560)
        main_sizer.Add(subtitle, 0, wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        main_sizer.AddSpacer(theme.SPACE_LG)

        # --- Contenido principal: lista + detalle ---
        content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Panel izquierdo: lista de plantillas
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        lbl_list = wx.StaticText(panel, label="Plantillas disponibles:")
        lbl_list.SetFont(theme.get_font_medium())
        lbl_list.SetForegroundColour(theme.TEXT_PRIMARY)
        left_sizer.Add(lbl_list, 0, wx.BOTTOM, theme.SPACE_SM)

        self._template_list = wx.ListBox(panel, size=(280, 280))
        self._template_list.SetFont(theme.font_base())
        self._template_list.SetBackgroundColour(theme.BG_CARD)
        left_sizer.Add(self._template_list, 1, wx.EXPAND)

        # Botones debajo de la lista
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        btn_add = wx.Button(panel, label="+ Añadir desde Excel", size=(160, 38))
        btn_add.SetFont(theme.get_font_medium())
        btn_add.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_add.SetForegroundColour(theme.TEXT_INVERSE)

        self._btn_delete = wx.Button(panel, label="Eliminar", size=(90, 38))
        self._btn_delete.SetFont(theme.font_base())
        self._btn_delete.Enable(False)

        btn_sizer.Add(btn_add, 0, wx.RIGHT, theme.SPACE_SM)
        btn_sizer.Add(self._btn_delete, 0)

        left_sizer.Add(btn_sizer, 0, wx.TOP, theme.SPACE_MD)

        content_sizer.Add(left_sizer, 0, wx.EXPAND | wx.RIGHT, theme.SPACE_LG)

        # Panel derecho: detalle de la plantilla seleccionada
        right_sizer = wx.BoxSizer(wx.VERTICAL)

        lbl_detail = wx.StaticText(panel, label="Partidas de la plantilla:")
        lbl_detail.SetFont(theme.get_font_medium())
        lbl_detail.SetForegroundColour(theme.TEXT_PRIMARY)
        right_sizer.Add(lbl_detail, 0, wx.BOTTOM, theme.SPACE_SM)

        self._detail_list = wx.ListCtrl(
            panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(320, 280)
        )
        self._detail_list.SetFont(theme.font_sm())
        self._detail_list.SetBackgroundColour(theme.BG_CARD)
        self._detail_list.InsertColumn(0, "Concepto", width=180)
        self._detail_list.InsertColumn(1, "Ud.", width=40)
        self._detail_list.InsertColumn(2, "Precio ref.", width=80)
        right_sizer.Add(self._detail_list, 1, wx.EXPAND)

        # Contador de partidas
        self._lbl_count = theme.create_text(panel, "", muted=True)
        right_sizer.Add(self._lbl_count, 0, wx.TOP, theme.SPACE_SM)

        content_sizer.Add(right_sizer, 1, wx.EXPAND)

        main_sizer.Add(
            content_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL
        )

        # --- Separador + Cerrar ---
        main_sizer.AddSpacer(theme.SPACE_LG)
        main_sizer.Add(
            theme.create_divider(panel), 0,
            wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL
        )
        main_sizer.AddSpacer(theme.SPACE_LG)

        btn_close = wx.Button(panel, wx.ID_CLOSE, "Cerrar", size=(100, 40))
        btn_close.SetFont(theme.font_base())
        main_sizer.Add(btn_close, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, theme.SPACE_XL)

        panel.SetSizer(main_sizer)

        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)

        self.SetMinSize((700, 520))
        self.SetSize((740, 560))

        # Eventos
        self._template_list.Bind(wx.EVT_LISTBOX, self._on_select)
        btn_add.Bind(wx.EVT_BUTTON, self._on_add)
        self._btn_delete.Bind(wx.EVT_BUTTON, self._on_delete)
        self.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE), id=wx.ID_CLOSE)

    def _refresh_list(self):
        """Recarga la lista de plantillas."""
        self._template_list.Clear()
        self._detail_list.DeleteAllItems()
        self._lbl_count.SetLabel("")
        self._btn_delete.Enable(False)

        predefined = self._catalog.get_predefined_names()
        custom = self._catalog.get_custom_names()

        for name in predefined:
            self._template_list.Append(f"  {name}")
        for name in custom:
            self._template_list.Append(f"* {name}")

    def _on_select(self, event):
        """Muestra las partidas de la plantilla seleccionada."""
        sel = self._template_list.GetSelection()
        if sel == wx.NOT_FOUND:
            self._detail_list.DeleteAllItems()
            self._lbl_count.SetLabel("")
            self._btn_delete.Enable(False)
            return

        display_name = self._template_list.GetString(sel)
        # Quitar prefijo "  " o "* "
        nombre = display_name[2:]
        is_custom = display_name.startswith("* ")

        self._btn_delete.Enable(is_custom)

        plantilla = self._catalog.get_by_name(nombre)
        self._detail_list.DeleteAllItems()

        if not plantilla:
            self._lbl_count.SetLabel("")
            return

        partidas = plantilla.get('partidas_base', [])
        for i, p in enumerate(partidas):
            idx = self._detail_list.InsertItem(i, p.get('concepto', ''))
            self._detail_list.SetItem(idx, 1, p.get('unidad', 'ud'))
            precio = p.get('precio_ref', 0)
            self._detail_list.SetItem(idx, 2, f"{precio:.2f} €")

        self._lbl_count.SetLabel(f"{len(partidas)} partidas")

    def _on_add(self, event):
        """Abre el flujo para añadir una plantilla desde un Excel."""
        # Paso 1: Pedir nombre de la plantilla
        name_dlg = wx.TextEntryDialog(
            self,
            "Nombre para la nueva plantilla:\n\n"
            "Ejemplo: Reforma cocina completa, Sustitución ascensor, etc.",
            "Nueva plantilla personalizada",
        )
        if name_dlg.ShowModal() != wx.ID_OK:
            name_dlg.Destroy()
            return

        nombre = name_dlg.GetValue().strip()
        name_dlg.Destroy()

        if not nombre:
            wx.MessageBox(
                "El nombre no puede estar vacío.",
                "Error", wx.OK | wx.ICON_WARNING,
            )
            return

        # Comprobar si ya existe
        existing = self._catalog.get_by_name(nombre)
        if existing and not existing.get('personalizada'):
            wx.MessageBox(
                f"Ya existe una plantilla predefinida con ese nombre:\n'{nombre}'.\n\n"
                "Elige un nombre diferente.",
                "Nombre duplicado", wx.OK | wx.ICON_WARNING,
            )
            return

        if existing and existing.get('personalizada'):
            confirm = wx.MessageBox(
                f"Ya existe una plantilla personalizada con ese nombre:\n'{nombre}'.\n\n"
                "¿Deseas reemplazarla?",
                "Reemplazar plantilla",
                wx.YES_NO | wx.ICON_QUESTION,
            )
            if confirm != wx.YES:
                return

        # Paso 2: Seleccionar archivo Excel
        file_dlg = wx.FileDialog(
            self,
            "Selecciona el presupuesto Excel para importar partidas",
            wildcard="Archivos Excel (*.xlsx)|*.xlsx",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        )
        if file_dlg.ShowModal() != wx.ID_OK:
            file_dlg.Destroy()
            return

        excel_path = file_dlg.GetPath()
        file_dlg.Destroy()

        # Paso 3: Extraer partidas
        wx.BeginBusyCursor()
        partidas = self._extractor.extract(excel_path)
        wx.EndBusyCursor()

        if not partidas:
            wx.MessageBox(
                f"No se encontraron partidas en el archivo:\n{os.path.basename(excel_path)}\n\n"
                "Asegúrate de que el Excel tiene partidas con el formato de la plantilla "
                "(número en col A, unidad en col B, descripción en col C, "
                "cantidad en col G, precio en col H).",
                "Sin partidas", wx.OK | wx.ICON_WARNING,
            )
            return

        # Paso 4: Mostrar resumen y confirmar
        resumen = f"Se encontraron {len(partidas)} partidas en el Excel:\n\n"
        for i, p in enumerate(partidas[:8]):
            resumen += f"  {i+1}. {p['concepto'][:50]} ({p['unidad']}, {p['precio_ref']:.2f}€)\n"
        if len(partidas) > 8:
            resumen += f"  ... y {len(partidas) - 8} más\n"
        resumen += f"\n¿Guardar como plantilla '{nombre}'?"

        confirm = wx.MessageBox(
            resumen,
            "Confirmar importación",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if confirm != wx.YES:
            return

        # Paso 5: Guardar plantilla
        plantilla = {
            'nombre': nombre,
            'categoria': 'personalizada',
            'descripcion': f"Plantilla importada desde {os.path.basename(excel_path)}",
            'contexto_ia': (
                f"Presupuesto de tipo '{nombre}'. "
                f"Partidas de referencia importadas de un presupuesto real. "
                f"Usar como base para generar partidas similares adaptadas al caso concreto."
            ),
            'partidas_base': partidas,
        }

        if self._catalog.add_custom(plantilla):
            wx.MessageBox(
                f"Plantilla '{nombre}' guardada con {len(partidas)} partidas.",
                "Plantilla creada", wx.OK | wx.ICON_INFORMATION,
            )
            self._refresh_list()

            # Seleccionar la nueva plantilla en la lista
            custom_names = self._catalog.get_custom_names()
            predefined_count = len(self._catalog.get_predefined_names())
            if nombre in custom_names:
                idx = predefined_count + custom_names.index(nombre)
                self._template_list.SetSelection(idx)
                self._on_select(None)
        else:
            wx.MessageBox(
                "Error al guardar la plantilla.",
                "Error", wx.OK | wx.ICON_ERROR,
            )

    def _on_delete(self, event):
        """Elimina la plantilla personalizada seleccionada."""
        sel = self._template_list.GetSelection()
        if sel == wx.NOT_FOUND:
            return

        display_name = self._template_list.GetString(sel)
        if not display_name.startswith("* "):
            wx.MessageBox(
                "Solo se pueden eliminar plantillas personalizadas.",
                "No permitido", wx.OK | wx.ICON_WARNING,
            )
            return

        nombre = display_name[2:]

        confirm = wx.MessageBox(
            f"¿Eliminar la plantilla personalizada '{nombre}'?\n\n"
            "Esta acción no se puede deshacer.",
            "Confirmar eliminación",
            wx.YES_NO | wx.ICON_WARNING,
        )
        if confirm != wx.YES:
            return

        if self._catalog.remove_custom(nombre):
            wx.MessageBox(
                f"Plantilla '{nombre}' eliminada.",
                "Eliminada", wx.OK | wx.ICON_INFORMATION,
            )
            self._refresh_list()
        else:
            wx.MessageBox(
                "Error al eliminar la plantilla.",
                "Error", wx.OK | wx.ICON_ERROR,
            )
