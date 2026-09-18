"""
Contrato de destino de guardado (S1-A / H01).

La ruta del diálogo es la ruta escrita; repetir la creación sobre un archivo
existente no lo sobrescribe sin consentimiento explícito sobre esa misma ruta.
"""

import hashlib
import importlib.util
import os

import pytest

from src.core import db_repository
from src.core.services.budget_service import BudgetCreationResult, BudgetService
from src.core.template_manager import TemplateManager


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_destino_contract.db"))
    return tmp_path


@pytest.fixture
def template_path():
    path = TemplateManager().get_template_path()
    if not os.path.exists(path):
        pytest.skip("Plantilla no disponible")
    return path


def _project_data():
    return {
        "numero": "99",
        "fecha": "13-02-26",
        "cliente": "TEST CLIENT",
        "calle": "Calle Test",
        "num_calle": "1",
        "codigo_postal": "03001",
        "tipo": "TEST OBRA",
        "localidad": "Alicante",
    }


def _sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def _mark_existing_file(path):
    with open(path, "ab") as handle:
        handle.write(b"marca-de-cambio")


def test_create_budget_escribe_en_la_ruta_elegida(db_env, template_path, tmp_path):
    save_path = str(tmp_path / "Chosen.xlsx")
    svc = BudgetService()

    result = svc.create_budget(
        _project_data(), "Original", save_path, template_path,
    )

    assert result.success is True
    assert result.excel_path == save_path
    assert os.path.exists(save_path)
    assert not os.path.exists(tmp_path / "Original" / "Original.xlsx")
    assert os.path.isdir(tmp_path / "FOTOS")


def test_create_budget_rechaza_guardar_en_una_carpeta_de_estado(db_env, template_path, tmp_path):
    state_dir = tmp_path / "PTE. PRESUPUESTAR"
    state_dir.mkdir()
    save_path = str(state_dir / "Chosen.xlsx")

    result = BudgetService().create_budget(
        _project_data(), "Original", save_path, template_path,
    )

    assert result.success is False
    assert result.error
    assert not os.path.exists(save_path)
    assert not os.path.isdir(state_dir / "FOTOS")


def test_create_budget_no_sobrescribe_un_excel_existente(db_env, template_path, tmp_path):
    save_path = str(tmp_path / "Chosen.xlsx")
    svc = BudgetService()

    first = svc.create_budget(_project_data(), "Original", save_path, template_path)
    assert first.success is True
    _mark_existing_file(save_path)
    before = _sha256(save_path)

    second = svc.create_budget(_project_data(), "Original", save_path, template_path)

    assert second.success is False
    assert second.error
    assert _sha256(save_path) == before


def test_create_budget_sobrescribe_solo_con_overwrite_explicito(db_env, template_path, tmp_path):
    save_path = str(tmp_path / "Chosen.xlsx")
    svc = BudgetService()

    assert svc.create_budget(_project_data(), "Original", save_path, template_path).success
    _mark_existing_file(save_path)
    before = _sha256(save_path)

    result = svc.create_budget(
        _project_data(), "Original", save_path, template_path, overwrite=True,
    )

    assert result.success is True
    assert _sha256(save_path) != before


def test_create_budget_falla_sin_permiso_de_escritura(db_env, template_path, monkeypatch, tmp_path):
    def _raise_permission_error(*args, **kwargs):
        raise PermissionError("sin permiso")

    monkeypatch.setattr("src.core.excel_template_filler.shutil.copy2", _raise_permission_error)
    save_path = str(tmp_path / "Chosen.xlsx")

    result = BudgetService().create_budget(
        _project_data(), "Original", save_path, template_path,
    )

    assert result.success is False
    assert result.error
    assert db_repository.get_presupuesto_por_ruta(save_path) is None


class _NoUiMessageBox:
    class StandardButton:
        Yes = 1
        No = 0

    @staticmethod
    def critical(*args, **kwargs):
        return 0

    @staticmethod
    def warning(*args, **kwargs):
        return 0

    @staticmethod
    def question(*args, **kwargs):
        return _NoUiMessageBox.StandardButton.No


class _RecordingBudgetService:
    def __init__(self):
        self.calls = []

    def get_template_path(self):
        return "plantilla.xlsx"

    def create_budget(self, project_data, project_name, save_path, template_path, **kwargs):
        self.calls.append({"save_path": save_path, "overwrite": kwargs.get("overwrite")})
        return BudgetCreationResult(success=True, excel_path=save_path)

    def finalize_budget(self, *args, **kwargs):
        return True

    def discard_budget(self, *args, **kwargs):
        return True


class _DummyDbService:
    @staticmethod
    def get_admin_para_comunidad(comunidad_data):
        return None


def _build_gui_frame(monkeypatch, tmp_path, chosen, question_answer=None):
    from src.gui import main_frame as main_mod
    from src.gui.main_frame import MainFrame

    monkeypatch.setattr(main_mod, "QMessageBox", _NoUiMessageBox)
    if question_answer is not None:
        monkeypatch.setattr(
            _NoUiMessageBox, "question",
            staticmethod(lambda *args, **kwargs: question_answer),
        )
    monkeypatch.setattr(
        "src.core.settings.Settings.get_default_path",
        lambda self, key: str(tmp_path),
    )
    monkeypatch.setattr(
        main_mod.QFileDialog, "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(chosen), "")),
    )

    frame = MainFrame.__new__(MainFrame)
    frame._budget_svc = _RecordingBudgetService()
    frame._db_svc = _DummyDbService()
    frame._obtain_project_data = lambda: (dict(_project_data()), "Original")
    frame._buscar_comunidad_para_presupuesto = lambda *args, **kwargs: None
    frame._offer_partidas_unified = lambda *args, **kwargs: None
    frame._open_dashboard = lambda *args, **kwargs: None
    frame._schedule_historical_feedback = lambda *args, **kwargs: None
    return frame


@pytest.mark.parametrize("chosen_exists", [False, True])
def test_create_budget_gui_pasa_la_ruta_elegida_y_el_consentimiento(
    monkeypatch, tmp_path, chosen_exists,
):
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 no disponible en entorno de tests")
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_gui_contract.db"))
    chosen = tmp_path / "Original" / "Chosen.xlsx"
    if chosen_exists:
        chosen.parent.mkdir(parents=True, exist_ok=True)
        chosen.write_bytes(b"previo")
    frame = _build_gui_frame(monkeypatch, tmp_path, chosen)

    frame._create_budget()

    assert len(frame._budget_svc.calls) == 1
    call = frame._budget_svc.calls[0]
    assert call["save_path"] == str(chosen)
    assert call["overwrite"] is chosen_exists


def test_create_budget_gui_rechaza_guardar_en_la_carpeta_configurada(monkeypatch, tmp_path):
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 no disponible en entorno de tests")
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_gui_raiz.db"))
    frame = _build_gui_frame(monkeypatch, tmp_path, tmp_path / "Chosen.xlsx")

    frame._create_budget()

    assert frame._budget_svc.calls == []
    assert not (tmp_path / "Original").exists()


def test_create_budget_gui_limpia_la_carpeta_propuesta_si_guarda_en_otro_sitio(
    monkeypatch, tmp_path,
):
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 no disponible en entorno de tests")
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_gui_limpieza.db"))
    elsewhere = tmp_path / "Elsewhere" / "Chosen.xlsx"
    frame = _build_gui_frame(monkeypatch, tmp_path, elsewhere)

    frame._create_budget()

    assert len(frame._budget_svc.calls) == 1
    assert frame._budget_svc.calls[0]["save_path"] == str(elsewhere)
    assert not (tmp_path / "Original").exists()


@pytest.mark.parametrize("question_answer, expected_calls", [
    (_NoUiMessageBox.StandardButton.No, 0),
    (_NoUiMessageBox.StandardButton.Yes, 1),
])
def test_create_budget_gui_reconfirma_al_normalizar_la_extension(
    monkeypatch, tmp_path, question_answer, expected_calls,
):
    if importlib.util.find_spec("PySide6") is None:
        pytest.skip("PySide6 no disponible en entorno de tests")
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos_gui_extension.db"))
    chosen = tmp_path / "Original" / "Chosen"
    normalized = chosen.with_suffix(".xlsx")
    normalized.parent.mkdir(parents=True, exist_ok=True)
    normalized.write_bytes(b"previo")
    frame = _build_gui_frame(monkeypatch, tmp_path, chosen, question_answer=question_answer)

    frame._create_budget()

    assert len(frame._budget_svc.calls) == expected_calls
    if expected_calls:
        call = frame._budget_svc.calls[0]
        assert call["save_path"] == str(normalized)
        assert call["overwrite"] is True
