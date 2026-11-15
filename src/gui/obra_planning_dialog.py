"""Diálogo de planificación de una obra (o varias a la vez): fechas, margen y notas.

No guarda nada: devuelve los cambios para `upsert_plan`. Ver
docs/superpowers/specs/2026-11-13-planificacion-obras-design.md.
"""

from datetime import date
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)


class _OptionalDate(QWidget):
    """Casilla "con fecha" + selector con calendario (QDateEdit no admite vacío)."""

    def __init__(self, parent=None, value: Optional[date] = None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self._check = QCheckBox(self)
        self._edit = QDateEdit(self)
        self._edit.setCalendarPopup(True)
        self._edit.setDisplayFormat("dd/MM/yyyy")
        self._check.toggled.connect(self._edit.setEnabled)
        lay.addWidget(self._check)
        lay.addWidget(self._edit, 1)
        self.set_value(value)

    def set_value(self, value: Optional[date]) -> None:
        self._check.setChecked(value is not None)
        self._edit.setEnabled(value is not None)
        self._edit.setDate(QDate(value.year, value.month, value.day) if value else QDate.currentDate())

    def is_set(self) -> bool:
        return self._check.isChecked()

    def value(self) -> Optional[date]:
        if not self.is_set():
            return None
        q = self._edit.date()
        return date(q.year(), q.month(), q.day())


class ObraPlanningDialog(QDialog):
    def __init__(
        self,
        parent=None,
        titulo: str = "",
        plan: Optional[Dict] = None,
        margen_general: int = 7,
        propuesta: Optional[Tuple[date, bool]] = None,
        varias: bool = False,
    ):
        super().__init__(parent)
        self.setWindowTitle("Planificación de la obra" if not varias else "Planificación de varias obras")
        self._plan = dict(plan or {})
        self._varias = varias
        self._changes: Optional[Dict] = None

        lay = QVBoxLayout(self)
        cabecera = QLabel(titulo, self)
        cabecera.setWordWrap(True)
        lay.addWidget(cabecera)

        form = QFormLayout()
        inicio = self._plan.get("inicio_previsto")
        self._aviso_propuesta = QLabel("", self)
        if inicio is None and propuesta:
            inicio = propuesta[0]
            texto = "aproximada, tomada del nombre de la carpeta" if propuesta[1] else "tomada del nombre de la carpeta"
            self._aviso_propuesta.setText(f"Fecha propuesta ({texto}): revísala y guarda para confirmarla.")
        self._inicio_previsto = _OptionalDate(self, inicio)
        self._fin_previsto = _OptionalDate(self, self._plan.get("fin_previsto"))
        form.addRow("Inicio previsto:", self._inicio_previsto)
        form.addRow("Fin previsto:", self._fin_previsto)

        if not varias:
            self._inicio_real = _OptionalDate(self, self._plan.get("inicio_real"))
            self._inicio_real_aprox = QCheckBox("aproximada", self)
            self._inicio_real_aprox.setChecked(bool(self._plan.get("inicio_real_aproximado")))
            self._fin_real = _OptionalDate(self, self._plan.get("fin_real"))
            self._fin_real_aprox = QCheckBox("aproximada", self)
            self._fin_real_aprox.setChecked(bool(self._plan.get("fin_real_aproximado")))
            form.addRow("Inicio real:", self._row(self._inicio_real, self._inicio_real_aprox))
            form.addRow("Fin real:", self._row(self._fin_real, self._fin_real_aprox))
            self._margen = QSpinBox(self)
            self._margen.setRange(-1, 365)
            self._margen.setSpecialValueText(f"General ({margen_general} días)")
            margen = self._plan.get("margen_aviso_dias")
            self._margen.setValue(-1 if margen is None else int(margen))
            self._margen.setSuffix(" días")
            form.addRow("Margen de aviso:", self._margen)
            self._notas = QLineEdit(self._plan.get("notas") or "", self)
            form.addRow("Notas:", self._notas)
        lay.addLayout(form)
        lay.addWidget(self._aviso_propuesta)

        botones = QHBoxLayout()
        btn_clear = QPushButton("Quitar fechas", self)
        btn_clear.clicked.connect(self._on_clear_dates)
        btn_cancel = QPushButton("Cancelar", self)
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Guardar", self)
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._on_save)
        botones.addWidget(btn_clear)
        botones.addStretch(1)
        botones.addWidget(btn_cancel)
        botones.addWidget(btn_save)
        lay.addLayout(botones)

    @staticmethod
    def _row(*widgets) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        for x in widgets:
            lay.addWidget(x)
        return w

    def _collect(self) -> Dict:
        changes: Dict = {
            "inicio_previsto": self._inicio_previsto.value(),
            "fin_previsto": self._fin_previsto.value(),
        }
        if not self._varias:
            changes.update(
                inicio_real=self._inicio_real.value(),
                inicio_real_aproximado=self._inicio_real.is_set() and self._inicio_real_aprox.isChecked(),
                fin_real=self._fin_real.value(),
                fin_real_aproximado=self._fin_real.is_set() and self._fin_real_aprox.isChecked(),
                margen_aviso_dias=None if self._margen.value() < 0 else self._margen.value(),
                notas=self._notas.text().strip() or None,
            )
        return changes

    @staticmethod
    def _incoherent(inicio: Optional[date], fin: Optional[date]) -> bool:
        return inicio is not None and fin is not None and fin < inicio

    def _on_save(self):
        changes = self._collect()
        if self._incoherent(changes["inicio_previsto"], changes["fin_previsto"]) or self._incoherent(
            changes.get("inicio_real"), changes.get("fin_real")
        ):
            QMessageBox.warning(self, "Planificación", "La fecha de fin no puede ser anterior a la de inicio.")
            return
        self._changes = changes
        self.accept()

    def _on_clear_dates(self):
        for w in (self._inicio_previsto, self._fin_previsto):
            w.set_value(None)
        if not self._varias:
            self._inicio_real.set_value(None)
            self._fin_real.set_value(None)
        self._changes = self._collect()
        self.accept()

    def get_changes(self) -> Optional[Dict]:
        """Campos para upsert_plan, o None si se canceló."""
        return self._changes
