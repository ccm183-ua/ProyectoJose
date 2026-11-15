"""Esquemas Pydantic de request/response del backend privado (H4)."""

from typing import List, Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class MeResponse(BaseModel):
    email: str


class BudgetLineIn(BaseModel):
    concepto: str
    unidad: Optional[str] = None
    cantidad: float
    precio: float
    source: str = "manual"


class CreateBudgetRequest(BaseModel):
    nombre_proyecto: str
    lines: List[BudgetLineIn]
    numero_proyecto: Optional[str] = None


class NewVersionRequest(BaseModel):
    lines: List[BudgetLineIn]
    origen: str = "manual_edit"


class ApproveRequest(BaseModel):
    nota: Optional[str] = ""


class ExportExcelRequest(BaseModel):
    output_path: str


class ExportPdfRequest(BaseModel):
    pdf_path: Optional[str] = None
