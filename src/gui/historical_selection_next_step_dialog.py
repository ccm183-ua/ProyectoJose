"""
Decisión tras seleccionar partidas históricas (estilo aviso estándar).
"""

from PySide6.QtWidgets import QMessageBox


class HistoricalSelectionNextStepDialog:
    """Mantiene constantes y API compatible; internamente usa QMessageBox."""

    CREATE_ONLY = "CREATE_ONLY"
    COMPLETE_WITH_AI = "COMPLETE_WITH_AI"
    CANCEL = "CANCEL"

    def __init__(self, parent=None, selected_count: int = 0):
        self._parent = parent
        self._selected_count = selected_count
        self._result = self.CANCEL

    def exec(self) -> int:
        box = QMessageBox(self._parent)
        box.setMinimumWidth(420)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Partidas seleccionadas")
        box.setText(
            f"Has seleccionado {self._selected_count} partidas históricas.\n\n"
            "¿Quieres crear el presupuesto con ellas o pedir a la IA que proponga complementos?"
        )
        btn_solo = box.addButton("Crear", QMessageBox.ButtonRole.AcceptRole)
        btn_ia = box.addButton("Usar IA", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(btn_solo)
        box.exec()
        clicked = box.clickedButton()
        if clicked == btn_solo:
            self._result = self.CREATE_ONLY
        elif clicked == btn_ia:
            self._result = self.COMPLETE_WITH_AI
        else:
            self._result = self.CANCEL
        return 1

    def get_result(self) -> str:
        return self._result
