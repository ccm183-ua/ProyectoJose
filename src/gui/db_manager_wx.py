"""
Ventana de gestión de la base de datos (PySide6).
"""

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from src.core import db_repository as repo
from src.gui import theme


# ---------------------------------------------------------------------------
# Popup replacements (PySide6 uses QComboBox + QLineEdit search instead
# of wx.ComboPopup). For the multi-select "contactos" picker we use a
# QLineEdit (display only) + QPushButton that opens a small QDialog.
# ---------------------------------------------------------------------------

class SearchSelectWidget(QWidget):
    """QLineEdit (readonly display) + dropdown button for single-select with search."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[tuple] = []
        self._selected_id = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._display = QLineEdit(self)
        self._display.setReadOnly(True)
        self._display.setFont(theme.font_base())
        layout.addWidget(self._display, 1)

        btn = QPushButton("\u25BC", self)
        btn.setFixedSize(28, 28)
        btn.setProperty("class", "dropdown")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._open_popup)
        layout.addWidget(btn)

    def set_items(self, items: list[tuple]):
        self._items = list(items)

    def get_selected_id(self):
        return self._selected_id

    def set_selected_id(self, id_):
        self._selected_id = id_
        self._update_display()

    def _update_display(self):
        for id_, disp in self._items:
            if id_ == self._selected_id:
                self._display.setText(disp)
                return
        self._display.setText("")

    def _open_popup(self):
        dlg = _SearchSelectDialog(self, self._items, self._selected_id)
        if dlg.exec() == 1:
            self._selected_id = dlg.get_selected_id()
            self._update_display()


class _SearchSelectDialog(QDialog):
    def __init__(self, parent, items, current_id):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar")
        self._items = items
        self._visible = list(items)
        self._selected_id = current_id

        layout = QVBoxLayout(self)
        layout.setSpacing(theme.SPACE_SM)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Buscar...")
        self._search.setFont(theme.font_base())
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._list = QListWidget(self)
        self._list.setFont(theme.font_base())
        self._list.doubleClicked.connect(self._on_select)
        layout.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn = QPushButton("Seleccionar", self)
        btn.setFont(theme.font_base())
        btn.setFixedHeight(32)
        btn.setProperty("class", "primary")
        btn.clicked.connect(self._on_select)
        btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self.resize(350, 300)
        self._filter()

    def _filter(self):
        self._list.clear()
        q = self._search.text().strip().lower()
        self._visible = []
        for id_, disp in self._items:
            if q and q not in disp.lower():
                continue
            self._visible.append((id_, disp))
            self._list.addItem(disp)
        if self._selected_id:
            for i, (id_, _) in enumerate(self._visible):
                if id_ == self._selected_id:
                    self._list.setCurrentRow(i)
                    break

    def _on_select(self):
        row = self._list.currentRow()
        if 0 <= row < len(self._visible):
            self._selected_id = self._visible[row][0]
            self.accept()

    def get_selected_id(self):
        return self._selected_id


class CheckSelectWidget(QWidget):
    """QLineEdit (readonly display) + button that opens multi-select dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[tuple] = []
        self._selected_ids: set = set()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._display = QLineEdit(self)
        self._display.setReadOnly(True)
        self._display.setFont(theme.font_base())
        self._display.setPlaceholderText("Seleccionar contactos...")
        layout.addWidget(self._display, 1)

        btn = QPushButton("\u25BC", self)
        btn.setFixedSize(28, 28)
        btn.setProperty("class", "dropdown")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._open_popup)
        layout.addWidget(btn)

    def set_items(self, items):
        self._items = list(items)

    def get_selected_ids(self):
        return set(self._selected_ids)

    def set_selected_ids(self, ids):
        self._selected_ids = set(ids)
        self._update_display()

    def _update_display(self):
        n = len(self._selected_ids)
        if n == 0:
            self._display.setText("Seleccionar contactos...")
        elif n == 1:
            for id_, disp in self._items:
                if id_ in self._selected_ids:
                    self._display.setText(disp)
                    return
        else:
            self._display.setText(f"{n} contactos seleccionados")

    def _open_popup(self):
        dlg = _CheckSelectDialog(self, self._items, self._selected_ids)
        if dlg.exec() == 1:
            self._selected_ids = dlg.get_selected_ids()
            self._update_display()


class _CheckSelectDialog(QDialog):
    def __init__(self, parent, items, selected_ids):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar contactos")
        self._items = items
        self._visible = list(items)
        self._selected_ids = set(selected_ids)

        layout = QVBoxLayout(self)
        layout.setSpacing(theme.SPACE_SM)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Buscar...")
        self._search.setFont(theme.font_base())
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._list = QListWidget(self)
        self._list.setFont(theme.font_base())
        layout.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn = QPushButton("Aceptar", self)
        btn.setFont(theme.font_base())
        btn.setFixedHeight(32)
        btn.setProperty("class", "primary")
        btn.clicked.connect(self.accept)
        btn_row.addWidget(btn)
        layout.addLayout(btn_row)

        self.resize(350, 320)
        self._filter()

    def _filter(self):
        self._list.clear()
        q = self._search.text().strip().lower()
        self._visible = []
        selected_first, others = [], []
        for id_, disp in self._items:
            if q and q not in disp.lower():
                continue
            if id_ in self._selected_ids:
                selected_first.append((id_, disp))
            else:
                others.append((id_, disp))
        for id_, disp in selected_first + others:
            self._visible.append((id_, disp))
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(disp)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if id_ in self._selected_ids else Qt.CheckState.Unchecked)
            self._list.addItem(item)
        self._list.itemChanged.connect(self._on_check)

    def _on_check(self, item):
        row = self._list.row(item)
        if 0 <= row < len(self._visible):
            id_ = self._visible[row][0]
            if item.checkState() == Qt.CheckState.Checked:
                self._selected_ids.add(id_)
            else:
                self._selected_ids.discard(id_)

    def get_selected_ids(self):
        return set(self._selected_ids)


# ---------------------------------------------------------------------------
# Main DB Manager Frame
# ---------------------------------------------------------------------------

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

        # === HEADER ===
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

        # === NOTEBOOK ===
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


# ---------------------------------------------------------------------------
# Ficha detallada de una entidad (administración o comunidad)
# ---------------------------------------------------------------------------

class FichaDialog(QDialog):

    def __init__(self, parent, entity_type: str, entity_id: int, on_edit=None):
        title = "Ficha de Administración" if entity_type == "admin" else "Ficha de Comunidad"
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._entity_type = entity_type
        self._entity_id = entity_id
        self._on_edit = on_edit
        self._edited = False
        self._build_ui()

    def was_edited(self) -> bool:
        return self._edited

    # --- helpers visuales ---

    @staticmethod
    def _make_card(parent):
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        card = QFrame(parent)
        card.setStyleSheet(
            "QFrame { background: #ffffff; border: 1px solid #e8ecf1; border-radius: 8px; }"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 2)
        shadow.setColor(theme.qcolor("#00000018"))
        card.setGraphicsEffect(shadow)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(6)
        return card, cl

    @staticmethod
    def _section_label(parent, text):
        lbl = QLabel(text, parent)
        lbl.setFont(theme.create_font(9, theme.QFont.Weight.Bold))
        lbl.setStyleSheet(
            f"color: {theme.ACCENT_DARK}; background: transparent;"
            "border: none; letter-spacing: 1px;"
        )
        return lbl

    @staticmethod
    def _field(parent, layout, label, value):
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(label, parent)
        lbl.setFont(theme.font_sm())
        lbl.setFixedWidth(75)
        lbl.setStyleSheet(
            f"color: {theme.TEXT_SECONDARY}; background: {theme.BG_SECONDARY};"
            f"border: 1px solid {theme.BORDER_LIGHT}; border-radius: 3px;"
            "padding: 2px 6px;"
        )
        row.addWidget(lbl)
        val = QLabel(value or "—", parent)
        val.setFont(theme.font_base())
        val.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent; border: none;")
        val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        val.setWordWrap(True)
        row.addWidget(val, 1)
        layout.addLayout(row)

    def _person_entry(self, parent, layout, name, fields, notas=None):
        n = QLabel(name or "—", parent)
        n.setFont(theme.get_font_bold(11))
        n.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent; border: none;")
        n.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(n)

        for lbl_t, val_t in fields:
            if not val_t:
                continue
            self._field(parent, layout, lbl_t, val_t)

        if notas:
            nota = QLabel(f"Nota: {notas}", parent)
            nota.setFont(theme.font_xs())
            nota.setStyleSheet(
                f"color: {theme.TEXT_TERTIARY}; background: transparent;"
                "border: none; font-style: italic;"
            )
            nota.setWordWrap(True)
            layout.addWidget(nota)

        layout.addSpacing(6)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setStyleSheet("QDialog { background: #f0f2f5; }")

        if self._entity_type == "admin":
            data = repo.get_administracion_por_id(self._entity_id)
            contactos = repo.get_contactos_por_administracion_id(self._entity_id)
        else:
            data = repo.get_comunidad_por_id(self._entity_id)
            contactos = repo.get_contactos_por_comunidad_id(self._entity_id)

        if not data:
            lbl = QLabel("Entidad no encontrada.", self)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFont(theme.font_base())
            root.addWidget(lbl, 1)
            return

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # --- Card cabecera ---
        hdr_card, hdr_lay = self._make_card(page)
        tipo_text = "Administración" if self._entity_type == "admin" else "Comunidad"
        tipo_lbl = QLabel(tipo_text.upper(), hdr_card)
        tipo_lbl.setFont(theme.create_font(8, theme.QFont.Weight.Bold))
        tipo_lbl.setStyleSheet(
            f"color: {theme.ACCENT_PRIMARY}; background: {theme.ACCENT_LIGHT};"
            "border: none; border-radius: 3px; padding: 2px 8px; letter-spacing: 1px;"
        )
        tipo_lbl.setFixedWidth(tipo_lbl.sizeHint().width() + 16)
        hdr_lay.addWidget(tipo_lbl)

        name_lbl = QLabel(data.get("nombre", "—"), hdr_card)
        name_lbl.setFont(theme.get_font_bold(15))
        name_lbl.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent; border: none;")
        name_lbl.setWordWrap(True)
        name_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        hdr_lay.addWidget(name_lbl)
        layout.addWidget(hdr_card)

        # --- Card información ---
        info_card, info_lay = self._make_card(page)
        info_lay.addWidget(self._section_label(info_card, "INFORMACIÓN"))

        if self._entity_type == "admin":
            fields = [("Email", data.get("email")), ("Teléfono", data.get("telefono")),
                       ("Dirección", data.get("direccion"))]
        else:
            fields = [("CIF", data.get("cif")), ("Dirección", data.get("direccion")),
                       ("Email", data.get("email")), ("Teléfono", data.get("telefono"))]

        for lbl_t, val_t in fields:
            self._field(info_card, info_lay, lbl_t, val_t)
        layout.addWidget(info_card)

        # --- Card administración (solo comunidad) ---
        if self._entity_type != "admin":
            admin_card, admin_lay = self._make_card(page)
            admin_lay.addWidget(self._section_label(admin_card, "ADMINISTRACIÓN"))
            admin_data = None
            if data.get("administracion_id"):
                admin_data = repo.get_administracion_por_id(data["administracion_id"])
            if admin_data:
                self._person_entry(admin_card, admin_lay, admin_data.get("nombre"), [
                    ("Email", admin_data.get("email")),
                    ("Teléfono", admin_data.get("telefono")),
                    ("Dirección", admin_data.get("direccion")),
                ])
            else:
                empty = QLabel("Sin administración asignada.", admin_card)
                empty.setFont(theme.font_sm())
                empty.setStyleSheet(f"color: {theme.TEXT_TERTIARY}; background: transparent; border: none;")
                admin_lay.addWidget(empty)
            layout.addWidget(admin_card)

        # --- Card contactos ---
        ct_card, ct_lay = self._make_card(page)
        ct_lay.addWidget(self._section_label(ct_card, f"CONTACTOS ({len(contactos)})"))
        if contactos:
            for c in contactos:
                self._person_entry(ct_card, ct_lay, c.get("nombre"), [
                    ("Teléfono", c.get("telefono")),
                    ("Teléfono 2", c.get("telefono2")),
                    ("Email", c.get("email")),
                ], notas=c.get("notas"))
        else:
            empty = QLabel("No hay contactos asociados.", ct_card)
            empty.setFont(theme.font_sm())
            empty.setStyleSheet(f"color: {theme.TEXT_TERTIARY}; background: transparent; border: none;")
            ct_lay.addWidget(empty)
        layout.addWidget(ct_card)

        layout.addStretch()
        scroll.setWidget(page)
        root.addWidget(scroll, 1)

        # --- Botones ---
        btn_bar = QWidget(self)
        btn_bar.setStyleSheet("QWidget { background: #ffffff; border-top: 1px solid #e2e8f0; }")
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(16, 8, 16, 8)
        btn_layout.addStretch()
        if self._on_edit:
            btn_edit = QPushButton("Editar", btn_bar)
            btn_edit.setFont(theme.font_base())
            btn_edit.setFixedSize(80, 28)
            btn_edit.setStyleSheet(
                f"QPushButton {{ background: #ffffff; color: {theme.TEXT_PRIMARY};"
                f"border: 1px solid {theme.BORDER_LIGHT}; border-radius: 6px; }}"
                f"QPushButton:hover {{ background: {theme.BG_SECONDARY}; border-color: {theme.BORDER_DEFAULT}; }}"
            )
            btn_edit.clicked.connect(self._on_edit_click)
            btn_layout.addWidget(btn_edit)
            btn_layout.addSpacing(8)
        btn_close = QPushButton("Cerrar", btn_bar)
        btn_close.setFont(theme.font_base())
        btn_close.setFixedSize(80, 28)
        btn_close.setStyleSheet(
            f"QPushButton {{ background: {theme.ACCENT_PRIMARY}; color: #ffffff;"
            "border: none; border-radius: 6px; }}"
            f"QPushButton:hover {{ background: {theme.ACCENT_DARK}; }}"
        )
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        root.addWidget(btn_bar)

        theme.fit_dialog(self, 480, 500)

    def _on_edit_click(self):
        if self._on_edit:
            self._on_edit(self._entity_type, self._entity_id)
            self._edited = True
            self.accept()


# ---------------------------------------------------------------------------
# Validaciones
# ---------------------------------------------------------------------------

_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_RE_PHONE_CHARS = re.compile(r"^[\d\s+\-().]+$")
_RE_CIF = re.compile(r"^[A-Za-z]\d{7}[\dA-Za-z]$|^\d{8}[A-Za-z]$")


def _validate_phone(value: str) -> str | None:
    """Devuelve mensaje de error o None si válido. Acepta vacío."""
    if not value:
        return None
    if not _RE_PHONE_CHARS.match(value):
        return "El teléfono contiene caracteres no válidos."
    digits = re.sub(r"\D", "", value)
    if len(digits) < 9:
        return "El teléfono debe tener al menos 9 dígitos."
    return None


def _validate_email(value: str) -> str | None:
    if not value:
        return None
    if not _RE_EMAIL.match(value):
        return "El formato de email no es válido (ej: usuario@dominio.com)."
    return None


def _validate_cif(value: str) -> str | None:
    if not value:
        return None
    clean = value.replace("-", "").replace(" ", "")
    if not _RE_CIF.match(clean):
        return "El CIF/NIF no parece válido (ej: B12345678 o 12345678A)."
    return None


def _run_validations(dialog, checks: list[tuple[str, str | None]]) -> bool:
    """Ejecuta una lista de (campo, error_o_none). Muestra el primer error y retorna False, o True si todo OK."""
    for field_name, err in checks:
        if err:
            QMessageBox.warning(dialog, "Validación", f"{field_name}: {err}")
            return False
    return True


# ---------------------------------------------------------------------------
# Quick dialogs
# ---------------------------------------------------------------------------

class QuickContactoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo Contacto")
        self._contacto = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(2)

        title = theme.create_title(self, "Nuevo contacto", "lg")
        layout.addWidget(title)
        layout.addSpacing(12)

        self._fields = {}
        for label_text, attr in [("Nombre *", "nombre"), ("Teléfono *", "telefono"),
                                  ("Teléfono 2", "telefono2"), ("Email", "email"),
                                  ("Notas", "notas")]:
            lbl = theme.create_form_label(self, label_text)
            layout.addWidget(lbl)
            txt = theme.create_input(self)
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
        btn_ok = QPushButton("Crear", self)
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
        if not _run_validations(self, [
            ("Teléfono", _validate_phone(telefono)),
            ("Teléfono 2", _validate_phone(telefono2)),
            ("Email", _validate_email(email)),
        ]):
            return
        new_id, err = repo.create_contacto(
            nombre, telefono, telefono2, email,
            self._fields["notas"].text().strip(),
        )
        if err:
            QMessageBox.critical(self, "Error", f"Error:\n{err}")
            return
        self._contacto = {"id": new_id, "nombre": nombre, "telefono": telefono}
        self.accept()

    def get_contacto(self):
        return self._contacto


class QuickAdminDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nueva Administración")
        self._admin = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(2)

        title = theme.create_title(self, "Nueva administración", "lg")
        layout.addWidget(title)
        layout.addSpacing(12)

        self._fields = {}
        for label_text, attr in [("Nombre *", "nombre"), ("Email", "email"),
                                  ("Teléfono", "telefono"), ("Dirección", "direccion")]:
            lbl = theme.create_form_label(self, label_text)
            layout.addWidget(lbl)
            txt = theme.create_input(self)
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
        btn_ok = QPushButton("Crear", self)
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
        if not nombre:
            QMessageBox.information(self, "Aviso", "El nombre es obligatorio.")
            return
        if not _run_validations(self, [
            ("Email", _validate_email(email)),
            ("Teléfono", _validate_phone(telefono)),
        ]):
            return
        new_id, err = repo.create_administracion(
            nombre, email, telefono,
            self._fields["direccion"].text().strip(),
        )
        if err:
            QMessageBox.critical(self, "Error", f"Error:\n{err}")
            return
        self._admin = {
            "id": new_id, "nombre": nombre,
            "email": email, "telefono": telefono,
            "direccion": self._fields["direccion"].text().strip(),
        }
        self.accept()

    def get_admin(self):
        return self._admin


# ---------------------------------------------------------------------------
# Admin / Comunidad form dialogs
# ---------------------------------------------------------------------------

class AdminFormDialog(QDialog):
    def __init__(self, parent, title, initial=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self._initial = initial or {}
        self._all_contactos = repo.get_contactos()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(2)

        title_label = theme.create_title(self, self.windowTitle(), "lg")
        layout.addWidget(title_label)
        layout.addSpacing(12)

        self._ctrls = {}
        for lbl_text, key, default in [
            ("Nombre *", "nombre", self._initial.get("nombre", "")),
            ("Email", "email", self._initial.get("email", "")),
            ("Teléfono", "telefono", self._initial.get("telefono", "")),
            ("Dirección", "direccion", self._initial.get("direccion", "")),
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

        ct_lbl = theme.create_form_label(self, "Contactos")
        layout.addWidget(ct_lbl)

        ct_row = QHBoxLayout()
        ct_row.setSpacing(6)
        self._ct_widget = CheckSelectWidget(self)
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
        theme.fit_dialog(self, 400, 380)

    def _on_ok(self):
        if not self._ctrls["nombre"].text().strip():
            QMessageBox.information(self, "Aviso", "El nombre es obligatorio.")
            return
        if not _run_validations(self, [
            ("Email", _validate_email(self._ctrls["email"].text().strip())),
            ("Teléfono", _validate_phone(self._ctrls["telefono"].text().strip())),
        ]):
            return
        self.accept()

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

    def get_values(self):
        return {
            "nombre": self._ctrls["nombre"].text().strip(),
            "email": self._ctrls["email"].text().strip(),
            "telefono": self._ctrls["telefono"].text().strip(),
            "direccion": self._ctrls["direccion"].text().strip(),
            "contacto_ids": list(self._ct_widget.get_selected_ids()),
        }


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
        self._admin_widget = SearchSelectWidget(self)
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
        self._ct_widget = CheckSelectWidget(self)
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
        if not _run_validations(self, [
            ("CIF", _validate_cif(self._ctrls["cif"].text().strip())),
            ("Email", _validate_email(self._ctrls["email"].text().strip())),
            ("Teléfono", _validate_phone(self._ctrls["telefono"].text().strip())),
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
