"""
Ventana de gestión de la base de datos (wxPython).
"""

import wx
from src.core import db_repository as repo
from src.gui import theme


class DBManagerFrame(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title="Base de Datos - cubiApp", size=(1050, 700))
        theme.style_frame(self)
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

    def _build_ui(self):
        main_panel = wx.Panel(self)
        main_panel.SetBackgroundColour(theme.BG_PRIMARY)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # === HEADER ===
        header = wx.Panel(main_panel)
        header.SetBackgroundColour(theme.BG_PRIMARY)
        header_sizer = wx.BoxSizer(wx.VERTICAL)
        
        title = theme.create_title(header, "Base de Datos", "2xl")
        header_sizer.Add(title, 0, wx.LEFT | wx.TOP, theme.SPACE_XL)
        
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
        
        self.list_admin = wx.ListCtrl(self.panel_admin, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE)
        theme.style_listctrl(self.list_admin)
        for col, w in [("ID", 60), ("Email", 240), ("Teléfono", 150), ("Dirección", 240), ("Contactos", 250)]:
            self.list_admin.AppendColumn(col, width=w)
        sza.Add(self.list_admin, 1, wx.EXPAND | wx.ALL, theme.SPACE_LG)
        
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
        self.list_admin.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._edit_admin())
        self.notebook.AddPage(self.panel_admin, "  Administraciones  ")

        # === PESTAÑA COMUNIDADES ===
        self.panel_com = wx.Panel(self.notebook)
        self.panel_com.SetBackgroundColour(theme.BG_PRIMARY)
        szc = wx.BoxSizer(wx.VERTICAL)
        
        self.list_com = wx.ListCtrl(self.panel_com, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE)
        theme.style_listctrl(self.list_com)
        for col, w in [("ID", 60), ("Nombre", 220), ("Administración", 220), ("Contactos", 280)]:
            self.list_com.AppendColumn(col, width=w)
        szc.Add(self.list_com, 1, wx.EXPAND | wx.ALL, theme.SPACE_LG)
        
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
        self.list_com.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._edit_comunidad())
        self.notebook.AddPage(self.panel_com, "  Comunidades  ")

        # === PESTAÑA CONTACTOS ===
        self.panel_cont = wx.Panel(self.notebook)
        self.panel_cont.SetBackgroundColour(theme.BG_PRIMARY)
        szct = wx.BoxSizer(wx.VERTICAL)
        
        self.list_cont = wx.ListCtrl(self.panel_cont, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE)
        theme.style_listctrl(self.list_cont)
        for col, w in [("ID", 60), ("Nombre", 160), ("Teléfono", 140), ("Email", 200), ("Administraciones", 200), ("Comunidades", 200)]:
            self.list_cont.AppendColumn(col, width=w)
        szct.Add(self.list_cont, 1, wx.EXPAND | wx.ALL, theme.SPACE_LG)
        
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
        self.list_cont.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._edit_contacto())
        self.notebook.AddPage(self.panel_cont, "  Contactos  ")

        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, theme.SPACE_LG)
        main_panel.SetSizer(main_sizer)

    def _refresh_all(self):
        self._refresh_admin()
        self._refresh_comunidades()
        self._refresh_contactos()

    def _refresh_admin(self):
        self.list_admin.DeleteAllItems()
        for r in repo.get_administraciones_para_tabla():
            self.list_admin.Append([str(r["id"]), r["email"] or "—", r["telefono"] or "—", r["direccion"] or "—", r["contactos"]])

    def _refresh_comunidades(self):
        self.list_com.DeleteAllItems()
        for r in repo.get_comunidades_para_tabla():
            self.list_com.Append([str(r["id"]), r["nombre"], r["nombre_administracion"], r["contactos"]])

    def _refresh_contactos(self):
        self.list_cont.DeleteAllItems()
        for r in repo.get_contactos_para_tabla():
            self.list_cont.Append([
                str(r["id"]), r["nombre"], r["telefono"], r["email"] or "—",
                r.get("administraciones", "—") or "—", r.get("comunidades", "—") or "—",
            ])

    def _ver_relacion_admin(self):
        idx = self.list_admin.GetFirstSelected()
        if idx < 0:
            wx.MessageBox("Selecciona una fila para ver sus contactos.", "Ver relación", wx.OK)
            return
        id_ = int(self.list_admin.GetItemText(idx))
        contactos = repo.get_contactos_por_administracion_id(id_)
        cols = ["ID", "Nombre", "Teléfono", "Email"]
        rows = [([str(c["id"]), c["nombre"] or "—", c["telefono"] or "—", c.get("email") or "—"], "contacto", c["id"]) for c in contactos]
        if not rows:
            rows = [(["—", "(ningún contacto asignado)", "—", "—"], None, None)]
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
        cols = ["ID", "Nombre", "Teléfono", "Email"]
        rows = [([str(c["id"]), c["nombre"] or "—", c["telefono"] or "—", c.get("email") or "—"], "contacto", c["id"]) for c in contactos]
        if not rows:
            rows = [(["—", "(ningún contacto asignado)", "—", "—"], None, None)]
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
        admin_map = {a["id"]: a.get("email") or f"ID {a['id']}" for a in admins}
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

    def _add_admin(self):
        d = SimpleDialog(self, "Añadir administración", ["Email", "Teléfono", "Dirección"])
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        vals = d.get_values()
        d.Destroy()
        id_, err = repo.create_administracion(vals.get("Email", ""), vals.get("Teléfono", ""), vals.get("Dirección", ""))
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            self._refresh_admin()
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
        d = SimpleDialog(self, "Editar administración", ["Email", "Teléfono", "Dirección"], initial={"Email": r["email"], "Teléfono": r["telefono"], "Dirección": r["direccion"]})
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        vals = d.get_values()
        d.Destroy()
        err = repo.update_administracion(id_, vals.get("Email", ""), vals.get("Teléfono", ""), vals.get("Dirección", ""))
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            self._refresh_admin()
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
            self._refresh_admin()

    def _add_comunidad(self):
        admins = repo.get_administraciones()
        if not admins:
            wx.MessageBox("Crea antes al menos una administración.", "Añadir comunidad", wx.OK)
            return
        labels = ["Nombre *", "Administración (ID)", "Dirección", "Email", "Teléfono"]
        choices = {"Administración (ID)": [str(a["id"]) for a in admins]}
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
        try:
            admin_id = int(vals.get("Administración (ID)", 0) or (admins[0]["id"] if admins else 0))
        except ValueError:
            admin_id = admins[0]["id"] if admins else 0
        id_, err = repo.create_comunidad(nombre, admin_id, vals.get("Dirección", ""), vals.get("Email", ""), vals.get("Teléfono", ""))
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            self._refresh_comunidades()
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
        labels = ["Nombre *", "Administración (ID)", "Dirección", "Email", "Teléfono"]
        choices = {"Administración (ID)": [str(a["id"]) for a in admins]}
        initial = {"Nombre *": r["nombre"], "Administración (ID)": str(r["administracion_id"]), "Dirección": r.get("direccion", ""), "Email": r.get("email", ""), "Teléfono": r.get("telefono", "")}
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
        try:
            admin_id = int(vals.get("Administración (ID)", 0))
        except ValueError:
            admin_id = r["administracion_id"]
        err = repo.update_comunidad(id_, nombre, admin_id, vals.get("Dirección", ""), vals.get("Email", ""), vals.get("Teléfono", ""))
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            self._refresh_comunidades()
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
            self._refresh_comunidades()

    def _add_contacto(self):
        d = SimpleDialog(self, "Añadir contacto", ["Nombre *", "Teléfono *", "Teléfono 2", "Email", "Notas"])
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        vals = d.get_values()
        d.Destroy()
        nombre = (vals.get("Nombre *") or "").strip()
        telefono = (vals.get("Teléfono *") or "").strip()
        if not nombre or not telefono:
            wx.MessageBox("Nombre y teléfono son obligatorios.", "Error", wx.OK | wx.ICON_ERROR)
            return
        id_, err = repo.create_contacto(nombre, telefono, vals.get("Teléfono 2", ""), vals.get("Email", ""), vals.get("Notas", ""))
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            self._refresh_contactos()
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
        d = SimpleDialog(self, "Editar contacto", ["Nombre *", "Teléfono *", "Teléfono 2", "Email", "Notas"], initial={"Nombre *": r["nombre"], "Teléfono *": r["telefono"], "Teléfono 2": r.get("telefono2", ""), "Email": r.get("email", ""), "Notas": r.get("notas", "")})
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            return
        vals = d.get_values()
        d.Destroy()
        nombre = (vals.get("Nombre *") or "").strip()
        telefono = (vals.get("Teléfono *") or "").strip()
        if not nombre or not telefono:
            wx.MessageBox("Nombre y teléfono son obligatorios.", "Error", wx.OK | wx.ICON_ERROR)
            return
        err = repo.update_contacto(id_, nombre, telefono, vals.get("Teléfono 2", ""), vals.get("Email", ""), vals.get("Notas", ""))
        if err:
            wx.MessageBox(err, "Error", wx.OK | wx.ICON_ERROR)
        else:
            self._refresh_contactos()
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
            self._refresh_contactos()


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
        
        widths = [70, 200, 160, 200] if len(column_headers) == 4 else [160, 400]
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
        self.SetSize((640, 500))
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
            # Label
            label = theme.create_text(panel, lbl)
            form_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT)
            
            # Control
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
        main_sizer.AddStretchSpacer()
        
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
        
        self.SetMinSize((480, 300))
        self.SetSize((520, max(350, 120 + len(field_labels) * 55)))
        self.CenterOnParent()

    def get_values(self):
        return {lbl: (self._ctrls[lbl].GetValue() if hasattr(self._ctrls[lbl], "GetValue") else self._ctrls[lbl].GetStringSelection()) for lbl in self._labels}
