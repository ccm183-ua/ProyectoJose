"""
Parser para datos de proyecto desde el portapapeles (Excel TSV).
"""

import re
from typing import Dict, Optional, Tuple


class ProjectParser:
    """Clase para parsear datos de proyecto desde el portapapeles."""
    
    # Campos obligatorios
    REQUIRED_FIELDS = ['numero', 'fecha', 'cliente', 'calle']
    
    def __init__(self):
        """Inicializa el parser."""
        pass
    
    def parse_clipboard_data(self, clipboard_text: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Parsea los datos del portapapeles (TSV desde Excel).
        
        Args:
            clipboard_text: Texto del portapapeles (separado por tabulaciones)
            
        Returns:
            Tuple[Optional[Dict], Optional[str]]: (datos parseados, mensaje de error)
        """
        if not clipboard_text or not clipboard_text.strip():
            return None, "El portapapeles está vacío"
        
        # Dividir por tabulaciones
        parts = clipboard_text.strip().split('\t')
        
        # Debe tener al menos 9 columnas (A-I)
        if len(parts) < 9:
            return None, f"Faltan columnas. Se esperaban 9, se encontraron {len(parts)}"
        
        # Extraer datos según el orden: Nº, FECHA, CLIENTE, MEDIACIÓN, CALLE, NUM, C.P, LOCALIDAD, TIPO
        try:
            numero = parts[0].strip() if parts[0] else None
            fecha = parts[1].strip() if parts[1] else None
            cliente = parts[2].strip() if parts[2] else None
            mediacion = parts[3].strip() if parts[3] else None
            calle = parts[4].strip() if parts[4] else None
            num_calle = parts[5].strip() if parts[5] else None
            codigo_postal = parts[6].strip() if parts[6] else None
            localidad = parts[7].strip() if parts[7] else None
            tipo = parts[8].strip() if parts[8] else None
            
            # Validar campos obligatorios
            if not numero:
                return None, "El campo Nº es obligatorio"
            if not fecha:
                return None, "El campo FECHA es obligatorio"
            if not cliente:
                return None, "El campo CLIENTE es obligatorio"
            if not calle:
                return None, "El campo CALLE es obligatorio"
            
            # Validar formato de fecha (debe ser DD-MM-YY)
            if not self._validate_date_format(fecha):
                return None, f"Formato de fecha inválido: {fecha}. Se espera DD-MM-YY"
            
            # Construir diccionario de datos
            data = {
                'numero': numero,
                'fecha': fecha,
                'cliente': cliente,
                'mediacion': mediacion if mediacion else '',
                'calle': calle,
                'num_calle': num_calle if num_calle else '',
                'codigo_postal': codigo_postal if codigo_postal else '',
                'localidad': localidad if localidad else '',
                'tipo': tipo if tipo else ''
            }
            
            return data, None
            
        except Exception as e:
            return None, f"Error al parsear datos: {str(e)}"
    
    def _validate_date_format(self, date_str: str) -> bool:
        """
        Valida que la fecha tenga el formato DD-MM-YY.
        
        Args:
            date_str: String con la fecha
            
        Returns:
            bool: True si el formato es válido
        """
        # Formato esperado: DD-MM-YY (ej: 08-01-26)
        pattern = r'^\d{2}-\d{2}-\d{2}$'
        return bool(re.match(pattern, date_str))
    
    def extract_year_from_date(self, date_str: str) -> str:
        """
        Extrae los últimos dos dígitos del año desde una fecha DD-MM-YY.
        
        Args:
            date_str: Fecha en formato DD-MM-YY
            
        Returns:
            str: Últimos dos dígitos del año (YY)
        """
        if not date_str:
            return ''
        
        # La fecha viene como DD-MM-YY, los últimos dos dígitos son el año
        parts = date_str.split('-')
        if len(parts) == 3:
            return parts[2]  # YY es la última parte
        return ''
