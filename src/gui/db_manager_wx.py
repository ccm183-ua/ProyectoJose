"""
Ventana de gestión de la base de datos (wxPython).
"""

import wx
from src.core import db_repository as repo
from src.gui import theme


# ---------------------------------------------------------------------------
# Popups reutilizables para ComboCtrl
# ---------------------------------------------------------------------------

class SearchSelectPopup(wx.ComboPopup):
    """Popup con SearchCtrl + ListBox para selección simple (ej: administración).

    El popup tiene su propio buscador interno para que el foco quede siempre
    dentro del popup. El ComboCtrl muestra el nombre del elemento seleccionado.
    """

    def __init__(self):
        super().__init__()
        self._items = []
        self._visible = []
        self._selected_id = None
        self._panel = None
        self._search = None
        self._list = None

    def Create(self, parent):
        self._panel = wx.Panel(parent)
        self._panel.SetBackgroundColour(wx.WHITE)
        sz = wx.BoxSizer(wx.VERTICAL)

        self._search = wx.SearchCtrl(self._panel, size=(-1, 28))
        self._search.SetDescriptiveText("Buscar...")
        self._search.ShowCancelButton(True)
        self._search.Bind(wx.EVT_TEXT, lambda e: self._filter())
        self._search.Bind(wx.EVT_SEARCHCTRL_CANCEL_BTN,
                          lambda e: (self._search.SetValue(""), self._filter()))
        sz.Add(self._search, 0, wx.EXPAND | wx.ALL, 4)

        self._list = wx.ListBox(self._panel, style=wx.LB_SINGLE)
        self._list.Bind(wx.EVT_LISTBOX_DCLICK, self._on_dclick)
        self._list.Bind(wx.EVT_LEFT_UP, self._on_click)
        sz.Add(self._list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 4)

        self._panel.SetSizer(sz)
        return True

    def GetControl(self):
        return self._panel

    def GetStringValue(self):
        for id_, disp in self._items:
            if id_ == self._selected_id:
                return disp
        return ""

    def SetStringValue(self, val):
        for id_, disp in self._items:
            if disp == val:
                self._selected_id = id_
                break

    def GetAdjustedSize(self, minWidth, prefHeight, maxHeight):
        count = min(len(self._visible) if self._visible else len(self._items), 10)
        h = max(count * 22 + 50, 120)
        return wx.Size(max(minWidth, 300), min(h, maxHeight))

    def OnPopup(self):
        self._search.SetFocus()
        self._filter()

    def OnDismiss(self):
        combo = self.GetComboCtrl()
        if combo:
            combo.SetValue(self.GetStringValue())

    def _filter(self):
        self._list.Clear()
        self._visible = []
        q = self._search.GetValue().strip().lower() if self._search else ""
        for id_, disp in self._items:
            if q and q not in disp.lower():
                continue
            self._visible.append((id_, disp))
            self._list.Append(disp)
        if self._selected_id:
            for i, (id_, _) in enumerate(self._visible):
                if id_ == self._selected_id:
                    self._list.SetSelection(i)
                    break

    def _on_click(self, event):
        idx = self._list.GetSelection()
        if 0 <= idx < len(self._visible):
            self._selected_id = self._visible[idx][0]
            self.Dismiss()
        event.Skip()

    def _on_dclick(self, event):
        idx = self._list.GetSelection()
        if 0 <= idx < len(self._visible):
            self._selected_id = self._visible[idx][0]
            self.Dismiss()

    def set_items(self, items):
        self._items = list(items)

    def get_selected_id(self):
        return self._selected_id

    def set_selected_id(self, id_):
        self._selected_id = id_


class CheckSelectPopup(wx.ComboPopup):
    """Popup con SearchCtrl + CheckListBox para selección múltiple (ej: contactos).

    El ComboCtrl muestra un texto resumen ("N contactos seleccionados").
    El popup tiene su propio buscador interno.
    """

    def __init__(self):
        super().__init__()
        self._items = []
        self._visible = []
        self._selected_ids = set()
        self._panel = None
        self._search = None
        self._checklist = None

    def Create(self, parent):
        self._panel = wx.Panel(parent)
        self._panel.SetBackgroundColour(wx.WHITE)
        sz = wx.BoxSizer(wx.VERTICAL)

        self._search = wx.SearchCtrl(self._panel, size=(-1, 28))
        self._search.SetDescriptiveText("Buscar...")
        self._search.ShowCancelButton(True)
        self._search.Bind(wx.EVT_TEXT, lambda e: self._filter())
        self._search.Bind(wx.EVT_SEARCHCTRL_CANCEL_BTN,
                          lambda e: (self._search.SetValue(""), self._filter()))
        sz.Add(self._search, 0, wx.EXPAND | wx.ALL, 4)

        self._checklist = wx.CheckListBox(self._panel)
        self._checklist.Bind(wx.EVT_CHECKLISTBOX, self._on_check)
        sz.Add(self._checklist, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 4)

        self._panel.SetSizer(sz)
        return True

    def GetControl(self):
        return self._panel

    def GetStringValue(self):
        n = len(self._selected_ids)
        if n == 0:
            return "Seleccionar contactos..."
        if n == 1:
            for id_, disp in self._items:
                if id_ in self._selected_ids:
                    return disp
        return f"{n} contactos seleccionados"

    def SetStringValue(self, val):
        pass

    def GetAdjustedSize(self, minWidth, prefHeight, maxHeight):
        count = min(len(self._items), 8)
        h = max(count * 22 + 50, 160)
        return wx.Size(max(minWidth, 320), min(h, maxHeight))

    def OnPopup(self):
        self._search.SetFocus()
        self._filter()

    def OnDismiss(self):
        combo = self.GetComboCtrl()
        if combo:
            combo.SetValue(self.GetStringValue())

    def _filter(self):
        self._checklist.Clear()
        self._visible = []
        q = self._search.GetValue().strip().lower() if self._search else ""
        selected, others = [], []
        for id_, disp in self._items:
            if q and q not in disp.lower():
                continue
            if id_ in self._selected_ids:
                selected.append((id_, disp))
            else:
                others.append((id_, disp))
        for id_, disp in selected + others:
            self._visible.append((id_, disp))
            self._checklist.Append(disp)
        for i, (id_, _) in enumerate(self._visible):
            if id_ in self._selected_ids:
                self._checklist.Check(i, True)

    def _on_check(self, event):
        idx = event.GetInt()
        if 0 <= idx < len(self._visible):
            id_ = self._visible[idx][0]
            if self._checklist.IsChecked(idx):
                self._selected_ids.add(id_)
            else:
                self._selected_ids.discard(id_)

    def set_items(self, items):
        self._items = list(items)

    def get_selected_ids(self):
        return set(self._selected_ids)

    def set_selected_ids(self, ids):
        self._selected_ids = set(ids)


class DBManagerFrame(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title="Base de Datos - cubiApp", size=(1100, 750))
        theme.style_frame(self)
        # Datos completos para poder filtrar en memoria
        self._admin_rows = []
        self._com_rows = []
        self._cont_rows = []
        self._build_ui()
        self._refresh_all()
        self.Centre()

    def _create_toolbar_button(self, parent, label, handler, primary=False):
        """Crea un botón de toolbar."""
        btn = wx.Button(parent, label=label, size=(-1, 38))
        btn.SetFont(theme.font_base())
        if primary:
            btn.SetBackgroundColour(theme.ACCENT_PRIMARY)
            btn.SetForegroundColour(theme.TEXT_INVERSE)
        else:
            btn.SetBackgroundColour(theme.BG_CARD)
            btn.SetForegroundColour(theme.TEXT_PRIMARY)
        btn.Bind(wx.EVT_BUTTON, lambda e, h=handler: h())
        return btn

    def _create_search_box(self, parent, hint, on_change):
        """Crea un buscador con estilo."""
        search_panel = wx.Panel(parent)
        search_panel.SetBackgroundColour(theme.BG_PRIMARY)
        sz = wx.BoxSizer(wx.HORIZONTAL)
        
        label = theme.create_text(search_panel, "Buscar:")
        sz.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, theme.SPACE_SM)
        
        search = wx.TextCtrl(search_panel, style=wx.TE_PROCESS_ENTER, size=(-1, 32))
        theme.style_textctrl(search)
        try:
            search.SetHint(hint)
        except AttributeError:
            pass
        search.Bind(wx.EVT_TEXT, on_change)
        search.Bind(wx.EVT_TEXT_ENTER, on_change)
        sz.Add(search, 1, wx.EXPAND)
        
        search_panel.SetSizer(sz)
        return search_panel, search

    def _build_ui(self):
        main_panel = wx.Panel(self)
        main_panel.SetBackgroundColour(theme.BG_PRIMARY)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # === HEADER ===
        header = wx.Panel(main_panel)
        header.SetBackgroundColour(theme.BG_PRIMARY)
        header_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Fila superior: título + botón actualizar
        top_row = wx.BoxSizer(wx.HORIZONTAL)
        title = theme.create_title(header, "Base de Datos", "2xl")
        top_row.Add(title, 1, wx.ALIGN_CENTER_VERTICAL)
        
        btn_refresh = wx.Button(header, label="\u27F3 Actualizar", size=(-1, 36))
        btn_refresh.SetFont(theme.font_base())
        btn_refresh.SetBackgroundColour(theme.BG_CARD)
        btn_refresh.SetForegroundColour(theme.TEXT_PRIMARY)
        btn_refresh.SetToolTip("Recargar todas las tablas desde la base de datos")
        btn_refresh.Bind(wx.EVT_BUTTON, lambda e: self._refresh_all())
        top_row.Add(btn_refresh, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, theme.SPACE_XL)
        
        header_sizer.Add(top_row, 0, wx.EXPAND | wx.LEFT | wx.TOP, theme.SPACE_XL)
        
        subtitle = theme.create_text(header, "Gestiona administraciones, comunidades y contactos")
        header_sizer.Add(subtitle, 0, wx.LEFT | wx.TOP, theme.SPACE_XL)
        header_sizer.AddSpacer(theme.SPACE_LG)
        
        header.SetSizer(header_sizer)
        main_sizer.Add(header, 0, wx.EXPAND)
        
        # === NOTEBOOK ===
        self.notebook = wx.Notebook(main_panel)
        self.notebook.SetBackgroundColour(theme.BG_SECONDARY)
        self.notebook.SetFont(theme.font_base())
        
        # === PESTAÑA ADMINISTRACIONES ===
        self.panel_admin = wx.Panel(self.notebook)
        self.panel_admin.SetBackgroundColour(theme.BG_PRIMARY)
        sza = wx.BoxSizer(wx.VERTICAL)
        
        # Buscador Administración
        search_panel_a, self.search_admin = self._create_search_box(
            self.panel_admin, "Nombre, email, teléfono, dirección o contactos", self._on_search_admin
        )
        sza.Add(search_panel_a, 0, wx.EXPAND | wx.ALL, theme.SPACE_MD)
        
        self.list_admin = wx.ListCtrl(self.panel_admin, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE)
        theme.style_listctrl(self.list_admin)
        for col, w in [("Nombre", 220), ("Dirección", 200), ("Email", 200), ("Teléfono", 130), ("Contactos", 200)]:
            self.list_admin.AppendColumn(col, width=w)
        sza.Add(self.list_admin, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_LG)
        
        # Toolbar
        toolbar_a = wx.Panel(self.panel_admin)
        toolbar_a.SetBackgroundColour(theme.BG_SECONDARY)
        tb_sza = wx.BoxSizer(wx.HORIZONTAL)
        tb_sza.AddSpacer(theme.SPACE_LG)
        
        for label, handler, primary in [
            ("+ Añadir", self._add_admin, True),
            ("Editar", self._edit_admin, False),
            ("Eliminar", self._delete_admin, False),
            ("Ver ficha", self._ver_ficha_admin, False)
        ]:
            btn = self._create_toolbar_button(toolbar_a, label, handler, primary)
            tb_sza.Add(btn, 0, wx.ALL, theme.SPACE_SM)
        
        toolbar_a.SetSizer(tb_sza)
        sza.Add(toolbar_a, 0, wx.EXPAND)
        
        self.panel_admin.SetSizer(sza)
        self.list_admin.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._ver_ficha_admin())
        self.notebook.AddPage(self.panel_admin, "  Administraciones  ")

        # === PESTAÑA COMUNIDADES ===
        self.panel_com = wx.Panel(self.notebook)
        self.panel_com.SetBackgroundColour(theme.BG_PRIMARY)
        szc = wx.BoxSizer(wx.VERTICAL)
        
        # Buscador Comunidad
        search_panel_c, self.search_com = self._create_search_box(
            self.panel_com, "Nombre, CIF, dirección, email, teléfono, administración o contactos", self._on_search_com
        )
        szc.Add(search_panel_c, 0, wx.EXPAND | wx.ALL, theme.SPACE_MD)
        
        self.list_com = wx.ListCtrl(self.panel_com, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE)
        theme.style_listctrl(self.list_com)
        for col, w in [("Nombre", 170), ("CIF", 100), ("Dirección", 150), ("Email", 160), ("Teléfono", 110), ("Administración", 150), ("Contactos", 170)]:
            self.list_com.AppendColumn(col, width=w)
        szc.Add(self.list_com, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_LG)
        
        toolbar_c = wx.Panel(self.panel_com)
        toolbar_c.SetBackgroundColour(theme.BG_SECONDARY)
        tb_szc = wx.BoxSizer(wx.HORIZONTAL)
        tb_szc.AddSpacer(theme.SPACE_LG)
        
        for label, handler, primary in [
            ("+ Añadir", self._add_comunidad, True),
            ("Editar", self._edit_comunidad, False),
            ("Eliminar", self._delete_comunidad, False),
            ("Ver ficha", self._ver_ficha_comunidad, False)
        ]:
            btn = self._create_toolbar_button(toolbar_c, label, handler, primary)
            tb_szc.Add(btn, 0, wx.ALL, theme.SPACE_SM)
        
        toolbar_c.SetSizer(tb_szc)
        szc.Add(toolbar_c, 0, wx.EXPAND)
        
        self.panel_com.SetSizer(szc)
        self.list_com.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._ver_ficha_comunidad())
        self.notebook.AddPage(self.panel_com, "  Comunidades  ")

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, theme.SPACE_LG)
        main_panel.SetSizer(main_sizer)

    def _refresh_all(self):
        self._refresh_admin()
        self._refresh_comunidades()

    def _refresh_admin(self):
        self._admin_rows = repo.get_administraciones_para_tabla()
        self._populate_admin_list()

    def _refresh_comunidades(self):
        self._com_rows = repo.get_comunidades_para_tabla()
        self._populate_com_list()

    # ---------------- Filtro / buscadores ----------------

    def _filter_rows(self, rows, keys, query):
        q = (query or "").strip().lower()
        if not q:
            return rows
        out = []
        for r in rows:
            for k in keys:
                v = str((r.get(k, "") if isinstance(r, dict) else "") or "").lower()
                if q in v:
                    out.append(r)
                    break
        return out

    def _populate_admin_list(self):
        self.list_admin.DeleteAllItems()
        rows = self._admin_rows or []
        query = self.search_admin.GetValue() if hasattr(self, "search_admin") else ""
        rows = self._filter_rows(rows, ["nombre", "email", "telefono", "direccion", "contactos"], query)
        for r in rows:
            idx = self.list_admin.Append([
                r["nombre"] or "—",
                r["direccion"] or "—", r["email"] or "—", r["telefono"] or "—",
                r["contactos"],
            ])
            self.list_admin.SetItemData(idx, int(r["id"]))

    def _populate_com_list(self):
        self.list_com.DeleteAllItems()
        rows = self._com_rows or []
        query = self.search_com.GetValue() if hasattr(self, "search_com") else ""
        rows = self._filter_rows(
            rows,
            ["nombre", "cif", "direccion", "telefono", "email", "nombre_administracion", "contactos"],
            query,
        )
        for r in rows:
            ix = self.list_com.Append([
                r["nombre"], r.get("cif", "") or "—",
                r.get("direccion", "") or "—", r.get("email", "") or "—", r.get("telefono", "") or "—",
                r["nombre_administracion"], r["contactos"],
            ])
            self.list_com.SetItemData(ix, int(r["id"]))

    def _on_search_admin(self, event):
        self._populate_admin_list()

    def _on_search_com(self, event):
        self._populate_com_list()

    def _ver_ficha_admin(self):
        idx = self.list_admin.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila.", "Ver ficha", wx.OK)
            return
        id_ = self.list_admin.GetItemData(idx)
        d = FichaDialog(self, "admin", id_, on_edit=self._ficha_editar)
        d.ShowModal()
        if d.was_edited():
            self._refresh_all()
        d.Destroy()

    def _ver_ficha_comunidad(self):
        idx = self.list_com.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila.", "Ver ficha", wx.OK)
            return
        id_ = self.list_com.GetItemData(idx)
        d = FichaDialog(self, "comunidad", id_, on_edit=self._ficha_editar)
        d.ShowModal()
        if d.was_edited():
            self._refresh_all()
        d.Destroy()

    def _ficha_editar(self, entity_type, entity_id):
        """Callback desde FichaDialog: abre el formulario de edición correspondiente."""
        if entity_type == "admin":
            self._edit_admin_by_id(entity_id)
        else:
            self._edit_comunidad_by_id(entity_id)

    def _ir_a_entidad(self, tipo, id_):
        """Cierra el diálogo de relación y navega a la pestaña correspondiente seleccionando la fila con ese id."""
        if tipo is None or id_ is None:
            return
        self._relacion_ir_a = (tipo, id_)

    def _aplicar_ir_a_entidad(self):
        """Aplica la navegación pendiente (llamar después de cerrar el diálogo)."""
        pendiente = getattr(self, "_relacion_ir_a", None)
        if not pendiente:
            return
        self._relacion_ir_a = None
        tipo, id_ = pendiente
        if tipo == "administracion":
            self.notebook.SetSelection(0)
            for i in range(self.list_admin.GetItemCount()):
                if self.list_admin.GetItemData(i) == id_:
                    self.list_admin.Select(i)
                    self.list_admin.EnsureVisible(i)
                    break
        elif tipo == "comunidad":
            self.notebook.SetSelection(1)
            for i in range(self.list_com.GetItemCount()):
                if self.list_com.GetItemData(i) == id_:
                    self.list_com.Select(i)
                    self.list_com.EnsureVisible(i)
                    break

    def _admin_display(self, a):
        """Texto para mostrar en lista/combobox de administración (nombre es clave, no se repite)."""
        return a.get("nombre") or a.get("email") or f"ID {a['id']}"

    def _add_admin(self):
        d = AdminFormDialog(self, "Añadir administración")
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        vals = d.get_values()
        d.Destroy()
        nombre = vals["nombre"]
        if not nombre:
            wx.MessageBox("El nombre es obligatorio.", "Error", wx.OK | wx.ICON_ERROR)
            return
        id_, err = repo.create_administracion(nombre, vals["email"], vals["telefono"], vals["direccion"])
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            if vals["contacto_ids"]:
                repo.set_contactos_para_administracion(id_, vals["contacto_ids"])
            self._refresh_all()
            wx.MessageBox("Administración creada.", "OK", wx.OK)

    def _edit_admin(self):
        idx = self.list_admin.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila.", "Editar", wx.OK)
            return
        self._edit_admin_by_id(self.list_admin.GetItemData(idx))

    def _edit_admin_by_id(self, id_):
        r = repo.get_administracion_por_id(id_)
        if not r:
            return
        contacto_ids = [c["id"] for c in repo.get_contactos_por_administracion_id(id_)]
        initial = {
            "nombre": r["nombre"], "email": r["email"],
            "telefono": r["telefono"], "direccion": r["direccion"],
            "contacto_ids": contacto_ids,
        }
        d = AdminFormDialog(self, "Editar administración", initial=initial)
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        vals = d.get_values()
        d.Destroy()
        nombre = vals["nombre"]
        if not nombre:
            wx.MessageBox("El nombre es obligatorio.", "Error", wx.OK | wx.ICON_ERROR)
            return
        err = repo.update_administracion(id_, nombre, vals["email"], vals["telefono"], vals["direccion"])
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            repo.set_contactos_para_administracion(id_, vals["contacto_ids"])
            self._refresh_all()
            wx.MessageBox("Guardado.", "OK", wx.OK)

    def _delete_admin(self):
        idx = self.list_admin.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila.", "Eliminar", wx.OK)
            return
        if wx.MessageBox("¿Eliminar esta administración?", "Confirmar", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        id_ = self.list_admin.GetItemData(idx)
        err = repo.delete_administracion(id_)
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            self._refresh_all()

    def _add_comunidad(self):
        admins = repo.get_administraciones()
        if not admins:
            wx.MessageBox("Crea antes al menos una administración.", "Añadir comunidad", wx.OK)
            return
        d = ComunidadFormDialog(self, "Añadir comunidad")
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        vals = d.get_values()
        d.Destroy()
        nombre = vals["nombre"]
        if not nombre:
            wx.MessageBox("El nombre es obligatorio.", "Error", wx.OK | wx.ICON_ERROR)
            return
        admin_id = vals.get("administracion_id")
        if not admin_id:
            wx.MessageBox("La administración es obligatoria.", "Error", wx.OK | wx.ICON_ERROR)
            return
        id_, err = repo.create_comunidad(
            nombre, admin_id, cif=vals.get("cif", ""),
            direccion=vals.get("direccion", ""), email=vals.get("email", ""),
            telefono=vals.get("telefono", ""),
        )
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            if vals["contacto_ids"]:
                repo.set_contactos_para_comunidad(id_, vals["contacto_ids"])
            self._refresh_all()
            wx.MessageBox("Comunidad creada.", "OK", wx.OK)

    def _edit_comunidad(self):
        idx = self.list_com.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila.", "Editar", wx.OK)
            return
        self._edit_comunidad_by_id(self.list_com.GetItemData(idx))

    def _edit_comunidad_by_id(self, id_):
        r = repo.get_comunidad_por_id(id_)
        if not r:
            return
        contacto_ids = [c["id"] for c in repo.get_contactos_por_comunidad_id(id_)]
        initial = {
            "nombre": r["nombre"], "cif": r.get("cif", ""),
            "direccion": r.get("direccion", ""), "email": r.get("email", ""),
            "telefono": r.get("telefono", ""),
            "administracion_id": r["administracion_id"],
            "contacto_ids": contacto_ids,
        }
        d = ComunidadFormDialog(self, "Editar comunidad", initial=initial)
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        vals = d.get_values()
        d.Destroy()
        nombre = vals["nombre"]
        if not nombre:
            wx.MessageBox("El nombre es obligatorio.", "Error", wx.OK | wx.ICON_ERROR)
            return
        admin_id = vals.get("administracion_id")
        if not admin_id:
            wx.MessageBox("La administración es obligatoria.", "Error", wx.OK | wx.ICON_ERROR)
            return
        err = repo.update_comunidad(
            id_, nombre, admin_id, cif=vals.get("cif", ""),
            direccion=vals.get("direccion", ""), email=vals.get("email", ""),
            telefono=vals.get("telefono", ""),
        )
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            repo.set_contactos_para_comunidad(id_, vals.get("contacto_ids", []))
            self._refresh_all()
            wx.MessageBox("Guardado.", "OK", wx.OK)

    def _delete_comunidad(self):
        idx = self.list_com.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila.", "Eliminar", wx.OK)
            return
        if wx.MessageBox("¿Eliminar esta comunidad?", "Confirmar", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        id_ = self.list_com.GetItemData(idx)
        err = repo.delete_comunidad(id_)
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            self._refresh_all()

# ---------------------------------------------------------------------------
# Ficha detallada de una entidad (administración o comunidad)
# ---------------------------------------------------------------------------

class FichaDialog(wx.Dialog):
    """Diálogo de ficha: muestra todos los datos de una entidad y sus contactos asociados."""

    def __init__(self, parent, entity_type: str, entity_id: int, on_edit=None):
        """
        Args:
            entity_type: 'admin' o 'comunidad'
            entity_id: ID de la entidad
            on_edit: callback opcional; si se proporciona se muestra botón Editar
        """
        title = "Ficha de Administración" if entity_type == "admin" else "Ficha de Comunidad"
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        self._entity_type = entity_type
        self._entity_id = entity_id
        self._on_edit = on_edit
        self._edited = False
        self._build_ui()

    def was_edited(self) -> bool:
        return self._edited

    # ── construcción de UI ──────────────────────────────────────────────

    def _build_ui(self):
        scroll = wx.ScrolledWindow(self, style=wx.VSCROLL)
        scroll.SetScrollRate(0, 8)
        scroll.SetBackgroundColour(theme.BG_PRIMARY)

        content = wx.BoxSizer(wx.VERTICAL)

        if self._entity_type == "admin":
            data = repo.get_administracion_por_id(self._entity_id)
            contactos = repo.get_contactos_por_administracion_id(self._entity_id)
            if not data:
                content.Add(wx.StaticText(scroll, label="Administración no encontrada."),
                            0, wx.ALL, theme.SPACE_LG)
            else:
                self._build_admin_ficha(scroll, content, data, contactos)
        else:
            data = repo.get_comunidad_por_id(self._entity_id)
            contactos = repo.get_contactos_por_comunidad_id(self._entity_id)
            if not data:
                content.Add(wx.StaticText(scroll, label="Comunidad no encontrada."),
                            0, wx.ALL, theme.SPACE_LG)
            else:
                admin_data = None
                if data.get("administracion_id"):
                    admin_data = repo.get_administracion_por_id(data["administracion_id"])
                self._build_comunidad_ficha(scroll, content, data, contactos, admin_data)

        scroll.SetSizer(content)

        # Botones
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        if self._on_edit:
            btn_edit = wx.Button(self, label="Editar")
            btn_edit.SetFont(theme.font_base())
            btn_edit.Bind(wx.EVT_BUTTON, self._on_edit_click)
            btn_sizer.Add(btn_edit, 0, wx.RIGHT, theme.SPACE_SM)
        btn_close = wx.Button(self, wx.ID_OK, "Cerrar")
        btn_close.SetFont(theme.font_base())
        theme.style_button_primary(btn_close)
        btn_sizer.Add(btn_close)

        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(scroll, 1, wx.EXPAND)
        root.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.TOP, theme.SPACE_XS)
        root.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, theme.SPACE_MD)
        self.SetSizer(root)

        theme.fit_dialog(self, 520, 460)

    # ── helpers de layout ───────────────────────────────────────────────

    @staticmethod
    def _add_section_title(parent, sizer, text):
        lbl = wx.StaticText(parent, label=text)
        lbl.SetFont(theme.font_lg())
        lbl.SetForegroundColour(theme.ACCENT_PRIMARY)
        sizer.Add(lbl, 0, wx.LEFT | wx.TOP, theme.SPACE_SM)
        sizer.Add(wx.StaticLine(parent), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_SM)

    @staticmethod
    def _selectable(parent, text):
        """TextCtrl readonly sin borde: parece StaticText pero permite seleccionar y copiar."""
        tc = wx.TextCtrl(parent, value=text or "—",
                         style=wx.TE_READONLY | wx.BORDER_NONE)
        tc.SetFont(theme.font_base())
        tc.SetForegroundColour(theme.TEXT_PRIMARY)
        tc.SetBackgroundColour(parent.GetBackgroundColour())
        return tc

    @staticmethod
    def _add_field(parent, sizer, label, value):
        row = wx.BoxSizer(wx.HORIZONTAL)

        lbl = wx.StaticText(parent, label=label, size=(100, -1))
        lbl.SetFont(theme.get_font_medium(10))
        lbl.SetForegroundColour(theme.TEXT_SECONDARY)
        row.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)

        val = FichaDialog._selectable(parent, value)
        row.Add(val, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, theme.SPACE_XS)

        sizer.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_SM)

    @staticmethod
    def _card_selectable(parent, text):
        """TextCtrl readonly sin borde para usar dentro de tarjetas (fondo BG_CARD)."""
        tc = wx.TextCtrl(parent, value=text or "—",
                         style=wx.TE_READONLY | wx.BORDER_NONE)
        tc.SetFont(theme.font_sm())
        tc.SetForegroundColour(theme.TEXT_SECONDARY)
        tc.SetBackgroundColour(theme.BG_CARD)
        return tc

    def _build_contact_card(self, parent, sizer, c):
        """Construye una mini-tarjeta para un contacto."""
        card = wx.Panel(parent, style=wx.BORDER_SIMPLE)
        card.SetBackgroundColour(theme.BG_CARD)
        card_sz = wx.BoxSizer(wx.VERTICAL)

        accent = wx.Panel(card, size=(-1, 3))
        accent.SetBackgroundColour(theme.ACCENT_PRIMARY)
        card_sz.Add(accent, 0, wx.EXPAND)

        nombre = wx.StaticText(card, label=c["nombre"] or "Sin nombre")
        nombre.SetFont(theme.get_font_bold(11))
        nombre.SetForegroundColour(theme.TEXT_PRIMARY)
        card_sz.Add(nombre, 0, wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_SM)

        fields = []
        if c.get("telefono"):
            fields.append(("Teléfono", c["telefono"]))
        if c.get("telefono2"):
            fields.append(("Teléfono 2", c["telefono2"]))
        if c.get("email"):
            fields.append(("Email", c["email"]))

        if fields:
            grid = wx.FlexGridSizer(cols=2, vgap=1, hgap=theme.SPACE_XS)
            grid.AddGrowableCol(1, 1)
            for label, value in fields:
                lbl = wx.StaticText(card, label=label)
                lbl.SetFont(theme.font_sm())
                lbl.SetForegroundColour(theme.TEXT_TERTIARY)
                grid.Add(lbl, 0, wx.ALIGN_CENTER_VERTICAL)
                grid.Add(self._card_selectable(card, value), 1,
                         wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

            card_sz.Add(grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
                        theme.SPACE_XS)

        if c.get("notas"):
            line = wx.StaticLine(card)
            card_sz.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
                        theme.SPACE_XS)
            notas = self._card_selectable(card, c["notas"])
            card_sz.Add(notas, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
                        theme.SPACE_XS)

        card_sz.AddSpacer(theme.SPACE_XS)
        card.SetSizer(card_sz)
        sizer.Add(card, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
                   theme.SPACE_SM)

    def _build_entity_card(self, parent, sizer, name, fields):
        """Tarjeta genérica: nombre + lista de (label, value)."""
        card = wx.Panel(parent, style=wx.BORDER_SIMPLE)
        card.SetBackgroundColour(theme.BG_CARD)
        card_sz = wx.BoxSizer(wx.VERTICAL)

        accent = wx.Panel(card, size=(-1, 3))
        accent.SetBackgroundColour(theme.ACCENT_PRIMARY)
        card_sz.Add(accent, 0, wx.EXPAND)

        lbl_name = wx.StaticText(card, label=name or "—")
        lbl_name.SetFont(theme.get_font_bold(11))
        lbl_name.SetForegroundColour(theme.TEXT_PRIMARY)
        card_sz.Add(lbl_name, 0, wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_SM)

        visible = [(l, v) for l, v in fields if v]
        if visible:
            grid = wx.FlexGridSizer(cols=2, vgap=1, hgap=theme.SPACE_XS)
            grid.AddGrowableCol(1, 1)
            for label, value in visible:
                l = wx.StaticText(card, label=label)
                l.SetFont(theme.font_sm())
                l.SetForegroundColour(theme.TEXT_TERTIARY)
                grid.Add(l, 0, wx.ALIGN_CENTER_VERTICAL)
                grid.Add(self._card_selectable(card, value), 1,
                         wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)
            card_sz.Add(grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
                        theme.SPACE_XS)

        card_sz.AddSpacer(theme.SPACE_XS)
        card.SetSizer(card_sz)
        sizer.Add(card, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
                   theme.SPACE_SM)

    # ── fichas concretas ────────────────────────────────────────────────

    def _build_admin_ficha(self, parent, sizer, data, contactos):
        header = wx.StaticText(parent, label=data["nombre"])
        header.SetFont(theme.font_xl())
        header.SetForegroundColour(theme.TEXT_PRIMARY)
        sizer.Add(header, 0, wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_MD)

        self._add_section_title(parent, sizer, "Datos")
        self._add_field(parent, sizer, "Email:", data.get("email"))
        self._add_field(parent, sizer, "Teléfono:", data.get("telefono"))
        self._add_field(parent, sizer, "Dirección:", data.get("direccion"))

        sizer.AddSpacer(theme.SPACE_SM)
        self._add_section_title(parent, sizer, f"Contactos ({len(contactos)})")

        if contactos:
            for c in contactos:
                self._build_contact_card(parent, sizer, c)
        else:
            no_ct = wx.StaticText(parent, label="No hay contactos asociados.")
            no_ct.SetFont(theme.font_base())
            no_ct.SetForegroundColour(theme.TEXT_TERTIARY)
            sizer.Add(no_ct, 0, wx.ALL, theme.SPACE_SM)

        sizer.AddSpacer(theme.SPACE_SM)

    def _build_comunidad_ficha(self, parent, sizer, data, contactos, admin_data):
        header = wx.StaticText(parent, label=data["nombre"])
        header.SetFont(theme.font_xl())
        header.SetForegroundColour(theme.TEXT_PRIMARY)
        sizer.Add(header, 0, wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_MD)

        self._add_section_title(parent, sizer, "Datos")
        self._add_field(parent, sizer, "CIF:", data.get("cif"))
        self._add_field(parent, sizer, "Dirección:", data.get("direccion"))
        self._add_field(parent, sizer, "Email:", data.get("email"))
        self._add_field(parent, sizer, "Teléfono:", data.get("telefono"))

        sizer.AddSpacer(theme.SPACE_SM)
        self._add_section_title(parent, sizer, "Administración")
        if admin_data:
            self._build_entity_card(parent, sizer, admin_data["nombre"], [
                ("Email", admin_data.get("email")),
                ("Teléfono", admin_data.get("telefono")),
                ("Dirección", admin_data.get("direccion")),
            ])
        else:
            lbl = wx.StaticText(parent, label="Sin administración asignada.")
            lbl.SetFont(theme.font_base())
            lbl.SetForegroundColour(theme.TEXT_TERTIARY)
            sizer.Add(lbl, 0, wx.ALL, theme.SPACE_MD)

        sizer.AddSpacer(theme.SPACE_SM)
        self._add_section_title(parent, sizer, f"Contactos ({len(contactos)})")

        if contactos:
            for c in contactos:
                self._build_contact_card(parent, sizer, c)
        else:
            no_ct = wx.StaticText(parent, label="No hay contactos asociados.")
            no_ct.SetFont(theme.font_base())
            no_ct.SetForegroundColour(theme.TEXT_TERTIARY)
            sizer.Add(no_ct, 0, wx.ALL, theme.SPACE_SM)

        sizer.AddSpacer(theme.SPACE_SM)

    # ── editar ──────────────────────────────────────────────────────────

    def _on_edit_click(self, evt):
        if self._on_edit:
            self._on_edit(self._entity_type, self._entity_id)
            self._edited = True
            self.EndModal(wx.ID_OK)


class VerRelacionDialog(wx.Dialog):
    """Diálogo para ver relaciones entre entidades."""
    def __init__(self, parent, title, column_headers, rows, on_activate=None):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        self._on_activate = on_activate
        self._item_data = []
        
        panel = wx.Panel(self)
        panel.SetBackgroundColour(theme.BG_PRIMARY)
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Header
        header_title = theme.create_title(panel, title, "xl")
        sizer.Add(header_title, 0, wx.ALL, theme.SPACE_XL)
        
        # Lista
        self._list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE)
        theme.style_listctrl(self._list)
        
        if len(column_headers) == 5:
            widths = [60, 160, 110, 110, 160]
        elif len(column_headers) == 4:
            widths = [70, 200, 160, 200]
        else:
            widths = [160, 400]
        for i, h in enumerate(column_headers):
            w = widths[i] if i < len(widths) else 160
            self._list.AppendColumn(h, width=w)
        for cells, tipo, id_ in rows:
            self._list.Append(cells)
            self._item_data.append((tipo, id_))
        sizer.Add(self._list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)
        
        # Hint
        hint = theme.create_caption(panel, "Doble clic para navegar a la entidad")
        sizer.Add(hint, 0, wx.LEFT | wx.TOP, theme.SPACE_XL)
        
        # Botón cerrar
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn = wx.Button(panel, wx.ID_OK, "Cerrar", size=(110, 40))
        btn.SetFont(theme.font_base())
        btn_sizer.Add(btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, theme.SPACE_XL)
        
        panel.SetSizer(sizer)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(main_sizer)
        theme.fit_dialog(self, 560, 420)
        self._list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_activated)

    def _on_activated(self, evt):
        idx = evt.GetIndex()
        if idx < 0 or idx >= len(self._item_data):
            return
        tipo, id_ = self._item_data[idx]
        if self._on_activate and tipo is not None and id_ is not None:
            self._on_activate(tipo, id_)
            self.EndModal(wx.ID_OK)


class ContactoDialog(wx.Dialog):
    """Diálogo para añadir/editar contacto con asignación a administraciones y comunidades."""
    def __init__(self, parent, title, initial=None):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        initial = initial or {}
        self._admins = repo.get_administraciones()
        self._comunidades = repo.get_comunidades()
        self._admin_display = lambda a: a.get("nombre") or a.get("email") or f"ID {a['id']}"

        panel = wx.Panel(self)
        panel.SetBackgroundColour(theme.BG_PRIMARY)
        main = wx.BoxSizer(wx.VERTICAL)
        
        # Título
        title_label = theme.create_title(panel, title, "xl")
        main.Add(title_label, 0, wx.LEFT | wx.TOP, theme.SPACE_XL)
        main.AddSpacer(theme.SPACE_MD)
        
        # Formulario
        grid = wx.FlexGridSizer(cols=2, vgap=theme.SPACE_SM, hgap=theme.SPACE_LG)
        grid.AddGrowableCol(1, 1)
        fields = ["Nombre *", "Teléfono *", "Teléfono 2", "Email", "Notas"]
        self._ctrls = {}
        for lbl in fields:
            label = theme.create_text(panel, lbl)
            grid.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
            default = ""
            if lbl == "Nombre *": default = initial.get("nombre", "")
            elif lbl == "Teléfono *": default = initial.get("telefono", "")
            elif lbl == "Teléfono 2": default = initial.get("telefono2", "")
            elif lbl == "Email": default = initial.get("email", "")
            elif lbl == "Notas": default = initial.get("notas", "")
            c = theme.create_input(panel, value=default)
            self._ctrls[lbl] = c
            grid.Add(c, 1, wx.EXPAND)
        main.Add(grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        main.AddSpacer(theme.SPACE_SM)
        
        # Filtro + desplegable de administración
        admin_label = theme.create_text(panel, "Administración (opcional):")
        main.Add(admin_label, 0, wx.LEFT | wx.RIGHT, theme.SPACE_XL)
        self._admin_filter = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER, size=(-1, 32))
        theme.style_textctrl(self._admin_filter)
        try:
            self._admin_filter.SetHint("Buscar administración por nombre o email")
        except AttributeError:
            pass
        self._admin_filter.Bind(wx.EVT_TEXT, self._on_admin_filter_change)
        main.Add(self._admin_filter, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_XL)
        self._combo_admin = wx.ComboBox(panel, style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self._combo_admin.SetFont(theme.font_base())
        main.Add(self._combo_admin, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_XL)

        main.AddSpacer(theme.SPACE_MD)
        
        # Filtro + desplegable de comunidad
        com_label = theme.create_text(panel, "Comunidad (opcional):")
        main.Add(com_label, 0, wx.LEFT | wx.RIGHT, theme.SPACE_XL)
        self._com_filter = wx.TextCtrl(panel, style=wx.TE_PROCESS_ENTER, size=(-1, 32))
        theme.style_textctrl(self._com_filter)
        try:
            self._com_filter.SetHint("Buscar comunidad por nombre")
        except AttributeError:
            pass
        self._com_filter.Bind(wx.EVT_TEXT, self._on_com_filter_change)
        main.Add(self._com_filter, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_XL)
        self._combo_com = wx.ComboBox(panel, style=wx.CB_DROPDOWN | wx.CB_READONLY)
        self._combo_com.SetFont(theme.font_base())
        main.Add(self._combo_com, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_XL)

        # Mapas de índices visibles
        self._admin_combo_map = []
        self._com_combo_map = []
        admin_ids_ini = initial.get("administracion_ids", [])
        com_ids_ini = initial.get("comunidad_ids", [])
        pre_admin = admin_ids_ini[0] if len(admin_ids_ini) == 1 else None
        pre_com = com_ids_ini[0] if len(com_ids_ini) == 1 else None
        self._refresh_admin_combo(pre_admin)
        self._refresh_com_combo(pre_com)

        # Separador
        main.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_SM)
        main.AddSpacer(theme.SPACE_SM)
        
        # Botones
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancelar", size=(110, 36))
        btn_cancel.SetFont(theme.font_base())
        btn_cancel.SetBackgroundColour(theme.BG_SECONDARY)
        btn_cancel.SetForegroundColour(theme.TEXT_PRIMARY)
        
        btn_ok = wx.Button(panel, wx.ID_OK, "Guardar", size=(110, 36))
        btn_ok.SetFont(theme.get_font_medium())
        btn_ok.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_ok.SetForegroundColour(theme.TEXT_INVERSE)
        
        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_ok, 0)
        main.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, theme.SPACE_XL)
        
        panel.SetSizer(main)

        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(panel, 1, wx.EXPAND)
        self.SetSizer(root)
        theme.fit_dialog(self, 500, 400)

    def get_values(self):
        vals = {
            "nombre": self._ctrls["Nombre *"].GetValue().strip(),
            "telefono": self._ctrls["Teléfono *"].GetValue().strip(),
            "telefono2": self._ctrls["Teléfono 2"].GetValue().strip(),
            "email": self._ctrls["Email"].GetValue().strip(),
            "notas": self._ctrls["Notas"].GetValue().strip(),
        }
        # Resolver administración seleccionada
        a_sel = self._combo_admin.GetSelection()
        if a_sel <= 0 or not self._admin_combo_map:
            vals["administracion_ids"] = []
        else:
            idx = self._admin_combo_map[a_sel - 1]
            vals["administracion_ids"] = [self._admins[idx]["id"]]
        # Resolver comunidad seleccionada
        c_sel = self._combo_com.GetSelection()
        if c_sel <= 0 or not self._com_combo_map:
            vals["comunidad_ids"] = []
        else:
            idx = self._com_combo_map[c_sel - 1]
            vals["comunidad_ids"] = [self._comunidades[idx]["id"]]
        return vals

    def _refresh_admin_combo(self, preselect_id=None):
        if preselect_id is None and self._admin_combo_map:
            cur = self._combo_admin.GetSelection()
            if cur > 0 and cur - 1 < len(self._admin_combo_map):
                preselect_id = self._admins[self._admin_combo_map[cur - 1]]["id"]
        self._combo_admin.Clear()
        self._admin_combo_map = []
        self._combo_admin.Append("(ninguna)")
        q = (self._admin_filter.GetValue() if hasattr(self, "_admin_filter") else "").strip().lower()
        for idx, a in enumerate(self._admins):
            disp = self._admin_display(a).strip()
            if q and q not in disp.lower():
                continue
            self._admin_combo_map.append(idx)
            self._combo_admin.Append(disp)
        if preselect_id is not None:
            for i, idx in enumerate(self._admin_combo_map, start=1):
                if self._admins[idx]["id"] == preselect_id:
                    self._combo_admin.SetSelection(i)
                    break
            else:
                self._combo_admin.SetSelection(0)
        else:
            self._combo_admin.SetSelection(0)

    def _refresh_com_combo(self, preselect_id=None):
        if preselect_id is None and self._com_combo_map:
            cur = self._combo_com.GetSelection()
            if cur > 0 and cur - 1 < len(self._com_combo_map):
                preselect_id = self._comunidades[self._com_combo_map[cur - 1]]["id"]
        self._combo_com.Clear()
        self._com_combo_map = []
        self._combo_com.Append("(ninguna)")
        q = (self._com_filter.GetValue() if hasattr(self, "_com_filter") else "").strip().lower()
        for idx, c in enumerate(self._comunidades):
            nombre = (c.get("nombre") or f"ID {c['id']}").strip()
            if q and q not in nombre.lower():
                continue
            self._com_combo_map.append(idx)
            self._combo_com.Append(nombre)
        if preselect_id is not None:
            for i, idx in enumerate(self._com_combo_map, start=1):
                if self._comunidades[idx]["id"] == preselect_id:
                    self._combo_com.SetSelection(i)
                    break
            else:
                self._combo_com.SetSelection(0)
        else:
            self._combo_com.SetSelection(0)

    def _on_admin_filter_change(self, event):
        self._refresh_admin_combo()

    def _on_com_filter_change(self, event):
        self._refresh_com_combo()


class QuickContactoDialog(wx.Dialog):
    """Diálogo rápido para crear un nuevo contacto."""

    def __init__(self, parent):
        super().__init__(parent, title="Nuevo Contacto",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        self._contacto = None
        self._build_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = theme.create_title(panel, "Nuevo contacto", "xl")
        sizer.Add(title, 0, wx.LEFT | wx.TOP, theme.SPACE_XL)
        sizer.AddSpacer(theme.SPACE_MD)

        self._fields = {}
        for label_text, attr in [("Nombre *", "nombre"), ("Teléfono *", "telefono"),
                                  ("Teléfono 2", "telefono2"), ("Email", "email"),
                                  ("Notas", "notas")]:
            lbl = theme.create_text(panel, label_text)
            sizer.Add(lbl, 0, wx.LEFT, theme.SPACE_XL + 2)
            sizer.AddSpacer(theme.SPACE_XS)
            txt = theme.create_input(panel)
            self._fields[attr] = txt
            sizer.Add(txt, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)
            sizer.AddSpacer(theme.SPACE_XS)

        sizer.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_SM)
        sizer.AddSpacer(theme.SPACE_SM)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancelar", size=(100, 36))
        btn_cancel.SetFont(theme.font_base())
        btn_ok = wx.Button(panel, wx.ID_OK, "Crear", size=(100, 36))
        btn_ok.SetFont(theme.get_font_medium())
        btn_ok.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_ok.SetForegroundColour(theme.TEXT_INVERSE)
        btn_ok.SetDefault()
        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_ok, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, theme.SPACE_XL)

        panel.SetSizer(sizer)
        dlg_sizer = wx.BoxSizer(wx.VERTICAL)
        dlg_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dlg_sizer)
        theme.fit_dialog(self, 420, 380)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

    def _on_ok(self, event):
        nombre = self._fields["nombre"].GetValue().strip()
        telefono = self._fields["telefono"].GetValue().strip()
        if not nombre:
            wx.MessageBox("El nombre es obligatorio.", "Aviso", wx.OK)
            return
        if not telefono:
            wx.MessageBox("El teléfono es obligatorio.", "Aviso", wx.OK)
            return
        new_id, err = repo.create_contacto(
            nombre, telefono,
            self._fields["telefono2"].GetValue().strip(),
            self._fields["email"].GetValue().strip(),
            self._fields["notas"].GetValue().strip(),
        )
        if err:
            wx.MessageBox(f"Error:\n{err}", "Error", wx.OK | wx.ICON_ERROR)
            return
        self._contacto = {"id": new_id, "nombre": nombre, "telefono": telefono}
        self.EndModal(wx.ID_OK)

    def get_contacto(self):
        return self._contacto


class QuickAdminDialog(wx.Dialog):
    """Diálogo rápido para crear una nueva administración."""

    def __init__(self, parent):
        super().__init__(parent, title="Nueva Administración",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        self._admin = None
        self._build_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        theme.style_panel(panel)
        sizer = wx.BoxSizer(wx.VERTICAL)

        title = theme.create_title(panel, "Nueva administración", "xl")
        sizer.Add(title, 0, wx.LEFT | wx.TOP, theme.SPACE_XL)
        sizer.AddSpacer(theme.SPACE_MD)

        self._fields = {}
        for label_text, attr in [("Nombre *", "nombre"), ("Email", "email"),
                                  ("Teléfono", "telefono"), ("Dirección", "direccion")]:
            lbl = theme.create_text(panel, label_text)
            sizer.Add(lbl, 0, wx.LEFT, theme.SPACE_XL + 2)
            sizer.AddSpacer(theme.SPACE_XS)
            txt = theme.create_input(panel)
            self._fields[attr] = txt
            sizer.Add(txt, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)
            sizer.AddSpacer(theme.SPACE_XS)

        sizer.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_SM)
        sizer.AddSpacer(theme.SPACE_SM)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancelar", size=(100, 36))
        btn_cancel.SetFont(theme.font_base())
        btn_ok = wx.Button(panel, wx.ID_OK, "Crear", size=(100, 36))
        btn_ok.SetFont(theme.get_font_medium())
        btn_ok.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_ok.SetForegroundColour(theme.TEXT_INVERSE)
        btn_ok.SetDefault()
        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_ok, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, theme.SPACE_XL)

        panel.SetSizer(sizer)
        dlg_sizer = wx.BoxSizer(wx.VERTICAL)
        dlg_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dlg_sizer)
        theme.fit_dialog(self, 420, 350)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

    def _on_ok(self, event):
        nombre = self._fields["nombre"].GetValue().strip()
        if not nombre:
            wx.MessageBox("El nombre es obligatorio.", "Aviso", wx.OK)
            return
        new_id, err = repo.create_administracion(
            nombre,
            self._fields["email"].GetValue().strip(),
            self._fields["telefono"].GetValue().strip(),
            self._fields["direccion"].GetValue().strip(),
        )
        if err:
            wx.MessageBox(f"Error:\n{err}", "Error", wx.OK | wx.ICON_ERROR)
            return
        self._admin = {
            "id": new_id, "nombre": nombre,
            "email": self._fields["email"].GetValue().strip(),
            "telefono": self._fields["telefono"].GetValue().strip(),
            "direccion": self._fields["direccion"].GetValue().strip(),
        }
        self.EndModal(wx.ID_OK)

    def get_admin(self):
        return self._admin


class AdminFormDialog(wx.Dialog):
    """Diálogo para añadir/editar administración con gestión de contactos."""

    def __init__(self, parent, title, initial=None):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        self._initial = initial or {}
        self._all_contactos = repo.get_contactos()
        self._build_ui()

    def _build_ui(self):
        panel = wx.Panel(self)
        panel.SetBackgroundColour(theme.BG_PRIMARY)
        main = wx.BoxSizer(wx.VERTICAL)

        title_label = theme.create_title(panel, self.GetTitle(), "xl")
        main.Add(title_label, 0, wx.LEFT | wx.TOP, theme.SPACE_XL)
        main.AddSpacer(theme.SPACE_MD)

        # --- Campos (layout vertical: label encima del input) ---
        self._ctrls = {}
        for lbl_text, key, default in [
            ("Nombre *", "nombre", self._initial.get("nombre", "")),
            ("Email", "email", self._initial.get("email", "")),
            ("Teléfono", "telefono", self._initial.get("telefono", "")),
            ("Dirección", "direccion", self._initial.get("direccion", "")),
        ]:
            lbl = theme.create_text(panel, lbl_text)
            main.Add(lbl, 0, wx.LEFT, theme.SPACE_XL + 2)
            main.AddSpacer(theme.SPACE_XS)
            ctrl = theme.create_input(panel, value=default or "")
            self._ctrls[key] = ctrl
            main.Add(ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)
            main.AddSpacer(theme.SPACE_XS)

        # --- Sección Contactos ---
        main.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)
        main.AddSpacer(theme.SPACE_SM)

        ct_lbl = theme.create_text(panel, "Contactos")
        main.Add(ct_lbl, 0, wx.LEFT, theme.SPACE_XL + 2)
        main.AddSpacer(theme.SPACE_XS)

        ct_row = wx.BoxSizer(wx.HORIZONTAL)

        self._ct_combo = wx.ComboCtrl(panel, size=(-1, 32))
        self._ct_combo.SetFont(theme.font_base())
        self._ct_popup = CheckSelectPopup()
        self._ct_combo.SetPopupControl(self._ct_popup)

        ct_items = [(c["id"], f"{c['nombre']}  —  {c['telefono']}") for c in self._all_contactos]
        self._ct_popup.set_items(ct_items)
        self._ct_popup.set_selected_ids(set(self._initial.get("contacto_ids", [])))
        self._ct_combo.SetValue(self._ct_popup.GetStringValue())

        ct_row.Add(self._ct_combo, 1, wx.EXPAND | wx.RIGHT, theme.SPACE_SM)

        btn_new_ct = wx.Button(panel, label="+ Nuevo", size=(90, 32))
        btn_new_ct.SetFont(theme.font_sm())
        btn_new_ct.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_new_ct.SetForegroundColour(theme.TEXT_INVERSE)
        btn_new_ct.Bind(wx.EVT_BUTTON, self._on_new_contacto)
        ct_row.Add(btn_new_ct, 0)

        main.Add(ct_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        # --- Botones ---
        main.AddSpacer(theme.SPACE_SM)
        main.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)
        main.AddSpacer(theme.SPACE_SM)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancelar", size=(110, 36))
        btn_cancel.SetFont(theme.font_base())
        btn_cancel.SetBackgroundColour(theme.BG_SECONDARY)
        btn_cancel.SetForegroundColour(theme.TEXT_PRIMARY)
        btn_ok = wx.Button(panel, wx.ID_OK, "Guardar", size=(110, 36))
        btn_ok.SetFont(theme.get_font_medium())
        btn_ok.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_ok.SetForegroundColour(theme.TEXT_INVERSE)
        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_ok, 0)
        main.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, theme.SPACE_XL)

        panel.SetSizer(main)
        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(panel, 1, wx.EXPAND)
        self.SetSizer(root)
        theme.fit_dialog(self, 480, 420)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

    def _on_ok(self, event):
        if not self._ctrls["nombre"].GetValue().strip():
            wx.MessageBox("El nombre es obligatorio.", "Aviso", wx.OK)
            return
        self.EndModal(wx.ID_OK)

    def _on_new_contacto(self, event):
        d = QuickContactoDialog(self)
        if d.ShowModal() == wx.ID_OK:
            new_ct = d.get_contacto()
            if new_ct:
                self._all_contactos = repo.get_contactos()
                ct_items = [(c["id"], f"{c['nombre']}  —  {c['telefono']}") for c in self._all_contactos]
                self._ct_popup.set_items(ct_items)
                self._ct_popup._selected_ids.add(new_ct["id"])
                self._ct_combo.SetValue(self._ct_popup.GetStringValue())
        d.Destroy()

    def get_values(self):
        return {
            "nombre": self._ctrls["nombre"].GetValue().strip(),
            "email": self._ctrls["email"].GetValue().strip(),
            "telefono": self._ctrls["telefono"].GetValue().strip(),
            "direccion": self._ctrls["direccion"].GetValue().strip(),
            "contacto_ids": list(self._ct_popup.get_selected_ids()),
        }


class ComunidadFormDialog(wx.Dialog):
    """Diálogo para añadir/editar comunidad con búsqueda de admin y gestión de contactos."""

    def __init__(self, parent, title, initial=None):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        self._initial = initial or {}
        self._all_admins = repo.get_administraciones()
        self._all_contactos = repo.get_contactos()
        self._build_ui()

    @staticmethod
    def _admin_display(a):
        return a.get("nombre") or a.get("email") or f"ID {a['id']}"

    def _build_ui(self):
        panel = wx.Panel(self)
        panel.SetBackgroundColour(theme.BG_PRIMARY)
        main = wx.BoxSizer(wx.VERTICAL)

        title_label = theme.create_title(panel, self.GetTitle(), "xl")
        main.Add(title_label, 0, wx.LEFT | wx.TOP, theme.SPACE_XL)
        main.AddSpacer(theme.SPACE_MD)

        # --- Campos básicos (layout vertical) ---
        self._ctrls = {}

        row_top = wx.BoxSizer(wx.HORIZONTAL)
        col_nombre = wx.BoxSizer(wx.VERTICAL)
        col_nombre.Add(theme.create_text(panel, "Nombre *"), 0, wx.LEFT, 2)
        col_nombre.AddSpacer(theme.SPACE_XS)
        ctrl_n = theme.create_input(panel, value=self._initial.get("nombre", "") or "")
        self._ctrls["nombre"] = ctrl_n
        col_nombre.Add(ctrl_n, 0, wx.EXPAND)
        row_top.Add(col_nombre, 3, wx.EXPAND | wx.RIGHT, theme.SPACE_SM)

        col_cif = wx.BoxSizer(wx.VERTICAL)
        col_cif.Add(theme.create_text(panel, "CIF"), 0, wx.LEFT, 2)
        col_cif.AddSpacer(theme.SPACE_XS)
        ctrl_c = theme.create_input(panel, value=self._initial.get("cif", "") or "")
        self._ctrls["cif"] = ctrl_c
        col_cif.Add(ctrl_c, 0, wx.EXPAND)
        row_top.Add(col_cif, 2, wx.EXPAND)

        main.Add(row_top, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)
        main.AddSpacer(theme.SPACE_XS)

        for lbl_text, key, default in [
            ("Dirección", "direccion", self._initial.get("direccion", "")),
            ("Email", "email", self._initial.get("email", "")),
            ("Teléfono", "telefono", self._initial.get("telefono", "")),
        ]:
            lbl = theme.create_text(panel, lbl_text)
            main.Add(lbl, 0, wx.LEFT, theme.SPACE_XL + 2)
            main.AddSpacer(theme.SPACE_XS)
            ctrl = theme.create_input(panel, value=default or "")
            self._ctrls[key] = ctrl
            main.Add(ctrl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)
            main.AddSpacer(theme.SPACE_XS)

        # --- Sección Administración ---
        main.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)
        main.AddSpacer(theme.SPACE_SM)

        admin_lbl = theme.create_text(panel, "Administración *")
        main.Add(admin_lbl, 0, wx.LEFT, theme.SPACE_XL + 2)
        main.AddSpacer(theme.SPACE_XS)

        admin_row = wx.BoxSizer(wx.HORIZONTAL)

        self._admin_cc = wx.ComboCtrl(panel, size=(-1, 32))
        self._admin_cc.SetFont(theme.font_base())
        self._admin_popup = SearchSelectPopup()
        self._admin_cc.SetPopupControl(self._admin_popup)

        admin_items = [(a["id"], self._admin_display(a)) for a in self._all_admins]
        self._admin_popup.set_items(admin_items)

        pre_admin = self._initial.get("administracion_id")
        if pre_admin:
            self._admin_popup.set_selected_id(pre_admin)
            self._admin_cc.SetValue(self._admin_popup.GetStringValue())

        admin_row.Add(self._admin_cc, 1, wx.EXPAND | wx.RIGHT, theme.SPACE_SM)

        btn_new_admin = wx.Button(panel, label="+ Nueva", size=(80, 32))
        btn_new_admin.SetFont(theme.font_sm())
        btn_new_admin.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_new_admin.SetForegroundColour(theme.TEXT_INVERSE)
        btn_new_admin.Bind(wx.EVT_BUTTON, self._on_new_admin)
        admin_row.Add(btn_new_admin, 0)

        main.Add(admin_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        # --- Sección Contactos ---
        main.AddSpacer(theme.SPACE_SM)

        ct_lbl = theme.create_text(panel, "Contactos")
        main.Add(ct_lbl, 0, wx.LEFT, theme.SPACE_XL + 2)
        main.AddSpacer(theme.SPACE_XS)

        ct_row = wx.BoxSizer(wx.HORIZONTAL)

        self._ct_combo = wx.ComboCtrl(panel, size=(-1, 32))
        self._ct_combo.SetFont(theme.font_base())
        self._ct_popup = CheckSelectPopup()
        self._ct_combo.SetPopupControl(self._ct_popup)

        ct_items = [(c["id"], f"{c['nombre']}  —  {c['telefono']}") for c in self._all_contactos]
        self._ct_popup.set_items(ct_items)
        self._ct_popup.set_selected_ids(set(self._initial.get("contacto_ids", [])))
        self._ct_combo.SetValue(self._ct_popup.GetStringValue())

        ct_row.Add(self._ct_combo, 1, wx.EXPAND | wx.RIGHT, theme.SPACE_SM)

        btn_new_ct = wx.Button(panel, label="+ Nuevo", size=(80, 32))
        btn_new_ct.SetFont(theme.font_sm())
        btn_new_ct.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_new_ct.SetForegroundColour(theme.TEXT_INVERSE)
        btn_new_ct.Bind(wx.EVT_BUTTON, self._on_new_contacto)
        ct_row.Add(btn_new_ct, 0)

        main.Add(ct_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        # --- Botones ---
        main.AddSpacer(theme.SPACE_SM)
        main.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)
        main.AddSpacer(theme.SPACE_SM)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancelar", size=(110, 36))
        btn_cancel.SetFont(theme.font_base())
        btn_cancel.SetBackgroundColour(theme.BG_SECONDARY)
        btn_cancel.SetForegroundColour(theme.TEXT_PRIMARY)
        btn_ok = wx.Button(panel, wx.ID_OK, "Guardar", size=(110, 36))
        btn_ok.SetFont(theme.get_font_medium())
        btn_ok.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_ok.SetForegroundColour(theme.TEXT_INVERSE)
        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_ok, 0)
        main.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.RIGHT | wx.BOTTOM, theme.SPACE_XL)

        panel.SetSizer(main)
        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(panel, 1, wx.EXPAND)
        self.SetSizer(root)
        theme.fit_dialog(self, 500, 470)
        self.Bind(wx.EVT_BUTTON, self._on_ok, id=wx.ID_OK)

    def _on_ok(self, event):
        if not self._ctrls["nombre"].GetValue().strip():
            wx.MessageBox("El nombre de la comunidad es obligatorio.", "Aviso", wx.OK)
            return
        if not self._admin_popup.get_selected_id():
            wx.MessageBox("Debe seleccionar una administración.", "Aviso", wx.OK)
            return
        self.EndModal(wx.ID_OK)

    # --- Admin ComboCtrl ---

    def _on_new_admin(self, event):
        d = QuickAdminDialog(self)
        if d.ShowModal() == wx.ID_OK:
            new_admin = d.get_admin()
            if new_admin:
                self._all_admins = repo.get_administraciones()
                admin_items = [(a["id"], self._admin_display(a)) for a in self._all_admins]
                self._admin_popup.set_items(admin_items)
                self._admin_popup.set_selected_id(new_admin["id"])
                self._admin_cc.SetValue(self._admin_popup.GetStringValue())
        d.Destroy()

    # --- Contactos ComboCtrl ---

    def _on_new_contacto(self, event):
        d = QuickContactoDialog(self)
        if d.ShowModal() == wx.ID_OK:
            new_ct = d.get_contacto()
            if new_ct:
                self._all_contactos = repo.get_contactos()
                ct_items = [(c["id"], f"{c['nombre']}  —  {c['telefono']}") for c in self._all_contactos]
                self._ct_popup.set_items(ct_items)
                self._ct_popup._selected_ids.add(new_ct["id"])
                self._ct_combo.SetValue(self._ct_popup.GetStringValue())
        d.Destroy()

    def get_values(self):
        return {
            "nombre": self._ctrls["nombre"].GetValue().strip(),
            "cif": self._ctrls["cif"].GetValue().strip(),
            "direccion": self._ctrls["direccion"].GetValue().strip(),
            "email": self._ctrls["email"].GetValue().strip(),
            "telefono": self._ctrls["telefono"].GetValue().strip(),
            "administracion_id": self._admin_popup.get_selected_id(),
            "contacto_ids": list(self._ct_popup.get_selected_ids()),
        }


class SimpleDialog(wx.Dialog):
    """Diálogo de formulario con diseño limpio."""
    def __init__(self, parent, title, field_labels, initial=None, choices=None):
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        theme.style_dialog(self)
        self._labels = field_labels
        self._initial = initial or {}
        self._choices = choices or {}
        self._ctrls = {}
        
        panel = wx.Panel(self)
        panel.SetBackgroundColour(theme.BG_PRIMARY)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título
        title_label = theme.create_title(panel, title, "xl")
        main_sizer.Add(title_label, 0, wx.LEFT | wx.TOP, theme.SPACE_XL)
        main_sizer.AddSpacer(theme.SPACE_LG)
        
        # Campos del formulario
        form_sizer = wx.FlexGridSizer(cols=2, vgap=theme.SPACE_MD, hgap=theme.SPACE_LG)
        form_sizer.AddGrowableCol(1, 1)
        
        for lbl in field_labels:
            label = theme.create_text(panel, lbl)
            form_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
            
            if lbl in self._choices:
                c = wx.ComboBox(panel, value=self._initial.get(lbl, ""), 
                               choices=self._choices[lbl], style=wx.CB_READONLY)
                c.SetFont(theme.font_base())
            else:
                c = wx.TextCtrl(panel, value=self._initial.get(lbl, ""), size=(-1, 36))
                theme.style_textctrl(c)
            self._ctrls[lbl] = c
            form_sizer.Add(c, 1, wx.EXPAND)
        
        main_sizer.Add(form_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)
        
        # Separador
        main_sizer.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_XL)
        
        # Botones
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, "Cancelar", size=(120, 42))
        btn_cancel.SetFont(theme.font_base())
        btn_cancel.SetBackgroundColour(theme.BG_SECONDARY)
        btn_cancel.SetForegroundColour(theme.TEXT_PRIMARY)
        
        btn_ok = wx.Button(panel, wx.ID_OK, "Guardar", size=(120, 42))
        btn_ok.SetFont(theme.get_font_medium())
        btn_ok.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_ok.SetForegroundColour(theme.TEXT_INVERSE)
        
        btn_sizer.Add(btn_cancel, 0, wx.RIGHT, theme.SPACE_MD)
        btn_sizer.Add(btn_ok, 0)
        main_sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, theme.SPACE_XL)
        
        panel.SetSizer(main_sizer)
        
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(dialog_sizer)
        theme.fit_dialog(self, 480, 300)

    def get_values(self):
        return {lbl: (self._ctrls[lbl].GetValue() if hasattr(self._ctrls[lbl], "GetValue") else self._ctrls[lbl].GetStringSelection()) for lbl in self._labels}
