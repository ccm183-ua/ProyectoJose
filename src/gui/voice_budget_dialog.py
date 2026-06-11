"""
Diálogo unificado de creación de presupuesto por voz o texto libre.

Punto de entrada único que elimina la bifurcación histórico/IA.
El cliente describe la obra en lenguaje natural (dictado o escrito)
y el BudgetOrchestrator decide internamente qué viene del histórico
y qué genera la IA.

Flujo:
  Usuario describe la obra (voz o texto)
       ↓
  BudgetOrchestrator.generate()
  [histórico + IA para huecos, automático]
       ↓
  Resultado con etiqueta 'fuente' por partida
  ('historico' → precio real | 'ia_estimado' → revisar rápido)
"""

import threading
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.budget_orchestrator import BudgetOrchestrator
from src.core.settings import Settings
from src.core.speech_to_text_service import SpeechToTextService, SpeechToTextUnavailable


class VoiceBudgetDialog(QDialog):
    """
    Diálogo de creación de presupuesto con un único campo de descripción libre.

    El usuario describe la obra como se la explicaría a un colega:
    breve, técnica y directa. El sistema hace el resto.
    """

    _generation_done = Signal(dict)

    def __init__(
        self,
        settings: Optional[Settings] = None,
        datos_proyecto: Optional[Dict] = None,
        plantilla: Optional[Dict] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._settings = settings or Settings()
        self._datos_proyecto = datos_proyecto or {}
        self._plantilla = plantilla
        self._orchestrator = BudgetOrchestrator(settings=self._settings)
        self._stt = SpeechToTextService()
        self._result: Optional[Dict] = None

        self.setWindowTitle("Crear presupuesto")
        self.setMinimumWidth(520)
        self.setMinimumHeight(340)
        self._build_ui()
        self._generation_done.connect(self._on_generation_done)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 18, 20, 18)

        # Cabecera
        title = QLabel("Describe la obra")
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        hint = QLabel(
            "Explícalo como se lo dirías a tu aparejador.\n"
            "Sé breve y técnico: zona, trabajo, material si procede."
        )
        hint.setStyleSheet("color: #666; font-size: 12px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # Campo de descripción libre
        self._txt_descripcion = QTextEdit()
        self._txt_descripcion.setPlaceholderText(
            "Ej: Cambio bajante PVC 110mm pluviales, 5ª y 6ª planta, comunidad de 8 vecinos"
        )
        self._txt_descripcion.setFixedHeight(110)
        layout.addWidget(self._txt_descripcion)

        # Fila botones dictado + estado
        row_voice = QHBoxLayout()
        self._btn_dictar = QPushButton("🎤  Dictar")
        self._btn_dictar.setFixedWidth(110)
        self._btn_dictar.clicked.connect(self._on_dictar)
        if not self._stt.is_available():
            self._btn_dictar.setToolTip(
                "SpeechRecognition/PyAudio no instalados. "
                "Instala con: pip install SpeechRecognition pyaudio"
            )
            self._btn_dictar.setEnabled(False)
        row_voice.addWidget(self._btn_dictar)

        self._lbl_status = QLabel("")
        self._lbl_status.setStyleSheet("color: #888; font-size: 11px;")
        row_voice.addWidget(self._lbl_status, stretch=1)
        layout.addLayout(row_voice)

        # Info de cobertura (se muestra tras generar)
        self._lbl_cobertura = QLabel("")
        self._lbl_cobertura.setWordWrap(True)
        self._lbl_cobertura.setStyleSheet("font-size: 11px; color: #555;")
        self._lbl_cobertura.hide()
        layout.addWidget(self._lbl_cobertura)

        layout.addStretch()

        # Botones aceptar / cancelar
        row_btns = QHBoxLayout()
        row_btns.addStretch()
        self._btn_cancelar = QPushButton("Cancelar")
        self._btn_cancelar.clicked.connect(self.reject)
        row_btns.addWidget(self._btn_cancelar)

        self._btn_generar = QPushButton("Generar presupuesto")
        self._btn_generar.setDefault(True)
        self._btn_generar.clicked.connect(self._on_generar)
        row_btns.addWidget(self._btn_generar)
        layout.addLayout(row_btns)

    # ── Dictado ───────────────────────────────────────────────────────────────

    _dictation_done = Signal(str)

    def _on_dictar(self):
        self._set_buttons_enabled(False)
        self._btn_dictar.setText("Escuchando…")
        self._lbl_status.setText("Escuchando, habla ahora…")
        self._dictation_done.connect(self._on_dictation_result)
        threading.Thread(target=self._run_dictation, daemon=True).start()

    def _run_dictation(self):
        try:
            text = self._stt.transcribe_once(timeout=12.0, phrase_time_limit=60.0)
            self._dictation_done.emit(text)
        except SpeechToTextUnavailable as exc:
            self._dictation_done.emit(f"__error__:{exc}")
        except Exception as exc:
            self._dictation_done.emit(f"__error__:{exc}")

    def _on_dictation_result(self, text: str):
        try:
            self._dictation_done.disconnect(self._on_dictation_result)
        except RuntimeError:
            pass
        self._btn_dictar.setText("🎤  Dictar")
        self._set_buttons_enabled(True)
        if text.startswith("__error__:"):
            self._lbl_status.setText(text[len("__error__:"):])
            return
        current = self._txt_descripcion.toPlainText().strip()
        joined = f"{current} {text}".strip() if current else text
        self._txt_descripcion.setPlainText(joined)
        self._lbl_status.setText("Dictado aplicado.")

    # ── Generación ────────────────────────────────────────────────────────────

    def _on_generar(self):
        descripcion = self._txt_descripcion.toPlainText().strip()
        if not descripcion:
            QMessageBox.warning(self, "Descripción vacía", "Escribe o dicta la descripción de la obra.")
            return
        self._set_buttons_enabled(False)
        self._lbl_status.setText("Generando presupuesto…")
        self._lbl_cobertura.hide()
        threading.Thread(
            target=self._run_generation,
            args=(descripcion,),
            daemon=True,
        ).start()

    def _run_generation(self, descripcion: str):
        result = self._orchestrator.generate(
            descripcion_libre=descripcion,
            datos_proyecto=self._datos_proyecto,
            plantilla=self._plantilla,
        )
        self._generation_done.emit(result)

    def _on_generation_done(self, result: Dict):
        self._set_buttons_enabled(True)
        self._lbl_status.setText("")

        if result.get("error") and not result.get("partidas"):
            QMessageBox.warning(
                self,
                "Error al generar",
                f"No se pudieron generar partidas.\n\n{result['error']}",
            )
            return

        self._result = result
        cobertura = result.get("cobertura", {})
        self._mostrar_cobertura(cobertura)
        self.accept()

    def _mostrar_cobertura(self, cobertura: Dict):
        n_hist = cobertura.get("partidas_historicas", 0)
        n_ia = cobertura.get("partidas_ia", 0)
        if n_hist and n_ia:
            msg = (
                f"✓ {n_hist} partidas del histórico (precios reales)  "
                f"·  {n_ia} partidas estimadas por IA"
            )
        elif n_hist:
            msg = f"✓ {n_hist} partidas del histórico (precios reales)"
        else:
            msg = f"✓ {n_ia} partidas generadas por IA"
        self._lbl_cobertura.setText(msg)
        self._lbl_cobertura.show()

    # ── Resultado público ─────────────────────────────────────────────────────

    def get_result(self) -> Optional[Dict]:
        """Devuelve el resultado del orquestador o None si el diálogo fue cancelado."""
        return self._result

    def get_partidas(self) -> List[Dict]:
        """Devuelve la lista de partidas generadas."""
        if self._result:
            return self._result.get("partidas", [])
        return []

    # ── Utilidades ────────────────────────────────────────────────────────────

    def _set_buttons_enabled(self, enabled: bool):
        self._btn_generar.setEnabled(enabled)
        self._btn_cancelar.setEnabled(enabled)
        if self._stt.is_available():
            self._btn_dictar.setEnabled(enabled)
