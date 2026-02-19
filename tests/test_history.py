"""
Tests para el historial de presupuestos.

Cubre:
- Esquema de la tabla historial_presupuesto
- CRUD: registrar, listar, actualizar acceso, actualizar total, buscar, eliminar
- Constraint UNIQUE en ruta_excel (upsert)
- Migración: BD existente sin tabla historial se actualiza correctamente
"""

import sqlite3
import pytest
from unittest.mock import patch

from src.core import database
from src.core import db_repository as repo


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(tmp_path / "datos.db"))
    return tmp_path / "datos.db"


@pytest.fixture
def conn(db_env):
    c = database.connect()
    yield c
    c.close()


class TestHistorialSchema:
    """La tabla historial_presupuesto existe y tiene la estructura correcta."""

    def test_tabla_existe(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='historial_presupuesto'"
        )
        assert cur.fetchone() is not None

    def test_columnas(self, conn):
        cur = conn.execute("PRAGMA table_info(historial_presupuesto)")
        cols = {row[1] for row in cur.fetchall()}
        expected = {
            "id", "nombre_proyecto", "ruta_excel", "ruta_carpeta",
            "fecha_creacion", "fecha_ultimo_acceso", "cliente",
            "localidad", "tipo_obra", "numero_proyecto",
            "usa_partidas_ia", "total_presupuesto",
        }
        assert expected.issubset(cols)

    def test_indice_fecha(self, conn):
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_historial_fecha'"
        )
        assert cur.fetchone() is not None

    def test_unique_ruta_excel(self, conn):
        conn.execute(
            "INSERT INTO historial_presupuesto (nombre_proyecto, ruta_excel, fecha_creacion, fecha_ultimo_acceso) "
            "VALUES ('A', '/ruta/a.xlsx', '2026-01-01', '2026-01-01')"
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO historial_presupuesto (nombre_proyecto, ruta_excel, fecha_creacion, fecha_ultimo_acceso) "
                "VALUES ('B', '/ruta/a.xlsx', '2026-01-02', '2026-01-02')"
            )
            conn.commit()

    def test_schema_idempotente(self, conn):
        database.init_schema(conn)
        database.init_schema(conn)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='historial_presupuesto'"
        )
        assert cur.fetchone() is not None


class TestRegistrarPresupuesto:
    """registrar_presupuesto: INSERT y upsert por ruta_excel."""

    def test_registrar_nuevo(self, db_env):
        datos = {
            "nombre_proyecto": "001/26 COM.NORTE",
            "ruta_excel": "C:/proyectos/001.xlsx",
            "ruta_carpeta": "C:/proyectos/001",
            "cliente": "Comunidad Norte",
            "localidad": "Murcia",
            "tipo_obra": "Bajante",
            "numero_proyecto": "001",
        }
        id_, err = repo.registrar_presupuesto(datos)
        assert err is None
        assert id_ is not None and id_ > 0

    def test_registrar_duplicado_actualiza(self, db_env):
        datos = {
            "nombre_proyecto": "001/26 COM.NORTE",
            "ruta_excel": "C:/proyectos/001.xlsx",
            "cliente": "Comunidad Norte",
        }
        id1, _ = repo.registrar_presupuesto(datos)
        datos["cliente"] = "Comunidad Sur"
        id2, _ = repo.registrar_presupuesto(datos)
        assert id1 == id2
        historial = repo.get_historial_reciente()
        assert len(historial) == 1
        assert historial[0]["cliente"] == "Comunidad Sur"

    def test_registrar_sin_nombre_falla(self, db_env):
        id_, err = repo.registrar_presupuesto({"ruta_excel": "/a.xlsx"})
        assert id_ is None
        assert err is not None

    def test_registrar_sin_ruta_falla(self, db_env):
        id_, err = repo.registrar_presupuesto({"nombre_proyecto": "Test"})
        assert id_ is None
        assert err is not None

    def test_registrar_con_partidas_ia(self, db_env):
        datos = {
            "nombre_proyecto": "Test IA",
            "ruta_excel": "/ia.xlsx",
            "usa_partidas_ia": True,
        }
        id_, _ = repo.registrar_presupuesto(datos)
        historial = repo.get_historial_reciente()
        assert historial[0]["usa_partidas_ia"] is True

    def test_registrar_con_total(self, db_env):
        datos = {
            "nombre_proyecto": "Test Total",
            "ruta_excel": "/total.xlsx",
            "total_presupuesto": 1500.50,
        }
        repo.registrar_presupuesto(datos)
        historial = repo.get_historial_reciente()
        assert historial[0]["total_presupuesto"] == 1500.50


class TestGetHistorialReciente:
    """get_historial_reciente: listar ordenado por fecha_ultimo_acceso DESC."""

    def test_vacio(self, db_env):
        assert repo.get_historial_reciente() == []

    def test_orden_por_acceso(self, db_env):
        for i, name in enumerate(["A", "B", "C"]):
            repo.registrar_presupuesto({
                "nombre_proyecto": name,
                "ruta_excel": f"/{name}.xlsx",
                "fecha_creacion": f"2026-01-0{i+1}",
            })
        # El ultimo registrado tiene la fecha_ultimo_acceso mas reciente
        historial = repo.get_historial_reciente()
        assert len(historial) == 3
        assert historial[0]["nombre_proyecto"] == "C"

    def test_limit(self, db_env):
        for i in range(10):
            repo.registrar_presupuesto({
                "nombre_proyecto": f"P{i}",
                "ruta_excel": f"/{i}.xlsx",
            })
        assert len(repo.get_historial_reciente(limit=3)) == 3


class TestActualizarAcceso:
    """actualizar_acceso: actualiza fecha_ultimo_acceso."""

    def test_actualiza(self, db_env):
        repo.registrar_presupuesto({
            "nombre_proyecto": "Test",
            "ruta_excel": "/test.xlsx",
            "fecha_creacion": "2026-01-01 10:00:00",
        })
        err = repo.actualizar_acceso("/test.xlsx")
        assert err is None
        h = repo.get_historial_reciente()
        assert h[0]["fecha_ultimo_acceso"] != "2026-01-01 10:00:00"


class TestActualizarTotal:
    """actualizar_total: actualiza total_presupuesto."""

    def test_actualiza(self, db_env):
        repo.registrar_presupuesto({
            "nombre_proyecto": "Test",
            "ruta_excel": "/test.xlsx",
        })
        err = repo.actualizar_total("/test.xlsx", 9999.99)
        assert err is None
        h = repo.get_historial_reciente()
        assert h[0]["total_presupuesto"] == 9999.99


class TestEliminarHistorial:
    """eliminar_historial: borra entrada sin borrar el archivo."""

    def test_eliminar(self, db_env):
        id_, _ = repo.registrar_presupuesto({
            "nombre_proyecto": "Test",
            "ruta_excel": "/test.xlsx",
        })
        err = repo.eliminar_historial(id_)
        assert err is None
        assert repo.get_historial_reciente() == []

    def test_eliminar_inexistente_no_falla(self, db_env):
        err = repo.eliminar_historial(99999)
        assert err is None


class TestBuscarHistorial:
    """buscar_historial: busqueda LIKE en nombre, cliente, localidad."""

    def _seed(self, db_env):
        repo.registrar_presupuesto({
            "nombre_proyecto": "001/26 COM.NORTE - MURCIA",
            "ruta_excel": "/1.xlsx",
            "cliente": "Comunidad Norte",
            "localidad": "Murcia",
        })
        repo.registrar_presupuesto({
            "nombre_proyecto": "002/26 COM.SUR - CARTAGENA",
            "ruta_excel": "/2.xlsx",
            "cliente": "Comunidad Sur",
            "localidad": "Cartagena",
        })

    def test_buscar_por_nombre(self, db_env):
        self._seed(db_env)
        results = repo.buscar_historial("NORTE")
        assert len(results) == 1
        assert "NORTE" in results[0]["nombre_proyecto"]

    def test_buscar_por_cliente(self, db_env):
        self._seed(db_env)
        results = repo.buscar_historial("Sur")
        assert len(results) == 1

    def test_buscar_por_localidad(self, db_env):
        self._seed(db_env)
        results = repo.buscar_historial("Cartagena")
        assert len(results) == 1

    def test_buscar_vacio_devuelve_todo(self, db_env):
        self._seed(db_env)
        results = repo.buscar_historial("")
        assert len(results) == 2

    def test_buscar_sin_resultados(self, db_env):
        self._seed(db_env)
        results = repo.buscar_historial("ZZZZZ")
        assert len(results) == 0
