"""Aviso pasajero: no bloquea, se cierra solo y ejecuta sus acciones."""

import pytest

try:
    from PySide6.QtWidgets import QMainWindow

    from src.gui.widgets.toast import Toast, current_toast, show_toast

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


@pytest.fixture
def window(qapp):
    w = QMainWindow()
    w.resize(600, 400)
    yield w
    w.close()


def test_toast_without_actions_uses_short_timeout(window):
    toast = show_toast(window, "Releídos 3")
    assert isinstance(toast, Toast)
    assert toast.text() == "Releídos 3"
    assert toast.action_labels() == []
    assert toast.timeout_ms() == 5000
    assert current_toast(window) is toast


def test_toast_with_actions_runs_callback_and_closes(window):
    calls = []
    toast = show_toast(window, "3 movidos", actions=[("Deshacer", lambda: calls.append(1))])
    assert toast.timeout_ms() == 8000
    assert toast.action_labels() == ["Deshacer"]
    toast.trigger("Deshacer")
    assert calls == [1]
    assert current_toast(window) is None


def test_new_toast_replaces_previous(window):
    first = show_toast(window, "uno")
    second = show_toast(window, "dos")
    assert current_toast(window) is second
    assert first.isHidden()


def test_explicit_timeout(window):
    assert show_toast(window, "x", timeout_ms=1234).timeout_ms() == 1234
