"""Tests para src.core.project_data_resolver."""

import pytest
from unittest.mock import patch, MagicMock

from src.core.project_data_resolver import (
    resolve_projects,
    build_relation_index,
    _empty_entry,
    _fill_from_relation,
)


class TestEmptyEntry:
    def test_builds_expected_keys(self):
        proj = {
            "nombre_carpeta": "122-20 Portal",
            "numero_proyecto": "122-20",
            "ruta_excel": "/ruta/excel.xlsx",
            "ruta_carpeta": "/ruta",
        }
        entry = _empty_entry(proj)
        assert entry["nombre_proyecto"] == "122-20 Portal"
        assert entry["numero"] == "122-20"
        assert entry["ruta_excel"] == "/ruta/excel.xlsx"
        assert entry["cliente"] == ""
        assert entry["total"] is None

    def test_handles_missing_keys(self):
        entry = _empty_entry({})
        assert entry["nombre_proyecto"] == ""
        assert entry["numero"] == ""


class TestFillFromRelation:
    def test_fills_fields(self):
        entry = _empty_entry({"nombre_carpeta": "x", "numero_proyecto": "1-25"})
        rel = {
            "cliente": "ACME",
            "localidad": "Madrid",
            "tipo": "Reforma",
            "fecha": "08-01-26",
            "importe": "1234.56",
        }
        _fill_from_relation(entry, rel)
        assert entry["cliente"] == "ACME"
        assert entry["localidad"] == "Madrid"
        assert entry["tipo_obra"] == "Reforma"
        assert entry["fecha"] == "08-01-26"
        assert entry["total"] == pytest.approx(1234.56)

    def test_invalid_importe_ignored(self):
        entry = _empty_entry({"nombre_carpeta": "x"})
        _fill_from_relation(entry, {"importe": "no-number"})
        assert entry["total"] is None


class TestResolveProjects:
    def test_fills_from_relation_index(self):
        scanned = [{
            "nombre_carpeta": "122-20 Portal",
            "numero_proyecto": "122-20",
            "ruta_excel": "/excel.xlsx",
            "ruta_carpeta": "/dir",
        }]
        rel_index = {
            "122-20": {
                "cliente": "ACME",
                "localidad": "Madrid",
                "tipo": "Obra",
                "fecha": "01-02-26",
                "importe": "5000",
            }
        }
        result = resolve_projects(scanned, rel_index)
        assert len(result) == 1
        assert result[0]["cliente"] == "ACME"
        assert result[0]["total"] == pytest.approx(5000)

    @patch("src.core.project_data_resolver.BudgetReader")
    def test_falls_back_to_budget_reader(self, MockReader):
        mock_instance = MockReader.return_value
        mock_instance.read.return_value = {
            "cabecera": {"cliente": "Reader Client", "direccion": "Dir", "obra": "Tipo", "fecha": "01-01-26"},
            "total": 999.0,
        }
        scanned = [{
            "nombre_carpeta": "1-25 Test",
            "numero_proyecto": "1-25",
            "ruta_excel": "/some.xlsx",
            "ruta_carpeta": "/dir",
        }]
        result = resolve_projects(scanned, None)
        assert result[0]["cliente"] == "Reader Client"
        assert result[0]["total"] == pytest.approx(999.0)

    def test_empty_scanned(self):
        assert resolve_projects([], {}) == []


class TestBuildRelationIndex:
    @patch("src.core.project_data_resolver.Settings")
    @patch("src.core.project_data_resolver.ExcelRelationReader")
    def test_returns_index(self, MockReader, MockSettings):
        MockSettings.return_value.get_default_path.return_value = "/rel.xlsx"
        MockReader.return_value.read.return_value = (
            [{"numero": "122-20", "cliente": "A"}, {"numero": "123-20", "cliente": "B"}],
            None,
        )
        idx = build_relation_index()
        assert "122-20" in idx
        assert "123-20" in idx

    @patch("src.core.project_data_resolver.Settings")
    def test_returns_empty_when_no_path(self, MockSettings):
        MockSettings.return_value.get_default_path.return_value = None
        assert build_relation_index() == {}

    def test_explicit_file_not_found(self):
        idx = build_relation_index("/no/existe.xlsx")
        assert idx == {}
