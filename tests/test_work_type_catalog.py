"""
Tests para WorkTypeCatalog (FASE 1 - RED).

Cubren:
- Carga del catálogo JSON de tipos de obra
- Validación del schema de plantillas y partidas
- Búsqueda de plantillas por nombre
- Listado de nombres disponibles
"""

import pytest

from src.core.work_type_catalog import WorkTypeCatalog


@pytest.fixture
def catalog():
    """Fixture: instancia de WorkTypeCatalog con el catálogo real."""
    return WorkTypeCatalog()


class TestLoadCatalog:
    """Tests para la carga del catálogo."""

    def test_load_catalog(self, catalog):
        """El catálogo se carga correctamente y devuelve una lista de plantillas."""
        plantillas = catalog.get_all()
        assert isinstance(plantillas, list)
        assert len(plantillas) > 0

    def test_catalog_not_empty(self, catalog):
        """El catálogo debe tener al menos 2 plantillas definidas."""
        plantillas = catalog.get_all()
        assert len(plantillas) >= 2


class TestCatalogSchema:
    """Tests para validar el schema del catálogo."""

    def test_catalog_schema_valid(self, catalog):
        """Cada plantilla debe tener los campos requeridos: nombre, categoria, descripcion, contexto_ia, partidas_base."""
        required_fields = ['nombre', 'categoria', 'descripcion', 'contexto_ia', 'partidas_base']
        plantillas = catalog.get_all()
        for plantilla in plantillas:
            for field in required_fields:
                assert field in plantilla, (
                    f"La plantilla '{plantilla.get('nombre', '???')}' no tiene el campo '{field}'"
                )

    def test_partida_schema_valid(self, catalog):
        """Cada partida_base debe tener los campos requeridos: concepto, unidad, precio_ref."""
        required_fields = ['concepto', 'unidad', 'precio_ref']
        plantillas = catalog.get_all()
        for plantilla in plantillas:
            assert isinstance(plantilla['partidas_base'], list), (
                f"partidas_base de '{plantilla['nombre']}' debe ser una lista"
            )
            assert len(plantilla['partidas_base']) > 0, (
                f"partidas_base de '{plantilla['nombre']}' no puede estar vacía"
            )
            for partida in plantilla['partidas_base']:
                for field in required_fields:
                    assert field in partida, (
                        f"Partida en '{plantilla['nombre']}' no tiene el campo '{field}'"
                    )

    def test_partida_precio_ref_is_number(self, catalog):
        """El precio_ref de cada partida debe ser un número positivo."""
        plantillas = catalog.get_all()
        for plantilla in plantillas:
            for partida in plantilla['partidas_base']:
                assert isinstance(partida['precio_ref'], (int, float)), (
                    f"precio_ref de '{partida['concepto']}' debe ser numérico"
                )
                assert partida['precio_ref'] > 0, (
                    f"precio_ref de '{partida['concepto']}' debe ser positivo"
                )

    def test_nombre_is_string_not_empty(self, catalog):
        """El nombre de cada plantilla debe ser un string no vacío."""
        plantillas = catalog.get_all()
        for plantilla in plantillas:
            assert isinstance(plantilla['nombre'], str)
            assert len(plantilla['nombre'].strip()) > 0


class TestSearchByName:
    """Tests para búsqueda de plantillas por nombre."""

    def test_get_by_name(self, catalog):
        """Buscar una plantilla existente por nombre exacto devuelve la plantilla."""
        # Obtenemos el primer nombre del catálogo para buscar algo que seguro existe
        all_names = catalog.get_all_names()
        assert len(all_names) > 0, "El catálogo debe tener al menos una plantilla"
        first_name = all_names[0]
        result = catalog.get_by_name(first_name)
        assert result is not None
        assert result['nombre'] == first_name

    def test_get_by_name_not_found(self, catalog):
        """Buscar una plantilla inexistente devuelve None."""
        result = catalog.get_by_name("TIPO_INEXISTENTE_XYZ_12345")
        assert result is None

    def test_get_all_names(self, catalog):
        """get_all_names devuelve una lista de strings con los nombres de todas las plantillas."""
        names = catalog.get_all_names()
        assert isinstance(names, list)
        assert len(names) >= 2
        for name in names:
            assert isinstance(name, str)
            assert len(name.strip()) > 0

    def test_get_all_names_matches_catalog_length(self, catalog):
        """La cantidad de nombres debe coincidir con la cantidad de plantillas."""
        names = catalog.get_all_names()
        plantillas = catalog.get_all()
        assert len(names) == len(plantillas)
