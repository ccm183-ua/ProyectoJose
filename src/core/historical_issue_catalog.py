"""
Catalogo de codigos de incidencias del aprendizaje historico.
"""

KNOWN_HISTORICAL_ISSUE_CODES = {
    "SEVERE_NO_PARTIDAS": "No se han detectado partidas validas en el presupuesto.",
    "SEVERE_TOTAL_ZERO": "El presupuesto tiene total 0 o no se ha detectado correctamente.",
    "SEVERE_MANY_ZERO_PRICES": "Mas del 50% de las partidas tienen precio unitario <= 0.",
    "WARN_NO_EXPECTED_NUMERO": "No se pudo confirmar el numero de presupuesto esperado.",
    "WARN_NUMERO_MISMATCH": "El numero detectado no coincide con el numero esperado.",
    "WARN_LOW_PARTIDA_COUNT": "Se detectaron pocas partidas; conviene revisar.",
    "NO_PARTIDA_STRUCTURE": "El archivo no tiene una estructura de partidas compatible.",
    "NO_BUDGET_HEADER": "No se ha detectado la cabecera esperada del presupuesto.",
    "READ_ERROR": "Error tecnico durante la lectura del Excel.",
    "MANUALLY_EXCLUDED": "Archivo excluido manualmente del aprendizaje.",
    "MANUALLY_INCLUDED": "Archivo marcado manualmente como apto para aprendizaje.",
    "NO_WORKSHEETS": "No se encontraron hojas de calculo legibles.",
    "NO_PROBE_RESULT": "No se pudo evaluar la compatibilidad del archivo.",
}


def is_known_historical_issue_code(code: str) -> bool:
    return (code or "").strip().upper() in KNOWN_HISTORICAL_ISSUE_CODES


def historical_issue_label(code: str) -> str:
    return KNOWN_HISTORICAL_ISSUE_CODES.get(
        (code or "").strip().upper(),
        "Aviso del analisis historico.",
    )
