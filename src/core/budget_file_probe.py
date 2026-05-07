"""
Probe de compatibilidad para presupuestos históricos.
"""

import re
from typing import Dict, List

from src.core.budget_reader import BudgetReader
from src.utils.budget_utils import normalize_project_num


class BudgetFileProbe:
    def __init__(self, reader: BudgetReader | None = None):
        self.reader = reader or BudgetReader()

    def probe(self, file_path: str, expected_numero: str = "") -> Dict:
        file_bytes = self.reader._load_file_bytes(file_path)
        if file_bytes is None:
            return self._empty_result(expected_numero, "ERROR", "READ_ERROR", "No se pudo abrir el archivo Excel.")

        shared_strings = self.reader._read_shared_strings(file_bytes)
        sheets = self.reader._read_all_sheets(file_bytes)
        if not sheets:
            return self._empty_result(expected_numero, "WARN", "NO_WORKSHEETS", "No se encontraron hojas de cálculo legibles.")

        best = None
        norm_expected = normalize_project_num(expected_numero) if expected_numero else ""
        for sheet in sheets:
            rows = self.reader._extract_rows(sheet["sheet_xml"])
            header = self.reader._extract_header(rows, shared_strings)
            partidas = self.reader._extract_partidas(rows, shared_strings)
            totals = self.reader._read_totals_from_cells(rows, shared_strings)
            total = float((totals or {}).get("total") or 0.0)
            has_positive_price = any(float(p.get("precio") or 0.0) > 0 for p in partidas)
            detected_numero = (header.get("numero") or "").strip()
            score = self._score_sheet(
                header=header,
                partidas_count=len(partidas),
                total=total,
                expected_numero=expected_numero,
                detected_numero=detected_numero,
                has_positive_price=has_positive_price,
                has_budget_terms=self._contains_budget_terms(rows, shared_strings),
            )
            item = {
                "sheet_name": sheet.get("sheet_name", ""),
                "sheet_index": sheet.get("sheet_index"),
                "score": score,
                "header": header,
                "partidas_count": len(partidas),
                "total": total,
                "detected_numero": detected_numero,
                "numero_matches": bool(
                    norm_expected
                    and normalize_project_num(detected_numero)
                    and normalize_project_num(detected_numero) == norm_expected
                ),
            }
            if best is None or item["score"] > best["score"]:
                best = item

        if best is None:
            return self._empty_result(expected_numero, "WARN", "NO_PROBE_RESULT", "No se pudo evaluar la compatibilidad del archivo.")

        issues: List[Dict] = []
        if best["partidas_count"] <= 0:
            issues.append(
                {
                    "severity": "WARN",
                    "code": "NO_PARTIDA_STRUCTURE",
                    "message": "No se detectaron filas de partidas en formato esperado.",
                }
            )
        if not best["detected_numero"]:
            issues.append(
                {
                    "severity": "WARN",
                    "code": "NO_BUDGET_HEADER",
                    "message": "No se detectó número de presupuesto en cabecera.",
                }
            )

        forced_compatible = bool(best["partidas_count"] > 0 and best["detected_numero"])
        is_compatible = best["score"] >= 12 or (best["score"] >= 7 and best["partidas_count"] > 0) or forced_compatible

        return {
            "is_compatible": is_compatible,
            "score": int(best["score"]),
            "selected_sheet": best["sheet_name"],
            "selected_sheet_index": best["sheet_index"],
            "expected_numero": expected_numero or "",
            "detected_numero": best["detected_numero"],
            "numero_matches": bool(best["numero_matches"]),
            "header_score": int(self._header_score(best["header"], expected_numero, best["detected_numero"])),
            "partida_score": int(self._partida_score(best["partidas_count"], best["total"])),
            "partidas_detectadas": int(best["partidas_count"]),
            "total_detectado": float(best["total"]),
            "issues": issues,
        }

    def _score_sheet(
        self,
        header: Dict,
        partidas_count: int,
        total: float,
        expected_numero: str,
        detected_numero: str,
        has_positive_price: bool,
        has_budget_terms: bool,
    ) -> int:
        return self._header_score(
            header,
            expected_numero,
            detected_numero,
            has_budget_terms,
        ) + self._partida_score(partidas_count, total, has_positive_price)

    @staticmethod
    def _header_score(header: Dict, expected_numero: str, detected_numero: str, has_budget_terms: bool) -> int:
        score = 0
        if re.search(r"\b\d{1,4}[/-]\d{2}\b", detected_numero or ""):
            score += 5
        if expected_numero and normalize_project_num(expected_numero) == normalize_project_num(detected_numero):
            score += 5
        if (header.get("cliente") or "").strip():
            score += 3
        if (header.get("obra") or "").strip():
            score += 3
        if has_budget_terms:
            score += 2
        return score

    @staticmethod
    def _partida_score(partidas_count: int, total: float, has_positive_price: bool) -> int:
        score = min(10, max(0, int(partidas_count)))
        if total > 0:
            score += 4
        if partidas_count <= 0:
            score -= 5
        if total <= 0 and not has_positive_price:
            score -= 5
        return score

    @staticmethod
    def _contains_budget_terms(rows: Dict[int, Dict], shared_strings: List[str]) -> bool:
        terms = ("PRESUPUESTO", "TOTAL PRESUPUESTO", "I.V.A")
        for row_num in sorted(rows.keys()):
            if row_num > 120:
                break
            row = rows[row_num]
            text = " ".join(
                BudgetReader._get_cell_value(cell, shared_strings).upper()
                for cell in row.values()
            )
            if any(term in text for term in terms):
                return True
        return False

    @staticmethod
    def _empty_result(expected_numero: str, severity: str, code: str, message: str) -> Dict:
        return {
            "is_compatible": False,
            "score": 0,
            "selected_sheet": "",
            "selected_sheet_index": None,
            "expected_numero": expected_numero or "",
            "detected_numero": "",
            "numero_matches": False,
            "header_score": 0,
            "partida_score": 0,
            "partidas_detectadas": 0,
            "total_detectado": 0.0,
            "issues": [{"severity": severity, "code": code, "message": message}],
        }
