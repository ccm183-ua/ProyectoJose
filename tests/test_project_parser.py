"""Tests para src.core.project_parser."""

import pytest

from src.core.project_parser import ProjectParser


@pytest.fixture
def parser():
    return ProjectParser()


class TestParseClipboardData:
    VALID_TSV = "122-20\t08-01-26\tCliente X\tMediación\tCalle Y\t5\t28001\tMadrid\tReforma"

    def test_valid_input(self, parser):
        data, err = parser.parse_clipboard_data(self.VALID_TSV)
        assert err is None
        assert data["numero"] == "122-20"
        assert data["fecha"] == "08-01-26"
        assert data["cliente"] == "Cliente X"
        assert data["calle"] == "Calle Y"
        assert data["localidad"] == "Madrid"
        assert data["tipo"] == "Reforma"

    def test_empty_clipboard(self, parser):
        data, err = parser.parse_clipboard_data("")
        assert data is None
        assert "vacío" in err

    def test_none_clipboard(self, parser):
        data, err = parser.parse_clipboard_data(None)
        assert data is None

    def test_too_few_columns(self, parser):
        data, err = parser.parse_clipboard_data("a\tb\tc")
        assert data is None
        assert "columnas" in err.lower()

    def test_missing_numero_returns_error(self, parser):
        """Cuando la primera columna (Nº) está vacía tras strip, el parser retorna error."""
        tsv = "\t08-01-26\tCliente\tMed\tCalle\t5\t28001\tLoc\tTipo"
        data, err = parser.parse_clipboard_data(tsv)
        assert data is None
        assert err is not None

    def test_missing_fecha(self, parser):
        tsv = "122-20\t\tCliente\tMed\tCalle\t5\t28001\tLoc\tTipo"
        data, err = parser.parse_clipboard_data(tsv)
        assert data is None
        assert "FECHA" in err

    def test_missing_cliente(self, parser):
        tsv = "122-20\t08-01-26\t\tMed\tCalle\t5\t28001\tLoc\tTipo"
        data, err = parser.parse_clipboard_data(tsv)
        assert data is None
        assert "CLIENTE" in err

    def test_missing_calle(self, parser):
        tsv = "122-20\t08-01-26\tCliente\tMed\t\t5\t28001\tLoc\tTipo"
        data, err = parser.parse_clipboard_data(tsv)
        assert data is None
        assert "CALLE" in err

    def test_invalid_date_format(self, parser):
        tsv = "122-20\t2026-01-08\tCliente\tMed\tCalle\t5\t28001\tLoc\tTipo"
        data, err = parser.parse_clipboard_data(tsv)
        assert data is None
        assert "fecha" in err.lower()

    def test_optional_fields_empty(self, parser):
        tsv = "122-20\t08-01-26\tCliente\t-\tCalle\t-\t-\t-\t-"
        data, err = parser.parse_clipboard_data(tsv)
        assert err is None
        assert data["numero"] == "122-20"
        assert data["mediacion"] == "-"
        assert data["num_calle"] == "-"

    def test_optional_fields_with_content(self, parser):
        tsv = "122-20\t08-01-26\tCliente\tMediacion\tCalle\t10\t28001\tMadrid\tReforma"
        data, err = parser.parse_clipboard_data(tsv)
        assert err is None
        assert data["mediacion"] == "Mediacion"
        assert data["codigo_postal"] == "28001"
        assert data["localidad"] == "Madrid"
        assert data["tipo"] == "Reforma"

    def test_extra_columns_ignored(self, parser):
        tsv = "122-20\t08-01-26\tCliente\tMed\tCalle\t5\t28001\tLoc\tTipo\tExtra1\tExtra2"
        data, err = parser.parse_clipboard_data(tsv)
        assert err is None
        assert data["numero"] == "122-20"


class TestValidateDateFormat:
    def test_valid(self, parser):
        assert parser._validate_date_format("08-01-26") is True

    def test_invalid_separator(self, parser):
        assert parser._validate_date_format("08/01/26") is False

    def test_too_long(self, parser):
        assert parser._validate_date_format("08-01-2026") is False

    def test_empty(self, parser):
        assert parser._validate_date_format("") is False


class TestExtractYear:
    def test_normal(self, parser):
        assert parser.extract_year_from_date("08-01-26") == "26"

    def test_empty(self, parser):
        assert parser.extract_year_from_date("") == ""

    def test_none(self, parser):
        assert parser.extract_year_from_date(None) == ""

    def test_malformed(self, parser):
        assert parser.extract_year_from_date("no-date") == ""
