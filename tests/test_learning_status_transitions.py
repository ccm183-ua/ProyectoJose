from datetime import datetime

from src.core import database
from src.core.historical_budget_analyzer import _apply_existing_manual_learning_decision
from src.core.repositories import (
    approve_budget_for_learning,
    get_historical_budget_by_path,
    set_historical_budget_learning_status,
    set_historical_budget_manual_status,
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
            "file_sha256": "hash_pending_review",
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


def test_pending_review_inclusion_only_through_explicit_approval(tmp_path, monkeypatch):
    """H06: el escritor genérico no puede incluir; la aprobación explícita sí,
    y deja actor, fecha y hash ligados a la versión revisada."""
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_learning_transition_incl.db"))
    path, budget_id = _create_pending_budget(tmp_path)

    err = set_historical_budget_learning_status(
        budget_id,
        "INCLUDED",
        True,
        decision_source="MANUAL",
        decision_reason="Intento de inclusion sin aprobacion",
    )
    assert err is not None
    assert "approve_budget_for_learning" in err

    row = get_historical_budget_by_path(path)
    assert row is not None
    assert row["learning_status"] == "PENDING_REVIEW"
    assert row["usable_for_learning"] is False
    assert not (row.get("approved_by") or "").strip()
    assert not (row.get("approved_at") or "").strip()

    err = approve_budget_for_learning(budget_id, "SERGIO")
    assert err is None

    row = get_historical_budget_by_path(path)
    assert row is not None
    assert row["analysis_status"] == "VALID_WITH_WARNINGS"
    assert row["learning_status"] == "INCLUDED"
    assert row["usable_for_learning"] is True
    assert row["approved_by"] == "SERGIO"
    assert (row["approved_at"] or "").strip()
    assert (row["file_sha256"] or "").strip()


def test_repository_rejects_including_technically_invalid_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_learning_invalid_include.db"))
    budget_path = tmp_path / "invalid.xlsx"
    budget_id, err = upsert_historical_budget(
        {
            "ruta_excel": str(budget_path),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": "invalid.xlsx",
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "analisis_ok": True,
            "analysis_status": "EXCLUDED_INCOMPLETE_DATA",
            "usable_for_learning": False,
            "learning_status": "NOT_ELIGIBLE",
            "learning_status_source": "AUTO",
        }
    )
    assert err is None
    assert budget_id is not None

    err = set_historical_budget_learning_status(
        int(budget_id),
        "INCLUDED",
        True,
        decision_source="MANUAL",
        decision_reason="Intento directo no permitido",
    )

    assert err is not None
    assert "approve_budget_for_learning" in err
    row = get_historical_budget_by_path(str(budget_path))
    assert row is not None
    assert row["learning_status"] == "NOT_ELIGIBLE"
    assert row["usable_for_learning"] is False


def _assert_no_unproven_inclusion():
    with database.get_connection(read_only=True) as conn:
        bad = conn.execute(
            """SELECT id, approved_by, approved_at, file_sha256
               FROM historical_budget
               WHERE (learning_status='INCLUDED' OR usable_for_learning=1)
                 AND (COALESCE(approved_by, '')=''
                      OR COALESCE(approved_at, '')=''
                      OR COALESCE(file_sha256, '')='')"""
        ).fetchall()
    assert bad == []


def test_no_exported_route_persists_reusable_inclusion_without_proof(tmp_path, monkeypatch):
    """H06: ninguna ruta exportada puede dejar una fila reutilizable sin
    actor, fecha ni hash de contenido revisado."""
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_learning_invariant.db"))
    path, budget_id = _create_pending_budget(tmp_path)
    _assert_no_unproven_inclusion()

    assert set_historical_budget_learning_status(budget_id, "INCLUDED", True) is not None
    assert set_historical_budget_learning_status(budget_id, "EXCLUDED", True) is not None
    assert set_historical_budget_manual_status(budget_id, "VALID", True) is not None
    assert upsert_historical_budget(
        {
            "ruta_excel": str(tmp_path / "inclusion_sin_prueba.xlsx"),
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "analysis_status": "VALID",
            "usable_for_learning": True,
            "learning_status": "INCLUDED",
            "learning_status_source": "MANUAL",
        }
    )[1] is not None
    _assert_no_unproven_inclusion()

    assert approve_budget_for_learning(budget_id, "SERGIO") is None
    row = get_historical_budget_by_path(path)
    assert (row["approved_by"] or "").strip()
    assert (row["approved_at"] or "").strip()
    assert (row["file_sha256"] or "").strip()
    _assert_no_unproven_inclusion()


def test_upsert_rejects_reusable_inclusion_without_approval_proof(tmp_path, monkeypatch):
    """H06: el escritor genérico no admite una fila reutilizable sin actor,
    fecha y hash de contenido revisado."""
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_learning_upsert_invariant.db"))
    path, existing_id = _create_pending_budget(tmp_path)

    budget_id, err = upsert_historical_budget(
        {
            "ruta_excel": str(tmp_path / "sin_prueba.xlsx"),
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "analysis_status": "VALID",
            "usable_for_learning": True,
            "learning_status": "INCLUDED",
            "learning_status_source": "MANUAL",
            "file_sha256": "hash_sin_actor_ni_fecha",
        }
    )
    assert err is not None
    assert budget_id is None
    _assert_no_unproven_inclusion()

    _, err = upsert_historical_budget(
        {
            "ruta_excel": path,
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "analysis_status": "VALID",
            "usable_for_learning": True,
            "learning_status": "INCLUDED",
            "learning_status_source": "MANUAL",
            "approved_by": "SERGIO",
            "approved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file_sha256": "",
        }
    )
    assert err is not None
    row = get_historical_budget_by_path(path)
    assert row is not None
    assert row["learning_status"] == "PENDING_REVIEW"
    assert row["usable_for_learning"] is False
    assert existing_id
    _assert_no_unproven_inclusion()


def test_manual_status_writer_cannot_grant_reusable_inclusion(tmp_path, monkeypatch):
    """H06: el escritor de estado manual solo alcanza estados no
    reutilizables; incluir exige approve_budget_for_learning."""
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_learning_manual_status.db"))
    path, budget_id = _create_pending_budget(tmp_path)

    err = set_historical_budget_manual_status(budget_id, "VALID", True)
    assert err is not None
    row = get_historical_budget_by_path(path)
    assert row is not None
    assert row["usable_for_learning"] is False
    _assert_no_unproven_inclusion()

    assert set_historical_budget_manual_status(budget_id, "VALID", False) is None
    row = get_historical_budget_by_path(path)
    assert row is not None
    assert row["analysis_status"] == "VALID"
    assert row["usable_for_learning"] is False


def test_reentry_requires_approval_proof_before_keeping_inclusion(tmp_path, monkeypatch):
    """H06: reanalizar no puede heredar una inclusión sin actor ni fecha; con
    la aprobación sellada, sí la conserva."""
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_learning_reentry.db"))
    path, budget_id = _create_pending_budget(tmp_path)
    assert approve_budget_for_learning(budget_id, "SERGIO") is None
    approved = get_historical_budget_by_path(path)
    assert approved is not None

    def _payload():
        return {
            "file_sha256": approved["file_sha256"],
            "analysis_status": "VALID",
            "usable_for_learning": False,
            "learning_status": "PENDING_REVIEW",
            "learning_status_source": "AUTO",
            "approved_at": "",
            "approved_by": "",
        }

    preserved = _payload()
    _apply_existing_manual_learning_decision(preserved, approved)
    assert preserved["learning_status"] == "INCLUDED"
    assert preserved["usable_for_learning"] is True
    assert preserved["approved_by"] == "SERGIO"
    assert preserved["approved_at"]

    for missing in ("approved_by", "approved_at"):
        unproven = dict(approved)
        unproven[missing] = ""
        payload = _payload()
        _apply_existing_manual_learning_decision(payload, unproven)
        assert payload["learning_status"] == "PENDING_REVIEW"
        assert payload["usable_for_learning"] is False
        assert not (payload["approved_by"] or "").strip()
        assert not (payload["approved_at"] or "").strip()


def test_approve_rejects_budget_without_content_hash(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_learning_nohash.db"))
    budget_path = tmp_path / "sin_hash.xlsx"
    budget_id, err = upsert_historical_budget(
        {
            "ruta_excel": str(budget_path),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": "sin_hash.xlsx",
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "analysis_status": "VALID",
            "learning_status": "PENDING_REVIEW",
            "learning_status_source": "AUTO",
        }
    )
    assert err is None

    err = approve_budget_for_learning(int(budget_id), "SERGIO")
    assert err is not None
    assert "hash" in err.lower()
    row = get_historical_budget_by_path(str(budget_path))
    assert row is not None
    assert row["learning_status"] != "INCLUDED"
    assert row["usable_for_learning"] is False


def test_repository_rejects_usable_true_even_if_status_is_not_included(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_learning_invalid_usable.db"))
    budget_path = tmp_path / "not_compatible.xlsx"
    budget_id, err = upsert_historical_budget(
        {
            "ruta_excel": str(budget_path),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": "not_compatible.xlsx",
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "analisis_ok": True,
            "analysis_status": "NOT_COMPATIBLE",
            "usable_for_learning": False,
            "learning_status": "NOT_ELIGIBLE",
            "learning_status_source": "AUTO",
        }
    )
    assert err is None

    err = set_historical_budget_learning_status(
        int(budget_id),
        "EXCLUDED",
        True,
        decision_source="MANUAL",
        decision_reason="usable true no permitido",
    )

    assert err is not None
    row = get_historical_budget_by_path(str(budget_path))
    assert row is not None
    assert row["learning_status"] == "NOT_ELIGIBLE"
    assert row["usable_for_learning"] is False
