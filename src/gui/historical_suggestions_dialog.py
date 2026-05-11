"""
Diálogo para revisar sugerencias históricas de partidas.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.core.historical_context import (
    build_initial_historical_context,
    is_generic_historical_context,
    is_useful_historical_context,
)
from src.gui import theme


_FAILURE_HELP = {
    "NO_MODULES": (
        "No se ha podido interpretar el tipo de trabajo.",
        "Ejemplo: Reparación de bajante en patio interior con sustitución de PVC y cierre de rozas.",
    ),
    "TOO_GENERIC": (
        "Se ha detectado una descripción demasiado general.",
        "Añade zona y trabajos concretos: fachada, cubierta, patio, estructura, pintura, impermeabilización...",
    ),
    "NO_PATTERNS": (
        "Se detectaron módulos, pero no hay patrones históricos suficientes.",
        "Añade materiales, zona, alcance o elementos afectados para intentar cruzar mejor con la memoria.",
    ),
    "FILTERED_OUT": (
        "Se encontraron patrones, pero no superan frecuencia/confianza mínima.",
        "Añade materiales, zona, alcance o elementos afectados para intentar cruzar mejor con la memoria.",
    ),
}


class HistoricalSuggestionDescriptionDialog(QDialog):
    """Pide confirmar contexto antes de buscar sugerencias historicas."""

    def __init__(self, parent, project_data: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Describir trabajo para buscar en memoria")
        self._project_data = project_data or {}
        self._confirmed_context = ""
        self._search_requested = False
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        lay.setSpacing(theme.SPACE_SM)

        title = theme.create_title(self, "Describir trabajo para buscar en memoria", "lg")
        lay.addWidget(title)

        initial_context = build_initial_historical_context(self._project_data)
        intro = QLabel(
            "Describe qué se va a ejecutar, dónde y sobre qué elemento. "
            "Ejemplo: Reparación de bajante en patio interior con sustitución de PVC y cierre de rozas.",
            self,
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; background: transparent;")
        lay.addWidget(intro)

        if initial_context:
            proposed = QLabel(f"Descripción inicial propuesta:\n{initial_context}", self)
        else:
            proposed = QLabel("Descripción inicial propuesta:\n-", self)
        proposed.setWordWrap(True)
        proposed.setStyleSheet(f"color: {theme.TEXT_MUTED}; background: transparent;")
        lay.addWidget(proposed)

        self._generic_warning = QLabel(
            "La descripción inicial parece demasiado genérica. Añade zona, elemento y trabajo a ejecutar.",
            self,
        )
        self._generic_warning.setWordWrap(True)
        self._generic_warning.setStyleSheet(f"color: {theme.WARNING}; background: transparent;")
        self._generic_warning.setVisible(is_generic_historical_context(initial_context))
        lay.addWidget(self._generic_warning)

        self._context_edit = QTextEdit(self)
        self._context_edit.setPlaceholderText("Ejemplo: Reparación de bajante en patio interior con sustitución de PVC")
        self._context_edit.setMinimumHeight(150)
        self._context_edit.setPlainText(initial_context)
        lay.addWidget(self._context_edit, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        btn_continue = QPushButton("Continuar sin sugerencias", self)
        btn_continue.clicked.connect(self._on_continue_without)
        actions.addWidget(btn_continue)
        btn_search = QPushButton("Buscar en memoria", self)
        btn_search.setProperty("class", "primary")
        btn_search.clicked.connect(self._on_search)
        actions.addWidget(btn_search)
        lay.addLayout(actions)
        self.resize(820, 460)

    def _on_search(self):
        context = self._context_edit.toPlainText().strip()
        if not is_useful_historical_context(context):
            QMessageBox.warning(
                self,
                "Descripción insuficiente",
                "La descripción es demasiado breve o genérica. Añade zona, elemento y trabajo a ejecutar.",
            )
            return
        self._confirmed_context = context
        self._search_requested = True
        self.accept()

    def _on_continue_without(self):
        self._confirmed_context = ""
        self._search_requested = False
        self.reject()

    def get_confirmed_context(self) -> str:
        return self._confirmed_context

    def wants_search(self) -> bool:
        return self._search_requested


class HistoricalSuggestionContextDialog(QDialog):
    """Permite aportar contexto manual para reintentar sugerencias históricas."""

    def __init__(self, parent, suggestion_result: dict):
        super().__init__(parent)
        self.setWindowTitle("Añadir contexto para sugerencias históricas")
        self._result = suggestion_result or {}
        self._manual_context = ""
        self._search_again = False
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        lay.setSpacing(theme.SPACE_SM)

        reason = (self._result.get("failure_reason") or "").strip().upper()
        reason_msg, example = _FAILURE_HELP.get(
            reason,
            (
                "Las sugerencias históricas no son suficientes para este caso.",
                "Añade materiales, zona y alcance para mejorar la detección.",
            ),
        )
        analyzed_text = (self._result.get("input_text") or "").strip() or "(vacío)"
        detected_modules = ", ".join(m.get("label") or m.get("name") or "" for m in self._result.get("detected_modules", []))
        if not detected_modules:
            detected_modules = "-"
        patterns_found = int(self._result.get("patterns_found") or 0)
        patterns_after_filters = int(self._result.get("patterns_after_filters") or 0)

        title = theme.create_title(self, "Añadir contexto para sugerencias históricas", "lg")
        lay.addWidget(title)

        info = QLabel(
            (
                f"Texto analizado:\n{analyzed_text}\n\n"
                f"Motivo: {reason_msg}\n"
                f"Módulos detectados: {detected_modules}\n"
                f"Patrones encontrados: {patterns_found} | Tras filtros: {patterns_after_filters}\n\n"
                f"Ayuda: {example}"
            ),
            self,
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; background: transparent;")
        lay.addWidget(info)

        self._context_edit = QTextEdit(self)
        self._context_edit.setPlaceholderText(
            "Describe mejor el trabajo (zona, elementos, materiales, alcance, daños, etc.)"
        )
        self._context_edit.setMinimumHeight(140)
        lay.addWidget(self._context_edit, 1)

        actions = QHBoxLayout()
        actions.addStretch()
        btn_continue = QPushButton("Continuar sin sugerencias", self)
        btn_continue.clicked.connect(self._on_continue_without)
        actions.addWidget(btn_continue)
        btn_retry = QPushButton("Buscar de nuevo", self)
        btn_retry.setProperty("class", "primary")
        btn_retry.clicked.connect(self._on_retry)
        actions.addWidget(btn_retry)
        lay.addLayout(actions)
        self.resize(820, 480)

    def _on_retry(self):
        self._manual_context = self._context_edit.toPlainText().strip()
        if not self._manual_context:
            QMessageBox.warning(
                self,
                "Contexto requerido",
                "Escribe un contexto manual antes de volver a buscar sugerencias históricas.",
            )
            return
        self._search_again = True
        self.accept()

    def _on_continue_without(self):
        self._manual_context = ""
        self._search_again = False
        self.reject()

    def get_manual_context(self) -> str:
        return self._manual_context

    def wants_search_again(self) -> bool:
        return self._search_again


class HistoricalSuggestionsDialog(QDialog):
    """Permite activar partidas históricas y ajustar cantidad/precio."""

    def __init__(self, parent, suggestion_result: dict, project_data: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Sugerencias históricas")
        self._result = suggestion_result or {}
        self._project_data = project_data or {}
        self._modules = self._result.get("detected_modules", [])
        self._partidas = self._result.get("partidas", [])
        self._selected_partidas = []
        self._build_ui()
        self._populate()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL, theme.SPACE_XL)
        layout.setSpacing(theme.SPACE_SM)

        title = theme.create_title(panel, "Sugerencias históricas", "xl")
        layout.addWidget(title)

        stats = self._result.get("stats", {})
        self._msg_label = theme.create_text(
            panel,
            f"Basado en {stats.get('partidas_base', 0)} partidas históricas asociadas a los módulos detectados.",
        )
        self._msg_label.setWordWrap(True)
        layout.addWidget(self._msg_label)

        modules_text = ", ".join(
            f"{m.get('label', m.get('name', ''))} ({int((m.get('confidence', 0) or 0) * 100)}%)"
            for m in self._modules[:6]
        )
        self._modules_label = QLabel("", panel)
        self._modules_label.setFont(theme.font_sm())
        self._modules_label.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; background: transparent;")
        self._modules_label.setWordWrap(True)
        layout.addWidget(self._modules_label)
        self._set_modules_text(modules_text)

        self._dup_label = QLabel("", panel)
        self._dup_label.setWordWrap(True)
        self._dup_label.setStyleSheet(f"color: {theme.TEXT_TERTIARY}; background: transparent;")
        layout.addWidget(self._dup_label)
        self._update_dup_notice()

        self._table = QTableWidget(panel)
        self._table.setColumnCount(9)
        self._table.setHorizontalHeaderLabels(
            ["Usar", "Módulo", "Concepto", "Cantidad", "Unidad", "Precio Unit.", "Rango €", "Frecuencia", "Conf."]
        )
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 44)
        self._table.setColumnWidth(1, 140)
        self._table.setColumnWidth(3, 85)
        self._table.setColumnWidth(4, 70)
        self._table.setColumnWidth(5, 95)
        self._table.setColumnWidth(6, 110)
        self._table.setColumnWidth(7, 80)
        self._table.setColumnWidth(8, 70)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self._table.doubleClicked.connect(self._toggle_current_row)
        layout.addWidget(self._table, 1)

        actions = QHBoxLayout()
        btn_all = QPushButton("Seleccionar todas", panel)
        btn_all.setFont(theme.font_sm())
        btn_all.clicked.connect(self._select_all)
        actions.addWidget(btn_all)
        btn_none = QPushButton("Deseleccionar todas", panel)
        btn_none.setFont(theme.font_sm())
        btn_none.clicked.connect(self._select_none)
        actions.addWidget(btn_none)
        btn_context = QPushButton("Añadir más contexto", panel)
        btn_context.setFont(theme.font_sm())
        btn_context.clicked.connect(self._retry_with_manual_context)
        actions.addWidget(btn_context)
        actions.addStretch()
        layout.addLayout(actions)

        layout.addWidget(theme.create_divider(panel))
        buttons = QHBoxLayout()
        buttons.addStretch()
        btn_cancel = QPushButton("Saltar", panel)
        btn_cancel.setFont(theme.font_base())
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)
        buttons.addSpacing(8)
        btn_apply = QPushButton("Insertar seleccionadas", panel)
        btn_apply.setFont(theme.get_font_medium())
        btn_apply.setProperty("class", "primary")
        btn_apply.clicked.connect(self._on_apply)
        buttons.addWidget(btn_apply)
        layout.addLayout(buttons)

        main_layout.addWidget(panel)
        self.resize(980, 600)

    def _set_modules_text(self, modules_text: str):
        if modules_text:
            self._modules_label.setText(f"Módulos detectados: {modules_text}")
            self._modules_label.show()
        else:
            self._modules_label.hide()

    def _update_dup_notice(self):
        removed = int(self._result.get("duplicates_hidden_count") or 0)
        if removed > 0:
            self._dup_label.setText(f"Se han ocultado {removed} sugerencias similares.")
            self._dup_label.show()
        else:
            self._dup_label.clear()
            self._dup_label.hide()

    def _populate(self):
        stats = self._result.get("stats", {})
        self._msg_label.setText(
            f"Basado en {stats.get('partidas_base', 0)} partidas históricas asociadas a los módulos detectados."
        )
        modules_text = ", ".join(
            f"{m.get('label', m.get('name', ''))} ({int((m.get('confidence', 0) or 0) * 100)}%)"
            for m in self._modules[:6]
        )
        self._set_modules_text(modules_text)
        self._table.setRowCount(len(self._partidas))
        for i, partida in enumerate(self._partidas):
            use_checked = (
                float(partida.get("confidence", 0.0)) >= 0.7
                and int(partida.get("historical_frequency", 0)) >= 3
            )
            use_item = QTableWidgetItem()
            use_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
            )
            use_item.setCheckState(
                Qt.CheckState.Checked if use_checked else Qt.CheckState.Unchecked
            )
            use_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(i, 0, use_item)
            self._table.setItem(i, 1, QTableWidgetItem(str(partida.get("module", ""))))
            self._table.setItem(i, 2, QTableWidgetItem(str(partida.get("concepto", ""))))

            qty_item = QTableWidgetItem(str(partida.get("cantidad", 1)))
            qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 3, qty_item)

            self._table.setItem(i, 4, QTableWidgetItem(str(partida.get("unidad", "ud"))))

            price_item = QTableWidgetItem(str(partida.get("precio_unitario", 0.0)))
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 5, price_item)

            rango_min = float(partida.get("precio_min", 0.0))
            rango_max = float(partida.get("precio_max", 0.0))
            rango_item = QTableWidgetItem(f"{rango_min:.2f}-{rango_max:.2f}")
            rango_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 6, rango_item)

            freq_item = QTableWidgetItem(str(partida.get("historical_frequency", 0)))
            freq_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 7, freq_item)

            conf = float(partida.get("confidence", 0.0))
            conf_item = QTableWidgetItem(f"{int(conf * 100)}%")
            conf_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(i, 8, conf_item)

        # Solo cantidad y precio son editables
        for row in range(self._table.rowCount()):
            for col in (3, 5):
                item = self._table.item(row, col)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self._update_dup_notice()

    def _toggle_current_row(self):
        row = self._table.currentRow()
        if row < 0:
            return
        it = self._table.item(row, 0)
        if it is None:
            return
        it.setCheckState(
            Qt.CheckState.Unchecked
            if it.checkState() == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )

    def _select_all(self):
        for i in range(self._table.rowCount()):
            it = self._table.item(i, 0)
            if it is not None:
                it.setCheckState(Qt.CheckState.Checked)

    def _select_none(self):
        for i in range(self._table.rowCount()):
            it = self._table.item(i, 0)
            if it is not None:
                it.setCheckState(Qt.CheckState.Unchecked)

    def _on_apply(self):
        selected = []
        for row, partida in enumerate(self._partidas):
            use_it = self._table.item(row, 0)
            if use_it is None or use_it.checkState() != Qt.CheckState.Checked:
                continue
            try:
                cantidad = float((self._table.item(row, 3).text() or "1").replace(",", "."))
                precio = float((self._table.item(row, 5).text() or "0").replace(",", "."))
            except ValueError:
                QMessageBox.warning(
                    self, "Valor inválido", "Cantidad y precio deben ser numéricos."
                )
                return

            concepto = str(partida.get("concepto", "")).strip()
            titulo = str(partida.get("titulo", "")).strip() or concepto.upper()
            descripcion = str(partida.get("descripcion", "")).strip()
            selected.append(
                {
                    "titulo": titulo,
                    "descripcion": descripcion,
                    "concepto": concepto,
                    "cantidad": cantidad,
                    "unidad": str(partida.get("unidad", "ud")),
                    "precio_unitario": precio,
                }
            )
        self._selected_partidas = selected
        self.accept()

    def _retry_with_manual_context(self):
        from src.core.historical_suggestion_service import HistoricalSuggestionService

        context_dlg = HistoricalSuggestionContextDialog(self, self._result)
        if context_dlg.exec() != 1 or not context_dlg.wants_search_again():
            return

        manual_context = context_dlg.get_manual_context()
        fresh = HistoricalSuggestionService().suggest_for_project(
            self._project_data or {},
            user_description=manual_context,
        )
        if not fresh.get("partidas"):
            detected_modules = ", ".join(
                m.get("label") or m.get("name") or ""
                for m in fresh.get("detected_modules", [])
            ) or "-"
            QMessageBox.information(
                self,
                "Sugerencias históricas",
                (
                    f"{fresh.get('message', 'No se han encontrado sugerencias suficientes.')}\n\n"
                    f"Motivo: {fresh.get('failure_reason', '-')}\n"
                    f"Texto analizado: {fresh.get('input_text', '') or '(vacío)'}\n"
                    f"Módulos detectados: {detected_modules}\n"
                    f"Patrones encontrados: {int(fresh.get('patterns_found') or 0)} | "
                    f"Tras filtros: {int(fresh.get('patterns_after_filters') or 0)}\n\n"
                    "Puedes continuar con las sugerencias actuales o seguir con IA."
                ),
            )
            return

        from src.core.historical_suggestions_dedupe import dedupe_historical_partidas

        deduped, removed = dedupe_historical_partidas(fresh.get("partidas", []))
        fresh["partidas"] = deduped
        fresh["duplicates_hidden_count"] = removed

        self._result = fresh
        self._modules = fresh.get("detected_modules", [])
        self._partidas = fresh.get("partidas", [])
        self._selected_partidas = []
        self._populate()

    def get_selected_partidas(self):
        return self._selected_partidas
