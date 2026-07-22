"""
Reglas de negocio compartidas del flujo unificado de generación de partidas
(H2.2): mismo seam para creación de presupuesto (main_frame) y para
regenerar/añadir desde el dashboard, con un modo explícito.

No importa PySide6: los diálogos (VoiceBudgetDialog, CombinedPartidasReviewDialog)
siguen en la GUI y solo aportan presentación/confirmación. Este módulo decide
qué partidas se muestran y cómo se aplican, para poder probarlo sin UI ni disco.
"""

from typing import Dict, List, Optional, Tuple

from src.core.historical_suggestions_dedupe import exclude_existing_from_candidates

MODE_CREATE = "create"
MODE_APPEND = "append"
MODE_REPLACE = "replace"


def split_generated_partidas_for_review(
    partidas: List[Dict],
    mode: str,
    existing_partidas: Optional[List[Dict]] = None,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Aplica las reglas comunes a las partidas que devuelve el orquestador antes
    de mostrarlas en la revisión combinada:

    - En modo 'append', excluye duplicados exactos frente a las partidas ya
      presentes en el presupuesto (ver `exclude_existing_from_candidates`);
      los duplicados dudosos no se descartan, se marcan.
    - Separa por procedencia (`historical` / resto) para que la GUI pueda
      etiquetar el origen en la revisión.

    Returns:
        (historicas, ia_estimadas)
    """
    candidates = list(partidas or [])
    if mode == MODE_APPEND and existing_partidas:
        candidates = exclude_existing_from_candidates(candidates, existing_partidas)

    # Fixes histórico evidenciado, Tarea 5: BudgetOrchestrator ya no emite
    # solo 'historical' generico, emite 'historical_exact'/'historical_comparable'.
    def _is_historical(source) -> bool:
        return str(source or "").startswith("historical")

    historicas = [p for p in candidates if _is_historical(p.get("source"))]
    ia_estimadas = [p for p in candidates if not _is_historical(p.get("source"))]
    return historicas, ia_estimadas


def apply_reviewed_partidas(
    budget_service,
    excel_path: str,
    selected_partidas: List[Dict],
    mode: str,
    project_data: Optional[Dict] = None,
) -> bool:
    """
    Escribe las partidas ya revisadas/confirmadas por el usuario en el Excel,
    eligiendo entre insertar (create/replace) o añadir (append) según el modo.
    """
    if mode == MODE_APPEND:
        return budget_service.append_partidas(excel_path, selected_partidas)
    return budget_service.insert_partidas(excel_path, selected_partidas, project_data)
