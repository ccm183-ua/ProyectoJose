"""
Registro de auditoria del backend privado (H4): quien hizo que y cuando.

`detail` es texto corto (p. ej. clase de excepcion, "12 lineas") - nunca
prompts completos ni datos personales de terceros.
"""

import sqlite3
from datetime import datetime
from typing import Optional

from src.core import database
from src.core.repositories._common import _mensaje_integridad

_VALID_EVENT_TYPES = {
    "login_success", "login_failure", "logout",
    "budget_created", "version_created", "version_approved",
    "export_excel", "export_pdf", "error",
}


def record_event(
    event_type: str, email: Optional[str] = None, budget_id: Optional[int] = None, detail: str = "",
) -> Optional[str]:
    """Inserta una fila de auditoria. Devuelve un mensaje de error o None si fue bien."""
    if event_type not in _VALID_EVENT_TYPES:
        return f"event_type no valido: {event_type}."
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with database.get_connection() as conn:
        try:
            conn.execute(
                """INSERT INTO audit_log (event_type, email, budget_id, detail, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (event_type, email, budget_id, (detail or "").strip() or None, now),
            )
            conn.commit()
            return None
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return _mensaje_integridad(e)
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."
