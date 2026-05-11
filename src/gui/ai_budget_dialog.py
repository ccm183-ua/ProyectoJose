"""
Diálogo para configurar la generación de partidas con IA.

Permite al usuario:
- Escribir el tipo de obra (texto libre)
- Añadir una descripción adicional para dar contexto a la IA
- Redactar o pulir la descripción con ayuda de la IA y revisarla antes de aplicar
- Dictar por micrófono (opcional) para rellenar la descripción
- Opcionalmente seleccionar una plantilla predefinida como referencia
- Generar partidas con IA o saltar el paso
"""

import threading
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.description_assistant import polish_budget_context_description
from src.core.speech_to_text_service import (
    STT_INSTALL_HINT,
    SpeechToTextService,
    SpeechToTextUnavailable,
)
from src.core.work_type_catalog import WorkTypeCatalog
from src.core.budget_generator import BudgetGenerator
from src.core.settings import Settings
from src.gui import theme


class DescriptionPolishPreviewDialog(QDialog):
    """Muestra el texto sugerido por la IA; el usuario puede editarlo y aplicar o descartar."""

    def __init__(self, parent, texto: str):
        super().__init__(parent)
        self.setWindowTitle("Descripción sugerida por la IA")
        self._choice: Optional[str] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        hint = theme.create_text(
            self,
            "Puede editar el texto antes de aplicarlo al campo de descripción.",
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._edit = QTextEdit(self)
        self._edit.setPlainText(texto)
        self._edit.setFont(theme.font_base())
        self._edit.setMinimumHeight(200)
        layout.addWidget(self._edit)

        row = QHBoxLayout()
        row.addStretch()

        btn_cancel = QPushButton("Cerrar sin aplicar", self)
        btn_cancel.setFont(theme.font_base())
        btn_cancel.clicked.connect(self.reject)
        row.addWidget(btn_cancel)

        btn_append = QPushButton("Añadir al final", self)
        btn_append.setFont(theme.font_base())
        btn_append.setToolTip("Concatena al texto que ya tenía en la descripción")
        btn_append.clicked.connect(self._on_append)
        row.addWidget(btn_append)

        btn_replace = QPushButton("Sustituir descripción", self)
        btn_replace.setFont(theme.get_font_medium())
        btn_replace.setProperty("class", "primary")
        btn_replace.setToolTip("Reemplaza por completo el contenido del campo descripción")
        btn_replace.clicked.connect(self._on_replace)
        row.addWidget(btn_replace)

        layout.addLayout(row)
        theme.fit_dialog(self, 560, 420)

    def _on_replace(self):
        self._choice = "replace"
        self.accept()

    def _on_append(self):
        self._choice = "append"
        self.accept()

    def choice(self) -> Optional[str]:
        return self._choice

    def edited_text(self) -> str:
        return self._edit.toPlainText().strip()


class AIBudgetDialog(QDialog):
    """Diálogo para configurar y lanzar la generación de partidas con IA."""

    _generation_done = Signal(dict)
    _polish_done = Signal(str, str)
    _dictation_done = Signal(str, str)

    def __init__(
        self,
        parent=None,
        datos_proyecto=None,
        context_extra="",
        historical_context=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Generar Partidas con IA")
        self._generation_done.connect(self._on_generation_complete)
        self._polish_done.connect(self._on_polish_done)
        self._dictation_done.connect(self._on_dictation_done)

        self._datos_proyecto = datos_proyecto or {}
        self._context_extra = context_extra or ""
        self._historical_context = historical_context or {}
        self._catalog = WorkTypeCatalog()
        self._settings = Settings()
        self._selected_plantilla = None
        self._result = None
        self._speech = SpeechToTextService()

        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        title = theme.create_title(panel, "Generar Partidas con IA", "xl")
        layout.addWidget(title)

        subtitle = theme.create_text(
            panel,
            "Describe el tipo de obra y la IA generará las partidas del presupuesto "
            "con precios orientativos. Puede dictar o pulir la descripción antes de generar.",
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(theme.SPACE_SM)

        lbl_tipo = QLabel("Tipo de obra:", panel)
        lbl_tipo.setFont(theme.get_font_medium())
        lbl_tipo.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(lbl_tipo)

        self._tipo_text = QLineEdit(panel)
        self._tipo_text.setPlaceholderText("Ej: Reparación de bajante comunitaria, Reforma integral cocina...")
        self._tipo_text.setFont(theme.font_base())
        self._tipo_text.setMinimumHeight(32)
        layout.addWidget(self._tipo_text)

        tipo_mic_row = QHBoxLayout()
        tipo_mic_row.addStretch()
        self._btn_dictate_tipo = QPushButton("Dictar tipo", panel)
        self._btn_dictate_tipo.setFont(theme.font_base())
        self._btn_dictate_tipo.setToolTip("Graba una frase corta y la escribe en tipo de obra")
        self._btn_dictate_tipo.clicked.connect(self._on_dictate_tipo)
        tipo_mic_row.addWidget(self._btn_dictate_tipo)
        layout.addLayout(tipo_mic_row)

        layout.addSpacing(theme.SPACE_XS)

        lbl_desc = QLabel("Descripción adicional (contexto para la IA):", panel)
        lbl_desc.setFont(theme.get_font_medium())
        lbl_desc.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(lbl_desc)

        self._desc_text = QTextEdit(panel)
        self._desc_text.setPlaceholderText(
            "Ej: Bajante de PVC en patio interior, edificio 4 plantas, "
            "acceso difícil por estrechez del patio..."
        )
        self._desc_text.setFont(theme.font_base())
        self._desc_text.setMinimumHeight(72)
        self._desc_text.setMaximumHeight(140)
        layout.addWidget(self._desc_text)

        desc_tools = QHBoxLayout()
        self._btn_polish = QPushButton("Redactar con IA", panel)
        self._btn_polish.setFont(theme.font_base())
        self._btn_polish.setToolTip(
            "Mejora o amplía la descripción usando su tipo de obra y datos del proyecto; "
            "podrá revisar el texto antes de aplicarlo."
        )
        self._btn_polish.clicked.connect(self._on_polish_description)
        desc_tools.addWidget(self._btn_polish)

        self._btn_dictate_desc = QPushButton("Dictar descripción", panel)
        self._btn_dictate_desc.setFont(theme.font_base())
        self._btn_dictate_desc.setToolTip(
            "Graba con el micrófono y añade el texto reconocido a la descripción "
            "(requiere SpeechRecognition y PyAudio)."
        )
        self._btn_dictate_desc.clicked.connect(self._on_dictate_description)
        desc_tools.addWidget(self._btn_dictate_desc)

        if not self._speech.is_available():
            stt_hint = theme.create_text(
                panel,
                STT_INSTALL_HINT.replace("\n", " ").strip(),
                muted=True,
            )
            desc_tools.addWidget(stt_hint, 1)
        else:
            desc_tools.addStretch()

        layout.addLayout(desc_tools)

        layout.addSpacing(theme.SPACE_XS)

        lbl_plantilla = QLabel("Plantilla de referencia (opcional):", panel)
        lbl_plantilla.setFont(theme.get_font_medium())
        lbl_plantilla.setStyleSheet(f"color: {theme.TEXT_PRIMARY}; background: transparent;")
        layout.addWidget(lbl_plantilla)

        plantilla_hint = theme.create_text(
            panel,
            "Si seleccionas una, la IA la usará como base para generar partidas más precisas.",
            muted=True,
        )
        layout.addWidget(plantilla_hint)

        names = self._catalog.get_all_names()
        self._plantilla_list = QListWidget(panel)
        self._plantilla_list.addItem("(Ninguna - generar desde cero)")
        self._plantilla_list.addItems(names)
        self._plantilla_list.setCurrentRow(0)
        self._plantilla_list.setFont(theme.font_base())
        self._plantilla_list.setMaximumHeight(100)
        layout.addWidget(self._plantilla_list)

        if not self._settings.has_active_ai_key():
            warning_layout = QHBoxLayout()
            warning_icon = QLabel("⚠", panel)
            warning_icon.setStyleSheet(f"color: {theme.WARNING}; background: transparent;")
            warning_icon.setFont(theme.font_lg())
            warning_layout.addWidget(warning_icon)

            warning_text = theme.create_text(
                panel, "No hay API key configurada. Solo se podrán usar plantillas offline.",
            )
            warning_text.setStyleSheet(f"color: {theme.WARNING}; background: transparent;")
            warning_layout.addWidget(warning_text, 1)
            layout.addSpacing(theme.SPACE_SM)
            layout.addLayout(warning_layout)

        layout.addSpacing(theme.SPACE_MD)
        layout.addWidget(theme.create_divider(panel))
        layout.addSpacing(theme.SPACE_MD)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._btn_skip = QPushButton("Saltar", panel)
        self._btn_skip.setFont(theme.font_base())
        self._btn_skip.setFixedSize(120, 44)
        self._btn_skip.setToolTip("Crear presupuesto vacío sin partidas IA")
        self._btn_skip.clicked.connect(self.reject)
        btn_layout.addWidget(self._btn_skip)
        btn_layout.addSpacing(theme.SPACE_MD)

        self._btn_generate = QPushButton("Generar partidas con IA", panel)
        self._btn_generate.setFont(theme.get_font_medium())
        self._btn_generate.setFixedSize(220, 44)
        self._btn_generate.setProperty("class", "primary")
        self._btn_generate.setDefault(True)
        self._btn_generate.clicked.connect(self._on_generate)
        btn_layout.addWidget(self._btn_generate)

        layout.addLayout(btn_layout)

        main_layout.addWidget(panel)

        self.setMinimumSize(650, 520)
        self.resize(650, 620)

    def _end_aux_work(self):
        self._btn_polish.setEnabled(True)
        self._btn_polish.setText("Redactar con IA")
        self._btn_dictate_desc.setEnabled(True)
        self._btn_dictate_desc.setText("Dictar descripción")
        self._btn_dictate_tipo.setEnabled(True)
        self._btn_dictate_tipo.setText("Dictar tipo")
        self._btn_generate.setEnabled(True)

    def _begin_polish_work(self):
        self._btn_polish.setEnabled(False)
        self._btn_dictate_desc.setEnabled(False)
        self._btn_dictate_tipo.setEnabled(False)
        self._btn_generate.setEnabled(False)
        self._btn_polish.setText("Redactando…")

    def _begin_dictate_desc_work(self):
        self._btn_polish.setEnabled(False)
        self._btn_dictate_desc.setEnabled(False)
        self._btn_dictate_tipo.setEnabled(False)
        self._btn_generate.setEnabled(False)
        self._btn_dictate_desc.setText("Escuchando…")

    def _on_polish_description(self):
        if not self._settings.has_active_ai_key():
            QMessageBox.warning(
                self,
                "IA no configurada",
                "Configure una API key en Configuración > IA para usar la redacción asistida.",
            )
            return

        tipo = self._tipo_text.text().strip()
        if not tipo and not self._desc_text.toPlainText().strip():
            QMessageBox.information(
                self,
                "Falta contexto",
                "Escriba al menos el tipo de obra o un borrador en la descripción "
                "para que la IA pueda redactar.",
            )
            return

        self._begin_polish_work()

        borrador = self._desc_text.toPlainText().strip()
        ctx_hist = ""
        if self._historical_context:
            try:
                ctx_hist = str(self._historical_context.get("resumen_busqueda", ""))[:1200]
            except Exception:
                ctx_hist = ""

        def run():
            text, err = polish_budget_context_description(
                self._settings,
                tipo_obra=tipo or "(sin tipo aún)",
                borrador=borrador,
                datos_proyecto=self._datos_proyecto,
                context_extra=(self._context_extra or "") + (("\n" + ctx_hist) if ctx_hist else ""),
            )
            self._polish_done.emit(text or "", err or "")

        threading.Thread(target=run, daemon=True).start()

    def _on_polish_done(self, text: str, err: str):
        self._end_aux_work()
        if err:
            QMessageBox.warning(self, "No se pudo redactar", err)
            return
        dlg = DescriptionPolishPreviewDialog(self, text)
        if dlg.exec() != 1:
            return
        choice = dlg.choice()
        edited = dlg.edited_text()
        if not edited:
            return
        if choice == "replace":
            self._desc_text.setPlainText(edited)
        elif choice == "append":
            cur = self._desc_text.toPlainText().strip()
            if cur:
                self._desc_text.setPlainText(f"{cur}\n\n{edited}")
            else:
                self._desc_text.setPlainText(edited)

    def _on_dictate_description(self):
        if not self._speech.is_available():
            QMessageBox.information(self, "Dictado no disponible", STT_INSTALL_HINT)
            return
        self._begin_dictate_desc_work()
        threading.Thread(target=self._run_dictation_description, daemon=True).start()

    def _on_dictate_tipo(self):
        if not self._speech.is_available():
            QMessageBox.information(self, "Dictado no disponible", STT_INSTALL_HINT)
            return
        self._btn_dictate_tipo.setEnabled(False)
        self._btn_dictate_desc.setEnabled(False)
        self._btn_polish.setEnabled(False)
        self._btn_generate.setEnabled(False)
        self._btn_dictate_tipo.setText("Escuchando…")
        threading.Thread(target=self._run_dictation_tipo, daemon=True).start()

    def _run_dictation_description(self):
        try:
            text = self._speech.transcribe_once(timeout=10.0, phrase_time_limit=50.0)
            self._dictation_done.emit(text, "")
        except SpeechToTextUnavailable as exc:
            self._dictation_done.emit("", str(exc))
        except Exception as exc:
            self._dictation_done.emit("", str(exc))

    def _run_dictation_tipo(self):
        try:
            text = self._speech.transcribe_once(timeout=8.0, phrase_time_limit=25.0)
            self._dictation_done.emit("__tipo__:" + text, "")
        except SpeechToTextUnavailable as exc:
            self._dictation_done.emit("", str(exc))
        except Exception as exc:
            self._dictation_done.emit("", str(exc))

    def _on_dictation_done(self, text: str, err: str):
        self._end_aux_work()

        if err:
            QMessageBox.warning(self, "Dictado", err)
            return

        if text.startswith("__tipo__:"):
            fragment = text[len("__tipo__:") :].strip()
            if fragment:
                cur = self._tipo_text.text().strip()
                self._tipo_text.setText(f"{cur} {fragment}".strip() if cur else fragment)
            return

        if not text:
            return
        cur = self._desc_text.toPlainText().strip()
        if cur:
            self._desc_text.setPlainText(f"{cur}\n{text}")
        else:
            self._desc_text.setPlainText(text)

    def _on_generate(self):
        tipo = self._tipo_text.text().strip()
        if not tipo:
            QMessageBox.warning(self, "Campo obligatorio", "Por favor, escribe el tipo de obra.")
            return

        descripcion = self._desc_text.toPlainText().strip()

        sel_idx = self._plantilla_list.currentRow()
        if sel_idx > 0:
            nombre = self._plantilla_list.item(sel_idx).text()
            self._selected_plantilla = self._catalog.get_by_name(nombre)
        else:
            self._selected_plantilla = None

        self._btn_generate.setEnabled(False)
        self._btn_polish.setEnabled(False)
        self._btn_dictate_desc.setEnabled(False)
        self._btn_dictate_tipo.setEnabled(False)
        self._btn_generate.setText("Generando...")

        thread = threading.Thread(
            target=self._run_generation,
            args=(tipo, descripcion),
            daemon=True,
        )
        thread.start()

    def _run_generation(self, tipo, descripcion):
        try:
            generator = BudgetGenerator(settings=self._settings)

            full_desc = descripcion
            if self._context_extra:
                full_desc = f"{descripcion}\n{self._context_extra}" if descripcion else self._context_extra

            result = generator.generate(
                tipo_obra=tipo,
                descripcion=full_desc,
                plantilla=self._selected_plantilla,
                datos_proyecto=self._datos_proyecto,
                historical_context=self._historical_context,
            )

            self._generation_done.emit(result)
        except Exception as exc:
            self._generation_done.emit({
                'partidas': [],
                'source': 'error',
                'error': f"Error inesperado en la generación: {exc}",
            })

    def _on_generation_complete(self, result):
        self._result = result
        self._btn_generate.setEnabled(True)
        self._btn_polish.setEnabled(True)
        self._btn_dictate_desc.setEnabled(True)
        self._btn_dictate_tipo.setEnabled(True)
        self._btn_generate.setText("Generar partidas con IA")

        source = result.get('source', 'error')

        if source == 'error' or (result.get('error') and not result.get('partidas')):
            QMessageBox.warning(
                self, "Error de generación",
                f"No se pudieron generar partidas:\n\n{result.get('error', '')}",
            )
            return

        if source == 'offline':
            confirm = QMessageBox.question(
                self,
                "Modo offline - Partidas de plantilla",
                "La IA no está disponible en este momento (cuota agotada o sin conexión).\n\n"
                "Se han cargado las partidas base de la plantilla seleccionada "
                "como punto de partida. Estas partidas NO han sido adaptadas por la IA "
                "a tu descripción específica.\n\n"
                "¿Quieres usar estas partidas base como referencia?\n"
                "(Podrás editarlas manualmente en el siguiente paso)",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                self._result = None
                return
            self.accept()
            return

        self.accept()

    def get_result(self):
        return self._result
