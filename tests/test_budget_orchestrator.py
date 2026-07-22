"""
Tests de contrato para BudgetOrchestrator (H1.1 / H1.4): procedencia unificada
y los escenarios obligatorios del flujo IA local (histórico, cobertura parcial,
fallback completo, sin API key, errores inesperados, mezcla y duplicados).

Ningún adapter real (ni histórico en BDD, ni proveedor IA, ni red, ni sleeps):
se sustituyen los dos colaboradores del orquestador por dobles deterministas.
"""

from src.core.budget_orchestrator import BudgetOrchestrator
from src.core.partida_normalizer import normalize_partida_for_excel


class _FakeSuggestionService:
    def __init__(
        self,
        partidas=None,
        detected_modules=None,
        confidence=0.8,
        failure_reason="OK",
        raises=None,
        evidence_report=None,
    ):
        self._partidas = partidas or []
        self._detected_modules = detected_modules or []
        self._confidence = confidence
        self._failure_reason = failure_reason
        self._raises = raises
        self._evidence_report = evidence_report if evidence_report is not None else []
        self.calls = 0

    def suggest_for_project(self, project_data, user_description=""):
        self.calls += 1
        if self._raises:
            raise self._raises
        return {
            "partidas": self._partidas,
            "detected_modules": self._detected_modules,
            "confidence": self._confidence,
            "failure_reason": self._failure_reason,
            "evidence_report": self._evidence_report,
        }


class _FakeGenerator:
    def __init__(self, gap_result=None, full_result=None, raises=None):
        self._gap_result = gap_result if gap_result is not None else {"partidas": [], "error": None}
        self._full_result = full_result if full_result is not None else {"partidas": [], "error": None}
        self._raises = raises
        self.calls = []

    def generate_for_gap_modules(self, **kwargs):
        self.calls.append(("gap", kwargs))
        if self._raises:
            raise self._raises
        return self._gap_result

    def generate(self, **kwargs):
        self.calls.append(("full", kwargs))
        if self._raises:
            raise self._raises
        return self._full_result


def _make_orchestrator(suggestion_service, generator):
    orch = BudgetOrchestrator.__new__(BudgetOrchestrator)
    orch._settings = None
    orch._suggestion_service = suggestion_service
    orch._generator = generator
    return orch


def _historical_partida(module="sustitucion_bajante", confidence=0.9, frequency=5):
    return {
        "titulo": "Sustitucion bajante",
        "concepto": "sustitucion bajante",
        "unidad": "ml",
        "precio_unitario": 20.0,
        "confidence": confidence,
        "historical_frequency": frequency,
        "module": module,
    }


# 1. Histórico cubre todos los módulos: cero llamadas al proveedor IA.
def test_full_historical_coverage_makes_zero_ai_calls():
    suggestion_service = _FakeSuggestionService(
        partidas=[_historical_partida()],
        detected_modules=[{"name": "sustitucion_bajante", "confidence": 0.9}],
    )
    generator = _FakeGenerator()
    orch = _make_orchestrator(suggestion_service, generator)

    result = orch.generate("Sustituir bajante")

    assert generator.calls == []
    assert result["source"] == "historico"
    assert [p["source"] for p in result["partidas"]] == ["historical"]


# 2. Cobertura parcial: IA recibe solo los módulos gap, no los ya cubiertos.
def test_partial_coverage_sends_only_gap_modules_to_ai():
    suggestion_service = _FakeSuggestionService(
        partidas=[_historical_partida(module="sustitucion_bajante")],
        detected_modules=[
            {"name": "sustitucion_bajante", "confidence": 0.9},
            {"name": "pintura", "confidence": 0.7},
        ],
    )
    generator = _FakeGenerator(
        gap_result={"partidas": [{"titulo": "Pintura fachada", "unidad": "m2", "precio_unitario": 12.0}], "error": None}
    )
    orch = _make_orchestrator(suggestion_service, generator)

    result = orch.generate("Sustituir bajante y pintar fachada")

    assert len(generator.calls) == 1
    kind, kwargs = generator.calls[0]
    assert kind == "gap"
    assert kwargs["gap_modules"] == ["pintura"]

    sources = {p["source"] for p in result["partidas"]}
    assert sources == {"historical", "ai_completion"}
    assert result["source"] == "orquestado"


# 3. Sin módulos ni histórico: fallback completo (generate(), no generate_for_gap_modules()).
def test_no_modules_and_no_historical_triggers_full_fallback():
    suggestion_service = _FakeSuggestionService(partidas=[], detected_modules=[])
    generator = _FakeGenerator(
        full_result={"partidas": [{"titulo": "Estimacion generica", "unidad": "ud", "precio_unitario": 50.0}], "error": None}
    )
    orch = _make_orchestrator(suggestion_service, generator)

    result = orch.generate("Obra sin descripcion clara")

    assert [kind for kind, _ in generator.calls] == ["full"]
    assert result["source"] == "ia"
    assert result["partidas"][0]["source"] == "ai_completion"


# 4. Sin API key: resultado incompleto y error accionable, no excepcion sin tratar.
def test_missing_api_key_returns_actionable_error_without_raising():
    suggestion_service = _FakeSuggestionService(partidas=[], detected_modules=[])
    generator = _FakeGenerator(
        full_result={"partidas": [], "error": "No hay API key configurada.", "source": "error"}
    )
    orch = _make_orchestrator(suggestion_service, generator)

    result = orch.generate("Obra sin descripcion clara")

    assert result["partidas"] == []
    assert result["source"] == "error"
    assert result["error"] == "No hay API key configurada."


# 5a. Error de BDD (excepcion sin tratar del servicio historico) no se propaga.
def test_suggestion_service_exception_is_contained_as_error_result():
    suggestion_service = _FakeSuggestionService(raises=RuntimeError("BDD bloqueada"))
    generator = _FakeGenerator()
    orch = _make_orchestrator(suggestion_service, generator)

    result = orch.generate("Sustituir bajante")

    assert result["source"] == "error"
    assert result["partidas"] == []
    assert "BDD bloqueada" in result["error"]
    assert result["cobertura"]["failure_reason"] == "UNEXPECTED_ERROR"


# 5b. Error del proveedor IA (excepcion sin tratar del generador) no se propaga.
def test_generator_exception_is_contained_as_error_result():
    suggestion_service = _FakeSuggestionService(partidas=[], detected_modules=[])
    generator = _FakeGenerator(raises=RuntimeError("Proveedor IA caido"))
    orch = _make_orchestrator(suggestion_service, generator)

    result = orch.generate("Obra sin descripcion clara")

    assert result["source"] == "error"
    assert result["partidas"] == []
    assert "Proveedor IA caido" in result["error"]


# 6. Respuesta IA invalida (sin clave 'partidas') no rompe el merge.
def test_malformed_ai_response_without_partidas_key_does_not_crash():
    suggestion_service = _FakeSuggestionService(
        partidas=[_historical_partida(module="sustitucion_bajante")],
        detected_modules=[
            {"name": "sustitucion_bajante", "confidence": 0.9},
            {"name": "pintura", "confidence": 0.7},
        ],
    )
    generator = _FakeGenerator(gap_result={"error": "JSON invalido"})
    orch = _make_orchestrator(suggestion_service, generator)

    result = orch.generate("Sustituir bajante y pintar fachada")

    assert [p["source"] for p in result["partidas"]] == ["historical"]
    assert result["source"] == "historico"


# 7 y 8. Mezcla con duplicado historico/IA: el orquestador no deduplica (eso
# corresponde al seam de revision, H1.2); procedencia y confianza sobreviven.
def test_mixed_coverage_tags_source_per_partida_and_survives_excel_normalization():
    historical_partidas = [_historical_partida(module="sustitucion_bajante")]
    detected_modules = [
        {"name": "sustitucion_bajante", "confidence": 0.9},
        {"name": "pintura", "confidence": 0.7},
    ]
    ia_partidas = [
        {
            "titulo": "Sustitucion bajante",
            "concepto": "sustitucion bajante",
            "unidad": "ml",
            "precio_unitario": 21.0,
        }
    ]
    suggestion_service = _FakeSuggestionService(partidas=historical_partidas, detected_modules=detected_modules)
    generator = _FakeGenerator(gap_result={"partidas": ia_partidas, "error": None})
    orch = _make_orchestrator(suggestion_service, generator)

    result = orch.generate("Sustituir bajante y pintar fachada")

    assert result["source"] == "orquestado"
    partidas = result["partidas"]
    assert len(partidas) == 2  # el duplicado conceptual no se elimina aqui

    sources = {p["source"] for p in partidas}
    assert sources == {"historical", "ai_completion"}
    assert "fuente" not in partidas[0] and "fuente" not in partidas[1]

    historical = next(p for p in partidas if p["source"] == "historical")
    assert historical["confidence"] == 0.9
    assert historical["historical_frequency"] == 5
    assert historical["module"] == "sustitucion_bajante"

    for p in partidas:
        normalized = normalize_partida_for_excel(p, source=p.get("source"))
        assert normalized["source"] != "unknown"
        assert normalized["source"] == p["source"]


# Fase 4, Tarea 11 (alcance reducido): la trazabilidad de evidencia calculada
# por el comparador (Tarea 8/10) llega hasta el resultado del orquestador, en
# vez de perderse al usar solo el filtro de confianza/frecuencia agregado.
def test_evidence_report_from_suggestion_service_is_passed_through():
    evidence = [
        {"level": "exact", "precio_unitario": 20.0, "partida_id": 1},
        {"level": "related", "precio_unitario": 999.0, "partida_id": 2},
    ]
    suggestion_service = _FakeSuggestionService(
        partidas=[_historical_partida()],
        detected_modules=[{"name": "sustitucion_bajante", "confidence": 0.9}],
        evidence_report=evidence,
    )
    orch = _make_orchestrator(suggestion_service, _FakeGenerator())

    result = orch.generate("Sustituir bajante")

    assert result["evidence_report"] == evidence


def test_evidence_report_defaults_to_empty_list_when_suggestion_service_omits_it():
    class _BareSuggestionService:
        def suggest_for_project(self, project_data, user_description=""):
            return {"partidas": [], "detected_modules": [], "confidence": 0.0, "failure_reason": "OK"}

    orch = _make_orchestrator(_BareSuggestionService(), _FakeGenerator())
    result = orch.generate("Obra sin descripcion")
    assert result["evidence_report"] == []


def test_only_historical_coverage_reports_historical_source():
    orch = _make_orchestrator(
        _FakeSuggestionService(
            partidas=[_historical_partida()],
            detected_modules=[{"name": "sustitucion_bajante", "confidence": 0.9}],
        ),
        _FakeGenerator(),
    )
    result = orch.generate("Sustituir bajante")

    assert result["source"] == "historico"
    partidas = result["partidas"]
    assert len(partidas) == 1
    assert partidas[0]["source"] == "historical"
