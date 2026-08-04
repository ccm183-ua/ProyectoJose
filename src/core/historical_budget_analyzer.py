"""
Analizador de presupuestos históricos para inteligencia offline.
"""

import hashlib
import os
import re
import json
from dataclasses import asdict
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from src.core.budget_reader import BudgetReader
from src.core.budget_file_probe import BudgetFileProbe
from src.core.historical_partida_classifier import HistoricalPartidaClassifier
from src.core.historical_partida_features import extract_partida_features
from src.core.historical_analysis_status import AnalysisStatus, IssueSeverity
from src.core.historical_budget_quality import validate_budget_quality
from src.core.repositories import (
    assign_partida_module,
    clear_historical_partida_modules_for_budget,
    create_analysis_run,
    delete_partidas_for_budget,
    find_historical_budget_by_sha256,
    finish_analysis_run,
    get_historical_budget_by_path,
    get_historical_partidas_for_classification,
    get_presupuesto_por_ruta,
    get_or_create_execution_module,
    insert_historical_partida,
    rebuild_budget_module_summary,
    replace_budget_issues,
    upsert_historical_budget,
    upsert_partida_features,
)
from src.core.work_type_normalizer import normalize_text, normalize_work_type


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _safe_json_dumps(data: Dict) -> str:
    """Serializa datos de diagnóstico sin romper el flujo por tipos no JSON."""
    try:
        return json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return "{}"


def _apply_existing_manual_learning_decision(budget_payload: Dict, existing: Optional[Dict]) -> None:
    """Conserva decisiones manuales cuando el nuevo análisis sigue siendo apto."""
    if not existing:
        return
    if (existing.get("learning_status_source") or "").strip().upper() != "MANUAL":
        return

    previous_status = (existing.get("learning_status") or "").strip().upper()
    if previous_status == "EXCLUDED":
        budget_payload["usable_for_learning"] = False
        budget_payload["learning_status"] = "EXCLUDED"
        budget_payload["learning_status_source"] = "MANUAL"
        budget_payload["learning_decision_reason"] = existing.get("learning_decision_reason") or "Decision manual preservada tras reanalisis."
        budget_payload["learning_decision_at"] = existing.get("learning_decision_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return

    if previous_status != "INCLUDED":
        return

    if budget_payload.get("analysis_status") in (AnalysisStatus.VALID, AnalysisStatus.VALID_WITH_WARNINGS):
        budget_payload["usable_for_learning"] = True
        budget_payload["learning_status"] = "INCLUDED"
        budget_payload["learning_status_source"] = "MANUAL"
        budget_payload["learning_decision_reason"] = existing.get("learning_decision_reason") or "Decision manual preservada tras reanalisis."
        budget_payload["learning_decision_at"] = existing.get("learning_decision_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class HistoricalBudgetAnalyzer:
    """Analiza Excels históricos, persiste partidas y clasifica módulos."""

    ANALYZER_VERSION = "historical_budget_analyzer_v2"
    PROBE_VERSION = "budget_file_probe_v2"
    READER_VERSION = "budget_reader_v1"
    QUALITY_RULES_VERSION = "budget_quality_v1"
    CLASSIFIER_VERSION = "historical_partida_classifier_v1"

    def __init__(
        self,
        reader: Optional[BudgetReader] = None,
        classifier: Optional[HistoricalPartidaClassifier] = None,
    ):
        self.reader = reader or BudgetReader()
        self.classifier = classifier or HistoricalPartidaClassifier()
        self.probe = BudgetFileProbe(self.reader)

    @staticmethod
    def _collect_excel_paths(folder_path: str, recursive: bool) -> List[str]:
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
        return excel_paths

    def analyze_folder(
        self, folder_path: str, recursive: bool = True, force_reanalyze: bool = False
    ) -> Dict:
        excel_paths = self._collect_excel_paths(folder_path, recursive)
        return self.analyze_files(
            excel_paths, source_folder=folder_path, force_reanalyze=force_reanalyze
        )

    def analyze_folders(
        self, folder_paths: List[str], recursive: bool = True, force_reanalyze: bool = False
    ) -> Dict:
        """Como analyze_folder pero para varias carpetas a la vez: un único
        run_id, un único backup y una única reconstrucción de patrones al
        final, en vez de repetir el proceso completo carpeta a carpeta."""
        excel_paths: List[str] = []
        seen = set()
        for folder_path in folder_paths:
            for path in self._collect_excel_paths(folder_path, recursive):
                if path not in seen:
                    seen.add(path)
                    excel_paths.append(path)
        return self.analyze_files(
            excel_paths,
            source_folder="; ".join(folder_paths),
            force_reanalyze=force_reanalyze,
        )

    def analyze_files(
        self,
        excel_paths: List[str],
        source_folder: str = "",
        force_reanalyze: bool = False,
        source_kind: str = "external_excel",
    ) -> Dict:
        if len(excel_paths or []) > 1:
            try:
                from src.core.database_backup import create_database_backup

                create_database_backup("before_historical_analysis_batch")
            except Exception:
                pass
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
            "status_counts": {
                AnalysisStatus.VALID: 0,
                AnalysisStatus.VALID_WITH_WARNINGS: 0,
                AnalysisStatus.EXCLUDED_INCOMPLETE_DATA: 0,
                AnalysisStatus.NOT_COMPATIBLE: 0,
                AnalysisStatus.READ_ERROR: 0,
                AnalysisStatus.SKIPPED_UNCHANGED: 0,
                AnalysisStatus.MANUALLY_EXCLUDED: 0,
            },
            "run_id": run_id,
        }

        for path in excel_paths:
            result = self.analyze_budget(
                path,
                metadata={"analysis_run_id": run_id},
                force_reanalyze=force_reanalyze,
                source_kind=source_kind,
            )
            status = result.get("status")
            if status == "processed":
                summary["procesados"] += 1
            elif status == "skipped":
                summary["omitidos"] += 1
            else:
                summary["errores"] += 1
            analysis_status = result.get("analysis_status")
            if analysis_status in summary["status_counts"]:
                summary["status_counts"][analysis_status] += 1
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

    def analyze_budget(
        self,
        excel_path: str,
        metadata: Optional[Dict] = None,
        force_reanalyze: bool = False,
        source_kind: str = "external_excel",
    ) -> Dict:
        metadata = metadata or {}
        mtime = _file_mtime_iso(excel_path)
        if not mtime:
            return {"status": "error", "excel_path": excel_path, "error": "No se pudo leer mtime"}

        existing = get_historical_budget_by_path(excel_path)
        if (
            not force_reanalyze
            and existing
            and existing.get("fecha_modificacion_excel") == mtime
            and existing.get("analisis_ok")
        ):
            return {
                "status": "skipped",
                "excel_path": excel_path,
                "analysis_status": AnalysisStatus.SKIPPED_UNCHANGED,
            }

        try:
            file_hash = sha256_file(excel_path)
        except OSError:
            file_hash = ""

        if file_hash:
            duplicate = find_historical_budget_by_sha256(file_hash)
            existing_id = existing.get("id") if existing else None
            if duplicate and duplicate.get("id") != existing_id:
                # Mismo contenido ya importado bajo otra ruta: no se tocan
                # partidas ni patrones, se devuelve la referencia al original.
                return {
                    "status": "duplicate",
                    "excel_path": excel_path,
                    "duplicate_of_budget_id": duplicate["id"],
                    "analysis_status": duplicate.get("analysis_status", ""),
                }

        probe_diagnostics_json = ""
        try:
            expected_numero = _resolve_expected_numero(excel_path, existing)
            probe_result = self.probe.probe(excel_path, expected_numero=expected_numero)
            probe_diagnostics_json = _safe_json_dumps(probe_result)
            if not probe_result.get("is_compatible"):
                budget_payload = {
                    "ruta_excel": excel_path,
                    "ruta_carpeta": os.path.dirname(excel_path),
                    "numero_proyecto": "",
                    "nombre_proyecto": os.path.basename(excel_path),
                    "cliente": "",
                    "localidad": "",
                    "tipo_obra_original": "",
                    "tipo_obra_normalizado": "",
                    "estado": "",
                    "total": 0.0,
                    "fecha_presupuesto": "",
                    "fecha_modificacion_excel": mtime,
                    "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "num_partidas": int(probe_result.get("partidas_detectadas", 0)),
                    "analysis_run_id": metadata.get("analysis_run_id"),
                    "analisis_ok": True,
                    "warning_count": len(probe_result.get("issues", [])),
                    "warnings": " | ".join(
                        f"{i.get('severity', 'WARN')}:{i.get('message', '')}"
                        for i in probe_result.get("issues", [])
                    ),
                    "analysis_status": AnalysisStatus.NOT_COMPATIBLE,
                    "compatible_score": int(probe_result.get("score") or 0),
                    "selected_sheet": probe_result.get("selected_sheet") or "",
                    "selected_sheet_index": probe_result.get("selected_sheet_index"),
                    "expected_numero": probe_result.get("expected_numero") or "",
                    "detected_numero": probe_result.get("detected_numero") or "",
                    "numero_matches": bool(probe_result.get("numero_matches")),
                    "usable_for_learning": False,
                    "learning_status": "NOT_ELIGIBLE",
                    "learning_status_source": "AUTO",
                    "learning_decision_reason": "Archivo no compatible con estructura de presupuesto.",
                    "learning_decision_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "analyzer_version": self.ANALYZER_VERSION,
                    "probe_version": self.PROBE_VERSION,
                    "reader_version": self.READER_VERSION,
                    "quality_rules_version": self.QUALITY_RULES_VERSION,
                    "classifier_version": self.CLASSIFIER_VERSION,
                    "probe_diagnostics_json": probe_diagnostics_json,
                    "header_score": int(probe_result.get("header_score") or 0),
                    "partida_score": int(probe_result.get("partida_score") or 0),
                    "error": "",
                    "source_kind": source_kind,
                    "file_sha256": file_hash or None,
                }
                _apply_existing_manual_learning_decision(budget_payload, existing)
                budget_id, budget_err = upsert_historical_budget(budget_payload)
                if budget_err or not budget_id:
                    raise RuntimeError(budget_err or "No se pudo guardar presupuesto histórico")
                replace_budget_issues(budget_id, probe_result.get("issues", []))
                return {
                    "status": "processed",
                    "excel_path": excel_path,
                    "historical_budget_id": budget_id,
                    "analysis_status": AnalysisStatus.NOT_COMPATIBLE,
                    "warning_count": len(probe_result.get("issues", [])),
                    "warnings": [
                        f"{i.get('severity', 'WARN')}:{i.get('message', '')}"
                        for i in probe_result.get("issues", [])
                    ],
                }

            read_result = self.reader.read(
                excel_path,
                expected_numero=expected_numero,
                include_diagnostics=True,
            )
            if not read_result:
                raise ValueError("No se pudo leer el presupuesto con BudgetReader")

            cabecera = read_result.get("cabecera", {})
            partidas = read_result.get("partidas", [])
            tipo_original = cabecera.get("obra", "")
            warnings: List[str] = []
            severe_warnings: List[str] = []
            issues: List[Dict] = list(probe_result.get("issues", []))
            diagnostics = read_result.get("diagnostics", {})
            detected_numero = (diagnostics.get("detected_numero") or cabecera.get("numero") or "").strip()
            numero_matches = bool(diagnostics.get("numero_matches"))
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
                "analysis_status": AnalysisStatus.VALID,
                "compatible_score": int(probe_result.get("score") or 0),
                "selected_sheet": diagnostics.get("selected_sheet") or probe_result.get("selected_sheet") or "",
                "selected_sheet_index": diagnostics.get("selected_sheet_index") or probe_result.get("selected_sheet_index"),
                "expected_numero": expected_numero,
                "detected_numero": detected_numero,
                "numero_matches": numero_matches,
                # Contrato (fixes histórico evidenciado, Tarea 1): TODO origen
                # nuevo empieza PENDING_REVIEW, sin excepción por source_kind.
                # Solo approve_budget_for_learning() puede pasar a INCLUDED.
                "usable_for_learning": False,
                "learning_status": "PENDING_REVIEW",
                "learning_status_source": "AUTO",
                "learning_decision_reason": "Requiere aprobación explícita antes de aprender.",
                "learning_decision_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analyzer_version": self.ANALYZER_VERSION,
                "probe_version": self.PROBE_VERSION,
                "reader_version": self.READER_VERSION,
                "quality_rules_version": self.QUALITY_RULES_VERSION,
                "classifier_version": self.CLASSIFIER_VERSION,
                "probe_diagnostics_json": probe_diagnostics_json,
                "header_score": int(probe_result.get("header_score") or 0),
                "partida_score": int(probe_result.get("partida_score") or 0),
                "error": "",
                "source_kind": source_kind,
                "file_sha256": file_hash or None,
            }
            quality = validate_budget_quality(read_result, expected_numero=expected_numero)
            issues.extend(quality.get("issues", []))
            for issue in quality.get("issues", []):
                if issue.get("severity") == IssueSeverity.SEVERE:
                    severe_warnings.append(issue.get("message", ""))
                elif issue.get("severity") == IssueSeverity.WARN:
                    warnings.append(issue.get("message", ""))

            if quality.get("has_severe"):
                budget_payload["analysis_status"] = AnalysisStatus.EXCLUDED_INCOMPLETE_DATA
                budget_payload["usable_for_learning"] = False
                budget_payload["learning_status"] = "NOT_ELIGIBLE"
                budget_payload["learning_status_source"] = "AUTO"
                budget_payload["learning_decision_reason"] = "Datos economicos incompletos o invalidos."
                budget_payload["learning_decision_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            elif quality.get("has_warn"):
                budget_payload["analysis_status"] = AnalysisStatus.VALID_WITH_WARNINGS
                # Los presupuestos con avisos quedan pendientes de aprobacion manual.
                budget_payload["usable_for_learning"] = False
                budget_payload["learning_status"] = "PENDING_REVIEW"
                budget_payload["learning_status_source"] = "AUTO"
                budget_payload["learning_decision_reason"] = "Requiere revision manual por avisos."
                budget_payload["learning_decision_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            all_warnings = [f"WARN:{w}" for w in warnings] + [f"SEVERE:{w}" for w in severe_warnings]
            if all_warnings:
                budget_payload["warning_count"] = len(all_warnings)
                budget_payload["warnings"] = " | ".join(all_warnings)
            _apply_existing_manual_learning_decision(budget_payload, existing)
            budget_id, budget_err = upsert_historical_budget(budget_payload)
            if budget_err or not budget_id:
                raise RuntimeError(budget_err or "No se pudo guardar presupuesto histórico")
            replace_budget_issues(budget_id, issues)

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

                if budget_payload["usable_for_learning"]:
                    # classify() ahora devuelve un único módulo principal; aquí se
                    # mantiene classify_text() (lista sin colapsar) porque esta
                    # asignación en historical_partida_module es de solo
                    # clasificación/consulta, no de construcción de patrones de
                    # precio (eso lo restringe la Tarea 9 al módulo principal).
                    classifications = self.classifier.classify_text(concepto)
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
                "analysis_status": budget_payload["analysis_status"],
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
                "analysis_status": AnalysisStatus.READ_ERROR,
                "usable_for_learning": False,
                "learning_status": "NOT_ELIGIBLE",
                "learning_status_source": "AUTO",
                "learning_decision_reason": "Error de lectura durante el analisis.",
                "source_kind": source_kind,
                "learning_decision_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analyzer_version": self.ANALYZER_VERSION,
                "probe_version": self.PROBE_VERSION,
                "reader_version": self.READER_VERSION,
                "quality_rules_version": self.QUALITY_RULES_VERSION,
                "classifier_version": self.CLASSIFIER_VERSION,
                "probe_diagnostics_json": probe_diagnostics_json,
                "error": str(exc),
            }
            _apply_existing_manual_learning_decision(error_payload, existing)
            budget_id, _ = upsert_historical_budget(error_payload)
            if budget_id:
                replace_budget_issues(
                    budget_id,
                    [
                        {
                            "severity": IssueSeverity.ERROR,
                            "code": "READ_ERROR",
                            "message": str(exc),
                        }
                    ],
                )
            return {
                "status": "error",
                "excel_path": excel_path,
                "analysis_status": AnalysisStatus.READ_ERROR,
                "error": str(exc),
            }

    def reclassify_budget_modules(self, historical_budget_id: int) -> Dict:
        clear_err = clear_historical_partida_modules_for_budget(historical_budget_id)
        if clear_err:
            return {"ok": False, "error": clear_err}

        partidas = get_historical_partidas_for_classification(historical_budget_id)
        assigned = 0
        for partida in partidas:
            concepto = (partida.get("concepto_original") or partida.get("titulo") or "").strip()
            if not concepto:
                continue
            # Ver nota en analyze_budget(): esta asignación usa classify_text()
            # (lista sin colapsar), no el módulo principal único de classify().
            composed_text = self.classifier._compose_partida_text(
                {
                    "titulo": partida.get("titulo") or concepto,
                    "descripcion": "",
                    "concepto": concepto,
                    "capitulo": partida.get("capitulo") or "",
                }
            )
            classifications = self.classifier.classify_text(composed_text)
            for row in classifications:
                module_id, module_err = get_or_create_execution_module(row.get("module", ""))
                if module_err or not module_id:
                    continue
                assign_err = assign_partida_module(
                    partida_id=int(partida.get("id") or 0),
                    module_id=module_id,
                    confidence=float(row.get("confidence") or 0),
                    source=row.get("source", "rules"),
                )
                if not assign_err:
                    assigned += 1
        rebuild_budget_module_summary(historical_budget_id)
        return {"ok": True, "partidas": len(partidas), "assignments": assigned}

    def rebuild_partida_features(self, budget_ids: Iterable[int]) -> int:
        """Reconstruye la ficha derivada (historical_partida_feature) de las
        partidas de los presupuestos indicados, sin tocar historical_partida
        (el dato bruto). Idempotente: upsert por partida_id."""
        count = 0
        for budget_id in budget_ids:
            for partida in get_historical_partidas_for_classification(budget_id):
                concepto = (partida.get("concepto_original") or partida.get("titulo") or "").strip()
                if not concepto:
                    continue
                composed_text = self.classifier._compose_partida_text(
                    {
                        "titulo": partida.get("titulo") or concepto,
                        "descripcion": "",
                        "concepto": concepto,
                        "capitulo": partida.get("capitulo") or "",
                    }
                )
                candidates = self.classifier.classify_text(composed_text)
                features = extract_partida_features(concepto, partida.get("unidad", ""), candidates)
                features_dict = asdict(features)
                features_dict["classifier_version"] = self.CLASSIFIER_VERSION
                err = upsert_partida_features(partida["id"], features_dict)
                if not err:
                    count += 1
        return count
