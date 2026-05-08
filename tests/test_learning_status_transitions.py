from datetime import datetime

from src.core.repositories import (
    get_historical_budget_by_path,
    set_historical_budget_learning_status,
    upsert_historical_budget,
)


def _create_pending_budget(tmp_path):
    budget_path = tmp_path / "pending_review.xlsx"
    budget_id, err = upsert_historical_budget(
        {
            "ruta_excel": str(budget_path),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": "pending_review.xlsx",
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "analisis_ok": True,
            "analysis_status": "VALID_WITH_WARNINGS",
            "usable_for_learning": False,
            "learning_status": "PENDING_REVIEW",
            "learning_status_source": "AUTO",
            "learning_decision_reason": "Requiere revision manual por avisos.",
            "learning_decision_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    assert err is None
    assert budget_id is not None
    return str(budget_path), int(budget_id)


def test_pending_review_can_be_excluded_without_changing_analysis_status(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_learning_transition_excl.db"))
    path, budget_id = _create_pending_budget(tmp_path)

    err = set_historical_budget_learning_status(
        budget_id,
        "EXCLUDED",
        False,
        decision_source="MANUAL",
        decision_reason="Excluido desde revision",
    )
    assert err is None

    row = get_historical_budget_by_path(path)
    assert row is not None
    assert row["analysis_status"] == "VALID_WITH_WARNINGS"
    assert row["learning_status"] == "EXCLUDED"
    assert row["usable_for_learning"] is False


def test_pending_review_can_be_included_without_changing_analysis_status(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_learning_transition_incl.db"))
    path, budget_id = _create_pending_budget(tmp_path)

    err = set_historical_budget_learning_status(
        budget_id,
        "INCLUDED",
        True,
        decision_source="MANUAL",
        decision_reason="Incluido desde revision",
    )
    assert err is None

    row = get_historical_budget_by_path(path)
    assert row is not None
    assert row["analysis_status"] == "VALID_WITH_WARNINGS"
    assert row["learning_status"] == "INCLUDED"
    assert row["usable_for_learning"] is True
