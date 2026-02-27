"""Tests para src.core.project_data_resolver y src.core.budget_cache."""

import os

import pytest
from unittest.mock import patch, MagicMock

from src.core.project_data_resolver import (
    resolve_projects,
    build_relation_index,
)
from src.utils.budget_utils import normalize_date, normalize_project_num, strip_obra_prefix
from src.core.budget_cache import (
    _empty_entry,
    _fill_entry_from_cache,
    _get_file_mtime_iso,
    _is_template_data,
    _lookup_relation,
)


class TestNormalizeDate:
    def test_empty(self):
        assert normalize_date("") == ""

    def test_text_passthrough(self):
        assert normalize_date("08-01-26") == "08-01-26"

    def test_excel_serial(self):
        # 44174 = 06-12-20
        result = normalize_date("44174")
        assert result  # no vacío
        assert "-" in result


class TestStripObraPrefix:
    def test_removes_prefix(self):
        assert strip_obra_prefix("Obra: Reforma portal.") == "Reforma portal"

    def test_no_prefix(self):
        assert strip_obra_prefix("Reforma portal") == "Reforma portal"


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

    def test_includes_state(self):
        entry = _empty_entry({}, state_name="PRESUPUESTADO")
        assert entry["estado"] == "PRESUPUESTADO"


class TestFillEntryFromCache:
    def test_fills_fields(self):
        entry = _empty_entry({"nombre_carpeta": "x", "numero_proyecto": "1-25"})
        cached = {
            "cliente": "ACME",
            "localidad": "Madrid",
            "tipo_obra": "Reforma",
            "fecha": "08-01-26",
            "total": 1234.56,
            "datos_completos": True,
            "estado": "PRESUPUESTADO",
        }
        _fill_entry_from_cache(entry, cached)
        assert entry["cliente"] == "ACME"
        assert entry["localidad"] == "Madrid"
        assert entry["tipo_obra"] == "Reforma"
        assert entry["fecha"] == "08-01-26"
        assert entry["total"] == pytest.approx(1234.56)
        assert entry["datos_completos"] is True


class TestGetFileMtimeIso:
    def test_existing_file(self, tmp_path):
        f = tmp_path / "test.xlsx"
        f.write_bytes(b"\x00" * 100)
        result = _get_file_mtime_iso(str(f))
        assert result is not None
        assert "T" in result  # ISO format

    def test_nonexistent_file(self):
        assert _get_file_mtime_iso("/no/existe/nada.xlsx") is None


class TestNormalizeProjectNum:
    def test_dash_format(self):
        assert normalize_project_num("71-26") == "71-26"

    def test_slash_format(self):
        assert normalize_project_num("71/26") == "71-26"

    def test_three_digit(self):
        assert normalize_project_num("120/20") == "120-20"

    def test_empty(self):
        assert normalize_project_num("") == ""

    def test_no_match(self):
        assert normalize_project_num("abc") == ""

    def test_embedded_in_text(self):
        assert normalize_project_num("Presupuesto 71/26 reforma") == "71-26"

    def test_leading_zeros_stripped(self):
        assert normalize_project_num("06-26") == "6-26"

    def test_leading_zeros_match(self):
        assert normalize_project_num("06-26") == normalize_project_num("6/26")


class TestIsTemplateData:
    def test_detects_template_120_20(self):
        # 120/20 es la plantilla, carpeta es 20-26 → plantilla
        assert _is_template_data("120/20", "20-26") is True

    def test_detects_template_different_year(self):
        assert _is_template_data("120/20", "71-26") is True

    def test_real_data_matches(self):
        assert _is_template_data("71/26", "71-26") is False

    def test_real_data_matches_11(self):
        assert _is_template_data("11/26", "11-26") is False

    def test_real_data_with_leading_zeros(self):
        # "6/26" en Excel y "06-26" en carpeta → mismo proyecto, no es plantilla
        assert _is_template_data("6/26", "06-26") is False

    def test_empty_excel_number(self):
        # Sin número de Excel, no podemos afirmar que sea plantilla
        assert _is_template_data("", "71-26") is False

    def test_empty_expected_number(self):
        assert _is_template_data("71/26", "") is False

    def test_both_empty(self):
        assert _is_template_data("", "") is False


class TestLookupRelation:
    """Verifica que _lookup_relation enlaza proyectos con la relación."""

    _RELATION = {
        "1": {"cliente": "A", "importe": "4650"},
        "11": {"cliente": "B", "importe": "900"},
        "127-25": {"cliente": "C", "importe": "15000"},
    }

    def test_exact_match(self):
        """Clave exacta presente → la devuelve."""
        assert _lookup_relation(self._RELATION, "127-25") == self._RELATION["127-25"]

    def test_number_only_match(self):
        """'1-26' debe resolver a clave '1' (sin año)."""
        result = _lookup_relation(self._RELATION, "1-26")
        assert result is not None
        assert result["cliente"] == "A"

    def test_number_only_match_double_digit(self):
        """'11-26' debe resolver a clave '11'."""
        result = _lookup_relation(self._RELATION, "11-26")
        assert result is not None
        assert result["cliente"] == "B"

    def test_leading_zeros(self):
        """'06-26' debe resolver a clave '6' si existiera (o None)."""
        assert _lookup_relation(self._RELATION, "06-26") is None  # no hay '6'

    def test_leading_zeros_stripped_match(self):
        """'01-26' debe resolver a clave '1'."""
        result = _lookup_relation(self._RELATION, "01-26")
        assert result is not None
        assert result["cliente"] == "A"

    def test_not_found(self):
        assert _lookup_relation(self._RELATION, "999-26") is None

    def test_empty_index(self):
        assert _lookup_relation({}, "1-26") is None
        assert _lookup_relation(None, "1-26") is None

    def test_empty_numero(self):
        assert _lookup_relation(self._RELATION, "") is None


class TestResolveProjects:
    @patch("src.core.project_data_resolver.sync_presupuestos")
    def test_delegates_to_sync(self, mock_sync):
        mock_sync.return_value = [{"cliente": "ACME"}]
        scanned = [{"nombre_carpeta": "test", "numero_proyecto": "1-25"}]
        result = resolve_projects(scanned, {"1-25": {}}, "PRESUPUESTADO")
        mock_sync.assert_called_once_with(scanned, {"1-25": {}}, "PRESUPUESTADO")
        assert result == [{"cliente": "ACME"}]

    @patch("src.core.project_data_resolver.sync_presupuestos")
    def test_empty_scanned(self, mock_sync):
        mock_sync.return_value = []
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
