"""
Tests para AIService (FASE 3 - RED).

Cubren:
- Parseo de respuestas JSON válidas e inválidas
- Disponibilidad del servicio (con/sin API key)
- Generación de partidas con mock de la API
- Manejo de errores y timeouts
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from src.core.ai_service import AIService


@pytest.fixture
def service():
    """Fixture: AIService con API key de test (no se conecta realmente)."""
    return AIService(api_key="test-fake-key")


@pytest.fixture
def valid_ai_response():
    """Fixture: respuesta JSON válida simulando lo que devolvería Gemini."""
    return json.dumps({
        "partidas": [
            {
                "concepto": "Desmontaje de bajante existente",
                "cantidad": 12,
                "unidad": "ml",
                "precio_unitario": 18.50
            },
            {
                "concepto": "Suministro e instalación de bajante PVC",
                "cantidad": 12,
                "unidad": "ml",
                "precio_unitario": 32.00
            },
            {
                "concepto": "Transporte de escombros",
                "cantidad": 1,
                "unidad": "ud",
                "precio_unitario": 180.00
            }
        ]
    })


class TestParseResponse:
    """Tests para el parseo de respuestas de la IA."""

    def test_parse_valid_json_response(self, service, valid_ai_response):
        """Parsea correctamente una respuesta JSON con partidas."""
        partidas = service.parse_response(valid_ai_response)
        assert isinstance(partidas, list)
        assert len(partidas) == 3
        assert partidas[0]['concepto'] == "Desmontaje de bajante existente"
        assert partidas[0]['cantidad'] == 12
        assert partidas[0]['unidad'] == "ml"
        assert partidas[0]['precio_unitario'] == 18.50

    def test_parse_malformed_json(self, service):
        """Maneja JSON mal formado sin crash, devuelve lista vacía."""
        partidas = service.parse_response("esto no es json {{{")
        assert isinstance(partidas, list)
        assert len(partidas) == 0

    def test_parse_json_without_partidas_key(self, service):
        """Maneja JSON válido pero sin la clave 'partidas'."""
        partidas = service.parse_response('{"items": []}')
        assert isinstance(partidas, list)
        assert len(partidas) == 0

    def test_parse_missing_fields(self, service):
        """Partidas con campos faltantes se incluyen con valores por defecto."""
        response = json.dumps({
            "partidas": [
                {"concepto": "Solo concepto"},
                {"concepto": "Con unidad", "unidad": "m2"}
            ]
        })
        partidas = service.parse_response(response)
        assert len(partidas) == 2
        # Deben tener todos los campos aunque sean por defecto
        for partida in partidas:
            assert 'concepto' in partida
            assert 'cantidad' in partida
            assert 'unidad' in partida
            assert 'precio_unitario' in partida

    def test_parse_json_with_markdown_wrapper(self, service, valid_ai_response):
        """Parsea JSON envuelto en bloques markdown (```json ... ```)."""
        wrapped = f"```json\n{valid_ai_response}\n```"
        partidas = service.parse_response(wrapped)
        assert isinstance(partidas, list)
        assert len(partidas) == 3


class TestAvailability:
    """Tests para la disponibilidad del servicio."""

    def test_is_available_without_key(self):
        """Sin API key el servicio no está disponible."""
        service = AIService(api_key=None)
        assert service.is_available() is False

    def test_is_available_with_empty_key(self):
        """Con API key vacía el servicio no está disponible."""
        service = AIService(api_key="")
        assert service.is_available() is False

    def test_is_available_with_key(self):
        """Con API key configurada el servicio se considera disponible."""
        service = AIService(api_key="valid-key-here")
        assert service.is_available() is True


class TestGeneratePartidas:
    """Tests para la generación de partidas (con mocks)."""

    def test_generate_partidas_mock(self, service, valid_ai_response):
        """Con mock de Gemini, devuelve lista de partidas estructuradas."""
        mock_response = MagicMock()
        mock_response.text = valid_ai_response

        with patch.object(service, '_call_api', return_value=mock_response):
            partidas, error = service.generate_partidas("prompt de test")
            assert error is None
            assert isinstance(partidas, list)
            assert len(partidas) == 3
            assert partidas[0]['concepto'] == "Desmontaje de bajante existente"

    def test_generate_partidas_api_error(self, service):
        """Error de API devuelve lista vacía y mensaje de error."""
        with patch.object(service, '_call_api', side_effect=Exception("API error 500")):
            partidas, error = service.generate_partidas("prompt de test")
            assert isinstance(partidas, list)
            assert len(partidas) == 0
            assert error is not None
            assert len(error) > 0

    def test_generate_partidas_timeout(self, service):
        """Timeout devuelve lista vacía y mensaje de error."""
        with patch.object(service, '_call_api', side_effect=TimeoutError("Request timed out")):
            partidas, error = service.generate_partidas("prompt de test")
            assert isinstance(partidas, list)
            assert len(partidas) == 0
            assert error is not None

    def test_generate_partidas_without_key(self):
        """Intentar generar sin API key devuelve error descriptivo."""
        service = AIService(api_key=None)
        partidas, error = service.generate_partidas("prompt de test")
        assert len(partidas) == 0
        assert error is not None
        assert "API key" in error or "api key" in error.lower() or "clave" in error.lower()
