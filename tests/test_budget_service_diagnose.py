"""«Escanear presupuestos» explica por qué no se pudo leer cada Excel."""

from openpyxl import Workbook

from src.core.services.budget_service import BudgetService


def _excel(path, e5_values):
    wb = Workbook()
    for i, value in enumerate(e5_values):
        ws = wb.active if i == 0 else wb.create_sheet(f"Hoja{i}")
        ws["E5"] = value
    wb.save(path)
    return str(path)


def test_missing_file():
    assert BudgetService().diagnose_read_failure("C:/no/existe.xlsx", "1-26") == "No existe el fichero"


def test_no_sheet_matches_lists_e5_values(tmp_path):
    ruta = _excel(tmp_path / "107-26 obra.xlsx", ["106/26", ""])

    motivo = BudgetService().diagnose_read_failure(ruta, "107-26")

    assert motivo == "Ninguna hoja coincide con 107-26: E5 dice 106/26"


def test_no_sheet_matches_with_empty_e5(tmp_path):
    ruta = _excel(tmp_path / "31-26 obra.xlsx", ["", ""])

    motivo = BudgetService().diagnose_read_failure(ruta, "31-26")

    assert motivo == "Ninguna hoja coincide con 31-26: E5 vacío en todas las hojas"


def test_unreadable_file(tmp_path):
    ruta = tmp_path / "roto.xlsx"
    ruta.write_bytes(b"esto no es un zip")

    motivo = BudgetService().diagnose_read_failure(str(ruta), "1-26")

    assert motivo == "No se pudo leer el Excel (formato no reconocido o fichero dañado)"
