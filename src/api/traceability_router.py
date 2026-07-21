"""Endpoint de trazabilidad de un budget (H4): de donde sale cada dato."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import require_session
from src.core.repositories.canonical_budget_repository import (
    get_active_version,
    get_approval,
    get_budget,
    get_lines,
    list_documents,
    list_field_evidence,
)

router = APIRouter(prefix="/budgets", tags=["traceability"], dependencies=[Depends(require_session)])


@router.get("/{budget_id}/traceability")
def get_traceability(budget_id: int):
    budget = get_budget(budget_id)
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se encontro el budget indicado.")

    version = get_active_version(budget_id)
    if not version:
        return {"lines": [], "documents": [], "approval": None}

    lines = get_lines(version["id"])
    for line in lines:
        line["field_evidence"] = list_field_evidence(line["id"])

    return {
        "lines": lines,
        "documents": list_documents(version["id"]),
        "approval": get_approval(version["id"]),
    }
