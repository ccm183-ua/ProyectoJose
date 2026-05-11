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

    def test_hormigon_terms_classify_as_estructura_not_hormigon(self):
        classifier = HistoricalPartidaClassifier()
        results = classifier.classify_text("Dados de hormigon en parking con refuerzo de viga")
        modules = [row["module"] for row in results]
        assert "estructura" in modules
        assert "hormigon" not in modules

    def test_generic_reparacion_and_rehabilitacion_are_not_final_modules(self):
        classifier = HistoricalPartidaClassifier()
        results = classifier.classify_text("Rehabilitacion y reparacion general de edificio")
        modules = [row["module"] for row in results]
        assert "rehabilitacion" not in modules
        assert "reparacion" not in modules

    def test_fachada_classifies_as_real_module(self):
        classifier = HistoricalPartidaClassifier()
        results = classifier.classify_text("Revision fachadas con grieta y fisura")
        modules = [row["module"] for row in results]
        assert "fachada" in modules
