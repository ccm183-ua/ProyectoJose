"""
Adapter de exportacion del dominio canonico (H3): genera el Excel (plantilla
122-20 exacta) y el PDF a partir de un `budget`, segun la decision del
propietario ("plantilla exacta + PDF").

Direccion segun ADR 0002: Excel/PDF se generan *desde* el dominio canonico,
nunca al reves. Los importes/totales que se escriben son siempre los ya
calculados por `budget_math` y persistidos en `budget_version`/`budget_line`
(nunca se recalculan aqui de forma distinta).

Enriquecimiento de cabecera: el modelo minimo de H3 (`budget`) todavia no
modela cliente/direccion/administracion — eso no esta en el roadmap de H3.
Si el budget viene de una importacion (`presupuesto_legacy_id`), se completan
esos campos de cabecera leyendo la fila `presupuesto` enlazada (solo lectura,
nunca se escribe alli). Un budget sin origen legacy exporta con esos campos
en blanco: no se inventan datos que el dominio canonico no tiene.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

from src.core.excel_manager import ExcelManager
from src.core.repositories.canonical_budget_repository import get_active_version, get_budget, get_lines
from src.core.repositories.presupuesto_cache_repository import get_presupuesto_por_id
from src.core.template_manager import TemplateManager


@dataclass
class ExportResult:
    success: bool
    output_path: str = ""
    error: str = ""


def _build_header_data(budget: Dict) -> Dict:
    """Cabecera minima desde el dominio canonico, enriquecida con la fila
    `presupuesto` legacy enlazada si existe (solo lectura)."""
    data = {
        "nombre_obra": budget.get("nombre_proyecto", ""),
        "numero_proyecto": budget.get("numero_proyecto", ""),
        "tipo": budget.get("nombre_proyecto", ""),
    }
    legacy_id = budget.get("presupuesto_legacy_id")
    if legacy_id:
        legacy = get_presupuesto_por_id(legacy_id)
        if legacy:
            data.update({
                "cliente": legacy.get("cliente", ""),
                "direccion": legacy.get("direccion", ""),
                "localidad": legacy.get("localidad", ""),
                "codigo_postal": legacy.get("codigo_postal", ""),
                "fecha": legacy.get("fecha", ""),
                "admin_cif": legacy.get("cif_admin", ""),
                "admin_email": legacy.get("email_admin", ""),
                "admin_telefono": legacy.get("telefono_admin", ""),
                "tipo": legacy.get("tipo_obra", "") or data["tipo"],
            })
    return data


def _lines_to_partidas(lines: List[Dict]) -> List[Dict]:
    return [
        {
            "concepto": line.get("concepto", ""),
            "unidad": line.get("unidad") or "ud",
            "cantidad": line.get("cantidad", 0),
            "precio_unitario": line.get("precio", 0),
        }
        for line in lines
    ]


def export_budget_to_excel(
    budget_id: int,
    output_path: str,
    version_id: Optional[int] = None,
    excel_manager: Optional[ExcelManager] = None,
    template_manager: Optional[TemplateManager] = None,
) -> ExportResult:
    """Genera un Excel (plantilla 122-20 exacta) con la cabecera y las
    partidas de una version de un budget canonico. Por defecto exporta la
    version activa; `version_id` permite exportar una version concreta
    (por ejemplo, una ya superseded, para auditoria)."""
    excel_manager = excel_manager or ExcelManager()
    template_manager = template_manager or TemplateManager()

    budget = get_budget(budget_id)
    if not budget:
        return ExportResult(success=False, error="No se encontro el budget indicado.")

    if version_id is None:
        version = get_active_version(budget_id)
        if not version:
            return ExportResult(success=False, error="El budget no tiene version activa.")
    else:
        version = {"id": version_id}

    lines = get_lines(version["id"])

    template_path = template_manager.get_template_path()
    header_data = _build_header_data(budget)
    if not excel_manager.create_from_template(template_path, output_path, header_data):
        return ExportResult(success=False, error="No se pudo crear el Excel desde la plantilla.")

    partidas = _lines_to_partidas(lines)
    if partidas and not excel_manager.insert_partidas_via_xml(output_path, partidas):
        return ExportResult(success=False, error="No se pudieron insertar las partidas en el Excel.")

    return ExportResult(success=True, output_path=output_path)


def export_budget_to_pdf(
    excel_path: str,
    pdf_path: Optional[str] = None,
    pdf_exporter=None,
) -> ExportResult:
    """Genera el PDF a partir de un Excel ya exportado (requiere Excel real
    vía COM; `pdf_exporter` permite inyectar un doble en tests)."""
    if pdf_exporter is None:
        from src.core.pdf_exporter import PDFExporter

        pdf_exporter = PDFExporter()

    ok, result_path_or_error = pdf_exporter.export(excel_path, pdf_path)
    if not ok:
        return ExportResult(success=False, error=result_path_or_error or "Error al exportar a PDF.")
    return ExportResult(success=True, output_path=result_path_or_error)
