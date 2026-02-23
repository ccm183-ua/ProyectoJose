"""
Ventana principal de gestión de la base de datos (PySide6).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QHeaderView, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from src.core import db_repository as repo
from src.gui import theme
from src.gui.admin_form_dialog import AdminFormDialog
from src.gui.comunidad_form_dialog import ComunidadFormDialog
from src.gui.ficha_dialog import FichaDialog


class DBManagerFrame(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Base de Datos - cubiApp")
        self.resize(1100, 750)
        self._admin_rows = []
        self._com_rows = []
        self._build_ui()
        self._refresh_all()
        self._center()

    def _center(self):
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )

    def _create_toolbar_button(self, parent, label, handler, primary=False):
        btn = QPushButton(label, parent)
        btn.setFont(theme.font_base())
        btn.setFixedHeight(38)
        if primary:
            btn.setProperty("class", "primary")
        btn.clicked.connect(handler)
        return btn

    def _create_search_box(self, parent, hint, on_change):
        search_widget = QWidget(parent)
        sz = QHBoxLayout(search_widget)
        sz.setContentsMargins(0, 0, 0, 0)

        label = theme.create_text(search_widget, "Buscar:")
        sz.addWidget(label)

        search = QLineEdit(search_widget)
        search.setFont(theme.font_base())
        search.setPlaceholderText(hint)
        search.setMinimumHeight(32)
        search.textChanged.connect(on_change)
        sz.addWidget(search, 1)

        return search_widget, search

    def _build_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, 0)

        top_row = QHBoxLayout()
        title = theme.create_title(header, "Base de Datos", "2xl")
        top_row.addWidget(title, 1)

        btn_refresh = QPushButton("\u27F3 Actualizar", header)
        btn_refresh.setFont(theme.font_base())
        btn_refresh.setFixedHeight(36)
        btn_refresh.setToolTip("Recargar todas las tablas desde la base de datos")
        btn_refresh.clicked.connect(self._refresh_all)
        top_row.addWidget(btn_refresh)

        header_layout.addLayout(top_row)

        subtitle = theme.create_text(header, "Gestiona administraciones, comunidades y contactos")
        header_layout.addWidget(subtitle)
        header_layout.addSpacing(theme.SPACE_MD)

        main_layout.addWidget(header)

        self.notebook = QTabWidget(central)
        self.notebook.setFont(theme.font_base())

        # === PESTAÑA ADMINISTRACIONES ===
        self.panel_admin = QWidget()
        sza = QVBoxLayout(self.panel_admin)
        sza.setContentsMargins(theme.SPACE_MD, theme.SPACE_MD, theme.SPACE_MD, 0)

        search_a, self.search_admin = self._create_search_box(
            self.panel_admin, "Nombre, email, teléfono, dirección o contactos", self._on_search_admin,
        )
        sza.addWidget(search_a)

        self.table_admin = QTableWidget(self.panel_admin)
        admin_cols = [("Nombre", 220), ("Dirección", 200), ("Email", 200), ("Teléfono", 130), ("Contactos", 200)]
        self.table_admin.setColumnCount(len(admin_cols))
        self.table_admin.setHorizontalHeaderLabels([c[0] for c in admin_cols])
        for i, (_, w) in enumerate(admin_cols):
            self.table_admin.setColumnWidth(i, w)
        self.table_admin.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_admin.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_admin.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table_admin.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_admin.setAlternatingRowColors(True)
        self.table_admin.verticalHeader().setVisible(False)
        self.table_admin.doubleClicked.connect(self._ver_ficha_admin)
        sza.addWidget(self.table_admin, 1)

        toolbar_a = QWidget(self.panel_admin)
        toolbar_a.setProperty("class", "toolbar")
        tb_la = QHBoxLayout(toolbar_a)
        tb_la.setContentsMargins(theme.SPACE_LG, theme.SPACE_SM, theme.SPACE_LG, theme.SPACE_SM)
        for label, handler, primary in [
            ("+ Añadir", self._add_admin, True),
            ("Editar", self._edit_admin, False),
            ("Eliminar", self._delete_admin, False),
            ("Ver ficha", self._ver_ficha_admin, False),
        ]:
            btn = self._create_toolbar_button(toolbar_a, label, handler, primary)
            tb_la.addWidget(btn)
        tb_la.addStretch()
        sza.addWidget(toolbar_a)

        self.notebook.addTab(self.panel_admin, "  Administraciones  ")

        # === PESTAÑA COMUNIDADES ===
        self.panel_com = QWidget()
        szc = QVBoxLayout(self.panel_com)
        szc.setContentsMargins(theme.SPACE_MD, theme.SPACE_MD, theme.SPACE_MD, 0)

        search_c, self.search_com = self._create_search_box(
            self.panel_com, "Nombre, CIF, dirección, email, teléfono, administración o contactos", self._on_search_com,
        )
        szc.addWidget(search_c)

        self.table_com = QTableWidget(self.panel_com)
        com_cols = [("Nombre", 170), ("CIF", 100), ("Dirección", 150), ("Email", 160),
                    ("Teléfono", 110), ("Administración", 150), ("Contactos", 170)]
        self.table_com.setColumnCount(len(com_cols))
        self.table_com.setHorizontalHeaderLabels([c[0] for c in com_cols])
        for i, (_, w) in enumerate(com_cols):
            self.table_com.setColumnWidth(i, w)
        self.table_com.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_com.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_com.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table_com.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_com.setAlternatingRowColors(True)
        self.table_com.verticalHeader().setVisible(False)
        self.table_com.doubleClicked.connect(self._ver_ficha_comunidad)
        szc.addWidget(self.table_com, 1)

        toolbar_c = QWidget(self.panel_com)
        toolbar_c.setProperty("class", "toolbar")
        tb_lc = QHBoxLayout(toolbar_c)
        tb_lc.setContentsMargins(theme.SPACE_LG, theme.SPACE_SM, theme.SPACE_LG, theme.SPACE_SM)
        for label, handler, primary in [
            ("+ Añadir", self._add_comunidad, True),
            ("Editar", self._edit_comunidad, False),
            ("Eliminar", self._delete_comunidad, False),
            ("Ver ficha", self._ver_ficha_comunidad, False),
        ]:
            btn = self._create_toolbar_button(toolbar_c, label, handler, primary)
            tb_lc.addWidget(btn)
        tb_lc.addStretch()
        szc.addWidget(toolbar_c)

        self.notebook.addTab(self.panel_com, "  Comunidades  ")

        main_layout.addWidget(self.notebook, 1)
        self.setCentralWidget(central)

    # ── refresh ──

    def _refresh_all(self):
        self._refresh_admin()
        self._refresh_comunidades()

    def _refresh_admin(self):
        self._admin_rows = repo.get_administraciones_para_tabla()
        self._populate_admin_table()

    def _refresh_comunidades(self):
        self._com_rows = repo.get_comunidades_para_tabla()
        self._populate_com_table()

    # ── filter ──

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

    def _populate_admin_table(self):
        rows = self._admin_rows or []
        query = self.search_admin.text() if hasattr(self, "search_admin") else ""
        rows = self._filter_rows(rows, ["nombre", "email", "telefono", "direccion", "contactos"], query)
        self.table_admin.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table_admin.setItem(i, 0, QTableWidgetItem(r["nombre"] or "—"))
            self.table_admin.setItem(i, 1, QTableWidgetItem(r["direccion"] or "—"))
            self.table_admin.setItem(i, 2, QTableWidgetItem(r["email"] or "—"))
            self.table_admin.setItem(i, 3, QTableWidgetItem(r["telefono"] or "—"))
            self.table_admin.setItem(i, 4, QTableWidgetItem(r["contactos"]))
            for col in range(5):
                item = self.table_admin.item(i, col)
                if item:
                    item.setData(Qt.ItemDataRole.UserRole, int(r["id"]))

    def _populate_com_table(self):
        rows = self._com_rows or []
        query = self.search_com.text() if hasattr(self, "search_com") else ""
        rows = self._filter_rows(
            rows, ["nombre", "cif", "direccion", "telefono", "email", "nombre_administracion", "contactos"], query,
        )
        self.table_com.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.table_com.setItem(i, 0, QTableWidgetItem(r["nombre"]))
            self.table_com.setItem(i, 1, QTableWidgetItem(r.get("cif", "") or "—"))
            self.table_com.setItem(i, 2, QTableWidgetItem(r.get("direccion", "") or "—"))
            self.table_com.setItem(i, 3, QTableWidgetItem(r.get("email", "") or "—"))
            self.table_com.setItem(i, 4, QTableWidgetItem(r.get("telefono", "") or "—"))
            self.table_com.setItem(i, 5, QTableWidgetItem(r["nombre_administracion"]))
            self.table_com.setItem(i, 6, QTableWidgetItem(r["contactos"]))
            for col in range(7):
                item = self.table_com.item(i, col)
                if item:
                    item.setData(Qt.ItemDataRole.UserRole, int(r["id"]))

    def _on_search_admin(self):
        self._populate_admin_table()

    def _on_search_com(self):
        self._populate_com_table()

    # ── helpers ──

    def _get_selected_id(self, table: QTableWidget):
        row = table.currentRow()
        if row < 0:
            return None
        item = table.item(row, 0)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    # ── fichas ──

    def _ver_ficha_admin(self):
        id_ = self._get_selected_id(self.table_admin)
        if id_ is None:
            QMessageBox.information(self, "Ver ficha", "Selecciona una fila.")
            return
        d = FichaDialog(self, "admin", id_, on_edit=self._ficha_editar)
        d.finished.connect(lambda: self._on_ficha_closed(d))
        d.show()

    def _ver_ficha_comunidad(self):
        id_ = self._get_selected_id(self.table_com)
        if id_ is None:
            QMessageBox.information(self, "Ver ficha", "Selecciona una fila.")
            return
        d = FichaDialog(self, "comunidad", id_, on_edit=self._ficha_editar)
        d.finished.connect(lambda: self._on_ficha_closed(d))
        d.show()

    def _on_ficha_closed(self, dialog):
        if dialog.was_edited():
            self._refresh_all()

    def _ficha_editar(self, entity_type, entity_id):
        if entity_type == "admin":
            self._edit_admin_by_id(entity_id)
        else:
            self._edit_comunidad_by_id(entity_id)

    # ── admin CRUD ──

    def _add_admin(self):
        d = AdminFormDialog(self, "Añadir administración")
        if d.exec() != 1:
            return
        vals = d.get_values()
        nombre = vals["nombre"]
        if not nombre:
            QMessageBox.critical(self, "Error", "El nombre es obligatorio.")
            return
        id_, err = repo.create_administracion(nombre, vals["email"], vals["telefono"], vals["direccion"])
        if err:
            QMessageBox.critical(self, "Error", err)
        else:
            if vals["contacto_ids"]:
                repo.set_contactos_para_administracion(id_, vals["contacto_ids"])
            self._refresh_all()
            QMessageBox.information(self, "OK", "Administración creada.")

    def _edit_admin(self):
        id_ = self._get_selected_id(self.table_admin)
        if id_ is None:
            QMessageBox.information(self, "Editar", "Selecciona una fila.")
            return
        self._edit_admin_by_id(id_)

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
        if d.exec() != 1:
            return
        vals = d.get_values()
        nombre = vals["nombre"]
        if not nombre:
            QMessageBox.critical(self, "Error", "El nombre es obligatorio.")
            return
        err = repo.update_administracion(id_, nombre, vals["email"], vals["telefono"], vals["direccion"])
        if err:
            QMessageBox.critical(self, "Error", err)
        else:
            repo.set_contactos_para_administracion(id_, vals["contacto_ids"])
            self._refresh_all()
            QMessageBox.information(self, "OK", "Guardado.")

    def _delete_admin(self):
        id_ = self._get_selected_id(self.table_admin)
        if id_ is None:
            QMessageBox.information(self, "Eliminar", "Selecciona una fila.")
            return
        resp = QMessageBox.question(self, "Confirmar", "¿Eliminar esta administración?")
        if resp != QMessageBox.StandardButton.Yes:
            return
        err = repo.delete_administracion(id_)
        if err:
            QMessageBox.critical(self, "Error", err)
        else:
            self._refresh_all()

    # ── comunidad CRUD ──

    def _add_comunidad(self):
        admins = repo.get_administraciones()
        if not admins:
            QMessageBox.information(self, "Añadir comunidad", "Crea antes al menos una administración.")
            return
        d = ComunidadFormDialog(self, "Añadir comunidad")
        if d.exec() != 1:
            return
        vals = d.get_values()
        nombre = vals["nombre"]
        if not nombre:
            QMessageBox.critical(self, "Error", "El nombre es obligatorio.")
            return
        admin_id = vals.get("administracion_id")
        if not admin_id:
            QMessageBox.critical(self, "Error", "La administración es obligatoria.")
            return
        id_, err = repo.create_comunidad(
            nombre, admin_id, cif=vals.get("cif", ""),
            direccion=vals.get("direccion", ""), email=vals.get("email", ""),
            telefono=vals.get("telefono", ""),
        )
        if err:
            QMessageBox.critical(self, "Error", err)
        else:
            if vals["contacto_ids"]:
                repo.set_contactos_para_comunidad(id_, vals["contacto_ids"])
            self._refresh_all()
            QMessageBox.information(self, "OK", "Comunidad creada.")

    def _edit_comunidad(self):
        id_ = self._get_selected_id(self.table_com)
        if id_ is None:
            QMessageBox.information(self, "Editar", "Selecciona una fila.")
            return
        self._edit_comunidad_by_id(id_)

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
        if d.exec() != 1:
            return
        vals = d.get_values()
        nombre = vals["nombre"]
        if not nombre:
            QMessageBox.critical(self, "Error", "El nombre es obligatorio.")
            return
        admin_id = vals.get("administracion_id")
        if not admin_id:
            QMessageBox.critical(self, "Error", "La administración es obligatoria.")
            return
        err = repo.update_comunidad(
            id_, nombre, admin_id, cif=vals.get("cif", ""),
            direccion=vals.get("direccion", ""), email=vals.get("email", ""),
            telefono=vals.get("telefono", ""),
        )
        if err:
            QMessageBox.critical(self, "Error", err)
        else:
            repo.set_contactos_para_comunidad(id_, vals.get("contacto_ids", []))
            self._refresh_all()
            QMessageBox.information(self, "OK", "Guardado.")

    def _delete_comunidad(self):
        id_ = self._get_selected_id(self.table_com)
        if id_ is None:
            QMessageBox.information(self, "Eliminar", "Selecciona una fila.")
            return
        resp = QMessageBox.question(self, "Confirmar", "¿Eliminar esta comunidad?")
        if resp != QMessageBox.StandardButton.Yes:
            return
        err = repo.delete_comunidad(id_)
        if err:
            QMessageBox.critical(self, "Error", err)
        else:
            self._refresh_all()
