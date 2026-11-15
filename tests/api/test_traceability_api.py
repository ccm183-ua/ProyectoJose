from src.core.repositories.canonical_budget_repository import (
    get_active_version,
    link_field_evidence,
    record_evidence,
)


def _sample_payload():
    return {
        "nombre_proyecto": "Obra con trazabilidad API",
        "lines": [
            {"concepto": "Sustitucion bajante", "unidad": "ml", "cantidad": 10, "precio": 20.0, "source": "manual"},
        ],
    }


def test_traceability_requires_auth(client):
    resp = client.get("/budgets/1/traceability")
    assert resp.status_code == 401


def test_traceability_reflects_evidence_recorded_via_core(authed_client):
    budget_id = authed_client.post("/budgets", json=_sample_payload()).json()["budget_id"]

    version = get_active_version(budget_id)
    lines = authed_client.get(f"/budgets/{budget_id}").json()["lines"]
    evidence_id, err = record_evidence("legacy_excel", referencia="C:/fake/obra.xlsx")
    assert err is None
    link_field_evidence(lines[0]["id"], "precio", evidence_id)

    resp = authed_client.get(f"/budgets/{budget_id}/traceability")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["lines"]) == 1
    assert len(body["lines"][0]["field_evidence"]) == 1
    assert body["lines"][0]["field_evidence"][0]["evidence"]["tipo_fuente"] == "legacy_excel"
    assert body["approval"] is None


def test_traceability_unknown_budget_is_404(authed_client):
    resp = authed_client.get("/budgets/999999/traceability")
    assert resp.status_code == 404
