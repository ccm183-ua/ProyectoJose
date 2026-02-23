"""
Diálogos rápidos para crear/editar contactos y administraciones.
"""

from PySide6.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout

from src.core import db_repository as repo
from src.gui import theme
from src.gui.db_validations import run_validations, validate_email, validate_phone


class QuickContactoDialog(QDialog):
    def __init__(self, parent=None, edit_id=None, initial=None):
        super().__init__(parent)
        self._edit_id = edit_id
        self._initial = initial or {}
        editing = edit_id is not None
        self.setWindowTitle("Editar Contacto" if editing else "Nuevo Contacto")
        self._contacto = None
        self._build_ui()

    def _build_ui(self):
        editing = self._edit_id is not None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(2)

        title = theme.create_title(
            self, "Editar contacto" if editing else "Nuevo contacto", "lg",
        )
        layout.addWidget(title)
        layout.addSpacing(12)

        self._fields = {}
        for label_text, attr in [("Nombre *", "nombre"), ("Teléfono *", "telefono"),
                                  ("Teléfono 2", "telefono2"), ("Email", "email"),
                                  ("Notas", "notas")]:
            lbl = theme.create_form_label(self, label_text)
            layout.addWidget(lbl)
            txt = theme.create_input(self, value=self._initial.get(attr, "") or "")
            self._fields[attr] = txt
            layout.addWidget(txt)
            layout.addSpacing(6)

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
        btn_ok = QPushButton("Guardar" if editing else "Crear", self)
        btn_ok.setFont(theme.get_font_medium())
        btn_ok.setFixedSize(90, 30)
        btn_ok.setProperty("class", "primary")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_ok)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
        theme.fit_dialog(self, 380, 380)

    def _on_ok(self):
        nombre = self._fields["nombre"].text().strip()
        telefono = self._fields["telefono"].text().strip()
        telefono2 = self._fields["telefono2"].text().strip()
        email = self._fields["email"].text().strip()
        if not nombre:
            QMessageBox.information(self, "Aviso", "El nombre es obligatorio.")
            return
        if not telefono:
            QMessageBox.information(self, "Aviso", "El teléfono es obligatorio.")
            return
        if not run_validations(self, [
            ("Teléfono", validate_phone(telefono)),
            ("Teléfono 2", validate_phone(telefono2)),
            ("Email", validate_email(email)),
        ]):
            return
        notas = self._fields["notas"].text().strip()
        if self._edit_id is not None:
            err = repo.update_contacto(
                self._edit_id, nombre, telefono, telefono2, email, notas,
            )
            if err:
                QMessageBox.critical(self, "Error", f"Error:\n{err}")
                return
            self._contacto = {"id": self._edit_id, "nombre": nombre, "telefono": telefono}
        else:
            new_id, err = repo.create_contacto(nombre, telefono, telefono2, email, notas)
            if err:
                QMessageBox.critical(self, "Error", f"Error:\n{err}")
                return
            self._contacto = {"id": new_id, "nombre": nombre, "telefono": telefono}
        self.accept()

    def get_contacto(self):
        return self._contacto


class QuickAdminDialog(QDialog):
    def __init__(self, parent=None, edit_id=None, initial=None):
        super().__init__(parent)
        self._edit_id = edit_id
        self._initial = initial or {}
        editing = edit_id is not None
        self.setWindowTitle("Editar Administración" if editing else "Nueva Administración")
        self._admin = None
        self._build_ui()

    def _build_ui(self):
        editing = self._edit_id is not None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(2)

        title = theme.create_title(
            self, "Editar administración" if editing else "Nueva administración", "lg",
        )
        layout.addWidget(title)
        layout.addSpacing(12)

        self._fields = {}
        for label_text, attr in [("Nombre *", "nombre"), ("Email", "email"),
                                  ("Teléfono", "telefono"), ("Dirección", "direccion")]:
            lbl = theme.create_form_label(self, label_text)
            layout.addWidget(lbl)
            txt = theme.create_input(self, value=self._initial.get(attr, "") or "")
            self._fields[attr] = txt
            layout.addWidget(txt)
            layout.addSpacing(6)

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
        btn_ok = QPushButton("Guardar" if editing else "Crear", self)
        btn_ok.setFont(theme.get_font_medium())
        btn_ok.setFixedSize(90, 30)
        btn_ok.setProperty("class", "primary")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._on_ok)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)
        theme.fit_dialog(self, 380, 330)

    def _on_ok(self):
        nombre = self._fields["nombre"].text().strip()
        email = self._fields["email"].text().strip()
        telefono = self._fields["telefono"].text().strip()
        direccion = self._fields["direccion"].text().strip()
        if not nombre:
            QMessageBox.information(self, "Aviso", "El nombre es obligatorio.")
            return
        if not run_validations(self, [
            ("Email", validate_email(email)),
            ("Teléfono", validate_phone(telefono)),
        ]):
            return
        if self._edit_id is not None:
            err = repo.update_administracion(
                self._edit_id, nombre, email, telefono, direccion,
            )
            if err:
                QMessageBox.critical(self, "Error", f"Error:\n{err}")
                return
            self._admin = {
                "id": self._edit_id, "nombre": nombre,
                "email": email, "telefono": telefono, "direccion": direccion,
            }
        else:
            new_id, err = repo.create_administracion(nombre, email, telefono, direccion)
            if err:
                QMessageBox.critical(self, "Error", f"Error:\n{err}")
                return
            self._admin = {
                "id": new_id, "nombre": nombre,
                "email": email, "telefono": telefono, "direccion": direccion,
            }
        self.accept()

    def get_admin(self):
        return self._admin
