"""H11/H12: la búsqueda y el refresco conservan la geometría y el contexto de trabajo.

H11: el aviso de "sin resultados" funde todas las columnas de la fila 0
(``setSpan``). Al volver a haber resultados hay que deshacer esa unión.

H12a: el menú contextual no debe colapsar una selección múltiple ya existente.

H12b: el refresco reconstruye las pestañas; debe conservar la pestaña activa,
el texto de búsqueda por pestaña y el orden aplicado donde siga siendo válido.
"""

import os

import pytest

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMenu, QTableWidgetSelectionRange

    from src.core import folder_scanner
    from src.core.settings import Settings
    from src.gui import budget_dashboard
    from src.gui.budget_dashboard import BudgetDashboardFrame

    _HAS_PYSIDE6 = True
except ImportError:
    _HAS_PYSIDE6 = False

pytestmark = pytest.mark.skipif(not _HAS_PYSIDE6, reason="PySide6 no disponible")


def _project(numero, nombre, **extra):
    data = {
        "numero": numero,
        "nombre_proyecto": nombre,
        "cliente": extra.get("cliente", ""),
        "administracion_nombre": "",
        "direccion": "",
        "localidad": "",
        "tipo_obra": "",
        "fecha": "",
        "subtotal": 0.0,
        "iva": 0.0,
        "total": 0.0,
        "fuente_datos": "scan",
        "es_finalizado": False,
        "calidad_datos": 100,
        "datos_completos": True,
        "ruta_excel": extra.get("ruta_excel", ""),
        "ruta_carpeta": extra.get("ruta_carpeta", ""),
    }
    data.update(extra)
    return data


def _explorer_entry(nombre, **extra):
    data = {
        "nombre": nombre,
        "extension": os.path.splitext(nombre)[1].lstrip("."),
        "tamano": 10,
        "fecha_modificacion": "2026-01-01",
        "es_carpeta": False,
        "ruta": extra.get("ruta", ""),
    }
    data.update(extra)
    return data


@pytest.fixture
def dashboard(qapp, monkeypatch):
    monkeypatch.setattr(Settings, "get_default_path", lambda self, key: "")
    frame = BudgetDashboardFrame()
    yield frame
    frame.close()


def _install_tabs(monkeypatch, frame, root_path, rows_by_state, explorer=False):
    monkeypatch.setattr(budget_dashboard, "cleanup_orphaned_cache", lambda *a, **k: None)
    monkeypatch.setattr(
        budget_dashboard, "resolve_projects", lambda scanned, index, state: scanned
    )
    if explorer:
        monkeypatch.setattr(
            folder_scanner,
            "scan_explorer",
            lambda state_dir: list(rows_by_state.get(os.path.basename(state_dir), [])),
        )
    else:
        monkeypatch.setattr(
            folder_scanner,
            "scan_projects",
            lambda state_dir: list(rows_by_state.get(os.path.basename(state_dir), [])),
        )
    frame._explorer_mode = explorer
    frame._root_path = root_path
    frame._rebuild_tabs(list(rows_by_state), root_path)


def _assert_geometry_restored(frame, state_name, expected_text):
    table = frame._tab_tables[state_name]
    assert table.columnSpan(0, 0) == 1
    assert table.item(0, 0).text() == expected_text


def test_h11_budget_geometry_restored_after_empty_search(qapp, monkeypatch, dashboard):
    state = "PTE. PRESUPUESTAR"
    _install_tabs(monkeypatch, dashboard, "", {state: [_project("1-26", "1-26 Obra")]})
    search = dashboard._tab_searches[state]
    table = dashboard._tab_tables[state]

    search.setText("zzz")
    assert table.rowCount() == 1
    assert table.columnSpan(0, 0) == table.columnCount()

    search.setText("")
    _assert_geometry_restored(dashboard, state, "1-26")

    # Segundo ciclo vacío→resultados: la unión no debe reaparecer.
    search.setText("zzz")
    assert table.columnSpan(0, 0) == table.columnCount()
    search.setText("")
    _assert_geometry_restored(dashboard, state, "1-26")


def test_h11_explorer_geometry_restored_after_empty_search(qapp, monkeypatch, dashboard):
    state = "PTE. PRESUPUESTAR"
    _install_tabs(
        monkeypatch,
        dashboard,
        "",
        {state: [_explorer_entry("documento.txt")]},
        explorer=True,
    )
    search = dashboard._tab_searches[state]
    table = dashboard._tab_tables[state]

    search.setText("zzz")
    assert table.rowCount() == 1
    assert table.columnSpan(0, 0) == table.columnCount()

    search.setText("")
    assert table.columnSpan(0, 0) == 1
    assert "documento.txt" in table.item(0, 0).text()


def test_h11_geometry_restored_with_sorting_active(qapp, monkeypatch, dashboard):
    state = "PTE. PRESUPUESTAR"
    rows = [_project("1-26", "1-26 Obra"), _project("2-26", "2-26 Otra")]
    _install_tabs(monkeypatch, dashboard, "", {state: rows})
    search = dashboard._tab_searches[state]
    table = dashboard._tab_tables[state]

    table.sortItems(1, Qt.SortOrder.AscendingOrder)
    search.setText("zzz")
    assert table.columnSpan(0, 0) == table.columnCount()

    search.setText("")
    assert table.columnSpan(0, 0) == 1
    assert table.rowCount() == 2


def test_h12_context_menu_preserves_two_recipients(qapp, monkeypatch, dashboard, tmp_path):
    state = "PTE. PRESUPUESTAR"
    # _find_real_folder_name busca la carpeta física en disco.
    (tmp_path / "PRESUPUESTADO").mkdir()
    rows = [
        _project("1-26", "1-26 Obra", ruta_carpeta=str(tmp_path / "PRESUPUESTADO" / "1-26")),
        _project("2-26", "2-26 Otra", ruta_carpeta=str(tmp_path / "PRESUPUESTADO" / "2-26")),
    ]
    _install_tabs(monkeypatch, dashboard, str(tmp_path), {state: rows})
    table = dashboard._tab_tables[state]

    dashboard.show()
    qapp.processEvents()

    table.setRangeSelected(
        QTableWidgetSelectionRange(0, 0, 1, table.columnCount() - 1), True
    )

    captured = {}

    def _fake_move(projects, from_state, to_state):
        captured["n"] = len(projects)
        captured["to"] = to_state

    monkeypatch.setattr(dashboard, "_move_project", _fake_move)

    def _fake_exec(menu, *args, **kwargs):
        for action in menu.actions():
            submenu = action.menu()
            if submenu is None:
                continue
            for sub_action in submenu.actions():
                if sub_action.text() == "PRESUPUESTADO":
                    sub_action.trigger()
                    return None
        return None

    class _FakeMenu(QMenu):
        def exec(self, *args, **kwargs):
            return _fake_exec(self)

    monkeypatch.setattr(budget_dashboard, "QMenu", _FakeMenu)

    dashboard._on_context_menu(table.visualItemRect(table.item(0, 1)).center(), state)

    assert captured == {"n": 2, "to": "PRESUPUESTADO"}


def test_h12_refresh_preserves_tab_search_and_sort(qapp, monkeypatch, dashboard, tmp_path):
    first = "PTE. PRESUPUESTAR"
    second = "PRESUPUESTADO"
    rows_by_state = {
        first: [_project("1-26", "1-26 Obra")],
        second: [
            _project("2-26", "2-26 Filtro especial"),
            _project("3-26", "3-26 Otra"),
        ],
    }
    _install_tabs(monkeypatch, dashboard, "", rows_by_state)

    second_table = dashboard._tab_tables[second]
    dashboard._tab_searches[second].setText("Filtro")
    second_table.sortItems(1, Qt.SortOrder.AscendingOrder)
    dashboard._notebook.setCurrentIndex(dashboard._state_names.index(second))

    monkeypatch.setattr(
        budget_dashboard, "run_in_background", lambda work, callback: callback(True, work())
    )
    monkeypatch.setattr(budget_dashboard, "build_relation_index", lambda: {})
    monkeypatch.setattr(folder_scanner, "scan_root", lambda root_path: [first, second])
    monkeypatch.setattr(Settings, "get_default_path", lambda self, key: str(tmp_path))

    dashboard._load_data()

    assert dashboard._current_state() == second
    restored_search = dashboard._tab_searches[second]
    assert restored_search.text() == "Filtro"
    restored_table = dashboard._tab_tables[second]
    assert restored_table.rowCount() == 1
    header = restored_table.horizontalHeader()
    assert header.sortIndicatorSection() == 1
    assert header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
