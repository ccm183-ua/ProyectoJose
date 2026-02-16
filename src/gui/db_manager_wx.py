"""
Ventana de gestión de la base de datos (wxPython).
"""

import wx
from src.core import db_repository as repo
from src.gui import theme


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
            self.panel_admin, "Nombre, C.I.F, email, teléfono, dirección o contactos", self._on_search_admin
        )
        sza.Add(search_panel_a, 0, wx.EXPAND | wx.ALL, theme.SPACE_MD)
        
        self.list_admin = wx.ListCtrl(self.panel_admin, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE)
        theme.style_listctrl(self.list_admin)
        for col, w in [("ID", 50), ("Nombre", 170), ("C.I.F", 110), ("Dirección", 160), ("Email", 160), ("Teléfono", 110), ("Contactos", 180)]:
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
            ("Ver relación", self._ver_relacion_admin, False)
        ]:
            btn = self._create_toolbar_button(toolbar_a, label, handler, primary)
            tb_sza.Add(btn, 0, wx.ALL, theme.SPACE_SM)
        
        toolbar_a.SetSizer(tb_sza)
        sza.Add(toolbar_a, 0, wx.EXPAND)
        
        self.panel_admin.SetSizer(sza)
        self.list_admin.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._ver_relacion_admin())
        self.notebook.AddPage(self.panel_admin, "  Administraciones  ")

        # === PESTAÑA COMUNIDADES ===
        self.panel_com = wx.Panel(self.notebook)
        self.panel_com.SetBackgroundColour(theme.BG_PRIMARY)
        szc = wx.BoxSizer(wx.VERTICAL)
        
        # Buscador Comunidad
        search_panel_c, self.search_com = self._create_search_box(
            self.panel_com, "Nombre, dirección, email, teléfono, administración o contactos", self._on_search_com
        )
        szc.Add(search_panel_c, 0, wx.EXPAND | wx.ALL, theme.SPACE_MD)
        
        self.list_com = wx.ListCtrl(self.panel_com, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE)
        theme.style_listctrl(self.list_com)
        for col, w in [("ID", 50), ("Nombre", 160), ("Dirección", 160), ("Email", 160), ("Teléfono", 110), ("Administración", 150), ("Contactos", 180)]:
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
            ("Ver relación", self._ver_relacion_comunidad, False)
        ]:
            btn = self._create_toolbar_button(toolbar_c, label, handler, primary)
            tb_szc.Add(btn, 0, wx.ALL, theme.SPACE_SM)
        
        toolbar_c.SetSizer(tb_szc)
        szc.Add(toolbar_c, 0, wx.EXPAND)
        
        self.panel_com.SetSizer(szc)
        self.list_com.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._ver_relacion_comunidad())
        self.notebook.AddPage(self.panel_com, "  Comunidades  ")

        # === PESTAÑA CONTACTOS ===
        self.panel_cont = wx.Panel(self.notebook)
        self.panel_cont.SetBackgroundColour(theme.BG_PRIMARY)
        szct = wx.BoxSizer(wx.VERTICAL)
        
        # Buscador Contacto
        search_panel_ct, self.search_cont = self._create_search_box(
            self.panel_cont, "Nombre, teléfono, email, administraciones o comunidades", self._on_search_cont
        )
        szct.Add(search_panel_ct, 0, wx.EXPAND | wx.ALL, theme.SPACE_MD)
        
        self.list_cont = wx.ListCtrl(self.panel_cont, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE)
        theme.style_listctrl(self.list_cont)
        for col, w in [("ID", 50), ("Nombre", 140), ("Teléfono", 110), ("Teléfono 2", 110), ("Email", 160), ("Administraciones", 160), ("Comunidades", 160), ("Notas", 160)]:
            self.list_cont.AppendColumn(col, width=w)
        szct.Add(self.list_cont, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_LG)
        
        toolbar_ct = wx.Panel(self.panel_cont)
        toolbar_ct.SetBackgroundColour(theme.BG_SECONDARY)
        tb_szct = wx.BoxSizer(wx.HORIZONTAL)
        tb_szct.AddSpacer(theme.SPACE_LG)
        
        for label, handler, primary in [
            ("+ Añadir", self._add_contacto, True),
            ("Editar", self._edit_contacto, False),
            ("Eliminar", self._delete_contacto, False),
            ("Ver relación", self._ver_relacion_contacto, False)
        ]:
            btn = self._create_toolbar_button(toolbar_ct, label, handler, primary)
            tb_szct.Add(btn, 0, wx.ALL, theme.SPACE_SM)
        
        toolbar_ct.SetSizer(tb_szct)
        szct.Add(toolbar_ct, 0, wx.EXPAND)
        
        self.panel_cont.SetSizer(szct)
        self.list_cont.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._ver_relacion_contacto())
        self.notebook.AddPage(self.panel_cont, "  Contactos  ")

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, theme.SPACE_LG)
        main_panel.SetSizer(main_sizer)

    def _refresh_all(self):
        self._refresh_admin()
        self._refresh_comunidades()
        self._refresh_contactos()

    def _refresh_admin(self):
        self._admin_rows = repo.get_administraciones_para_tabla()
        self._populate_admin_list()

    def _refresh_comunidades(self):
        self._com_rows = repo.get_comunidades_para_tabla()
        self._populate_com_list()

    def _refresh_contactos(self):
        self._cont_rows = repo.get_contactos_para_tabla()
        self._populate_cont_list()

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
        rows = self._filter_rows(rows, ["nombre", "cif", "email", "telefono", "direccion", "contactos"], query)
        for r in rows:
            self.list_admin.Append([
                str(r["id"]), r["nombre"] or "—", r["cif"] or "—",
                r["direccion"] or "—", r["email"] or "—", r["telefono"] or "—",
                r["contactos"],
            ])

    def _populate_com_list(self):
        self.list_com.DeleteAllItems()
        rows = self._com_rows or []
        query = self.search_com.GetValue() if hasattr(self, "search_com") else ""
        rows = self._filter_rows(
            rows,
            ["nombre", "direccion", "telefono", "email", "nombre_administracion", "contactos"],
            query,
        )
        for r in rows:
            self.list_com.Append([
                str(r["id"]), r["nombre"],
                r.get("direccion", "") or "—", r.get("email", "") or "—", r.get("telefono", "") or "—",
                r["nombre_administracion"], r["contactos"],
            ])

    def _populate_cont_list(self):
        self.list_cont.DeleteAllItems()
        rows = self._cont_rows or []
        query = self.search_cont.GetValue() if hasattr(self, "search_cont") else ""
        rows = self._filter_rows(
            rows,
            ["nombre", "telefono", "telefono2", "email", "notas", "administraciones", "comunidades"],
            query,
        )
        for r in rows:
            self.list_cont.Append([
                str(r["id"]), r["nombre"],
                r["telefono"], r.get("telefono2", "") or "—",
                r["email"] or "—",
                r.get("administraciones", "—") or "—", r.get("comunidades", "—") or "—",
                r.get("notas", "") or "—",
            ])

    def _on_search_admin(self, event):
        self._populate_admin_list()

    def _on_search_com(self, event):
        self._populate_com_list()

    def _on_search_cont(self, event):
        self._populate_cont_list()

    def _ver_relacion_admin(self):
        idx = self.list_admin.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila para ver sus contactos.", "Ver relación", wx.OK)
            return
        id_ = int(self.list_admin.GetItemText(idx))
        contactos = repo.get_contactos_por_administracion_id(id_)
        cols = ["ID", "Nombre", "Teléfono", "Teléfono 2", "Email"]
        rows = [(
            [str(c["id"]), c["nombre"] or "—", c["telefono"] or "—", c.get("telefono2", "") or "—", c.get("email") or "—"],
            "contacto",
            c["id"],
        ) for c in contactos]
        if not rows:
            rows = [(["—", "(ningún contacto asignado)", "—", "—", "—"], None, None)]
        d = VerRelacionDialog(self, "Contactos de esta administración", cols, rows, on_activate=self._ir_a_entidad)
        d.ShowModal()
        d.Destroy()
        self._aplicar_ir_a_entidad()

    def _ver_relacion_comunidad(self):
        idx = self.list_com.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila para ver sus contactos.", "Ver relación", wx.OK)
            return
        id_ = int(self.list_com.GetItemText(idx))
        contactos = repo.get_contactos_por_comunidad_id(id_)
        cols = ["ID", "Nombre", "Teléfono", "Teléfono 2", "Email"]
        rows = [(
            [str(c["id"]), c["nombre"] or "—", c["telefono"] or "—", c.get("telefono2", "") or "—", c.get("email") or "—"],
            "contacto",
            c["id"],
        ) for c in contactos]
        if not rows:
            rows = [(["—", "(ningún contacto asignado)", "—", "—", "—"], None, None)]
        d = VerRelacionDialog(self, "Contactos de esta comunidad", cols, rows, on_activate=self._ir_a_entidad)
        d.ShowModal()
        d.Destroy()
        self._aplicar_ir_a_entidad()

    def _ver_relacion_contacto(self):
        idx = self.list_cont.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila para ver administraciones y comunidades.", "Ver relación", wx.OK)
            return
        id_ = int(self.list_cont.GetItemText(idx))
        admin_ids = repo.get_administracion_ids_para_contacto(id_)
        com_ids = repo.get_comunidad_ids_para_contacto(id_)
        admins = repo.get_administraciones()
        coms = repo.get_comunidades()
        admin_map = {a["id"]: (a.get("nombre") or a.get("email")) or f"ID {a['id']}" for a in admins}
        com_map = {c["id"]: c.get("nombre") or f"ID {c['id']}" for c in coms}
        rows = [(["Administración", admin_map.get(aid, str(aid))], "administracion", aid) for aid in admin_ids]
        rows += [(["Comunidad", com_map.get(cid, str(cid))], "comunidad", cid) for cid in com_ids]
        if not rows:
            d = VerRelacionDialog(self, "Relaciones de este contacto", ["Tipo", "Nombre"], [(["—", "(ninguna asignada)"], None, None)], on_activate=None)
        else:
            d = VerRelacionDialog(self, "Relaciones de este contacto", ["Tipo", "Nombre"], rows, on_activate=self._ir_a_entidad)
        d.ShowModal()
        d.Destroy()
        self._aplicar_ir_a_entidad()

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
        if tipo == "contacto":
            self.notebook.SetSelection(2)
            for i in range(self.list_cont.GetItemCount()):
                if self.list_cont.GetItemText(i) == str(id_):
                    self.list_cont.Select(i)
                    self.list_cont.EnsureVisible(i)
                    break
        elif tipo == "administracion":
            self.notebook.SetSelection(0)
            for i in range(self.list_admin.GetItemCount()):
                if self.list_admin.GetItemText(i) == str(id_):
                    self.list_admin.Select(i)
                    self.list_admin.EnsureVisible(i)
                    break
        elif tipo == "comunidad":
            self.notebook.SetSelection(1)
            for i in range(self.list_com.GetItemCount()):
                if self.list_com.GetItemText(i) == str(id_):
                    self.list_com.Select(i)
                    self.list_com.EnsureVisible(i)
                    break

    def _admin_display(self, a):
        """Texto para mostrar en lista/combobox de administración (nombre es clave, no se repite)."""
        return a.get("nombre") or a.get("email") or f"ID {a['id']}"

    def _add_admin(self):
        d = SimpleDialog(self, "Añadir administración", ["Nombre *", "C.I.F", "Email", "Teléfono", "Dirección"])
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        vals = d.get_values()
        d.Destroy()
        nombre = (vals.get("Nombre *", "") or "").strip()
        if not nombre:
            wx.MessageBox("El nombre es obligatorio.", "Error", wx.OK | wx.ICON_ERROR)
            return
        id_, err = repo.create_administracion(nombre, vals.get("C.I.F", ""), vals.get("Email", ""), vals.get("Teléfono", ""), vals.get("Dirección", ""))
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            self._refresh_all()
            wx.MessageBox("Administración creada.", "OK", wx.OK)

    def _edit_admin(self):
        idx = self.list_admin.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila.", "Editar", wx.OK)
            return
        id_ = int(self.list_admin.GetItemText(idx))
        r = repo.get_administracion_por_id(id_)
        if not r:
            return
        d = SimpleDialog(self, "Editar administración", ["Nombre *", "C.I.F", "Email", "Teléfono", "Dirección"], initial={"Nombre *": r["nombre"], "C.I.F": r["cif"], "Email": r["email"], "Teléfono": r["telefono"], "Dirección": r["direccion"]})
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        vals = d.get_values()
        d.Destroy()
        nombre = (vals.get("Nombre *") or "").strip()
        if not nombre:
            wx.MessageBox("El nombre es obligatorio.", "Error", wx.OK | wx.ICON_ERROR)
            return
        err = repo.update_administracion(id_, nombre, vals.get("C.I.F", ""), vals.get("Email", ""), vals.get("Teléfono", ""), vals.get("Dirección", ""))
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            self._refresh_all()
            wx.MessageBox("Guardado.", "OK", wx.OK)

    def _delete_admin(self):
        idx = self.list_admin.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila.", "Eliminar", wx.OK)
            return
        if wx.MessageBox("¿Eliminar esta administración?", "Confirmar", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        id_ = int(self.list_admin.GetItemText(idx))
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
        labels = ["Nombre *", "Administración", "Dirección", "Email", "Teléfono"]
        choices = {"Administración": [self._admin_display(a) for a in admins]}
        d = SimpleDialog(self, "Añadir comunidad", labels, choices=choices)
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        vals = d.get_values()
        d.Destroy()
        nombre = (vals.get("Nombre *") or "").strip()
        if not nombre:
            wx.MessageBox("El nombre es obligatorio.", "Error", wx.OK | wx.ICON_ERROR)
            return
        sel = vals.get("Administración", "")
        admin = next((a for a in admins if self._admin_display(a) == sel), admins[0] if admins else None)
        admin_id = admin["id"] if admin else (admins[0]["id"] if admins else 0)
        id_, err = repo.create_comunidad(nombre, admin_id, vals.get("Dirección", ""), vals.get("Email", ""), vals.get("Teléfono", ""))
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            self._refresh_all()
            wx.MessageBox("Comunidad creada.", "OK", wx.OK)

    def _edit_comunidad(self):
        idx = self.list_com.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila.", "Editar", wx.OK)
            return
        id_ = int(self.list_com.GetItemText(idx))
        r = repo.get_comunidad_por_id(id_)
        if not r:
            return
        admins = repo.get_administraciones()
        labels = ["Nombre *", "Administración", "Dirección", "Email", "Teléfono"]
        choices = {"Administración": [self._admin_display(a) for a in admins]}
        current_admin = next((a for a in admins if a["id"] == r["administracion_id"]), None)
        initial_admin = self._admin_display(current_admin) if current_admin else (choices["Administración"][0] if choices["Administración"] else "")
        initial = {"Nombre *": r["nombre"], "Administración": initial_admin, "Dirección": r.get("direccion", ""), "Email": r.get("email", ""), "Teléfono": r.get("telefono", "")}
        d = SimpleDialog(self, "Editar comunidad", labels, initial=initial, choices=choices)
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        vals = d.get_values()
        d.Destroy()
        nombre = (vals.get("Nombre *") or "").strip()
        if not nombre:
            wx.MessageBox("El nombre es obligatorio.", "Error", wx.OK | wx.ICON_ERROR)
            return
        sel = vals.get("Administración", "")
        admin = next((a for a in admins if self._admin_display(a) == sel), current_admin)
        admin_id = admin["id"] if admin else r["administracion_id"]
        err = repo.update_comunidad(id_, nombre, admin_id, vals.get("Dirección", ""), vals.get("Email", ""), vals.get("Teléfono", ""))
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            self._refresh_all()
            wx.MessageBox("Guardado.", "OK", wx.OK)

    def _delete_comunidad(self):
        idx = self.list_com.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila.", "Eliminar", wx.OK)
            return
        if wx.MessageBox("¿Eliminar esta comunidad?", "Confirmar", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        id_ = int(self.list_com.GetItemText(idx))
        err = repo.delete_comunidad(id_)
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            self._refresh_all()

    def _add_contacto(self):
        d = ContactoDialog(self, "Añadir contacto", initial={})
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        vals = d.get_values()
        d.Destroy()
        nombre = (vals.get("nombre") or "").strip()
        telefono = (vals.get("telefono") or "").strip()
        if not nombre or not telefono:
            wx.MessageBox("Nombre y teléfono son obligatorios.", "Error", wx.OK | wx.ICON_ERROR)
            return
        id_, err = repo.create_contacto(nombre, telefono, vals.get("telefono2", ""), vals.get("email", ""), vals.get("notas", ""))
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
            return
        err = repo.set_administracion_contacto(id_, vals.get("administracion_ids", []))
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            err2 = repo.set_comunidad_contacto(id_, vals.get("comunidad_ids", []))
            if err2:
                wx.MessageBox(err2, "Error", wx.OK | wx.ICON_ERROR)
        self._refresh_all()
        wx.MessageBox("Contacto creado.", "OK", wx.OK)

    def _edit_contacto(self):
        idx = self.list_cont.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila.", "Editar", wx.OK)
            return
        id_ = int(self.list_cont.GetItemText(idx))
        contactos = repo.get_contactos()
        r = next((c for c in contactos if c["id"] == id_), None)
        if not r:
            return
        initial = {
            "nombre": r["nombre"], "telefono": r["telefono"], "telefono2": r.get("telefono2", ""),
            "email": r.get("email", ""), "notas": r.get("notas", ""),
            "administracion_ids": repo.get_administracion_ids_para_contacto(id_),
            "comunidad_ids": repo.get_comunidad_ids_para_contacto(id_),
        }
        d = ContactoDialog(self, "Editar contacto", initial=initial)
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        vals = d.get_values()
        d.Destroy()
        nombre = (vals.get("nombre") or "").strip()
        telefono = (vals.get("telefono") or "").strip()
        if not nombre or not telefono:
            wx.MessageBox("Nombre y teléfono son obligatorios.", "Error", wx.OK | wx.ICON_ERROR)
            return
        err = repo.update_contacto(id_, nombre, telefono, vals.get("telefono2", ""), vals.get("email", ""), vals.get("notas", ""))
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
            return
        err = repo.set_administracion_contacto(id_, vals.get("administracion_ids", []))
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            err2 = repo.set_comunidad_contacto(id_, vals.get("comunidad_ids", []))
            if err2:
                wx.MessageBox(err2, "Error", wx.OK | wx.ICON_ERROR)
        self._refresh_all()
        wx.MessageBox("Guardado.", "OK", wx.OK)

    def _delete_contacto(self):
        idx = self.list_cont.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila.", "Eliminar", wx.OK)
            return
        if wx.MessageBox("¿Eliminar este contacto?", "Confirmar", wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
            return
        id_ = int(self.list_cont.GetItemText(idx))
        err = repo.delete_contacto(id_)
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            self._refresh_all()


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
        
        self.SetMinSize((560, 420))
        self.SetSize((680, 520))
        self.CenterOnParent()
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
        main.AddSpacer(theme.SPACE_LG)
        
        # Formulario
        grid = wx.FlexGridSizer(cols=2, vgap=theme.SPACE_MD, hgap=theme.SPACE_LG)
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
            c = wx.TextCtrl(panel, value=default, size=(-1, 36))
            theme.style_textctrl(c)
            self._ctrls[lbl] = c
            grid.Add(c, 1, wx.EXPAND)
        main.Add(grid, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_XL)

        main.AddSpacer(theme.SPACE_LG)
        
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
        main.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, theme.SPACE_XL)
        
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
        main.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, theme.SPACE_XL)
        
        panel.SetSizer(main)

        root = wx.BoxSizer(wx.VERTICAL)
        root.Add(panel, 1, wx.EXPAND)
        self.SetSizer(root)
        
        # Auto-dimensionar al contenido, limitado a la pantalla
        self.Fit()
        w, h = self.GetSize()
        w = max(w, 560)
        display = wx.Display(wx.Display.GetFromWindow(self) if wx.Display.GetFromWindow(self) >= 0 else 0)
        screen_w, screen_h = display.GetClientArea().GetSize()
        w = min(w, screen_w - 40)
        h = min(h, screen_h - 40)
        self.SetSize((w, h))
        self.SetMinSize((500, 400))
        self.CenterOnParent()

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
        
        # Auto-dimensionar al contenido, limitado a la pantalla
        self.Fit()
        w, h = self.GetSize()
        w = max(w, 520)
        display = wx.Display(wx.Display.GetFromWindow(self) if wx.Display.GetFromWindow(self) >= 0 else 0)
        screen_w, screen_h = display.GetClientArea().GetSize()
        w = min(w, screen_w - 40)
        h = min(h, screen_h - 40)
        self.SetSize((w, h))
        self.SetMinSize((480, 300))
        self.CenterOnParent()

    def get_values(self):
        return {lbl: (self._ctrls[lbl].GetValue() if hasattr(self._ctrls[lbl], "GetValue") else self._ctrls[lbl].GetStringSelection()) for lbl in self._labels}
