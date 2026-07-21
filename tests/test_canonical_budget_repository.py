"""
Tests del repositorio del dominio canonico (H3): creacion atomica,
maquina de estados de budget_version, evidencia y documentos.
"""

import pytest

from src.core.repositories.canonical_budget_repository import (
    approve_active_version,
    create_budget_with_first_version,
    get_active_version,
    get_approval,
    get_budget,
    get_budget_by_legacy_id,
    get_evidence,
    get_lines,
    link_field_evidence,
    list_documents,
    list_field_evidence,
    list_versions,
    record_evidence,
    register_document,
    start_new_version,
)


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_canonical_test.db"))
    return tmp_path


def _sample_lines():
    return [
        {"concepto": "Sustitucion bajante", "unidad": "ml", "cantidad": 10, "precio": 20.0, "source": "historical"},
        {"concepto": "Pintura fachada", "unidad": "m2", "cantidad": 5, "precio": 12.0, "source": "ai_completion"},
    ]


def test_create_budget_with_first_version_is_atomic_and_computes_totals(db_env):
    budget_id, err = create_budget_with_first_version("Obra de prueba", _sample_lines())
    assert err is None
    assert budget_id is not None

    budget = get_budget(budget_id)
    assert budget["active_version_id"] is not None
    assert budget["estado"] == "draft"

    version = get_active_version(budget_id)
    assert version["numero_version"] == 1
    assert version["estado"] == "draft"
    assert version["subtotal"] == 260.0  # 10*20 + 5*12
    assert version["iva"] == 26.0
    assert version["total"] == 286.0

    lines = get_lines(version["id"])
    assert len(lines) == 2
    assert all(l["line_uid"] for l in lines)
    assert {l["orden"] for l in lines} == {1, 2}


def test_create_budget_requires_nombre_proyecto(db_env):
    budget_id, err = create_budget_with_first_version("", _sample_lines())
    assert budget_id is None
    assert "obligatorio" in err.lower()


def test_create_budget_with_estado_aprobado_directo(db_env):
    budget_id, err = create_budget_with_first_version(
        "Obra finalizada", _sample_lines(), estado_inicial="approved",
    )
    assert err is None
    version = get_active_version(budget_id)
    assert version["estado"] == "approved"
    assert version["approved_at"]


def test_get_budget_by_legacy_id(db_env):
    from datetime import datetime

    from src.core.repositories.presupuesto_cache_repository import get_presupuesto_por_id, upsert_presupuesto

    legacy_id, err = upsert_presupuesto({
        "nombre_proyecto": "Obra legado",
        "ruta_excel": str(db_env / "legado.xlsx"),
        "fecha_modificacion_excel": datetime.now().isoformat(),
        "fecha_cache": datetime.now().isoformat(),
    })
    assert err is None
    assert get_presupuesto_por_id(legacy_id)["nombre_proyecto"] == "Obra legado"
    assert get_presupuesto_por_id(-1) is None

    budget_id, err = create_budget_with_first_version(
        "Obra con legado", _sample_lines(), presupuesto_legacy_id=legacy_id,
    )
    assert err is None
    found = get_budget_by_legacy_id(legacy_id)
    assert found["id"] == budget_id


def test_start_new_version_supersedes_previous_and_becomes_draft(db_env):
    budget_id, _ = create_budget_with_first_version("Obra v1", _sample_lines())
    v1 = get_active_version(budget_id)

    new_lines = [{"concepto": "Partida revisada", "unidad": "ud", "cantidad": 1, "precio": 100.0}]
    version_id, err = start_new_version(budget_id, new_lines, origen="manual_edit")
    assert err is None

    versions = list_versions(budget_id)
    assert len(versions) == 2
    v1_after = next(v for v in versions if v["id"] == v1["id"])
    assert v1_after["estado"] == "superseded"
    assert v1_after["superseded_by_version_id"] == version_id

    budget = get_budget(budget_id)
    assert budget["active_version_id"] == version_id
    assert budget["estado"] == "draft"

    active = get_active_version(budget_id)
    assert active["numero_version"] == 2
    assert active["total"] == 110.0


def test_start_new_version_from_approved_also_supersedes(db_env):
    budget_id, _ = create_budget_with_first_version(
        "Obra aprobada", _sample_lines(), estado_inicial="approved",
    )
    v1 = get_active_version(budget_id)
    assert v1["estado"] == "approved"

    version_id, err = start_new_version(budget_id, [{"concepto": "X", "unidad": "ud", "cantidad": 1, "precio": 1}])
    assert err is None

    versions = list_versions(budget_id)
    v1_after = next(v for v in versions if v["id"] == v1["id"])
    assert v1_after["estado"] == "superseded"


def test_start_new_version_rejects_unknown_budget(db_env):
    version_id, err = start_new_version(999999, _sample_lines())
    assert version_id is None
    assert "no se encontro" in err.lower()


def test_approve_active_version_success(db_env):
    budget_id, _ = create_budget_with_first_version("Obra a aprobar", _sample_lines())
    ok, err = approve_active_version(budget_id, aprobado_por="cayetano")
    assert ok is True
    assert err is None

    version = get_active_version(budget_id)
    assert version["estado"] == "approved"
    assert get_budget(budget_id)["estado"] == "approved"


def test_approve_active_version_rejects_already_approved(db_env):
    budget_id, _ = create_budget_with_first_version(
        "Obra ya aprobada", _sample_lines(), estado_inicial="approved",
    )
    ok, err = approve_active_version(budget_id, aprobado_por="cayetano")
    assert ok is False
    assert "borrador" in err.lower()


def test_approve_active_version_requires_aprobado_por(db_env):
    budget_id, _ = create_budget_with_first_version("Obra", _sample_lines())
    ok, err = approve_active_version(budget_id, aprobado_por="")
    assert ok is False
    assert "obligatorio" in err.lower()


def test_evidence_and_field_evidence_and_document(db_env):
    budget_id, _ = create_budget_with_first_version("Obra con evidencia", _sample_lines())
    version = get_active_version(budget_id)
    lines = get_lines(version["id"])

    evidence_id, err = record_evidence("legacy_excel", referencia="C:/fake/obra.xlsx")
    assert err is None

    err = link_field_evidence(lines[0]["id"], "precio", evidence_id)
    assert err is None

    doc_id, err = register_document(version["id"], "excel_import", "C:/fake/obra.xlsx")
    assert err is None
    assert doc_id is not None


def test_record_evidence_rejects_unknown_tipo_fuente(db_env):
    evidence_id, err = record_evidence("no_existe")
    assert evidence_id is None
    assert "no valido" in err.lower()


def test_traceability_read_functions(db_env):
    budget_id, _ = create_budget_with_first_version("Obra con trazabilidad", _sample_lines())
    version = get_active_version(budget_id)
    lines = get_lines(version["id"])

    evidence_id, _ = record_evidence("legacy_excel", referencia="C:/fake/obra.xlsx", resumen="Excel original")
    link_field_evidence(lines[0]["id"], "precio", evidence_id)
    register_document(version["id"], "excel_import", "C:/fake/obra.xlsx")
    approve_active_version(budget_id, aprobado_por="cayetanocanovas13@gmail.com", nota="ok")

    evidence = get_evidence(evidence_id)
    assert evidence["tipo_fuente"] == "legacy_excel"
    assert evidence["resumen"] == "Excel original"

    field_evidence = list_field_evidence(lines[0]["id"])
    assert len(field_evidence) == 1
    assert field_evidence[0]["campo"] == "precio"
    assert field_evidence[0]["evidence"]["tipo_fuente"] == "legacy_excel"

    documents = list_documents(version["id"])
    assert len(documents) == 1
    assert documents[0]["tipo"] == "excel_import"

    approval = get_approval(version["id"])
    assert approval["aprobado_por"] == "cayetanocanovas13@gmail.com"
    assert approval["nota"] == "ok"


def test_traceability_read_functions_return_empty_or_none_when_absent(db_env):
    budget_id, _ = create_budget_with_first_version("Obra sin trazabilidad", _sample_lines())
    version = get_active_version(budget_id)
    lines = get_lines(version["id"])

    assert get_evidence(999999) is None
    assert list_field_evidence(lines[0]["id"]) == []
    assert list_documents(version["id"]) == []
    assert get_approval(version["id"]) is None
