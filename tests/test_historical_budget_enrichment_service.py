import json
from datetime import datetime

from src.core import database
from src.core.historical_budget_enrichment_service import (
    build_technical_description_input,
    calculate_input_hash,
    generate_technical_description_for_budget,
    generate_technical_descriptions_for_budgets,
)
from src.core.repositories import (
    assign_partida_module,
    get_budget_enrichment,
    get_or_create_execution_module,
    insert_historical_partida,
    upsert_budget_enrichment,
    upsert_historical_budget,
)


class FakeAIClient:
    def __init__(self, text=None, error=""):
        self.text = text or json.dumps(
            {
                "technical_description": "Impermeabilizacion de cubierta comunitaria con reparacion de filtraciones.",
                "main_works": ["impermeabilizacion", "reparacion de filtraciones"],
                "elements": ["cubierta"],
                "zones": ["cubierta comunitaria"],
                "materials": ["lamina impermeabilizante"],
                "confidence": 0.78,
                "warnings": [],
            }
        )
        self.error = error
        self.calls = 0

    def generate_technical_description(self, prompt):
        self.calls += 1
        return {"text": self.text, "error": self.error, "model": "fake-model"}


def _budget(tmp_path, name="budget.xlsx", **overrides):
    data = {
        "ruta_excel": str(tmp_path / name),
        "ruta_carpeta": str(tmp_path),
        "nombre_proyecto": "Impermeabilizacion cubierta",
        "numero_proyecto": "001-26",
        "cliente": "Comunidad Test",
        "localidad": "Alicante",
        "tipo_obra_original": "Cubierta",
        "tipo_obra_normalizado": "impermeabilizacion",
        "fecha_modificacion_excel": datetime.now().isoformat(),
        "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analisis_ok": True,
        "analysis_status": "VALID",
        "learning_status": "INCLUDED",
        "usable_for_learning": True,
        "warning_count": 0,
        "total": 1234.56,
        "num_partidas": 2,
        "selected_sheet": "Presupuesto",
        "compatible_score": 90,
    }
    data.update(overrides)
    budget_id, err = upsert_historical_budget(data)
    assert err is None
    assert budget_id is not None
    return int(budget_id)


def _add_partidas_and_module(budget_id):
    module_id, err = get_or_create_execution_module("impermeabilizacion")
    assert err is None
    partida_id, partida_err = insert_historical_partida(
        budget_id,
        {
            "orden": 1,
            "codigo": "01",
            "concepto_original": "Impermeabilizacion de cubierta con lamina asfaltica",
            "concepto_normalizado": "impermeabilizacion cubierta lamina asfaltica",
            "unidad": "m2",
            "cantidad": 20,
            "precio_unitario": 35,
            "total_linea": 700,
        },
    )
    assert partida_err is None
    assert assign_partida_module(partida_id, module_id, 0.9, "rules") is None
    partida2_id, partida2_err = insert_historical_partida(
        budget_id,
        {
            "orden": 2,
            "codigo": "02",
            "concepto_original": "Revision y limpieza de sumideros",
            "concepto_normalizado": "revision limpieza sumideros",
            "unidad": "ud",
            "cantidad": 2,
            "precio_unitario": 50,
            "total_linea": 100,
        },
    )
    assert partida2_err is None
    assert assign_partida_module(partida2_id, module_id, 0.7, "rules") is None


def test_valid_budget_generates_pending_ai_enrichment(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "ai_enrichment.db"))
    with database.get_connection() as _conn:
        pass
    budget_id = _budget(tmp_path)
    _add_partidas_and_module(budget_id)
    fake = FakeAIClient()

    result = generate_technical_description_for_budget(budget_id, ai_client=fake)

    assert result["status"] == "generated"
    row = get_budget_enrichment(budget_id, "TECHNICAL_DESCRIPTION")
    assert row is not None
    assert row["status"] == "PENDING_REVIEW"
    assert row["source"] == "AI"
    assert row["model"] == "fake-model"
    assert row["prompt_version"] == "historical_technical_description_v1"
    assert row["input_hash"]
    assert row["confidence"] == 0.78
    metadata = json.loads(row["metadata_json"])
    assert metadata["main_works"] == ["impermeabilizacion", "reparacion de filtraciones"]
    assert metadata["elements"] == ["cubierta"]


def test_invalid_budget_is_skipped_without_ai_call(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "ai_invalid.db"))
    with database.get_connection() as _conn:
        pass
    budget_id = _budget(tmp_path, analysis_status="NOT_COMPATIBLE", usable_for_learning=False)
    fake = FakeAIClient()

    result = generate_technical_description_for_budget(budget_id, ai_client=fake)

    assert result["status"] == "skipped"
    assert result["skipped_reason"] == "not_eligible"
    assert fake.calls == 0
    assert get_budget_enrichment(budget_id, "TECHNICAL_DESCRIPTION") is None


def test_does_not_overwrite_manual_or_approved(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "ai_protected.db"))
    with database.get_connection() as _conn:
        pass
    manual_id = _budget(tmp_path, "manual.xlsx")
    approved_id = _budget(tmp_path, "approved.xlsx")
    assert upsert_budget_enrichment(
        manual_id, "TECHNICAL_DESCRIPTION", "MANUAL", "MANUAL", "Descripcion manual."
    ) is None
    assert upsert_budget_enrichment(
        approved_id, "TECHNICAL_DESCRIPTION", "APPROVED", "AI", "Descripcion aprobada."
    ) is None
    fake = FakeAIClient()

    manual_result = generate_technical_description_for_budget(manual_id, ai_client=fake)
    approved_result = generate_technical_description_for_budget(approved_id, ai_client=fake)

    assert manual_result["status"] == "skipped"
    assert approved_result["status"] == "skipped"
    assert fake.calls == 0
    assert get_budget_enrichment(manual_id, "TECHNICAL_DESCRIPTION")["content"] == "Descripcion manual."
    assert get_budget_enrichment(approved_id, "TECHNICAL_DESCRIPTION")["content"] == "Descripcion aprobada."


def test_invalid_ai_response_returns_error_without_saving(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "ai_bad_response.db"))
    with database.get_connection() as _conn:
        pass
    budget_id = _budget(tmp_path)
    fake = FakeAIClient(text="{bad json")

    result = generate_technical_description_for_budget(budget_id, ai_client=fake)

    assert result["status"] == "error"
    assert "JSON valido" in result["message"]
    assert get_budget_enrichment(budget_id, "TECHNICAL_DESCRIPTION") is None


def test_input_hash_is_stable_and_metadata_is_saved(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "ai_hash.db"))
    with database.get_connection() as _conn:
        pass
    budget_id = _budget(tmp_path)
    _add_partidas_and_module(budget_id)

    payload_one = build_technical_description_input({"id": budget_id, **_budget_data_stub()})
    payload_two = build_technical_description_input({"id": budget_id, **_budget_data_stub()})
    assert calculate_input_hash(payload_one) == calculate_input_hash(payload_two)

    result = generate_technical_description_for_budget(budget_id, ai_client=FakeAIClient())
    assert result["status"] == "generated"
    metadata = json.loads(get_budget_enrichment(budget_id, "TECHNICAL_DESCRIPTION")["metadata_json"])
    assert metadata["total_partidas"] == 2
    assert metadata["partidas_sent"] == 2


def test_batch_skips_not_eligible(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "ai_batch.db"))
    with database.get_connection() as _conn:
        pass
    valid_id = _budget(tmp_path, "valid.xlsx")
    invalid_id = _budget(tmp_path, "invalid.xlsx", analysis_status="READ_ERROR", usable_for_learning=False)
    fake = FakeAIClient()

    result = generate_technical_descriptions_for_budgets([valid_id, invalid_id], ai_client=fake)

    assert result["processed"] == 2
    assert result["generated"] == 1
    assert result["skipped"] == 1
    assert result["errors"] == 0
    assert fake.calls == 1


def _budget_data_stub():
    return {
        "ruta_excel": "budget.xlsx",
        "nombre_proyecto": "Impermeabilizacion cubierta",
        "cliente": "Comunidad Test",
        "localidad": "Alicante",
        "tipo_obra_original": "Cubierta",
        "tipo_obra_normalizado": "impermeabilizacion",
        "total": 1234.56,
        "selected_sheet": "Presupuesto",
    }
