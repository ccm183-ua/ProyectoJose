"""
Gestor de archivos Excel.
"""

import os
import re
import shutil
import tempfile
import zipfile
from xml.sax.saxutils import escape as xml_escape

from openpyxl import load_workbook
from src.core.template_manager import TemplateManager

# Hoja de datos en la plantilla 122-20 (PRESUP FINAL = sheet2)
SHEET_12220 = "xl/worksheets/sheet2.xml"


def _replace_cell_in_sheet_xml(sheet_xml, ref, value):
    """Sustituye el valor de la celda ref en el XML de la hoja; conserva el estilo (s=...)."""
    escaped = xml_escape(str(value))
    # Celda: <c r="E5" s="64"/> o <c r="E5" s="64">...</c>; conservar estilo
    pattern = r'<c r="' + re.escape(ref) + r'" ([^>]*?)(?:/>|>.*?</c>)'
    match = re.search(pattern, sheet_xml, re.DOTALL)
    if not match:
        return sheet_xml
    attrs = match.group(1)
    style = re.search(r's="\d+"', attrs)
    style_str = (" " + style.group(0)) if style else ""
    new_cell = f'<c r="{ref}"{style_str} t="inlineStr"><is><t>{escaped}</t></is></c>'
    return re.sub(pattern, new_cell, sheet_xml, count=1, flags=re.DOTALL)


class ExcelManager:
    """Clase para gestionar archivos Excel."""
    
    def __init__(self):
        """Inicializa el gestor de Excel."""
        self.template_manager = TemplateManager()
    
    def create_from_template(self, template_path, output_path, data):
        """
        Crea un archivo Excel desde una plantilla rellenando los datos.
        
        Args:
            template_path: Ruta de la plantilla
            output_path: Ruta donde guardar el archivo
            data: Diccionario con los datos a rellenar
            
        Returns:
            bool: True si se creó correctamente, False en caso contrario
        """
        try:
            # Crear directorio de salida primero
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Copiar plantilla al destino (logo, imágenes y formato quedan intactos)
            shutil.copy2(template_path, output_path)

            # Preparar datos del proyecto
            nombre_obra = data.get('nombre_obra', '')
            if not nombre_obra:
                nombre_obra = f"{data.get('direccion', '')} {data.get('numero', '')}".strip()
            direccion_parts = []
            if data.get('calle'):
                direccion_parts.append(data.get('calle'))
            if data.get('num_calle'):
                direccion_parts.append(f"Nº {data.get('num_calle')}")
            direccion_solo_calle_numero = ' '.join(direccion_parts)
            if not direccion_solo_calle_numero:
                direccion_solo_calle_numero = (data.get('direccion', '') or '').strip()
                if data.get('numero'):
                    direccion_solo_calle_numero = f"{direccion_solo_calle_numero} Nº {data.get('numero')}".strip()

            # Rellenar solo las celdas de datos en el XML de la hoja (sin abrir con openpyxl = logo/título intactos)
            self._patch_sheet2_cells_12220(output_path, data, nombre_obra, direccion_solo_calle_numero)
            return True
            
        except Exception as e:
            print(f"Error al crear archivo Excel: {e}")
            return False

    def _patch_sheet2_cells_12220(self, output_path, data, nombre_obra, direccion_solo_calle_numero):
        """
        Modifica solo el XML de la hoja de datos (sheet2) dentro del xlsx, sin tocar
        medios (logo, imágenes) ni dibujos. Así el logo y el título quedan intactos.
        """
        # Valores para cada celda (inlineStr para no tocar sharedStrings)
        fecha = data.get('fecha', '')
        if fecha:
            try:
                parts = str(fecha).strip().split('-')
                if len(parts) == 3:
                    fecha = f"{parts[0]}/{parts[1]}/20{parts[2]}"
            except Exception:
                pass
        obra_texto = (data.get('tipo', '') or nombre_obra or '').strip()
        obra_final = f"Obra: {obra_texto}." if obra_texto else "Obra:"

        celdas = {
            "E5": str(data.get('numero_proyecto', '') or data.get('numero', '') or '').strip(),
            "H5": fecha or '',
            "B7": (data.get('cliente', '') or '').strip(),
            "H7": '',
            "B9": (direccion_solo_calle_numero or '').strip(),
            "H9": str(data.get('codigo_postal', '') or '').strip(),
            "B11": '',
            "H11": '',
            "A14": obra_final,
        }

        with zipfile.ZipFile(output_path, "r") as z_in:
            namelist = z_in.namelist()
            sheet_content = z_in.read(SHEET_12220).decode("utf-8")
            otros = {n: z_in.read(n) for n in namelist if n != SHEET_12220}

        for ref, valor in celdas.items():
            sheet_content = _replace_cell_in_sheet_xml(sheet_content, ref, valor)

        fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
        try:
            os.close(fd)
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as z_out:
                for name in namelist:
                    if name == SHEET_12220:
                        z_out.writestr(name, sheet_content.encode("utf-8"))
                    else:
                        z_out.writestr(name, otros[name])
            shutil.move(tmp_path, output_path)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise

    def load_budget(self, file_path):
        """
        Carga un presupuesto desde un archivo Excel.
        
        Args:
            file_path: Ruta del archivo Excel
            
        Returns:
            Workbook: Objeto Workbook o None si hay error
        """
        try:
            if not os.path.exists(file_path):
                return None
            
            wb = load_workbook(file_path)
            return wb
        except Exception as e:
            return None
    
    def add_budget_row(self, file_path, budget_row):
        """
        Añade una fila de presupuesto al archivo Excel.
        
        Args:
            file_path: Ruta del archivo Excel
            budget_row: Diccionario con los datos de la fila
            
        Returns:
            bool: True si se añadió correctamente, False en caso contrario
        """
        try:
            wb = load_workbook(file_path)
            ws = wb.active
            
            # Encontrar la última fila con datos antes de los totales (filas 15-17)
            # Asumimos que los encabezados están en la fila 11
            start_row = 12
            last_data_row = start_row - 1
            total_row_start = None
            
            # Buscar la última fila con datos y dónde empiezan los totales
            for row_idx in range(start_row, min(ws.max_row + 10, 30)):  # Buscar hasta la fila 30
                cell_value = ws.cell(row=row_idx, column=1).value
                # Detener si encontramos "SUBTOTAL", "IVA" o "TOTAL"
                if cell_value:
                    cell_str = str(cell_value).upper()
                    if ('SUBTOTAL' in cell_str or 'IVA' in cell_str or 'TOTAL' in cell_str) and total_row_start is None:
                        total_row_start = row_idx
                        break
                if cell_value is not None and cell_value != '':
                    last_data_row = row_idx
            
            # Si no encontramos dónde empiezan los totales, asumimos fila 15
            if total_row_start is None:
                total_row_start = 15
            
            # Siempre insertar una nueva fila después de la última fila con datos
            if last_data_row < start_row:
                # No hay datos, insertar en start_row
                ws.insert_rows(start_row)
                empty_row = start_row
            else:
                # Insertar después de la última fila con datos, pero antes de los totales
                empty_row = last_data_row + 1
                # Solo insertar si no estamos en la fila de totales
                if empty_row < total_row_start:
                    ws.insert_rows(empty_row)
                else:
                    # Si ya estamos en o después de los totales, insertar antes de ellos
                    ws.insert_rows(total_row_start)
                    empty_row = total_row_start
            
            # Añadir datos
            ws.cell(row=empty_row, column=1).value = budget_row.get('concepto', '')
            ws.cell(row=empty_row, column=2).value = budget_row.get('cantidad', 0)
            ws.cell(row=empty_row, column=3).value = budget_row.get('unidad', '')
            ws.cell(row=empty_row, column=4).value = budget_row.get('precio_unitario', 0)
            ws.cell(row=empty_row, column=5).value = budget_row.get('importe', 0)
            
            # Guardar el archivo
            wb.save(file_path)
            
            # Actualizar fórmulas de totales (esto recargará el archivo)
            self.recalculate_totals(file_path)
            
            return True
            
        except Exception as e:
            print(f"Error al añadir fila: {e}")
            return False
    
    def modify_budget_row(self, file_path, row_index, new_data):
        """
        Modifica una fila de presupuesto.
        
        Args:
            file_path: Ruta del archivo Excel
            row_index: Índice de la fila a modificar
            new_data: Diccionario con los nuevos datos
            
        Returns:
            bool: True si se modificó correctamente, False en caso contrario
        """
        try:
            wb = load_workbook(file_path)
            ws = wb.active
            
            # Modificar datos (row_index es 1-based, pero ajustamos para la fila real)
            actual_row = 11 + row_index  # Asumiendo que los datos empiezan en fila 12
            
            if actual_row <= ws.max_row:
                ws.cell(row=actual_row, column=1).value = new_data.get('concepto', '')
                ws.cell(row=actual_row, column=2).value = new_data.get('cantidad', 0)
                ws.cell(row=actual_row, column=3).value = new_data.get('unidad', '')
                ws.cell(row=actual_row, column=4).value = new_data.get('precio_unitario', 0)
                ws.cell(row=actual_row, column=5).value = new_data.get('importe', 0)
                
                # Recalcular totales
                self.recalculate_totals(file_path)
                
                wb.save(file_path)
                return True
            
            return False
            
        except Exception as e:
            print(f"Error al modificar fila: {e}")
            return False
    
    def delete_budget_row(self, file_path, row_index):
        """
        Elimina una fila de presupuesto.
        
        Args:
            file_path: Ruta del archivo Excel
            row_index: Índice de la fila a eliminar
            
        Returns:
            bool: True si se eliminó correctamente, False en caso contrario
        """
        try:
            wb = load_workbook(file_path)
            ws = wb.active
            
            actual_row = 11 + row_index
            
            if actual_row <= ws.max_row:
                ws.delete_rows(actual_row)
                
                # Recalcular totales
                self.recalculate_totals(file_path)
                
                wb.save(file_path)
                return True
            
            return False
            
        except Exception as e:
            print(f"Error al eliminar fila: {e}")
            return False
    
    def recalculate_totals(self, file_path):
        """
        Recalcula los totales del presupuesto.
        
        Args:
            file_path: Ruta del archivo Excel
            
        Returns:
            bool: True si se recalculó correctamente, False en caso contrario
        """
        try:
            wb = load_workbook(file_path)
            ws = wb.active
            
            # Encontrar fila de inicio de datos (asumimos fila 12)
            start_row = 12
            end_row = start_row - 1
            
            # Buscar última fila con datos antes de los totales (filas 15-17)
            # Buscar desde start_row hasta la fila 14 (antes de los totales)
            for row_idx in range(start_row, 15):
                if ws.cell(row=row_idx, column=1).value is not None and ws.cell(row=row_idx, column=1).value != '':
                    end_row = row_idx
            
            # Si no encontramos datos en las filas 12-14, buscar más abajo
            if end_row < start_row:
                # Buscar en un rango más amplio, pero antes de los totales
                for row_idx in range(start_row, ws.max_row + 1):
                    # Detener si encontramos "SUBTOTAL", "IVA" o "TOTAL"
                    cell_value = str(ws.cell(row=row_idx, column=1).value or '').upper()
                    if 'SUBTOTAL' in cell_value or 'IVA' in cell_value or 'TOTAL' in cell_value:
                        break
                    if ws.cell(row=row_idx, column=1).value is not None and ws.cell(row=row_idx, column=1).value != '':
                        end_row = row_idx
            
            # Si aún no encontramos, usar max_row pero asegurarnos de que no sea una fila de totales
            if end_row < start_row:
                end_row = min(ws.max_row, 14)  # Máximo hasta la fila 14
            
            # Actualizar fórmula de subtotal (asumimos fila 15)
            if end_row >= start_row:
                subtotal_formula = f"=SUM(E{start_row}:E{end_row})"
                ws['E15'] = subtotal_formula
                ws['E15'].number_format = '#,##0.00 €'
            
            # Actualizar fórmula de IVA (asumimos fila 16)
            ws['E16'] = '=E15*0.21'
            ws['E16'].number_format = '#,##0.00 €'
            
            # Actualizar fórmula de TOTAL (asumimos fila 17)
            ws['E17'] = '=E15+E16'
            ws['E17'].number_format = '#,##0.00 €'
            
            wb.save(file_path)
            return True
            
        except Exception as e:
            print(f"Error al recalcular totales: {e}")
            return False
    
    def save_budget(self, file_path):
        """
        Guarda un presupuesto.
        
        Args:
            file_path: Ruta del archivo Excel
            
        Returns:
            bool: True si se guardó correctamente, False en caso contrario
        """
        try:
            # Este método se puede usar para guardar cambios si se está editando
            # Por ahora, simplemente verificamos que el archivo existe
            return os.path.exists(file_path)
        except Exception:
            return False
