"""
Diálogo para configurar la generación de partidas con IA.

Permite al usuario:
- Escribir el tipo de obra (texto libre)
- Añadir una descripción adicional para dar contexto a la IA
- Opcionalmente seleccionar una plantilla predefinida como referencia
- Generar partidas con IA o saltar el paso
"""

import wx
import threading

from src.core.work_type_catalog import WorkTypeCatalog
from src.core.budget_generator import BudgetGenerator
from src.core.prompt_builder import PromptBuilder
from src.core.settings import Settings
from src.gui import theme


class AIBudgetDialog(wx.Dialog):
    """Diálogo para configurar y lanzar la generación de partidas con IA."""

    def __init__(self, parent, datos_proyecto=None):
        """
        Args:
            parent: Ventana padre.
            datos_proyecto: Diccionario con datos del proyecto (localidad, cliente, etc.).
        """
        super().__init__(
            parent,
            title="Generar Partidas con IA",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        theme.style_dialog(self)

        self._datos_proyecto = datos_proyecto or {}
        self._catalog = WorkTypeCatalog()
        self._settings = Settings()
        self._selected_plantilla = None
        self._result = None  # Resultado de la generación

        self._build_ui()
        self.CenterOnParent()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Título ---
        title = theme.create_title(panel, "Generar Partidas con IA", "xl")
        main_sizer.Add(title, 0, wx.LEFT | wx.TOP | wx.RIGHT, theme.SPACE_XL)

        subtitle = theme.create_text(
            panel,
            "Describe el tipo de obra y la IA generará las partidas del presupuesto "
            "con precios orientativos. Opcionalmente selecciona una plantilla de referencia."
        )
        subtitle.Wrap(580)
        main_sizer.Add(subtitle, 0, wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_MD)

        main_sizer.AddSpacer(theme.SPACE_MD)

        # --- Tipo de obra ---
        lbl_tipo = wx.StaticText(panel, label="Tipo de obra:")
        lbl_tipo.SetFont(theme.get_font_medium())
        lbl_tipo.SetForegroundColour(theme.TEXT_PRIMARY)
        main_sizer.Add(lbl_tipo, 0, wx.LEFT, theme.SPACE_XL)

        self._tipo_text = wx.TextCtrl(panel, size=(-1, 32))
        theme.style_textctrl(self._tipo_text)
        try:
            self._tipo_text.SetHint("Ej: Reparación de bajante comunitaria, Reforma integral cocina...")
        except AttributeError:
            pass
        main_sizer.Add(self._tipo_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_SM)

        main_sizer.AddSpacer(theme.SPACE_SM)

        # --- Descripción adicional ---
        lbl_desc = wx.StaticText(panel, label="Descripción adicional (contexto para la IA):")
        lbl_desc.SetFont(theme.get_font_medium())
        lbl_desc.SetForegroundColour(theme.TEXT_PRIMARY)
        main_sizer.Add(lbl_desc, 0, wx.LEFT, theme.SPACE_XL)

        self._desc_text = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 64))
        theme.style_textctrl(self._desc_text)
        try:
            self._desc_text.SetHint(
                "Ej: Bajante de PVC en patio interior, edificio 4 plantas, "
                "acceso difícil por estrechez del patio..."
            )
        except AttributeError:
            pass
        main_sizer.Add(self._desc_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_SM)

        main_sizer.AddSpacer(theme.SPACE_SM)

        # --- Plantilla de referencia (opcional) ---
        lbl_plantilla = wx.StaticText(panel, label="Plantilla de referencia (opcional):")
        lbl_plantilla.SetFont(theme.get_font_medium())
        lbl_plantilla.SetForegroundColour(theme.TEXT_PRIMARY)
        main_sizer.Add(lbl_plantilla, 0, wx.LEFT, theme.SPACE_XL)

        plantilla_hint = theme.create_text(
            panel,
            "Si seleccionas una, la IA la usará como base para generar partidas más precisas.",
            muted=True,
        )
        main_sizer.Add(plantilla_hint, 0, wx.LEFT | wx.TOP, theme.SPACE_SM)

        # Lista de plantillas
        names = self._catalog.get_all_names()
        self._plantilla_list = wx.ListBox(
            panel,
            choices=["(Ninguna - generar desde cero)"] + names,
            size=(-1, 100),
        )
        self._plantilla_list.SetSelection(0)  # "Ninguna" por defecto
        self._plantilla_list.SetFont(theme.font_base())
        self._plantilla_list.SetBackgroundColour(theme.BG_CARD)
        main_sizer.Add(
            self._plantilla_list, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_SM
        )

        # --- Botón vista previa del prompt ---
        btn_preview = wx.Button(panel, label="Ver prompt que se enviará", size=(220, 30))
        btn_preview.SetFont(theme.font_sm())
        btn_preview.SetForegroundColour(theme.TEXT_SECONDARY)
        btn_preview.Bind(wx.EVT_BUTTON, self._on_preview_prompt)
        main_sizer.Add(btn_preview, 0, wx.LEFT | wx.TOP, theme.SPACE_SM)

        # --- Aviso API key ---
        if not self._settings.has_api_key():
            warning_sizer = wx.BoxSizer(wx.HORIZONTAL)
            warning_icon = wx.StaticText(panel, label="⚠")
            warning_icon.SetForegroundColour(theme.WARNING)
            warning_icon.SetFont(theme.font_lg())
            warning_sizer.Add(warning_icon, 0, wx.RIGHT, theme.SPACE_SM)

            warning_text = theme.create_text(
                panel,
                "No hay API key configurada. Solo se podrán usar plantillas offline.",
            )
            warning_text.SetForegroundColour(theme.WARNING)
            warning_sizer.Add(warning_text, 1, wx.ALIGN_CENTER_VERTICAL)

            main_sizer.AddSpacer(theme.SPACE_SM)
            main_sizer.Add(warning_sizer, 0, wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        # --- Separador ---
        main_sizer.AddSpacer(theme.SPACE_MD)
        main_sizer.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)
        main_sizer.AddSpacer(theme.SPACE_MD)

        # --- Botones ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        btn_skip = wx.Button(panel, wx.ID_CANCEL, "Saltar", size=(120, 44))
        btn_skip.SetFont(theme.font_base())
        btn_skip.SetToolTip("Crear presupuesto vacío sin partidas IA")

        self._btn_generate = wx.Button(panel, wx.ID_OK, "Generar partidas con IA", size=(220, 44))
        self._btn_generate.SetFont(theme.get_font_medium())
        self._btn_generate.SetBackgroundColour(theme.ACCENT_PRIMARY)
        self._btn_generate.SetForegroundColour(theme.TEXT_INVERSE)
        self._btn_generate.SetDefault()

        btn_sizer.Add(btn_skip, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(self._btn_generate, 0)

        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, theme.SPACE_XL)

        panel.SetSizer(main_sizer)

        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)

        self.Fit()
        w, h = self.GetSize()
        w = max(w, 650)
        h = max(h, 580)
        display = wx.Display(wx.Display.GetFromWindow(self) if wx.Display.GetFromWindow(self) >= 0 else 0)
        screen_w, screen_h = display.GetClientArea().GetSize()
        w = min(w, screen_w - 40)
        h = min(h, screen_h - 40)
        self.SetSize((w, h))
        self.SetMinSize((650, 500))

        # Eventos
        self.Bind(wx.EVT_BUTTON, self._on_generate, id=wx.ID_OK)

    def _on_preview_prompt(self, event):
        """Muestra una vista previa del prompt que se enviará a la IA."""
        tipo = self._tipo_text.GetValue().strip()
        descripcion = self._desc_text.GetValue().strip()

        if not tipo:
            wx.MessageBox(
                "Escribe el tipo de obra para ver el prompt.",
                "Campo obligatorio", wx.OK | wx.ICON_WARNING,
            )
            return

        # Obtener plantilla seleccionada
        sel_idx = self._plantilla_list.GetSelection()
        plantilla = None
        if sel_idx > 0:
            nombre = self._plantilla_list.GetString(sel_idx)
            plantilla = self._catalog.get_by_name(nombre)

        # Construir prompt
        builder = PromptBuilder()
        prompt = builder.build_prompt(
            tipo_obra=tipo,
            descripcion=descripcion,
            plantilla=plantilla,
            datos_proyecto=self._datos_proyecto,
        )

        # Mostrar en diálogo de solo lectura
        dlg = wx.Dialog(
            self, title="Prompt para la IA", size=(600, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        theme.style_dialog(dlg)

        panel = wx.Panel(dlg)
        theme.style_panel(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        lbl = theme.create_title(panel, "Prompt completo", "xl")
        sizer.Add(lbl, 0, wx.ALL, theme.SPACE_LG)

        text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY,
            size=(-1, -1),
        )
        theme.style_textctrl(text)
        text.SetValue(prompt)
        sizer.Add(text, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_LG)

        info = theme.create_text(
            panel,
            f"Longitud: {len(prompt)} caracteres",
            muted=True,
        )
        sizer.Add(info, 0, wx.LEFT | wx.TOP, theme.SPACE_SM)

        btn_close = wx.Button(panel, wx.ID_CLOSE, "Cerrar", size=(100, 36))
        btn_close.SetFont(theme.font_base())
        sizer.Add(btn_close, 0, wx.ALIGN_RIGHT | wx.ALL, theme.SPACE_LG)

        panel.SetSizer(sizer)

        dlg_sizer = wx.BoxSizer(wx.VERTICAL)
        dlg_sizer.Add(panel, 1, wx.EXPAND)
        dlg.SetSizer(dlg_sizer)
        dlg.SetMinSize((400, 300))

        dlg.Bind(wx.EVT_BUTTON, lambda e: dlg.EndModal(wx.ID_CLOSE), id=wx.ID_CLOSE)
        dlg.CenterOnParent()
        dlg.ShowModal()
        dlg.Destroy()

    def _on_generate(self, event):
        """Valida y lanza la generación de partidas."""
        tipo = self._tipo_text.GetValue().strip()
        if not tipo:
            wx.MessageBox(
                "Por favor, escribe el tipo de obra.",
                "Campo obligatorio",
                wx.OK | wx.ICON_WARNING,
            )
            return

        descripcion = self._desc_text.GetValue().strip()

        # Obtener plantilla seleccionada (si no es "Ninguna")
        sel_idx = self._plantilla_list.GetSelection()
        if sel_idx > 0:
            nombre = self._plantilla_list.GetString(sel_idx)
            self._selected_plantilla = self._catalog.get_by_name(nombre)
        else:
            self._selected_plantilla = None

        # Generar partidas
        self._btn_generate.Disable()
        self._btn_generate.SetLabel("Generando...")

        # Ejecutar en hilo para no bloquear la UI
        thread = threading.Thread(
            target=self._run_generation,
            args=(tipo, descripcion),
            daemon=True,
        )
        thread.start()

    def _run_generation(self, tipo, descripcion):
        """Ejecuta la generación en un hilo separado."""
        api_key = self._settings.get_api_key()
        generator = BudgetGenerator(api_key=api_key)

        result = generator.generate(
            tipo_obra=tipo,
            descripcion=descripcion,
            plantilla=self._selected_plantilla,
            datos_proyecto=self._datos_proyecto,
        )

        # Volver al hilo principal de la UI
        wx.CallAfter(self._on_generation_complete, result)

    def _on_generation_complete(self, result):
        """Callback cuando la generación termina."""
        self._result = result
        self._btn_generate.Enable()
        self._btn_generate.SetLabel("Generar partidas con IA")

        source = result.get('source', 'error')

        # Caso 1: Error total - sin partidas
        if source == 'error' or (result['error'] and not result['partidas']):
            wx.MessageBox(
                f"No se pudieron generar partidas:\n\n{result['error']}",
                "Error de generación",
                wx.OK | wx.ICON_WARNING,
            )
            return

        # Caso 2: Fallback offline - avisar al usuario y preguntar
        if source == 'offline':
            confirm = wx.MessageBox(
                "La IA no está disponible en este momento (cuota agotada o sin conexión).\n\n"
                "Se han cargado las partidas base de la plantilla seleccionada "
                "como punto de partida. Estas partidas NO han sido adaptadas por la IA "
                "a tu descripción específica.\n\n"
                "¿Quieres usar estas partidas base como referencia?\n"
                "(Podrás editarlas manualmente en el siguiente paso)",
                "Modo offline - Partidas de plantilla",
                wx.YES_NO | wx.ICON_INFORMATION,
            )
            if confirm != wx.YES:
                self._result = None
                return
            self.EndModal(wx.ID_OK)
            return

        # Caso 3: Generadas por IA correctamente
        self.EndModal(wx.ID_OK)

    def get_result(self):
        """Devuelve el resultado de la generación."""
        return self._result
