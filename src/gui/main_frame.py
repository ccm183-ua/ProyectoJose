"""
Ventana principal de cubiApp (PySide6).
"""

import os
import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QMainWindow, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from src.core import database as db_module
from src.core.historical_context import request_historical_suggestions_for_context
from src.core.historical_suggestions_dedupe import (
    dedupe_historical_partidas,
    dedupe_merged_review_partidas,
)
from src.core.partida_normalizer import normalize_partida_for_excel
from src.core.services import BudgetService, DatabaseService
from src.gui import theme
from src.gui.historical_suggestions_dialog import (
    HistoricalSuggestionContextDialog,
    HistoricalSuggestionDescriptionDialog,
)


class MainFrame(QMainWindow):
    def __init__(self, parent=None, title="cubiApp", **kwargs):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 520)
        self._budget_svc = BudgetService()
        self._db_svc = DatabaseService()
        self._db_frame = None
        self._dashboard_frame = None
        self._historical_memory_dashboard = None
        self._build_ui()
        self._center()

    def _center(self):
        screen = self.screen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # === HEADER ===
        header = QWidget()
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 60, 0, 0)
        header_layout.setSpacing(8)

        title = theme.create_title(header, "cubiApp", "display")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        header_layout.addWidget(title)

        subtitle = theme.create_subtitle(header, "Gestión de presupuestos")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        header_layout.addWidget(subtitle)

        main_layout.addWidget(header)
        main_layout.addSpacing(50)

        # === BOTONES ===
        btn_container = QWidget()
        btn_layout = QVBoxLayout(btn_container)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        btn_layout.setSpacing(theme.SPACE_MD)

        btn_create = QPushButton("+ Crear nuevo presupuesto")
        btn_create.setFixedSize(320, 50)
        btn_create.setFont(theme.get_font_medium(12))
        btn_create.setProperty("class", "primary")
        btn_create.clicked.connect(self._create_budget)
        btn_layout.addWidget(btn_create, alignment=Qt.AlignmentFlag.AlignHCenter)

        btn_open = QPushButton("Presupuestos existentes")
        btn_open.setFixedSize(320, 46)
        btn_open.setFont(theme.font_base())
        btn_open.clicked.connect(self._open_dashboard)
        btn_layout.addWidget(btn_open, alignment=Qt.AlignmentFlag.AlignHCenter)

        btn_db = QPushButton("Gestionar base de datos")
        btn_db.setFixedSize(320, 46)
        btn_db.setFont(theme.font_base())
        btn_db.clicked.connect(self._open_db_manager)
        btn_layout.addWidget(btn_db, alignment=Qt.AlignmentFlag.AlignHCenter)

        main_layout.addWidget(btn_container, 1)

        # === FOOTER ===
        footer = theme.create_caption(central, "versión 1.0")
        footer.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        main_layout.addWidget(footer)
        main_layout.addSpacing(theme.SPACE_XL)

        self.setCentralWidget(central)
        self._create_menu()

    def _create_menu(self):
        menubar = self.menuBar()

        m_archivo = menubar.addMenu("&Archivo")
        act_open = m_archivo.addAction("Abrir presupuesto...\tCtrl+O")
        act_open.triggered.connect(self._open_excel)
        act_new = m_archivo.addAction("Crear nuevo presupuesto...\tCtrl+N")
        act_new.triggered.connect(self._create_budget)
        m_archivo.addSeparator()
        act_exit = m_archivo.addAction("Salir\tCtrl+Q")
        act_exit.triggered.connect(self.close)

        m_bd = menubar.addMenu("Base de &datos")
        act_db = m_bd.addAction("Gestionar base de datos...")
        act_db.triggered.connect(self._open_db_manager)
        act_folder = m_bd.addAction("Abrir carpeta de la base de datos")
        act_folder.triggered.connect(self._open_db_folder)

        m_config = menubar.addMenu("&Configuración")
        act_ai = m_config.addAction("Configuración IA...")
        act_ai.triggered.connect(self._open_ai_settings)
        act_templates = m_config.addAction("Gestionar plantillas...")
        act_templates.triggered.connect(self._open_template_manager)
        act_paths = m_config.addAction("Rutas por defecto...")
        act_paths.triggered.connect(self._open_default_paths)

        m_tools = menubar.addMenu("&Herramientas")
        act_ai_tools = m_tools.addAction("Configuración IA...")
        act_ai_tools.triggered.connect(self._open_ai_settings)
        act_hist = m_tools.addAction("Analizar presupuestos terminados...")
        act_hist.triggered.connect(self._open_historical_analysis)
        act_memory = m_tools.addAction("Panel de memoria historica...")
        act_memory.triggered.connect(self._open_historical_memory_dashboard)

        m_ayuda = menubar.addMenu("&Ayuda")
        act_about = m_ayuda.addAction("Acerca de...")
        act_about.triggered.connect(
            lambda: QMessageBox.information(
                self, "Acerca de",
                "cubiApp\n\nAbre o crea presupuestos desde plantilla Excel.",
            )
        )

    def _open_db_manager(self):
        try:
            from src.gui.db_manager import DBManagerFrame
            if self._db_frame is not None:
                try:
                    if self._db_frame.isVisible():
                        self._db_frame.raise_()
                        self._db_frame.activateWindow()
                        return
                except RuntimeError:
                    self._db_frame = None

            self._db_frame = DBManagerFrame(self)
            self._db_frame.destroyed.connect(lambda: setattr(self, '_db_frame', None))
            self._db_frame.show()
            self._db_frame.raise_()
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Error al abrir la base de datos: {ex}")

    def _open_dashboard(self, refresh=False):
        try:
            from src.gui.budget_dashboard import BudgetDashboardFrame
            if self._dashboard_frame is not None:
                try:
                    if self._dashboard_frame.isVisible():
                        if refresh:
                            self._dashboard_frame._load_data()
                        self._dashboard_frame.raise_()
                        self._dashboard_frame.activateWindow()
                        return
                except RuntimeError:
                    self._dashboard_frame = None

            self._dashboard_frame = BudgetDashboardFrame(self)
            self._dashboard_frame.destroyed.connect(lambda: setattr(self, '_dashboard_frame', None))
            self._dashboard_frame.show()
            self._dashboard_frame.raise_()
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Error al abrir el dashboard: {ex}")

    def _open_historical_memory_dashboard(self):
        try:
            from src.gui.historical_memory_dashboard import HistoricalMemoryDashboard

            if self._historical_memory_dashboard is not None:
                try:
                    if self._historical_memory_dashboard.isVisible():
                        self._historical_memory_dashboard._reload()
                        self._historical_memory_dashboard.raise_()
                        self._historical_memory_dashboard.activateWindow()
                        return
                except RuntimeError:
                    self._historical_memory_dashboard = None

            self._historical_memory_dashboard = HistoricalMemoryDashboard(self)
            self._historical_memory_dashboard.destroyed.connect(
                lambda: setattr(self, "_historical_memory_dashboard", None)
            )
            self._historical_memory_dashboard.show()
            self._historical_memory_dashboard.raise_()
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Error al abrir la memoria historica: {ex}")

    def _open_db_folder(self):
        try:
            path = db_module.get_db_path()
            db_module.ensure_db_directory(path)
            conn = db_module.connect()
            try:
                pass
            finally:
                conn.close()
            folder = str(path.parent)
            if sys.platform == "darwin":
                subprocess.run(["open", folder], check=True)
            elif sys.platform == "win32":
                subprocess.run(["explorer", folder], check=True)
            else:
                subprocess.run(["xdg-open", folder], check=True)
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Error: {ex}")

    def _open_excel(self):
        from src.core.settings import Settings
        default_dir = Settings().get_default_path(Settings.PATH_OPEN_BUDGETS) or ""
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Presupuesto", default_dir,
            "Excel (*.xlsx *.xls);;Todos (*.*)",
        )
        if not path:
            return
        try:
            if self._budget_svc.open_budget(path):
                QMessageBox.information(self, "Éxito", f"Presupuesto abierto: {os.path.basename(path)}")
            else:
                QMessageBox.critical(self, "Error", "No se pudo abrir el archivo Excel.")
        except Exception as ex:
            QMessageBox.critical(self, "Error", f"Error: {ex}")

    def _create_budget(self):
        project_data, project_name = self._obtain_project_data()
        if not project_data or not project_name:
            return

        from src.core.settings import Settings
        from src.utils.helpers import sanitize_filename
        save_default_dir = Settings().get_default_path(Settings.PATH_SAVE_BUDGETS) or ""
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar Presupuesto",
            os.path.join(save_default_dir, f"{sanitize_filename(project_name)}.xlsx"),
            "Excel (*.xlsx);;Todos (*.*)",
        )
        if not save_path:
            return

        template_path = self._budget_svc.get_template_path()
        save_dir = os.path.dirname(save_path)

        partes_dir = [
            p for p in [
                project_data.get("calle", ""),
                project_data.get("num_calle", ""),
                project_data.get("codigo_postal", ""),
                project_data.get("localidad", ""),
            ] if p
        ]
        direccion_proyecto = ", ".join(partes_dir)

        comunidad_data = self._buscar_comunidad_para_presupuesto(
            project_data.get("cliente", ""), direccion=direccion_proyecto,
        )
        admin_data = self._db_svc.get_admin_para_comunidad(comunidad_data)

        result = self._budget_svc.create_budget(
            project_data, project_name, save_dir, template_path,
            comunidad_data=comunidad_data, admin_data=admin_data,
        )
        if not result.success:
            QMessageBox.critical(self, "Error", result.error)
            return

        # Flujo completo: contexto memoria → sugerencias históricas → revisión combinada / IA complementaria
        # (no solo el diálogo «Generar Partidas con IA» aislado).
        self._offer_partidas(result.excel_path, project_data)
        finalized = self._budget_svc.finalize_budget(
            result.excel_path,
            project_data=project_data,
            comunidad_data=comunidad_data,
            admin_data=admin_data,
        )
        if not finalized:
            QMessageBox.warning(
                self,
                "Aviso",
                "El presupuesto se creó, pero no se pudo guardar su detalle completo en la base de datos.",
            )
        self._open_dashboard(refresh=True)

    def _obtain_project_data(self):
        from src.gui.dialogs import obtain_project_data
        return obtain_project_data(self)

    def _open_default_paths(self):
        from src.gui.dialogs import DefaultPathsDialog
        dlg = DefaultPathsDialog(self)
        dlg.exec()

    def _open_historical_analysis(self):
        from src.gui.historical_analysis_dialog import HistoricalAnalysisDialog
        dlg = HistoricalAnalysisDialog(self)
        dlg.exec()

    def _buscar_comunidad_para_presupuesto(self, nombre_cliente: str, direccion: str = "") -> dict | None:
        from src.gui.dialogs import (
            ComunidadConfirmDialog, ComunidadFuzzySelectDialog,
            crear_comunidad_con_formulario,
        )

        exacta, fuzzy = self._db_svc.buscar_comunidad(nombre_cliente)

        if exacta:
            dlg = ComunidadConfirmDialog(self, exacta, nombre_cliente.strip())
            if dlg.exec() == QMessageBox.DialogCode.Accepted.value:
                return dlg.get_comunidad_data()
            return None

        if fuzzy:
            dlg = ComunidadFuzzySelectDialog(
                self, fuzzy, nombre_cliente.strip(), direccion_prefill=direccion,
            )
            if dlg.exec() == QMessageBox.DialogCode.Accepted.value:
                return dlg.get_comunidad_data()
            return None

        if not nombre_cliente or not nombre_cliente.strip():
            return None

        resp = QMessageBox.question(
            self,
            "Comunidad no encontrada",
            f'No se encontró ninguna comunidad con el nombre "{nombre_cliente.strip()}".\n\n'
            "¿Desea añadir una nueva comunidad a la base de datos?",
        )
        if resp == QMessageBox.StandardButton.Yes:
            return crear_comunidad_con_formulario(
                self, nombre_prefill=nombre_cliente.strip(), direccion_prefill=direccion,
            )

        return None

    def _offer_ai_partidas(self, excel_path, project_data, historical_context=None):
        from src.gui.ai_budget_dialog import AIBudgetDialog
        from src.gui.partidas_dialog import SuggestedPartidasDialog

        ai_dlg = AIBudgetDialog(
            self,
            datos_proyecto=project_data,
            historical_context=historical_context or {},
        )
        if ai_dlg.exec() != 1:
            QMessageBox.information(
                self, "Éxito",
                f"Presupuesto creado (sin partidas IA):\n{excel_path}",
            )
            return

        result = ai_dlg.get_result()

        if not result or not result.get('partidas'):
            QMessageBox.information(
                self, "Éxito",
                f"Presupuesto creado (sin partidas IA):\n{excel_path}",
            )
            return

        partidas_dlg = SuggestedPartidasDialog(self, result)
        if partidas_dlg.exec() != 1:
            QMessageBox.information(
                self, "Éxito",
                f"Presupuesto creado (sin partidas IA):\n{excel_path}",
            )
            return

        selected = partidas_dlg.get_selected_partidas()

        if selected:
            if self._budget_svc.insert_partidas(excel_path, selected, project_data):
                QMessageBox.information(
                    self, "Éxito",
                    f"Presupuesto creado con {len(selected)} partidas:\n{excel_path}",
                )
            else:
                QMessageBox.warning(
                    self, "Aviso",
                    f"Presupuesto creado pero hubo un error al insertar las partidas.\n{excel_path}",
                )
        else:
            QMessageBox.information(
                self, "Éxito",
                f"Presupuesto creado (sin partidas):\n{excel_path}",
            )

    def _offer_partidas(self, excel_path, project_data):
        confirmed_context = self._request_historical_context(project_data)
        if confirmed_context is None:
            self._offer_ai_partidas(excel_path, project_data)
            return

        historical_result = self._try_historical_suggestions(project_data, confirmed_context)
        if historical_result and self._should_offer_context_retry(historical_result):
            retried = self._retry_historical_with_manual_context(project_data, historical_result)
            if retried is not None:
                historical_result = retried
            elif historical_result and historical_result.get("message") and not historical_result.get("partidas"):
                QMessageBox.information(
                    self,
                    "Sugerencias históricas",
                    (
                        f"{historical_result.get('message', 'No hay sugerencias históricas disponibles.')}\n\n"
                        "Continuaremos con el flujo normal (IA opcional)."
                    ),
                )
        if historical_result and historical_result.get("partidas"):
            from src.gui.historical_suggestions_dialog import HistoricalSuggestionsDialog
            from src.gui.ai_complete_historical_budget_dialog import AICompleteHistoricalBudgetDialog
            from src.gui.combined_partidas_review_dialog import CombinedPartidasReviewDialog
            from src.gui.historical_selection_next_step_dialog import HistoricalSelectionNextStepDialog

            hr = dict(historical_result)
            partidas_dedup, dup_removed = dedupe_historical_partidas(hr.get("partidas", []))
            hr["partidas"] = partidas_dedup
            hr["duplicates_hidden_count"] = dup_removed

            dlg = HistoricalSuggestionsDialog(self, hr, project_data=project_data)
            if dlg.exec() == 1:
                selected = dlg.get_selected_partidas()
                if selected:
                    selected_normalized = [
                        normalize_partida_for_excel(p, source="historical")
                        for p in selected
                    ]
                    next_step = HistoricalSelectionNextStepDialog(self, selected_count=len(selected_normalized))
                    next_step.exec()
                    user_action = next_step.get_result()
                    if user_action == HistoricalSelectionNextStepDialog.CANCEL:
                        return
                    if user_action == HistoricalSelectionNextStepDialog.CREATE_ONLY:
                        review = CombinedPartidasReviewDialog(
                            self,
                            historical_partidas=selected_normalized,
                            ai_partidas=[],
                        )
                        if review.exec() != 1:
                            return
                        self._insert_final_partidas_once(
                            excel_path,
                            review.get_selected_partidas(),
                            project_data,
                        )
                        return
                    completion_dlg = AICompleteHistoricalBudgetDialog(
                        self,
                        project_data=project_data,
                        confirmed_context=confirmed_context,
                        selected_historical_partidas=selected,
                        historical_result=historical_result,
                    )
                    if completion_dlg.exec() != 1:
                        return
                    completion_action = completion_dlg.get_action()
                    completion_result = completion_dlg.get_result()
                    ai_partidas_raw = (
                        completion_result.get("partidas", [])
                        if completion_action == "ai_completion"
                        else []
                    )
                    ai_partidas = [
                        normalize_partida_for_excel(p, source="ai_completion")
                        for p in ai_partidas_raw
                    ]
                    if completion_action == "ai_completion" and not ai_partidas:
                        QMessageBox.information(
                            self,
                            "Sin complementos",
                            "La IA no ha detectado partidas complementarias. Puedes continuar con históricas.",
                        )
                    hist_for_review, ai_for_review, cross_deduped = dedupe_merged_review_partidas(
                        selected_normalized,
                        ai_partidas,
                    )
                    merge_note = ""
                    if cross_deduped > 0:
                        merge_note = (
                            f"Se han ocultado {cross_deduped} partidas duplicadas entre históricas "
                            "e IA complementaria."
                        )
                    review = CombinedPartidasReviewDialog(
                        self,
                        historical_partidas=hist_for_review,
                        ai_partidas=ai_for_review,
                        merge_duplicates_note=merge_note,
                    )
                    if review.exec() != 1:
                        return
                    self._insert_final_partidas_once(
                        excel_path,
                        review.get_selected_partidas(),
                        project_data,
                    )
                    return
                # Si acepta sin seleccionar, continuar a IA opcional
                ask_ai_no_sel = QMessageBox.question(
                    self,
                    "Sin partidas históricas seleccionadas",
                    "No has seleccionado partidas históricas.\n\n"
                    "¿Deseas continuar con IA usando contexto histórico?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if ask_ai_no_sel == QMessageBox.StandardButton.Yes:
                    self._offer_ai_partidas(
                        excel_path, project_data, historical_context=historical_result
                    )
                return
            # Si cancela el diálogo histórico, preguntar IA sin contexto.
            ask_ai = QMessageBox.question(
                self,
                "Sugerencias históricas canceladas",
                "¿Deseas continuar con generación IA sin contexto histórico?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ask_ai == QMessageBox.StandardButton.Yes:
                self._offer_ai_partidas(excel_path, project_data, historical_context=None)
            return

        self._offer_ai_partidas(excel_path, project_data)

    def _insert_final_partidas_once(self, excel_path: str, selected: list, project_data: dict):
        if selected:
            if self._budget_svc.insert_partidas(excel_path, selected, project_data):
                QMessageBox.information(
                    self,
                    "Éxito",
                    f"Presupuesto creado con {len(selected)} partidas:\n{excel_path}",
                )
            else:
                QMessageBox.warning(
                    self,
                    "Aviso",
                    f"Presupuesto creado pero hubo un error al insertar las partidas.\n{excel_path}",
                )
        else:
            QMessageBox.information(
                self,
                "Éxito",
                f"Presupuesto creado (sin partidas):\n{excel_path}",
            )

    @staticmethod
    def _should_offer_context_retry(suggestion_result: dict) -> bool:
        if not suggestion_result or suggestion_result.get("partidas"):
            return False
        reason = (suggestion_result.get("failure_reason") or "").strip().upper()
        return reason in {"NO_MODULES", "TOO_GENERIC", "NO_PATTERNS", "FILTERED_OUT"}

    def _retry_historical_with_manual_context(self, project_data: dict, suggestion_result: dict):
        from src.core.historical_suggestion_service import HistoricalSuggestionService

        ctx_dlg = HistoricalSuggestionContextDialog(self, suggestion_result)
        if ctx_dlg.exec() != 1 or not ctx_dlg.wants_search_again():
            return None

        manual_context = ctx_dlg.get_manual_context()
        fresh = HistoricalSuggestionService().suggest_for_project(
            project_data or {},
            user_description=manual_context,
        )
        if not fresh.get("partidas"):
            QMessageBox.information(
                self,
                "Sugerencias históricas",
                (
                    f"{fresh.get('message', 'No se han encontrado sugerencias suficientes.')}\n\n"
                    "Puedes continuar con IA o sin sugerencias históricas."
                ),
            )
        return fresh

    def _request_historical_context(self, project_data: dict) -> str | None:
        dlg = HistoricalSuggestionDescriptionDialog(self, project_data or {})
        if dlg.exec() != 1 or not dlg.wants_search():
            return None
        return dlg.get_confirmed_context()

    @staticmethod
    def _try_historical_suggestions(project_data, confirmed_context: str = ""):
        try:
            return request_historical_suggestions_for_context(
                project_data or {},
                confirmed_context,
            )
        except Exception:
            return None

    def _open_template_manager(self):
        from src.gui.template_manager_dialog import TemplateManagerDialog
        dlg = TemplateManagerDialog(self)
        dlg.exec()

    def _open_ai_settings(self):
        from src.gui.ai_settings_dialog import AISettingsDialog

        dlg = AISettingsDialog(self)
        if dlg.exec() == 1:
            QMessageBox.information(self, "Configuración IA", "Configuración guardada correctamente.")
