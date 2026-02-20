"""
Dashboard de presupuestos existentes (wxPython).

Muestra los presupuestos organizados por carpetas de estado (pestañas
dinámicas) a partir de la ruta configurada en PATH_OPEN_BUDGETS.
"""

import os
import subprocess
import sys

import wx

from src.core import folder_scanner
from src.core.project_data_resolver import build_relation_index, resolve_projects
from src.core.settings import Settings
from src.gui import theme
from src.utils.helpers import run_in_background

_COLUMNS = [
    ("Proyecto", 220),
    ("Cliente", 160),
    ("Localidad", 120),
    ("Tipo obra", 120),
    ("Fecha", 90),
    ("Total", 100),
]

_SEARCH_KEYS = ("nombre_proyecto", "cliente", "localidad", "tipo_obra", "numero")


class BudgetDashboardFrame(wx.Frame):
    """Ventana principal del dashboard de presupuestos."""

    def __init__(self, parent):
        super().__init__(
            parent,
            title="Presupuestos existentes",
            size=(1060, 650),
            style=wx.DEFAULT_FRAME_STYLE,
        )
        self._parent = parent
        self._settings = Settings()

        self._tab_data: dict[str, list[dict]] = {}
        self._tab_lists: dict[str, wx.ListCtrl] = {}
        self._tab_searches: dict[str, wx.TextCtrl] = {}
        self._state_names: list[str] = []
        self._relation_index: dict = {}

        self._build_ui()
        self.Centre()
        self._load_data()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        theme.style_frame(self)
        main_panel = wx.Panel(self)
        main_panel.SetBackgroundColour(theme.BG_PRIMARY)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Header ---
        header = wx.Panel(main_panel)
        header.SetBackgroundColour(theme.BG_PRIMARY)
        header_sizer = wx.BoxSizer(wx.VERTICAL)

        top_row = wx.BoxSizer(wx.HORIZONTAL)
        title = theme.create_title(header, "Presupuestos", "2xl")
        top_row.Add(title, 1, wx.ALIGN_CENTER_VERTICAL)

        btn_refresh = wx.Button(header, label="\u27F3 Actualizar", size=(-1, 36))
        btn_refresh.SetFont(theme.font_base())
        btn_refresh.SetBackgroundColour(theme.BG_CARD)
        btn_refresh.SetForegroundColour(theme.TEXT_PRIMARY)
        btn_refresh.SetToolTip("Recargar presupuestos desde las carpetas")
        btn_refresh.Bind(wx.EVT_BUTTON, lambda e: self._load_data())
        top_row.Add(btn_refresh, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, theme.SPACE_XL)

        header_sizer.Add(top_row, 0, wx.EXPAND | wx.LEFT | wx.TOP, theme.SPACE_XL)

        root_path = self._settings.get_default_path(Settings.PATH_OPEN_BUDGETS) or ""
        hint = root_path if root_path else "Ruta no configurada"
        subtitle = theme.create_text(header, hint, muted=True)
        header_sizer.Add(subtitle, 0, wx.LEFT | wx.TOP, theme.SPACE_XL)
        self._subtitle = subtitle
        header_sizer.AddSpacer(theme.SPACE_LG)

        header.SetSizer(header_sizer)
        main_sizer.Add(header, 0, wx.EXPAND)

        # --- Notebook (se rellena en _load_data) ---
        self._notebook = wx.Notebook(main_panel)
        self._notebook.SetBackgroundColour(theme.BG_SECONDARY)
        self._notebook.SetFont(theme.font_base())
        self._notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_tab_changed)
        main_sizer.Add(
            self._notebook, 1,
            wx.EXPAND | wx.LEFT | wx.RIGHT,
            theme.SPACE_LG,
        )

        # --- Toolbar ---
        toolbar = wx.Panel(main_panel)
        toolbar.SetBackgroundColour(theme.BG_SECONDARY)
        tb_sizer = wx.BoxSizer(wx.HORIZONTAL)
        tb_sizer.AddSpacer(theme.SPACE_LG)

        self._btn_preview = self._tb_button(toolbar, "Previsualizar", self._on_preview)
        self._btn_edit = self._tb_button(toolbar, "Editar \u25BC", self._on_edit_menu)
        self._btn_pdf = self._tb_button(toolbar, "Exportar PDF", self._on_export_pdf)
        self._btn_open = self._tb_button(toolbar, "Abrir Excel", self._on_open_excel, primary=True)
        self._btn_folder = self._tb_button(toolbar, "Abrir carpeta", self._on_open_folder)

        for btn in (self._btn_preview, self._btn_edit, self._btn_pdf,
                    self._btn_open, self._btn_folder):
            tb_sizer.Add(btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, theme.SPACE_SM)

        toolbar.SetSizer(tb_sizer)
        main_sizer.Add(toolbar, 0, wx.EXPAND | wx.ALL, theme.SPACE_LG)

        main_panel.SetSizer(main_sizer)
        self._update_buttons()

    @staticmethod
    def _tb_button(parent, label, handler, primary=False):
        btn = wx.Button(parent, label=label)
        btn.SetFont(theme.font_base())
        if primary:
            btn.SetBackgroundColour(theme.ACCENT_PRIMARY)
            btn.SetForegroundColour(theme.TEXT_INVERSE)
        btn.Bind(wx.EVT_BUTTON, handler)
        return btn

    # ------------------------------------------------------------------
    # Carga de datos
    # ------------------------------------------------------------------

    def _load_data(self):
        root_path = self._settings.get_default_path(Settings.PATH_OPEN_BUDGETS)
        if not root_path or not os.path.isdir(root_path):
            self._show_empty_state(
                "La ruta de presupuestos existentes no est\u00e1 configurada.\n\n"
                "Configura la ruta en Configuraci\u00f3n \u2192 Rutas por defecto."
            )
            return

        self._subtitle.SetLabel(root_path)
        self._show_empty_state("Cargando presupuestos\u2026")
        self._set_toolbar_enabled(False)

        def _scan():
            rel_index = build_relation_index()
            states = folder_scanner.scan_root(root_path)
            return rel_index, states

        def _on_done(ok, payload):
            self._set_toolbar_enabled(True)
            if not ok:
                self._show_empty_state(f"Error al cargar: {payload}")
                return
            rel_index, states = payload
            self._relation_index = rel_index
            if not states:
                self._show_empty_state(
                    "No se encontraron subcarpetas en:\n" + root_path
                )
                return
            self._rebuild_tabs(states, root_path)

        run_in_background(_scan, _on_done)

    def _set_toolbar_enabled(self, enabled):
        for btn in (self._btn_preview, self._btn_edit, self._btn_pdf,
                    self._btn_open, self._btn_folder):
            btn.Enable(enabled)

    def _rebuild_tabs(self, states, root_path):
        self._rebuilding = True
        self._notebook.Freeze()
        while self._notebook.GetPageCount():
            self._notebook.DeletePage(0)
        self._tab_data.clear()
        self._tab_lists.clear()
        self._tab_searches.clear()
        self._state_names = states

        for state_name in states:
            state_dir = os.path.join(root_path, state_name)
            scanned = folder_scanner.scan_projects(state_dir)
            resolved = resolve_projects(scanned, self._relation_index)
            self._tab_data[state_name] = resolved

            panel = wx.Panel(self._notebook)
            panel.SetBackgroundColour(theme.BG_PRIMARY)
            sizer = wx.BoxSizer(wx.VERTICAL)

            search_panel, search_ctrl = self._create_search_box(panel, state_name)
            sizer.Add(search_panel, 0, wx.EXPAND | wx.ALL, theme.SPACE_MD)
            self._tab_searches[state_name] = search_ctrl

            list_ctrl = wx.ListCtrl(
                panel,
                style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE,
            )
            theme.style_listctrl(list_ctrl)
            for i, (col_name, col_w) in enumerate(_COLUMNS):
                fmt = wx.LIST_FORMAT_RIGHT if col_name == "Total" else wx.LIST_FORMAT_LEFT
                list_ctrl.InsertColumn(i, col_name, fmt, col_w)

            list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_item_dblclick)
            list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_selection_changed)
            list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_selection_changed)
            sizer.Add(list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_LG)

            self._tab_lists[state_name] = list_ctrl

            panel.SetSizer(sizer)
            self._notebook.AddPage(panel, f"  {state_name}  ")

        self._rebuilding = False
        self._notebook.Thaw()

        for state_name in states:
            self._populate_list(state_name)

        self._update_buttons()

    def _show_empty_state(self, message):
        self._rebuilding = True
        self._notebook.Freeze()
        while self._notebook.GetPageCount():
            self._notebook.DeletePage(0)
        self._tab_data.clear()
        self._tab_lists.clear()
        self._tab_searches.clear()
        self._state_names = []

        panel = wx.Panel(self._notebook)
        panel.SetBackgroundColour(theme.BG_PRIMARY)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddStretchSpacer()
        lbl = wx.StaticText(panel, label=message, style=wx.ALIGN_CENTRE_HORIZONTAL)
        lbl.SetFont(theme.font_lg())
        lbl.SetForegroundColour(theme.TEXT_TERTIARY)
        sizer.Add(lbl, 0, wx.ALIGN_CENTER | wx.ALL, theme.SPACE_XL)
        sizer.AddStretchSpacer()
        panel.SetSizer(sizer)
        self._notebook.AddPage(panel, "  Sin datos  ")
        self._rebuilding = False
        self._notebook.Thaw()
        self._update_buttons()

    # ------------------------------------------------------------------
    # Búsqueda
    # ------------------------------------------------------------------

    def _create_search_box(self, parent, state_name):
        search_panel = wx.Panel(parent)
        search_panel.SetBackgroundColour(theme.BG_PRIMARY)
        sz = wx.BoxSizer(wx.HORIZONTAL)

        label = theme.create_text(search_panel, "Buscar:")
        sz.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, theme.SPACE_SM)

        search = wx.TextCtrl(search_panel, style=wx.TE_PROCESS_ENTER, size=(-1, 32))
        theme.style_textctrl(search)
        try:
            search.SetHint("Proyecto, cliente, localidad...")
        except AttributeError:
            pass
        search.Bind(wx.EVT_TEXT, lambda e, s=state_name: self._on_search(s))
        search.Bind(wx.EVT_TEXT_ENTER, lambda e, s=state_name: self._on_search(s))
        sz.Add(search, 1, wx.EXPAND)

        search_panel.SetSizer(sz)
        return search_panel, search

    def _on_search(self, state_name):
        self._populate_list(state_name)

    def _filter_rows(self, rows, query):
        q = (query or "").strip().lower()
        if not q:
            return rows
        out = []
        for r in rows:
            for k in _SEARCH_KEYS:
                v = str(r.get(k, "") or "").lower()
                if q in v:
                    out.append(r)
                    break
        return out

    # ------------------------------------------------------------------
    # Poblar lista
    # ------------------------------------------------------------------

    def _populate_list(self, state_name):
        list_ctrl = self._tab_lists.get(state_name)
        if list_ctrl is None:
            return
        rows = self._tab_data.get(state_name, [])
        search_ctrl = self._tab_searches.get(state_name)
        query = search_ctrl.GetValue() if search_ctrl else ""
        filtered = self._filter_rows(rows, query)

        list_ctrl.DeleteAllItems()
        for i, proj in enumerate(filtered):
            has_excel = bool(proj.get("ruta_excel")) and os.path.exists(proj.get("ruta_excel", ""))
            nombre = proj.get("nombre_proyecto", "")
            if not has_excel:
                nombre = f"\u26A0 {nombre}"

            idx = list_ctrl.InsertItem(i, nombre)
            list_ctrl.SetItem(idx, 1, proj.get("cliente", ""))
            list_ctrl.SetItem(idx, 2, proj.get("localidad", ""))
            list_ctrl.SetItem(idx, 3, proj.get("tipo_obra", ""))

            fecha_raw = proj.get("fecha", "")
            list_ctrl.SetItem(idx, 4, fecha_raw)

            total = proj.get("total")
            if total is not None:
                try:
                    t = f"{float(total):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    list_ctrl.SetItem(idx, 5, f"{t} \u20AC")
                except (ValueError, TypeError):
                    pass

            if not has_excel:
                list_ctrl.SetItemTextColour(idx, theme.TEXT_TERTIARY)

        self._update_buttons()

    # ------------------------------------------------------------------
    # Selección y helpers
    # ------------------------------------------------------------------

    def _current_state(self):
        page = self._notebook.GetSelection()
        if page < 0 or page >= len(self._state_names):
            return None
        return self._state_names[page]

    def _get_selected(self):
        state = self._current_state()
        if state is None:
            return None
        list_ctrl = self._tab_lists.get(state)
        if list_ctrl is None:
            return None
        idx = list_ctrl.GetFirstSelected()
        if idx < 0:
            return None

        search_ctrl = self._tab_searches.get(state)
        query = search_ctrl.GetValue() if search_ctrl else ""
        visible = self._filter_rows(self._tab_data.get(state, []), query)
        if idx >= len(visible):
            return None
        return visible[idx]

    def _on_selection_changed(self, event):
        self._update_buttons()
        event.Skip()

    def _on_tab_changed(self, event):
        if not getattr(self, "_rebuilding", False):
            self._update_buttons()
        event.Skip()

    def _update_buttons(self):
        selected = self._get_selected()
        has_sel = selected is not None
        file_ok = has_sel and os.path.exists(selected.get("ruta_excel", ""))
        for btn in (self._btn_preview, self._btn_edit, self._btn_pdf,
                    self._btn_open, self._btn_folder):
            btn.Enable(has_sel)
        if has_sel and not file_ok:
            self._btn_preview.Enable(False)
            self._btn_edit.Enable(False)
            self._btn_pdf.Enable(False)
            self._btn_open.Enable(False)

    def _on_item_dblclick(self, event):
        self._on_preview(event)

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _on_preview(self, event):
        selected = self._get_selected()
        if not selected:
            return
        ruta = os.path.normpath(selected.get("ruta_excel", ""))
        if not os.path.exists(ruta):
            wx.MessageBox(
                f"El archivo ya no existe:\n{ruta}",
                "Error", wx.OK | wx.ICON_WARNING,
            )
            return
        from src.gui.budget_preview_dialog_wx import BudgetPreviewDialog
        dlg = BudgetPreviewDialog(self, ruta)
        dlg.ShowModal()
        dlg.Destroy()

    def _on_edit_menu(self, event):
        selected = self._get_selected()
        if not selected:
            return
        ruta = os.path.normpath(selected.get("ruta_excel", ""))
        if not os.path.exists(ruta):
            wx.MessageBox(
                f"El archivo ya no existe:\n{ruta}",
                "Error", wx.OK | wx.ICON_WARNING,
            )
            return

        menu = wx.Menu()
        id_regen = wx.NewIdRef()
        id_add = wx.NewIdRef()
        id_header = wx.NewIdRef()

        menu.Append(id_regen, "Regenerar todas las partidas (IA)")
        menu.Append(id_add, "A\u00f1adir m\u00e1s partidas (IA)")
        menu.AppendSeparator()
        menu.Append(id_header, "Regenerar campos del presupuesto")

        self.Bind(wx.EVT_MENU, lambda e: self._edit_regen_all(ruta), id=id_regen)
        self.Bind(wx.EVT_MENU, lambda e: self._edit_add_partidas(ruta), id=id_add)
        numero = selected.get("numero", "")
        self.Bind(wx.EVT_MENU, lambda e: self._edit_regen_header(ruta, numero), id=id_header)

        self._btn_edit.PopupMenu(menu)
        menu.Destroy()

    def _on_export_pdf(self, event):
        selected = self._get_selected()
        if not selected:
            return
        ruta = os.path.normpath(selected.get("ruta_excel", ""))
        if not os.path.exists(ruta):
            wx.MessageBox(
                f"El archivo ya no existe:\n{ruta}",
                "Error", wx.OK | wx.ICON_WARNING,
            )
            return
        from src.core.pdf_exporter import PDFExporter
        exporter = PDFExporter()
        if not exporter.is_available():
            wx.MessageBox(
                "Microsoft Excel no est\u00e1 disponible.\n"
                "Para exportar a PDF se necesita Excel instalado.",
                "Exportar PDF", wx.OK | wx.ICON_WARNING,
            )
            return

        self._btn_pdf.Disable()
        self._btn_pdf.SetLabel("Exportando\u2026")

        def _on_pdf_done(ok_outer, payload):
            self._btn_pdf.Enable()
            self._btn_pdf.SetLabel("Exportar PDF")
            if not ok_outer:
                wx.MessageBox(f"Error al exportar PDF:\n{payload}", "Error", wx.OK | wx.ICON_ERROR)
                return
            ok, result = payload
            if ok:
                resp = wx.MessageBox(
                    f"PDF generado:\n{result}\n\n\u00bfDesea abrirlo?",
                    "PDF exportado", wx.YES_NO | wx.ICON_INFORMATION,
                )
                if resp == wx.YES:
                    self._open_file(result)
            else:
                wx.MessageBox(f"Error al exportar PDF:\n{result}", "Error", wx.OK | wx.ICON_ERROR)

        run_in_background(lambda: exporter.export(ruta), _on_pdf_done)

    def _on_open_excel(self, event):
        selected = self._get_selected()
        if not selected:
            return
        ruta = os.path.normpath(selected.get("ruta_excel", ""))
        if not os.path.exists(ruta):
            wx.MessageBox(
                f"El archivo ya no existe:\n{ruta}",
                "Error", wx.OK | wx.ICON_WARNING,
            )
            return
        self._open_file(ruta)

    def _on_open_folder(self, event):
        selected = self._get_selected()
        if not selected:
            return
        folder = selected.get("ruta_carpeta", "")
        if not folder or not os.path.isdir(folder):
            ruta = selected.get("ruta_excel", "")
            folder = os.path.dirname(ruta) if ruta else ""
        if folder and os.path.isdir(folder):
            self._open_file(folder)
        else:
            wx.MessageBox("No se encontr\u00f3 la carpeta.", "Error", wx.OK | wx.ICON_WARNING)

    # ------------------------------------------------------------------
    # Edición
    # ------------------------------------------------------------------

    def _edit_regen_all(self, ruta):
        confirm = wx.MessageBox(
            "Esta acción reemplazará TODAS las partidas actuales del presupuesto "
            "por las que genere la IA.\n\n¿Desea continuar?",
            "Regenerar partidas",
            wx.YES_NO | wx.ICON_WARNING,
        )
        if confirm != wx.YES:
            return

        from src.gui.ai_budget_dialog_wx import AIBudgetDialog
        from src.gui.partidas_dialog_wx import SuggestedPartidasDialog
        from src.core.excel_manager import ExcelManager

        ai_dlg = AIBudgetDialog(self)
        if ai_dlg.ShowModal() != wx.ID_OK:
            ai_dlg.Destroy()
            return
        result = ai_dlg.get_result()
        ai_dlg.Destroy()
        if not result or not result.get("partidas"):
            wx.MessageBox("No se generaron partidas.", "Aviso", wx.OK)
            return

        partidas_dlg = SuggestedPartidasDialog(self, result)
        if partidas_dlg.ShowModal() != wx.ID_OK:
            partidas_dlg.Destroy()
            return
        selected_partidas = partidas_dlg.get_selected_partidas()
        partidas_dlg.Destroy()

        if not selected_partidas:
            return

        em = ExcelManager()
        if em.insert_partidas_via_xml(ruta, selected_partidas):
            wx.MessageBox(
                f"Partidas regeneradas ({len(selected_partidas)}).",
                "\u00c9xito", wx.OK,
            )
            self._load_data()
        else:
            wx.MessageBox("Error al insertar partidas.", "Error", wx.OK | wx.ICON_ERROR)

    def _edit_add_partidas(self, ruta):
        from src.core.budget_reader import BudgetReader
        from src.gui.ai_budget_dialog_wx import AIBudgetDialog
        from src.gui.partidas_dialog_wx import SuggestedPartidasDialog
        from src.core.excel_manager import ExcelManager

        reader = BudgetReader()
        existing = reader.read(ruta)
        existing_partidas = existing["partidas"] if existing else []

        context = ""
        if existing_partidas:
            conceptos = [p["concepto"] for p in existing_partidas]
            context = (
                f"Ya existen {len(existing_partidas)} partidas: "
                + ", ".join(conceptos[:10])
                + (". " if len(conceptos) <= 10 else "... ")
                + "Genera partidas ADICIONALES que complementen las existentes."
            )

        ai_dlg = AIBudgetDialog(self, context_extra=context)
        if ai_dlg.ShowModal() != wx.ID_OK:
            ai_dlg.Destroy()
            return
        result = ai_dlg.get_result()
        ai_dlg.Destroy()
        if not result or not result.get("partidas"):
            wx.MessageBox("No se generaron partidas.", "Aviso", wx.OK)
            return

        partidas_dlg = SuggestedPartidasDialog(self, result)
        if partidas_dlg.ShowModal() != wx.ID_OK:
            partidas_dlg.Destroy()
            return
        selected_partidas = partidas_dlg.get_selected_partidas()
        partidas_dlg.Destroy()

        if not selected_partidas:
            return

        em = ExcelManager()
        if em.append_partidas_via_xml(ruta, selected_partidas):
            wx.MessageBox(
                f"{len(selected_partidas)} partidas a\u00f1adidas.",
                "\u00c9xito", wx.OK,
            )
            self._load_data()
        else:
            wx.MessageBox("Error al a\u00f1adir partidas.", "Error", wx.OK | wx.ICON_ERROR)

    def _edit_regen_header(self, ruta, numero_proyecto=""):
        confirm = wx.MessageBox(
            "Esta acción sobrescribirá los campos de cabecera del presupuesto "
            "(cliente, dirección, fecha, etc.).\n\n¿Desea continuar?",
            "Regenerar campos",
            wx.YES_NO | wx.ICON_WARNING,
        )
        if confirm != wx.YES:
            return

        from src.core.excel_manager import ExcelManager

        project_data, project_name = self._obtain_project_data(preselect_numero=numero_proyecto)
        if not project_data:
            return

        comunidad_data = None
        if hasattr(self._parent, "_buscar_comunidad_para_presupuesto"):
            comunidad_data = self._parent._buscar_comunidad_para_presupuesto(
                project_data.get("cliente", "")
            )

        excel_data = {
            "nombre_obra": project_name or "",
            "numero_proyecto": project_data.get("numero", ""),
            "fecha": project_data.get("fecha", ""),
            "cliente": project_data.get("cliente", ""),
            "calle": project_data.get("calle", ""),
            "num_calle": project_data.get("num_calle", ""),
            "codigo_postal": project_data.get("codigo_postal", ""),
            "tipo": project_data.get("tipo", ""),
            "admin_cif": comunidad_data.get("cif", "") if comunidad_data else "",
            "admin_email": comunidad_data.get("email", "") if comunidad_data else "",
            "admin_telefono": comunidad_data.get("telefono", "") if comunidad_data else "",
        }

        em = ExcelManager()
        if em.update_header_fields(ruta, excel_data):
            wx.MessageBox("Campos actualizados.", "\u00c9xito", wx.OK)
            self._load_data()
        else:
            wx.MessageBox("Error al actualizar campos.", "Error", wx.OK | wx.ICON_ERROR)

    # ------------------------------------------------------------------
    # Obtención de datos de proyecto (relación Excel o portapapeles)
    # ------------------------------------------------------------------

    def _obtain_project_data(self, preselect_numero=""):
        from src.gui.dialogs_wx import obtain_project_data
        return obtain_project_data(self, preselect_numero=preselect_numero)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _open_file(path):
        path = os.path.normpath(path)
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", path], check=True)
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.run(["xdg-open", path], check=True)
        except Exception as exc:
            wx.MessageBox(
                f"No se pudo abrir:\n{path}\n\nError: {exc}",
                "Error al abrir", wx.OK | wx.ICON_ERROR,
            )
