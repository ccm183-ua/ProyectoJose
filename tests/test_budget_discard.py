"""
S1-D / H04: BudgetService.discard_budget deshace un presupuesto recién creado
que el usuario decidió no conservar, sin borrar nunca contenido del usuario.
"""

import pytest

from src.core import db_repository
from src.core.services.budget_service import BudgetService


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_discard.db"))
    return tmp_path


_SUBFOLDERS = ["FOTOS", "PLANOS", "PROYECTO", "MEDICIONES", "PRESUPUESTOS"]


def _crear_borrador(tmp_path):
    folder = tmp_path / "Obra"
    folder.mkdir()
    for name in _SUBFOLDERS:
        (folder / name).mkdir()
    excel = folder / "obra.xlsx"
    excel.write_bytes(b"contenido")
    db_repository.registrar_presupuesto({
        "nombre_proyecto": "Obra",
        "ruta_excel": str(excel),
        "ruta_carpeta": str(folder),
    })
    return folder, excel


def test_discard_budget_borra_excel_historial_y_carpetas_vacias(db_env):
    folder, excel = _crear_borrador(db_env)

    ok = BudgetService().discard_budget(str(excel), str(folder))

    assert ok is True
    assert not excel.exists()
    assert not folder.exists()
    assert all(
        entry["ruta_excel"] != str(excel)
        for entry in db_repository.get_historial_reciente()
    )


def test_discard_budget_conserva_carpetas_con_contenido(db_env):
    folder, excel = _crear_borrador(db_env)
    plano = folder / "PLANOS" / "plano.pdf"
    plano.write_bytes(b"plano")

    ok = BudgetService().discard_budget(str(excel), str(folder))

    assert ok is True
    assert not excel.exists()
    assert plano.exists()
    assert folder.exists()


def test_discard_budget_informa_si_no_puede_borrar_el_excel(db_env, monkeypatch):
    folder, excel = _crear_borrador(db_env)

    def _raise_oserror(*args, **kwargs):
        raise OSError("bloqueado")

    monkeypatch.setattr("src.core.services.budget_service.os.remove", _raise_oserror)

    ok = BudgetService().discard_budget(str(excel), str(folder))

    assert ok is False
    assert excel.exists()
    assert any(
        entry["ruta_excel"] == str(excel)
        for entry in db_repository.get_historial_reciente()
    )
