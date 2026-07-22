"""
Fase 6, Tarea 15: prueba de extremo a extremo del hito completo.

Flujo real (adaptado al API que existe hoy, no al aspiracional del plan:
BudgetOrchestrator no tiene create_draft/finalize_draft ni GeneratedBudget,
ver nota de alcance de la Tarea 11):

    Excel analizado (VALID) -> aprobacion humana explicita (Tarea 4/11)
    -> ficha derivada (Tarea 7) -> patrones (Tarea 9)
    -> BudgetOrchestrator.generate() consulta el historico (Tarea 10)
    -> evidence_report contiene el nivel exact para la linea aprobada
    -> ninguna llamada a generate() aprende nada automaticamente
       (ni de la partida IA, ni de nada: no hay ninguna llamada a
       HistoricalBudgetAnalyzer/rebuild_patterns dentro del orquestador).
"""

from datetime import datetime

from src.core import database
from src.core.budget_orchestrator import BudgetOrchestrator
from src.core.historical_budget_analyzer import HistoricalBudgetAnalyzer
from src.core.historical_pattern_builder import HistoricalPatternBuilder
from src.core.historical_suggestion_service import HistoricalSuggestionService
from src.core.repositories import (
    approve_budget_for_learning,
    get_or_create_execution_module,
    insert_historical_partida,
    upsert_historical_budget,
)


class _FakeGenerator:
    """Sustituye a BudgetGenerator (IA real): sin red, sin API key."""

    def generate_for_gap_modules(self, **kwargs):
        return {
            "partidas": [
                {"titulo": "Estimacion IA", "unidad": "ud", "precio_unitario": 999.0}
            ],
            "error": None,
        }

    def generate(self, **kwargs):
        return self.generate_for_gap_modules(**kwargs)


def _import_and_approve_atomic_facade_budget(tmp_path) -> int:
    """Simula un Excel histórico ya analizado (Tarea 2/3/4) con una única
    línea atómica de fachada, y su aprobación humana explícita (Tarea 11)."""
    budget_id, err = upsert_historical_budget(
        {
            "ruta_excel": str(tmp_path / "historico_fachada.xlsx"),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": "historico_fachada.xlsx",
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "analysis_status": "VALID",
            "learning_status": "PENDING_REVIEW",
            "source_kind": "external_excel",
        }
    )
    assert err is None

    partida_id, perr = insert_historical_partida(
        budget_id,
        {
            "concepto_original": "Reparacion de fachada con grieta",
            "concepto_normalizado": "reparacion de fachada con grieta",
            "unidad": "m2",
            "precio_unitario": 50.0,
            "cantidad": 1,
            "total_linea": 50.0,
        },
    )
    assert perr is None
    module_id, module_err = get_or_create_execution_module("fachada")
    assert module_err is None

    # Sin aprobacion explicita, un VALID no basta para entrar en memoria
    # (Tarea 4): lo confirmamos antes de aprobar.
    with database.get_connection(read_only=True) as conn:
        status_before = conn.execute(
            "SELECT learning_status FROM historical_budget WHERE id=?", (budget_id,)
        ).fetchone()[0]
    assert status_before == "PENDING_REVIEW"

    approve_err = approve_budget_for_learning(budget_id, "SERGIO")
    assert approve_err is None

    HistoricalBudgetAnalyzer().rebuild_partida_features([budget_id])
    HistoricalPatternBuilder().rebuild_patterns()

    return budget_id, module_id, partida_id


def test_approved_atomic_history_prices_a_matching_draft_but_nothing_is_auto_learned(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "e2e.db"))

    history_budget_id, _module_id, _partida_id = _import_and_approve_atomic_facade_budget(tmp_path)

    with database.get_connection(read_only=True) as conn:
        historical_budgets_before = conn.execute(
            "SELECT COUNT(*) FROM historical_budget"
        ).fetchone()[0]

    orchestrator = BudgetOrchestrator.__new__(BudgetOrchestrator)
    orchestrator._settings = None
    orchestrator._suggestion_service = HistoricalSuggestionService()
    orchestrator._generator = _FakeGenerator()

    result = orchestrator.generate("Reparacion de fachada con grieta")

    # La evidencia por linea (Tarea 10) encuentra la partida aprobada como
    # coincidencia exacta, con trazabilidad hasta el presupuesto fuente.
    assert result["evidence_report"], "debe encontrar evidencia para una descripcion identica a la aprobada"
    exact_matches = [e for e in result["evidence_report"] if e["level"] == "exact"]
    assert exact_matches, "la partida aprobada debe aparecer como evidencia exacta"
    assert exact_matches[0]["historical_budget_id"] == history_budget_id
    assert exact_matches[0]["precio_unitario"] == 50.0

    # generate() puede seguir completando con IA los modulos sin patron con
    # frecuencia suficiente (Task 9 exige frecuencia>=2 para 'partidas'; una
    # sola fuente aprobada no basta) -- eso es esperado, no un fallo: el
    # punto de esta prueba es que la llamada a generate() en si misma nunca
    # aprende nada, tenga o no partidas de IA en el resultado.
    generate_partida_sources = {p.get("source") for p in result["partidas"]}
    assert generate_partida_sources.issubset(
        {"historical_exact", "historical_comparable", "ai_completion"}
    )

    with database.get_connection(read_only=True) as conn:
        historical_budgets_after_one_call = conn.execute(
            "SELECT COUNT(*) FROM historical_budget"
        ).fetchone()[0]
    assert historical_budgets_after_one_call == historical_budgets_before

    # Repetir la generacion varias veces (como si el usuario pidiera varios
    # borradores) tampoco debe crear presupuestos historicos nuevos: no hay
    # ninguna ruta de aprendizaje automatico dentro de BudgetOrchestrator.
    for _ in range(3):
        orchestrator.generate("Reparacion de fachada con grieta")

    with database.get_connection(read_only=True) as conn:
        historical_budgets_after_repeated_calls = conn.execute(
            "SELECT COUNT(*) FROM historical_budget"
        ).fetchone()[0]
        pending_review_count = conn.execute(
            "SELECT COUNT(*) FROM historical_budget WHERE learning_status='PENDING_REVIEW'"
        ).fetchone()[0]
        included_count = conn.execute(
            "SELECT COUNT(*) FROM historical_budget WHERE learning_status='INCLUDED'"
        ).fetchone()[0]

    assert historical_budgets_after_repeated_calls == historical_budgets_before
    assert pending_review_count == 0
    assert included_count == 1


def test_no_private_evidence_is_clearly_reported_as_such(tmp_path, monkeypatch):
    """Sin ningun historico aprobado, evidence_report debe quedar vacio (no
    inventar evidencia), no fallar ni devolver falsos positivos."""
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "e2e_sin_evidencia.db"))

    orchestrator = BudgetOrchestrator.__new__(BudgetOrchestrator)
    orchestrator._settings = None
    orchestrator._suggestion_service = HistoricalSuggestionService()
    orchestrator._generator = _FakeGenerator()

    result = orchestrator.generate("Sustitucion completa de tejado de pizarra")

    assert result["evidence_report"] == []
    assert result["source"] in {"ia", "orquestado"}
