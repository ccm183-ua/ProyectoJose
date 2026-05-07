"""
Tests del clasificador de partidas históricas.
"""

from src.core.historical_partida_classifier import HistoricalPartidaClassifier


class TestHistoricalPartidaClassifier:
    def test_classify_partida_single_module(self):
        classifier = HistoricalPartidaClassifier()
        partida = {
            "titulo": "Suministro e instalacion de bajante PVC 110 mm",
            "descripcion": "Incluye codos, manguitos y abrazaderas",
        }
        results = classifier.classify(partida)
        modules = [row["module"] for row in results]
        assert "sustitucion_bajante" in modules

    def test_classify_partida_multiple_modules(self):
        classifier = HistoricalPartidaClassifier()
        partida = {
            "titulo": "Apertura y cierre de rozas para sustitucion de bajante",
            "descripcion": "Demolicion de revestimiento, mortero y PVC",
        }
        results = classifier.classify(partida)
        modules = [row["module"] for row in results]
        assert "demolicion" in modules
        assert "albanileria" in modules
        assert "sustitucion_bajante" in modules
