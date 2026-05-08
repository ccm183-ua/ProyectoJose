"""
Helpers de enriquecimiento histórico reutilizables (sin dependencias de UI).
"""


def technical_description_status_label(status: str) -> str:
    normalized = (status or "").strip().upper()
    if not normalized:
        return "Sin descripción"
    return {
        "MANUAL": "Manual",
        "APPROVED": "Aprobada",
        "PENDING_REVIEW": "Pendiente",
        "PENDING": "Pendiente",
        "REJECTED": "Rechazada",
    }.get(normalized, normalized.title())
