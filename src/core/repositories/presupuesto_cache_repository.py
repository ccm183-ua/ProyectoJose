"""
CRUD de cache de presupuestos (tabla presupuesto).
"""

from datetime import datetime
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from src.core import database
from src.core.repositories._common import _mensaje_integridad


def _row_to_presupuesto_cache(r) -> Dict:
    """Convierte una fila de la tabla presupuesto a dict."""
    return {
        "id": r[0],
        "numero_proyecto": r[1] or "",
        "nombre_proyecto": r[2] or "",
        "ruta_excel": r[3] or "",
        "ruta_carpeta": r[4] or "",
        "estado": r[5] or "",
        "cliente": r[6] or "",
        "localidad": r[7] or "",
        "tipo_obra": r[8] or "",
        "fecha": r[9] or "",
        "total": r[10],
        "subtotal": r[11],
        "iva": r[12],
        "obra_descripcion": r[13] or "",
        "cif_admin": r[14] or "",
        "email_admin": r[15] or "",
        "telefono_admin": r[16] or "",
        "codigo_postal": r[17] or "",
        "direccion": r[18] or "",
        "localizacion": r[19] or "",
        "comunidad_id": r[20],
        "administracion_id": r[21],
        "comunidad_nombre": r[22] or "",
        "administracion_nombre": r[23] or "",
        "fecha_modificacion_excel": r[24] or "",
        "fecha_cache": r[25] or "",
        "datos_completos": bool(r[26]),
        "total_partidas": r[27],
        "num_partidas": r[28] or 0,
        "fuente_datos": r[29] or "scan",
        "es_finalizado": bool(r[30]),
        "fecha_finalizacion": r[31] or "",
        "calidad_datos": int(r[32] or 0),
        "motivo_incompleto": r[33] or "",
        "metodo_resolucion_admin": r[34] or "",
        "metodo_resolucion_comunidad": r[35] or "",
    }


_PRESUPUESTO_COLS = (
    "id, numero_proyecto, nombre_proyecto, ruta_excel, ruta_carpeta, "
    "estado, cliente, localidad, tipo_obra, fecha, total, subtotal, iva, "
    "obra_descripcion, cif_admin, email_admin, telefono_admin, codigo_postal, "
    "direccion, localizacion, comunidad_id, administracion_id, comunidad_nombre, "
    "administracion_nombre, fecha_modificacion_excel, fecha_cache, datos_completos, "
    "total_partidas, num_partidas, fuente_datos, es_finalizado, fecha_finalizacion, "
    "calidad_datos, motivo_incompleto, metodo_resolucion_admin, metodo_resolucion_comunidad"
)


def _calcular_calidad_datos(datos: Dict[str, Any], partidas: Optional[List[Dict[str, Any]]] = None) -> int:
    """Calcula un score simple (0-100) según campos relevantes presentes."""
    checks = [
        bool((datos.get("nombre_proyecto") or "").strip()),
        bool((datos.get("numero_proyecto") or "").strip()),
        bool((datos.get("cliente") or "").strip()),
        bool((datos.get("localidad") or "").strip()),
        bool((datos.get("codigo_postal") or "").strip()),
        bool((datos.get("direccion") or "").strip() or (datos.get("localizacion") or "").strip()),
        datos.get("total") is not None,
        datos.get("subtotal") is not None,
        bool(datos.get("comunidad_id") or (datos.get("comunidad_nombre") or "").strip()),
        bool(datos.get("administracion_id") or (datos.get("administracion_nombre") or "").strip()),
    ]
    if partidas is not None:
        checks.append(len(partidas) > 0)
    return int(round((sum(1 for c in checks if c) * 100) / len(checks)))


def get_presupuesto_por_ruta(ruta_excel: str) -> Optional[Dict]:
    """Busca un presupuesto en la cache por su ruta_excel.

    Args:
        ruta_excel: Ruta normalizada al fichero .xlsx.

    Returns:
        Dict con los datos cacheados, o None si no existe.
    """
    ruta = (ruta_excel or "").strip()
    if not ruta:
        return None
    with database.get_connection() as conn:
        cur = conn.execute(
            f"SELECT {_PRESUPUESTO_COLS} FROM presupuesto WHERE ruta_excel = ?",
            (ruta,),
        )
        r = cur.fetchone()
        if not r:
            return None
        return _row_to_presupuesto_cache(r)


def get_presupuesto_detalle_por_ruta(ruta_excel: str) -> Optional[Dict]:
    """Obtiene presupuesto + partidas por ruta_excel."""
    base = get_presupuesto_por_ruta(ruta_excel)
    if not base:
        return None
    base["partidas"] = get_partidas_de_presupuesto(presupuesto_id=base["id"])
    return base


def get_presupuestos_por_estado(estado: str) -> List[Dict]:
    """Lista todos los presupuestos cacheados de un estado dado.

    Args:
        estado: Nombre de la carpeta de estado (ej: 'PRESUPUESTADO').

    Returns:
        Lista de dicts con los datos cacheados.
    """
    with database.get_connection() as conn:
        cur = conn.execute(
            "SELECT "
            f"{_PRESUPUESTO_COLS} "
            "FROM presupuesto WHERE estado = ? "
            "ORDER BY es_finalizado DESC, numero_proyecto",
            (estado,),
        )
        return [_row_to_presupuesto_cache(r) for r in cur.fetchall()]


def upsert_presupuesto(datos: Dict) -> Tuple[Optional[int], Optional[str]]:
    """Inserta o actualiza un presupuesto en la cache (ON CONFLICT ruta_excel).

    Args:
        datos: Dict con los campos del presupuesto. Claves esperadas:
            numero_proyecto, nombre_proyecto (obligatorio), ruta_excel (obligatorio),
            ruta_carpeta, estado, cliente, localidad, tipo_obra, fecha, total,
            subtotal, iva, obra_descripcion, cif_admin, email_admin,
            telefono_admin, codigo_postal, comunidad_id, administracion_id,
            fecha_modificacion_excel (obligatorio), datos_completos.

    Returns:
        (id, None) si ok, (None, mensaje_error) si falla.
    """
    nombre = (datos.get("nombre_proyecto") or "").strip()
    ruta = (datos.get("ruta_excel") or "").strip()
    fecha_mod = (datos.get("fecha_modificacion_excel") or "").strip()
    if not nombre or not ruta or not fecha_mod:
        return (None, "nombre_proyecto, ruta_excel y fecha_modificacion_excel son obligatorios.")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    calidad = _calcular_calidad_datos(datos)
    with database.get_connection() as conn:
        try:
            conn.execute(
                """INSERT INTO presupuesto
                   (numero_proyecto, nombre_proyecto, ruta_excel, ruta_carpeta,
                    estado, cliente, localidad, tipo_obra, fecha, total,
                    subtotal, iva, obra_descripcion, cif_admin, email_admin,
                    telefono_admin, codigo_postal, direccion, localizacion,
                    comunidad_id, administracion_id, comunidad_nombre,
                    administracion_nombre, fecha_modificacion_excel, fecha_cache,
                    datos_completos, total_partidas, num_partidas, fuente_datos,
                    es_finalizado, fecha_finalizacion, calidad_datos,
                    motivo_incompleto, metodo_resolucion_admin, metodo_resolucion_comunidad)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(ruta_excel) DO UPDATE SET
                       numero_proyecto  = excluded.numero_proyecto,
                       nombre_proyecto  = excluded.nombre_proyecto,
                       ruta_carpeta     = excluded.ruta_carpeta,
                       estado           = excluded.estado,
                       cliente          = excluded.cliente,
                       localidad        = excluded.localidad,
                       tipo_obra        = excluded.tipo_obra,
                       fecha            = excluded.fecha,
                       total            = excluded.total,
                       subtotal         = excluded.subtotal,
                       iva              = excluded.iva,
                       obra_descripcion = excluded.obra_descripcion,
                       cif_admin        = excluded.cif_admin,
                       email_admin      = excluded.email_admin,
                       telefono_admin   = excluded.telefono_admin,
                       codigo_postal    = excluded.codigo_postal,
                       direccion        = excluded.direccion,
                       localizacion     = excluded.localizacion,
                       comunidad_id     = excluded.comunidad_id,
                       administracion_id = excluded.administracion_id,
                       comunidad_nombre = excluded.comunidad_nombre,
                       administracion_nombre = excluded.administracion_nombre,
                       fecha_modificacion_excel = excluded.fecha_modificacion_excel,
                       fecha_cache      = excluded.fecha_cache,
                       datos_completos  = excluded.datos_completos,
                       total_partidas   = excluded.total_partidas,
                       num_partidas     = excluded.num_partidas,
                       fuente_datos     = excluded.fuente_datos,
                       calidad_datos    = excluded.calidad_datos,
                       motivo_incompleto = excluded.motivo_incompleto,
                       metodo_resolucion_admin = excluded.metodo_resolucion_admin,
                       metodo_resolucion_comunidad = excluded.metodo_resolucion_comunidad
                   WHERE presupuesto.es_finalizado = 0
                """,
                (
                    (datos.get("numero_proyecto") or "").strip() or None,
                    nombre,
                    ruta,
                    (datos.get("ruta_carpeta") or "").strip() or None,
                    (datos.get("estado") or "").strip() or None,
                    (datos.get("cliente") or "").strip() or None,
                    (datos.get("localidad") or "").strip() or None,
                    (datos.get("tipo_obra") or "").strip() or None,
                    (datos.get("fecha") or "").strip() or None,
                    datos.get("total"),
                    datos.get("subtotal"),
                    datos.get("iva"),
                    (datos.get("obra_descripcion") or "").strip() or None,
                    (datos.get("cif_admin") or "").strip() or None,
                    (datos.get("email_admin") or "").strip() or None,
                    (datos.get("telefono_admin") or "").strip() or None,
                    (datos.get("codigo_postal") or "").strip() or None,
                    (datos.get("direccion") or "").strip() or None,
                    (datos.get("localizacion") or "").strip() or None,
                    datos.get("comunidad_id"),
                    datos.get("administracion_id"),
                    (datos.get("comunidad_nombre") or "").strip() or None,
                    (datos.get("administracion_nombre") or "").strip() or None,
                    fecha_mod,
                    now,
                    1 if datos.get("datos_completos") else 0,
                    datos.get("total_partidas"),
                    int(datos.get("num_partidas") or 0),
                    (datos.get("fuente_datos") or "scan").strip(),
                    1 if datos.get("es_finalizado") else 0,
                    (datos.get("fecha_finalizacion") or "").strip() or None,
                    int(datos.get("calidad_datos") or calidad),
                    (datos.get("motivo_incompleto") or "").strip() or None,
                    (datos.get("metodo_resolucion_admin") or "").strip() or None,
                    (datos.get("metodo_resolucion_comunidad") or "").strip() or None,
                ),
            )
            conn.commit()
            cur = conn.execute(
                "SELECT id FROM presupuesto WHERE ruta_excel = ?", (ruta,)
            )
            row = cur.fetchone()
            return (row[0] if row else None, None)
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return (None, _mensaje_integridad(e))
        except sqlite3.OperationalError as e:
            conn.rollback()
            return (None, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}.")


def upsert_presupuesto_finalizado(
    datos: Dict[str, Any], partidas: List[Dict[str, Any]],
) -> Tuple[Optional[int], Optional[str]]:
    """Guarda presupuesto finalizado y sus partidas en una única transacción."""
    nombre = (datos.get("nombre_proyecto") or "").strip()
    ruta = (datos.get("ruta_excel") or "").strip()
    fecha_mod = (datos.get("fecha_modificacion_excel") or "").strip()
    if not nombre or not ruta:
        return (None, "nombre_proyecto y ruta_excel son obligatorios.")
    if not fecha_mod:
        fecha_mod = datetime.now().isoformat()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_partidas = datos.get("total_partidas")
    if total_partidas is None:
        total_partidas = round(
            sum(float(p.get("importe") or 0.0) for p in partidas),
            2,
        )

    datos_merge = {**datos}
    datos_merge["total_partidas"] = total_partidas
    datos_merge["num_partidas"] = len(partidas)
    calidad = _calcular_calidad_datos(datos_merge, partidas=partidas)

    with database.get_connection() as conn:
        try:
            conn.execute(
                """INSERT INTO presupuesto
                   (numero_proyecto, nombre_proyecto, ruta_excel, ruta_carpeta,
                    estado, cliente, localidad, tipo_obra, fecha, total,
                    subtotal, iva, obra_descripcion, cif_admin, email_admin,
                    telefono_admin, codigo_postal, direccion, localizacion,
                    comunidad_id, administracion_id, comunidad_nombre,
                    administracion_nombre, fecha_modificacion_excel, fecha_cache,
                    datos_completos, total_partidas, num_partidas, fuente_datos,
                    es_finalizado, fecha_finalizacion, calidad_datos,
                    motivo_incompleto, metodo_resolucion_admin, metodo_resolucion_comunidad)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(ruta_excel) DO UPDATE SET
                       numero_proyecto  = excluded.numero_proyecto,
                       nombre_proyecto  = excluded.nombre_proyecto,
                       ruta_carpeta     = excluded.ruta_carpeta,
                       estado           = excluded.estado,
                       cliente          = excluded.cliente,
                       localidad        = excluded.localidad,
                       tipo_obra        = excluded.tipo_obra,
                       fecha            = excluded.fecha,
                       total            = excluded.total,
                       subtotal         = excluded.subtotal,
                       iva              = excluded.iva,
                       obra_descripcion = excluded.obra_descripcion,
                       cif_admin        = excluded.cif_admin,
                       email_admin      = excluded.email_admin,
                       telefono_admin   = excluded.telefono_admin,
                       codigo_postal    = excluded.codigo_postal,
                       direccion        = excluded.direccion,
                       localizacion     = excluded.localizacion,
                       comunidad_id     = excluded.comunidad_id,
                       administracion_id = excluded.administracion_id,
                       comunidad_nombre = excluded.comunidad_nombre,
                       administracion_nombre = excluded.administracion_nombre,
                       fecha_modificacion_excel = excluded.fecha_modificacion_excel,
                       fecha_cache      = excluded.fecha_cache,
                       datos_completos  = excluded.datos_completos,
                       total_partidas   = excluded.total_partidas,
                       num_partidas     = excluded.num_partidas,
                       fuente_datos     = excluded.fuente_datos,
                       es_finalizado    = excluded.es_finalizado,
                       fecha_finalizacion = excluded.fecha_finalizacion,
                       calidad_datos    = excluded.calidad_datos,
                       motivo_incompleto = excluded.motivo_incompleto,
                       metodo_resolucion_admin = excluded.metodo_resolucion_admin,
                       metodo_resolucion_comunidad = excluded.metodo_resolucion_comunidad
                """,
                (
                    (datos.get("numero_proyecto") or "").strip() or None,
                    nombre,
                    ruta,
                    (datos.get("ruta_carpeta") or "").strip() or None,
                    (datos.get("estado") or "").strip() or None,
                    (datos.get("cliente") or "").strip() or None,
                    (datos.get("localidad") or "").strip() or None,
                    (datos.get("tipo_obra") or "").strip() or None,
                    (datos.get("fecha") or "").strip() or None,
                    datos.get("total"),
                    datos.get("subtotal"),
                    datos.get("iva"),
                    (datos.get("obra_descripcion") or "").strip() or None,
                    (datos.get("cif_admin") or "").strip() or None,
                    (datos.get("email_admin") or "").strip() or None,
                    (datos.get("telefono_admin") or "").strip() or None,
                    (datos.get("codigo_postal") or "").strip() or None,
                    (datos.get("direccion") or "").strip() or None,
                    (datos.get("localizacion") or "").strip() or None,
                    datos.get("comunidad_id"),
                    datos.get("administracion_id"),
                    (datos.get("comunidad_nombre") or "").strip() or None,
                    (datos.get("administracion_nombre") or "").strip() or None,
                    fecha_mod,
                    now,
                    1 if datos.get("datos_completos", True) else 0,
                    total_partidas,
                    len(partidas),
                    "finalizado",
                    1,
                    now,
                    calidad,
                    (datos.get("motivo_incompleto") or "").strip() or None,
                    (datos.get("metodo_resolucion_admin") or "").strip() or None,
                    (datos.get("metodo_resolucion_comunidad") or "").strip() or None,
                ),
            )

            cur = conn.execute("SELECT id FROM presupuesto WHERE ruta_excel = ?", (ruta,))
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return (None, "No se pudo recuperar el presupuesto finalizado.")

            presupuesto_id = row[0]
            conn.execute(
                "DELETE FROM presupuesto_partida WHERE presupuesto_id = ?",
                (presupuesto_id,),
            )

            if partidas:
                conn.executemany(
                    """INSERT INTO presupuesto_partida
                       (presupuesto_id, orden, numero, concepto, unidad, cantidad, precio, importe)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    [
                        (
                            presupuesto_id,
                            idx + 1,
                            (p.get("numero") or "").strip() or None,
                            (p.get("concepto") or "").strip() or "Partida",
                            (p.get("unidad") or "").strip() or None,
                            p.get("cantidad"),
                            p.get("precio"),
                            p.get("importe"),
                        )
                        for idx, p in enumerate(partidas)
                    ],
                )

            conn.commit()
            return (presupuesto_id, None)
        except sqlite3.IntegrityError as e:
            conn.rollback()
            return (None, _mensaje_integridad(e))
        except sqlite3.OperationalError as e:
            conn.rollback()
            return (None, f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}.")


def get_partidas_de_presupuesto(
    presupuesto_id: Optional[int] = None,
    ruta_excel: str = "",
) -> List[Dict]:
    """Devuelve partidas por presupuesto_id o ruta_excel."""
    if presupuesto_id is None and not (ruta_excel or "").strip():
        return []
    with database.get_connection() as conn:
        if presupuesto_id is None:
            cur = conn.execute(
                "SELECT id FROM presupuesto WHERE ruta_excel = ?",
                ((ruta_excel or "").strip(),),
            )
            row = cur.fetchone()
            if not row:
                return []
            presupuesto_id = row[0]

        cur = conn.execute(
            """SELECT id, presupuesto_id, orden, numero, concepto, unidad, cantidad, precio, importe
               FROM presupuesto_partida
               WHERE presupuesto_id = ?
               ORDER BY orden, id""",
            (presupuesto_id,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "presupuesto_id": r[1],
                "orden": r[2],
                "numero": r[3] or "",
                "concepto": r[4] or "",
                "unidad": r[5] or "",
                "cantidad": r[6],
                "precio": r[7],
                "importe": r[8],
            }
            for r in rows
        ]


def get_presupuestos_para_tabla(
    estado: str = "",
    solo_finalizados: bool = False,
    calidad_min: int = 0,
) -> List[Dict]:
    """Lista presupuestos con filtros para la tabla principal."""
    where = []
    params: List[Any] = []
    if estado.strip():
        where.append("estado = ?")
        params.append(estado.strip())
    if solo_finalizados:
        where.append("es_finalizado = 1")
    if calidad_min > 0:
        where.append("calidad_datos >= ?")
        params.append(int(calidad_min))

    where_sql = ""
    if where:
        where_sql = "WHERE " + " AND ".join(where)

    with database.get_connection() as conn:
        cur = conn.execute(
            "SELECT "
            f"{_PRESUPUESTO_COLS} "
            "FROM presupuesto "
            f"{where_sql} "
            "ORDER BY es_finalizado DESC, calidad_datos DESC, numero_proyecto",
            tuple(params),
        )
        return [_row_to_presupuesto_cache(r) for r in cur.fetchall()]


def actualizar_estado_presupuesto(ruta_excel: str, estado: str) -> Optional[str]:
    """Actualiza solo el campo estado de un presupuesto cacheado.

    Útil cuando se mueve un proyecto de carpeta sin que cambie el Excel.

    Returns:
        None si ok, mensaje de error si falla.
    """
    with database.get_connection() as conn:
        try:
            conn.execute(
                "UPDATE presupuesto SET estado = ? WHERE ruta_excel = ?",
                (estado, ruta_excel),
            )
            conn.commit()
            return None
        except sqlite3.OperationalError as e:
            conn.rollback()
            return f"Error de base de datos: {e.args[0] if e.args else 'desconocido'}."


def limpiar_presupuestos_huerfanos(rutas_vigentes: List[str]) -> int:
    """Elimina de la cache presupuestos cuya ruta_excel ya no está en disco.

    Args:
        rutas_vigentes: Lista de rutas de Excel actualmente presentes en las carpetas.

    Returns:
        Número de registros eliminados.
    """
    with database.get_connection() as conn:
        cur = conn.execute("SELECT id, ruta_excel FROM presupuesto")
        all_cached = cur.fetchall()
        vigentes_set = set(rutas_vigentes)
        ids_to_delete = [
            r[0] for r in all_cached
            if r[1] and r[1] not in vigentes_set
        ]
        if ids_to_delete:
            placeholders = ",".join("?" for _ in ids_to_delete)
            conn.execute(
                f"DELETE FROM presupuesto WHERE id IN ({placeholders})",
                ids_to_delete,
            )
            conn.commit()
        return len(ids_to_delete)


def get_all_presupuestos_cache() -> List[Dict]:
    """Devuelve todos los presupuestos de la cache.

    Returns:
        Lista de dicts con todos los campos.
    """
    with database.get_connection() as conn:
        cur = conn.execute(
            "SELECT "
            f"{_PRESUPUESTO_COLS} "
            "FROM presupuesto ORDER BY estado, es_finalizado DESC, numero_proyecto"
        )
        return [_row_to_presupuesto_cache(r) for r in cur.fetchall()]
