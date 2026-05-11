"""Servicio para enriquecimientos opcionales de presupuestos historicos."""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional

from src.core.ai_service import AIService
from src.core.prompts.historical_technical_description_v1 import (
    PROMPT_VERSION,
    SYSTEM_INSTRUCTIONS,
)
from src.core.repositories import (
    get_budget_enrichment,
    get_historical_budget,
    get_historical_budget_issues,
    get_historical_budget_modules,
    get_historical_budget_partidas,
    upsert_budget_enrichment,
)
from src.core.settings import Settings


ENRICHMENT_TYPE = "TECHNICAL_DESCRIPTION"
ALLOWED_ANALYSIS_STATUSES = {"VALID", "VALID_WITH_WARNINGS"}
PROTECTED_STATUSES = {"MANUAL", "APPROVED"}
MAX_PARTIDAS_FOR_AI = 80
MAX_DESCRIPTION_LENGTH = 900


class HistoricalTechnicalDescriptionAIClient:
    """Adaptador minimo sobre AIService para poder inyectar fakes en tests."""

    def __init__(self, ai_service: Optional[AIService] = None):
        self._ai_service = ai_service or AIService(api_key=Settings().get_api_key())

    def generate_technical_description(self, prompt: str) -> Dict[str, str]:
        text, error, model = self._ai_service.generate_text(prompt)
        return {"text": text, "error": error or "", "model": model or ""}


def generate_technical_description_for_budget(
    budget_id: int,
    force: bool = False,
    ai_client: Optional[Any] = None,
) -> Dict:
    candidate = inspect_technical_description_generation_candidate(budget_id, force=force)
    if candidate.get("status") == "error":
        return _result(budget_id, "error", candidate.get("message", "Error preparando generacion."))
    if not candidate.get("eligible"):
        return _result(
            budget_id,
            "skipped",
            candidate.get("message", ""),
            skipped_reason=candidate.get("reason", ""),
            input_hash=candidate.get("input_hash", ""),
        )

    payload = candidate["payload"]
    input_hash = candidate["input_hash"]

    client = ai_client or HistoricalTechnicalDescriptionAIClient()
    prompt = build_prompt(payload)
    ai_response = _call_ai_client(client, prompt)
    if ai_response.get("error"):
        return _result(budget_id, "error", ai_response["error"], input_hash=input_hash)

    parsed, validation_error = validate_ai_response(ai_response.get("text", ""))
    if validation_error:
        return _result(budget_id, "error", validation_error, input_hash=input_hash)

    metadata = {
        "main_works": parsed["main_works"],
        "elements": parsed["elements"],
        "zones": parsed["zones"],
        "materials": parsed["materials"],
        "warnings": parsed["warnings"],
        "input_truncated": payload.get("input_truncated", False),
        "total_partidas": payload.get("total_partidas", len(payload.get("partidas", []))),
        "partidas_sent": len(payload.get("partidas", [])),
    }
    warnings_json = json.dumps(parsed["warnings"], ensure_ascii=False)
    metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
    err = upsert_budget_enrichment(
        historical_budget_id=int(budget_id),
        enrichment_type=ENRICHMENT_TYPE,
        status="PENDING_REVIEW",
        source="AI",
        content=parsed["technical_description"],
        model=ai_response.get("model", ""),
        prompt_version=PROMPT_VERSION,
        input_hash=input_hash,
        confidence=parsed["confidence"],
        warnings=warnings_json,
        metadata_json=metadata_json,
    )
    if err:
        return _result(budget_id, "error", err, input_hash=input_hash)
    return _result(
        budget_id,
        "generated",
        "",
        content=parsed["technical_description"],
        confidence=parsed["confidence"],
        input_hash=input_hash,
    )


def inspect_technical_description_generation_candidate(budget_id: int, force: bool = False) -> Dict:
    budget = get_historical_budget(int(budget_id or 0))
    if not budget:
        return _candidate(budget_id, False, "not_found", "No se encontro el presupuesto historico.", status="error")

    analysis_status = (budget.get("analysis_status") or "").strip().upper()
    if analysis_status not in ALLOWED_ANALYSIS_STATUSES:
        return _candidate(
            budget_id,
            False,
            "not_eligible",
            f"Estado tecnico no apto: {analysis_status or 'desconocido'}.",
        )

    current = get_budget_enrichment(int(budget_id), ENRICHMENT_TYPE)
    if current:
        current_status = (current.get("status") or "").strip().upper()
        current_source = (current.get("source") or "").strip().upper()
        if not force and (current_status in PROTECTED_STATUSES or current_source == "MANUAL"):
            return _candidate(
                budget_id,
                False,
                "protected_description",
                "Ya existe una descripcion manual o aprobada.",
            )

    partidas_all = get_historical_budget_partidas(int(budget_id), limit=10000)
    if not partidas_all:
        return _candidate(budget_id, False, "no_partidas", "El presupuesto no tiene partidas extraidas.")
    if not _has_useful_partida_concepts(partidas_all):
        return _candidate(
            budget_id,
            False,
            "no_useful_partidas",
            "El presupuesto no tiene conceptos de partida aprovechables.",
        )

    payload = build_technical_description_input(budget, partidas_all=partidas_all)
    input_hash = calculate_input_hash(payload)
    if current and not force:
        current_hash = (current.get("input_hash") or "").strip()
        current_status = (current.get("status") or "").strip().upper()
        if current_hash == input_hash and current_status != "REJECTED":
            return _candidate(
                budget_id,
                False,
                "same_input_hash",
                "Ya existe una descripcion generada para los mismos datos.",
                input_hash=input_hash,
            )

    return _candidate(
        budget_id,
        True,
        "ready",
        "Apto para generar descripcion IA.",
        input_hash=input_hash,
        payload=payload,
    )


def classify_technical_description_generation_candidates(
    budget_ids: List[int],
    force: bool = False,
) -> Dict:
    details = [
        inspect_technical_description_generation_candidate(int(budget_id), force=force)
        for budget_id in (budget_ids or [])
    ]
    ready_ids = [d["budget_id"] for d in details if d.get("eligible")]
    counts = {
        "ready": 0,
        "not_eligible": 0,
        "protected_description": 0,
        "same_input_hash": 0,
        "no_partidas": 0,
        "no_useful_partidas": 0,
        "errors": 0,
    }
    for detail in details:
        reason = detail.get("reason", "")
        if detail.get("status") == "error":
            counts["errors"] += 1
        elif reason in counts:
            counts[reason] += 1
    return {
        "processed": len(budget_ids or []),
        "ready_ids": ready_ids,
        "counts": counts,
        "details": details,
    }


def format_generation_candidate_summary(classification: Dict) -> str:
    counts = classification.get("counts") or {}
    return (
        f"Seleccionados: {int(classification.get('processed', 0))}\n"
        f"Aptos para generacion: {int(counts.get('ready', 0))}\n"
        f"No aptos por estado tecnico: {int(counts.get('not_eligible', 0))}\n"
        f"Omitidos por descripcion manual/aprobada: {int(counts.get('protected_description', 0))}\n"
        f"Omitidos por mismo input_hash: {int(counts.get('same_input_hash', 0))}\n"
        f"Omitidos sin partidas: {int(counts.get('no_partidas', 0))}\n"
        f"Omitidos sin conceptos utiles: {int(counts.get('no_useful_partidas', 0))}\n"
        f"Errores preparando generacion: {int(counts.get('errors', 0))}"
    )


def generate_technical_descriptions_for_budgets(
    budget_ids: List[int],
    force: bool = False,
    ai_client: Optional[Any] = None,
) -> Dict:
    details = []
    summary = {"processed": len(budget_ids or []), "generated": 0, "skipped": 0, "errors": 0}
    for budget_id in budget_ids or []:
        result = generate_technical_description_for_budget(
            int(budget_id),
            force=force,
            ai_client=ai_client,
        )
        details.append(result)
        if result.get("status") == "generated":
            summary["generated"] += 1
        elif result.get("status") == "skipped":
            summary["skipped"] += 1
        else:
            summary["errors"] += 1
    summary["details"] = details
    return summary


def build_technical_description_input(budget: Dict, partidas_all: Optional[List[Dict]] = None) -> Dict:
    budget_id = int(budget.get("id") or 0)
    issues = get_historical_budget_issues(budget_id)
    modules = get_historical_budget_modules(budget_id)
    if partidas_all is None:
        partidas_all = get_historical_budget_partidas(budget_id, limit=10000)
    partidas = _select_relevant_partidas(partidas_all)
    return {
        "file_name": os.path.basename(budget.get("ruta_excel", "")),
        "project_name": budget.get("nombre_proyecto", ""),
        "client": budget.get("cliente", ""),
        "location": budget.get("localidad", ""),
        "work_type": budget.get("tipo_obra_normalizado") or budget.get("tipo_obra_original", ""),
        "total": budget.get("total"),
        "selected_sheet": budget.get("selected_sheet", ""),
        "modules": modules,
        "issues": [
            {
                "severity": issue.get("severity", ""),
                "code": issue.get("code", ""),
                "message": issue.get("message", ""),
            }
            for issue in issues
            if (issue.get("severity") or "").upper() in {"WARN", "SEVERE", "ERROR"}
        ],
        "partidas": [
            {
                "concepto": partida.get("concepto_original", ""),
                "unidad": partida.get("unidad", ""),
                "cantidad": partida.get("cantidad"),
                "precio_unitario": partida.get("precio_unitario"),
                "total_linea": partida.get("total_linea"),
            }
            for partida in partidas
        ],
        "total_partidas": len(partidas_all),
        "input_truncated": len(partidas_all) > len(partidas),
        "partidas_limit_note": (
            f"Se envian como maximo {MAX_PARTIDAS_FOR_AI} partidas, priorizando mayor importe y conservando el orden original."
        ),
    }


def build_prompt(payload: Dict) -> str:
    return (
        f"{SYSTEM_INSTRUCTIONS}\n\n"
        "Datos del presupuesto:\n"
        f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    )


def calculate_input_hash(payload: Dict) -> str:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_ai_response(response_text: str) -> tuple[Optional[Dict], Optional[str]]:
    try:
        data = json.loads(_extract_json_from_markdown(response_text))
    except (TypeError, json.JSONDecodeError):
        return None, "La IA no devolvio JSON valido."
    if not isinstance(data, dict):
        return None, "La respuesta de IA debe ser un objeto JSON."

    description = str(data.get("technical_description") or "").strip()
    if not description:
        return None, "La descripcion tecnica generada esta vacia."
    if len(description) > MAX_DESCRIPTION_LENGTH:
        return None, "La descripcion tecnica generada es demasiado larga."

    try:
        confidence = float(data.get("confidence"))
    except (TypeError, ValueError):
        return None, "La confianza devuelta por IA no es numerica."
    if confidence < 0 or confidence > 1:
        return None, "La confianza devuelta por IA debe estar entre 0 y 1."

    return {
        "technical_description": description,
        "main_works": _normalize_string_list(data.get("main_works")),
        "elements": _normalize_string_list(data.get("elements")),
        "zones": _normalize_string_list(data.get("zones")),
        "materials": _normalize_string_list(data.get("materials")),
        "confidence": confidence,
        "warnings": _normalize_string_list(data.get("warnings")),
    }, None


def _select_relevant_partidas(partidas: List[Dict]) -> List[Dict]:
    if len(partidas) <= MAX_PARTIDAS_FOR_AI:
        return partidas
    ranked = sorted(
        enumerate(partidas),
        key=lambda item: abs(float(item[1].get("total_linea") or 0.0)),
        reverse=True,
    )[:MAX_PARTIDAS_FOR_AI]
    selected_indexes = {idx for idx, _partida in ranked}
    return [partida for idx, partida in enumerate(partidas) if idx in selected_indexes]


def _has_useful_partida_concepts(partidas: List[Dict]) -> bool:
    for partida in partidas or []:
        for key in ("concepto_original", "titulo", "concepto_normalizado"):
            if str(partida.get(key) or "").strip():
                return True
    return False


def _candidate(
    budget_id: int,
    eligible: bool,
    reason: str,
    message: str,
    status: str = "ok",
    **extra,
) -> Dict:
    result = {
        "budget_id": int(budget_id or 0),
        "eligible": bool(eligible),
        "reason": reason,
        "message": message,
        "status": status,
    }
    result.update(extra)
    return result


def _call_ai_client(client: Any, prompt: str) -> Dict[str, str]:
    if not hasattr(client, "generate_technical_description"):
        return {"text": "", "error": "Cliente IA no compatible.", "model": ""}
    raw = client.generate_technical_description(prompt)
    if isinstance(raw, dict):
        return {
            "text": str(raw.get("text") or ""),
            "error": str(raw.get("error") or ""),
            "model": str(raw.get("model") or ""),
        }
    if isinstance(raw, tuple):
        text = raw[0] if len(raw) > 0 else ""
        error = raw[1] if len(raw) > 1 else ""
        model = raw[2] if len(raw) > 2 else ""
        return {"text": str(text or ""), "error": str(error or ""), "model": str(model or "")}
    return {"text": str(raw or ""), "error": "", "model": ""}


def _extract_json_from_markdown(text: str) -> str:
    clean = (text or "").strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", clean, re.DOTALL)
    return match.group(1).strip() if match else clean


def _normalize_string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    normalized = []
    for item in value:
        text = str(item or "").strip()
        if text:
            normalized.append(text[:120])
    return normalized


def _result(budget_id: int, status: str, message: str = "", **extra) -> Dict:
    result = {"budget_id": int(budget_id or 0), "status": status, "message": message}
    result.update(extra)
    return result
