"""
Tests para BudgetGenerator (FASE 4 - RED).

Cubren:
- Generación con IA + plantilla seleccionada (Camino A online)
- Generación con IA sin plantilla (Camino B online)
- Fallback offline con plantilla seleccionada
- Fallback offline sin plantilla (error descriptivo)
- Validación de campos requeridos en partidas devueltas
- Indicador de fuente (IA vs offline)
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from src.core.budget_generator import BudgetGenerator
from src.core.settings import AI_PROVIDER_DEEPSEEK


@pytest.fixture
def sample_plantilla():
    """Fixture: plantilla de ejemplo."""
    return {
        "nombre": "Reparación de bajante",
        "categoria": "fontanería",
        "descripcion": "Reparación o sustitución de bajantes.",
        "contexto_ia": "Incluye trabajos de fontanería y albañilería.",
        "partidas_base": [
            {"concepto": "Desmontaje de bajante existente", "unidad": "ml", "precio_ref": 18.50},
            {"concepto": "Instalación de bajante PVC", "unidad": "ml", "precio_ref": 32.00},
            {"concepto": "Transporte de escombros", "unidad": "ud", "precio_ref": 180.00},
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


@pytest.fixture
def mock_ai_partidas():
    """Fixture: partidas que devolvería la IA mockeada."""
    return [
        {"concepto": "Desmontaje de bajante", "cantidad": 12, "unidad": "ml", "precio_unitario": 19.00},
        {"concepto": "Bajante PVC 110mm", "cantidad": 12, "unidad": "ml", "precio_unitario": 33.50},
        {"concepto": "Codo PVC 45°", "cantidad": 4, "unidad": "ud", "precio_unitario": 13.00},
        {"concepto": "Retirada de escombros", "cantidad": 1, "unidad": "ud", "precio_unitario": 190.00},
    ]


class TestGenerateWithAI:
    """Tests para generación con IA (online)."""

    def test_generate_with_ai_and_template(self, sample_plantilla, sample_datos_proyecto, mock_ai_partidas):
        """Camino A online: IA recibe plantilla como contexto, devuelve partidas."""
        generator = BudgetGenerator(api_key="fake-key")

        with patch.object(
            generator._ai_service, 'generate_partidas',
            return_value=(mock_ai_partidas, None)
        ):
            result = generator.generate(
                tipo_obra="Reparación de bajante comunitaria",
                descripcion="Bajante en patio interior, 4 plantas",
                plantilla=sample_plantilla,
                datos_proyecto=sample_datos_proyecto,
            )

        assert result['partidas'] == mock_ai_partidas
        assert result['error'] is None
        assert result['source'] == 'ia'

    def test_generate_with_ai_no_template(self, sample_datos_proyecto, mock_ai_partidas):
        """Camino B online: IA recibe solo descripción, devuelve partidas."""
        generator = BudgetGenerator(api_key="fake-key")

        with patch.object(
            generator._ai_service, 'generate_partidas',
            return_value=(mock_ai_partidas, None)
        ):
            result = generator.generate(
                tipo_obra="Instalación de ascensor",
                descripcion="Edificio 5 plantas sin ascensor previo",
                plantilla=None,
                datos_proyecto=sample_datos_proyecto,
            )

        assert len(result['partidas']) > 0
        assert result['error'] is None
        assert result['source'] == 'ia'

    def test_generate_uses_deepseek_when_settings_selects_deepseek(
        self,
        sample_datos_proyecto,
        monkeypatch,
    ):
        """Si settings selecciona DeepSeek, usa el cliente DeepSeek."""
        calls = []

        class FakeSettings:
            def get_ai_provider(self):
                return AI_PROVIDER_DEEPSEEK

            def get_gemini_api_key(self):
                return None

            def get_gemini_model(self):
                return "gemini-test"

            def get_deepseek_api_key(self):
                return "sk-test-key-not-real"

            def get_deepseek_model(self):
                return "deepseek-v4-flash"

        class FakeDeepSeekClient:
            def __init__(self, api_key, model):
                calls.append((api_key, model))

            def is_available(self):
                return True

            def generate_json(self, **kwargs):
                calls.append(kwargs)
                return {
                    "partidas": [
                        {
                            "concepto": "Partida desde DeepSeek",
                            "cantidad": 1,
                            "unidad": "ud",
                            "precio_unitario": 10,
                        }
                    ]
                }

        monkeypatch.setattr("src.core.budget_generator.DeepSeekAIClient", FakeDeepSeekClient)
        generator = BudgetGenerator(settings=FakeSettings())
        result = generator.generate(
            tipo_obra="Test",
            descripcion="Test",
            plantilla=None,
            datos_proyecto=sample_datos_proyecto,
        )

        assert result["source"] == "ia"
        assert result["partidas"][0]["concepto"].startswith("PARTIDA DESDE DEEPSEEK")
        assert calls[0] == ("sk-test-key-not-real", "deepseek-v4-flash")


class TestFallbackOffline:
    """Tests para fallback offline."""

    def test_fallback_offline_with_template(self, sample_plantilla, sample_datos_proyecto):
        """Sin conexión + plantilla seleccionada: devuelve partidas_base."""
        generator = BudgetGenerator(api_key="fake-key")

        with patch.object(
            generator._ai_service, 'generate_partidas',
            return_value=([], "Error de conexión")
        ):
            result = generator.generate(
                tipo_obra="Reparación de bajante",
                descripcion="En patio interior",
                plantilla=sample_plantilla,
                datos_proyecto=sample_datos_proyecto,
            )

        # Debe usar las partidas_base de la plantilla como fallback
        assert len(result['partidas']) > 0
        assert result['source'] == 'offline'
        # Las partidas del fallback deben venir de la plantilla (ahora en MAYÚSCULAS)
        conceptos = [p['concepto'] for p in result['partidas']]
        assert any("DESMONTAJE" in c for c in conceptos)

    def test_fallback_offline_no_template(self, sample_datos_proyecto):
        """Sin conexión + sin plantilla: devuelve error descriptivo."""
        generator = BudgetGenerator(api_key="fake-key")

        with patch.object(
            generator._ai_service, 'generate_partidas',
            return_value=([], "Error de conexión")
        ):
            result = generator.generate(
                tipo_obra="Instalación de ascensor",
                descripcion="Edificio 5 plantas",
                plantilla=None,
                datos_proyecto=sample_datos_proyecto,
            )

        assert len(result['partidas']) == 0
        assert result['error'] is not None
        assert result['source'] == 'error'


class TestResultFormat:
    """Tests para el formato de los resultados."""

    def test_partidas_have_required_fields(self, sample_plantilla, sample_datos_proyecto, mock_ai_partidas):
        """Cada partida devuelta tiene los campos requeridos."""
        generator = BudgetGenerator(api_key="fake-key")
        required_fields = ['concepto', 'cantidad', 'unidad', 'precio_unitario']

        with patch.object(
            generator._ai_service, 'generate_partidas',
            return_value=(mock_ai_partidas, None)
        ):
            result = generator.generate(
                tipo_obra="Reparación",
                descripcion="Test",
                plantilla=sample_plantilla,
                datos_proyecto=sample_datos_proyecto,
            )

        for partida in result['partidas']:
            for field in required_fields:
                assert field in partida, f"Falta el campo '{field}' en la partida"

    def test_generate_returns_source_indicator(self, sample_datos_proyecto, mock_ai_partidas):
        """El resultado indica si las partidas vienen de IA o de fallback."""
        generator = BudgetGenerator(api_key="fake-key")

        # Test con IA exitosa
        with patch.object(
            generator._ai_service, 'generate_partidas',
            return_value=(mock_ai_partidas, None)
        ):
            result = generator.generate(
                tipo_obra="Test",
                descripcion="Test",
                plantilla=None,
                datos_proyecto=sample_datos_proyecto,
            )

        assert 'source' in result
        assert result['source'] in ('ia', 'offline', 'error')

    def test_result_always_has_expected_keys(self, sample_datos_proyecto):
        """El resultado siempre tiene las claves: partidas, error, source."""
        generator = BudgetGenerator(api_key=None)

        result = generator.generate(
            tipo_obra="Test",
            descripcion="Test",
            plantilla=None,
            datos_proyecto=sample_datos_proyecto,
        )

        assert 'partidas' in result
        assert 'error' in result
        assert 'source' in result
        assert isinstance(result['partidas'], list)

    def test_generate_passes_historical_context_to_prompt_builder(self, sample_datos_proyecto):
        """El generador propaga historical_context al PromptBuilder."""
        generator = BudgetGenerator(api_key="fake-key")
        historical_context = {"detected_modules": [{"name": "sustitucion_bajante"}]}

        with patch.object(generator._prompt_builder, "build_prompt", return_value="PROMPT") as build_mock:
            with patch.object(generator._ai_service, "generate_partidas", return_value=([], "error")):
                generator.generate(
                    tipo_obra="Reparación",
                    descripcion="Test",
                    plantilla=None,
                    datos_proyecto=sample_datos_proyecto,
                    historical_context=historical_context,
                )

        assert build_mock.called
        kwargs = build_mock.call_args.kwargs
        assert kwargs.get("historical_context") == historical_context
