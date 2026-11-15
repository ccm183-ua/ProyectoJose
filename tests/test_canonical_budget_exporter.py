"""
Tests del adapter de exportacion del dominio canonico (H3): genera un Excel
real desde la plantilla 122-20 y lo relee con BudgetReader para comprobar
cabecera, partidas y totales. El PDF (requiere Excel/COM real) se prueba con
un doble inyectado, sin Excel real.
"""

import os

import pytest

from src.core.budget_reader import BudgetReader
from src.core.canonical_budget_exporter import export_budget_to_excel, export_budget_to_pdf
from src.core.repositories.canonical_budget_repository import create_budget_with_first_version
from src.core.repositories.presupuesto_cache_repository import upsert_presupuesto
from src.core.template_manager import TemplateManager


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_exporter_test.db"))
    return tmp_path


@pytest.fixture
def template_path():
    path = TemplateManager().get_template_path()
    if not os.path.exists(path):
        pytest.skip("Plantilla 122-20 no encontrada")
    return path


def _sample_lines():
    return [
        {"concepto": "Sustitucion bajante PVC", "unidad": "ml", "cantidad": 10, "precio": 20.0, "source": "historical"},
        {"concepto": "Pintura fachada", "unidad": "m2", "cantidad": 5, "precio": 12.0, "source": "ai_completion"},
    ]


def test_export_budget_to_excel_writes_header_and_lines(db_env, template_path, tmp_path):
    budget_id, err = create_budget_with_first_version(
        "Obra exportable", _sample_lines(), numero_proyecto="1-26",
    )
    assert err is None

    output_path = str(tmp_path / "exportado.xlsx")
    result = export_budget_to_excel(budget_id, output_path)

    assert result.success is True
    assert result.output_path == output_path
    assert os.path.exists(output_path)

    data = BudgetReader().read(output_path)
    assert data is not None
    conceptos = [p["concepto"] for p in data["partidas"]]
    assert any("SUSTITUCION BAJANTE" in c.upper() for c in conceptos)
    assert any("PINTURA FACHADA" in c.upper() for c in conceptos)
    assert data["total"] == pytest.approx(286.0)  # (200+60) * 1.10


def test_export_budget_to_excel_enriches_header_from_legacy_presupuesto(db_env, template_path, tmp_path):
    from datetime import datetime

    legacy_id, err = upsert_presupuesto({
        "nombre_proyecto": "Obra legado",
        "ruta_excel": str(tmp_path / "legado.xlsx"),
        "fecha_modificacion_excel": datetime.now().isoformat(),
        "fecha_cache": datetime.now().isoformat(),
        "cliente": "Comunidad Legado SL",
        "codigo_postal": "28001",
    })
    assert err is None

    budget_id, err = create_budget_with_first_version(
        "Obra con cliente", _sample_lines(), presupuesto_legacy_id=legacy_id,
    )
    assert err is None

    output_path = str(tmp_path / "exportado_legado.xlsx")
    result = export_budget_to_excel(budget_id, output_path)
    assert result.success is True

    data = BudgetReader().read(output_path)
    assert data["cabecera"]["cliente"] == "Comunidad Legado SL"


def test_export_budget_to_excel_unknown_budget_fails_cleanly(db_env, template_path, tmp_path):
    result = export_budget_to_excel(999999, str(tmp_path / "no_existe.xlsx"))
    assert result.success is False
    assert "no se encontro" in result.error.lower()


class _FakePdfExporter:
    def __init__(self, ok=True, path_or_error="C:/fake/output.pdf"):
        self._ok = ok
        self._path_or_error = path_or_error
        self.calls = []

    def export(self, xlsx_path, pdf_path=None):
        self.calls.append((xlsx_path, pdf_path))
        return self._ok, self._path_or_error


def test_export_budget_to_pdf_success_with_fake_exporter():
    fake = _FakePdfExporter(ok=True, path_or_error="C:/fake/output.pdf")
    result = export_budget_to_pdf("C:/fake/input.xlsx", pdf_exporter=fake)

    assert result.success is True
    assert result.output_path == "C:/fake/output.pdf"
    assert fake.calls == [("C:/fake/input.xlsx", None)]


def test_export_budget_to_pdf_failure_with_fake_exporter():
    fake = _FakePdfExporter(ok=False, path_or_error="win32com no disponible")
    result = export_budget_to_pdf("C:/fake/input.xlsx", pdf_exporter=fake)

    assert result.success is False
    assert result.error == "win32com no disponible"
