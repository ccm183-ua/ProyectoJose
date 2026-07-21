"""
Deduplicación de sugerencias históricas presentadas al usuario (no altera la BD).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Tuple


def normalize_text_for_dedupe(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    lowered = without_accents.lower()
    cleaned = re.sub(r"[^\w\s]", " ", lowered)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:500]


def _concept_for_key(partida: Dict[str, Any]) -> str:
    p = partida or {}
    for key in ("concepto_original", "concepto", "titulo", "title"):
        val = p.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _precio_key(partida: Dict[str, Any]) -> float:
    p = partida or {}
    raw = p.get("precio_unitario", p.get("precio", 0))
    try:
        return round(float(str(raw).replace(",", ".")), 2)
    except (TypeError, ValueError):
        return 0.0


def _unidad_key(partida: Dict[str, Any]) -> str:
    p = partida or {}
    u = str(p.get("unidad") or p.get("ud") or "ud").strip().lower() or "ud"
    return u


def dedupe_key(partida: Dict[str, Any]) -> Tuple[str, str, float]:
    return (
        normalize_text_for_dedupe(_concept_for_key(partida)),
        _unidad_key(partida),
        _precio_key(partida),
    )


_STOPWORDS = frozenset(
    {
        "de",
        "la",
        "el",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "y",
        "o",
        "en",
        "con",
        "sin",
        "para",
        "por",
        "al",
        "del",
        "lo",
        "le",
        "les",
    }
)


def _module_key(partida: Dict[str, Any]) -> str:
    return str((partida or {}).get("module", "") or "").strip().lower()


def _sig_tokens(text: str, n: int = 10) -> Tuple[str, ...]:
    norm = normalize_text_for_dedupe(text)
    toks = [w for w in norm.split() if w and w not in _STOPWORDS and len(w) > 1]
    return tuple(toks[:n])


def _price_similar(a: float, b: float) -> bool:
    diff = abs(a - b)
    return diff <= max(2.0, 0.10 * max(abs(a), abs(b), 1.0))


def _concept_signature_similar(p: Dict[str, Any], q: Dict[str, Any]) -> bool:
    cp = _concept_for_key(p)
    cq = _concept_for_key(q)
    sp = _sig_tokens(cp, 10)
    sq = _sig_tokens(cq, 10)
    if not sp or not sq:
        return False
    if sp == sq:
        return True
    n = min(6, len(sp), len(sq))
    if n >= 4 and sp[:n] == sq[:n]:
        return True
    nsp = normalize_text_for_dedupe(cp)[:80]
    nsq = normalize_text_for_dedupe(cq)[:80]
    if len(nsp) >= 28 and len(nsq) >= 28 and (nsp.startswith(nsq[:40]) or nsq.startswith(nsp[:40])):
        return True
    return False


def _dedupe_similar_after_exact(partidas: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Oculta sugerencias casi duplicadas (mismo módulo, unidad, concepto muy parecido, precio cercano).
    Conserva la de mayor (confianza, frecuencia); orden estable respecto a la entrada.
    """
    if len(partidas) <= 1:
        return partidas, 0

    indexed = sorted(
        list(enumerate(partidas)),
        key=lambda t: _score_tuple(t[1], t[0]),
        reverse=True,
    )
    kept: List[Dict[str, Any]] = []
    removed = 0
    for _orig_i, p in indexed:
        is_dup = False
        for q in kept:
            if _module_key(p) != _module_key(q):
                continue
            if _unidad_key(p) != _unidad_key(q):
                continue
            if not _price_similar(_precio_key(p), _precio_key(q)):
                continue
            if _concept_signature_similar(p, q):
                is_dup = True
                break
        if is_dup:
            removed += 1
        else:
            kept.append(p)

    id_order = {id(x): i for i, x in enumerate(partidas)}
    kept.sort(key=lambda x: id_order.get(id(x), 0))
    return kept, removed


def _score_tuple(partida: Dict[str, Any], index: int) -> Tuple[float, int, int]:
    conf = float(partida.get("confidence", 0) or 0)
    freq = int(partida.get("historical_frequency", 0) or 0)
    return (conf, freq, -index)


def dedupe_historical_partidas(partidas: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Elimina duplicados exactos (concepto normalizado + unidad + precio) y luego casi duplicados
    (mismo módulo, unidad, concepto muy parecido, precio con tolerancia).
    Conserva la partida con mayor (confianza, frecuencia); a empate, la primera en lista.
    """
    if not partidas:
        return [], 0

    best_for_key: Dict[Tuple[str, str, float], Tuple[Tuple[float, int, int], int]] = {}
    for idx, p in enumerate(partidas):
        key = dedupe_key(p)
        sc = _score_tuple(p, idx)
        if key not in best_for_key or sc > best_for_key[key][0]:
            best_for_key[key] = (sc, idx)

    winner_indices = sorted({t[1] for t in best_for_key.values()})
    out = [partidas[i] for i in winner_indices]
    removed_exact = len(partidas) - len(out)

    out2, removed_similar = _dedupe_similar_after_exact(out)
    return out2, removed_exact + removed_similar


def dedupe_normalized_partidas(partidas: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Igual que dedupe_historical_partidas pero usando campos ya normalizados."""
    if not partidas:
        return [], 0

    def concept_norm(p: Dict[str, Any]) -> str:
        return str(p.get("titulo") or p.get("concepto") or "").strip()

    def key(p: Dict[str, Any]) -> Tuple[str, str, float]:
        return (
            normalize_text_for_dedupe(concept_norm(p)),
            str(p.get("unidad", "ud")).strip().lower() or "ud",
            round(float(p.get("precio_unitario", p.get("precio", 0)) or 0), 2),
        )

    best_for_key: Dict[Tuple[str, str, float], Tuple[Tuple[float, int, int], int]] = {}
    for idx, p in enumerate(partidas):
        k = key(p)
        conf = float(p.get("confidence", 0) or 0)
        freq = int(p.get("historical_frequency", 0) or 0)
        sc = (conf, freq, -idx)
        if k not in best_for_key or sc > best_for_key[k][0]:
            best_for_key[k] = (sc, idx)

    winner_indices = sorted({t[1] for t in best_for_key.values()})
    out = [partidas[i] for i in winner_indices]
    removed = len(partidas) - len(out)
    return out, removed


def _normalized_concept_key(p: Dict[str, Any]) -> Tuple[str, str, float]:
    c = str(p.get("titulo") or p.get("concepto") or "").strip()
    fake = {"concepto": c, "unidad": p.get("unidad"), "precio_unitario": p.get("precio_unitario", p.get("precio"))}
    return dedupe_key(fake)


def _merge_review_score(p: Dict[str, Any], index: int) -> Tuple[int, float, int, int]:
    origin_boost = 1 if p.get("_dedupe_origin") == "Histórica" else 0
    conf = float(p.get("confidence", 0) or 0)
    freq = int(p.get("historical_frequency", 0) or 0)
    return (origin_boost, conf, freq, -index)


def dedupe_merged_review_partidas(
    historical: List[Dict[str, Any]],
    ai_complement: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    """
    Elimina duplicados entre históricas normalizadas e IA complementaria.
    Ante misma clave, prioriza partida histórica; luego mayor confianza/frecuencia.
    """
    merged: List[Dict[str, Any]] = []
    for p in historical or []:
        q = dict(p)
        q["_dedupe_origin"] = "Histórica"
        merged.append(q)
    for p in ai_complement or []:
        q = dict(p)
        q["_dedupe_origin"] = "IA complementaria"
        merged.append(q)
    if not merged:
        return [], [], 0

    best_for_key: Dict[Tuple[str, str, float], Tuple[Tuple[int, float, int, int], int]] = {}
    for idx, p in enumerate(merged):
        k = _normalized_concept_key(p)
        sc = _merge_review_score(p, idx)
        if k not in best_for_key or sc > best_for_key[k][0]:
            best_for_key[k] = (sc, idx)

    keep_indices = sorted({t[1] for t in best_for_key.values()})
    kept = [merged[i] for i in keep_indices]
    removed = len(merged) - len(kept)

    hist_out: List[Dict[str, Any]] = []
    ai_out: List[Dict[str, Any]] = []
    for p in kept:
        origin = p.pop("_dedupe_origin", "")
        if origin == "Histórica":
            hist_out.append(p)
        else:
            ai_out.append(p)
    return hist_out, ai_out, removed


def exclude_existing_from_candidates(
    candidates: List[Dict[str, Any]],
    existing_partidas: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Filtra partidas candidatas (nuevas, para modo "añadir") frente a las que ya
    están en el presupuesto. Coincidencia exacta (concepto normalizado + unidad
    + precio) se descarta en silencio. Coincidencia de concepto + unidad con
    precio distinto no se descarta: se marca como posible duplicado dudoso
    (campo 'reason') para que la revisión la muestre en vez de ocultarla.
    """
    existing = existing_partidas or []
    existing_exact_keys = {dedupe_key(p) for p in existing}
    existing_concept_unit_keys = {dedupe_key(p)[:2] for p in existing}

    kept: List[Dict[str, Any]] = []
    for p in candidates or []:
        key = dedupe_key(p)
        if key in existing_exact_keys:
            continue
        item = dict(p)
        if key[:2] in existing_concept_unit_keys:
            item["reason"] = item.get("reason") or (
                "Posible duplicado: ya existe una partida similar con otro precio."
            )
        kept.append(item)
    return kept
