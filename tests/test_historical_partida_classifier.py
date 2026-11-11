"""
Tests del clasificador de partidas históricas.
"""

import pytest

import src.core.historical_partida_features as hpf
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

    def test_decision_5_tabique_is_partition_wall_and_tirar_is_demolish(self):
        """La Decision 5 dejó "tirar" sin acción por chocar con "retirar";
        la Decision 32 (2026-11-11) lo añade a demolish."""
        classifier = HistoricalPartidaClassifier()
        text = "Tirar tabiques existentes de pasillo, cocina, galeria y estudio, con retirada de escombros a contenedor."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.element == "partition_wall"
        assert features.action == "demolish"

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

    def test_decision_7_entresuelo_is_no_longer_a_false_positive(self):
        """La Decision 7 aceptaba que "suelo" casara dentro de "entresuelo"
        (planta/piso, no el elemento suelo). Desde que los keywords casan solo
        desde inicio de palabra (``keyword_in_text``) ese falso positivo ya no
        se produce."""
        classifier = HistoricalPartidaClassifier()
        text = "Localizar fuga de agua en vivienda del entresuelo B, comprobando valvula de plato de ducha."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.element != "flooring"

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

    # Decisiones 12-15, familia albanileria (2026-08-04): ver
    # docs/criterios-clasificacion-partidas.md y
    # docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md.

    def test_decision_12_yeso_is_plaster(self):
        """El texto real revisado tambien menciona "tabique", que gana la
        primera posicion de _match_first (tabla anterior a plaster) --
        _match_first devuelve partition_wall como elemento primario, pero
        "yeso" si se detecta como segundo elemento real (via _match_all),
        lo que correctamente vuelve compuesta la linea: son dos partidas
        facturables distintas (demoler tabique + remate de yeso), no una."""
        classifier = HistoricalPartidaClassifier()
        text = "REMATES DE YESO EN PAREDES Y TECHOS. Remates de yeso en paredes y techos donde se quitan los tabique o se realiza alguna actuacion."
        features = extract_partida_features(text, "p.a.", classifier.classify_text(text))
        assert features.element == "partition_wall"
        assert "plaster" in hpf._match_all(hpf.normalize_text(text), hpf._ELEMENT_SYNONYMS)
        assert features.line_kind == "composite"

    def test_decision_13_rozas_is_wall_channel(self):
        classifier = HistoricalPartidaClassifier()
        text = "ROZAS EN VIVIENDA PARA INSTAL. ELECTRICIDAD. Abrir rozas y tapar, para nueva instalacion de electricidad."
        features = extract_partida_features(text, "p.a.", classifier.classify_text(text))
        assert features.action == "install"
        assert features.element == "wall_channel"

    def test_decision_14_derribar_is_demolish(self):
        classifier = HistoricalPartidaClassifier()
        text = "REMATE DE YESO EN PAREDES, al derribar tabiques y hacer rozas de electricidad en la vivienda."
        features = extract_partida_features(text, "p.a.", classifier.classify_text(text))
        assert features.action == "demolish"

    def test_decision_15_quitan_conjugated_form_is_demolish(self):
        classifier = HistoricalPartidaClassifier()
        text = "REMATES DE YESO EN PAREDES Y TECHOS. Remates de yeso en paredes y techos donde se quitan los tabique o se realiza alguna actuacion."
        features = extract_partida_features(text, "p.a.", classifier.classify_text(text))
        assert features.action == "demolish"

    # Decisiones 16-20, familia impermeabilizacion (2026-08-04): ver
    # docs/criterios-clasificacion-partidas.md y
    # docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md.

    def test_decision_16_desmontar_is_demolish(self):
        classifier = HistoricalPartidaClassifier()
        text = "SUBIR ENFRIADORA A/A A CUBIERTA. Desmontar enfriadora de Split de Aire Acondicionado de la terraza existente a planta superior de cubierta."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.action == "demolish"

    def test_decision_17_arranque_is_demolish(self):
        classifier = HistoricalPartidaClassifier()
        text = "Arranque de albardilla ceramica para cubricion de muros, con medios manuales, y carga manual de escombros sobre camion o contenedor."
        features = extract_partida_features(text, "ml", classifier.classify_text(text))
        assert features.action == "demolish"
        assert features.element == "coping"

    def test_decision_18_sellado_is_new_seal_action(self):
        """El patron revisado ("SELLADO CON CAUCHO... para su
        impermeabilizacion") tambien menciona "impermeabilizacion", que
        gana por ir antes en la tabla de prioridad -- resultado razonable
        (el sellado se hace CON ese fin). Se prueba "seal" con un ejemplo
        real distinto que no menciona impermeabilizacion, para demostrar
        que la categoria nueva si gana cuando es la unica accion presente."""
        classifier = HistoricalPartidaClassifier()
        text = (
            "Sellado de junta de dilatacion de 15 mm de anchura, en paramento "
            "vertical exterior, con masilla selladora monocomponente de "
            "poliuretano, dureza Shore A aproximada de 25 y alargamiento en "
            "rotura > 500%, aplicada con pistola sobre fondo de junta de 20 mm "
            "de diametro."
        )
        features = extract_partida_features(text, "ml", classifier.classify_text(text))
        assert features.action == "seal"

    def test_decision_20_albardilla_spec_is_coping(self):
        classifier = HistoricalPartidaClassifier()
        text = "Albardilla ceramica para cubricion de muros, en piezas de 40x20x4 cm."
        features = extract_partida_features(text, "ml", classifier.classify_text(text))
        assert features.element == "coping"

    # Decisiones 21-24, familia carpinteria (2026-08-04): ver
    # docs/criterios-clasificacion-partidas.md y
    # docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md.

    def test_decision_21_sustitucion_is_install(self):
        classifier = HistoricalPartidaClassifier()
        text = "SUSTITUCION PUERTA ENTRADA. Suministro y sustitucion de puerta de entrada a zaguan, compuesta de 1 hoja practicable derecha y 1 fijo superior, en aluminio, color LACADO BLANCO."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.action == "install"

    def test_decision_22_mueble_generico_is_furniture(self):
        classifier = HistoricalPartidaClassifier()
        text = "Suministro y colocacion de mueble laminado gris de 0,90x,83x0,54 para descalcificador, formado por modulo y encimera de laminado de madera."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.action == "install"
        assert features.element == "furniture"

    def test_decision_23_barnizado_is_paint(self):
        classifier = HistoricalPartidaClassifier()
        text = "BARNIZADO PASAMANOS ESCALERA MADERA. Barnizado de pasamanos de escalera, en tono nogual brillante."
        features = extract_partida_features(text, "ml", classifier.classify_text(text))
        assert features.action == "paint"
        assert features.element == "railing"

    def test_decision_24_maestreado_y_enlucido_is_render(self):
        classifier = HistoricalPartidaClassifier()
        text = "Maestreado y enlucido en liso, las paredes de la cocina, estudio y pasillo hasta puerta existente."
        features = extract_partida_features(text, "m2", classifier.classify_text(text))
        assert features.action == "render"

    # Decisiones 25-26, familia cerrajeria (2026-08-04): ver
    # docs/criterios-clasificacion-partidas.md y
    # docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md.

    def test_decision_25_fregadero_is_sink(self):
        classifier = HistoricalPartidaClassifier()
        text = "Suministro y colocacion de fregadero de cocina en acero inox. Modelo BERLIN PLUS 55 B/E y grifo de cocina IMEX CAPRI MNM FREGADERO OSMOSIS CROMO."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.action == "install"
        assert features.element == "sink"

    def test_decision_26_imprimacion_is_paint(self):
        classifier = HistoricalPartidaClassifier()
        text = "Tratamiento superficial de proteccion anticorrosiva para elementos de acero mediante imprimacion anticorrosiva a base de resina epoxi y fosfato de zinc, aplicada en dos manos."
        features = extract_partida_features(text, "m2", classifier.classify_text(text))
        assert features.action == "paint"

    # Decisiones 27-29, familia sustitucion_bajante (2026-08-04): ver
    # docs/criterios-clasificacion-partidas.md y
    # docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md.

    def test_decision_27_rejilla_y_cazoleta_is_drain_fitting(self):
        classifier = HistoricalPartidaClassifier()
        text = "EMBOCAR REJILLAS A DESAGUES EXISTENTES. Sellado con producto especifico entre rejilla y cazoleta. Sellado de refuerzo de laterales y base de cazoleta con sellante para PVC/ABS."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.action == "seal"
        assert features.element == "drain_fitting"

    def test_decision_28_manguito_is_pipe_fitting(self):
        classifier = HistoricalPartidaClassifier()
        text = "MANGUITO UNION 90MM. Suministro y colocacion de manguito de union de PVC Serie B de 90 mm de diametro. Incluye union y material auxiliar."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.action == "install"
        assert features.element == "pipe_fitting"

    def test_decision_28_codo_is_pipe_fitting(self):
        classifier = HistoricalPartidaClassifier()
        text = "CODO PVC 45 90MM. Suministro y colocacion de codo de PVC Serie B de 45 grados y 90 mm de diametro. Incluye union y material auxiliar."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.action == "install"
        assert features.element == "pipe_fitting"

    def test_decision_29_bomba_is_pump(self):
        classifier = HistoricalPartidaClassifier()
        text = "BOMBAS AGUAS SUCIAS Y CONDUCCION P.V.C. Suministro e instalacion de bomba de achique de aguas sucias y nueva instalacion de tuberia de PVC., incluidas piezas de conexiones."
        features = extract_partida_features(text, "ud", classifier.classify_text(text))
        assert features.action == "install"
        assert features.element == "pump"


def test_keyword_no_casa_a_mitad_de_palabra():
    """Regresión: "atado" (estructura) aparecía dentro de "alicatado"."""
    from src.core.historical_partida_classifier import HistoricalPartidaClassifier

    modules = [r["module"] for r in HistoricalPartidaClassifier().classify_text(
        "Alicatado de baño con azulejo"
    )]
    assert modules == ["alicatado"]


def test_keyword_raiz_sigue_casando_al_inicio_de_palabra():
    from src.core.work_type_normalizer import keyword_in_text

    assert keyword_in_text("impermeabiliz", "impermeabilizacion de cubierta")
    assert keyword_in_text("atado", "atado de armaduras")
    assert not keyword_in_text("atado", "alicatado de bano")


class TestDecisionesNoviembre2026:
    """Decisiones 30-37 (2026-11-11), probadas con texto real del histórico."""

    @staticmethod
    def _features(text, unit="ud"):
        classifier = HistoricalPartidaClassifier()
        return extract_partida_features(text, unit, classifier.classify_text(text))

    def test_decision_30_reposicion_es_reparacion(self):
        assert self._features("Reposición de gresite desprendido", "m2").action == "repair"

    @pytest.mark.parametrize("text", [
        "TABIQUE CERÁMICO H-7. Suministro y formación de nuevo tabique cerámico H-7",
        "FORMACIÓN DE BASE DE MOSTRADOR DE PLADUR. Formación de base para mostrador con doble tabique de pladur",
        "Formación de pendientes en interior de jardinera, de mortero M-10 de 4 cm de espesor",
    ])
    def test_decision_31_formacion_de_es_build(self, text):
        assert self._features(text).action == "build"

    def test_decision_31_formacion_del_personal_no_es_build(self):
        text = ("Formación del personal, necesaria para el cumplimiento de la normativa "
                "vigente en materia de Seguridad y Salud en el Trabajo.")
        assert self._features(text).action != "build"

    def test_decision_31_build_no_pisa_otra_accion(self):
        text = "Formación de pendientes e impermeabilización de cubierta con lámina asfáltica"
        assert self._features(text, "m2").action == "waterproof"

    @pytest.mark.parametrize("text", [
        "Tirar tabiques existentes de pasillo, cocina, galeria y estudio, con retirada de escombros a contenedor.",
        "Tirar techo de escayola, con retirada de escombros a contenedor.",
    ])
    def test_decision_32_tirar_es_demolish(self, text):
        assert self._features(text).action == "demolish"

    def test_decision_32_retirar_no_es_tirar(self):
        assert self._features("Retirada de escombros a vertedero autorizado").action != "demolish"

    def test_decision_33_repaso_es_repair(self):
        assert self._features("Repaso de grietas y saneado de la escalera.").action == "repair"

    def test_decision_33_saneado_en_pintura_no_vuelve_compuesta_la_partida(self):
        text = ("PINTAR PUERTAS DE ASCENSOR. Saneado, rascado y lijado de puertas de ascensor, "
                "aplicación de pintura epoxi anticorrosión y acabado con dos manos de esmalte")
        features = self._features(text)
        assert features.action == "paint"
        assert features.line_kind != "composite"

    def test_decision_31_formacion_no_vuelve_compuesta_una_partida_con_otra_accion(self):
        text = ("Demolición de pavimento exterior de baldosas y/o losetas de hormigón y formación "
                "de pendientes, con martillo neumático y carga manual sobre camión o contenedor")
        features = self._features(text, "m2")
        assert features.action == "demolish"
        assert features.line_kind != "composite"

    @staticmethod
    def _modules(text):
        return [r["module"] for r in HistoricalPartidaClassifier().classify_text(text)]

    @pytest.mark.parametrize("text", [
        "PINTURA PUERTA VEHÍCULOS GARAJE. Lijado superficial de puerta de vehículos, aplicación de imprimación",
        "PUERTA CORTAFUEGOS EN PARKING. Suministro y colocación de puerta cortafuegos en entrada a parking.",
    ])
    def test_decision_34_garaje_y_parking_no_son_estructura(self, text):
        assert "estructura" not in self._modules(text)

    @pytest.mark.parametrize("text", [
        "PINTURA SILICATO. Aplicación manual de dos manos de pintura al silicato, color blanco, sobre hormigón",
        "REFUERZO EN REJILLA SUELTA AL FINAL DE RAMPA. Picar las garras sueltas del marco de las rejillas",
        "CALDERETA SIFÓNICA PVC. Picar en el forjado para abrir hueco y posterior colocación de caldereta.",
    ])
    def test_decision_35_una_sola_senal_debil_no_es_estructura(self, text):
        assert "estructura" not in self._modules(text)

    @pytest.mark.parametrize("text", [
        "Reparación de frente de forjado de hormigón armado, de canto 30 cm, mediante picado del hormigón deteriorado",
        "CANTO DE FORJADO 1º PISO Y BAJO BALCÓN. Picar frente de forjado en 1º piso hasta llegar a las armaduras",
    ])
    def test_decision_35_dos_senales_debiles_si_son_estructura(self, text):
        assert "estructura" in self._modules(text)

    def test_decision_36_plurales_no_cuentan_doble(self):
        classifier = HistoricalPartidaClassifier()
        singular = {r["module"]: r["confidence"] for r in classifier.classify_text("Refuerzo de viga")}
        plural = {r["module"]: r["confidence"] for r in classifier.classify_text("Refuerzo de vigas")}
        assert plural["estructura"] == singular["estructura"]

    def test_decision_37_entrevigado_es_estructura(self):
        assert "estructura" in self._modules("Relleno de entrevigado con hormigón")
