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
from src.core.ai_settings_persistence import api_key_status_text, save_ai_settings_from_dialog
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

        self._clear_gemini = False
        self._clear_deepseek = False

        self._gemini_key = self._secret_field("")
        self._gemini_key.setPlaceholderText(mask_secret(self._settings.get_gemini_api_key() or ""))
        self._gemini_key.textChanged.connect(lambda text: self._on_secret_text_changed("gemini", text))
        self._gemini_status = self._status_label(
            api_key_status_text("Gemini", self._settings.get_gemini_api_key_source())
        )
        self._gemini_toggle = QPushButton("Mostrar", self)
        self._gemini_toggle.clicked.connect(lambda: self._toggle_secret(self._gemini_key, self._gemini_toggle))
        self._gemini_clear = QPushButton("Borrar clave", self)
        self._gemini_clear.clicked.connect(lambda: self._clear_secret(self._gemini_key, "gemini"))
        grid.addWidget(QLabel("API key Gemini:", self), 1, 0)
        grid.addWidget(self._gemini_key, 1, 1)
        grid.addWidget(self._gemini_toggle, 1, 2)
        grid.addWidget(self._gemini_clear, 1, 3)
        grid.addWidget(self._gemini_status, 2, 1, 1, 3)

        self._gemini_model = QLineEdit(self)
        self._gemini_model.setText(self._settings.get_gemini_model())
        grid.addWidget(QLabel("Modelo Gemini:", self), 3, 0)
        grid.addWidget(self._gemini_model, 3, 1, 1, 3)

        self._deepseek_key = self._secret_field("")
        self._deepseek_key.setPlaceholderText(mask_secret(self._settings.get_deepseek_api_key() or ""))
        self._deepseek_key.textChanged.connect(lambda text: self._on_secret_text_changed("deepseek", text))
        self._deepseek_status = self._status_label(
            api_key_status_text("DeepSeek", self._settings.get_deepseek_api_key_source())
        )
        self._deepseek_toggle = QPushButton("Mostrar", self)
        self._deepseek_toggle.clicked.connect(lambda: self._toggle_secret(self._deepseek_key, self._deepseek_toggle))
        self._deepseek_clear = QPushButton("Borrar clave", self)
        self._deepseek_clear.clicked.connect(lambda: self._clear_secret(self._deepseek_key, "deepseek"))
        grid.addWidget(QLabel("API key DeepSeek:", self), 4, 0)
        grid.addWidget(self._deepseek_key, 4, 1)
        grid.addWidget(self._deepseek_toggle, 4, 2)
        grid.addWidget(self._deepseek_clear, 4, 3)
        grid.addWidget(self._deepseek_status, 5, 1, 1, 3)

        self._deepseek_model = QLineEdit(self)
        self._deepseek_model.setText(self._settings.get_deepseek_model())
        grid.addWidget(QLabel("Modelo DeepSeek:", self), 6, 0)
        grid.addWidget(self._deepseek_model, 6, 1, 1, 3)

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
    def _status_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; background: transparent;")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _toggle_secret(field: QLineEdit, button: QPushButton) -> None:
        if field.echoMode() == QLineEdit.EchoMode.Password:
            field.setEchoMode(QLineEdit.EchoMode.Normal)
            button.setText("Ocultar")
        else:
            field.setEchoMode(QLineEdit.EchoMode.Password)
            button.setText("Mostrar")

    def _clear_secret(self, field: QLineEdit, provider: str) -> None:
        field.setText("")
        if provider == "gemini":
            self._clear_gemini = True
            self._gemini_status.setText("Clave Gemini: se borrará al guardar")
        else:
            self._clear_deepseek = True
            self._deepseek_status.setText("Clave DeepSeek: se borrará al guardar")

    def _on_secret_text_changed(self, provider: str, text: str) -> None:
        if not (text or "").strip():
            return
        if provider == "gemini":
            self._clear_gemini = False
            self._gemini_status.setText("Clave Gemini: se guardará una nueva clave")
        else:
            self._clear_deepseek = False
            self._deepseek_status.setText("Clave DeepSeek: se guardará una nueva clave")

    def _set_test_buttons_enabled(self, enabled: bool) -> None:
        self._btn_test_gemini.setEnabled(enabled)
        self._btn_test_deepseek.setEnabled(enabled)

    def _test_provider(self, provider: str) -> None:
        self._set_test_buttons_enabled(False)

        def run():
            if provider == AI_PROVIDER_DEEPSEEK:
                api_key = self._deepseek_key.text().strip() or self._settings.get_deepseek_api_key()
                client = DeepSeekAIClient(api_key, self._deepseek_model.text().strip())
                name = "DeepSeek"
            else:
                api_key = self._gemini_key.text().strip() or self._settings.get_gemini_api_key()
                client = GeminiAIClient(api_key, self._gemini_model.text().strip())
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
        save_ai_settings_from_dialog(
            self._settings,
            provider=self._provider.currentData(),
            gemini_key_input=self._gemini_key.text(),
            deepseek_key_input=self._deepseek_key.text(),
            gemini_model=self._gemini_model.text(),
            deepseek_model=self._deepseek_model.text(),
            clear_gemini=self._clear_gemini,
            clear_deepseek=self._clear_deepseek,
        )
        self.accept()
