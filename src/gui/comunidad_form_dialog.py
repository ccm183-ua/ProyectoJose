"""
Diálogo de formulario para crear/editar comunidades.
"""

from PySide6.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout

from src.core import db_repository as repo
from src.gui import theme
from src.gui.db_validations import run_validations, validate_cif, validate_email, validate_phone
from src.gui.quick_dialogs import QuickAdminDialog, QuickContactoDialog
from src.gui.search_widgets import CheckSelectWidget, SearchSelectWidget


class ComunidadFormDialog(QDialog):
    def __init__(self, parent, title, initial=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._initial = initial or {}
        self._all_admins = repo.get_administraciones()
        self._all_contactos = repo.get_contactos()
        self._build_ui()

    @staticmethod
    def _admin_display(a):
        return a.get("nombre") or a.get("email") or f"ID {a['id']}"

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(2)

        title_label = theme.create_title(self, self.windowTitle(), "lg")
        layout.addWidget(title_label)
        layout.addSpacing(12)

        self._ctrls = {}

        row_top = QHBoxLayout()
        row_top.setSpacing(10)
        col_nombre = QVBoxLayout()
        col_nombre.setSpacing(2)
        col_nombre.addWidget(theme.create_form_label(self, "Nombre *"))
        ctrl_n = theme.create_input(self, value=self._initial.get("nombre", "") or "")
        self._ctrls["nombre"] = ctrl_n
        col_nombre.addWidget(ctrl_n)
        row_top.addLayout(col_nombre, 3)

        col_cif = QVBoxLayout()
        col_cif.setSpacing(2)
        col_cif.addWidget(theme.create_form_label(self, "CIF"))
        ctrl_c = theme.create_input(self, value=self._initial.get("cif", "") or "")
        self._ctrls["cif"] = ctrl_c
        col_cif.addWidget(ctrl_c)
        row_top.addLayout(col_cif, 2)
        layout.addLayout(row_top)
        layout.addSpacing(6)

        for lbl_text, key, default in [
            ("Dirección", "direccion", self._initial.get("direccion", "")),
            ("Email", "email", self._initial.get("email", "")),
            ("Teléfono", "telefono", self._initial.get("telefono", "")),
        ]:
            lbl = theme.create_form_label(self, lbl_text)
            layout.addWidget(lbl)
            ctrl = theme.create_input(self, value=default or "")
            self._ctrls[key] = ctrl
            layout.addWidget(ctrl)
            layout.addSpacing(6)

        layout.addSpacing(4)
        layout.addWidget(theme.create_divider(self))
        layout.addSpacing(6)

        admin_lbl = theme.create_form_label(self, "Administración *")
        layout.addWidget(admin_lbl)

        admin_row = QHBoxLayout()
        admin_row.setSpacing(6)
        self._admin_widget = SearchSelectWidget(
            self,
            on_edit=self._on_edit_admin,
            on_delete=self._on_delete_admin,
        )
        admin_items = [(a["id"], self._admin_display(a)) for a in self._all_admins]
        self._admin_widget.set_items(admin_items)
        pre_admin = self._initial.get("administracion_id")
        if pre_admin:
            self._admin_widget.set_selected_id(pre_admin)
        admin_row.addWidget(self._admin_widget, 1)

        btn_new_admin = QPushButton("+ Nueva", self)
        btn_new_admin.setFont(theme.font_sm())
        btn_new_admin.setFixedHeight(28)
        btn_new_admin.setProperty("class", "primary")
        btn_new_admin.clicked.connect(self._on_new_admin)
        admin_row.addWidget(btn_new_admin)
        layout.addLayout(admin_row)

        layout.addSpacing(6)
        ct_lbl = theme.create_form_label(self, "Contactos")
        layout.addWidget(ct_lbl)

        ct_row = QHBoxLayout()
        ct_row.setSpacing(6)
        self._ct_widget = CheckSelectWidget(
            self,
            on_edit=self._on_edit_contacto,
            on_delete=self._on_delete_contacto,
        )
        ct_items = [(c["id"], f"{c['nombre']}  —  {c['telefono']}") for c in self._all_contactos]
        self._ct_widget.set_items(ct_items)
        self._ct_widget.set_selected_ids(set(self._initial.get("contacto_ids", [])))
        ct_row.addWidget(self._ct_widget, 1)

        btn_new_ct = QPushButton("+ Nuevo", self)
        btn_new_ct.setFont(theme.font_sm())
        btn_new_ct.setFixedHeight(28)
        btn_new_ct.setProperty("class", "primary")
        btn_new_ct.clicked.connect(self._on_new_contacto)
        ct_row.addWidget(btn_new_ct)
        layout.addLayout(ct_row)

        layout.addStretch()
        layout.addWidget(theme.create_divider(self))
        layout.addSpacing(10)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("Cancelar", self)
        btn_cancel.setFont(theme.font_base())
        btn_cancel.setFixedSize(90, 30)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addSpacing(8)
        btn_ok = QPushButton("Guardar", self)
        btn_ok.setFont(theme.get_font_medium())
        btn_ok.setFixedSize(90, 30)
        btn_ok.setProperty("class", "primary")
        btn_ok.clicked.connect(self._on_ok)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
        theme.fit_dialog(self, 420, 430)

    def _on_ok(self):
        if not self._ctrls["nombre"].text().strip():
            QMessageBox.information(self, "Aviso", "El nombre de la comunidad es obligatorio.")
            return
        if not self._admin_widget.get_selected_id():
            QMessageBox.information(self, "Aviso", "Debe seleccionar una administración.")
            return
        if not run_validations(self, [
            ("CIF", validate_cif(self._ctrls["cif"].text().strip())),
            ("Email", validate_email(self._ctrls["email"].text().strip())),
            ("Teléfono", validate_phone(self._ctrls["telefono"].text().strip())),
        ]):
            return
        self.accept()

    def _on_new_admin(self):
        d = QuickAdminDialog(self)
        if d.exec() == 1:
            new_admin = d.get_admin()
            if new_admin:
                self._all_admins = repo.get_administraciones()
                admin_items = [(a["id"], self._admin_display(a)) for a in self._all_admins]
                self._admin_widget.set_items(admin_items)
                self._admin_widget.set_selected_id(new_admin["id"])

    def _on_edit_admin(self, id_):
        data = repo.get_administracion_por_id(id_)
        if not data:
            return None
        d = QuickAdminDialog(self, edit_id=id_, initial=data)
        if d.exec() != 1:
            return None
        self._all_admins = repo.get_administraciones()
        return [(a["id"], self._admin_display(a)) for a in self._all_admins]

    def _on_delete_admin(self, id_):
        resp = QMessageBox.question(self, "Confirmar", "¿Eliminar esta administración?")
        if resp != QMessageBox.StandardButton.Yes:
            return None
        err = repo.delete_administracion(id_)
        if err:
            QMessageBox.critical(self, "Error", err)
            return None
        self._all_admins = repo.get_administraciones()
        return [(a["id"], self._admin_display(a)) for a in self._all_admins]

    def _on_new_contacto(self):
        d = QuickContactoDialog(self)
        if d.exec() == 1:
            new_ct = d.get_contacto()
            if new_ct:
                self._all_contactos = repo.get_contactos()
                ct_items = [(c["id"], f"{c['nombre']}  —  {c['telefono']}") for c in self._all_contactos]
                self._ct_widget.set_items(ct_items)
                ids = self._ct_widget.get_selected_ids()
                ids.add(new_ct["id"])
                self._ct_widget.set_selected_ids(ids)

    def _on_edit_contacto(self, id_):
        contact = next((c for c in self._all_contactos if c["id"] == id_), None)
        if not contact:
            return None
        d = QuickContactoDialog(self, edit_id=id_, initial=contact)
        if d.exec() != 1:
            return None
        self._all_contactos = repo.get_contactos()
        return [(c["id"], f"{c['nombre']}  —  {c['telefono']}") for c in self._all_contactos]

    def _on_delete_contacto(self, id_):
        resp = QMessageBox.question(self, "Confirmar", "¿Eliminar este contacto?")
        if resp != QMessageBox.StandardButton.Yes:
            return None
        err = repo.delete_contacto(id_)
        if err:
            QMessageBox.critical(self, "Error", err)
            return None
        self._all_contactos = repo.get_contactos()
        return [(c["id"], f"{c['nombre']}  —  {c['telefono']}") for c in self._all_contactos]

    def get_values(self):
        return {
            "nombre": self._ctrls["nombre"].text().strip(),
            "cif": self._ctrls["cif"].text().strip(),
            "direccion": self._ctrls["direccion"].text().strip(),
            "email": self._ctrls["email"].text().strip(),
            "telefono": self._ctrls["telefono"].text().strip(),
            "administracion_id": self._admin_widget.get_selected_id(),
            "contacto_ids": list(self._ct_widget.get_selected_ids()),
        }
