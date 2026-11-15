"""
H08: distinguir un snapshot finalizado de la version actual del Excel.

El escaneo no debe presentar como actuales datos finalizados cuando el fichero
cambio despues; y el observador del Excel abierto debe seguir vigilando tras el
primer guardado en vez de rendirse a los pocos minutos.
"""

import os
import threading
import time
from datetime import datetime

from src.core.budget_cache import (
    _get_file_mtime_iso,
    _wait_for_excel_change,
    sync_presupuestos,
)
from src.core.repositories import upsert_presupuesto_finalizado


def _seed_finalized(tmp_path, excel_path, mtime_iso):
    payload = {
        "numero_proyecto": "001-26",
        "nombre_proyecto": "001-26 obra",
        "ruta_excel": str(excel_path),
        "ruta_carpeta": str(tmp_path),
        "estado": "PRESUPUESTADO",
        "cliente": "Comunidad Test",
        "localidad": "Alicante",
        "tipo_obra": "Reforma",
        "fecha": "2026-01-01",
        "total": 100.0,
        "subtotal": 90.0,
        "iva": 10.0,
        "fecha_modificacion_excel": mtime_iso,
        "datos_completos": True,
    }
    _id, err = upsert_presupuesto_finalizado(payload, [])
    assert err is None


def _scanned(tmp_path, excel_path):
    return [
        {
            "nombre_carpeta": "001-26 obra",
            "numero_proyecto": "001-26",
            "ruta_excel": str(excel_path),
            "ruta_carpeta": str(tmp_path),
        }
    ]


def test_finalized_snapshot_flagged_stale_when_excel_mtime_changed(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "stale.db"))
    excel = tmp_path / "001-26.xlsx"
    excel.write_bytes(b"contenido")
    _seed_finalized(tmp_path, excel, "2026-01-01T00:00:00")

    result = sync_presupuestos(_scanned(tmp_path, excel), {}, "PRESUPUESTADO")

    row = result[0]
    assert row["es_finalizado"] is True
    assert row["snapshot_desactualizado"] is True
    assert "cambió" in row["aviso_actualizacion"]


def test_finalized_snapshot_not_flagged_when_excel_mtime_matches(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "current.db"))
    excel = tmp_path / "001-26.xlsx"
    excel.write_bytes(b"contenido")
    _seed_finalized(tmp_path, excel, _get_file_mtime_iso(str(excel)))

    result = sync_presupuestos(_scanned(tmp_path, excel), {}, "PRESUPUESTADO")

    row = result[0]
    assert row["es_finalizado"] is True
    assert row["snapshot_desactualizado"] is False
    assert row["aviso_actualizacion"] == ""


def test_wait_for_excel_change_detects_change(tmp_path):
    excel = tmp_path / "watch.xlsx"
    excel.write_bytes(b"v1")
    baseline = os.path.getmtime(excel)
    stop = threading.Event()

    outcomes = {}

    def _run():
        outcomes["changed"] = _wait_for_excel_change(excel, stop, baseline, poll_seconds=0.01)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    time.sleep(0.05)
    os.utime(excel, (baseline + 10, baseline + 10))
    thread.join(timeout=5)

    assert outcomes.get("changed") is True


def test_wait_for_excel_change_stops_when_asked(tmp_path):
    excel = tmp_path / "watch_stop.xlsx"
    excel.write_bytes(b"v1")
    baseline = os.path.getmtime(excel)
    stop = threading.Event()

    outcomes = {}

    def _run():
        outcomes["changed"] = _wait_for_excel_change(excel, stop, baseline, poll_seconds=0.01)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    stop.set()
    thread.join(timeout=5)

    assert outcomes.get("changed") is False
