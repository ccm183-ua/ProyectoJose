"""
Servicio de presupuestos: orquesta la creación, apertura y gestión
de presupuestos desacoplando la GUI de los módulos core.
"""

import logging
import os
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from src.core import db_repository
from src.core.budget_reader import BudgetReader
from src.core.excel_manager import ExcelManager
from src.core.file_manager import FileManager
from src.core.template_manager import TemplateManager
from src.utils.helpers import sanitize_filename
from src.utils.budget_utils import normalize_date, strip_obra_prefix

logger = logging.getLogger(__name__)


@dataclass
class BudgetCreationResult:
    """Resultado de la creación de un presupuesto."""
    success: bool
    excel_path: str = ""
    folder_path: str = ""
    error: str = ""


class BudgetService:
    """Orquesta las operaciones de presupuestos.

    Centraliza la lógica de negocio que antes estaba dispersa entre
    MainFrame._create_budget, _offer_ai_partidas y _open_excel.
    """

    def __init__(
        self,
        excel_manager: Optional[ExcelManager] = None,
        file_manager: Optional[FileManager] = None,
        template_manager: Optional[TemplateManager] = None,
        budget_reader: Optional[BudgetReader] = None,
    ):
        self._excel = excel_manager or ExcelManager()
        self._files = file_manager or FileManager()
        self._templates = template_manager or TemplateManager()
        self._reader = budget_reader or BudgetReader()

    def get_template_path(self) -> str:
        return self._templates.get_template_path()

    def create_budget(
        self,
        project_data: Dict,
        project_name: str,
        save_dir: str,
        template_path: str,
        comunidad_data: Optional[Dict] = None,
        admin_data: Optional[Dict] = None,
    ) -> BudgetCreationResult:
        """Crea un presupuesto completo: carpeta, subcarpetas, Excel desde plantilla y registro en historial.

        Args:
            project_data: Datos del proyecto (calle, num_calle, codigo_postal, etc.).
            project_name: Nombre del proyecto para el archivo y la carpeta.
            save_dir: Directorio donde guardar el presupuesto.
            template_path: Ruta a la plantilla Excel.
            comunidad_data: Datos de la comunidad (opcional).
            admin_data: Datos de la administración (opcional).

        Returns:
            BudgetCreationResult con el resultado de la operación.
        """
        if not os.path.exists(template_path):
            return BudgetCreationResult(success=False, error="No se encontró la plantilla.")

        folder_name = sanitize_filename(project_name)
        folder_path = os.path.join(save_dir, folder_name)
        if not self._files.create_folder(folder_path):
            return BudgetCreationResult(success=False, error="No se pudo crear la carpeta.")

        subfolders = ["FOTOS", "PLANOS", "PROYECTO", "MEDICIONES", "PRESUPUESTOS"]
        self._files.create_subfolders(folder_path, subfolders)

        save_path = os.path.join(folder_path, f"{folder_name}.xlsx")

        excel_data = self._build_excel_data(
            project_data, project_name, comunidad_data, admin_data,
        )

        if not self._excel.create_from_template(template_path, save_path, excel_data):
            return BudgetCreationResult(
                success=False, error="Error al crear el presupuesto desde la plantilla.",
            )

        db_repository.registrar_presupuesto({
            "nombre_proyecto": project_name,
            "ruta_excel": save_path,
            "ruta_carpeta": folder_path,
            "cliente": project_data.get("cliente", ""),
            "localidad": project_data.get("localidad", ""),
            "tipo_obra": project_data.get("tipo", ""),
            "numero_proyecto": project_data.get("numero", ""),
        })

        return BudgetCreationResult(
            success=True, excel_path=save_path, folder_path=folder_path,
        )

    def insert_partidas(
        self, excel_path: str, partidas: List[Dict], project_data: Optional[Dict] = None,
    ) -> bool:
        """Inserta partidas en un presupuesto y actualiza el total en historial."""
        if not self._excel.insert_partidas_via_xml(excel_path, partidas):
            return False

        if project_data:
            db_repository.registrar_presupuesto({
                "nombre_proyecto": project_data.get(
                    "nombre_obra", os.path.basename(excel_path),
                ),
                "ruta_excel": excel_path,
                "usa_partidas_ia": True,
            })

        data = self._reader.read(excel_path)
        if data:
            db_repository.actualizar_total(excel_path, data["total"])

        return True

    def open_budget(self, file_path: str) -> bool:
        """Abre un presupuesto, lo registra en historial y devuelve True si fue exitoso."""
        budget = self._excel.load_budget(file_path)
        if not budget:
            return False
        budget.close()

        db_repository.registrar_presupuesto({
            "nombre_proyecto": os.path.splitext(os.path.basename(file_path))[0],
            "ruta_excel": file_path,
            "ruta_carpeta": os.path.dirname(file_path),
        })
        return True

    def finalize_budget(
        self,
        file_path: str,
        project_data: Optional[Dict] = None,
        comunidad_data: Optional[Dict] = None,
        admin_data: Optional[Dict] = None,
        estado: str = "",
    ) -> bool:
        """Persiste presupuesto completo (cabecera + partidas) al finalizar."""
        data = self._reader.read(file_path)
        if not data:
            return False

        try:
            fecha_modificacion = datetime.fromtimestamp(
                os.path.getmtime(file_path)
            ).isoformat()
        except (OSError, ValueError):
            fecha_modificacion = datetime.now().isoformat()

        cabecera = data.get("cabecera", {}) or {}
        partidas = data.get("partidas", []) or []

        comunidad_res, admin_res, metodo_admin, metodo_comunidad = self._resolve_entities(
            cabecera=cabecera,
            comunidad_data=comunidad_data,
            admin_data=admin_data,
            project_data=project_data,
        )
        if not estado:
            estado = self._infer_estado(file_path)

        localidad = ""
        if project_data:
            localidad = (project_data.get("localidad") or "").strip()
        if not localidad:
            localidad = (cabecera.get("localidad") or "").strip()

        direccion = self._build_direccion(project_data)
        if not direccion:
            direccion = (cabecera.get("direccion") or "").strip()

        codigo_postal = ""
        if project_data:
            codigo_postal = (project_data.get("codigo_postal") or "").strip()
        if not codigo_postal:
            codigo_postal = (cabecera.get("codigo_postal") or "").strip()

        nombre_proyecto = (cabecera.get("obra") or "").strip()
        if not nombre_proyecto:
            nombre_proyecto = os.path.splitext(os.path.basename(file_path))[0]

        total = data.get("total")
        subtotal = data.get("subtotal")
        iva = data.get("iva")
        total_partidas = round(sum(float(p.get("importe") or 0.0) for p in partidas), 2)

        missing = []
        if not (cabecera.get("cliente") or "").strip():
            missing.append("cliente")
        if not localidad:
            missing.append("localidad")
        if not codigo_postal:
            missing.append("codigo_postal")
        if total is None:
            missing.append("total")
        if not partidas:
            missing.append("partidas")
        if not (comunidad_res or {}).get("id"):
            missing.append("comunidad")
        if not (admin_res or {}).get("id"):
            missing.append("administracion")

        motivo_incompleto = ""
        datos_completos = len(missing) == 0
        if not datos_completos:
            motivo_incompleto = "Faltan: " + ", ".join(missing)

        payload = {
            "numero_proyecto": (cabecera.get("numero") or "").strip(),
            "nombre_proyecto": nombre_proyecto,
            "ruta_excel": file_path,
            "ruta_carpeta": os.path.dirname(file_path),
            "estado": estado,
            "cliente": (cabecera.get("cliente") or "").strip(),
            "localidad": localidad,
            "tipo_obra": (project_data or {}).get("tipo", "") if project_data else "",
            "fecha": normalize_date((cabecera.get("fecha") or "").strip()),
            "total": total,
            "subtotal": subtotal,
            "iva": iva,
            "obra_descripcion": (cabecera.get("obra") or "").strip(),
            "cif_admin": (cabecera.get("cif_admin") or "").strip(),
            "email_admin": (cabecera.get("email_admin") or "").strip(),
            "telefono_admin": (cabecera.get("telefono_admin") or "").strip(),
            "codigo_postal": codigo_postal,
            "direccion": direccion,
            "localizacion": direccion,
            "comunidad_id": (comunidad_res or {}).get("id"),
            "administracion_id": (admin_res or {}).get("id"),
            "comunidad_nombre": (comunidad_res or {}).get("nombre", ""),
            "administracion_nombre": (admin_res or {}).get("nombre", ""),
            "fecha_modificacion_excel": fecha_modificacion,
            "datos_completos": datos_completos,
            "total_partidas": total_partidas,
            "num_partidas": len(partidas),
            "motivo_incompleto": motivo_incompleto,
            "metodo_resolucion_admin": metodo_admin,
            "metodo_resolucion_comunidad": metodo_comunidad,
        }

        _id, err = db_repository.upsert_presupuesto_finalizado(payload, partidas)
        if err:
            logger.error("No se pudo finalizar presupuesto %s: %s", file_path, err)
            return False

        db_repository.registrar_presupuesto({
            "nombre_proyecto": nombre_proyecto,
            "ruta_excel": file_path,
            "ruta_carpeta": os.path.dirname(file_path),
            "cliente": payload["cliente"],
            "localidad": payload["localidad"],
            "tipo_obra": payload["tipo_obra"],
            "numero_proyecto": payload["numero_proyecto"],
            "total_presupuesto": total,
        })
        return True

    def read_budget(self, file_path: str, expected_numero: str = "") -> Optional[Dict]:
        """Lee los datos de un presupuesto."""
        return self._reader.read(file_path, expected_numero=expected_numero)

    def update_header_fields(self, file_path: str, data: Dict) -> bool:
        """Actualiza los campos de cabecera de un presupuesto existente."""
        return self._excel.update_header_fields(file_path, data)

    def append_partidas(self, file_path: str, new_partidas: List[Dict]) -> bool:
        """Añade partidas al final de las existentes."""
        return self._excel.append_partidas_via_xml(file_path, new_partidas)

    def refresh_budget_cache_entry(
        self,
        file_path: str,
        estado: str = "",
        expected_numero: str = "",
    ) -> bool:
        """Relee un Excel y actualiza su registro en tabla presupuesto."""
        data = self._reader.read(file_path, expected_numero=expected_numero)
        if not data:
            return False

        try:
            fecha_modificacion = datetime.fromtimestamp(
                os.path.getmtime(file_path)
            ).isoformat()
        except (OSError, ValueError):
            fecha_modificacion = datetime.now().isoformat()

        cabecera = data.get("cabecera", {}) or {}
        partidas = data.get("partidas", []) or []
        direccion = (cabecera.get("direccion") or "").strip()
        tipo_obra = strip_obra_prefix(cabecera.get("obra", ""))
        existing = db_repository.get_presupuesto_por_ruta(file_path)
        comunidad_res, admin_res, metodo_admin, metodo_comunidad = self._resolve_entities(
            cabecera=cabecera,
            comunidad_data=None,
            admin_data=None,
            project_data=None,
        )
        if not estado:
            estado = self._infer_estado(file_path)

        payload = {
            "numero_proyecto": (cabecera.get("numero") or "").strip() or expected_numero,
            "nombre_proyecto": os.path.splitext(os.path.basename(file_path))[0],
            "ruta_excel": file_path,
            "ruta_carpeta": os.path.dirname(file_path),
            "estado": estado,
            "cliente": (cabecera.get("cliente") or "").strip(),
            "localidad": self._infer_localidad_from_direccion(direccion),
            "tipo_obra": tipo_obra,
            "fecha": normalize_date((cabecera.get("fecha") or "").strip()),
            "total": data.get("total"),
            "subtotal": data.get("subtotal"),
            "iva": data.get("iva"),
            "obra_descripcion": tipo_obra,
            "cif_admin": (cabecera.get("cif_admin") or "").strip(),
            "email_admin": (cabecera.get("email_admin") or "").strip(),
            "telefono_admin": (cabecera.get("telefono_admin") or "").strip(),
            "codigo_postal": (cabecera.get("codigo_postal") or "").strip(),
            "direccion": direccion,
            "localizacion": direccion,
            "comunidad_id": (comunidad_res or {}).get("id"),
            "administracion_id": (admin_res or {}).get("id"),
            "comunidad_nombre": (comunidad_res or {}).get("nombre", ""),
            "administracion_nombre": (admin_res or {}).get("nombre", ""),
            "metodo_resolucion_admin": metodo_admin,
            "metodo_resolucion_comunidad": metodo_comunidad,
            "fecha_modificacion_excel": fecha_modificacion,
            "datos_completos": bool(data.get("total") is not None and tipo_obra),
            "total_partidas": round(sum(float(p.get("importe") or 0.0) for p in partidas), 2),
            "num_partidas": len(partidas),
            "fuente_datos": "scan",
        }

        if existing and existing.get("es_finalizado"):
            # Para registros finalizados, mantener FKs si no se lograron resolver
            if not payload.get("comunidad_id"):
                payload["comunidad_id"] = existing.get("comunidad_id")
                payload["comunidad_nombre"] = existing.get("comunidad_nombre", "")
            if not payload.get("administracion_id"):
                payload["administracion_id"] = existing.get("administracion_id")
                payload["administracion_nombre"] = existing.get("administracion_nombre", "")
            _id, err = db_repository.upsert_presupuesto_finalizado(payload, partidas)
            return bool(_id and not err)

        _id, err = db_repository.upsert_presupuesto(payload)
        return bool(_id and not err)

    @staticmethod
    def _build_direccion(project_data: Optional[Dict]) -> str:
        if not project_data:
            return ""
        parts = [
            (project_data.get("calle") or "").strip(),
            (project_data.get("num_calle") or "").strip(),
            (project_data.get("codigo_postal") or "").strip(),
            (project_data.get("localidad") or "").strip(),
        ]
        return ", ".join([p for p in parts if p])

    @staticmethod
    def _infer_estado(file_path: str) -> str:
        folder = os.path.dirname(file_path)
        project_folder = os.path.dirname(folder)
        state = os.path.basename(project_folder).strip()
        return state or "PTE. PRESUPUESTAR"

    @staticmethod
    def _infer_localidad_from_direccion(direccion: str) -> str:
        text = (direccion or "").strip()
        if not text:
            return ""
        parts = [p.strip() for p in text.split(",") if p.strip()]
        if not parts:
            return ""
        tail = parts[-1]
        tokens = tail.split()
        if tokens and tokens[0].isdigit() and len(tokens[0]) in (4, 5):
            tail = " ".join(tokens[1:]).strip()
        return tail

    @staticmethod
    def _resolve_entities(
        cabecera: Dict,
        comunidad_data: Optional[Dict],
        admin_data: Optional[Dict],
        project_data: Optional[Dict],
    ) -> Tuple[Optional[Dict], Optional[Dict], str, str]:
        comunidad = comunidad_data
        admin = admin_data
        metodo_admin = ""
        metodo_comunidad = ""

        if comunidad and comunidad.get("id"):
            metodo_comunidad = "seleccion_manual"
            if not admin and comunidad.get("administracion_id"):
                admin = db_repository.get_administracion_por_id(comunidad["administracion_id"])
                if admin:
                    metodo_admin = "por_comunidad"

        email_admin = (cabecera.get("email_admin") or "").strip()
        if not email_admin and admin:
            email_admin = (admin.get("email") or "").strip()
        if not admin and email_admin:
            admin = db_repository.buscar_administracion_por_email(email_admin)
            if admin:
                metodo_admin = "por_email"

        cliente_nombre = (cabecera.get("cliente") or "").strip()
        if not cliente_nombre and project_data:
            cliente_nombre = (project_data.get("cliente") or "").strip()

        if not comunidad and cliente_nombre:
            comunidad = db_repository.buscar_comunidad_por_nombre(cliente_nombre)
            if comunidad:
                metodo_comunidad = "por_nombre_cliente"
                if not admin and comunidad.get("administracion_id"):
                    admin = db_repository.get_administracion_por_id(comunidad["administracion_id"])
                    if admin and not metodo_admin:
                        metodo_admin = "por_comunidad"

        if not admin and cliente_nombre:
            admin = db_repository.buscar_administracion_por_nombre(cliente_nombre)
            if admin and not metodo_admin:
                metodo_admin = "por_nombre_cliente"

        if not metodo_admin:
            metodo_admin = "sin_resolver"
        if not metodo_comunidad:
            metodo_comunidad = "sin_resolver"
        return comunidad, admin, metodo_admin, metodo_comunidad

    @staticmethod
    def _build_excel_data(
        project_data: Dict,
        project_name: str,
        comunidad_data: Optional[Dict],
        admin_data: Optional[Dict],
    ) -> Dict:
        return {
            "nombre_obra": project_name,
            "direccion": project_data.get("calle", ""),
            "numero": project_data.get("num_calle", ""),
            "codigo_postal": project_data.get("codigo_postal", ""),
            "descripcion": project_data.get("tipo", ""),
            "numero_proyecto": project_data.get("numero", ""),
            "fecha": project_data.get("fecha", ""),
            "cliente": project_data.get("cliente", ""),
            "mediacion": project_data.get("mediacion", ""),
            "calle": project_data.get("calle", ""),
            "num_calle": project_data.get("num_calle", ""),
            "localidad": project_data.get("localidad", ""),
            "tipo": project_data.get("tipo", ""),
            "admin_cif": comunidad_data.get("cif", "") if comunidad_data else "",
            "admin_email": admin_data.get("email", "") if admin_data else "",
            "admin_telefono": admin_data.get("telefono", "") if admin_data else "",
        }
