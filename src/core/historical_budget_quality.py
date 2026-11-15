"""
Validador de calidad económica para aprendizaje histórico.
"""

from typing import Dict, List


def validate_budget_quality(read_result: Dict, expected_numero: str = "") -> Dict:
    partidas = read_result.get("partidas", []) or []
    total = float(read_result.get("total") or 0.0)
    subtotal = float(read_result.get("subtotal") or 0.0)
    diagnostics = read_result.get("diagnostics", {}) or {}
    issues: List[Dict] = []

    if not partidas:
        issues.append(
            {
                "severity": "SEVERE",
                "code": "SEVERE_NO_PARTIDAS",
                "message": "No hay partidas detectadas.",
            }
        )
    if total <= 0 and subtotal <= 0:
        issues.append(
            {
                "severity": "SEVERE",
                "code": "SEVERE_TOTAL_ZERO",
                "message": "Total y subtotal no válidos (<= 0).",
            }
        )
    if partidas:
        zero_price = sum(1 for p in partidas if float(p.get("precio") or 0) <= 0)
        if zero_price / max(1, len(partidas)) > 0.5:
            issues.append(
                {
                    "severity": "SEVERE",
                    "code": "SEVERE_MANY_ZERO_PRICES",
                    "message": "Más del 50% de partidas tienen precio unitario <= 0.",
                }
            )
    if not expected_numero:
        issues.append(
            {
                "severity": "WARN",
                "code": "WARN_NO_EXPECTED_NUMERO",
                "message": "No se pudo resolver número esperado.",
            }
        )
    if expected_numero and diagnostics.get("detected_numero") and not diagnostics.get("numero_matches"):
        issues.append(
            {
                "severity": "WARN",
                "code": "WARN_NUMERO_MISMATCH",
                "message": "Número detectado no coincide con número esperado.",
            }
        )
    if len(partidas) == 1:
        issues.append(
            {
                "severity": "WARN",
                "code": "WARN_LOW_PARTIDA_COUNT",
                "message": "Solo se detectó una partida; conviene revisar.",
            }
        )

    has_severe = any(i["severity"] == "SEVERE" for i in issues)
    has_warn = any(i["severity"] == "WARN" for i in issues)
    return {"issues": issues, "has_severe": has_severe, "has_warn": has_warn}
