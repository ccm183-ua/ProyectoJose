"""Tests del catalogo de precios de referencia (H5)."""

from datetime import datetime, timedelta

import pytest

from src.core import database
from src.core.repositories.price_reference_repository import (
    approve_price_reference,
    create_price_reference,
    get_price_reference,
    list_price_references,
    refresh_expired_price_references,
    reject_price_reference,
)


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_price_reference_test.db"))
    return tmp_path


def test_create_price_reference_computes_vigencia(db_env):
    pr_id, err = create_price_reference(
        "Sustitucion bajante", "ml", 20.0, "manual", "2026-01-01",
    )
    assert err is None
    assert pr_id is not None

    pr = get_price_reference(pr_id)
    assert pr["concepto"] == "Sustitucion bajante"
    assert pr["estado"] == "proposed"
    assert pr["moneda"] == "EUR"
    assert pr["impuestos_incluidos"] is False
    assert pr["vigente_hasta"] == "2027-01-01"


def test_create_price_reference_rejects_empty_concepto(db_env):
    pr_id, err = create_price_reference("", "ml", 20.0, "manual", "2026-01-01")
    assert pr_id is None
    assert "concepto" in err.lower()


def test_create_price_reference_rejects_non_positive_importe(db_env):
    pr_id, err = create_price_reference("Concepto", "ml", 0, "manual", "2026-01-01")
    assert pr_id is None
    assert "importe" in err.lower()


def test_create_price_reference_rejects_unknown_origen(db_env):
    pr_id, err = create_price_reference("Concepto", "ml", 20.0, "web", "2026-01-01")
    assert pr_id is None
    assert "origen no valido" in err.lower()


def test_approve_then_reapprove_is_rejected(db_env):
    pr_id, _ = create_price_reference("Concepto", "ml", 20.0, "manual", "2026-01-01")

    ok, err = approve_price_reference(pr_id)
    assert ok is True
    assert get_price_reference(pr_id)["estado"] == "approved"

    ok2, err2 = approve_price_reference(pr_id)
    assert ok2 is False
    assert "proposed" in err2.lower()


def test_reject_price_reference(db_env):
    pr_id, _ = create_price_reference("Concepto", "ml", 20.0, "manual", "2026-01-01")
    ok, err = reject_price_reference(pr_id)
    assert ok is True
    assert get_price_reference(pr_id)["estado"] == "rejected"


def test_list_price_references_filters(db_env):
    create_price_reference("Bajante", "ml", 20.0, "manual", "2026-01-01")
    create_price_reference("Bajante", "ud", 5.0, "historical", "2026-01-01")
    create_price_reference("Pintura", "m2", 12.0, "manual", "2026-01-01")

    assert len(list_price_references(concepto="Bajante")) == 2
    assert len(list_price_references(unidad="ud")) == 1
    assert len(list_price_references(estado="proposed")) == 3


def test_refresh_expired_price_references_only_marks_past_vigencia(db_env):
    old_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
    recent_date = datetime.now().strftime("%Y-%m-%d")

    expired_id, _ = create_price_reference("Viejo", "ml", 20.0, "manual", old_date)
    vigente_id, _ = create_price_reference("Reciente", "ml", 20.0, "manual", recent_date)

    updated = refresh_expired_price_references()
    assert updated == 1
    assert get_price_reference(expired_id)["estado"] == "expired"
    assert get_price_reference(vigente_id)["estado"] == "proposed"
