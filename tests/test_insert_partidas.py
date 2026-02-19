"""
Tests para insert_partidas_via_xml (fix del bug de celdas combinadas).

Cubren:
- Inserción de partidas en la hoja correcta (sheet2) via XML
- Columnas correctas (A=num, B=ud, C=desc, G=qty, H=price, I=formula)
- Estilos mantenidos
- Fórmulas de subtotal generadas correctamente
- Múltiples partidas y filas separadoras
"""

import os
import re
import shutil
import tempfile
import zipfile
import pytest

from src.core.excel_manager import ExcelManager
from src.core.template_manager import TemplateManager

SHEET_12220 = "xl/worksheets/sheet1.xml"


@pytest.fixture
def temp_dir():
    """Directorio temporal para pruebas."""
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def budget_file(temp_dir):
    """Crea un presupuesto desde la plantilla para tests."""
    tm = TemplateManager()
    em = ExcelManager()
    template = tm.get_template_path()
    if not os.path.exists(template):
        pytest.skip("Plantilla no disponible")
    output = os.path.join(temp_dir, "test_presupuesto.xlsx")
    data = {
        "numero_proyecto": "99",
        "fecha": "13-02-26",
        "cliente": "TEST CLIENT",
        "calle": "Calle Test",
        "codigo_postal": "03001",
        "tipo": "TEST OBRA",
    }
    em.create_from_template(template, output, data)
    return output


@pytest.fixture
def sample_partidas():
    """Lista de partidas de ejemplo."""
    return [
        {"concepto": "Desmontaje de bajante existente", "cantidad": 12, "unidad": "ml", "precio_unitario": 18.50},
        {"concepto": "Suministro e instalación bajante PVC 110mm", "cantidad": 12, "unidad": "ml", "precio_unitario": 32.00},
        {"concepto": "Codo PVC 45 grados", "cantidad": 4, "unidad": "ud", "precio_unitario": 12.50},
        {"concepto": "Reposición de alicatado", "cantidad": 3.5, "unidad": "m2", "precio_unitario": 45.00},
        {"concepto": "Transporte de escombros", "cantidad": 1, "unidad": "ud", "precio_unitario": 180.00},
    ]


def _read_sheet2(file_path):
    """Lee el XML de sheet2 de un xlsx."""
    with zipfile.ZipFile(file_path, "r") as z:
        return z.read(SHEET_12220).decode("utf-8")


class TestInsertPartidas:
    """Tests para la inserción de partidas via XML."""

    def test_insert_creates_valid_xlsx(self, budget_file, sample_partidas):
        """El archivo resultante es un xlsx válido tras insertar partidas."""
        em = ExcelManager()
        result = em.insert_partidas_via_xml(budget_file, sample_partidas)
        assert result is True
        # Verificar que se puede abrir como zip
        assert zipfile.is_zipfile(budget_file)

    def test_partidas_in_correct_sheet(self, budget_file, sample_partidas):
        """Las partidas se insertan en sheet1 (plantilla 122-20)."""
        em = ExcelManager()
        em.insert_partidas_via_xml(budget_file, sample_partidas)
        sheet = _read_sheet2(budget_file)
        assert "Desmontaje de bajante existente" in sheet
        assert "Codo PVC 45 grados" in sheet

    def test_correct_number_of_data_rows(self, budget_file, sample_partidas):
        """Se generan el número correcto de filas de datos (una por partida)."""
        em = ExcelManager()
        em.insert_partidas_via_xml(budget_file, sample_partidas)
        sheet2 = _read_sheet2(budget_file)
        # Cada partida genera una fila con número 1.X
        for i in range(len(sample_partidas)):
            assert f"1.{i + 1}" in sheet2, f"Falta numeración 1.{i + 1}"

    def test_correct_column_mapping(self, budget_file, sample_partidas):
        """Las columnas siguen el formato de la plantilla: A=num, B=ud, G=qty, H=price, I=formula."""
        em = ExcelManager()
        em.insert_partidas_via_xml(budget_file, sample_partidas)
        sheet2 = _read_sheet2(budget_file)

        # Fila 17 debe ser la primera partida
        # A17 = "1.1"
        assert re.search(r'<c r="A17"[^>]*>.*?1\.1.*?</c>', sheet2, re.DOTALL), "A17 debe contener 1.1"
        # B17 = "ml" (unidad de la primera partida)
        assert re.search(r'<c r="B17"[^>]*>.*?ml.*?</c>', sheet2, re.DOTALL), "B17 debe contener ml"
        # C17 = concepto
        assert re.search(r'<c r="C17"[^>]*>.*?Desmontaje.*?</c>', sheet2, re.DOTALL), "C17 debe contener el concepto"
        # G17 = cantidad (12)
        assert re.search(r'<c r="G17"[^>]*><v>12', sheet2), "G17 debe contener cantidad 12"
        # H17 = precio (18.5)
        assert re.search(r'<c r="H17"[^>]*><v>18\.5', sheet2), "H17 debe contener precio 18.5"
        # I17 = fórmula G17*H17
        assert re.search(r'<c r="I17"[^>]*>.*?<f>G17\*H17</f>', sheet2, re.DOTALL), "I17 debe tener fórmula G17*H17"

    def test_subtotal_formula_correct(self, budget_file, sample_partidas):
        """La fórmula de subtotal tiene el rango correcto."""
        em = ExcelManager()
        em.insert_partidas_via_xml(budget_file, sample_partidas)
        sheet2 = _read_sheet2(budget_file)

        # 5 partidas → filas 17,18(sep),19,20(sep),21,22(sep),23,24(sep),25,26(sep)
        # Subtotal en fila 27 con SUM(I17:I26)
        assert "SUM(I17:I26)" in sheet2, "Subtotal debe tener SUM(I17:I26)"

    def test_styles_preserved(self, budget_file, sample_partidas):
        """Los estilos de celda se mantienen según la plantilla 122-20."""
        em = ExcelManager()
        em.insert_partidas_via_xml(budget_file, sample_partidas)
        sheet = _read_sheet2(budget_file)

        # A17 debe tener estilo s="31" (número de partida)
        assert re.search(r'<c r="A17" s="31"', sheet), "A17 debe tener estilo s=31"
        # G17 debe tener estilo s="34" (cantidad)
        assert re.search(r'<c r="G17" s="34"', sheet), "G17 debe tener estilo s=34"
        # I17 debe tener estilo s="35" (total con fórmula)
        assert re.search(r'<c r="I17" s="35"', sheet), "I17 debe tener estilo s=35"

    def test_merge_cells_for_description(self, budget_file, sample_partidas):
        """Las celdas de descripción (C:F) están combinadas para cada fila de datos."""
        em = ExcelManager()
        em.insert_partidas_via_xml(budget_file, sample_partidas)
        sheet2 = _read_sheet2(budget_file)

        # Cada partida (fila impar empezando en 17) debe tener merge C:F
        row = 17
        for i in range(len(sample_partidas)):
            merge_ref = f'C{row}:F{row}'
            assert merge_ref in sheet2, f"Falta merge {merge_ref} para partida {i + 1}"
            row += 2  # Saltar separador

    def test_empty_partidas_does_nothing(self, budget_file):
        """Con lista vacía no modifica el archivo."""
        em = ExcelManager()
        original = _read_sheet2(budget_file)
        result = em.insert_partidas_via_xml(budget_file, [])
        assert result is True
        after = _read_sheet2(budget_file)
        assert original == after

    def test_header_data_preserved(self, budget_file, sample_partidas):
        """Los datos de cabecera (cliente, fecha, etc.) no se pierden."""
        em = ExcelManager()
        em.insert_partidas_via_xml(budget_file, sample_partidas)
        sheet2 = _read_sheet2(budget_file)
        assert "TEST CLIENT" in sheet2
        assert "Calle Test" in sheet2
