"""
Servicio de presupuestos: orquesta la creación, apertura y gestión
de presupuestos desacoplando la GUI de los módulos core.
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.core import db_repository
from src.core.budget_reader import BudgetReader
from src.core.excel_manager import ExcelManager
from src.core.file_manager import FileManager
from src.core.template_manager import TemplateManager
from src.utils.helpers import sanitize_filename

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

    def read_budget(self, file_path: str, expected_numero: str = "") -> Optional[Dict]:
        """Lee los datos de un presupuesto."""
        return self._reader.read(file_path, expected_numero=expected_numero)

    def update_header_fields(self, file_path: str, data: Dict) -> bool:
        """Actualiza los campos de cabecera de un presupuesto existente."""
        return self._excel.update_header_fields(file_path, data)

    def append_partidas(self, file_path: str, new_partidas: List[Dict]) -> bool:
        """Añade partidas al final de las existentes."""
        return self._excel.append_partidas_via_xml(file_path, new_partidas)

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
