"""
Diálogo de previsualización de presupuesto (wxPython).

Muestra un resumen completo del presupuesto: datos de cabecera,
listado de partidas con importes y totales (subtotal, IVA, total).
"""

import os
import subprocess
import sys

import wx

from src.core.budget_reader import BudgetReader
from src.gui import theme


class BudgetPreviewDialog(wx.Dialog):
    """Previsualización de un presupuesto .xlsx."""

    def __init__(self, parent, file_path):
        super().__init__(
            parent, title="Previsualización del Presupuesto",
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._file_path = file_path
        self._data = None
        self._build_ui()
        self._load_data()
        theme.fit_dialog(self, min_w=720, min_h=560)

    def _build_ui(self):
        theme.style_dialog(self)
        self._main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Scrolled window for content
        self._scroll = wx.ScrolledWindow(self, style=wx.VSCROLL)
        self._scroll.SetScrollRate(0, 10)
        self._scroll.SetBackgroundColour(theme.BG_PRIMARY)
        self._scroll_sizer = wx.BoxSizer(wx.VERTICAL)
        self._scroll.SetSizer(self._scroll_sizer)

        self._main_sizer.Add(self._scroll, 1, wx.EXPAND)

        # Barra inferior de botones
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()

        btn_pdf = wx.Button(self, label="Exportar PDF")
        btn_pdf.SetFont(theme.font_base())
        btn_pdf.Bind(wx.EVT_BUTTON, self._on_export_pdf)
        btn_sizer.Add(btn_pdf, 0, wx.ALL, theme.SPACE_SM)

        btn_open = wx.Button(self, label="Abrir Excel")
        btn_open.SetFont(theme.font_base())
        btn_open.SetBackgroundColour(theme.ACCENT_PRIMARY)
        btn_open.SetForegroundColour(theme.TEXT_INVERSE)
        btn_open.Bind(wx.EVT_BUTTON, self._on_open_excel)
        btn_sizer.Add(btn_open, 0, wx.ALL, theme.SPACE_SM)

        btn_close = wx.Button(self, wx.ID_CLOSE, "Cerrar")
        btn_close.SetFont(theme.font_base())
        btn_close.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_CLOSE))
        btn_sizer.Add(btn_close, 0, wx.ALL, theme.SPACE_SM)

        self._main_sizer.Add(
            btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            theme.SPACE_MD,
        )
        self.SetSizer(self._main_sizer)

    def _load_data(self):
        reader = BudgetReader()
        self._data = reader.read(self._file_path)
        if not self._data:
            lbl = theme.create_text(
                self._scroll,
                "No se pudo leer el presupuesto.",
                muted=True,
            )
            self._scroll_sizer.Add(lbl, 0, wx.ALL, theme.SPACE_XL)
            return
        self._render_header()
        self._render_partidas()
        self._render_totals()
        self._scroll.FitInside()

    @staticmethod
    def _fmt_euro(value):
        """Formatea un número como euros con convención española (. miles, , decimal)."""
        try:
            val = float(value)
        except (TypeError, ValueError):
            return "0,00 \u20AC"
        txt = f"{val:,.2f}"
        txt = txt.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{txt} \u20AC"

    @staticmethod
    def _fmt_qty(value):
        """Formatea cantidad: sin decimales si es entero, 2 decimales si no."""
        try:
            val = float(value)
        except (TypeError, ValueError):
            return "0"
        if val == int(val):
            return str(int(val))
        return f"{val:.2f}".replace(".", ",")

    def _render_header(self):
        cab = self._data["cabecera"]
        card = theme.Card(self._scroll, padding=theme.SPACE_MD)
        sizer = card.GetInnerSizer()

        title = theme.create_title(card, "Datos del Proyecto", "lg")
        sizer.Add(title, 0, wx.BOTTOM, theme.SPACE_SM)
        sizer.Add(theme.create_divider(card), 0, wx.EXPAND | wx.BOTTOM, theme.SPACE_SM)

        fields = [
            ("Proyecto", cab.get("numero", "")),
            ("Fecha", cab.get("fecha", "")),
            ("Cliente", cab.get("cliente", "")),
            ("Dirección", cab.get("direccion", "")),
            ("Código Postal", cab.get("codigo_postal", "")),
            ("Obra", cab.get("obra", "")),
            ("CIF Admin.", cab.get("cif_admin", "")),
            ("Email Admin.", cab.get("email_admin", "")),
            ("Teléfono Admin.", cab.get("telefono_admin", "")),
        ]
        visible = [(l, v) for l, v in fields if v]

        grid = wx.FlexGridSizer(cols=2, hgap=theme.SPACE_LG, vgap=theme.SPACE_SM)
        grid.AddGrowableCol(1)

        for label_text, value in visible:
            lbl = wx.StaticText(card, label=f"{label_text}:")
            lbl.SetFont(theme.create_font(10, wx.FONTWEIGHT_MEDIUM))
            lbl.SetForegroundColour(theme.TEXT_SECONDARY)
            grid.Add(lbl, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)

            val = wx.StaticText(card, label=value)
            val.SetFont(theme.font_base())
            val.SetForegroundColour(theme.TEXT_PRIMARY)
            grid.Add(val, 1, wx.EXPAND | wx.ALIGN_CENTER_VERTICAL)

        sizer.Add(grid, 0, wx.EXPAND)
        self._scroll_sizer.Add(
            card, 0, wx.EXPAND | wx.ALL, theme.SPACE_LG,
        )

    def _render_partidas(self):
        partidas = self._data["partidas"]
        if not partidas:
            return

        card = theme.Card(self._scroll, padding=theme.SPACE_MD)
        sizer = card.GetInnerSizer()

        title = theme.create_title(card, f"Partidas ({len(partidas)})", "lg")
        sizer.Add(title, 0, wx.BOTTOM, theme.SPACE_SM)
        sizer.Add(theme.create_divider(card), 0, wx.EXPAND | wx.BOTTOM, theme.SPACE_SM)

        list_height = min(len(partidas) * 26 + 32, 360)
        list_ctrl = wx.ListCtrl(
            card,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE,
            size=(-1, list_height),
        )
        theme.style_listctrl(list_ctrl)

        list_ctrl.InsertColumn(0, "Num", width=50)
        list_ctrl.InsertColumn(1, "Concepto", width=300)
        list_ctrl.InsertColumn(2, "Ud", width=45)
        list_ctrl.InsertColumn(3, "Cant.", wx.LIST_FORMAT_RIGHT, width=60)
        list_ctrl.InsertColumn(4, "Precio", wx.LIST_FORMAT_RIGHT, width=85)
        list_ctrl.InsertColumn(5, "Importe", wx.LIST_FORMAT_RIGHT, width=95)

        for i, p in enumerate(partidas):
            idx = list_ctrl.InsertItem(i, p.get("numero", ""))
            concepto = p.get("concepto", "").replace("\n", " ").replace("&#10;", " ")
            list_ctrl.SetItem(idx, 1, concepto[:100])
            list_ctrl.SetItem(idx, 2, p.get("unidad", ""))
            list_ctrl.SetItem(idx, 3, self._fmt_qty(p.get("cantidad", 0)))
            list_ctrl.SetItem(idx, 4, self._fmt_euro(p.get("precio", 0)))
            list_ctrl.SetItem(idx, 5, self._fmt_euro(p.get("importe", 0)))

        sizer.Add(list_ctrl, 0, wx.EXPAND)
        self._scroll_sizer.Add(card, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, theme.SPACE_LG)

    def _render_totals(self):
        card = theme.Card(self._scroll, padding=theme.SPACE_MD)
        sizer = card.GetInnerSizer()

        entries = [
            ("Subtotal", self._fmt_euro(self._data.get("subtotal", 0))),
            ("IVA (10%)", self._fmt_euro(self._data.get("iva", 0))),
        ]

        for label_text, value in entries:
            row = wx.BoxSizer(wx.HORIZONTAL)
            lbl = wx.StaticText(card, label=label_text)
            lbl.SetFont(theme.font_base())
            lbl.SetForegroundColour(theme.TEXT_SECONDARY)
            row.Add(lbl, 1)
            val = wx.StaticText(card, label=value)
            val.SetFont(theme.font_base())
            val.SetForegroundColour(theme.TEXT_PRIMARY)
            row.Add(val, 0)
            sizer.Add(row, 0, wx.EXPAND | wx.BOTTOM, theme.SPACE_XS)

        sizer.Add(
            theme.create_divider(card), 0,
            wx.EXPAND | wx.TOP | wx.BOTTOM, theme.SPACE_SM,
        )

        total_sizer = wx.BoxSizer(wx.HORIZONTAL)
        lbl = wx.StaticText(card, label="TOTAL")
        lbl.SetFont(theme.create_font(14, wx.FONTWEIGHT_BOLD))
        lbl.SetForegroundColour(theme.TEXT_PRIMARY)
        total_sizer.Add(lbl, 1)
        val = wx.StaticText(
            card, label=self._fmt_euro(self._data.get("total", 0)),
        )
        val.SetFont(theme.create_font(14, wx.FONTWEIGHT_BOLD))
        val.SetForegroundColour(theme.ACCENT_PRIMARY)
        total_sizer.Add(val, 0)
        sizer.Add(total_sizer, 0, wx.EXPAND)

        self._scroll_sizer.Add(
            card, 0, wx.EXPAND | wx.ALL, theme.SPACE_LG,
        )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _on_export_pdf(self, event):
        from src.core.pdf_exporter import PDFExporter
        exporter = PDFExporter()
        if not exporter.is_available():
            wx.MessageBox(
                "Microsoft Excel no est\u00e1 disponible.\n"
                "Para exportar a PDF se necesita Excel instalado.",
                "Exportar PDF", wx.OK | wx.ICON_WARNING,
            )
            return
        ok, result = exporter.export(self._file_path)
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
        self._open_file(self._file_path)

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
