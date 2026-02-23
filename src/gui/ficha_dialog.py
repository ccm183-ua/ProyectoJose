"""
Diálogo de ficha detallada para administración o comunidad.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from src.core import db_repository as repo
from src.gui import theme


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
