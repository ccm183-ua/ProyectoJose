"""
Analizador de presupuestos históricos para inteligencia offline.
"""

import os
import re
from datetime import datetime
from typing import Dict, List, Optional

from src.core.budget_reader import BudgetReader
from src.core.historical_partida_classifier import HistoricalPartidaClassifier
from src.core.repositories import (
    assign_partida_module,
    create_analysis_run,
    delete_partidas_for_budget,
    finish_analysis_run,
    get_historical_budget_by_path,
    get_presupuesto_por_ruta,
    get_or_create_execution_module,
    insert_historical_partida,
    rebuild_budget_module_summary,
    upsert_historical_budget,
)
from src.core.work_type_normalizer import normalize_text, normalize_work_type


def _file_mtime_iso(path: str) -> Optional[str]:
    try:
        stat = os.stat(path)
        return datetime.fromtimestamp(stat.st_mtime).isoformat()
    except (OSError, ValueError):
        return None


def _guess_expected_numero(excel_path: str) -> str:
    """
    Intenta deducir el número de proyecto desde ruta/nombre de archivo.
    """
    candidates = [
        os.path.basename(excel_path),
        os.path.basename(os.path.dirname(excel_path)),
        excel_path,
    ]
    for text in candidates:
        match = re.search(r"\b(\d{1,4}-\d{2})\b", text)
        if match:
            return match.group(1)
    return ""


def _resolve_expected_numero(excel_path: str, existing: Optional[Dict]) -> str:
    """Resuelve numero esperado usando cache/repositorio antes de adivinar por nombre."""
    if existing and (existing.get("numero_proyecto") or "").strip():
        return existing["numero_proyecto"].strip()
    cached = get_presupuesto_por_ruta(excel_path)
    if cached and (cached.get("numero_proyecto") or "").strip():
        return str(cached["numero_proyecto"]).strip()
    return _guess_expected_numero(excel_path)


class HistoricalBudgetAnalyzer:
    """Analiza Excels históricos, persiste partidas y clasifica módulos."""

    def __init__(
        self,
        reader: Optional[BudgetReader] = None,
        classifier: Optional[HistoricalPartidaClassifier] = None,
    ):
        self.reader = reader or BudgetReader()
        self.classifier = classifier or HistoricalPartidaClassifier()

    def analyze_folder(self, folder_path: str, recursive: bool = True) -> Dict:
        excel_paths: List[str] = []
        if recursive:
            for root, _, files in os.walk(folder_path):
                for name in files:
                    if name.lower().endswith((".xlsx", ".xlsm")):
                        excel_paths.append(os.path.join(root, name))
        else:
            for name in os.listdir(folder_path):
                full_path = os.path.join(folder_path, name)
                if os.path.isfile(full_path) and name.lower().endswith((".xlsx", ".xlsm")):
                    excel_paths.append(full_path)
        return self.analyze_files(excel_paths, source_folder=folder_path)

    def analyze_files(self, excel_paths: List[str], source_folder: str = "") -> Dict:
        run_id, run_err = create_analysis_run(source_folder)
        if run_err:
            return {
                "total_archivos": len(excel_paths),
                "procesados": 0,
                "omitidos": 0,
                "errores": len(excel_paths),
                "run_id": None,
                "error": run_err,
            }

        summary = {
            "total_archivos": len(excel_paths),
            "procesados": 0,
            "omitidos": 0,
            "errores": 0,
            "warnings": 0,
            "warnings_detail": [],
            "run_id": run_id,
        }

        for path in excel_paths:
            result = self.analyze_budget(path, metadata={"analysis_run_id": run_id})
            status = result.get("status")
            if status == "processed":
                summary["procesados"] += 1
            elif status == "skipped":
                summary["omitidos"] += 1
            else:
                summary["errores"] += 1
            summary["warnings"] += int(result.get("warning_count", 0))
            if result.get("warnings"):
                summary["warnings_detail"].append(
                    {"excel_path": path, "warnings": result.get("warnings", [])}
                )

        # Regenerar patrones tras cada análisis (aunque solo haya omitidos),
        # para cubrir el caso de datos históricos ya cacheados sin patrones previos.
        try:
            from src.core.historical_pattern_builder import HistoricalPatternBuilder

            HistoricalPatternBuilder().rebuild_patterns()
        except Exception:
            summary["errores"] += 1

        finish_analysis_run(
            run_id,
            {
                "total_archivos": summary["total_archivos"],
                "procesados": summary["procesados"],
                "omitidos": summary["omitidos"],
                "errores": summary["errores"],
                "estado": "finished" if summary["errores"] == 0 else "finished_with_errors",
            },
        )
        return summary

    def analyze_budget(self, excel_path: str, metadata: Optional[Dict] = None) -> Dict:
        metadata = metadata or {}
        mtime = _file_mtime_iso(excel_path)
        if not mtime:
            return {"status": "error", "excel_path": excel_path, "error": "No se pudo leer mtime"}

        existing = get_historical_budget_by_path(excel_path)
        if existing and existing.get("fecha_modificacion_excel") == mtime and existing.get("analisis_ok"):
            return {"status": "skipped", "excel_path": excel_path}

        try:
            expected_numero = _resolve_expected_numero(excel_path, existing)
            read_result = self.reader.read(excel_path, expected_numero=expected_numero)
            if not read_result:
                raise ValueError("No se pudo leer el presupuesto con BudgetReader")

            cabecera = read_result.get("cabecera", {})
            partidas = read_result.get("partidas", [])
            tipo_original = cabecera.get("obra", "")
            warnings: List[str] = []
            severe_warnings: List[str] = []
            budget_payload = {
                "ruta_excel": excel_path,
                "ruta_carpeta": os.path.dirname(excel_path),
                "numero_proyecto": cabecera.get("numero", ""),
                "nombre_proyecto": os.path.basename(excel_path),
                "cliente": cabecera.get("cliente", ""),
                "localidad": "",
                "tipo_obra_original": tipo_original,
                "tipo_obra_normalizado": normalize_work_type(tipo_original),
                "estado": "",
                "total": read_result.get("total"),
                "fecha_presupuesto": cabecera.get("fecha", ""),
                "fecha_modificacion_excel": mtime,
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "num_partidas": len(partidas),
                "analysis_run_id": metadata.get("analysis_run_id"),
                "analisis_ok": True,
                "warning_count": 0,
                "warnings": "",
                "error": "",
            }
            if not expected_numero:
                warnings.append("Analizado sin numero esperado; posible seleccion incorrecta de hoja.")
            if not partidas:
                severe_warnings.append("Presupuesto sin partidas detectadas.")
            if float(read_result.get("total") or 0) <= 0:
                severe_warnings.append("Total de presupuesto cero o no detectado.")
            if partidas:
                zero_price = sum(
                    1 for p in partidas if float(p.get("precio") or 0) <= 0
                )
                if (zero_price / max(1, len(partidas))) >= 0.5:
                    severe_warnings.append("Mas del 50% de partidas con precio unitario cero.")

            all_warnings = [f"WARN:{w}" for w in warnings] + [f"SEVERE:{w}" for w in severe_warnings]
            if all_warnings:
                budget_payload["warning_count"] = len(all_warnings)
                budget_payload["warnings"] = " | ".join(all_warnings)
            budget_id, budget_err = upsert_historical_budget(budget_payload)
            if budget_err or not budget_id:
                raise RuntimeError(budget_err or "No se pudo guardar presupuesto histórico")

            delete_err = delete_partidas_for_budget(budget_id)
            if delete_err:
                raise RuntimeError(delete_err)

            for idx, partida in enumerate(partidas, start=1):
                concepto = (partida.get("concepto") or "").strip()
                partida_payload = {
                    "orden": idx,
                    "codigo": partida.get("numero", ""),
                    "titulo": concepto,
                    "descripcion": "",
                    "concepto_original": concepto,
                    "concepto_normalizado": normalize_text(concepto),
                    "unidad": partida.get("unidad", "ud"),
                    "cantidad": partida.get("cantidad", 1),
                    "precio_unitario": partida.get("precio", 0),
                    "total_linea": partida.get("importe"),
                    "capitulo": "",
                }
                partida_id, partida_err = insert_historical_partida(budget_id, partida_payload)
                if partida_err or not partida_id:
                    continue

                classifications = self.classifier.classify(
                    {
                        "titulo": concepto,
                        "descripcion": "",
                        "concepto": concepto,
                        "capitulo": "",
                    }
                )
                for row in classifications:
                    module_id, module_err = get_or_create_execution_module(row.get("module", ""))
                    if module_err or not module_id:
                        continue
                    assign_partida_module(
                        partida_id=partida_id,
                        module_id=module_id,
                        confidence=float(row.get("confidence") or 0),
                        source=row.get("source", "rules"),
                    )

            rebuild_budget_module_summary(budget_id)
            return {
                "status": "processed",
                "excel_path": excel_path,
                "historical_budget_id": budget_id,
                "warning_count": len(all_warnings),
                "warnings": all_warnings,
            }

        except Exception as exc:
            error_payload = {
                "ruta_excel": excel_path,
                "ruta_carpeta": os.path.dirname(excel_path),
                "fecha_modificacion_excel": mtime,
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "num_partidas": 0,
                "analysis_run_id": metadata.get("analysis_run_id"),
                "analisis_ok": False,
                "error": str(exc),
            }
            upsert_historical_budget(error_payload)
            return {"status": "error", "excel_path": excel_path, "error": str(exc)}
