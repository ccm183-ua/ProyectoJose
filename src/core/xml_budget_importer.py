"""
Importador del XML de partidas redactado por Claude, contra el contrato de
docs/esquema-partidas-ia.md.

Dos pasos separados:
  1. parse_and_validate(): aplica el contrato del esquema. Un fallo de forma
     (XML mal formado, elemento no previsto) rechaza el fichero completo; un
     fallo de datos en una partida (modulo/unidad fuera de vocabulario,
     atributos ausentes) rechaza solo esa partida, con motivo.
  2. match_partidas_with_evidence(): cruza cada partida con estado="conocida"
     contra la evidencia historica real, con el mismo comparador determinista
     que usa el resto de la app (historical_comparator.compare_partida_features).
     Nunca inventa un precio: sin evidencia exact/comparable, la partida se
     marca 'sin_evidencia_ia' con precio 0 y motivo visible en la revision.

Las partidas con estado="pendiente" nunca llegan a match_partidas_with_evidence:
no tienen cantidad, no se pueden escribir en el Excel, y se listan aparte para
que el usuario sepa que faltan por medir.
"""

import xml.etree.ElementTree as ET
from dataclasses import replace
from typing import Dict, List, Tuple

from src.core import database
from src.core.historical_partida_classifier import HistoricalPartidaClassifier
from src.core.historical_partida_features import extract_partida_features
from src.core.historical_suggestion_service import find_comparable_evidence

_ALLOWED_ELEMENTS = {"concepto", "unidad", "cantidad", "modulo", "nueva"}
_ALLOWED_ESTADOS = {"conocida", "pendiente"}


def _load_valid_modules(conn) -> set:
    return {
        row[0]
        for row in conn.execute("SELECT nombre FROM execution_module WHERE activo = 1").fetchall()
    }


def _load_valid_units(conn) -> set:
    return {
        row[0].strip().lower()
        for row in conn.execute(
            """SELECT DISTINCT hp.unidad
               FROM historical_partida hp
               JOIN historical_budget hb ON hb.id = hp.historical_budget_id
               WHERE hb.learning_status = 'INCLUDED' AND hp.precio_unitario > 0
                 AND hp.unidad IS NOT NULL AND hp.unidad <> ''"""
        ).fetchall()
        if row[0]
    }


def parse_and_validate(xml_path: str) -> Dict:
    """Aplica el contrato de docs/esquema-partidas-ia.md.

    Devuelve:
        {
            "ok": bool,                # False = fichero completo rechazado
            "error": str | None,
            "aceptadas": [ {concepto, unidad, cantidad, estado, modulo, nueva}, ... ],
            "rechazadas": [ {concepto, motivo}, ... ],  # rechazo por partida
        }
    """
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as exc:
        return {"ok": False, "error": f"XML mal formado: {exc}", "aceptadas": [], "rechazadas": []}

    root = tree.getroot()
    if root.tag != "presupuesto":
        return {
            "ok": False,
            "error": f"Elemento raiz '<{root.tag}>' distinto de '<presupuesto>'.",
            "aceptadas": [], "rechazadas": [],
        }

    partida_nodes = root.findall("partida")
    if not partida_nodes:
        return {
            "ok": False,
            "error": "El fichero no contiene ninguna <partida>.",
            "aceptadas": [], "rechazadas": [],
        }

    # Un elemento no previsto en cualquier partida (p.ej. <precio>) rechaza el
    # fichero completo: es la senal de que el contrato en si se ha roto.
    for node in partida_nodes:
        for child in node:
            if child.tag not in _ALLOWED_ELEMENTS:
                return {
                    "ok": False,
                    "error": (
                        f"Elemento no previsto en el esquema: <{child.tag}>. "
                        "El fichero completo se rechaza."
                    ),
                    "aceptadas": [], "rechazadas": [],
                }

    with database.get_connection(read_only=True) as conn:
        valid_modules = _load_valid_modules(conn)
        valid_units = _load_valid_units(conn)

    aceptadas: List[Dict] = []
    rechazadas: List[Dict] = []
    for node in partida_nodes:
        concepto = (node.findtext("concepto") or "").strip()
        unidad = (node.findtext("unidad") or "").strip()
        modulo = (node.findtext("modulo") or "").strip()
        nueva_text = node.findtext("nueva")
        cantidad_node = node.find("cantidad")

        motivo = None
        if not concepto:
            motivo = "concepto vacio."
        elif cantidad_node is None or "estado" not in cantidad_node.attrib:
            motivo = "falta el atributo 'estado' en <cantidad>."
        elif cantidad_node.attrib["estado"] not in _ALLOWED_ESTADOS:
            motivo = f"estado de cantidad no reconocido: '{cantidad_node.attrib['estado']}'."
        elif nueva_text is None or nueva_text.strip().lower() not in {"true", "false"}:
            motivo = "falta o no es valido el elemento <nueva> (debe ser 'true' o 'false')."
        elif not modulo:
            motivo = "modulo vacio."
        elif modulo not in valid_modules:
            motivo = f"modulo '{modulo}' no esta en el vocabulario cerrado de esta empresa."
        elif not unidad or unidad.lower() not in valid_units:
            motivo = f"unidad '{unidad}' no esta entre las unidades observadas en el historico."

        if motivo is None:
            estado = cantidad_node.attrib["estado"]
            if estado == "conocida":
                cantidad_text = (cantidad_node.text or "").strip()
                try:
                    from src.core.budget_math import parse_decimal_es

                    cantidad = parse_decimal_es(cantidad_text)
                except (TypeError, ValueError):
                    motivo = f"cantidad no numerica: '{cantidad_text}'."
            else:
                cantidad = None

        if motivo:
            rechazadas.append({"concepto": concepto or "(sin concepto)", "motivo": motivo})
            continue

        aceptadas.append({
            "concepto": concepto,
            "unidad": unidad,
            "cantidad": cantidad,
            "estado": cantidad_node.attrib["estado"],
            "modulo": modulo,
            "nueva": nueva_text.strip().lower() == "true",
        })

    return {"ok": True, "error": None, "aceptadas": aceptadas, "rechazadas": rechazadas}


def match_partidas_with_evidence(aceptadas: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Separa las partidas aceptadas en (listas_para_revision, pendientes_de_medida).

    Para cada partida con estado='conocida', fuerza el modulo ya confirmado en
    el XML (no el que detectaria un clasificador de texto libre) y cruza
    accion/elemento/unidad contra la evidencia real del mismo modulo. Sin
    evidencia 'exact'/'comparable', el precio queda en 0 y el motivo lo dice
    explicitamente -- nunca se inventa una cifra para no dejar un hueco.
    """
    listas: List[Dict] = []
    pendientes: List[Dict] = []
    classifier = HistoricalPartidaClassifier()

    for p in aceptadas:
        if p["estado"] == "pendiente":
            pendientes.append(p)
            continue

        candidates = classifier.classify_text(p["concepto"])
        features = extract_partida_features(p["concepto"], p["unidad"], candidates)
        features = replace(
            features,
            primary_module_id=p["modulo"],
            is_price_eligible=(
                features.line_kind == "atomic"
                and bool(features.unit)
                and bool(features.action)
                and bool(features.element)
            ),
        )

        evidence = find_comparable_evidence(features)
        priced = [c for c in evidence if c.comparison.level in ("exact", "comparable")]

        base = {
            "concepto": p["concepto"],
            "titulo": p["concepto"],
            "unidad": p["unidad"],
            "cantidad": p["cantidad"],
            "modulo": p["modulo"],
            "nueva": p["nueva"],
        }

        if priced:
            prices = sorted(c.precio_unitario for c in priced)
            n = len(prices)
            median_price = prices[n // 2] if n % 2 else (prices[n // 2 - 1] + prices[n // 2]) / 2
            level = "exact" if any(c.comparison.level == "exact" for c in priced) else "comparable"
            base.update({
                "source": f"historical_{level}",
                "evidence_level": level,
                "precio_unitario": round(median_price, 2),
                "evidence_price_min": round(prices[0], 2),
                "evidence_price_median": round(median_price, 2),
                "evidence_price_max": round(prices[-1], 2),
                "evidence_budget_ids": sorted({c.historical_budget_id for c in priced}),
                "reason": (
                    f"{'Partida nueva, ' if p['nueva'] else ''}"
                    f"evidencia {level} en {len(priced)} partida(s) historica(s)."
                ),
            })
        else:
            base.update({
                "source": "sin_evidencia_ia",
                "evidence_level": None,
                "precio_unitario": 0.0,
                "reason": (
                    "Sin evidencia comparable en el historico -- completar precio "
                    "a mano antes de aceptar esta partida."
                ),
            })
        listas.append(base)

    return listas, pendientes
