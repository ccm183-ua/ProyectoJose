"""Operaciones pesadas fuera del hilo de interfaz para diálogos con acciones de escritura."""

from PySide6.QtWidgets import QMessageBox

from src.utils.helpers import run_in_background


class BusyOperationsMixin:
    """Para subclases de QDialog (va antes de QDialog en las bases).

    Redefinir ``_busy_controls`` (controles a bloquear), ``_set_busy_status`` (texto de
    estado) y ``_after_busy`` (recarga de datos, tras terminar con o sin error).
    """

    _busy = False
    _closed = False

    def _busy_controls(self) -> tuple:
        return ()

    def _set_busy_status(self, text: str) -> None:
        pass

    def _after_busy(self) -> None:
        pass

    def done(self, r: int):
        self._closed = True
        super().done(r)

    def closeEvent(self, event):
        self._closed = True
        super().closeEvent(event)

    def _run_busy(self, label: str, work, on_done) -> None:
        """Ejecuta *work* fuera del hilo de UI con los controles de escritura bloqueados.

        *work* no debe tocar widgets. *on_done(resultado)* corre en el hilo de UI; si el
        diálogo se cerró mientras tanto, se descarta el resultado (el trabajo ya se hizo).
        """
        if self._busy:
            QMessageBox.information(self, label, "Hay otra operación en curso. Espera a que termine.")
            return
        self._busy = True
        controls = self._busy_controls()
        for control in controls:
            control.setEnabled(False)
        self._set_busy_status(f"{label}…")

        def _finish(ok, payload):
            self._busy = False
            if self._closed:
                return
            for control in controls:
                control.setEnabled(True)
            self._after_busy()
            if not ok:
                QMessageBox.warning(self, label, f"No se pudo completar la operación:\n{payload}")
                return
            on_done(payload)

        run_in_background(work, _finish)
