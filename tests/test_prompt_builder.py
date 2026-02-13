"""
Tests para PromptBuilder (FASE 2 - RED).

Cubren:
- Construcción de prompt con plantilla seleccionada (Camino A)
- Construcción de prompt sin plantilla (Camino B)
- Inclusión de datos del usuario y del proyecto en el prompt
- Formato de salida JSON requerido
"""

import pytest

from src.core.prompt_builder import PromptBuilder


@pytest.fixture
def builder():
    """Fixture: instancia de PromptBuilder."""
    return PromptBuilder()


@pytest.fixture
def sample_plantilla():
    """Fixture: plantilla de ejemplo simulando una del catálogo."""
    return {
        "nombre": "Reparación de bajante",
        "categoria": "fontanería",
        "descripcion": "Reparación o sustitución de bajantes.",
        "contexto_ia": "Incluye trabajos de fontanería, albañilería y reposición de acabados.",
        "partidas_base": [
            {"concepto": "Desmontaje de bajante existente", "unidad": "ml", "precio_ref": 18.50},
            {"concepto": "Suministro e instalación de bajante PVC", "unidad": "ml", "precio_ref": 32.00},
        ]
    }


@pytest.fixture
def sample_datos_proyecto():
    """Fixture: datos de proyecto de ejemplo."""
    return {
        "localidad": "Alicante",
        "cliente": "C.P. San Salvador",
        "calle": "Calle Mayor",
    }


class TestPromptWithTemplate:
    """Tests para Camino A: prompt CON plantilla seleccionada."""

    def test_build_prompt_with_template(self, builder, sample_plantilla, sample_datos_proyecto):
        """El prompt con plantilla contiene las secciones esperadas."""
        result = builder.build_prompt(
            tipo_obra="Reparación de bajante comunitaria",
            descripcion="Bajante de PVC en patio interior, 4 plantas",
            plantilla=sample_plantilla,
            datos_proyecto=sample_datos_proyecto
        )
        # Debe ser un string no vacío
        assert isinstance(result, str)
        assert len(result) > 0

    def test_prompt_with_template_includes_contexto_ia(self, builder, sample_plantilla, sample_datos_proyecto):
        """El prompt incluye el contexto_ia de la plantilla seleccionada."""
        result = builder.build_prompt(
            tipo_obra="Reparación de bajante",
            descripcion="En patio interior",
            plantilla=sample_plantilla,
            datos_proyecto=sample_datos_proyecto
        )
        assert sample_plantilla['contexto_ia'] in result

    def test_prompt_with_template_includes_partidas_base(self, builder, sample_plantilla, sample_datos_proyecto):
        """El prompt incluye las partidas de referencia de la plantilla."""
        result = builder.build_prompt(
            tipo_obra="Reparación de bajante",
            descripcion="En patio interior",
            plantilla=sample_plantilla,
            datos_proyecto=sample_datos_proyecto
        )
        # Verificar que al menos los conceptos de las partidas aparecen
        for partida in sample_plantilla['partidas_base']:
            assert partida['concepto'] in result, (
                f"La partida '{partida['concepto']}' debe aparecer en el prompt"
            )


class TestPromptWithoutTemplate:
    """Tests para Camino B: prompt SIN plantilla."""

    def test_build_prompt_without_template(self, builder, sample_datos_proyecto):
        """El prompt sin plantilla se genera correctamente."""
        result = builder.build_prompt(
            tipo_obra="Instalación de ascensor",
            descripcion="Edificio 5 plantas sin ascensor previo",
            plantilla=None,
            datos_proyecto=sample_datos_proyecto
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_prompt_without_template_is_different(self, builder, sample_plantilla, sample_datos_proyecto):
        """Los prompts con y sin plantilla son diferentes (el camino B no tiene partidas de referencia)."""
        prompt_a = builder.build_prompt(
            tipo_obra="Reparación de bajante",
            descripcion="En patio interior",
            plantilla=sample_plantilla,
            datos_proyecto=sample_datos_proyecto
        )
        prompt_b = builder.build_prompt(
            tipo_obra="Reparación de bajante",
            descripcion="En patio interior",
            plantilla=None,
            datos_proyecto=sample_datos_proyecto
        )
        assert prompt_a != prompt_b


class TestPromptContent:
    """Tests para el contenido del prompt (aplican a ambos caminos)."""

    def test_prompt_includes_user_type(self, builder, sample_datos_proyecto):
        """El tipo de obra escrito por el usuario aparece en el prompt."""
        tipo = "Rehabilitación de zaguán comunitario"
        result = builder.build_prompt(
            tipo_obra=tipo,
            descripcion="Zaguán muy deteriorado",
            plantilla=None,
            datos_proyecto=sample_datos_proyecto
        )
        assert tipo in result

    def test_prompt_includes_user_description(self, builder, sample_datos_proyecto):
        """La descripción del usuario aparece en el prompt."""
        descripcion = "Bajante de PVC en patio interior, edificio 4 plantas, acceso difícil"
        result = builder.build_prompt(
            tipo_obra="Reparación de bajante",
            descripcion=descripcion,
            plantilla=None,
            datos_proyecto=sample_datos_proyecto
        )
        assert descripcion in result

    def test_prompt_includes_location(self, builder, sample_datos_proyecto):
        """La localidad del proyecto aparece en el prompt."""
        result = builder.build_prompt(
            tipo_obra="Reparación de bajante",
            descripcion="En patio interior",
            plantilla=None,
            datos_proyecto=sample_datos_proyecto
        )
        assert sample_datos_proyecto['localidad'] in result

    def test_prompt_requests_json_output(self, builder, sample_datos_proyecto):
        """El prompt pide respuesta en formato JSON."""
        result = builder.build_prompt(
            tipo_obra="Reparación de bajante",
            descripcion="En patio interior",
            plantilla=None,
            datos_proyecto=sample_datos_proyecto
        )
        assert "JSON" in result or "json" in result
