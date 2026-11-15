"""Un Excel sin cambios no se vuelve a abrir en cada recarga del dashboard.

La caché recuerda, por mtime (y revisión del lector), si alguna hoja del Excel
coincide con el número de proyecto. Mientras el mtime no cambie, la recarga no
lee el fichero ni vuelve a aplicar la política de refresco.
"""

import os
import shutil
from pathlib import Path

import pytest
from openpyxl import Workbook

from src.core import database
from src.core.budget_cache import sync_presupuestos
from src.core.budget_reader import BudgetReader
from src.core.repositories import get_presupuesto_por_ruta, upsert_presupuesto

LEGACY_SNAPSHOT = Path(__file__).parent / "fixtures" / "legacy_schema_v0.db"


def _make_excel(path, e5_values):
    wb = Workbook()
    wb.active.title = "Hoja0"
    for i, value in enumerate(e5_values):
        ws = wb.active if i == 0 else wb.create_sheet(f"Hoja{i}")
        ws["E5"] = value
        ws["B7"] = "Comunidad Excel"
    wb.save(path)


def _scanned(path, numero):
    return [{
        "nombre_carpeta": f"{numero} obra",
        "numero_proyecto": numero,
        "ruta_excel": str(path),
        "ruta_carpeta": str(path.parent),
    }]


@pytest.fixture
def reads(monkeypatch):
    calls = []
    original = BudgetReader._load_file_bytes

    def _counting(file_path):
        calls.append(file_path)
        return original(file_path)

    monkeypatch.setattr(BudgetReader, "_load_file_bytes", staticmethod(_counting))
    return calls


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "verif.db"))


def test_second_sync_of_unchanged_excel_reads_nothing(tmp_path, db, reads):
    excel = tmp_path / "5-26 obra.xlsx"
    _make_excel(excel, ["5/26"])
    sync_presupuestos(_scanned(excel, "5-26"), {}, "PRESUPUESTADO")
    reads.clear()

    result = sync_presupuestos(_scanned(excel, "5-26"), {}, "PRESUPUESTADO")

    assert reads == []
    assert result[0]["cliente"] == "Comunidad Excel"


def test_mismatching_sheet_is_not_reprocessed_and_keeps_warning(tmp_path, db, reads):
    excel = tmp_path / "7-26 obra.xlsx"
    _make_excel(excel, ["120/20", "6/26"])
    first = sync_presupuestos(_scanned(excel, "7-26"), {}, "PRESUPUESTADO")
    assert "ninguna hoja" in first[0]["motivo_incompleto"].lower()
    reads.clear()

    second = sync_presupuestos(_scanned(excel, "7-26"), {}, "PRESUPUESTADO")

    assert reads == []
    assert "ninguna hoja" in second[0]["motivo_incompleto"].lower()
    assert second[0]["total"] is None


def test_changed_mtime_reads_excel_again(tmp_path, db, reads):
    excel = tmp_path / "8-26 obra.xlsx"
    _make_excel(excel, ["8/26"])
    sync_presupuestos(_scanned(excel, "8-26"), {}, "PRESUPUESTADO")
    stat = os.stat(excel)
    os.utime(excel, (stat.st_atime, stat.st_mtime + 10))
    reads.clear()

    sync_presupuestos(_scanned(excel, "8-26"), {}, "PRESUPUESTADO")

    assert reads


def test_external_upsert_forces_one_revalidation(tmp_path, db, reads):
    excel = tmp_path / "9-26 obra.xlsx"
    _make_excel(excel, ["9/26"])
    sync_presupuestos(_scanned(excel, "9-26"), {}, "PRESUPUESTADO")
    cached = get_presupuesto_por_ruta(str(excel))
    assert cached["clave_verificacion"]

    # Otra vía (p. ej. «Escanear presupuestos») reescribe la fila con el mismo mtime.
    upsert_presupuesto({**cached, "cliente": "Otro"})
    assert get_presupuesto_por_ruta(str(excel))["clave_verificacion"] == ""
    reads.clear()

    sync_presupuestos(_scanned(excel, "9-26"), {}, "PRESUPUESTADO")
    assert reads
    reads.clear()

    sync_presupuestos(_scanned(excel, "9-26"), {}, "PRESUPUESTADO")
    assert reads == []


def test_migration_adds_verification_columns(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    shutil.copy2(LEGACY_SNAPSHOT, db_path)
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
    monkeypatch.setenv("CUBIAPP_BACKUP_DIR", str(tmp_path / "backups"))
    database.invalidate_schema_cache()

    with database.get_connection() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(presupuesto)")}
        assert {"clave_verificacion", "hoja_coincide"} <= cols
        assert conn.execute("SELECT COUNT(*) FROM presupuesto").fetchone()[0] == 1
