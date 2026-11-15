"""Aviso pasajero en la parte inferior de una ventana (no bloquea ni roba el foco).

Sustituye a las ventanas de «Éxito»: los errores siguen en QMessageBox.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from src.gui import theme

_ATTR = "_cubiapp_toast"
_SHORT_MS = 5000
_WITH_ACTIONS_MS = 8000
_MARGIN = 16


class Toast(QFrame):
    def __init__(self, parent: QWidget, text: str,
                 actions: Optional[List[Tuple[str, Callable[[], None]]]], timeout_ms: int):
        super().__init__(parent)
        self.setObjectName("cubiToast")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet(
            f"#cubiToast {{ background: {theme.BG_DARK}; border-radius: {theme.RADIUS_MD}px; }}"
            f"#cubiToast QLabel {{ color: {theme.TEXT_INVERSE}; background: transparent; }}"
            f"#cubiToast QPushButton {{ color: {theme.ACCENT_LIGHT}; background: transparent;"
            f" border: none; font-weight: bold; padding: 2px 6px; }}"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_LG, theme.SPACE_SM, theme.SPACE_SM, theme.SPACE_SM)
        layout.setSpacing(theme.SPACE_SM)
        self._label = QLabel(text, self)
        self._label.setFont(theme.font_base())
        self._label.setWordWrap(True)
        layout.addWidget(self._label, 1)
        self._actions: dict = {}
        for label, callback in actions or []:
            btn = QPushButton(label, self)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, lb=label: self.trigger(lb))
            layout.addWidget(btn)
            self._actions[label] = callback
        close = QPushButton("×", self)
        close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close.setToolTip("Cerrar")
        close.clicked.connect(self.dismiss)
        layout.addWidget(close)
        self._timeout = timeout_ms
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)

    def text(self) -> str:
        return self._label.text()

    def action_labels(self) -> List[str]:
        return list(self._actions)

    def timeout_ms(self) -> int:
        return self._timeout

    def trigger(self, label: str) -> None:
        callback = self._actions.get(label)
        self.dismiss()
        if callback is not None:
            callback()

    def dismiss(self) -> None:
        self._timer.stop()
        parent = self.parentWidget()
        if parent is not None and getattr(parent, _ATTR, None) is self:
            setattr(parent, _ATTR, None)
        self.hide()
        self.deleteLater()

    def popup(self) -> None:
        parent = self.parentWidget()
        width = min(560, max(280, parent.width() - 2 * _MARGIN))
        self.setFixedWidth(width)
        self.adjustSize()
        self.move((parent.width() - width) // 2, parent.height() - self.height() - _MARGIN)
        self.show()
        self.raise_()
        self._timer.start(self._timeout)


def current_toast(parent: QWidget) -> Optional[Toast]:
    return getattr(parent, _ATTR, None)


def show_toast(parent: QWidget, text: str,
               actions: Optional[List[Tuple[str, Callable[[], None]]]] = None,
               timeout_ms: Optional[int] = None) -> Toast:
    previous = current_toast(parent)
    if previous is not None:
        previous.dismiss()
    if timeout_ms is None:
        timeout_ms = _WITH_ACTIONS_MS if actions else _SHORT_MS
    toast = Toast(parent, text, actions, timeout_ms)
    setattr(parent, _ATTR, toast)
    toast.popup()
    return toast
