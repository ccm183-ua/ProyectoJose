"""
Tests para el validador de esquema de plantillas.
"""

import pytest

from src.core.template_validator import TemplateValidator


@pytest.fixture
def validator():
    """Instancia del validador."""
    return TemplateValidator()


@pytest.fixture
def valid_plantilla():
    """Plantilla válida completa."""
    return {
        'nombre': 'Reforma de baño completa',
        'categoria': 'reforma',
        'descripcion': 'Reforma integral de baño incluyendo todos los oficios.',
        'contexto_ia': 'Reforma completa de baño incluyendo fontanería, electricidad y acabados.',
        'partidas_base': [
            {'concepto': 'Demolición de baño existente', 'unidad': 'm2', 'precio_ref': 18.0},
            {'concepto': 'Fontanería baño', 'unidad': 'ud', 'precio_ref': 900.0},
        ],
    }


class TestTemplateValidator:

    def test_plantilla_valida_completa(self, validator, valid_plantilla):
        """Una plantilla con todos los campos correctos es válida."""
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is True
        assert errors == []

    def test_plantilla_sin_nombre(self, validator, valid_plantilla):
        """Una plantilla sin nombre no es válida."""
        del valid_plantilla['nombre']
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is False
        assert any("nombre" in e.lower() for e in errors)

    def test_plantilla_nombre_vacio(self, validator, valid_plantilla):
        """Una plantilla con nombre vacío no es válida."""
        valid_plantilla['nombre'] = ''
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is False
        assert any("nombre" in e.lower() for e in errors)

    def test_plantilla_nombre_demasiado_largo(self, validator, valid_plantilla):
        """El nombre no puede superar 100 caracteres."""
        valid_plantilla['nombre'] = 'A' * 101
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is False
        assert any("100" in e for e in errors)

    def test_plantilla_sin_categoria(self, validator, valid_plantilla):
        """Una plantilla sin categoría no es válida."""
        del valid_plantilla['categoria']
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is False
        assert any("categoría" in e.lower() for e in errors)

    def test_plantilla_sin_descripcion(self, validator, valid_plantilla):
        """Una plantilla sin descripción no es válida."""
        del valid_plantilla['descripcion']
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is False
        assert any("descripción" in e.lower() for e in errors)

    def test_plantilla_partidas_vacias(self, validator, valid_plantilla):
        """Una plantilla con partidas_base vacío no es válida."""
        valid_plantilla['partidas_base'] = []
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is False
        assert any("al menos 1 partida" in e for e in errors)

    def test_plantilla_sin_partidas(self, validator, valid_plantilla):
        """Una plantilla sin el campo partidas_base no es válida."""
        del valid_plantilla['partidas_base']
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is False
        assert any("al menos 1 partida" in e for e in errors)

    def test_plantilla_precio_negativo(self, validator, valid_plantilla):
        """Un precio negativo no es válido."""
        valid_plantilla['partidas_base'][0]['precio_ref'] = -5.0
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is False
        assert any("positivo" in e for e in errors)

    def test_plantilla_precio_cero(self, validator, valid_plantilla):
        """Un precio de cero no es válido."""
        valid_plantilla['partidas_base'][0]['precio_ref'] = 0
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is False
        assert any("positivo" in e for e in errors)

    def test_plantilla_contexto_ia_muy_corto(self, validator, valid_plantilla):
        """El contexto_ia debe tener al menos 20 caracteres."""
        valid_plantilla['contexto_ia'] = 'Corto'
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is False
        assert any("20 caracteres" in e for e in errors)

    def test_plantilla_contexto_ia_vacio(self, validator, valid_plantilla):
        """El contexto_ia no puede estar vacío."""
        valid_plantilla['contexto_ia'] = ''
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is False

    def test_partida_sin_concepto(self, validator, valid_plantilla):
        """Una partida sin concepto no es válida."""
        valid_plantilla['partidas_base'][0]['concepto'] = ''
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is False
        assert any("concepto" in e for e in errors)

    def test_partida_sin_unidad(self, validator, valid_plantilla):
        """Una partida sin unidad no es válida."""
        valid_plantilla['partidas_base'][0]['unidad'] = ''
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is False
        assert any("unidad" in e for e in errors)

    def test_multiples_errores(self, validator):
        """Se acumulan todos los errores encontrados."""
        plantilla = {
            'nombre': '',
            'categoria': '',
            'descripcion': '',
            'contexto_ia': '',
            'partidas_base': [],
        }
        is_valid, errors = validator.validate(plantilla)
        assert is_valid is False
        assert len(errors) >= 4

    def test_plantilla_no_es_dict(self, validator):
        """Una plantilla que no es diccionario no es válida."""
        is_valid, errors = validator.validate("no es un dict")
        assert is_valid is False

    def test_plantilla_con_campo_personalizada(self, validator, valid_plantilla):
        """El campo personalizada no afecta la validación."""
        valid_plantilla['personalizada'] = True
        is_valid, errors = validator.validate(valid_plantilla)
        assert is_valid is True
        assert errors == []
