"""
Tests del seam de negocio compartido (H2.2) entre creación de presupuesto y
dashboard: split por procedencia, exclusión en modo append, y aplicación
final (insert vs append). Sin PySide6, sin disco real.
"""

from src.core.services.budget_partidas_flow import (
    MODE_APPEND,
    MODE_CREATE,
    MODE_REPLACE,
    apply_reviewed_partidas,
    split_generated_partidas_for_review,
)


def _partidas():
    return [
        {"titulo": "Sustitucion bajante", "unidad": "ml", "precio_unitario": 20.0, "source": "historical"},
        {"titulo": "Pintura fachada", "unidad": "m2", "precio_unitario": 12.0, "source": "ai_completion"},
    ]


def test_create_mode_splits_by_source_without_filtering():
    historicas, ia = split_generated_partidas_for_review(_partidas(), MODE_CREATE)
    assert [p["titulo"] for p in historicas] == ["Sustitucion bajante"]
    assert [p["titulo"] for p in ia] == ["Pintura fachada"]


def test_replace_mode_splits_by_source_without_filtering():
    historicas, ia = split_generated_partidas_for_review(_partidas(), MODE_REPLACE)
    assert len(historicas) == 1 and len(ia) == 1


def test_append_mode_excludes_exact_duplicates_of_existing():
    existing = [{"concepto": "Sustitucion bajante", "unidad": "ml", "precio": 20.0}]
    historicas, ia = split_generated_partidas_for_review(
        _partidas(), MODE_APPEND, existing_partidas=existing
    )
    assert historicas == []
    assert [p["titulo"] for p in ia] == ["Pintura fachada"]


def test_append_mode_without_existing_partidas_keeps_everything():
    historicas, ia = split_generated_partidas_for_review(_partidas(), MODE_APPEND, existing_partidas=[])
    assert len(historicas) == 1 and len(ia) == 1


class _FakeBudgetService:
    def __init__(self):
        self.insert_calls = []
        self.append_calls = []

    def insert_partidas(self, excel_path, partidas, project_data=None):
        self.insert_calls.append((excel_path, partidas, project_data))
        return True

    def append_partidas(self, excel_path, partidas):
        self.append_calls.append((excel_path, partidas))
        return True


def test_apply_reviewed_partidas_create_uses_insert():
    svc = _FakeBudgetService()
    ok = apply_reviewed_partidas(svc, "budget.xlsx", [{"titulo": "X"}], MODE_CREATE, {"cliente": "A"})
    assert ok is True
    assert svc.insert_calls == [("budget.xlsx", [{"titulo": "X"}], {"cliente": "A"})]
    assert svc.append_calls == []


def test_apply_reviewed_partidas_replace_uses_insert():
    svc = _FakeBudgetService()
    apply_reviewed_partidas(svc, "budget.xlsx", [{"titulo": "X"}], MODE_REPLACE)
    assert len(svc.insert_calls) == 1
    assert svc.append_calls == []


def test_apply_reviewed_partidas_append_uses_append():
    svc = _FakeBudgetService()
    apply_reviewed_partidas(svc, "budget.xlsx", [{"titulo": "X"}], MODE_APPEND)
    assert svc.insert_calls == []
    assert svc.append_calls == [("budget.xlsx", [{"titulo": "X"}])]
