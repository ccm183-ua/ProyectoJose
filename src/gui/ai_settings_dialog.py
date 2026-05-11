"""Dialogo de configuracion de proveedores IA."""

from __future__ import annotations

import threading

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.core.ai_clients import DeepSeekAIClient, GeminiAIClient, mask_secret
from src.core.settings import AI_PROVIDER_DEEPSEEK, AI_PROVIDER_GEMINI, Settings
from src.gui import theme


class AISettingsDialog(QDialog):
    _test_done = Signal(str, bool, str)

    def __init__(self, parent=None, settings: Settings | None = None):
        super().__init__(parent)
        self.setWindowTitle("Configuración IA")
        self._settings = settings or Settings()
        self._test_done.connect(self._on_test_done)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        layout.addWidget(theme.create_title(self, "Configuración IA", "xl"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(theme.SPACE_MD)
        grid.setVerticalSpacing(theme.SPACE_SM)

        self._provider = QComboBox(self)
        self._provider.addItem("Gemini", AI_PROVIDER_GEMINI)
        self._provider.addItem("DeepSeek", AI_PROVIDER_DEEPSEEK)
        current_provider = self._settings.get_ai_provider()
        idx = self._provider.findData(current_provider)
        self._provider.setCurrentIndex(max(0, idx))
        grid.addWidget(QLabel("Proveedor activo:", self), 0, 0)
        grid.addWidget(self._provider, 0, 1, 1, 2)

        self._gemini_key = self._secret_field(self._settings.get_gemini_api_key() or "")
        self._gemini_key.setPlaceholderText(mask_secret(self._settings.get_gemini_api_key() or ""))
        self._gemini_toggle = QPushButton("Mostrar", self)
        self._gemini_toggle.clicked.connect(lambda: self._toggle_secret(self._gemini_key, self._gemini_toggle))
        grid.addWidget(QLabel("API key Gemini:", self), 1, 0)
        grid.addWidget(self._gemini_key, 1, 1)
        grid.addWidget(self._gemini_toggle, 1, 2)

        self._gemini_model = QLineEdit(self)
        self._gemini_model.setText(self._settings.get_gemini_model())
        grid.addWidget(QLabel("Modelo Gemini:", self), 2, 0)
        grid.addWidget(self._gemini_model, 2, 1, 1, 2)

        self._deepseek_key = self._secret_field(self._settings.get_deepseek_api_key() or "")
        self._deepseek_key.setPlaceholderText(mask_secret(self._settings.get_deepseek_api_key() or ""))
        self._deepseek_toggle = QPushButton("Mostrar", self)
        self._deepseek_toggle.clicked.connect(lambda: self._toggle_secret(self._deepseek_key, self._deepseek_toggle))
        grid.addWidget(QLabel("API key DeepSeek:", self), 3, 0)
        grid.addWidget(self._deepseek_key, 3, 1)
        grid.addWidget(self._deepseek_toggle, 3, 2)

        self._deepseek_model = QLineEdit(self)
        self._deepseek_model.setText(self._settings.get_deepseek_model())
        grid.addWidget(QLabel("Modelo DeepSeek:", self), 4, 0)
        grid.addWidget(self._deepseek_model, 4, 1, 1, 2)

        layout.addLayout(grid)
        layout.addSpacing(theme.SPACE_MD)
        layout.addWidget(theme.create_divider(self))

        buttons = QHBoxLayout()
        self._btn_test_gemini = QPushButton("Probar Gemini", self)
        self._btn_test_gemini.clicked.connect(lambda: self._test_provider(AI_PROVIDER_GEMINI))
        buttons.addWidget(self._btn_test_gemini)

        self._btn_test_deepseek = QPushButton("Probar DeepSeek", self)
        self._btn_test_deepseek.clicked.connect(lambda: self._test_provider(AI_PROVIDER_DEEPSEEK))
        buttons.addWidget(self._btn_test_deepseek)
        buttons.addStretch()

        btn_cancel = QPushButton("Cancelar", self)
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)

        btn_save = QPushButton("Guardar", self)
        btn_save.setProperty("class", "primary")
        btn_save.clicked.connect(self._save)
        buttons.addWidget(btn_save)

        layout.addLayout(buttons)
        theme.fit_dialog(self, 660, 360)

    @staticmethod
    def _secret_field(value: str) -> QLineEdit:
        field = QLineEdit()
        field.setText(value)
        field.setEchoMode(QLineEdit.EchoMode.Password)
        return field

    @staticmethod
    def _toggle_secret(field: QLineEdit, button: QPushButton) -> None:
        if field.echoMode() == QLineEdit.EchoMode.Password:
            field.setEchoMode(QLineEdit.EchoMode.Normal)
            button.setText("Ocultar")
        else:
            field.setEchoMode(QLineEdit.EchoMode.Password)
            button.setText("Mostrar")

    def _set_test_buttons_enabled(self, enabled: bool) -> None:
        self._btn_test_gemini.setEnabled(enabled)
        self._btn_test_deepseek.setEnabled(enabled)

    def _test_provider(self, provider: str) -> None:
        self._set_test_buttons_enabled(False)

        def run():
            if provider == AI_PROVIDER_DEEPSEEK:
                client = DeepSeekAIClient(self._deepseek_key.text().strip(), self._deepseek_model.text().strip())
                name = "DeepSeek"
            else:
                client = GeminiAIClient(self._gemini_key.text().strip(), self._gemini_model.text().strip())
                name = "Gemini"
            ok, message = client.test_connection()
            self._test_done.emit(name, ok, message)

        threading.Thread(target=run, daemon=True).start()

    def _on_test_done(self, name: str, ok: bool, message: str) -> None:
        self._set_test_buttons_enabled(True)
        if ok:
            QMessageBox.information(self, name, "Conexión correcta")
        else:
            QMessageBox.warning(self, name, message or "No se pudo probar la conexión.")

    def _save(self) -> None:
        self._settings.save_ai_provider(self._provider.currentData())
        self._settings.save_gemini_api_key(self._gemini_key.text())
        self._settings.save_deepseek_api_key(self._deepseek_key.text())
        self._settings.save_gemini_model(self._gemini_model.text())
        self._settings.save_deepseek_model(self._deepseek_model.text())
        self.accept()
