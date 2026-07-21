"""Endpoints HTTP del dominio canonico de presupuestos (H4)."""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.deps import require_session
from src.api.schemas import (
    ApproveRequest,
    CreateBudgetRequest,
    ExportExcelRequest,
    ExportPdfRequest,
    NewVersionRequest,
)
from src.core.canonical_budget_exporter import export_budget_to_excel, export_budget_to_pdf
from src.core.repositories.audit_log_repository import record_event
from src.core.repositories.canonical_budget_repository import (
    approve_active_version,
    create_budget_with_first_version,
    get_active_version,
    get_budget,
    get_lines,
    list_documents,
    list_versions,
    register_document,
    start_new_version,
)

router = APIRouter(prefix="/budgets", tags=["budgets"], dependencies=[Depends(require_session)])


def _get_budget_or_404(budget_id: int) -> dict:
    budget = get_budget(budget_id)
    if not budget:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No se encontro el budget indicado.")
    return budget


@router.post("", status_code=status.HTTP_201_CREATED)
def create_budget(payload: CreateBudgetRequest, email: str = Depends(require_session)):
    budget_id, err = create_budget_with_first_version(
        payload.nombre_proyecto, [line.model_dump() for line in payload.lines],
        numero_proyecto=payload.numero_proyecto or "",
    )
    if err is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
    record_event("budget_created", email=email, budget_id=budget_id)
    return {"budget_id": budget_id}


@router.get("/{budget_id}")
def get_budget_state(budget_id: int):
    budget = _get_budget_or_404(budget_id)
    version = get_active_version(budget_id)
    lines = get_lines(version["id"]) if version else []
    return {"budget": budget, "version": version, "lines": lines}


@router.get("/{budget_id}/versions")
def get_budget_versions(budget_id: int):
    _get_budget_or_404(budget_id)
    return {"versions": list_versions(budget_id)}


@router.post("/{budget_id}/versions", status_code=status.HTTP_201_CREATED)
def create_budget_version(budget_id: int, payload: NewVersionRequest, email: str = Depends(require_session)):
    _get_budget_or_404(budget_id)
    version_id, err = start_new_version(
        budget_id, [line.model_dump() for line in payload.lines], origen=payload.origen,
    )
    if err is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
    record_event("version_created", email=email, budget_id=budget_id)
    return {"version_id": version_id}


@router.post("/{budget_id}/approve")
def approve_budget(budget_id: int, payload: ApproveRequest, email: str = Depends(require_session)):
    _get_budget_or_404(budget_id)
    ok, err = approve_active_version(budget_id, aprobado_por=email, nota=payload.nota or "")
    if not ok:
        if "solo se puede aprobar" in (err or "").lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=err)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err)
    record_event("version_approved", email=email, budget_id=budget_id)
    return {"ok": True}


@router.post("/{budget_id}/export/excel")
def export_excel(budget_id: int, payload: ExportExcelRequest, email: str = Depends(require_session)):
    _get_budget_or_404(budget_id)
    result = export_budget_to_excel(budget_id, payload.output_path)
    if not result.success:
        record_event("error", email=email, budget_id=budget_id, detail=result.error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.error)

    version = get_active_version(budget_id)
    register_document(version["id"], "excel_export", result.output_path)
    record_event("export_excel", email=email, budget_id=budget_id)
    return {"output_path": result.output_path}


@router.post("/{budget_id}/export/pdf")
def export_pdf(budget_id: int, payload: ExportPdfRequest, email: str = Depends(require_session)):
    _get_budget_or_404(budget_id)
    version = get_active_version(budget_id)
    documents = list_documents(version["id"]) if version else []
    excel_docs = [d for d in documents if d["tipo"] == "excel_export"]
    if not excel_docs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No hay ningun Excel exportado para esta version. Exporta a Excel primero.",
        )
    excel_path = excel_docs[-1]["ruta"]

    result = export_budget_to_pdf(excel_path, pdf_path=payload.pdf_path)
    if not result.success:
        record_event("error", email=email, budget_id=budget_id, detail=result.error)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.error)

    register_document(version["id"], "pdf_export", result.output_path)
    record_event("export_pdf", email=email, budget_id=budget_id)
    return {"output_path": result.output_path}
