"""
Tests para BudgetReader.

Cubre:
- Lectura de cabecera (numero, fecha, cliente, CIF, direccion, CP, etc.)
- Lectura de partidas (concepto, unidad, cantidad, precio, importe)
- Cálculo de totales (subtotal, IVA, total)
- Manejo de archivos inexistentes o corruptos
"""

import os
import shutil
import pytest

from src.core.budget_reader import BudgetReader
from src.core.excel_manager import ExcelManager
from src.core.template_manager import TemplateManager


@pytest.fixture
def template_path():
    """Ruta a la plantilla 122-20 real del proyecto."""
    tm = TemplateManager()
    path = tm.get_template_path()
    if not os.path.exists(path):
        pytest.skip("Plantilla 122-20 no encontrada")
    return path


@pytest.fixture
def budget_file(tmp_path, template_path):
    """Crea un presupuesto de prueba desde la plantilla con datos de cabecera."""
    em = ExcelManager()
    out = str(tmp_path / "test_budget.xlsx")
    data = {
        "nombre_obra": "001/26 COM.NORTE - MURCIA (Bajante)",
        "numero_proyecto": "001",
        "fecha": "08-01-26",
        "cliente": "COMUNIDAD DE PROPIETARIOS NORTE",
        "calle": "C/ Mayor",
        "num_calle": "5",
        "codigo_postal": "30001",
        "tipo": "Reparación de bajante",
        "admin_cif": "B12345678",
        "admin_email": "admin@test.com",
        "admin_telefono": "968111222",
    }
    ok = em.create_from_template(template_path, out, data)
    assert ok, "No se pudo crear el presupuesto de prueba"
    return out


@pytest.fixture
def budget_with_partidas(budget_file):
    """Presupuesto con partidas insertadas."""
    em = ExcelManager()
    partidas = [
        {
            "titulo": "DESMONTAJE DE BAJANTE.",
            "descripcion": "Desmontaje de bajante de fibrocemento.",
            "concepto": "DESMONTAJE DE BAJANTE.\nDesmontaje de bajante de fibrocemento.",
            "cantidad": 12,
            "unidad": "ml",
            "precio_unitario": 18.50,
        },
        {
            "titulo": "INSTALACIÓN NUEVA BAJANTE.",
            "descripcion": "Instalación de bajante de PVC.",
            "concepto": "INSTALACIÓN NUEVA BAJANTE.\nInstalación de bajante de PVC.",
            "cantidad": 12,
            "unidad": "ml",
            "precio_unitario": 25.00,
        },
    ]
    ok = em.insert_partidas_via_xml(budget_file, partidas)
    assert ok, "No se pudieron insertar partidas de prueba"
    return budget_file


class TestBudgetReaderHeader:
    """Lectura de datos de cabecera."""

    def test_lee_cabecera_basica(self, budget_file):
        reader = BudgetReader()
        result = reader.read(budget_file)
        assert result is not None
        cab = result["cabecera"]
        assert "001" in cab.get("numero", "")
        assert cab.get("cliente", "") != ""

    def test_lee_fecha(self, budget_file):
        reader = BudgetReader()
        result = reader.read(budget_file)
        cab = result["cabecera"]
        assert cab.get("fecha") != ""

    def test_lee_direccion(self, budget_file):
        reader = BudgetReader()
        result = reader.read(budget_file)
        cab = result["cabecera"]
        assert "Mayor" in cab.get("direccion", "")

    def test_lee_codigo_postal(self, budget_file):
        reader = BudgetReader()
        result = reader.read(budget_file)
        cab = result["cabecera"]
        assert "30001" in cab.get("codigo_postal", "")

    def test_lee_cif_admin(self, budget_file):
        reader = BudgetReader()
        result = reader.read(budget_file)
        cab = result["cabecera"]
        assert "B12345678" in cab.get("cif_admin", "")

    def test_lee_email_admin(self, budget_file):
        reader = BudgetReader()
        result = reader.read(budget_file)
        cab = result["cabecera"]
        assert "admin@test.com" in cab.get("email_admin", "")


class TestBudgetReaderPartidas:
    """Lectura de partidas del presupuesto."""

    def test_sin_partidas(self, budget_file):
        reader = BudgetReader()
        result = reader.read(budget_file)
        assert result is not None
        # Puede haber partidas de ejemplo de la plantilla o estar vacío
        assert isinstance(result["partidas"], list)

    def test_con_partidas(self, budget_with_partidas):
        reader = BudgetReader()
        result = reader.read(budget_with_partidas)
        assert result is not None
        partidas = result["partidas"]
        assert len(partidas) >= 2
        p1 = partidas[0]
        assert "DESMONTAJE" in p1["concepto"].upper()
        assert p1["cantidad"] == 12
        assert p1["precio"] == 18.50

    def test_importe_calculado(self, budget_with_partidas):
        reader = BudgetReader()
        result = reader.read(budget_with_partidas)
        p1 = result["partidas"][0]
        assert p1["importe"] == round(12 * 18.50, 2)


class TestBudgetReaderTotals:
    """Cálculo de totales."""

    def test_totales_con_partidas(self, budget_with_partidas):
        reader = BudgetReader()
        result = reader.read(budget_with_partidas)
        expected_sub = round(12 * 18.50 + 12 * 25.00, 2)
        assert result["subtotal"] == expected_sub
        assert result["iva"] == round(expected_sub * 0.10, 2)
        assert result["total"] == round(expected_sub * 1.10, 2)

    def test_totales_sin_partidas(self, budget_file):
        reader = BudgetReader()
        result = reader.read(budget_file)
        assert result is not None
        assert isinstance(result["subtotal"], float)
        assert isinstance(result["total"], float)


class TestBudgetReaderErrors:
    """Manejo de errores."""

    def test_archivo_inexistente(self):
        reader = BudgetReader()
        assert reader.read("/no/existe.xlsx") is None

    def test_archivo_corrupto(self, tmp_path):
        corrupto = str(tmp_path / "corrupto.xlsx")
        with open(corrupto, "w") as f:
            f.write("esto no es un xlsx")
        reader = BudgetReader()
        assert reader.read(corrupto) is None

    def test_ruta_vacia(self):
        reader = BudgetReader()
        assert reader.read("") is None

    def test_ruta_none(self):
        reader = BudgetReader()
        assert reader.read(None) is None
