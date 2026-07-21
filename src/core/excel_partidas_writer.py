"""
Inserción de partidas en presupuestos Excel mediante manipulación XML directa.
Incluye actualización de cabeceras y texto "Asciende el presupuesto...".
"""

import logging
import math
import os
import re
import shutil
import tempfile
import zipfile
from xml.sax.saxutils import escape as xml_escape

from src.core.budget_math import IVA_RATE, calcular_importe_linea, calcular_totales
from src.core.excel_template_filler import (
    SHEET_12220,
    euros_en_letras,
    replace_cell_in_sheet_xml,
)
from src.core.xlsx_cell_utils import (
    read_shared_strings_from_dict,
    resolve_cell_text,
)
from src.core.partida_normalizer import (
    force_split_long_plain_text,
    split_title_description,
    split_title_for_excel_bold,
)

logger = logging.getLogger(__name__)

# --- Altura de fila de partida (descripción en hoja 122-20, merge C:F o solo C) ---
DESC_DEFAULT_CHARS_PER_LINE_SINGLE_COL = 32
DESC_DEFAULT_CHARS_PER_LINE_MERGED = 46
# La suma OOXML de anchos C–F suele subestimar el ancho útil real al ajustar texto;
# un suelo evita contar demasiadas líneas y filas en blanco enormes.
MERGED_CHARS_PER_LINE_FLOOR = 38
MERGED_CHARS_PER_LINE_CAP = 78
EXCEL_LINE_HEIGHT = 13.2
EXCEL_ROW_PADDING = 6
EXCEL_ROW_MIN_SHORT = 34
EXCEL_ROW_MIN_MEDIUM = 42
EXCEL_ROW_MIN_LONG = 56
EXCEL_ROW_MAX_NORMAL = 150
# Por encima de esto no recortar texto (casos muy densos en descripción).
EXCEL_ROW_MAX_LONG = 230
SPACER_ROW_HEIGHT = 8
TITLE_DESC_VISUAL_GAP_LINES = 0.18

_A1_CELL_REF = re.compile(
    r"^(?P<ca>\$?)(?P<col>[A-Za-z]{1,3})(?P<ra>\$?)(?P<row>\d+)$",
)


def _shift_single_a1_cell(ref: str, start_from: int, offset: int) -> str:
    """Desplaza la fila en una referencia A1 si la fila es >= start_from. Conserva $ de columna/fila."""
    if offset == 0:
        return ref
    m = _A1_CELL_REF.match(ref.strip())
    if not m:
        return ref
    row = int(m.group("row"))
    if row < start_from:
        return ref
    new_row = row + offset
    col = m.group("col").upper()
    return f"{m.group('ca')}{col}{m.group('ra')}{new_row}"


def _shift_operand_range(range_text: str, start_from: int, offset: int) -> str:
    if ":" in range_text:
        left, right = range_text.split(":", 1)
        return _shift_single_a1_cell(left, start_from, offset) + ":" + _shift_single_a1_cell(
            right, start_from, offset
        )
    return _shift_single_a1_cell(range_text, start_from, offset)


def _shift_formula_row_refs_in_content(formula: str, start_from: int, offset: int) -> str:
    """
    Ajusta filas en referencias A1 dentro de una fórmula (p. ej. SUMA(I46:I47)).
    El XML a veces guarda la fórmula sin '='; se antepone '=' solo para tokenizar.
    """
    if offset == 0 or not formula or not str(formula).strip():
        return formula
    raw = str(formula).strip()
    parse_src = raw if raw.startswith("=") else "=" + raw
    try:
        from openpyxl.formula.tokenizer import Tokenizer
    except ImportError:
        return raw
    try:
        tokens = list(Tokenizer(parse_src).items)
    except Exception:
        return raw
    if len(tokens) == 1 and getattr(tokens[0], "type", "") == "LITERAL":
        return raw
    out: list[str] = []
    for tok in tokens:
        if getattr(tok, "type", "") == "OPERAND" and getattr(tok, "subtype", "") == "RANGE":
            out.append(_shift_operand_range(tok.value, start_from, offset))
        else:
            out.append(tok.value)
    return "".join(out)


def _shift_formula_row_refs_in_sheet_xml(sheet_xml: str, start_from: int, offset: int) -> str:
    """Tras _renumber_rows, corrige filas en <f>...</f> para que coincidan con el nuevo índice."""

    def _bump_f(match: re.Match) -> str:
        attrs, inner = match.group(1), match.group(2)
        new_inner = _shift_formula_row_refs_in_content(inner, start_from, offset)
        return f"<f{attrs}>{new_inner}</f>"

    if offset == 0:
        return sheet_xml
    return re.sub(r"<f([^>]*)>([^<]*)</f>", _bump_f, sheet_xml)


def _sheet_has_merge_c_to_f(sheet_xml: str) -> bool:
    """True si la hoja declara alguna combinación C*:F* (descripción ancha)."""
    return bool(re.search(r'<mergeCell ref="C\d+:F\d+"', sheet_xml, re.IGNORECASE))


def _column_width_map_from_sheet(sheet_xml: str) -> dict[int, float]:
    """
    Lee anchos OOXML de <cols> por índice de columna (1=A).
    Si un <col> abarca varias columnas, asigna el mismo width a cada una (comportamiento Excel).
    """
    out: dict[int, float] = {}
    cols_m = re.search(r"<cols[^>]*>(.*?)</cols>", sheet_xml, re.DOTALL | re.IGNORECASE)
    if not cols_m:
        return out
    for tag in re.finditer(r"<col\b([^/>]*)/>", cols_m.group(1), re.IGNORECASE):
        attrs = tag.group(1)

        def _attr(name: str) -> str | None:
            mm = re.search(rf'{name}="([^"]*)"', attrs, re.IGNORECASE)
            return mm.group(1) if mm else None

        w_s = _attr("width")
        if not w_s:
            continue
        try:
            w = float(w_s)
        except ValueError:
            continue
        mn_s, mx_s = _attr("min"), _attr("max")
        if not mn_s:
            continue
        try:
            cmin = int(mn_s)
            cmax = int(mx_s) if mx_s else cmin
        except ValueError:
            continue
        for ci in range(cmin, cmax + 1):
            out[ci] = w
    return out


def _sum_widths_cf(column_widths: dict[int, float]) -> float:
    return float(sum(column_widths.get(i, 0.0) for i in (3, 4, 5, 6)))


def _description_chars_per_line(sheet_xml: str, default: int | None = None) -> int:
    """
    Caracteres efectivos por línea para el área de descripción, según merge C:F y <cols>.

    Si hay merge C:F y suma de anchos C–F > 0, usa esa suma (acotada por seguridad).
    Si hay merge pero sin anchos, usa DESC_DEFAULT_CHARS_PER_LINE_MERGED.
    Sin merge: ancho solo columna C si consta; si no, DESC_DEFAULT_CHARS_PER_LINE_SINGLE_COL.
    """
    d = default if default is not None else DESC_DEFAULT_CHARS_PER_LINE_SINGLE_COL
    merged = _sheet_has_merge_c_to_f(sheet_xml)
    cmap = _column_width_map_from_sheet(sheet_xml)
    if merged:
        s = _sum_widths_cf(cmap)
        if s > 0:
            est = int(round(s))
            return max(MERGED_CHARS_PER_LINE_FLOOR, min(MERGED_CHARS_PER_LINE_CAP, est))
        return DESC_DEFAULT_CHARS_PER_LINE_MERGED
    w3 = cmap.get(3, 0.0)
    if w3 > 0:
        return max(18, min(44, int(w3)))
    return d


def _estimate_wrapped_lines(text: str, chars_per_line: int) -> float:
    """
    Líneas visuales estimadas respetando saltos explícitos y reparto por longitud.
    Párrafo vacío cuenta como 1 línea.
    """
    if chars_per_line < 1:
        chars_per_line = 1
    raw = str(text or "")
    if raw == "":
        return 0.0
    total = 0.0
    for paragraph in raw.splitlines():
        if paragraph == "":
            total += 1.0
        else:
            total += max(1.0, float(math.ceil(len(paragraph) / chars_per_line)))
    return total


def _estimate_row_height_impl(titulo: str, descripcion: str, chars_per_line: int) -> str:
    """
    Altura de fila en puntos Excel: prioridad no cortar texto (hasta EXCEL_ROW_MAX_LONG).
    """
    tit = str(titulo or "").strip()
    desc = str(descripcion or "").strip()
    title_lines = _estimate_wrapped_lines(tit, chars_per_line)
    desc_lines = _estimate_wrapped_lines(desc, chars_per_line)
    if not tit and not desc:
        total_lines = 1.0
    else:
        total_lines = title_lines + desc_lines
        if tit and desc:
            total_lines += TITLE_DESC_VISUAL_GAP_LINES

    raw_height = total_lines * EXCEL_LINE_HEIGHT + EXCEL_ROW_PADDING

    min_height = EXCEL_ROW_MIN_SHORT
    if total_lines >= 4:
        min_height = EXCEL_ROW_MIN_MEDIUM
    if total_lines >= 7:
        min_height = EXCEL_ROW_MIN_LONG

    # Prioridad: no recortar texto. Solo acotar filas muy vacías si raw queda por encima del techo "normal".
    soft_cap = (
        EXCEL_ROW_MAX_LONG
        if (total_lines > 10 or raw_height > EXCEL_ROW_MAX_NORMAL)
        else EXCEL_ROW_MAX_NORMAL
    )
    if raw_height <= soft_cap:
        height = max(min_height, raw_height)
    else:
        height = max(min_height, min(EXCEL_ROW_MAX_LONG, raw_height))
    return str(round(height, 1))


class PartidasWriter:
    """Inserta y actualiza partidas en archivos Excel 122-20 vía XML."""

    def insert_partidas_via_xml(self, file_path, partidas):
        """
        Inserta partidas en el Excel usando manipulación XML directa en sheet2.

        Reemplaza las partidas de ejemplo de la plantilla (filas 17-26) con las
        partidas proporcionadas, manteniendo estilos y formato del template.

        Estructura de columnas en la plantilla:
            A = Número (1.1, 1.2...)
            B = Unidad (m2, ud, ml...)
            C-F = Descripción (celdas C:F combinadas)
            G = Cantidad
            H = Precio unitario
            I = Total (fórmula =G*H)

        Args:
            file_path: Ruta del archivo Excel ya creado desde plantilla.
            partidas: Lista de dicts con concepto, cantidad, unidad, precio_unitario.

        Returns:
            bool: True si se insertaron correctamente.
        """
        if not partidas:
            return True  # Nada que insertar

        try:
            with zipfile.ZipFile(file_path, "r") as z_in:
                namelist = z_in.namelist()
                sheet_content = z_in.read(SHEET_12220).decode("utf-8")
                otros = {n: z_in.read(n) for n in namelist if n != SHEET_12220}

            wrap_style = self._create_wrap_style(otros, 47)
            partida_desc_style = self._create_wrap_style(otros, 32, vertical_top=True)
            sheet_content = self._replace_partidas_in_xml(
                sheet_content,
                partidas,
                asciende_style=wrap_style,
                partida_desc_style=partida_desc_style,
            )

            fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
            try:
                os.close(fd)
                with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as z_out:
                    for name in namelist:
                        if name == SHEET_12220:
                            z_out.writestr(name, sheet_content.encode("utf-8"))
                        elif name == "xl/workbook.xml":
                            wb_xml = otros[name].decode("utf-8")
                            wb_xml = re.sub(
                                r'<calcPr [^/]*/>',
                                '<calcPr calcId="144525" fullCalcOnLoad="1"/>',
                                wb_xml,
                            )
                            z_out.writestr(name, wb_xml.encode("utf-8"))
                        else:
                            z_out.writestr(name, otros[name])
                shutil.move(tmp_path, file_path)
            except Exception:
                if os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                raise

            self._apply_page_config_after_write(file_path)
            return True

        except Exception as e:
            logger.exception("Error al insertar partidas")
            return False

    @staticmethod
    def _estimate_row_height(titulo, descripcion, chars_per_line: int) -> str:
        """Delega en `_estimate_row_height_impl`; `chars_per_line` viene del XML de la hoja."""
        return _estimate_row_height_impl(titulo, descripcion, chars_per_line)

    def _replace_partidas_in_xml(
        self,
        sheet_xml,
        partidas,
        asciende_style="47",
        partida_desc_style="32",
    ):
        """
        Reemplaza las filas de partidas de ejemplo (17-26) con las partidas reales.
        """
        for row_num in range(17, 27):
            pattern = r'<row r="' + str(row_num) + r'"[^>]*>.*?</row>'
            sheet_xml = re.sub(pattern, '', sheet_xml, flags=re.DOTALL)

        new_rows_xml = []
        first_data_row = 17
        current_row = first_data_row
        ps = str(partida_desc_style)
        chars_per_line = _description_chars_per_line(sheet_xml)

        for idx, partida in enumerate(partidas):
            num = f"1.{idx + 1}"
            unidad = xml_escape(str(partida.get('unidad', 'ud')))
            cantidad = partida.get('cantidad', 1)
            precio = partida.get('precio_unitario', 0)
            try:
                cantidad = float(cantidad)
            except (ValueError, TypeError):
                cantidad = 1.0
            try:
                precio = float(precio)
            except (ValueError, TypeError):
                precio = 0.0

            titulo_plain = str(partida.get("titulo", "") or "").strip()
            descripcion_plain = str(partida.get("descripcion", "") or "").strip()

            if not descripcion_plain and len(titulo_plain) > 120:
                titulo_plain, descripcion_plain = split_title_description(titulo_plain)
            if not descripcion_plain and len(titulo_plain) > 120:
                titulo_plain, descripcion_plain = force_split_long_plain_text(titulo_plain, 85)

            bold_head, tail_title = split_title_for_excel_bold(titulo_plain, 72)
            if tail_title:
                titulo_plain = bold_head
                if descripcion_plain:
                    descripcion_plain = f"{tail_title}\n{descripcion_plain}".strip()
                else:
                    descripcion_plain = tail_title

            titulo_esc = xml_escape(titulo_plain)
            descripcion_esc = xml_escape(descripcion_plain)

            if titulo_esc and descripcion_esc:
                celda_c = (
                    f'<c r="C{current_row}" s="{ps}" t="inlineStr"><is>'
                    f'<r><rPr><b/><sz val="10"/><rFont val="Calibri"/></rPr>'
                    f'<t>{titulo_esc}</t></r>'
                    f'<r><rPr><sz val="10"/><rFont val="Calibri"/></rPr>'
                    f'<t xml:space="preserve">&#10;{descripcion_esc}</t></r>'
                    f'</is></c>'
                )
                row_height = self._estimate_row_height(
                    titulo_plain, descripcion_plain, chars_per_line
                )
            elif titulo_esc and len(titulo_plain) > 80 and not descripcion_plain:
                celda_c = (
                    f'<c r="C{current_row}" s="{ps}" t="inlineStr"><is>'
                    f'<r><rPr><sz val="10"/><rFont val="Calibri"/></rPr>'
                    f'<t>{titulo_esc}</t></r>'
                    f'</is></c>'
                )
                row_height = self._estimate_row_height(titulo_plain, "", chars_per_line)
            elif titulo_esc:
                celda_c = (
                    f'<c r="C{current_row}" s="{ps}" t="inlineStr"><is>'
                    f'<r><rPr><b/><sz val="10"/><rFont val="Calibri"/></rPr>'
                    f'<t>{titulo_esc}</t></r>'
                    f'</is></c>'
                )
                row_height = self._estimate_row_height(titulo_plain, "", chars_per_line)
            else:
                concepto = xml_escape(str(partida.get('concepto', '')))
                celda_c = (
                    f'<c r="C{current_row}" s="{ps}" t="inlineStr">'
                    f'<is><t>{concepto}</t></is></c>'
                )
                row_height = self._estimate_row_height(
                    str(partida.get("concepto", "")), "", chars_per_line
                )

            total = calcular_importe_linea(cantidad, precio)
            data_row = (
                f'<row r="{current_row}" spans="1:9" ht="{row_height}" customHeight="1">'
                f'<c r="A{current_row}" s="31" t="inlineStr"><is><t>{num}</t></is></c>'
                f'<c r="B{current_row}" s="31" t="inlineStr"><is><t>{unidad}</t></is></c>'
                f'{celda_c}'
                f'<c r="D{current_row}" s="{ps}"/>'
                f'<c r="E{current_row}" s="{ps}"/>'
                f'<c r="F{current_row}" s="33"/>'
                f'<c r="G{current_row}" s="34"><v>{cantidad}</v></c>'
                f'<c r="H{current_row}" s="35"><v>{precio}</v></c>'
                f'<c r="I{current_row}" s="35"><f>G{current_row}*H{current_row}</f><v>{total}</v></c>'
                f'</row>'
            )
            new_rows_xml.append(data_row)
            current_row += 1

            spacer_row = (
                f'<row r="{current_row}" spans="1:9" ht="{SPACER_ROW_HEIGHT}" customHeight="1">'
                f'<c r="A{current_row}" s="31"/>'
                f'<c r="B{current_row}" s="31"/>'
                f'<c r="C{current_row}" s="36"/>'
                f'<c r="D{current_row}" s="32"/>'
                f'<c r="E{current_row}" s="32"/>'
                f'<c r="F{current_row}" s="33"/>'
                f'<c r="G{current_row}" s="34"/>'
                f'<c r="H{current_row}" s="35"/>'
                f'<c r="I{current_row}" s="35"/>'
                f'</row>'
            )
            new_rows_xml.append(spacer_row)
            current_row += 1

        last_data_row = current_row - 1
        subtotal_row_num = current_row
        subtotal_label = xml_escape("Total presupuesto parcial nº 1 ACTUACIONES.")
        grand_total = round(sum(
            calcular_importe_linea(p.get('cantidad', 1), p.get('precio_unitario', 0))
            for p in partidas
        ), 2)
        subtotal_row = (
            f'<row r="{subtotal_row_num}" spans="1:9" customHeight="1">'
            f'<c r="A{subtotal_row_num}" s="39"/>'
            f'<c r="B{subtotal_row_num}" s="40"/>'
            f'<c r="C{subtotal_row_num}" s="41" t="inlineStr"><is><t>{subtotal_label}</t></is></c>'
            f'<c r="D{subtotal_row_num}" s="42"/>'
            f'<c r="E{subtotal_row_num}" s="42"/>'
            f'<c r="F{subtotal_row_num}" s="42"/>'
            f'<c r="G{subtotal_row_num}" s="42"/>'
            f'<c r="H{subtotal_row_num}" s="43"/>'
            f'<c r="I{subtotal_row_num}" s="54">'
            f'<f>SUM(I{first_data_row}:I{last_data_row})</f>'
            f'<v>{grand_total}</v></c>'
            f'</row>'
        )
        new_rows_xml.append(subtotal_row)

        pattern_27 = r'<row r="27"[^>]*>.*?</row>'
        sheet_xml = re.sub(pattern_27, '', sheet_xml, flags=re.DOTALL)
        offset = subtotal_row_num - 27

        if offset != 0:
            sheet_xml = self._renumber_rows(sheet_xml, start_from=28, offset=offset)
            sheet_xml = _shift_formula_row_refs_in_sheet_xml(sheet_xml, start_from=28, offset=offset)

        for row_num in range(17, 28):
            sheet_xml = re.sub(
                r'<mergeCell ref="[A-Z]+' + str(row_num) + r':[A-Z]+' + str(row_num) + r'"/>',
                '', sheet_xml
            )
        new_merges = []
        row = first_data_row
        for idx in range(len(partidas)):
            new_merges.append(f'<mergeCell ref="C{row}:F{row}"/>')
            row += 2
        new_merges.append(f'<mergeCell ref="C{subtotal_row_num}:G{subtotal_row_num}"/>')
        if offset != 0:
            sheet_xml = self._renumber_merges(sheet_xml, start_from=28, offset=offset)
        merge_insert = ''.join(new_merges)
        sheet_xml = sheet_xml.replace('</mergeCells>', merge_insert + '</mergeCells>')

        r43 = 43 + offset
        r45 = 45 + offset
        r46 = 46 + offset
        r47 = 47 + offset
        r49 = 49 + offset
        total_sin_iva = grand_total
        totales = calcular_totales([total_sin_iva])
        iva_amount = totales["iva"]
        total_con_iva = totales["total"]

        sheet_xml = self._update_formula_ref(
            sheet_xml, r43, 'I', f'I{subtotal_row_num}', total_sin_iva)
        sheet_xml = self._update_formula_ref(
            sheet_xml, r45, 'I', f'SUM(I{r43}:I{r43 + 1})', total_sin_iva)
        sheet_xml = self._update_formula_ref(
            sheet_xml, r46, 'I', f'I{r45}*0.1', iva_amount)
        sheet_xml = self._update_formula_ref(
            sheet_xml, r47, 'I', f'I{r45}+I{r46}', total_con_iva)

        texto_importe = (
            "Asciende el presupuesto de ejecución material a la expresada "
            f"cantidad de {euros_en_letras(total_con_iva)} IVA INCLUIDO."
        )
        sheet_xml = self._replace_cell_text(
            sheet_xml, f'A{r49}', texto_importe,
            style=asciende_style, bold=True, font_size=11,
        )

        next_original_row = 28 + offset
        insert_point_pattern = r'(<row r="' + str(next_original_row) + r'")'
        insert_point = re.search(insert_point_pattern, sheet_xml)
        all_new_rows = '\n'.join(new_rows_xml)
        if insert_point:
            sheet_xml = sheet_xml[:insert_point.start()] + all_new_rows + '\n' + sheet_xml[insert_point.start():]
        else:
            sheet_xml = sheet_xml.replace('</sheetData>', all_new_rows + '\n</sheetData>')

        last_row = 57 + offset
        sheet_xml = re.sub(
            r'<dimension ref="[^"]+"/>',
            f'<dimension ref="A1:R{last_row}"/>',
            sheet_xml
        )
        return sheet_xml

    def _renumber_rows(self, sheet_xml, start_from, offset):
        """Renumera filas y sus referencias de celda desde start_from aplicando offset."""
        if offset == 0:
            return sheet_xml
        rows_found = re.findall(r'<row r="(\d+)"', sheet_xml)
        rows_to_renumber = sorted(
            [int(r) for r in rows_found if int(r) >= start_from],
            reverse=True
        )
        for old_row in rows_to_renumber:
            new_row = old_row + offset
            sheet_xml = sheet_xml.replace(
                f'<row r="{old_row}"',
                f'<row r="{new_row}"'
            )
            for col in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L',
                        'M', 'N', 'O', 'P', 'Q', 'R']:
                sheet_xml = sheet_xml.replace(
                    f'r="{col}{old_row}"',
                    f'r="{col}{new_row}"'
                )
        return sheet_xml

    def _renumber_merges(self, sheet_xml, start_from, offset):
        """Renumera mergeCell refs que involucran filas >= start_from."""
        if offset == 0:
            return sheet_xml

        def _replace_merge(match):
            ref = match.group(1)
            parts = ref.split(':')
            if len(parts) != 2:
                return match.group(0)
            start_ref, end_ref = parts
            start_col = re.match(r'([A-Z]+)', start_ref).group(1)
            start_row = int(re.search(r'(\d+)', start_ref).group(1))
            end_col = re.match(r'([A-Z]+)', end_ref).group(1)
            end_row = int(re.search(r'(\d+)', end_ref).group(1))
            if start_row >= start_from:
                start_row += offset
                end_row += offset
                return f'<mergeCell ref="{start_col}{start_row}:{end_col}{end_row}"/>'
            return match.group(0)

        sheet_xml = re.sub(r'<mergeCell ref="([^"]+)"/>', _replace_merge, sheet_xml)
        return sheet_xml

    def _update_formula_ref(self, sheet_xml, row, col, new_formula, cached_value=None):
        """Actualiza la fórmula (y valor cacheado) de una celda específica."""
        pattern = (
            r'(<c r="' + col + str(row) + r'"[^>]*>)'
            r'(?:<f[^>]*>[^<]*</f>)?'
            r'(?:<v>[^<]*</v>)?'
        )
        match = re.search(pattern, sheet_xml)
        if match:
            v_part = ''
            if cached_value is not None:
                v_part = f'<v>{cached_value}</v>'
            replacement = match.group(1) + f'<f>{new_formula}</f>' + v_part
            sheet_xml = sheet_xml[:match.start()] + replacement + sheet_xml[match.end():]
        return sheet_xml

    def _replace_cell_text(self, sheet_xml, ref, text, style=None,
                           bold=False, font_size=10):
        """Reemplaza el contenido de texto de una celda (inline string)."""
        escaped = xml_escape(str(text))
        pattern = r'<c r="' + re.escape(ref) + r'"[^>]*?>(?:.*?</c>|/>)'
        match = re.search(pattern, sheet_xml, re.DOTALL)
        if match:
            s_attr = f' s="{style}"' if style else ''
            if bold:
                inner = (
                    f'<r><rPr><b/><sz val="{font_size}"/><rFont val="Calibri"/>'
                    '<family val="2"/></rPr>'
                    f'<t xml:space="preserve">{escaped}</t></r>'
                )
            else:
                inner = f'<t>{escaped}</t>'
            new_cell = (
                f'<c r="{ref}"{s_attr} t="inlineStr">'
                f'<is>{inner}</is></c>'
            )
            sheet_xml = sheet_xml[:match.start()] + new_cell + sheet_xml[match.end():]
        return sheet_xml

    def update_header_fields(self, file_path, data):
        """
        Actualiza los campos de cabecera de un presupuesto existente,
        incluyendo el texto "Asciende el presupuesto..." y el nombre
        del cliente al final del documento.
        """
        try:
            fecha_raw = data.get("fecha", "")
            fecha = ""
            if fecha_raw:
                parts = str(fecha_raw).strip().split("-")
                if len(parts) == 3:
                    fecha = f"{parts[0]}/{parts[1]}/{parts[2]}"

            numero_pres = (data.get("numero_proyecto", "") or "").strip()
            year_suffix = ""
            try:
                fecha_parts = str(fecha_raw).strip().split("-")
                if len(fecha_parts) == 3:
                    year_suffix = fecha_parts[2]
            except Exception:
                logger.debug("No se pudo extraer año de la fecha: %s", fecha_raw)
            if numero_pres and year_suffix:
                numero_pres = f"{numero_pres}/{year_suffix}"

            calle = (data.get("calle", "") or "").strip()
            num_calle = (data.get("num_calle", "") or "").strip()
            direccion = f"{calle} N\u00ba {num_calle}" if calle and num_calle else calle

            obra_final = ""
            tipo = (data.get("tipo", "") or "").strip()
            if tipo:
                obra_final = f"Obra: {tipo}."

            cliente = (data.get("cliente", "") or "").strip()

            celdas = {
                "E5": numero_pres,
                "H5": fecha or "",
                "B7": cliente,
                "H7": (data.get("admin_cif", "") or "").strip(),
                "B9": direccion,
                "H9": str(data.get("codigo_postal", "") or "").strip(),
                "B11": (data.get("admin_email", "") or "").strip(),
                "H11": (data.get("admin_telefono", "") or "").strip(),
                "A14": obra_final,
            }

            with zipfile.ZipFile(file_path, "r") as z_in:
                namelist = z_in.namelist()
                sheet_content = z_in.read(SHEET_12220).decode("utf-8")
                otros = {n: z_in.read(n) for n in namelist if n != SHEET_12220}

            for ref, valor in celdas.items():
                if valor:
                    sheet_content = replace_cell_in_sheet_xml(sheet_content, ref, valor)

            shared_strings = read_shared_strings_from_dict(otros)
            wrap_style = self._create_wrap_style(otros, 47)
            sheet_content = self._update_asciende_text(
                sheet_content, file_path, shared_strings,
                wrap_style=wrap_style,
            )
            if cliente:
                sheet_content = self._update_bottom_client_cell(
                    sheet_content, cliente, shared_strings,
                )

            fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
            try:
                os.close(fd)
                with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as z_out:
                    for name in namelist:
                        if name == SHEET_12220:
                            z_out.writestr(name, sheet_content.encode("utf-8"))
                        else:
                            z_out.writestr(name, otros[name])
                shutil.move(tmp_path, file_path)
            except Exception:
                if os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                raise

            self._apply_page_config_after_write(file_path)
            return True
        except Exception as e:
            logger.exception("Error al actualizar campos")
            return False

    @staticmethod
    def _create_wrap_style(otros_dict, base_style_idx=47, vertical_top=False):
        """Crea un nuevo estilo en styles.xml con wrapText y horizontal left (opcional vertical arriba)."""
        styles_key = "xl/styles.xml"
        if styles_key not in otros_dict:
            return str(base_style_idx)
        styles_xml = otros_dict[styles_key].decode("utf-8")
        cellxfs_match = re.search(
            r'(<cellXfs\s+count=")(\d+)(")(.*?)(</cellXfs>)',
            styles_xml, re.DOTALL,
        )
        if not cellxfs_match:
            return str(base_style_idx)
        count = int(cellxfs_match.group(2))
        content = cellxfs_match.group(4)
        xfs = list(re.finditer(
            r'<xf\b[^>]*?(?:/>|>.*?</xf>)', content, re.DOTALL,
        ))
        if base_style_idx >= len(xfs):
            return str(base_style_idx)
        base_xf = xfs[base_style_idx].group(0)
        has_top = 'vertical="top"' in base_xf
        if (
            'wrapText="1"' in base_xf
            and 'horizontal="left"' in base_xf
            and (not vertical_top or has_top)
        ):
            return str(base_style_idx)
        v_attr = ' vertical="top"' if vertical_top else ""
        _align = f'<alignment horizontal="left" wrapText="1"{v_attr}/>'
        new_xf = base_xf
        if '<alignment' in new_xf:
            new_xf = re.sub(
                r'<alignment[^/]*/>', _align, new_xf, count=1,
            )
        elif new_xf.endswith('/>'):
            new_xf = (
                new_xf[:-2]
                + ' applyAlignment="1">'
                + _align + '</xf>'
            )
        else:
            new_xf = new_xf.replace(
                '</xf>', _align + '</xf>', 1,
            )
            if 'applyAlignment' not in new_xf:
                new_xf = re.sub(
                    r'<xf\b', '<xf applyAlignment="1"', new_xf, count=1,
                )
        new_idx = count
        new_content = content + new_xf + '\n'
        new_section = (
            cellxfs_match.group(1)
            + str(new_idx + 1)
            + cellxfs_match.group(3)
            + new_content
            + cellxfs_match.group(5)
        )
        styles_xml = (
            styles_xml[:cellxfs_match.start()]
            + new_section
            + styles_xml[cellxfs_match.end():]
        )
        otros_dict[styles_key] = styles_xml.encode("utf-8")
        return str(new_idx)

    def _find_cell_by_text(self, sheet_xml, shared_strings, col, search_text,
                           min_row=0):
        """Busca en columna `col` la primera celda cuyo texto contenga `search_text`."""
        for m in re.finditer(
            r'<c r="' + col + r'(\d+)"[^>]*?(?:/>|>.*?</c>)',
            sheet_xml, re.DOTALL,
        ):
            row = int(m.group(1))
            if row < min_row:
                continue
            text = resolve_cell_text(m.group(0), shared_strings)
            if search_text.lower() in text.lower():
                return row
        return None

    def _update_asciende_text(self, sheet_xml, file_path, shared_strings,
                              wrap_style="47"):
        """Busca la celda 'Asciende el presupuesto...' y la actualiza con el total actual."""
        row = self._find_cell_by_text(
            sheet_xml, shared_strings, "A", "Asciende", min_row=30,
        )
        if row is None:
            return sheet_xml
        total_con_iva = self._extract_total_from_xml(sheet_xml, shared_strings)
        texto_importe = (
            "Asciende el presupuesto de ejecución material a la expresada "
            f"cantidad de {euros_en_letras(total_con_iva)} IVA INCLUIDO."
        )
        sheet_xml = self._replace_cell_text(
            sheet_xml, f"A{row}", texto_importe,
            style=wrap_style, bold=True, font_size=11,
        )
        return sheet_xml

    def _extract_total_from_xml(self, sheet_xml, shared_strings):
        """Extrae el total con IVA del XML de la hoja en memoria."""
        for row_m in re.finditer(
            r'<row r="(\d+)"[^>]*?(?:/>|>(.*?)</row>)', sheet_xml, re.DOTALL
        ):
            row_num = int(row_m.group(1))
            if row_num < 30:
                continue
            content = row_m.group(2)
            if not content:
                continue
            row_text = ""
            for cell_m in re.finditer(r'<c r="[A-Z]+\d+"[^>]*?(?:/>|>.*?</c>)', content, re.DOTALL):
                row_text += " " + resolve_cell_text(cell_m.group(0), shared_strings)
            text_up = row_text.upper()
            if "TOTAL" in text_up and "I.V.A" in text_up and "INCLUIDO" in text_up:
                val_m = re.search(
                    r'<c r="I' + str(row_num) + r'"[^>]*?>(.*?)</c>',
                    content, re.DOTALL,
                )
                if val_m:
                    v_m = re.search(r'<v>([^<]+)</v>', val_m.group(1))
                    if v_m:
                        try:
                            return float(v_m.group(1))
                        except (ValueError, TypeError):
                            pass
        return 0

    def _update_bottom_client_cell(self, sheet_xml, cliente, shared_strings):
        """Busca la última celda en columna A (fila >= 50) con texto y la reemplaza con cliente."""
        last_row = None
        for m in re.finditer(
            r'<c r="A(\d+)"[^>]*?(?:/>|>.*?</c>)',
            sheet_xml, re.DOTALL,
        ):
            row = int(m.group(1))
            cell = m.group(0)
            if row < 50 or "<f>" in cell:
                continue
            text = resolve_cell_text(cell, shared_strings)
            if text.strip():
                last_row = row
        if last_row is None:
            return sheet_xml
        sheet_xml = self._replace_cell_text(
            sheet_xml, f"A{last_row}", cliente,
            style="47", bold=True, font_size=11,
        )
        return sheet_xml

    def append_partidas_via_xml(self, file_path, new_partidas):
        """
        Añade partidas al final de las existentes en un presupuesto.
        """
        if not new_partidas:
            return True

        from src.core.budget_reader import BudgetReader

        try:
            reader = BudgetReader()
            existing_data = reader.read(file_path)
            existing_partidas = existing_data["partidas"] if existing_data else []

            combined = []
            for p in existing_partidas:
                combined.append({
                    "titulo": p.get("concepto", "").split("\n")[0] if p.get("concepto") else "",
                    "descripcion": "\n".join(p.get("concepto", "").split("\n")[1:]) if "\n" in p.get("concepto", "") else "",
                    "concepto": p.get("concepto", ""),
                    "cantidad": p.get("cantidad", 1),
                    "unidad": p.get("unidad", "ud"),
                    "precio_unitario": p.get("precio", 0),
                })
            for p in new_partidas:
                combined.append(p)

            return self.insert_partidas_via_xml(file_path, combined)
        except Exception as e:
            logger.exception("Error al añadir partidas")
            return False

    @staticmethod
    def _apply_page_config_after_write(file_path):
        """Aplica configuración de página: encabezados físicos + salto antes del resumen."""
        try:
            from src.core.pdf_exporter import PDFExporter
            h_row, s_row = PDFExporter._find_obra_rows(file_path)
            ok = PDFExporter.insert_headers_at_page_breaks(file_path)
            if not ok and s_row:
                PDFExporter.apply_page_config(file_path, h_row, s_row)
            logger.info(
                "Page config aplicada: %s (header=%s, summary=%s, com=%s)",
                file_path, h_row, s_row, ok,
            )
        except Exception as exc:
            logger.warning("Error al aplicar page config tras escribir: %s", exc)
