"""
Gestor de archivos Excel.
"""

import os
import shutil
from openpyxl import load_workbook
from src.core.template_manager import TemplateManager


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

            # Copiar plantilla al destino para preservar logo, título y formato; luego solo modificamos celdas
            shutil.copy2(template_path, output_path)
            wb = load_workbook(output_path)

            # Usar hoja PRESUP FINAL por nombre (nombre real en la plantilla 122-20)
            ws = wb["PRESUP FINAL"] if "PRESUP FINAL" in wb.sheetnames else wb.active

            # Preparar datos del proyecto
            nombre_obra = data.get('nombre_obra', '')
            if not nombre_obra:
                nombre_obra = f"{data.get('direccion', '')} {data.get('numero', '')}".strip()

            # Solo calle y número para la casilla Dirección (B9); C.P. va aparte en H9
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

            # Plantilla 122-20: rellenar por celdas fijas (hoja PRESUP FINAL)
            if ws.title == "PRESUP FINAL":
                self._fill_template_12220(ws, data, nombre_obra, direccion_solo_calle_numero)

            wb.save(output_path)
            return True
            
        except Exception as e:
            print(f"Error al crear archivo Excel: {e}")
            return False

    def _fill_template_12220(self, ws, data, nombre_obra, direccion_solo_calle_numero):
        """
        Rellena la plantilla 122-20 (hoja PRESUP FINAL) con los datos del proyecto.
        B9 = solo calle y número (sin C.P.). H9 = C.P. por separado.
        Correo (B11) y teléfono (H11) se dejan vacíos.
        """
        # E5: Presupuesto Nº (como texto para consistencia)
        numero_pres = data.get('numero_proyecto', '') or data.get('numero', '')
        ws['E5'] = str(numero_pres).strip() if numero_pres is not None else ''
        # H5: Fecha (DD-MM-YY → DD/MM/YYYY)
        fecha = data.get('fecha', '')
        if fecha:
            try:
                parts = str(fecha).strip().split('-')
                if len(parts) == 3:
                    day, month, year_short = parts
                    ws['H5'] = f"{day}/{month}/20{year_short}"
                else:
                    ws['H5'] = fecha
            except Exception:
                ws['H5'] = fecha
        else:
            ws['H5'] = ''
        # B7: Cliente
        ws['B7'] = (data.get('cliente', '') or '').strip()
        # H7: C.I.F. (sin dato por ahora)
        ws['H7'] = ''
        # B9: Dirección (solo calle y número, sin C.P.)
        ws['B9'] = (direccion_solo_calle_numero or '').strip()
        # H9: C.P. (por separado; como texto para conservar ceros a la izquierda, ej. 03690)
        cp = data.get('codigo_postal', '')
        ws['H9'] = str(cp).strip() if cp is not None else ''
        # B11: Correo (sin dato por ahora)
        ws['B11'] = ''
        # H11: Teléfono (sin dato por ahora)
        ws['H11'] = ''
        # A14: Obra (tipo o nombre de obra)
        obra_texto = (data.get('tipo', '') or nombre_obra or '').strip()
        ws['A14'] = f"Obra: {obra_texto}." if obra_texto else "Obra:"

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
