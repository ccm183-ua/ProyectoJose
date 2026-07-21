"""
Importador desde la cache existente (presupuesto/presupuesto_partida) hacia
el dominio canonico (H3): budget + budget_version + budget_line.

No borra ni modifica el origen. Los importes/totales se recalculan siempre
en codigo determinista (src.core.budget_math); un total leido de la cabecera
del presupuesto legacy solo sirve para comparar y generar una advertencia de
reconciliacion si difiere (tolerancia 0,01 EUR) — nunca se acepta tal cual.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.core.budget_math import calcular_importe_linea, calcular_totales
from src.core.repositories.canonical_budget_repository import (
    approve_active_version,
    create_budget_with_first_version,
    get_active_version,
    get_budget_by_legacy_id,
    get_lines,
    link_field_evidence,
    record_evidence,
    register_document,
    start_new_version,
)

TOLERANCE_EUR = 0.01


@dataclass
class ImportResult:
    success: bool
    budget_id: Optional[int] = None
    budget_version_id: Optional[int] = None
    warnings: List[Dict] = field(default_factory=list)
    error: str = ""


def _warning(codigo: str, mensaje: str, detalle: Optional[Dict] = None) -> Dict:
    return {"codigo": codigo, "severidad": "warning", "mensaje": mensaje, "detalle": detalle or {}}


def _normalize_lines(partidas: List[Dict]) -> tuple:
    """Recalcula importe, valida campos y reasigna orden duplicado.

    Returns:
        (lineas_normalizadas, warnings)
    """
    warnings: List[Dict] = []
    used_ordenes = set()
    next_free_orden = 1
    normalized: List[Dict] = []

    for p in partidas or []:
        concepto = str(p.get("concepto") or "").strip()
        if not concepto:
            warnings.append(_warning(
                "MISSING_CONCEPTO",
                "Partida sin concepto; se importa igualmente con concepto vacio.",
                {"orden": p.get("orden")},
            ))

        cantidad = float(p.get("cantidad") or 0)
        if cantidad <= 0:
            warnings.append(_warning(
                "NEGATIVE_OR_ZERO_QUANTITY",
                f"Cantidad no positiva ({cantidad}) en partida '{concepto or '(sin concepto)'}'.",
                {"cantidad": cantidad},
            ))

        precio = float(p.get("precio") if p.get("precio") is not None else p.get("precio_unitario") or 0)
        importe_recalculado = calcular_importe_linea(cantidad, precio)
        importe_original = p.get("importe")
        if importe_original is not None and abs(float(importe_original) - importe_recalculado) > TOLERANCE_EUR:
            warnings.append(_warning(
                "LINE_IMPORTE_MISMATCH",
                f"Importe recalculado ({importe_recalculado}) difiere del original "
                f"({importe_original}) en partida '{concepto or '(sin concepto)'}'.",
                {
                    "calculado": importe_recalculado, "original": float(importe_original),
                    "diferencia": round(abs(float(importe_original) - importe_recalculado), 2),
                },
            ))

        orden = p.get("orden")
        while orden is None or orden in used_ordenes:
            if orden is not None:
                warnings.append(_warning(
                    "DUPLICATE_ORDEN",
                    f"Orden {orden} duplicado en partida '{concepto or '(sin concepto)'}'; reasignado.",
                    {"orden_original": orden},
                ))
            orden = next_free_orden
            next_free_orden += 1
        used_ordenes.add(orden)
        next_free_orden = max(next_free_orden, orden + 1)

        normalized.append({
            "orden": orden,
            "numero": p.get("numero"),
            "concepto": concepto,
            "unidad": p.get("unidad"),
            "cantidad": cantidad,
            "precio": precio,
            "source": "legacy_import",
        })

    return normalized, warnings


def import_from_cache_snapshot(presupuesto: Dict, partidas: List[Dict]) -> ImportResult:
    """Crea (o reimporta como nueva version de) un budget canonico a partir
    de una fila `presupuesto` + sus `presupuesto_partida` ya existentes."""
    nombre_proyecto = (presupuesto or {}).get("nombre_proyecto", "")
    if not (nombre_proyecto or "").strip():
        return ImportResult(success=False, error="El presupuesto de origen no tiene nombre_proyecto.")

    lines, warnings = _normalize_lines(partidas)

    # Mismos importes por linea que persistira el repositorio (redondeados
    # individualmente antes de sumar), para que la comparacion de abajo use
    # exactamente el mismo total que quedara guardado.
    importes_linea = [calcular_importe_linea(l["cantidad"], l["precio"]) for l in lines]
    totales = calcular_totales(importes_linea)

    total_original = presupuesto.get("total")
    if total_original is not None and abs(float(total_original) - totales["total"]) > TOLERANCE_EUR:
        warnings.append(_warning(
            "TOTAL_MISMATCH",
            f"Total calculado ({totales['total']}) difiere del total leido "
            f"({total_original}) en {round(abs(float(total_original) - totales['total']), 2)} EUR.",
            {
                "calculado": totales["total"], "leido": float(total_original),
                "diferencia": round(abs(float(total_original) - totales["total"]), 2),
            },
        ))

    estado_inicial = "approved" if presupuesto.get("es_finalizado") else "draft"
    presupuesto_legacy_id = presupuesto.get("id")
    ruta_excel = (presupuesto.get("ruta_excel") or "").strip()

    existing = get_budget_by_legacy_id(presupuesto_legacy_id) if presupuesto_legacy_id else None

    if existing:
        version_id, err = start_new_version(existing["id"], lines, origen="import")
        if err:
            return ImportResult(success=False, error=err)
        budget_id = existing["id"]
        if estado_inicial == "approved":
            approve_active_version(budget_id, aprobado_por="migracion_automatica")
    else:
        budget_id, err = create_budget_with_first_version(
            nombre_proyecto=nombre_proyecto,
            lines=lines,
            numero_proyecto=presupuesto.get("numero_proyecto", ""),
            presupuesto_legacy_id=presupuesto_legacy_id,
            estado_inicial=estado_inicial,
        )
        if err:
            return ImportResult(success=False, error=err)
        version = get_active_version(budget_id)
        version_id = version["id"]

    if ruta_excel:
        register_document(version_id, "excel_import", ruta_excel)

    evidence_id, ev_err = record_evidence("legacy_excel", referencia=ruta_excel or f"presupuesto_legacy_id={presupuesto_legacy_id}")
    if not ev_err and evidence_id:
        for line in get_lines(version_id):
            for campo in ("precio", "cantidad", "concepto"):
                link_field_evidence(line["id"], campo, evidence_id)

    return ImportResult(
        success=True, budget_id=budget_id, budget_version_id=version_id, warnings=warnings,
    )
