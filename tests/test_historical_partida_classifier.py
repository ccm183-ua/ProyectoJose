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
        classification = classifier.classify(partida)
        assert classification["primary_module"]["id"] == "sustitucion_bajante"

    def test_classify_partida_multiple_modules(self):
        classifier = HistoricalPartidaClassifier()
        partida = {
            "titulo": "Apertura y cierre de rozas para sustitucion de bajante",
            "descripcion": "Demolicion de revestimiento, mortero y PVC",
        }
        classification = classifier.classify(partida)
        all_ids = {classification["primary_module"]["id"]} | {
            m["id"] for m in classification["secondary_modules"]
        }
        assert "demolicion" in all_ids
        assert "albanileria" in all_ids
        assert "sustitucion_bajante" in all_ids

    def test_classify_partida_never_repeats_primary_in_secondary(self):
        classifier = HistoricalPartidaClassifier()
        partida = {
            "titulo": "Apertura y cierre de rozas para sustitucion de bajante",
            "descripcion": "Demolicion de revestimiento, mortero y PVC",
        }
        classification = classifier.classify(partida)
        secondary_ids = {m["id"] for m in classification["secondary_modules"]}
        assert classification["primary_module"]["id"] not in secondary_ids

    def test_classify_partida_with_no_match_has_no_primary(self):
        classifier = HistoricalPartidaClassifier()
        classification = classifier.classify({"titulo": "Sin ninguna palabra clave reconocible"})
        assert classification["primary_module"] is None
        assert classification["secondary_modules"] == []
        assert classification["confidence"] == 0.0

    def test_seven_module_composite_line_picks_single_primary(self):
        """Regresion del caso real auditado: una reparacion de fachada compuesta
        (picado, mortero, medios auxiliares...) llegaba a alimentar 7 modulos de
        precio distintos. classify() debe elegir un unico primary_module."""
        classifier = HistoricalPartidaClassifier()
        composite_text = (
            "Picado y reparacion de fachada con grieta y fisura, enfoscado con "
            "mortero, refuerzo de estructura con viga, impermeabilizacion de "
            "cubierta con gotera, bajante con manguito, alquiler de andamio con "
            "plataforma elevadora"
        )
        classification = classifier.classify({"concepto": composite_text})
        assert classification["primary_module"]["id"] == "fachada"
        assert len(classification["secondary_modules"]) == 6
        secondary_ids = {m["id"] for m in classification["secondary_modules"]}
        assert classification["primary_module"]["id"] not in secondary_ids

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
