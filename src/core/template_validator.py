"""
Validador de esquema de plantillas de presupuesto.

Comprueba que una plantilla tiene todos los campos obligatorios
con los tipos y restricciones correctos antes de guardarla.
"""

from typing import Dict, List, Tuple


class TemplateValidator:
    """Valida el esquema de una plantilla antes de guardarla."""

    # Longitud máxima del nombre
    MAX_NOMBRE_LENGTH = 100

    # Longitud mínima del contexto_ia (debe ser descriptivo)
    MIN_CONTEXTO_IA_LENGTH = 20

    def validate(self, plantilla: dict) -> Tuple[bool, List[str]]:
        """
        Valida una plantilla completa.

        Args:
            plantilla: Diccionario con la plantilla a validar.

        Returns:
            Tupla (es_valida, lista_de_errores).
            Si es_valida es True, lista_de_errores estará vacía.
        """
        errors: List[str] = []

        if not isinstance(plantilla, dict):
            return False, ["La plantilla debe ser un diccionario"]

        # Validar nombre
        self._validate_nombre(plantilla, errors)

        # Validar categoría
        self._validate_string_field(
            plantilla, 'categoria', "La categoría es obligatoria", errors
        )

        # Validar descripción
        self._validate_string_field(
            plantilla, 'descripcion', "La descripción es obligatoria", errors
        )

        # Validar contexto_ia
        self._validate_contexto_ia(plantilla, errors)

        # Validar partidas_base
        self._validate_partidas_base(plantilla, errors)

        return (len(errors) == 0, errors)

    def _validate_nombre(self, plantilla: dict, errors: List[str]):
        """Valida el campo nombre."""
        nombre = plantilla.get('nombre')
        if not nombre or not isinstance(nombre, str) or not nombre.strip():
            errors.append("El nombre es obligatorio")
            return
        if len(nombre.strip()) > self.MAX_NOMBRE_LENGTH:
            errors.append(
                f"El nombre no puede superar {self.MAX_NOMBRE_LENGTH} caracteres"
            )

    def _validate_string_field(
        self, plantilla: dict, field: str, error_msg: str, errors: List[str]
    ):
        """Valida que un campo sea un string no vacío."""
        value = plantilla.get(field)
        if not value or not isinstance(value, str) or not value.strip():
            errors.append(error_msg)

    def _validate_contexto_ia(self, plantilla: dict, errors: List[str]):
        """Valida el campo contexto_ia."""
        contexto = plantilla.get('contexto_ia')
        if not contexto or not isinstance(contexto, str) or not contexto.strip():
            errors.append("El contexto IA es obligatorio")
            return
        if len(contexto.strip()) < self.MIN_CONTEXTO_IA_LENGTH:
            errors.append(
                "El contexto IA debe ser descriptivo "
                f"(mín. {self.MIN_CONTEXTO_IA_LENGTH} caracteres)"
            )

    def _validate_partidas_base(self, plantilla: dict, errors: List[str]):
        """Valida el campo partidas_base y cada partida individual."""
        partidas = plantilla.get('partidas_base')
        if not isinstance(partidas, list) or len(partidas) == 0:
            errors.append("Debe tener al menos 1 partida")
            return

        for i, partida in enumerate(partidas, start=1):
            if not isinstance(partida, dict):
                errors.append(f"La partida {i} no es válida")
                continue

            concepto = partida.get('concepto')
            if not concepto or not isinstance(concepto, str) or not concepto.strip():
                errors.append(f"La partida {i} debe tener un concepto")

            unidad = partida.get('unidad')
            if not unidad or not isinstance(unidad, str) or not unidad.strip():
                errors.append(f"La partida {i} debe tener una unidad")

            precio = partida.get('precio_ref')
            if precio is None:
                errors.append(f"La partida {i} debe tener un precio de referencia")
            elif not isinstance(precio, (int, float)):
                errors.append(f"El precio de la partida {i} debe ser un número")
            elif precio <= 0:
                errors.append(f"El precio de la partida {i} debe ser positivo")
