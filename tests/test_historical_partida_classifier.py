"""
Tests del clasificador de partidas históricas.
"""

from src.core.historical_partida_classifier import HistoricalPartidaClassifier
from src.core.historical_partida_features import extract_partida_features


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


class TestReviewedHistoricalCases:
    """Fase 5, Tarea 14: regresiones fijadas tras la revisión humana del
    histórico real (2026-07-22). Casos reales anonimizados/acortados donde
    el clasificador sobreclasificaba por mención incidental."""

    def test_demolition_with_debris_removal_stays_demolicion_not_residuos(self):
        classifier = HistoricalPartidaClassifier()
        classification = classifier.classify(
            {
                "concepto": (
                    "Desmontaje de bajante existente, incluyendo corte, retirada y "
                    "carga manual sobre contenedor de residuos"
                )
            }
        )
        assert classification["primary_module"]["id"] == "demolicion"

    def test_demolition_of_flooring_with_container_transport_stays_demolicion(self):
        classifier = HistoricalPartidaClassifier()
        classification = classifier.classify(
            {
                "concepto": (
                    "Demolicion de pavimento existente con medios manuales, sin "
                    "deteriorar elementos contiguos, y carga sobre contenedor a vertedero"
                )
            }
        )
        assert classification["primary_module"]["id"] == "demolicion"

    def test_pure_debris_transport_without_demolition_verb_stays_gestion_residuos(self):
        """gestion_residuos sigue ganando cuando es el UNICO modulo detectado
        (p.ej. una partida de solo transporte de residuos ya generados)."""
        classifier = HistoricalPartidaClassifier()
        classification = classifier.classify(
            {"concepto": "Transporte de residuos inertes en contenedor a vertedero"}
        )
        assert classification["primary_module"]["id"] == "gestion_residuos"

    def test_protection_during_facade_works_goes_to_medios_auxiliares_not_fachada(self):
        classifier = HistoricalPartidaClassifier()
        classification = classifier.classify(
            {
                "concepto": (
                    "Proteccion de pavimentos y descuelgues. Tapado mediante mantas "
                    "la zona de patio durante la ejecucion de los trabajos en fachada"
                )
            }
        )
        assert classification["primary_module"]["id"] == "medios_auxiliares"

    # Decisiones 3-8, familia demolicion (2026-08-04): ver
    # docs/criterios-clasificacion-partidas.md y
    # docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md.
    # Textos reales del histórico, patrones de mayor frecuencia sin ficha
    # completa (informe de src/core/historical_vocabulary_gap_report.py).

    def test_decision_3_quitar_is_demolish(self):
        classifier = HistoricalPartidaClassifier()
        text = "Quitar puerta de paso y premarco del bano, con retirada a vertedero de escombros con nuestros medios."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.action == "demolish"
        assert features.element == "door"

    def test_decision_4_paramento_vertical_exterior_is_facade_render(self):
        classifier = HistoricalPartidaClassifier()
        text = (
            "Picado de enfoscado de cemento, aplicado sobre paramento vertical "
            "exterior de hasta 3 m de altura, con medios manuales, y carga manual "
            "de escombros sobre camion o contenedor."
        )
        features = extract_partida_features(text, "m2", classifier.classify_text(text))
        assert features.action == "demolish"
        assert features.element == "facade_render"

    def test_decision_5_tabique_is_partition_wall_but_tirar_stays_unmatched(self):
        classifier = HistoricalPartidaClassifier()
        text = "Tirar tabiques existentes de pasillo, cocina, galeria y estudio, con retirada de escombros a contenedor."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.element == "partition_wall"
        assert features.action is None

    def test_decision_6_wc_y_lavabo_is_sanitary_ware(self):
        classifier = HistoricalPartidaClassifier()
        text = "Quitar WC y mueble de lavabo, con retirada a contenedor de escombros."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.action == "demolish"
        assert features.element == "sanitary_ware"

    def test_decision_7_suelo_laminado_is_flooring(self):
        classifier = HistoricalPartidaClassifier()
        text = "QUITAR SUELO LAMINADO. Quitar solado laminado existente en vivienda y rodapie, con retirada de escombros a vertedero."
        features = extract_partida_features(text, "m2", classifier.classify_text(text))
        assert features.action == "demolish"
        assert features.element == "flooring"

    def test_decision_7_entresuelo_is_a_known_accepted_false_positive(self):
        """"suelo" es substring de "entresuelo" (planta/piso, no el elemento
        suelo): 6 lineas reales colisionan frente a 485 aciertos genuinos.
        La Decision 7 acepta ese riesgo medido a proposito (a diferencia de
        "tirar"/"retirar" en la Decision 3, que se descarto) -- este test
        documenta el trade-off aceptado, no lo previene."""
        classifier = HistoricalPartidaClassifier()
        text = "Localizar fuga de agua en vivienda del entresuelo B, comprobando valvula de plato de ducha."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.element == "flooring"

    def test_decision_8_muebles_de_cocina_is_kitchen_furniture(self):
        classifier = HistoricalPartidaClassifier()
        text = "QUITAR MUEBLES DE COCINA. Quitar muebles de cocina existentes, con retirada a vertedero de escombros."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.action == "demolish"
        assert features.element == "kitchen_furniture"

    # Decisiones 9-11, familia alicatado (2026-08-04): ver
    # docs/criterios-clasificacion-partidas.md y
    # docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md.

    def test_decision_9_azulejo_is_tile(self):
        classifier = HistoricalPartidaClassifier()
        text = "Quitar azulejo existente en bano, cocina y galeria, con retirada de escombros a contenedor."
        features = extract_partida_features(text, "m2", classifier.classify_text(text))
        assert features.action == "demolish"
        assert features.element == "tile"

    def test_decision_9_alicatado_word_is_tile(self):
        classifier = HistoricalPartidaClassifier()
        text = "COLOCACION DE ALICATADO. Suministro y colocacion de alicatado en paredes de cocina y galeria, totalmente colocado, junteado y limpio."
        features = extract_partida_features(text, "m2", classifier.classify_text(text))
        assert features.action == "install"
        assert features.element == "tile"

    def test_decision_10_rodapie_is_skirting_not_tile(self):
        classifier = HistoricalPartidaClassifier()
        text = "Demolicion de rodapie ceramico con medios manuales y carga manual de escombros sobre camion o contenedor."
        features = extract_partida_features(text, "ml", classifier.classify_text(text))
        assert features.action == "demolish"
        assert features.element == "skirting"

    def test_decision_11_pavimento_ceramico_is_flooring(self):
        classifier = HistoricalPartidaClassifier()
        text = "DEMOLICION PAVIMENTO CERAMICO. Demolicion de pavimento de baldosas ceramicas con medios manuales y carga manual de escombros sobre camion o contenedor."
        features = extract_partida_features(text, "m2", classifier.classify_text(text))
        assert features.action == "demolish"
        assert features.element == "flooring"
