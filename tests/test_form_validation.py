"""
S3-E / H18: un unico intento debe revelar todos los campos invalidos.

Cubre el contrato de `run_validations` (todos los errores en un solo resumen,
marca por control y foco en el primero) y la integracion con los cuatro
dialogos de la base de datos.
"""

import pytest

try:
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QVBoxLayout
    from PySide6.QtWidgets import QMessageBox

    from src.gui.db_validations import (
        run_validations,
        validate_cif,
        validate_email,
        validate_phone,
    )

    _HAS_PYSIDE6 = True
except ImportError:  # pragma: no cover - entorno sin PySide6
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


class _ModalSpy:
    """Intercepta los modales; bajo offscreen uno real cuelga la suite."""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    def _record(self, kind):
        def handler(*args, **kwargs):
            self.calls.append((kind, args))
            return None

        return staticmethod(handler)

    def install(self, monkeypatch):
        monkeypatch.setattr(QMessageBox, "warning", self._record("warning"))
        monkeypatch.setattr(QMessageBox, "information", self._record("information"))
        monkeypatch.setattr(QMessageBox, "critical", self._record("critical"))

    @property
    def body(self):
        assert len(self.calls) == 1, f"se esperaba un unico modal, hubo {len(self.calls)}"
        return self.calls[0][1][2]


@pytest.fixture
def modals(monkeypatch):
    spy = _ModalSpy()
    spy.install(monkeypatch)
    return spy


@pytest.fixture
def form_dialog(qapp):
    dialog = QDialog()
    layout = QVBoxLayout(dialog)
    widgets = {}
    for label in ("nombre", "email", "telefono"):
        widget = QLineEdit(dialog)
        widgets[label] = widget
        layout.addWidget(widget)
    dialog._ctrls = widgets
    dialog.show()
    qapp.processEvents()
    yield dialog
    dialog.close()


_LABELS = {"nombre": "Nombre", "email": "Email", "telefono": "Teléfono"}


def _checks(dialog, errors):
    return [(dialog._ctrls[key], _LABELS[key], err) for key, err in errors.items()]


def test_run_validations_reports_every_invalid_field_in_one_call(form_dialog, modals):
    errors = {
        "nombre": "El nombre es obligatorio.",
        "email": "El formato de email no es válido (ej: usuario@dominio.com).",
        "telefono": "El teléfono debe tener al menos 9 dígitos.",
    }
    assert run_validations(form_dialog, _checks(form_dialog, errors)) is False
    assert modals.calls[0][0] == "warning"
    body = modals.body
    for label, message in (
        ("Nombre", errors["nombre"]),
        ("Email", errors["email"]),
        ("Teléfono", errors["telefono"]),
    ):
        assert label in body
        assert message in body


def test_run_validations_focuses_first_invalid_widget(form_dialog, modals):
    form_dialog._ctrls["telefono"].setFocus()
    QApplication.processEvents()
    assert form_dialog.focusWidget() is form_dialog._ctrls["telefono"]
    run_validations(form_dialog, _checks(form_dialog, {"nombre": "obligatorio", "email": "malo"}))
    assert form_dialog.focusWidget() is form_dialog._ctrls["nombre"]


def test_run_validations_clears_marks_and_returns_true_when_fixed(form_dialog, modals):
    errors = {"nombre": "obligatorio", "email": "malo", "telefono": "corto"}
    run_validations(form_dialog, _checks(form_dialog, errors))
    assert len(modals.calls) == 1
    for widget in form_dialog._ctrls.values():
        assert widget.property("error") is True
    assert form_dialog._ctrls["nombre"].toolTip() == "obligatorio"

    assert run_validations(form_dialog, _checks(form_dialog, dict.fromkeys(errors))) is True
    assert len(modals.calls) == 1
    for widget in form_dialog._ctrls.values():
        assert widget.property("error") is False
        assert widget.toolTip() == ""


def test_run_validations_returns_true_without_modal_when_all_valid(form_dialog, modals):
    assert run_validations(form_dialog, _checks(form_dialog, {"nombre": None})) is True
    assert modals.calls == []


def test_keyboard_correction_lands_on_first_invalid_field(form_dialog, modals):
    run_validations(form_dialog, _checks(form_dialog, {"email": "malo", "nombre": "obligatorio"}))
    focused = form_dialog.focusWidget()
    assert focused is form_dialog._ctrls["email"]
    QTest.keyClicks(focused, "Ana")
    assert focused.text() == "Ana"


@pytest.mark.parametrize(
    ("validator", "value", "expected_error"),
    [
        (validate_phone, "612345678", None),
        (validate_phone, "12", "El teléfono debe tener al menos 9 dígitos."),
        (validate_phone, "abc", "El teléfono contiene caracteres no válidos."),
        (validate_phone, "", None),
        (validate_email, "a@b.com", None),
        (validate_email, "nope", "El formato de email no es válido (ej: usuario@dominio.com)."),
        (validate_email, "", None),
        (validate_cif, "B12345678", None),
        (validate_cif, "12345678A", None),
        (validate_cif, "123", "El CIF/NIF no parece válido (ej: B12345678 o 12345678A)."),
        (validate_cif, "", None),
    ],
)
def test_existing_format_validators_unchanged(validator, value, expected_error):
    assert validator(value) == expected_error


def test_quick_contacto_one_attempt_lists_three_invalid_fields(qapp, monkeypatch, modals):
    from src.gui import quick_dialogs

    monkeypatch.setattr(quick_dialogs.repo, "create_contacto", lambda *a, **k: (1, None))
    dialog = quick_dialogs.QuickContactoDialog()
    dialog._fields["telefono"].setText("12")
    dialog._fields["email"].setText("nope")
    dialog.show()
    qapp.processEvents()
    dialog._fields["email"].setFocus()
    qapp.processEvents()

    dialog._on_ok()

    assert modals.calls[0][0] == "warning"
    body = modals.body
    assert "Nombre" in body
    assert "Teléfono" in body
    assert "Email" in body
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.focusWidget() is dialog._fields["nombre"]
    assert dialog._fields["telefono"].text() == "12"
    assert dialog._fields["email"].text() == "nope"

    dialog._fields["nombre"].setText("Ana")
    dialog._fields["telefono"].setText("612345678")
    dialog._fields["email"].setText("ana@dominio.com")
    dialog._on_ok()
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_quick_contacto_keeps_required_and_format_errors(qapp, monkeypatch, modals):
    from src.gui import quick_dialogs

    dialog = quick_dialogs.QuickContactoDialog()
    dialog.show()
    qapp.processEvents()
    dialog._on_ok()
    assert "El teléfono es obligatorio." in modals.body

    dialog._fields["telefono"].setText("12")
    dialog._fields["nombre"].setText("Ana")
    dialog._on_ok()
    assert "El teléfono debe tener al menos 9 dígitos." in modals.calls[-1][1][2]


def test_admin_form_one_attempt_lists_all_and_focuses_first(qapp, monkeypatch, modals):
    from src.gui import admin_form_dialog

    monkeypatch.setattr(admin_form_dialog.repo, "get_contactos", lambda: [])
    dialog = admin_form_dialog.AdminFormDialog(None, "Nueva administración")
    dialog._ctrls["email"].setText("nope")
    dialog._ctrls["telefono"].setText("12")
    dialog.show()
    qapp.processEvents()
    dialog._ctrls["telefono"].setFocus()
    qapp.processEvents()

    dialog._on_ok()

    body = modals.body
    for label in ("Nombre", "Email", "Teléfono"):
        assert label in body
    assert dialog.focusWidget() is dialog._ctrls["nombre"]
    assert dialog._ctrls["nombre"].property("error") is True
    assert dialog._ctrls["email"].property("error") is True
    assert dialog._ctrls["telefono"].property("error") is True
    assert dialog._ctrls["email"].text() == "nope"
    assert dialog._ctrls["telefono"].text() == "12"


def test_comunidad_form_one_attempt_includes_required_admin(qapp, monkeypatch, modals):
    from src.gui import comunidad_form_dialog

    monkeypatch.setattr(comunidad_form_dialog.repo, "get_administraciones", lambda: [])
    monkeypatch.setattr(comunidad_form_dialog.repo, "get_contactos", lambda: [])
    dialog = comunidad_form_dialog.ComunidadFormDialog(None, "Nueva comunidad")
    dialog._ctrls["cif"].setText("123")
    dialog._ctrls["email"].setText("nope")
    dialog.show()
    qapp.processEvents()
    dialog._ctrls["telefono"].setFocus()
    qapp.processEvents()

    dialog._on_ok()

    body = modals.body
    for label in ("Nombre", "CIF", "Email", "Administración"):
        assert label in body
    assert dialog.focusWidget() is dialog._ctrls["nombre"]
    assert dialog._admin_widget.editor.property("error") is True


def test_quick_admin_form_one_attempt_lists_all(qapp, monkeypatch, modals):
    from src.gui import quick_dialogs

    dialog = quick_dialogs.QuickAdminDialog()
    dialog._fields["email"].setText("nope")
    dialog._fields["telefono"].setText("12")
    dialog.show()
    qapp.processEvents()
    dialog._fields["telefono"].setFocus()
    qapp.processEvents()

    dialog._on_ok()

    body = modals.body
    for label in ("Nombre", "Email", "Teléfono"):
        assert label in body
    assert dialog.focusWidget() is dialog._fields["nombre"]
