"""
Tests robustos para el módulo de base de datos.

Objetivo: cubrir excepciones y posibles errores para que la app sea segura
para usuarios no técnicos. Todos los tests usan una BD temporal (no datos reales).

Cubre:
- Ruta y conexión (env, directorio, lectura/escritura)
- Esquema (tablas, índices, idempotencia)
- Restricciones NOT NULL (contacto, comunidad)
- Restricciones UNIQUE (telefono, nombre, email)
- Claves foráneas y ON DELETE RESTRICT/CASCADE
- open_db_folder (sin abrir el sistema de archivos real)
"""

import os
import sqlite3
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core import database


# ---------------------------------------------------------------------------
# Fixtures: BD temporal para no tocar datos reales
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    """Ruta a un fichero .db en un directorio temporal."""
    return tmp_path / "datos.db"


@pytest.fixture
def db_env(db_path, monkeypatch):
    """Fija CUBIAPP_DB_PATH al .db temporal para todos los tests que lo usen."""
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))
    return db_path


@pytest.fixture
def conn(db_env):
    """Conexión a la BD temporal ya inicializada (tablas creadas). El llamador debe cerrarla."""
    c = database.connect()
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Ruta y directorio
# ---------------------------------------------------------------------------

class TestGetDbPath:
    """Ruta del fichero de base de datos."""

    def test_respetar_env_si_esta_definido_y_es_absoluto(self, tmp_path, monkeypatch):
        ruta = tmp_path / "custom" / "mi.db"
        monkeypatch.setenv("CUBIAPP_DB_PATH", str(ruta))
        assert database.get_db_path() == ruta

    def test_ignorar_env_si_no_es_absoluto(self, monkeypatch):
        monkeypatch.setenv("CUBIAPP_DB_PATH", "relativo/datos.db")
        path = database.get_db_path()
        assert path.is_absolute()
        assert path.name == "datos.db"
        # Cae a la ruta por defecto (raíz del proyecto)
        assert path.parent == Path(__file__).resolve().parent.parent

    def test_ruta_por_defecto_si_no_hay_env(self, monkeypatch):
        monkeypatch.delenv("CUBIAPP_DB_PATH", raising=False)
        path = database.get_db_path()
        assert path.is_absolute()
        assert path.name == "datos.db"
        # La ruta por defecto es la raíz del proyecto (donde está src/)
        assert path.parent == Path(__file__).resolve().parent.parent


class TestEnsureDbDirectory:
    """Creación del directorio del .db."""

    def test_crea_directorio_si_no_existe(self, tmp_path):
        ruta_fichero = tmp_path / "sub" / "dir" / "datos.db"
        assert not ruta_fichero.parent.exists()
        database.ensure_db_directory(ruta_fichero)
        assert ruta_fichero.parent.exists()
        assert ruta_fichero.parent.is_dir()

    def test_no_borra_ni_sobrescribe_fichero_existente(self, tmp_path):
        ruta_fichero = tmp_path / "datos.db"
        ruta_fichero.write_text("existente")
        database.ensure_db_directory(ruta_fichero)
        assert ruta_fichero.read_text() == "existente"


# ---------------------------------------------------------------------------
# Conexión y esquema
# ---------------------------------------------------------------------------

class TestConnect:
    """Conexión a la base de datos."""

    def test_crea_fichero_y_tablas_si_no_existe(self, db_env):
        assert not db_env.exists()
        conn = database.connect()
        try:
            assert db_env.exists()
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tablas = [r[0] for r in cur.fetchall()]
            assert "administracion" in tablas
            assert "comunidad" in tablas
            assert "contacto" in tablas
            assert "administracion_contacto" in tablas
            assert "comunidad_contacto" in tablas
        finally:
            conn.close()

    def test_foreign_keys_activados(self, conn):
        cur = conn.execute("PRAGMA foreign_keys")
        assert cur.fetchone()[0] == 1

    def test_no_borra_datos_existentes_al_reconectar(self, db_env):
        conn1 = database.connect()
        conn1.execute(
            "INSERT INTO administracion (nombre, email, telefono) VALUES (?, ?, ?)",
            ("Admin Test", "admin@test.com", "600000000"),
        )
        conn1.commit()
        conn1.close()
        conn2 = database.connect()
        try:
            cur = conn2.execute("SELECT nombre, email FROM administracion")
            row = cur.fetchone()
            assert row[0] == "Admin Test" and row[1] == "admin@test.com"
        finally:
            conn2.close()

    def test_solo_lectura_abre_fichero_existente(self, db_env):
        database.connect().close()
        conn = database.connect(read_only=True)
        try:
            cur = conn.execute("SELECT 1")
            assert cur.fetchone()[0] == 1
        finally:
            conn.close()

    def test_solo_lectura_falla_si_fichero_no_existe(self, db_env):
        assert not db_env.exists()
        with pytest.raises(sqlite3.OperationalError):
            database.connect(read_only=True)


class TestInitSchema:
    """Inicialización del esquema."""

    def test_es_idempotente(self, conn):
        database.init_schema(conn)
        database.init_schema(conn)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        assert len(cur.fetchall()) >= 5


# ---------------------------------------------------------------------------
# Restricciones NOT NULL
# ---------------------------------------------------------------------------

class TestNotNullContacto:
    """Contacto: nombre y telefono obligatorios."""

    def test_insert_sin_nombre_falla(self, conn):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO contacto (nombre, telefono) VALUES (?, ?)",
                (None, "600111111"),
            )
            conn.commit()

    def test_insert_sin_telefono_falla(self, conn):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO contacto (nombre, telefono) VALUES (?, ?)",
                ("Juan", None),
            )
            conn.commit()

    def test_insert_valido_ok(self, conn):
        conn.execute(
            "INSERT INTO contacto (nombre, telefono) VALUES (?, ?)",
            ("Juan", "600111111"),
        )
        conn.commit()
        cur = conn.execute("SELECT nombre, telefono FROM contacto WHERE id=1")
        assert cur.fetchone() == ("Juan", "600111111")


class TestNotNullComunidad:
    """Comunidad: nombre y administracion_id obligatorios."""

    def test_insert_sin_nombre_falla(self, conn):
        conn.execute(
            "INSERT INTO administracion (id, nombre) VALUES (1, 'A')"
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO comunidad (nombre, administracion_id) VALUES (?, ?)",
                (None, 1),
            )
            conn.commit()

    def test_insert_sin_administracion_id_falla(self, conn):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO comunidad (nombre, administracion_id) VALUES (?, ?)",
                ("Comunidad Test", None),
            )
            conn.commit()

    def test_insert_con_administracion_id_invalido_falla(self, conn):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO comunidad (nombre, administracion_id) VALUES (?, ?)",
                ("Comunidad Test", 99999),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Restricciones UNIQUE
# ---------------------------------------------------------------------------

class TestUniqueContacto:
    """Contacto: telefono UNIQUE."""

    def test_dos_contactos_mismo_telefono_falla(self, conn):
        conn.execute(
            "INSERT INTO contacto (nombre, telefono) VALUES (?, ?)",
            ("Juan", "600222222"),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO contacto (nombre, telefono) VALUES (?, ?)",
                ("Pedro", "600222222"),
            )
            conn.commit()


class TestUniqueComunidad:
    """Comunidad: nombre UNIQUE."""

    def test_dos_comunidades_mismo_nombre_falla(self, conn):
        conn.execute("INSERT INTO administracion (id, nombre) VALUES (1, 'A')")
        conn.commit()
        conn.execute(
            "INSERT INTO comunidad (nombre, administracion_id) VALUES (?, ?)",
            ("Edificio Norte", 1),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO comunidad (nombre, administracion_id) VALUES (?, ?)",
                ("Edificio Norte", 1),
            )
            conn.commit()


class TestUniqueAdministracion:
    """Administración: email UNIQUE (varios NULL permitidos)."""

    def test_dos_administraciones_mismo_email_falla(self, conn):
        conn.execute(
            "INSERT INTO administracion (nombre, email) VALUES (?, ?)",
            ("A", "admin@test.com"),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO administracion (nombre, email) VALUES (?, ?)",
                ("B", "admin@test.com"),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Claves foráneas y tablas enlace
# ---------------------------------------------------------------------------

class TestForeignKeyEnlace:
    """administracion_contacto y comunidad_contacto exigen IDs válidos."""

    def test_administracion_contacto_administracion_invalida_falla(self, conn):
        conn.execute(
            "INSERT INTO contacto (nombre, telefono) VALUES (?, ?)",
            ("Juan", "600333333"),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO administracion_contacto (administracion_id, contacto_id) VALUES (?, ?)",
                (99999, 1),
            )
            conn.commit()

    def test_administracion_contacto_contacto_invalido_falla(self, conn):
        conn.execute("INSERT INTO administracion (id, nombre) VALUES (1, 'A')")
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO administracion_contacto (administracion_id, contacto_id) VALUES (?, ?)",
                (1, 99999),
            )
            conn.commit()

    def test_comunidad_contacto_comunidad_invalida_falla(self, conn):
        conn.execute(
            "INSERT INTO contacto (nombre, telefono) VALUES (?, ?)",
            ("Juan", "600444444"),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO comunidad_contacto (comunidad_id, contacto_id) VALUES (?, ?)",
                (99999, 1),
            )
            conn.commit()

    def test_enlaces_validos_ok(self, conn):
        conn.execute("INSERT INTO administracion (id, nombre) VALUES (1, 'A')")
        conn.execute(
            "INSERT INTO contacto (nombre, telefono) VALUES (?, ?)",
            ("Juan", "600555555"),
        )
        conn.execute(
            "INSERT INTO comunidad (nombre, administracion_id) VALUES (?, ?)",
            ("Edificio Sur", 1),
        )
        conn.commit()
        conn.execute(
            "INSERT INTO administracion_contacto (administracion_id, contacto_id) VALUES (1, 1)"
        )
        conn.execute(
            "INSERT INTO comunidad_contacto (comunidad_id, contacto_id) VALUES (1, 1)"
        )
        conn.commit()
        cur = conn.execute("SELECT COUNT(*) FROM administracion_contacto")
        assert cur.fetchone()[0] == 1
        cur = conn.execute("SELECT COUNT(*) FROM comunidad_contacto")
        assert cur.fetchone()[0] == 1


# ---------------------------------------------------------------------------
# ON DELETE RESTRICT / CASCADE
# ---------------------------------------------------------------------------

class TestOnDeleteRestrict:
    """No se puede borrar una administración si alguna comunidad la referencia."""

    def test_borrar_administracion_con_comunidad_falla(self, conn):
        conn.execute("INSERT INTO administracion (id, nombre) VALUES (1, 'A')")
        conn.execute(
            "INSERT INTO comunidad (nombre, administracion_id) VALUES (?, ?)",
            ("Edificio Este", 1),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM administracion WHERE id = 1")
            conn.commit()

    def test_borrar_administracion_sin_comunidad_ok(self, conn):
        conn.execute("INSERT INTO administracion (id, nombre) VALUES (1, 'A')")
        conn.commit()
        conn.execute("DELETE FROM administracion WHERE id = 1")
        conn.commit()
        cur = conn.execute("SELECT COUNT(*) FROM administracion")
        assert cur.fetchone()[0] == 0


class TestOnDeleteCascade:
    """Al borrar contacto o comunidad se borran los enlaces en las tablas N:M."""

    def test_borrar_contacto_borra_enlaces(self, conn):
        conn.execute("INSERT INTO administracion (id, nombre) VALUES (1, 'A')")
        conn.execute(
            "INSERT INTO contacto (nombre, telefono) VALUES (?, ?)",
            ("Juan", "600666666"),
        )
        conn.execute(
            "INSERT INTO administracion_contacto (administracion_id, contacto_id) VALUES (1, 1)"
        )
        conn.commit()
        conn.execute("DELETE FROM contacto WHERE id = 1")
        conn.commit()
        cur = conn.execute("SELECT COUNT(*) FROM administracion_contacto")
        assert cur.fetchone()[0] == 0

    def test_borrar_comunidad_borra_enlaces_comunidad_contacto(self, conn):
        conn.execute("INSERT INTO administracion (id, nombre) VALUES (1, 'A')")
        conn.execute(
            "INSERT INTO comunidad (nombre, administracion_id) VALUES (?, ?)",
            ("Edificio Oeste", 1),
        )
        conn.execute(
            "INSERT INTO contacto (nombre, telefono) VALUES (?, ?)",
            ("Maria", "600777777"),
        )
        conn.execute(
            "INSERT INTO comunidad_contacto (comunidad_id, contacto_id) VALUES (1, 1)"
        )
        conn.commit()
        conn.execute("DELETE FROM comunidad WHERE id = 1")
        conn.commit()
        cur = conn.execute("SELECT COUNT(*) FROM comunidad_contacto")
        assert cur.fetchone()[0] == 0


# ---------------------------------------------------------------------------
# open_db_folder (sin abrir el sistema de archivos real)
# ---------------------------------------------------------------------------

class TestOpenDbFolder:
    """Abrir carpeta de la BD: crea .db si no existe y no debe fallar."""

    def test_crea_db_si_no_existe_y_llama_al_sistema(self, db_env):
        assert not db_env.exists()
        with patch("src.core.database.subprocess.run", MagicMock(return_value=MagicMock())) as mock_run:
            result = database.open_db_folder()
            assert result is True
            assert db_env.exists()
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert str(db_env.parent) in args or db_env.parent.name in str(args)

    def test_devuelve_false_si_subprocess_falla(self, db_env):
        database.connect().close()
        with patch("src.core.database.subprocess.run", side_effect=OSError("fallo")):
            result = database.open_db_folder()
            assert result is False


# ---------------------------------------------------------------------------
# get_db_path_as_string
# ---------------------------------------------------------------------------

class TestGetDbPathAsString:
    def test_devuelve_misma_ruta_que_get_db_path(self, db_env):
        assert database.get_db_path_as_string() == str(database.get_db_path())
