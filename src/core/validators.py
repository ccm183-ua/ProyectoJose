"""
Validadores de datos para la aplicación.
"""

import re


class DataValidator:
    """Clase para validar datos de entrada."""
    
    MAX_OBRA_NAME_LENGTH = 200
    MAX_DESCRIPCION_LENGTH = 500
    
    def validate_obra_name(self, nombre):
        """
        Valida el nombre de la obra.
        
        Args:
            nombre: Nombre de la obra a validar
            
        Returns:
            bool: True si es válido, False en caso contrario
        """
        if not nombre:
            return False
        
        if not isinstance(nombre, str):
            return False
        
        if len(nombre.strip()) == 0:
            return False
        
        if len(nombre) > self.MAX_OBRA_NAME_LENGTH:
            return False
        
        return True
    
    def validate_direccion(self, direccion):
        """
        Valida la dirección.
        
        Args:
            direccion: Dirección a validar
            
        Returns:
            bool: True si es válido, False en caso contrario
        """
        if not direccion:
            return False
        
        if not isinstance(direccion, str):
            return False
        
        if len(direccion.strip()) == 0:
            return False
        
        return True
    
    def validate_numero(self, numero):
        """
        Valida el número de calle.
        
        Args:
            numero: Número a validar
            
        Returns:
            bool: True si es válido, False en caso contrario
        """
        if not numero:
            return False
        
        # Convertir a string si es número
        numero_str = str(numero).strip()
        
        if len(numero_str) == 0:
            return False
        
        return True
    
    def validate_descripcion(self, descripcion):
        """
        Valida la descripción.
        
        Args:
            descripcion: Descripción a validar
            
        Returns:
            bool: True si es válido, False en caso contrario
        """
        if not descripcion:
            return False
        
        if not isinstance(descripcion, str):
            return False
        
        descripcion = descripcion.strip()
        
        if len(descripcion) == 0:
            return False
        
        if len(descripcion) >= self.MAX_DESCRIPCION_LENGTH:
            return False
        
        return True
    
    def validate_postal_code(self, codigo_postal):
        """
        Valida el código postal (formato español: 5 dígitos).
        
        Args:
            codigo_postal: Código postal a validar
            
        Returns:
            bool: True si es válido, False en caso contrario
        """
        if not codigo_postal:
            return False
        
        if not isinstance(codigo_postal, str):
            codigo_postal = str(codigo_postal)
        
        codigo_postal = codigo_postal.strip()
        
        # Formato español: exactamente 5 dígitos
        pattern = r'^\d{5}$'
        
        if not re.match(pattern, codigo_postal):
            return False
        
        return True
    
    def validate_all(self, data):
        """
        Valida todos los campos de datos.
        
        Args:
            data: Diccionario con los datos a validar
            
        Returns:
            tuple: (bool, list) - (True si todos son válidos, lista de errores)
        """
        errors = []
        
        if not self.validate_direccion(data.get('direccion')):
            errors.append("Dirección inválida")
        
        if not self.validate_numero(data.get('numero')):
            errors.append("Número inválido")
        
        if not self.validate_postal_code(data.get('codigo_postal')):
            errors.append("Código postal inválido")
        
        if not self.validate_descripcion(data.get('descripcion')):
            errors.append("Descripción inválida")
        
        nombre_obra = f"{data.get('direccion', '')} {data.get('numero', '')}".strip()
        if not self.validate_obra_name(nombre_obra):
            errors.append("Nombre de obra inválido")
        
        return len(errors) == 0, errors
