"""
Tests del informe de impacto por familia (Task 1 del plan
docs/superpowers/plans/2026-08-04-completar-vocabulario-cerrado.md).
"""

from datetime import datetime

from src.core.repositories import (
    assign_partida_module,
    get_or_create_execution_module,
    insert_historical_partida,
    approve_budget_for_learning,
    upsert_historical_budget,
    upsert_partida_features,
)
from src.core.historical_vocabulary_gap_report import (
    rank_families_by_gap,
    top_unmatched_phrases_for_family,
)


def _seed(tmp_path, monkeypatch):
    db_path = tmp_path / "datos_gap_test.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))

    mod_alicatado, err = get_or_create_execution_module("alicatado")
    assert err is None
    mod_fachada, err = get_or_create_execution_module("fachada")
    assert err is None

    bid, berr = upsert_historical_budget(
        {
            "ruta_excel": str(tmp_path / "obra.xlsx"),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": "obra",
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "analisis_ok": True,
            "analysis_status": "VALID",
            "file_sha256": "sha-gap-test",
        }
    )
    assert berr is None
    # Desde septiembre de 2026 solo approve_budget_for_learning puede incluir
    # un presupuesto en la memoria (aprobación con autor y fecha).
    assert approve_budget_for_learning(bid, "TEST") is None

    def _partida(concepto, unidad, orden):
        pid, perr = insert_historical_partida(
            bid,
            {
                "orden": orden,
                "titulo": concepto[:40],
                "concepto_original": concepto,
                "concepto_normalizado": concepto.lower(),
                "unidad": unidad,
                "precio_unitario": 30.0,
                "cantidad": 1,
                "total_linea": 30.0,
            },
        )
        assert perr is None
        return pid

    # Dos lineas de "alicatado" sin element (misma frase repetida = frecuencia 2).
    for orden in (1, 2):
        pid = _partida("Demolicion de alicatado existente", "m2", orden)
        assign_partida_module(pid, mod_alicatado, 0.9, "rules")
        upsert_partida_features(
            pid,
            {
                "action": "demolish", "element": None, "system": None, "unit": "m2",
                "material": None, "dimensions": (), "conditions": (),
                "line_kind": "atomic", "primary_module_id": "alicatado",
                "secondary_module_ids": (), "confidence": 0.9, "reasons": (),
                "classifier_version": "test",
            },
        )

    # Una linea de "fachada" YA con ficha completa (no debe contar como hueco).
    pid = _partida("Reparacion de grieta en fachada", "m2", 3)
    assign_partida_module(pid, mod_fachada, 0.9, "rules")
    upsert_partida_features(
        pid,
        {
            "action": "repair", "element": "facade", "system": None, "unit": "m2",
            "material": None, "dimensions": (), "conditions": (),
            "line_kind": "atomic", "primary_module_id": "fachada",
            "secondary_module_ids": (), "confidence": 0.9, "reasons": (),
            "classifier_version": "test",
        },
    )

    return db_path


def test_rank_families_by_gap_orders_by_missing_feature_count(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)

    ranking = rank_families_by_gap(["alicatado", "fachada"])

    assert ranking[0]["familia"] == "alicatado"
    assert ranking[0]["sin_ficha_completa"] == 2
    assert ranking[1]["familia"] == "fachada"
    assert ranking[1]["sin_ficha_completa"] == 0


def test_top_unmatched_phrases_groups_by_normalized_text(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)

    phrases = top_unmatched_phrases_for_family("alicatado")

    assert len(phrases) == 1
    assert phrases[0]["frecuencia"] == 2
    assert phrases[0]["ejemplo_original"] == "Demolicion de alicatado existente"


def test_top_unmatched_phrases_excludes_complete_features(tmp_path, monkeypatch):
    _seed(tmp_path, monkeypatch)

    phrases = top_unmatched_phrases_for_family("fachada")

    assert phrases == []
