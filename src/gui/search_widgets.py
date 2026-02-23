"""
Widgets de selección con búsqueda para la gestión de base de datos.

SearchSelectWidget: selección simple con búsqueda (dropdown).
CheckSelectWidget: selección múltiple con checkboxes.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from src.gui import theme


class SearchSelectWidget(QWidget):
    """QLineEdit (readonly display) + dropdown button for single-select with search."""

    def __init__(self, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self._items: list[tuple] = []
        self._selected_id = None
        self._on_edit = on_edit
        self._on_delete = on_delete

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
        dlg = _SearchSelectDialog(
            self, self._items, self._selected_id,
            on_edit=self._on_edit, on_delete=self._on_delete,
        )
        result = dlg.exec()
        self._items = list(dlg._items)
        if result == 1:
            self._selected_id = dlg.get_selected_id()
        else:
            valid_ids = {id_ for id_, _ in self._items}
            if self._selected_id not in valid_ids:
                self._selected_id = None
        self._update_display()


class _SearchSelectDialog(QDialog):
    def __init__(self, parent, items, current_id, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar")
        self._items = list(items)
        self._visible = list(items)
        self._selected_id = current_id
        self._on_edit = on_edit
        self._on_delete = on_delete

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
        if self._on_edit:
            btn_e = QPushButton("Editar", self)
            btn_e.setFont(theme.font_sm())
            btn_e.setFixedHeight(32)
            btn_e.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_e.clicked.connect(self._handle_edit)
            btn_row.addWidget(btn_e)
        if self._on_delete:
            btn_d = QPushButton("Borrar", self)
            btn_d.setFont(theme.font_sm())
            btn_d.setFixedHeight(32)
            btn_d.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_d.setStyleSheet(
                "QPushButton { color: #e53e3e; }"
                "QPushButton:hover { background: #fee2e2; border-radius: 4px; }"
            )
            btn_d.clicked.connect(self._handle_delete)
            btn_row.addWidget(btn_d)
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

    def _get_current_id(self):
        row = self._list.currentRow()
        if 0 <= row < len(self._visible):
            return self._visible[row][0]
        return None

    def _handle_edit(self):
        id_ = self._get_current_id()
        if id_ is None:
            QMessageBox.information(self, "Editar", "Selecciona un elemento.")
            return
        new_items = self._on_edit(id_)
        if new_items is not None:
            self._items = new_items
            self._filter()

    def _handle_delete(self):
        id_ = self._get_current_id()
        if id_ is None:
            QMessageBox.information(self, "Eliminar", "Selecciona un elemento.")
            return
        new_items = self._on_delete(id_)
        if new_items is not None:
            self._items = new_items
            if id_ == self._selected_id:
                self._selected_id = None
            self._filter()

    def get_selected_id(self):
        return self._selected_id


class CheckSelectWidget(QWidget):
    """QLineEdit (readonly display) + button that opens multi-select dialog."""

    def __init__(self, parent=None, on_edit=None, on_delete=None):
        super().__init__(parent)
        self._items: list[tuple] = []
        self._selected_ids: set = set()
        self._on_edit = on_edit
        self._on_delete = on_delete

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
        dlg = _CheckSelectDialog(
            self, self._items, self._selected_ids,
            on_edit=self._on_edit, on_delete=self._on_delete,
        )
        result = dlg.exec()
        self._items = list(dlg._items)
        if result == 1:
            self._selected_ids = dlg.get_selected_ids()
        else:
            valid_ids = {id_ for id_, _ in self._items}
            self._selected_ids &= valid_ids
        self._update_display()


class _CheckSelectDialog(QDialog):
    def __init__(self, parent, items, selected_ids, on_edit=None, on_delete=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar contactos")
        self._items = list(items)
        self._visible = list(items)
        self._selected_ids = set(selected_ids)
        self._on_edit = on_edit
        self._on_delete = on_delete

        layout = QVBoxLayout(self)
        layout.setSpacing(theme.SPACE_SM)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Buscar...")
        self._search.setFont(theme.font_base())
        self._search.textChanged.connect(self._filter)
        layout.addWidget(self._search)

        self._list = QListWidget(self)
        self._list.setFont(theme.font_base())
        self._list.itemChanged.connect(self._on_check)
        layout.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        if self._on_edit:
            btn_e = QPushButton("Editar", self)
            btn_e.setFont(theme.font_sm())
            btn_e.setFixedHeight(32)
            btn_e.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_e.clicked.connect(self._handle_edit)
            btn_row.addWidget(btn_e)
        if self._on_delete:
            btn_d = QPushButton("Borrar", self)
            btn_d.setFont(theme.font_sm())
            btn_d.setFixedHeight(32)
            btn_d.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_d.setStyleSheet(
                "QPushButton { color: #e53e3e; }"
                "QPushButton:hover { background: #fee2e2; border-radius: 4px; }"
            )
            btn_d.clicked.connect(self._handle_delete)
            btn_row.addWidget(btn_d)
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
        self._list.blockSignals(True)
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
            item = QListWidgetItem(disp)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if id_ in self._selected_ids else Qt.CheckState.Unchecked)
            self._list.addItem(item)
        self._list.blockSignals(False)

    def _on_check(self, item):
        row = self._list.row(item)
        if 0 <= row < len(self._visible):
            id_ = self._visible[row][0]
            if item.checkState() == Qt.CheckState.Checked:
                self._selected_ids.add(id_)
            else:
                self._selected_ids.discard(id_)

    def _get_current_id(self):
        row = self._list.currentRow()
        if 0 <= row < len(self._visible):
            return self._visible[row][0]
        return None

    def _handle_edit(self):
        id_ = self._get_current_id()
        if id_ is None:
            QMessageBox.information(self, "Editar", "Selecciona un elemento.")
            return
        new_items = self._on_edit(id_)
        if new_items is not None:
            self._items = new_items
            self._filter()

    def _handle_delete(self):
        id_ = self._get_current_id()
        if id_ is None:
            QMessageBox.information(self, "Eliminar", "Selecciona un elemento.")
            return
        new_items = self._on_delete(id_)
        if new_items is not None:
            self._items = new_items
            self._selected_ids.discard(id_)
            self._filter()

    def get_selected_ids(self):
        return set(self._selected_ids)
