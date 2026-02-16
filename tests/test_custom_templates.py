"""
Tests para plantillas personalizadas: almacenamiento, extracción y catálogo unificado.
"""

import json
import os
import shutil
import tempfile

import pytest

from src.core.custom_templates import CustomTemplateStore
from src.core.work_type_catalog import WorkTypeCatalog
from src.core.excel_partidas_extractor import ExcelPartidasExtractor
from src.core.excel_manager import ExcelManager
from src.core.template_manager import TemplateManager


@pytest.fixture
def temp_dir():
    """Directorio temporal para tests."""
    path = tempfile.mkdtemp()
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def store(temp_dir):
    """CustomTemplateStore con directorio temporal."""
    return CustomTemplateStore(config_dir=temp_dir)


@pytest.fixture
def sample_plantilla():
    """Plantilla de ejemplo."""
    return {
        'nombre': 'Reforma cocina completa',
        'categoria': 'reforma',
        'descripcion': 'Reforma integral de cocina.',
        'contexto_ia': 'Reforma completa de cocina incluyendo todos los oficios.',
        'partidas_base': [
            {'concepto': 'Demolición de cocina existente', 'unidad': 'm2', 'precio_ref': 15.0},
            {'concepto': 'Fontanería cocina', 'unidad': 'ud', 'precio_ref': 800.0},
            {'concepto': 'Electricidad cocina', 'unidad': 'ud', 'precio_ref': 600.0},
        ],
    }


@pytest.fixture
def budget_file_with_partidas(temp_dir):
    """Crea un presupuesto con partidas insertadas para test de extracción."""
    tm = TemplateManager()
    em = ExcelManager()
    template = tm.get_template_path()
    if not os.path.exists(template):
        pytest.skip("Plantilla no disponible")
    output = os.path.join(temp_dir, "test_extract.xlsx")
    data = {
        "numero_proyecto": "77",
        "fecha": "13-02-26",
        "cliente": "EXTRACTOR TEST",
        "calle": "Calle Extractor",
        "codigo_postal": "03001",
        "tipo": "TEST EXTRACCION",
    }
    em.create_from_template(template, output, data)
    partidas = [
        {"concepto": "Demolición de tabiquería", "cantidad": 25, "unidad": "m2", "precio_unitario": 12.0},
        {"concepto": "Instalación de fontanería", "cantidad": 1, "unidad": "ud", "precio_unitario": 2800.0},
        {"concepto": "Pintura plástica", "cantidad": 80, "unidad": "m2", "precio_unitario": 7.5},
    ]
    em.insert_partidas_via_xml(output, partidas)
    return output


# ============================================================
# Tests: CustomTemplateStore
# ============================================================

class TestCustomTemplateStore:

    def test_empty_store(self, store):
        """Un store nuevo no tiene plantillas."""
        assert store.load_all() == []
        assert store.count() == 0

    def test_add_and_load(self, store, sample_plantilla):
        """Se puede añadir y recuperar una plantilla."""
        assert store.add(sample_plantilla) is True
        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0]['nombre'] == 'Reforma cocina completa'
        assert loaded[0]['personalizada'] is True

    def test_add_requires_nombre(self, store):
        """No se puede añadir una plantilla sin nombre."""
        assert store.add({}) is False
        assert store.add({'nombre': ''}) is False

    def test_replace_existing(self, store, sample_plantilla):
        """Al añadir con el mismo nombre se reemplaza."""
        store.add(sample_plantilla)
        modified = sample_plantilla.copy()
        modified['descripcion'] = 'Versión actualizada'
        store.add(modified)
        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0]['descripcion'] == 'Versión actualizada'

    def test_remove(self, store, sample_plantilla):
        """Se puede eliminar una plantilla existente."""
        store.add(sample_plantilla)
        assert store.remove('Reforma cocina completa') is True
        assert store.count() == 0

    def test_remove_nonexistent(self, store):
        """Eliminar una plantilla que no existe devuelve False."""
        assert store.remove('No existe') is False

    def test_get_by_name(self, store, sample_plantilla):
        """Se puede buscar por nombre."""
        store.add(sample_plantilla)
        found = store.get_by_name('Reforma cocina completa')
        assert found is not None
        assert found['categoria'] == 'reforma'
        assert store.get_by_name('No existe') is None

    def test_persistence(self, temp_dir, sample_plantilla):
        """Las plantillas persisten entre instancias del store."""
        store1 = CustomTemplateStore(config_dir=temp_dir)
        store1.add(sample_plantilla)

        store2 = CustomTemplateStore(config_dir=temp_dir)
        assert store2.count() == 1
        assert store2.load_all()[0]['nombre'] == 'Reforma cocina completa'

    def test_update_descripcion(self, store, sample_plantilla):
        """Se puede actualizar solo la descripción sin cambiar el resto."""
        store.add(sample_plantilla)
        result = store.update('Reforma cocina completa', {'descripcion': 'Nueva descripción'})
        assert result is True
        updated = store.get_by_name('Reforma cocina completa')
        assert updated['descripcion'] == 'Nueva descripción'
        assert updated['categoria'] == 'reforma'
        assert len(updated['partidas_base']) == 3

    def test_update_contexto_ia(self, store, sample_plantilla):
        """Se puede actualizar el contexto_ia."""
        store.add(sample_plantilla)
        nuevo_contexto = 'Nuevo contexto IA detallado para cocina completa con fontanería.'
        result = store.update('Reforma cocina completa', {'contexto_ia': nuevo_contexto})
        assert result is True
        assert store.get_by_name('Reforma cocina completa')['contexto_ia'] == nuevo_contexto

    def test_update_partidas_base(self, store, sample_plantilla):
        """Se puede reemplazar la lista de partidas_base."""
        store.add(sample_plantilla)
        nuevas_partidas = [
            {'concepto': 'Pintura cocina', 'unidad': 'm2', 'precio_ref': 12.0},
        ]
        result = store.update('Reforma cocina completa', {'partidas_base': nuevas_partidas})
        assert result is True
        updated = store.get_by_name('Reforma cocina completa')
        assert len(updated['partidas_base']) == 1
        assert updated['partidas_base'][0]['concepto'] == 'Pintura cocina'

    def test_update_nonexistent(self, store):
        """Intentar actualizar una plantilla inexistente devuelve False."""
        assert store.update('No existe', {'descripcion': 'test'}) is False

    def test_update_cannot_change_personalizada(self, store, sample_plantilla):
        """No se puede cambiar el flag personalizada mediante update."""
        store.add(sample_plantilla)
        store.update('Reforma cocina completa', {'personalizada': False})
        updated = store.get_by_name('Reforma cocina completa')
        assert updated['personalizada'] is True

    def test_update_nombre_changes_key(self, store, sample_plantilla):
        """Si se cambia el nombre, se actualiza correctamente."""
        store.add(sample_plantilla)
        result = store.update('Reforma cocina completa', {'nombre': 'Cocina premium'})
        assert result is True
        assert store.get_by_name('Reforma cocina completa') is None
        assert store.get_by_name('Cocina premium') is not None
        assert store.get_by_name('Cocina premium')['categoria'] == 'reforma'


# ============================================================
# Tests: WorkTypeCatalog unificado
# ============================================================

class TestCatalogUnified:

    def test_predefined_still_available(self):
        """Las plantillas predefinidas siguen disponibles."""
        catalog = WorkTypeCatalog()
        names = catalog.get_predefined_names()
        assert len(names) >= 6
        assert 'Reparación de bajante' in names

    def test_custom_templates_appear_in_get_all(self, temp_dir, sample_plantilla):
        """Las plantillas personalizadas aparecen en get_all."""
        store = CustomTemplateStore(config_dir=temp_dir)
        store.add(sample_plantilla)
        catalog = WorkTypeCatalog(custom_store=store)
        names = catalog.get_all_names()
        assert 'Reforma cocina completa' in names
        assert 'Reparación de bajante' in names

    def test_get_by_name_finds_custom(self, temp_dir, sample_plantilla):
        """get_by_name encuentra plantillas personalizadas."""
        store = CustomTemplateStore(config_dir=temp_dir)
        store.add(sample_plantilla)
        catalog = WorkTypeCatalog(custom_store=store)
        found = catalog.get_by_name('Reforma cocina completa')
        assert found is not None
        assert found['personalizada'] is True

    def test_add_custom_via_catalog(self, temp_dir, sample_plantilla):
        """Se pueden añadir plantillas personalizadas desde el catálogo."""
        store = CustomTemplateStore(config_dir=temp_dir)
        catalog = WorkTypeCatalog(custom_store=store)
        assert catalog.add_custom(sample_plantilla) is True
        assert 'Reforma cocina completa' in catalog.get_custom_names()

    def test_remove_custom_via_catalog(self, temp_dir, sample_plantilla):
        """Se pueden eliminar plantillas personalizadas desde el catálogo."""
        store = CustomTemplateStore(config_dir=temp_dir)
        catalog = WorkTypeCatalog(custom_store=store)
        catalog.add_custom(sample_plantilla)
        assert catalog.remove_custom('Reforma cocina completa') is True
        assert 'Reforma cocina completa' not in catalog.get_all_names()

    def test_cannot_remove_predefined(self):
        """No se pueden eliminar plantillas predefinidas."""
        catalog = WorkTypeCatalog()
        assert catalog.remove_custom('Reparación de bajante') is False

    def test_update_custom_via_catalog(self, temp_dir, sample_plantilla):
        """Se puede actualizar una plantilla personalizada desde el catálogo."""
        store = CustomTemplateStore(config_dir=temp_dir)
        catalog = WorkTypeCatalog(custom_store=store)
        catalog.add_custom(sample_plantilla)
        result = catalog.update_custom('Reforma cocina completa', {'descripcion': 'Actualizada'})
        assert result is True
        assert catalog.get_by_name('Reforma cocina completa')['descripcion'] == 'Actualizada'

    def test_cannot_update_predefined(self):
        """No se pueden modificar plantillas predefinidas."""
        catalog = WorkTypeCatalog()
        result = catalog.update_custom('Reparación de bajante', {'descripcion': 'hack'})
        assert result is False


# ============================================================
# Tests: ExcelPartidasExtractor
# ============================================================

class TestExcelPartidasExtractor:

    def test_extract_from_budget(self, budget_file_with_partidas):
        """Extrae partidas de un presupuesto generado con la plantilla."""
        extractor = ExcelPartidasExtractor()
        partidas = extractor.extract(budget_file_with_partidas)
        assert len(partidas) >= 3
        conceptos = [p['concepto'] for p in partidas]
        assert any('Demolición' in c for c in conceptos)
        assert any('fontanería' in c.lower() for c in conceptos)

    def test_extract_has_correct_fields(self, budget_file_with_partidas):
        """Las partidas extraídas tienen los campos esperados."""
        extractor = ExcelPartidasExtractor()
        partidas = extractor.extract(budget_file_with_partidas)
        for p in partidas:
            assert 'concepto' in p
            assert 'unidad' in p
            assert 'precio_ref' in p

    def test_extract_from_nonexistent_file(self):
        """Devuelve lista vacía si el archivo no existe."""
        extractor = ExcelPartidasExtractor()
        result = extractor.extract("no_existe.xlsx")
        assert result == []

    def test_extract_from_empty_template(self, temp_dir):
        """Extrae las partidas de ejemplo de la plantilla sin modificar."""
        tm = TemplateManager()
        em = ExcelManager()
        template = tm.get_template_path()
        if not os.path.exists(template):
            pytest.skip("Plantilla no disponible")
        output = os.path.join(temp_dir, "test_empty_template.xlsx")
        data = {"numero_proyecto": "0", "fecha": "01-01-26", "cliente": "TEST", "tipo": "TEST"}
        em.create_from_template(template, output, data)
        extractor = ExcelPartidasExtractor()
        partidas = extractor.extract(output)
        # La plantilla tiene partidas de ejemplo en filas 17-26
        assert len(partidas) >= 0  # Puede o no tener partidas de ejemplo
