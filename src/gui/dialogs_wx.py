"""
Diálogos wxPython para cubiApp.
"""

import os

import wx

from src.core.project_parser import ProjectParser
from src.core import db_repository
from src.utils.project_name_generator import ProjectNameGenerator
from src.gui import theme


# ---------------------------------------------------------------------------
# Diálogos de confirmación / selección de comunidad (flujo presupuesto)
# ---------------------------------------------------------------------------

ID_BTN_NUEVA_COMUNIDAD = wx.NewIdRef()


def crear_comunidad_con_formulario(parent, nombre_prefill: str = "") -> dict | None:
    """Abre el formulario unificado de comunidad, crea la entidad y devuelve sus datos.

    Utiliza ComunidadFormDialog de db_manager_wx para que el formulario sea
    idéntico tanto en la gestión de BDD como en el flujo de creación de proyecto.
    """
    from src.gui.db_manager_wx import ComunidadFormDialog

    initial = {"nombre": nombre_prefill} if nombre_prefill else {}
    dlg = ComunidadFormDialog(parent, "Nueva Comunidad", initial=initial)
    result = None
    if dlg.ShowModal() == wx.ID_OK:
        vals = dlg.get_values()
        nombre = vals.get("nombre", "").strip()
        admin_id = vals.get("administracion_id")
        new_id, err = db_repository.create_comunidad(
            nombre, admin_id,
            cif=vals.get("cif", ""),
            direccion=vals.get("direccion", ""),
            email=vals.get("email", ""),
            telefono=vals.get("telefono", ""),
        )
        if err:
            wx.MessageBox(f"Error al crear la comunidad:\n{err}", "Error",
                          wx.OK | wx.ICON_ERROR)
        else:
            ct_ids = vals.get("contacto_ids", [])
            if ct_ids:
                db_repository.set_contactos_para_comunidad(new_id, ct_ids)
            result = {
                "id": new_id, "nombre": nombre,
                "cif": vals.get("cif", ""),
                "direccion": vals.get("direccion", ""),
                "email": vals.get("email", ""),
                "telefono": vals.get("telefono", ""),
                "administracion_id": admin_id,
            }
    dlg.Destroy()
    return result


class ComunidadConfirmDialog(wx.Dialog):
    """Diálogo que muestra los datos de una comunidad encontrada y pide confirmación."""

    def __init__(self, parent, comunidad_data: dict, nombre_buscado: str):
        super().__init__(parent, title="Comunidad encontrada",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        self._comunidad = comunidad_data
        self._nombre_buscado = nombre_buscado
        self._build_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = theme.create_title(panel, "Comunidad encontrada", "xl")
        sizer.Add(title, 0, wx.ALL, theme.SPACE_XL)

        msg = theme.create_text(
            panel,
            f'Se ha encontrado una comunidad con el nombre "{self._nombre_buscado}".\n'
            "¿Desea rellenar automáticamente los datos del presupuesto con esta información?"
        )
        msg.Wrap(440)
        sizer.Add(msg, 0, wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        sizer.AddSpacer(theme.SPACE_LG)

        grid = wx.FlexGridSizer(cols=2, vgap=6, hgap=12)
        grid.AddGrowableCol(1, 1)

        campos = [
            ("Nombre:", self._comunidad.get("nombre", "")),
            ("CIF:", self._comunidad.get("cif", "") or "(vacío)"),
            ("Correo:", self._comunidad.get("email", "") or "(vacío)"),
            ("Teléfono:", self._comunidad.get("telefono", "") or "(vacío)"),
            ("Dirección:", self._comunidad.get("direccion", "") or "(vacío)"),
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
        theme.fit_dialog(self, 580, 460)

    def get_comunidad_data(self) -> dict:
        return self._comunidad


class ComunidadFuzzySelectDialog(wx.Dialog):
    """Diálogo que muestra coincidencias fuzzy y permite al usuario elegir una comunidad."""

    def __init__(self, parent, resultados: list, nombre_buscado: str):
        super().__init__(parent, title="Coincidencias aproximadas",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        self._resultados = resultados
        self._nombre_buscado = nombre_buscado
        self._selected_comunidad = None
        self._build_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = theme.create_title(panel, "Coincidencias aproximadas", "xl")
        sizer.Add(title, 0, wx.ALL, theme.SPACE_XL)

        msg = theme.create_text(
            panel,
            f'No se encontró una comunidad exacta con "{self._nombre_buscado}", '
            "pero se encontraron las siguientes coincidencias.\n"
            "Seleccione una para rellenar los datos del presupuesto:"
        )
        msg.Wrap(520)
        sizer.Add(msg, 0, wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        sizer.AddSpacer(theme.SPACE_MD)

        self._list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self._list.SetFont(theme.font_base())
        self._list.InsertColumn(0, "Nombre", width=200)
        self._list.InsertColumn(1, "CIF", width=100)
        self._list.InsertColumn(2, "Correo", width=160)
        self._list.InsertColumn(3, "Similitud", width=80)

        for idx, com in enumerate(self._resultados):
            pos = self._list.InsertItem(idx, com.get("nombre", ""))
            self._list.SetItem(pos, 1, com.get("cif", "") or "")
            self._list.SetItem(pos, 2, com.get("email", "") or "")
            similitud_pct = f"{com.get('similitud', 0) * 100:.0f}%"
            self._list.SetItem(pos, 3, similitud_pct)

        if self._resultados:
            self._list.Select(0)

        sizer.Add(self._list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        sizer.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.ALL, theme.SPACE_XL)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_skip = wx.Button(panel, wx.ID_CANCEL, "Continuar sin datos", size=(170, 44))
        btn_skip.SetFont(theme.font_base())
        btn_new = wx.Button(panel, ID_BTN_NUEVA_COMUNIDAD, "Añadir nueva", size=(150, 44))
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
        theme.fit_dialog(self, 720, 500)

        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._on_nueva_comunidad, id=ID_BTN_NUEVA_COMUNIDAD)

    def _on_ok(self, event):
        sel = self._list.GetFirstSelected()
        if sel < 0:
            wx.MessageBox("Seleccione una comunidad de la lista.", "Aviso", wx.OK)
            return
        self._selected_comunidad = self._resultados[sel]
        self.EndModal(wx.ID_OK)

    def _on_nueva_comunidad(self, event):
        result = crear_comunidad_con_formulario(self, nombre_prefill=self._nombre_buscado)
        if result:
            self._selected_comunidad = result
            self.EndModal(wx.ID_OK)

    def get_comunidad_data(self) -> dict:
        return self._selected_comunidad


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
        theme.fit_dialog(self, 600, 560)
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


# ---------------------------------------------------------------------------
# Función compartida: obtener datos de proyecto (relación Excel → portapapeles)
# ---------------------------------------------------------------------------

def _find_budget_by_numero(budgets: list, numero: str):
    """Devuelve el primer dict de *budgets* cuyo ``numero`` coincida.

    El *numero* del dashboard suele tener formato ``NNN-YY`` (ej. ``16-25``),
    mientras que la relación solo contiene ``NNN`` (ej. ``16``).  Se intenta
    primero coincidencia exacta y después se compara solo la parte antes del
    guion.
    """
    target = numero.strip()
    if not target:
        return None

    for b in budgets:
        if str(b.get("numero", "")).strip() == target:
            return b

    base = target.split("-")[0].strip() if "-" in target else ""
    if base:
        for b in budgets:
            if str(b.get("numero", "")).strip() == base:
                return b

    return None


def _ask_use_matched_budget(parent, budget: dict) -> int:
    """Muestra un diálogo de confirmación con los datos del presupuesto
    encontrado y devuelve ``wx.YES``, ``wx.NO`` o ``wx.CANCEL``."""
    num = budget.get("numero", "")
    cliente = budget.get("cliente", "")
    calle = budget.get("calle", "")
    localidad = budget.get("localidad", "")
    tipo = budget.get("tipo", "")
    fecha = budget.get("fecha", "")
    importe = budget.get("importe", "")

    lines = [
        f"Nº: {num}",
        f"Cliente: {cliente}",
        f"Calle: {calle}",
        f"Localidad: {localidad}",
        f"Tipo: {tipo}",
        f"Fecha: {fecha}",
        f"Importe: {importe}",
    ]
    msg = (
        f"Se ha encontrado el presupuesto Nº {num} en la relación:\n\n"
        + "\n".join(lines)
        + "\n\n¿Desea regenerar los campos con estos datos?"
        "\n\n(Sí = usar estos datos · No = elegir otro · Cancelar = salir)"
    )
    return wx.MessageBox(
        msg,
        "Presupuesto encontrado",
        wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION,
        parent,
    )


def obtain_project_data(parent, preselect_numero: str = "") -> tuple:
    """Obtiene ``(project_data, project_name)`` usando primero el Excel de
    relación (si está configurado) y después el portapapeles como fallback.

    Si *preselect_numero* coincide con una entrada de la relación, se ofrece
    al usuario usarla directamente mediante un diálogo de confirmación.
    Si rechaza, se muestra la lista completa.

    Devuelve ``(None, None)`` si el usuario cancela.
    """
    from src.core.settings import Settings

    settings = Settings()
    relation_path = settings.get_default_path(Settings.PATH_RELATION_FILE)

    if relation_path and os.path.isfile(relation_path):
        try:
            from src.core.excel_relation_reader import ExcelRelationReader

            budgets, err = ExcelRelationReader().read(relation_path)
            if not err and budgets:
                # --- Atajo: coincidencia directa por número ---------------
                if preselect_numero:
                    match = _find_budget_by_numero(budgets, preselect_numero)
                    if match is not None:
                        result = _ask_use_matched_budget(parent, match)
                        if result == wx.YES:
                            gen = ProjectNameGenerator()
                            data = {k: v for k, v in match.items() if k != "importe"}
                            name = gen.generate_project_name(data)
                            return data, name
                        if result == wx.CANCEL:
                            return None, None
                        # wx.NO → sigue al selector completo

                sel_dlg = BudgetSelectorDialog(parent, budgets)
                result = sel_dlg.ShowModal()
                if result == wx.ID_OK:
                    data = sel_dlg.get_project_data()
                    name = sel_dlg.get_project_name()
                    sel_dlg.Destroy()
                    return data, name
                use_clipboard = sel_dlg.used_clipboard_fallback()
                sel_dlg.Destroy()
                if not use_clipboard:
                    return None, None
            elif err:
                wx.MessageBox(
                    f"No se pudo leer el Excel de relación:\n{err}\n\n"
                    "Se usará el portapapeles como alternativa.",
                    "Aviso", wx.OK | wx.ICON_WARNING,
                )
        except Exception as exc:
            wx.MessageBox(
                f"Error leyendo el Excel de relación:\n{exc}\n\n"
                "Se usará el portapapeles como alternativa.",
                "Aviso", wx.OK | wx.ICON_WARNING,
            )

    dlg = ProjectNameDialogWx(parent)
    if dlg.ShowModal() != wx.ID_OK:
        dlg.Destroy()
        return None, None
    project_data = dlg.get_project_data()
    project_name = dlg.get_project_name()
    dlg.Destroy()
    return project_data, project_name


# ---------------------------------------------------------------------------
# Selector de presupuesto desde Excel de relación
# ---------------------------------------------------------------------------

ID_BTN_CLIPBOARD_FALLBACK = wx.NewIdRef()


class BudgetSelectorDialog(wx.Dialog):
    """Muestra los presupuestos leídos del Excel de relación y permite elegir uno."""

    def __init__(self, parent, budgets: list, preselect_numero: str = ""):
        super().__init__(parent, title="Seleccionar Presupuesto",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        self._budgets = budgets
        self._filtered: list = list(budgets)
        self._preselect_numero = preselect_numero.strip()
        self.project_data = None
        self.project_name = None
        self._use_clipboard = False
        self.name_generator = ProjectNameGenerator()
        self._build_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = theme.create_title(panel, "Crear Presupuesto desde Relación", "xl")
        sizer.Add(title, 0, wx.ALL, theme.SPACE_XL)

        inst = theme.create_text(
            panel,
            "Selecciona un presupuesto de la lista o utiliza el portapapeles como alternativa."
        )
        inst.Wrap(680)
        sizer.Add(inst, 0, wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        # Campo de búsqueda
        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lbl_search = wx.StaticText(panel, label="Buscar:")
        lbl_search.SetFont(theme.get_font_medium())
        lbl_search.SetForegroundColour(theme.TEXT_PRIMARY)
        search_sizer.Add(lbl_search, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, theme.SPACE_SM)
        self._search = wx.TextCtrl(panel, size=(300, -1))
        theme.style_textctrl(self._search)
        self._search.Bind(wx.EVT_TEXT, self._on_filter)
        search_sizer.Add(self._search, 1, wx.EXPAND)
        sizer.Add(search_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_XL)

        # Lista
        self._list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        theme.style_listctrl(self._list)
        cols = [("Nº", 50), ("Fecha", 85), ("Cliente", 200), ("Calle", 200),
                ("Localidad", 100), ("Tipo", 160), ("Importe", 80)]
        for idx, (name, width) in enumerate(cols):
            self._list.InsertColumn(idx, name, width=width)
        self._populate_list(self._budgets)
        self._list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_item_activated)
        sizer.Add(self._list, 1, wx.EXPAND | wx.ALL, theme.SPACE_XL)

        # Separador
        sizer.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        # Botones
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancelar", size=(120, 44))
        btn_cancel.SetFont(theme.font_base())
        btn_clipboard = wx.Button(panel, ID_BTN_CLIPBOARD_FALLBACK,
                                  "Pegar desde portapapeles", size=(210, 44))
        btn_clipboard.SetFont(theme.font_base())
        btn_ok = wx.Button(panel, wx.ID_OK, "Crear presupuesto seleccionado", size=(240, 44))
        btn_ok.SetFont(theme.get_font_medium())
        btn_ok.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_ok.SetForegroundColour(theme.TEXT_INVERSE)
        btn_ok.SetDefault()

        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_clipboard, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_ok, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, theme.SPACE_XL)

        panel.SetSizer(sizer)
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)
        theme.fit_dialog(self, 920, 560)

        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)
        self.Bind(wx.EVT_BUTTON, self._on_clipboard, id=ID_BTN_CLIPBOARD_FALLBACK)

    # ── Populate / filter ─────────────────────────────────────────

    def _populate_list(self, items: list):
        self._list.DeleteAllItems()
        select_idx = -1
        for i, b in enumerate(items):
            pos = self._list.InsertItem(i, str(b.get("numero", "")))
            self._list.SetItem(pos, 1, b.get("fecha", ""))
            self._list.SetItem(pos, 2, b.get("cliente", ""))
            self._list.SetItem(pos, 3, b.get("calle", ""))
            self._list.SetItem(pos, 4, b.get("localidad", ""))
            self._list.SetItem(pos, 5, b.get("tipo", ""))
            self._list.SetItem(pos, 6, b.get("importe", ""))
            if (self._preselect_numero
                    and str(b.get("numero", "")).strip() == self._preselect_numero):
                select_idx = i
        if select_idx >= 0:
            self._list.Select(select_idx)
            self._list.EnsureVisible(select_idx)
            self._list.Focus(select_idx)

    def _on_filter(self, _event):
        query = self._search.GetValue().strip().lower()
        if not query:
            self._filtered = list(self._budgets)
        else:
            self._filtered = [
                b for b in self._budgets
                if query in " ".join(str(v) for v in b.values()).lower()
            ]
        self._populate_list(self._filtered)

    # ── Selección ─────────────────────────────────────────────────

    def _get_selected_budget(self):
        sel = self._list.GetFirstSelected()
        if sel < 0 or sel >= len(self._filtered):
            return None
        return self._filtered[sel]

    def _on_item_activated(self, _event):
        """Doble-clic en un item equivale a pulsar OK."""
        self._on_ok(None)

    def _on_ok(self, _event):
        budget = self._get_selected_budget()
        if budget is None:
            wx.MessageBox("Selecciona un presupuesto de la lista.", "Aviso", wx.OK)
            return
        self.project_data = {k: v for k, v in budget.items() if k != "importe"}
        self.project_name = self.name_generator.generate_project_name(self.project_data)
        self.EndModal(wx.ID_OK)

    def _on_clipboard(self, _event):
        self._use_clipboard = True
        self.EndModal(wx.ID_CANCEL)

    # ── Acceso público ────────────────────────────────────────────

    def used_clipboard_fallback(self) -> bool:
        return self._use_clipboard

    def get_project_data(self):
        return self.project_data

    def get_project_name(self):
        return self.project_name


# ---------------------------------------------------------------------------
# Diálogo de configuración de rutas por defecto
# ---------------------------------------------------------------------------

class DefaultPathsDialog(wx.Dialog):
    """Permite al usuario configurar las 3 rutas por defecto de la aplicación."""

    def __init__(self, parent):
        super().__init__(parent, title="Rutas por defecto",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        from src.core.settings import Settings
        self._settings = Settings()
        self._fields: dict = {}
        self._build_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = theme.create_title(panel, "Rutas por defecto", "xl")
        sizer.Add(title, 0, wx.ALL, theme.SPACE_XL)

        inst = theme.create_text(
            panel,
            "Configura las carpetas y archivos por defecto que se usarán "
            "al abrir y guardar presupuestos."
        )
        inst.Wrap(520)
        sizer.Add(inst, 0, wx.LEFT | wx.RIGHT, theme.SPACE_XL)
        sizer.AddSpacer(theme.SPACE_LG)

        from src.core.settings import Settings
        descriptions = [
            (Settings.PATH_SAVE_BUDGETS,
             "Carpeta para guardar presupuestos nuevos:", "dir"),
            (Settings.PATH_OPEN_BUDGETS,
             "Carpeta para abrir presupuestos existentes:", "dir"),
            (Settings.PATH_RELATION_FILE,
             "Archivo Excel de relación de presupuestos:", "file"),
        ]

        for key, label_text, mode in descriptions:
            lbl = wx.StaticText(panel, label=label_text)
            lbl.SetFont(theme.get_font_medium())
            lbl.SetForegroundColour(theme.TEXT_PRIMARY)
            sizer.Add(lbl, 0, wx.LEFT | wx.TOP, theme.SPACE_XL)

            row = wx.BoxSizer(wx.HORIZONTAL)
            tc = wx.TextCtrl(panel, style=wx.TE_READONLY, size=(-1, 32))
            tc.SetBackgroundColour(theme.BG_SECONDARY)
            tc.SetFont(theme.font_base())
            current = self._settings.get_default_path(key) or ""
            tc.SetValue(current)
            row.Add(tc, 1, wx.EXPAND | wx.RIGHT, theme.SPACE_SM)

            btn_browse = wx.Button(panel, label="Examinar...", size=(100, 32))
            btn_browse.SetFont(theme.font_base())
            btn_browse.Bind(wx.EVT_BUTTON,
                            lambda e, k=key, t=tc, m=mode: self._browse(k, t, m))
            row.Add(btn_browse, 0, wx.RIGHT, theme.SPACE_SM)

            btn_clear = wx.Button(panel, label="Limpiar", size=(80, 32))
            btn_clear.SetFont(theme.font_base())
            btn_clear.Bind(wx.EVT_BUTTON, lambda e, t=tc: t.SetValue(""))
            row.Add(btn_clear, 0)

            sizer.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_XL)
            self._fields[key] = tc

        sizer.AddSpacer(theme.SPACE_LG)
        sizer.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancelar", size=(130, 44))
        btn_cancel.SetFont(theme.font_base())
        btn_save = wx.Button(panel, wx.ID_OK, "Guardar", size=(130, 44))
        btn_save.SetFont(theme.get_font_medium())
        btn_save.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_save.SetForegroundColour(theme.TEXT_INVERSE)
        btn_save.SetDefault()
        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_save, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, theme.SPACE_XL)

        panel.SetSizer(sizer)
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)
        theme.fit_dialog(self, 620, 480)

        self.Bind(wx.EVT_BUTTON, self._on_save, id=wx.ID_OK)

    def _browse(self, key: str, textctrl: wx.TextCtrl, mode: str):
        if mode == "dir":
            dlg = wx.DirDialog(self, "Selecciona una carpeta",
                               defaultPath=textctrl.GetValue(),
                               style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST)
        else:
            dlg = wx.FileDialog(self, "Selecciona el archivo Excel",
                                defaultDir=os.path.dirname(textctrl.GetValue()) if textctrl.GetValue() else "",
                                wildcard="Archivos Excel (*.xlsx)|*.xlsx",
                                style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        if dlg.ShowModal() == wx.ID_OK:
            textctrl.SetValue(dlg.GetPath())
        dlg.Destroy()

    def _on_save(self, _event):
        from src.core.settings import Settings
        for key, tc in self._fields.items():
            self._settings.set_default_path(key, tc.GetValue())
        self.EndModal(wx.ID_OK)
