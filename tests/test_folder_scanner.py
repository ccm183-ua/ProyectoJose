"""Tests para src.core.folder_scanner."""

import os

import pytest

from src.core import folder_scanner


class TestExtractProjectNumber:
    def test_standard_format(self):
        assert folder_scanner._extract_project_number("122-20 Reforma portal") == "122-20"

    def test_longer_number(self):
        assert folder_scanner._extract_project_number("1234-25 Obra") == "1234-25"

    def test_single_digit(self):
        assert folder_scanner._extract_project_number("5-21 Mini") == "5-21"

    def test_no_number(self):
        assert folder_scanner._extract_project_number("Sin numero") is None

    def test_empty(self):
        assert folder_scanner._extract_project_number("") is None


class TestScanRoot:
    def test_returns_sorted_subdirs(self, tmp_path):
        (tmp_path / "PRESUPUESTADOS").mkdir()
        (tmp_path / "ACEPTADOS").mkdir()
        (tmp_path / "some_file.txt").write_text("x")

        result = folder_scanner.scan_root(str(tmp_path))
        assert result == ["ACEPTADOS", "PRESUPUESTADOS"]

    def test_empty_dir(self, tmp_path):
        assert folder_scanner.scan_root(str(tmp_path)) == []

    def test_nonexistent_path(self):
        assert folder_scanner.scan_root("/no/existe/esto") == []

    def test_none_path(self):
        assert folder_scanner.scan_root(None) == []

    def test_empty_string(self):
        assert folder_scanner.scan_root("") == []


class TestScanProjects:
    def _make_xlsx(self, path, size=5000):
        """Crea un archivo .xlsx falso de tamaño suficiente."""
        path.write_bytes(b"\0" * size)

    def test_finds_projects(self, tmp_path):
        proj = tmp_path / "122-20 Portal"
        proj.mkdir()
        self._make_xlsx(proj / "122-20 Presupuesto.xlsx")

        result = folder_scanner.scan_projects(str(tmp_path))
        assert len(result) == 1
        assert result[0]["numero_proyecto"] == "122-20"
        assert result[0]["ruta_excel"].endswith(".xlsx")

    def test_ignores_files_at_top_level(self, tmp_path):
        (tmp_path / "not_a_dir.xlsx").write_bytes(b"\0" * 5000)
        result = folder_scanner.scan_projects(str(tmp_path))
        assert result == []

    def test_project_without_xlsx(self, tmp_path):
        (tmp_path / "122-20 Vacio").mkdir()
        result = folder_scanner.scan_projects(str(tmp_path))
        assert len(result) == 1
        assert result[0]["ruta_excel"] == ""

    def test_empty_path(self):
        assert folder_scanner.scan_projects("") == []


class TestIsValidXlsx:
    def test_valid_file(self, tmp_path):
        f = tmp_path / "ok.xlsx"
        f.write_bytes(b"\0" * 5000)
        assert folder_scanner._is_valid_xlsx(str(f)) is True

    def test_too_small(self, tmp_path):
        f = tmp_path / "tiny.xlsx"
        f.write_bytes(b"\0" * 100)
        assert folder_scanner._is_valid_xlsx(str(f)) is False

    def test_nonexistent(self):
        assert folder_scanner._is_valid_xlsx("/no/existe.xlsx") is False


class TestFindBestExcel:
    def _make_xlsx(self, path, size=5000):
        path.write_bytes(b"\0" * size)

    def test_prefers_matching_number(self, tmp_path):
        self._make_xlsx(tmp_path / "122-20 Presupuesto.xlsx")
        self._make_xlsx(tmp_path / "otro.xlsx")

        result = folder_scanner._find_best_excel(str(tmp_path), "122-20")
        assert "122-20" in result

    def test_excludes_copies(self, tmp_path):
        self._make_xlsx(tmp_path / "122-20 Presupuesto - copia.xlsx")
        self._make_xlsx(tmp_path / "122-20 Presupuesto.xlsx")

        result = folder_scanner._find_best_excel(str(tmp_path), "122-20")
        assert "copia" not in result

    def test_excludes_temp_files(self, tmp_path):
        self._make_xlsx(tmp_path / "~$temp.xlsx")
        self._make_xlsx(tmp_path / "real.xlsx")

        result = folder_scanner._find_best_excel(str(tmp_path), None)
        assert "~$" not in result

    def test_no_xlsx(self, tmp_path):
        (tmp_path / "readme.txt").write_text("x")
        assert folder_scanner._find_best_excel(str(tmp_path), None) is None

    def test_fallback_no_number(self, tmp_path):
        self._make_xlsx(tmp_path / "presupuesto.xlsx")
        result = folder_scanner._find_best_excel(str(tmp_path), None)
        assert result is not None
