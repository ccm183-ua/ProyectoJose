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
from src.core.excel_partidas_writer import (
    PartidasWriter,
    SPACER_ROW_HEIGHT,
    _description_chars_per_line,
    _estimate_row_height_impl,
    _estimate_wrapped_lines,
    _shift_formula_row_refs_in_sheet_xml,
)
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

    def test_title_and_description_use_separate_runs_with_bold_only_on_title(self, budget_file):
        """Si hay título+descripción, el título va en negrita y la descripción en run normal."""
        em = ExcelManager()
        partidas = [
            {
                "titulo": "PINTURA PAREDES.",
                "descripcion": "Aplicación de pintura plástica mate en paredes.",
                "cantidad": 10,
                "unidad": "m2",
                "precio_unitario": 8.5,
            }
        ]
        em.insert_partidas_via_xml(budget_file, partidas)
        sheet2 = _read_sheet2(budget_file)

        # Primer run (título) con negrita
        assert re.search(r'<rPr><b/><sz val="10"/><rFont val="Calibri"/></rPr>\s*<t>PINTURA PAREDES\.</t>', sheet2)
        # Segundo run (descripción) sin negrita
        assert re.search(
            r'<r><rPr><sz val="10"/><rFont val="Calibri"/></rPr>\s*<t xml:space="preserve">&#10;Aplicación de pintura plástica mate en paredes\.</t></r>',
            sheet2,
        )

    def test_long_title_without_description_not_single_bold_block(self, budget_file):
        """Título largo sin descripción: no debe aplicarse negrita a todo un bloque enorme."""
        em = ExcelManager()
        long_t = "TITULO LARGO " * 25
        em.insert_partidas_via_xml(
            budget_file,
            [{"titulo": long_t, "descripcion": "", "unidad": "ud", "cantidad": 1, "precio_unitario": 1}],
        )
        sheet2 = _read_sheet2(budget_file)
        m = re.search(r'<c r="C17"[^>]*>(.*?)</c>', sheet2, re.DOTALL)
        assert m
        inner = m.group(1)
        bold_count = inner.count("<b/>")
        assert bold_count <= 1
        if bold_count == 1:
            assert inner.count("<r>") >= 2


class TestEstimateWrappedLines:
    def test_explicit_newlines_add_lines(self):
        cpl = 32
        one = _estimate_wrapped_lines("a" * 60 + "b" * 60, cpl)
        two = _estimate_wrapped_lines("a" * 60 + "\n\n" + "b" * 60, cpl)
        assert two > one

    def test_empty_paragraph_counts_as_one_line(self):
        assert _estimate_wrapped_lines("x\n\ny", 20) >= _estimate_wrapped_lines("x\ny", 20)


class TestFormulaRowRefShift:
    def test_shift_updates_row_refs_in_formulas_after_renumber(self):
        xml = '<sheetData><c r="I27"><f>SUMA(I46:I47)+I28</f></c></sheetData>'
        out = _shift_formula_row_refs_in_sheet_xml(xml, start_from=28, offset=-6)
        assert "I40:I41" in out
        assert "I22" in out
        assert "SUMA" in out
        assert "I46" not in out

    def test_shift_leaves_refs_above_start_from(self):
        xml = '<c r="X1"><f>SUM(I17:I26)</f></c>'
        out = _shift_formula_row_refs_in_sheet_xml(xml, start_from=28, offset=-6)
        assert "I17:I26" in out


class TestDescriptionCharsPerLine:
    def test_merge_and_col_widths_sum(self):
        xml = (
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<cols><col min="3" max="6" width="10.5" customWidth="1"/></cols>'
            '<mergeCell ref="C17:F17"/>'
            "</worksheet>"
        )
        v = _description_chars_per_line(xml)
        assert 38 <= v <= 78
        assert v == max(38, min(78, int(round(10.5 * 4))))

    def test_single_column_c_width_without_merge(self):
        xml = (
            '<cols><col min="3" max="3" width="29" customWidth="1"/></cols>'
            "<worksheet/>"
        )
        v = _description_chars_per_line(xml)
        assert v == 29

    def test_fallback_without_cols_or_merge(self):
        assert _description_chars_per_line("<worksheet/>") == 32


class TestEstimateRowHeight:
    """Alturas coherentes con chars_per_line fijo (p. ej. 32) para tests reproducibles."""

    def test_short_title_and_description_height_band(self):
        h = float(
            _estimate_row_height_impl(
                "ANDAMIO.",
                "Montaje y desmontaje de andamio tubular.",
                32,
            )
        )
        assert 35 <= h <= 55

    def test_medium_title_and_description_height_band(self):
        titulo = "REFUERZO EN ENCUENTROS."
        descripcion = (
            "Refuerzo de impermeabilización en encuentros con paramentos verticales, "
            "juntas de dilatación y puntos singulares mediante banda de refuerzo y mástico."
        )
        h = float(_estimate_row_height_impl(titulo, descripcion, 32))
        assert 65 <= h <= 95

    def test_long_text_height_band(self):
        titulo = "MONTAJE DE SISTEMAS DE ANCLAJE DEFINITIVOS."
        descripcion = "x" * 280
        h = float(_estimate_row_height_impl(titulo, descripcion, 32))
        assert 105 <= h <= 165

    def test_extreme_height_never_exceeds_long_cap(self):
        titulo = "T" * 80
        descripcion = "z" * 4000
        h = float(_estimate_row_height_impl(titulo, descripcion, 32))
        assert h <= 230

    def test_partidas_writer_delegates_same_result(self):
        a = float(
            PartidasWriter._estimate_row_height("ANDAMIO.", "Montaje tubular.", 32)
        )
        b = float(_estimate_row_height_impl("ANDAMIO.", "Montaje tubular.", 32))
        assert a == b


class TestPartidaSpacerRow:
    def test_spacer_row_after_partida_has_small_fixed_height(self, budget_file):
        em = ExcelManager()
        em.insert_partidas_via_xml(
            budget_file,
            [{"titulo": "P1.", "descripcion": "D1.", "cantidad": 1, "unidad": "ud", "precio_unitario": 1}],
        )
        sheet = _read_sheet2(budget_file)
        assert re.search(
            rf'<row r="18"[^>]*ht="{SPACER_ROW_HEIGHT}"[^>]*customHeight="1"',
            sheet,
        ), "La fila separadora debe tener altura explícita mínima"


# ---------------------------------------------------------------------------
# Regresión: reescritura de partidas sobre un Excel que ya tiene partidas,
# renumeración de filas con desplazamiento negativo y fórmulas del pie.
# ---------------------------------------------------------------------------

def _mk_partidas(n, tag, precio=100.0):
    return [
        {"concepto": f"{tag} partida {i}", "cantidad": 1, "unidad": "ud", "precio_unitario": precio}
        for i in range(n)
    ]


def _row_numbers(sheet):
    return [int(r) for r in re.findall(r'<row r="(\d+)"', sheet)]


def _formula_cells(sheet):
    """{celda: (formula, valor_cacheado)} de todas las celdas con fórmula."""
    out = {}
    for m in re.finditer(
        r'<c r="([A-Z]+\d+)"[^>]*><f[^>]*>([^<]*)</f>(?:<v>([^<]*)</v>)?', sheet
    ):
        out[m.group(1)] = (m.group(2), m.group(3))
    return out


def _footer_rows(budget_file):
    """Localiza las filas del pie por su etiqueta en la columna A (vía openpyxl)."""
    import openpyxl

    ws = openpyxl.load_workbook(budget_file).worksheets[0]
    rows = {}
    for row in ws.iter_rows(min_col=1, max_col=1):
        cell = row[0]
        text = str(cell.value or "").strip().upper()
        if not text:
            continue
        if text.startswith("1.- ACTUACIONES"):
            rows["capitulo"] = cell.row
        elif "INCLUIDO" in text and "TOTAL" in text:
            rows["total_iva"] = cell.row
        elif "I.V.A" in text:
            rows["iva"] = cell.row
        elif text.startswith("TOTAL PRESUPUESTO"):
            rows["total"] = cell.row
        elif text.startswith("ASCIENDE"):
            rows["asciende"] = cell.row
    return rows


@pytest.fixture
def no_page_config(monkeypatch):
    """Aísla la lógica XML de la inserción de cabeceras vía Excel COM."""
    monkeypatch.setattr(
        PartidasWriter, "_apply_page_config_after_write", staticmethod(lambda _p: None)
    )


@pytest.mark.usefixtures("no_page_config")
class TestRewritePartidas:
    @pytest.mark.parametrize("n", [1, 2, 4, 5, 6, 12])
    def test_row_numbers_unique_and_ascending(self, budget_file, n):
        em = ExcelManager()
        assert em.insert_partidas_via_xml(budget_file, _mk_partidas(n, "A"))
        rows = _row_numbers(_read_sheet2(budget_file))
        assert rows == sorted(set(rows)), "Filas duplicadas o desordenadas en el XML"

    @pytest.mark.parametrize("n", [1, 3, 5, 8])
    def test_footer_formulas_point_to_subtotal(self, budget_file, n):
        em = ExcelManager()
        assert em.insert_partidas_via_xml(budget_file, _mk_partidas(n, "A", precio=100.0))
        sheet = _read_sheet2(budget_file)
        subtotal_row = 17 + 2 * n
        f = _formula_cells(sheet)
        assert f[f"I{subtotal_row}"][0] == f"SUM(I17:I{subtotal_row - 1})"

        ft = _footer_rows(budget_file)
        cap, tot, iva, tiva = ft["capitulo"], ft["total"], ft["iva"], ft["total_iva"]
        assert f[f"I{cap}"][0] == f"I{subtotal_row}"
        assert f[f"I{tot}"][0] == f"SUM(I{cap}:I{tot - 1})"
        assert f[f"I{iva}"][0] in (f"I{tot}*10%", f"I{tot}*0.1")
        assert f[f"I{tiva}"][0] == f"I{tot}+I{iva}"

        esperado = 100.0 * n
        assert float(f[f"I{cap}"][1]) == pytest.approx(esperado)
        assert float(f[f"I{tot}"][1]) == pytest.approx(esperado)
        assert float(f[f"I{iva}"][1]) == pytest.approx(esperado * 0.1)
        assert float(f[f"I{tiva}"][1]) == pytest.approx(esperado * 1.1)

        # Ninguna fórmula del pie (aparte del capítulo) puede referenciar el subtotal:
        # evita dobles conteos y referencias circulares.
        refs_subtotal = [c for c, (fx, _) in f.items() if fx == f"I{subtotal_row}"]
        assert refs_subtotal == [f"I{cap}"]
        assert not any(fx == c for c, (fx, _) in f.items()), "Referencia circular"

    @pytest.mark.parametrize("primera,segunda", [(10, 2), (2, 10), (1, 1), (3, 7), (7, 3)])
    def test_replace_existing_partidas_leaves_no_leftovers(self, budget_file, primera, segunda):
        em = ExcelManager()
        assert em.insert_partidas_via_xml(budget_file, _mk_partidas(primera, "VIEJA"))
        assert em.insert_partidas_via_xml(budget_file, _mk_partidas(segunda, "NUEVA", precio=50.0))
        sheet = _read_sheet2(budget_file)

        assert "VIEJA" not in sheet
        assert sheet.count("NUEVA partida") == segunda
        rows = _row_numbers(sheet)
        assert rows == sorted(set(rows))
        subtotales = re.findall(r"<f>SUM\(I17:I\d+\)</f>", sheet)
        assert subtotales == [f"<f>SUM(I17:I{16 + 2 * segunda})</f>"]

        ft = _footer_rows(budget_file)
        f = _formula_cells(sheet)
        assert float(f[f"I{ft['total_iva']}"][1]) == pytest.approx(50.0 * segunda * 1.1)
        assert "IVA INCLUIDO" in sheet

    def test_replace_matches_fresh_insert(self, temp_dir, budget_file):
        """Reescribir sobre un Excel con partidas da el mismo XML que escribir sobre la plantilla."""
        em = ExcelManager()
        fresh = os.path.join(temp_dir, "fresh.xlsx")
        shutil.copy(budget_file, fresh)
        assert em.insert_partidas_via_xml(fresh, _mk_partidas(3, "N"))

        assert em.insert_partidas_via_xml(budget_file, _mk_partidas(9, "X"))
        assert em.insert_partidas_via_xml(budget_file, _mk_partidas(3, "N"))
        assert _read_sheet2(budget_file) == _read_sheet2(fresh)

    def test_append_keeps_existing_and_adds_new(self, budget_file):
        em = ExcelManager()
        assert em.insert_partidas_via_xml(budget_file, _mk_partidas(3, "PRIMERA"))
        assert em.append_partidas_via_xml(budget_file, _mk_partidas(2, "SEGUNDA"))
        sheet = _read_sheet2(budget_file)
        assert sheet.count("PRIMERA partida") == 3
        assert sheet.count("SEGUNDA partida") == 2
        assert re.findall(r"<f>SUM\(I17:I\d+\)</f>", sheet) == ["<f>SUM(I17:I26)</f>"]

    def test_result_opens_with_openpyxl(self, budget_file):
        import openpyxl

        em = ExcelManager()
        assert em.insert_partidas_via_xml(budget_file, _mk_partidas(8, "A"))
        assert em.insert_partidas_via_xml(budget_file, _mk_partidas(2, "B"))
        openpyxl.load_workbook(budget_file)
