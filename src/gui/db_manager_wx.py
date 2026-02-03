"""
Ventana de gestión de la base de datos (wxPython).
"""

import wx
from src.core import db_repository as repo


class DBManagerFrame(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title="Gestionar base de datos", size=(900, 520))
        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        self.notebook = wx.Notebook(self)
        # Administración
        self.panel_admin = wx.Panel(self.notebook)
        self.list_admin = wx.ListCtrl(self.panel_admin, style=wx.LC_REPORT)
        self.list_admin.AppendColumn("ID", width=40)
        self.list_admin.AppendColumn("Email", width=180)
        self.list_admin.AppendColumn("Teléfono", width=120)
        self.list_admin.AppendColumn("Dirección", width=180)
        self.list_admin.AppendColumn("Contactos", width=200)
        sza = wx.BoxSizer(wx.VERTICAL)
        sza.Add(self.list_admin, 1, wx.EXPAND)
        btn_a = wx.BoxSizer(wx.HORIZONTAL)
        for lbl, handler in [("Actualizar", self._refresh_admin), ("Añadir", self._add_admin), ("Editar", self._edit_admin), ("Eliminar", self._delete_admin)]:
            b = wx.Button(self.panel_admin, label=lbl)
            b.Bind(wx.EVT_BUTTON, lambda e, h=handler: h())
            btn_a.Add(b, 0, wx.RIGHT, 4)
        sza.Add(btn_a, 0, wx.TOP, 4)
        self.panel_admin.SetSizer(sza)
        self.notebook.AddPage(self.panel_admin, "Administración")

        # Comunidad
        self.panel_com = wx.Panel(self.notebook)
        self.list_com = wx.ListCtrl(self.panel_com, style=wx.LC_REPORT)
        self.list_com.AppendColumn("ID", width=40)
        self.list_com.AppendColumn("Nombre", width=150)
        self.list_com.AppendColumn("Administración", width=150)
        self.list_com.AppendColumn("Contactos", width=200)
        szc = wx.BoxSizer(wx.VERTICAL)
        szc.Add(self.list_com, 1, wx.EXPAND)
        btn_c = wx.BoxSizer(wx.HORIZONTAL)
        for lbl, handler in [("Actualizar", self._refresh_comunidades), ("Añadir", self._add_comunidad), ("Editar", self._edit_comunidad), ("Eliminar", self._delete_comunidad)]:
            b = wx.Button(self.panel_com, label=lbl)
            b.Bind(wx.EVT_BUTTON, lambda e, h=handler: h())
            btn_c.Add(b, 0, wx.RIGHT, 4)
        szc.Add(btn_c, 0, wx.TOP, 4)
        self.panel_com.SetSizer(szc)
        self.notebook.AddPage(self.panel_com, "Comunidad")

        # Contacto
        self.panel_cont = wx.Panel(self.notebook)
        self.list_cont = wx.ListCtrl(self.panel_cont, style=wx.LC_REPORT)
        self.list_cont.AppendColumn("ID", width=40)
        self.list_cont.AppendColumn("Nombre", width=120)
        self.list_cont.AppendColumn("Teléfono", width=120)
        self.list_cont.AppendColumn("Email", width=180)
        szct = wx.BoxSizer(wx.VERTICAL)
        szct.Add(self.list_cont, 1, wx.EXPAND)
        btn_ct = wx.BoxSizer(wx.HORIZONTAL)
        for lbl, handler in [("Actualizar", self._refresh_contactos), ("Añadir", self._add_contacto), ("Editar", self._edit_contacto), ("Eliminar", self._delete_contacto)]:
            b = wx.Button(self.panel_cont, label=lbl)
            b.Bind(wx.EVT_BUTTON, lambda e, h=handler: h())
            btn_ct.Add(b, 0, wx.RIGHT, 4)
        szct.Add(btn_ct, 0, wx.TOP, 4)
        self.panel_cont.SetSizer(szct)
        self.notebook.AddPage(self.panel_cont, "Contacto")

        sz = wx.BoxSizer(wx.VERTICAL)
        sz.Add(self.notebook, 1, wx.EXPAND)
        self.SetSizer(sz)

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
            self.list_cont.Append([str(r["id"]), r["nombre"], r["telefono"], r["email"] or "—"])

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


class SimpleDialog(wx.Dialog):
    def __init__(self, parent, title, field_labels, initial=None, choices=None):
        super().__init__(parent, title=title, size=(400, 320))
        self._labels = field_labels
        self._initial = initial or {}
        self._choices = choices or {}
        self._ctrls = {}
        panel = wx.Panel(self)
        sizer = wx.FlexGridSizer(2, (5, 5))
        sizer.AddGrowableCol(1, 1)
        for lbl in field_labels:
            sizer.Add(wx.StaticText(panel, label=lbl), 0, wx.ALIGN_CENTER_VERTICAL)
            if lbl in self._choices:
                c = wx.ComboBox(panel, value=self._initial.get(lbl, ""), choices=self._choices[lbl], style=wx.CB_READONLY)
            else:
                c = wx.TextCtrl(panel, value=self._initial.get(lbl, ""), size=(260, -1))
            self._ctrls[lbl] = c
            sizer.Add(c, 0, wx.EXPAND)
        panel.SetSizer(sizer)
        btn_sizer = wx.StdDialogButtonSizer()
        btn_sizer.AddButton(wx.Button(panel, wx.ID_OK, "Aceptar"))
        btn_sizer.AddButton(wx.Button(panel, wx.ID_CANCEL, "Cancelar"))
        btn_sizer.Realize()
        sizer.Add((0, 0))
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT)
        self.Fit()

    def get_values(self):
        return {lbl: (self._ctrls[lbl].GetValue() if hasattr(self._ctrls[lbl], "GetValue") else self._ctrls[lbl].GetStringSelection()) for lbl in self._labels}
