"""
Dashboard de presupuestos existentes (wxPython).

Muestra el historial de presupuestos creados/abiertos, con opciones
de previsualización, edición, exportación a PDF y acceso rápido.
"""

import os
import subprocess
import sys

import wx

from src.core import db_repository as repo
from src.gui import theme


class BudgetDashboardFrame(wx.Frame):
    """Ventana principal del dashboard de presupuestos."""

    def __init__(self, parent):
        super().__init__(
            parent, title="Presupuestos existentes",
            size=(960, 600),
            style=wx.DEFAULT_FRAME_STYLE,
        )
        self._parent = parent
        self._historial = []
        self._build_ui()
        self.Centre()
        self._refresh_list()

    def _build_ui(self):
        theme.style_frame(self)
        panel = wx.Panel(self)
        panel.SetBackgroundColour(theme.BG_PRIMARY)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Header ---
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        title = theme.create_title(panel, "Presupuestos", "xl")
        header_sizer.Add(title, 0, wx.ALIGN_CENTER_VERTICAL)
        header_sizer.AddStretchSpacer()
        self._search = wx.SearchCtrl(panel, size=(260, 30))
        self._search.SetDescriptiveText("Buscar proyecto, cliente, localidad...")
        self._search.ShowCancelButton(True)
        theme.style_textctrl(self._search)
        self._search.Bind(wx.EVT_TEXT, self._on_search)
        self._search.Bind(wx.EVT_SEARCHCTRL_CANCEL_BTN, self._on_search_cancel)
        header_sizer.Add(self._search, 0, wx.ALIGN_CENTER_VERTICAL)
        main_sizer.Add(header_sizer, 0, wx.EXPAND | wx.ALL, theme.SPACE_LG)

        main_sizer.Add(theme.create_divider(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_LG)

        # --- ListCtrl ---
        self._list = wx.ListCtrl(
            panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_NONE,
        )
        theme.style_listctrl(self._list)

        columns = [
            ("Proyecto", 200),
            ("Cliente", 160),
            ("Localidad", 100),
            ("Tipo obra", 100),
            ("Fecha", 90),
            ("Total", 90),
            ("IA", 40),
        ]
        for i, (name, width) in enumerate(columns):
            fmt = wx.LIST_FORMAT_RIGHT if name in ("Total",) else wx.LIST_FORMAT_LEFT
            self._list.InsertColumn(i, name, fmt, width)

        self._list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_item_dblclick)
        self._list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_selection_changed)
        self._list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_selection_changed)
        main_sizer.Add(
            self._list, 1,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
            theme.SPACE_LG,
        )

        # --- Toolbar ---
        toolbar = wx.Panel(panel)
        toolbar.SetBackgroundColour(theme.BG_SECONDARY)
        tb_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._btn_preview = wx.Button(toolbar, label="Previsualizar")
        self._btn_preview.SetFont(theme.font_base())
        self._btn_preview.Bind(wx.EVT_BUTTON, self._on_preview)

        self._btn_edit = wx.Button(toolbar, label="Editar \u25BC")
        self._btn_edit.SetFont(theme.font_base())
        self._btn_edit.Bind(wx.EVT_BUTTON, self._on_edit_menu)

        self._btn_pdf = wx.Button(toolbar, label="Exportar PDF")
        self._btn_pdf.SetFont(theme.font_base())
        self._btn_pdf.Bind(wx.EVT_BUTTON, self._on_export_pdf)

        self._btn_open = wx.Button(toolbar, label="Abrir Excel")
        self._btn_open.SetFont(theme.font_base())
        self._btn_open.SetBackgroundColour(theme.ACCENT_PRIMARY)
        self._btn_open.SetForegroundColour(theme.TEXT_INVERSE)
        self._btn_open.Bind(wx.EVT_BUTTON, self._on_open_excel)

        self._btn_folder = wx.Button(toolbar, label="Abrir carpeta")
        self._btn_folder.SetFont(theme.font_base())
        self._btn_folder.Bind(wx.EVT_BUTTON, self._on_open_folder)

        self._btn_delete = wx.Button(toolbar, label="Eliminar")
        self._btn_delete.SetFont(theme.font_base())
        self._btn_delete.SetForegroundColour(theme.ERROR)
        self._btn_delete.Bind(wx.EVT_BUTTON, self._on_delete)

        for btn in (
            self._btn_preview, self._btn_edit, self._btn_pdf,
            self._btn_open, self._btn_folder, self._btn_delete,
        ):
            tb_sizer.Add(btn, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, theme.SPACE_SM)

        toolbar.SetSizer(tb_sizer)
        main_sizer.Add(toolbar, 0, wx.EXPAND | wx.ALL, theme.SPACE_LG)

        panel.SetSizer(main_sizer)
        self._update_buttons()

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def _refresh_list(self, search_text=""):
        """Recarga la lista desde la BD."""
        if search_text.strip():
            self._historial = repo.buscar_historial(search_text)
        else:
            self._historial = repo.get_historial_reciente()
        self._populate_list()

    def _populate_list(self):
        self._list.DeleteAllItems()
        for i, h in enumerate(self._historial):
            exists = os.path.exists(h["ruta_excel"]) if h["ruta_excel"] else False
            nombre = h["nombre_proyecto"]
            if not exists:
                nombre = f"\u26A0 {nombre}"

            idx = self._list.InsertItem(i, nombre)
            self._list.SetItem(idx, 1, h.get("cliente") or "")
            self._list.SetItem(idx, 2, h.get("localidad") or "")
            self._list.SetItem(idx, 3, h.get("tipo_obra") or "")

            fecha_raw = h.get("fecha_creacion") or ""
            if len(fecha_raw) >= 10:
                try:
                    parts = fecha_raw[:10].split("-")
                    fecha = f"{parts[2]}/{parts[1]}/{parts[0]}"
                except (IndexError, ValueError):
                    fecha = fecha_raw[:10]
            else:
                fecha = fecha_raw
            self._list.SetItem(idx, 4, fecha)

            total = h.get("total_presupuesto")
            if total is not None:
                t = f"{total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                self._list.SetItem(idx, 5, f"{t} \u20AC")

            self._list.SetItem(idx, 6, "\u2713" if h.get("usa_partidas_ia") else "")

            if not exists:
                self._list.SetItemTextColour(idx, theme.TEXT_TERTIARY)
        self._update_buttons()

    def _get_selected(self):
        """Devuelve el dict del presupuesto seleccionado o None."""
        idx = self._list.GetFirstSelected()
        if idx < 0 or idx >= len(self._historial):
            return None
        return self._historial[idx]

    # ------------------------------------------------------------------
    # Eventos de búsqueda
    # ------------------------------------------------------------------

    def _on_search(self, event):
        self._refresh_list(self._search.GetValue())

    def _on_search_cancel(self, event):
        self._search.SetValue("")
        self._refresh_list()

    # ------------------------------------------------------------------
    # Selección y doble-clic
    # ------------------------------------------------------------------

    def _on_selection_changed(self, event):
        self._update_buttons()
        event.Skip()

    def _update_buttons(self):
        selected = self._get_selected()
        has_sel = selected is not None
        file_ok = has_sel and os.path.exists(selected.get("ruta_excel", ""))
        for btn in (self._btn_preview, self._btn_edit, self._btn_pdf,
                    self._btn_open, self._btn_folder, self._btn_delete):
            btn.Enable(has_sel)
        if has_sel and not file_ok:
            self._btn_preview.Enable(False)
            self._btn_edit.Enable(False)
            self._btn_pdf.Enable(False)
            self._btn_open.Enable(False)

    def _on_item_dblclick(self, event):
        self._on_preview(event)

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _on_preview(self, event):
        selected = self._get_selected()
        if not selected:
            return
        ruta = selected.get("ruta_excel", "")
        if not os.path.exists(ruta):
            wx.MessageBox("El archivo ya no existe.", "Error", wx.OK | wx.ICON_WARNING)
            return
        from src.gui.budget_preview_dialog_wx import BudgetPreviewDialog
        dlg = BudgetPreviewDialog(self, ruta)
        dlg.ShowModal()
        dlg.Destroy()

    def _on_edit_menu(self, event):
        selected = self._get_selected()
        if not selected:
            return
        ruta = selected.get("ruta_excel", "")
        if not os.path.exists(ruta):
            wx.MessageBox("El archivo ya no existe.", "Error", wx.OK | wx.ICON_WARNING)
            return

        menu = wx.Menu()
        id_regen = wx.NewIdRef()
        id_add = wx.NewIdRef()
        id_header = wx.NewIdRef()

        menu.Append(id_regen, "Regenerar todas las partidas (IA)")
        menu.Append(id_add, "A\u00f1adir m\u00e1s partidas (IA)")
        menu.AppendSeparator()
        menu.Append(id_header, "Regenerar campos del presupuesto")

        self.Bind(wx.EVT_MENU, lambda e: self._edit_regen_all(ruta), id=id_regen)
        self.Bind(wx.EVT_MENU, lambda e: self._edit_add_partidas(ruta), id=id_add)
        self.Bind(wx.EVT_MENU, lambda e: self._edit_regen_header(ruta), id=id_header)

        self._btn_edit.PopupMenu(menu)
        menu.Destroy()

    def _on_export_pdf(self, event):
        selected = self._get_selected()
        if not selected:
            return
        ruta = selected.get("ruta_excel", "")
        if not os.path.exists(ruta):
            wx.MessageBox("El archivo ya no existe.", "Error", wx.OK | wx.ICON_WARNING)
            return
        from src.core.pdf_exporter import PDFExporter
        exporter = PDFExporter()
        if not exporter.is_available():
            wx.MessageBox(
                "Microsoft Excel no est\u00e1 disponible.\n"
                "Para exportar a PDF se necesita Excel instalado.",
                "Exportar PDF", wx.OK | wx.ICON_WARNING,
            )
            return
        ok, result = exporter.export(ruta)
        if ok:
            resp = wx.MessageBox(
                f"PDF generado:\n{result}\n\n\u00bfDesea abrirlo?",
                "PDF exportado", wx.YES_NO | wx.ICON_INFORMATION,
            )
            if resp == wx.YES:
                self._open_file(result)
        else:
            wx.MessageBox(f"Error al exportar PDF:\n{result}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_open_excel(self, event):
        selected = self._get_selected()
        if not selected:
            return
        ruta = selected.get("ruta_excel", "")
        if not os.path.exists(ruta):
            wx.MessageBox("El archivo ya no existe.", "Error", wx.OK | wx.ICON_WARNING)
            return
        repo.actualizar_acceso(ruta)
        self._open_file(ruta)

    def _on_open_folder(self, event):
        selected = self._get_selected()
        if not selected:
            return
        folder = selected.get("ruta_carpeta") or ""
        if not folder or not os.path.isdir(folder):
            ruta = selected.get("ruta_excel", "")
            folder = os.path.dirname(ruta) if ruta else ""
        if folder and os.path.isdir(folder):
            self._open_file(folder)
        else:
            wx.MessageBox("No se encontr\u00f3 la carpeta.", "Error", wx.OK | wx.ICON_WARNING)

    def _on_delete(self, event):
        selected = self._get_selected()
        if not selected:
            return
        resp = wx.MessageBox(
            f"\u00bfEliminar del historial?\n\n"
            f"{selected['nombre_proyecto']}\n\n"
            f"(El archivo no se borrar\u00e1)",
            "Confirmar", wx.YES_NO | wx.ICON_QUESTION,
        )
        if resp == wx.YES:
            repo.eliminar_historial(selected["id"])
            self._refresh_list(self._search.GetValue())

    # ------------------------------------------------------------------
    # Edición
    # ------------------------------------------------------------------

    def _edit_regen_all(self, ruta):
        """Regenerar todas las partidas con IA."""
        from src.gui.ai_budget_dialog_wx import AIBudgetDialog
        from src.gui.partidas_dialog_wx import SuggestedPartidasDialog
        from src.core.excel_manager import ExcelManager

        ai_dlg = AIBudgetDialog(self)
        if ai_dlg.ShowModal() != wx.ID_OK:
            ai_dlg.Destroy()
            return
        result = ai_dlg.get_result()
        ai_dlg.Destroy()
        if not result or not result.get("partidas"):
            wx.MessageBox("No se generaron partidas.", "Aviso", wx.OK)
            return

        partidas_dlg = SuggestedPartidasDialog(self, result)
        if partidas_dlg.ShowModal() != wx.ID_OK:
            partidas_dlg.Destroy()
            return
        selected_partidas = partidas_dlg.get_selected_partidas()
        partidas_dlg.Destroy()

        if not selected_partidas:
            return

        em = ExcelManager()
        if em.insert_partidas_via_xml(ruta, selected_partidas):
            from src.core.budget_reader import BudgetReader
            reader = BudgetReader()
            data = reader.read(ruta)
            if data:
                repo.actualizar_total(ruta, data["total"])
            wx.MessageBox(
                f"Partidas regeneradas ({len(selected_partidas)}).",
                "\u00c9xito", wx.OK,
            )
            self._refresh_list(self._search.GetValue())
        else:
            wx.MessageBox("Error al insertar partidas.", "Error", wx.OK | wx.ICON_ERROR)

    def _edit_add_partidas(self, ruta):
        """Añadir más partidas con IA a un presupuesto existente."""
        from src.core.budget_reader import BudgetReader
        from src.gui.ai_budget_dialog_wx import AIBudgetDialog
        from src.gui.partidas_dialog_wx import SuggestedPartidasDialog
        from src.core.excel_manager import ExcelManager

        reader = BudgetReader()
        existing = reader.read(ruta)
        existing_partidas = existing["partidas"] if existing else []

        context = ""
        if existing_partidas:
            conceptos = [p["concepto"] for p in existing_partidas]
            context = (
                f"Ya existen {len(existing_partidas)} partidas: "
                + ", ".join(conceptos[:10])
                + (". " if len(conceptos) <= 10 else "... ")
                + "Genera partidas ADICIONALES que complementen las existentes."
            )

        ai_dlg = AIBudgetDialog(self, context_extra=context)
        if ai_dlg.ShowModal() != wx.ID_OK:
            ai_dlg.Destroy()
            return
        result = ai_dlg.get_result()
        ai_dlg.Destroy()
        if not result or not result.get("partidas"):
            wx.MessageBox("No se generaron partidas.", "Aviso", wx.OK)
            return

        partidas_dlg = SuggestedPartidasDialog(self, result)
        if partidas_dlg.ShowModal() != wx.ID_OK:
            partidas_dlg.Destroy()
            return
        selected_partidas = partidas_dlg.get_selected_partidas()
        partidas_dlg.Destroy()

        if not selected_partidas:
            return

        em = ExcelManager()
        if em.append_partidas_via_xml(ruta, selected_partidas):
            data = reader.read(ruta)
            if data:
                repo.actualizar_total(ruta, data["total"])
            wx.MessageBox(
                f"{len(selected_partidas)} partidas a\u00f1adidas.",
                "\u00c9xito", wx.OK,
            )
            self._refresh_list(self._search.GetValue())
        else:
            wx.MessageBox("Error al a\u00f1adir partidas.", "Error", wx.OK | wx.ICON_ERROR)

    def _edit_regen_header(self, ruta):
        """Regenerar campos de cabecera del presupuesto."""
        from src.core.excel_manager import ExcelManager

        project_data, project_name = self._obtain_project_data()
        if not project_data:
            return

        comunidad_data = None
        if hasattr(self._parent, "_buscar_comunidad_para_presupuesto"):
            comunidad_data = self._parent._buscar_comunidad_para_presupuesto(
                project_data.get("cliente", "")
            )

        excel_data = {
            "nombre_obra": project_name or "",
            "numero_proyecto": project_data.get("numero", ""),
            "fecha": project_data.get("fecha", ""),
            "cliente": project_data.get("cliente", ""),
            "calle": project_data.get("calle", ""),
            "num_calle": project_data.get("num_calle", ""),
            "codigo_postal": project_data.get("codigo_postal", ""),
            "tipo": project_data.get("tipo", ""),
            "admin_cif": comunidad_data.get("cif", "") if comunidad_data else "",
            "admin_email": comunidad_data.get("email", "") if comunidad_data else "",
            "admin_telefono": comunidad_data.get("telefono", "") if comunidad_data else "",
        }

        em = ExcelManager()
        if em.update_header_fields(ruta, excel_data):
            selected = self._get_selected()
            if selected:
                repo.registrar_presupuesto({
                    "nombre_proyecto": project_name or selected["nombre_proyecto"],
                    "ruta_excel": ruta,
                    "ruta_carpeta": selected.get("ruta_carpeta"),
                    "fecha_creacion": selected.get("fecha_creacion"),
                    "cliente": project_data.get("cliente", ""),
                    "localidad": project_data.get("localidad", ""),
                    "tipo_obra": project_data.get("tipo", ""),
                    "numero_proyecto": project_data.get("numero", ""),
                })
            wx.MessageBox("Campos actualizados.", "\u00c9xito", wx.OK)
            self._refresh_list(self._search.GetValue())
        else:
            wx.MessageBox("Error al actualizar campos.", "Error", wx.OK | wx.ICON_ERROR)

    # ------------------------------------------------------------------
    # Obtención de datos de proyecto (relación Excel o portapapeles)
    # ------------------------------------------------------------------

    def _obtain_project_data(self):
        """Obtiene ``(project_data, project_name)`` intentando primero el Excel de relación."""
        from src.gui.dialogs_wx import obtain_project_data
        return obtain_project_data(self)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _open_file(path):
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", path], check=True)
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.run(["xdg-open", path], check=True)
        except Exception:
            pass
