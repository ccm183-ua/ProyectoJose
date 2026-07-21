"""
H4 puerta minima: los casos de uso se ejecutan igual por test directo (core)
y por HTTP. Compara resultados de negocio ignorando ids/uuids/timestamps,
que difieren legitimamente entre los dos budgets creados.
"""

from src.core.repositories.canonical_budget_repository import (
    approve_active_version,
    create_budget_with_first_version,
    get_active_version,
    get_lines,
)

_LINES = [
    {"concepto": "Sustitucion bajante", "unidad": "ml", "cantidad": 10, "precio": 20.0, "source": "manual"},
    {"concepto": "Pintura fachada", "unidad": "m2", "cantidad": 5, "precio": 12.0, "source": "manual"},
]


def _totales(version):
    return {"subtotal": version["subtotal"], "iva": version["iva"], "total": version["total"]}


def _lineas_comparables(lines):
    return sorted(
        [{"concepto": l["concepto"], "cantidad": l["cantidad"], "precio": l["precio"], "importe": l["importe"]} for l in lines],
        key=lambda l: l["concepto"],
    )


def test_create_budget_parity_core_vs_http(authed_client):
    core_budget_id, err = create_budget_with_first_version("Obra paridad core", list(_LINES))
    assert err is None
    core_version = get_active_version(core_budget_id)
    core_lines = get_lines(core_version["id"])

    resp = authed_client.post("/budgets", json={"nombre_proyecto": "Obra paridad http", "lines": _LINES})
    assert resp.status_code == 201
    http_budget_id = resp.json()["budget_id"]
    http_body = authed_client.get(f"/budgets/{http_budget_id}").json()

    assert _totales(core_version) == _totales(http_body["version"])
    assert _lineas_comparables(core_lines) == _lineas_comparables(http_body["lines"])


def test_approve_parity_core_vs_http(authed_client):
    core_budget_id, _ = create_budget_with_first_version("Obra aprobar core", list(_LINES))
    ok, err = approve_active_version(core_budget_id, aprobado_por="cayetanocanovas13@gmail.com")
    assert ok is True
    core_version = get_active_version(core_budget_id)

    http_budget_id = authed_client.post(
        "/budgets", json={"nombre_proyecto": "Obra aprobar http", "lines": _LINES}
    ).json()["budget_id"]
    resp_approve = authed_client.post(f"/budgets/{http_budget_id}/approve", json={})
    assert resp_approve.status_code == 200
    http_version = authed_client.get(f"/budgets/{http_budget_id}").json()["version"]

    assert core_version["estado"] == http_version["estado"] == "approved"
    assert _totales(core_version) == _totales(http_version)
