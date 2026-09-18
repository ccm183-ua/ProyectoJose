"""Tests de contrato de run_in_background (H05).

El helper debe entregar exactamente una respuesta de finalización al callback,
siempre en el hilo de UI, tanto si el trabajo tuvo éxito como si lanzó.
"""

import threading

import pytest

try:
    from PySide6.QtWidgets import QApplication  # noqa: F401

    from src.utils.helpers import run_in_background

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


def _run_and_collect(work_fn, qapp):
    received = []

    def callback(ok, payload):
        received.append((ok, payload))

    thread = run_in_background(work_fn, callback)
    thread.join(5)
    assert not thread.is_alive(), "el worker no terminó a tiempo"
    qapp.processEvents()
    return received


def test_worker_exception_reaches_callback_exactly_once(qapp):
    def work():
        raise ValueError("boom")

    received = _run_and_collect(work, qapp)

    assert len(received) == 1
    ok, payload = received[0]
    assert ok is False
    assert isinstance(payload, ValueError)
    assert str(payload) == "boom"


def test_worker_result_reaches_callback_exactly_once(qapp):
    received = _run_and_collect(lambda: 42, qapp)

    assert received == [(True, 42)]


def test_callback_runs_on_the_ui_thread(qapp):
    seen = []

    def callback(ok, payload):
        seen.append(threading.current_thread())

    thread = run_in_background(lambda: 1, callback)
    thread.join(5)
    assert not thread.is_alive(), "el worker no terminó a tiempo"
    qapp.processEvents()

    assert seen == [threading.main_thread()]
    assert seen[0] is not thread
