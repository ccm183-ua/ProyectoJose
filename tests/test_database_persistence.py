from datetime import datetime
from pathlib import Path

from src.core import database
from src.core.database_backup import create_database_backup, list_database_backups, prune_old_backups
from src.core.database_persistence import (
    copy_database_as_active,
    find_database_candidates,
    get_database_diagnostics,
    inspect_database_file,
)
from src.core.repositories import insert_historical_partida, upsert_budget_enrichment, upsert_historical_budget
from src.core.settings import Settings


def _isolated_config(monkeypatch, tmp_path):
    monkeypatch.setenv("CUBIAPP_CONFIG_DIR", str(tmp_path / "config"))


def _create_budget(tmp_path, name="historico.xlsx"):
    budget_id, err = upsert_historical_budget(
        {
            "ruta_excel": str(tmp_path / name),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": name,
            "numero_proyecto": "001-26",
            "cliente": "Comunidad Test",
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "analisis_ok": True,
            "analysis_status": "VALID",
            "learning_status": "INCLUDED",
            "usable_for_learning": True,
            "warning_count": 0,
            "total": 100.0,
            "num_partidas": 1,
            "selected_sheet": "Presupuesto",
            "compatible_score": 90,
        }
    )
    assert err is None
    assert budget_id is not None
    return int(budget_id)


def test_get_db_path_respects_absolute_env_path(tmp_path, monkeypatch):
    _isolated_config(monkeypatch, tmp_path)
    target = tmp_path / "env" / "datos.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(target))

    assert database.get_db_path() == target


def test_db_path_priority_settings_env_stable_legacy(tmp_path, monkeypatch):
    _isolated_config(monkeypatch, tmp_path)
    settings_path = tmp_path / "settings.db"
    env_path = tmp_path / "env.db"
    stable_path = tmp_path / "stable.db"
    legacy_path = tmp_path / "legacy.db"
    monkeypatch.setattr(database, "get_stable_default_db_path", lambda: stable_path)
    monkeypatch.setattr(database, "get_legacy_db_path", lambda: legacy_path)

    monkeypatch.setenv("CUBIAPP_DB_PATH", str(env_path))
    Settings().set_database_path(str(settings_path))
    assert database.get_db_path() == settings_path

    Settings().set_database_path("")
    assert database.get_db_path() == env_path

    monkeypatch.delenv("CUBIAPP_DB_PATH", raising=False)
    assert database.get_db_path() == stable_path

    stable_path.unlink(missing_ok=True)
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(legacy_path))
    with database.get_connection() as _conn:
        pass
    _create_budget(tmp_path, "legacy_priority.xlsx")
    monkeypatch.delenv("CUBIAPP_DB_PATH", raising=False)
    assert database.get_db_path() == legacy_path


def test_stable_with_normal_app_data_is_not_replaced_by_legacy(tmp_path, monkeypatch):
    _isolated_config(monkeypatch, tmp_path)
    stable_path = tmp_path / "stable_normal.db"
    legacy_path = tmp_path / "legacy_with_history.db"
    monkeypatch.setattr(database, "get_stable_default_db_path", lambda: stable_path)
    monkeypatch.setattr(database, "get_legacy_db_path", lambda: legacy_path)

    monkeypatch.setenv("CUBIAPP_DB_PATH", str(stable_path))
    with database.get_connection() as conn:
        conn.execute(
            """INSERT INTO administracion (nombre, email, telefono, direccion)
               VALUES (?, ?, ?, ?)""",
            ("Admin", "admin@example.com", "600000000", "Calle"),
        )
        conn.commit()

    monkeypatch.setenv("CUBIAPP_DB_PATH", str(legacy_path))
    with database.get_connection() as _conn:
        pass
    _create_budget(tmp_path, "legacy_history.xlsx")

    monkeypatch.delenv("CUBIAPP_DB_PATH", raising=False)
    assert database.get_db_path() == stable_path


def test_missing_stable_with_legacy_historical_uses_legacy_fallback(tmp_path, monkeypatch):
    _isolated_config(monkeypatch, tmp_path)
    stable_path = tmp_path / "missing_stable.db"
    legacy_path = tmp_path / "legacy_history.db"
    monkeypatch.setattr(database, "get_stable_default_db_path", lambda: stable_path)
    monkeypatch.setattr(database, "get_legacy_db_path", lambda: legacy_path)

    monkeypatch.setenv("CUBIAPP_DB_PATH", str(legacy_path))
    with database.get_connection() as _conn:
        pass
    _create_budget(tmp_path, "legacy_fallback.xlsx")

    monkeypatch.delenv("CUBIAPP_DB_PATH", raising=False)
    assert database.get_db_path() == legacy_path


def test_database_identity_created_once(tmp_path, monkeypatch):
    _isolated_config(monkeypatch, tmp_path)
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "identity.db"))

    with database.get_connection() as conn:
        first = conn.execute("SELECT database_uuid FROM app_database_identity WHERE id=1").fetchone()[0]
    with database.get_connection() as conn:
        second = conn.execute("SELECT database_uuid FROM app_database_identity WHERE id=1").fetchone()[0]
        count = conn.execute("SELECT COUNT(*) FROM app_database_identity").fetchone()[0]

    assert first
    assert second == first
    assert count == 1


def test_database_diagnostics_returns_counts(tmp_path, monkeypatch):
    _isolated_config(monkeypatch, tmp_path)
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "diagnostics.db"))
    with database.get_connection() as _conn:
        pass
    budget_id = _create_budget(tmp_path)
    partida_id, err = insert_historical_partida(
        budget_id,
        {
            "orden": 1,
            "concepto_original": "Reparacion de fachada",
            "concepto_normalizado": "reparacion fachada",
            "unidad": "ud",
            "cantidad": 1,
            "precio_unitario": 100,
            "total_linea": 100,
        },
    )
    assert err is None
    assert partida_id is not None
    assert upsert_budget_enrichment(
        budget_id,
        "TECHNICAL_DESCRIPTION",
        "MANUAL",
        "MANUAL",
        "Descripcion manual.",
    ) is None

    info = get_database_diagnostics()

    assert info["counts"]["historical_budget"] == 1
    assert info["counts"]["historical_partida"] == 1
    assert info["counts"]["historical_budget_enrichment"] == 1
    assert info["included_budgets"] == 1
    assert info["descriptions_manual"] == 1
    assert info["database_uuid"]


def test_find_database_candidates_detects_historical_data(tmp_path, monkeypatch):
    _isolated_config(monkeypatch, tmp_path)
    active = tmp_path / "active.db"
    stable = tmp_path / "stable.db"
    legacy = tmp_path / "legacy.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(active))
    monkeypatch.setattr(database, "get_stable_default_db_path", lambda: stable)
    monkeypatch.setattr(database, "get_legacy_db_path", lambda: legacy)
    with database.get_connection() as _conn:
        pass
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(legacy))
    with database.get_connection() as _conn:
        pass
    _create_budget(tmp_path, "legacy.xlsx")
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(active))

    candidates = find_database_candidates()
    legacy_info = next(c for c in candidates if c["path"] == str(legacy))

    assert legacy_info["counts"]["historical_budget"] == 1
    assert legacy_info["database_uuid"]


def test_backup_creates_file_and_prune_keeps_last_n(tmp_path, monkeypatch):
    _isolated_config(monkeypatch, tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("CUBIAPP_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "backup_source.db"))
    with database.get_connection() as _conn:
        pass

    paths = [create_database_backup(f"test_{idx}") for idx in range(4)]
    prune_old_backups(keep_last=2)
    remaining = [p for p in list_database_backups() if "before_migration" not in p.name]

    assert all(path.exists() for path in paths[-2:])
    assert len(remaining) == 2


def test_copy_database_as_active_does_not_delete_source(tmp_path, monkeypatch):
    _isolated_config(monkeypatch, tmp_path)
    source = tmp_path / "source.db"
    active = tmp_path / "active_copy.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(source))
    with database.get_connection() as _conn:
        pass
    _create_budget(tmp_path, "source.xlsx")
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(active))
    with database.get_connection() as _conn:
        pass

    result = copy_database_as_active(str(source))

    assert result["ok"] is True
    assert source.exists()
    assert active.exists()
    assert inspect_database_file(active)["counts"]["historical_budget"] == 1


def test_copy_database_as_active_noops_when_source_is_active(tmp_path, monkeypatch):
    _isolated_config(monkeypatch, tmp_path)
    active = tmp_path / "already_active.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(active))
    with database.get_connection() as _conn:
        pass

    result = copy_database_as_active(str(active))

    assert result["ok"] is False
    assert result["error"] == "La base seleccionada ya es la activa."


def test_empty_database_is_detected_as_empty(tmp_path, monkeypatch):
    _isolated_config(monkeypatch, tmp_path)
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
    with database.get_connection() as _conn:
        pass

    info = inspect_database_file(db_path)

    assert info["is_empty"] is True
    assert info["counts"]["historical_budget"] == 0


def _backup_env(tmp_path, monkeypatch):
    _isolated_config(monkeypatch, tmp_path)
    monkeypatch.setenv("CUBIAPP_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "retencion.db"))
    with database.get_connection() as _conn:
        pass


def test_orden_de_backups_por_fecha_de_creacion_no_por_mtime(tmp_path, monkeypatch):
    """copy2 conserva el mtime de la BD original: ordenar por mtime no
    distinguía los backups. Se ordena por la marca de tiempo del nombre."""
    _backup_env(tmp_path, monkeypatch)
    import os

    first = create_database_backup("primero")
    second = create_database_backup("segundo")
    os.utime(second, (1, 1))  # mtime antiguo en el más reciente
    assert list_database_backups()[:2] == [second, first]


def test_crear_backup_purga_y_conserva_los_protegidos(tmp_path, monkeypatch):
    _backup_env(tmp_path, monkeypatch)
    from src.core import database_backup

    monkeypatch.setattr(database_backup, "BACKUP_KEEP_LAST", 3)
    migracion = create_database_backup("before_migration_v3_to_v4")
    borrado = create_database_backup("before_clear_historical")
    normales = [create_database_backup(f"before_patterns_rebuild_{i}") for i in range(6)]

    restantes = list_database_backups()

    assert migracion.exists() and borrado.exists()
    assert [p for p in restantes if p in normales] == list(reversed(normales[-3:]))
    no_protegidos = [p for p in restantes if "before_migration" not in p.name
                     and "before_clear_historical" not in p.name]
    assert len(no_protegidos) == 3
