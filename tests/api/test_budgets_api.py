def _sample_payload():
    return {
        "nombre_proyecto": "Obra de prueba API",
        "lines": [
            {"concepto": "Sustitucion bajante", "unidad": "ml", "cantidad": 10, "precio": 20.0, "source": "manual"},
        ],
    }


def test_create_budget_requires_auth(client):
    resp = client.post("/budgets", json=_sample_payload())
    assert resp.status_code == 401


def test_create_and_get_budget(authed_client):
    resp = authed_client.post("/budgets", json=_sample_payload())
    assert resp.status_code == 201
    budget_id = resp.json()["budget_id"]

    resp_get = authed_client.get(f"/budgets/{budget_id}")
    assert resp_get.status_code == 200
    body = resp_get.json()
    assert body["budget"]["nombre_proyecto"] == "Obra de prueba API"
    assert body["version"]["estado"] == "draft"
    assert len(body["lines"]) == 1


def test_get_unknown_budget_is_404(authed_client):
    resp = authed_client.get("/budgets/999999")
    assert resp.status_code == 404


def test_create_new_version_then_list_versions(authed_client):
    budget_id = authed_client.post("/budgets", json=_sample_payload()).json()["budget_id"]

    resp = authed_client.post(
        f"/budgets/{budget_id}/versions",
        json={"lines": [
            {"concepto": "Pintura fachada", "unidad": "m2", "cantidad": 5, "precio": 12.0, "source": "manual"},
        ]},
    )
    assert resp.status_code == 201

    resp_versions = authed_client.get(f"/budgets/{budget_id}/versions")
    versions = resp_versions.json()["versions"]
    assert len(versions) == 2
    assert versions[0]["estado"] == "superseded"
    assert versions[1]["estado"] == "draft"


def test_approve_budget_then_reapprove_is_409(authed_client):
    budget_id = authed_client.post("/budgets", json=_sample_payload()).json()["budget_id"]

    resp = authed_client.post(f"/budgets/{budget_id}/approve", json={})
    assert resp.status_code == 200

    resp_again = authed_client.post(f"/budgets/{budget_id}/approve", json={})
    assert resp_again.status_code == 409


def test_approve_unknown_budget_is_404(authed_client):
    resp = authed_client.post("/budgets/999999/approve", json={})
    assert resp.status_code == 404


def test_export_pdf_without_prior_excel_export_is_409(authed_client):
    budget_id = authed_client.post("/budgets", json=_sample_payload()).json()["budget_id"]
    resp = authed_client.post(f"/budgets/{budget_id}/export/pdf", json={})
    assert resp.status_code == 409
