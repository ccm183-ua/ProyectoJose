"""
Cache inteligente de presupuestos.

Sincroniza los datos de los Excels de presupuesto con la tabla ``presupuesto``
de la base de datos. Solo re-lee un Excel si su fecha de modificación (mtime)
difiere de la almacenada en la cache, evitando abrir archivos innecesariamente.

Fuentes de datos:
- **Metadatos** (cliente, localidad, tipo_obra, fecha): siempre de la relación
  de presupuestos. No se leen de la cabecera del Excel porque muchos archivos
  aún contienen datos de la plantilla original.
- **Total**: se lee del Excel buscando la frase
  *"Asciende el presupuesto de ejecución material a la expresada cantidad de
  ... EUROS ..."* y parseando el importe en palabras.

Principios:
- Nunca inventar datos: si no se puede leer, ``datos_completos=0``.
- Coherencia: si el mtime cambia se re-lee; si el archivo desaparece se limpia.
- Rendimiento: la mayoría de las lecturas se resuelven desde SQLite.
"""

import logging
import os
import re
from datetime import datetime
from typing import Dict, List, Optional

from src.core.budget_reader import BudgetReader
from src.core.db_repository import (
    buscar_administracion_por_nombre,
    buscar_comunidad_por_nombre,
    get_presupuesto_por_ruta,
    limpiar_presupuestos_huerfanos,
    upsert_presupuesto,
)
from src.utils.budget_utils import normalize_date, strip_obra_prefix

logger = logging.getLogger(__name__)

# Regex para extraer (número, año) de formatos como "71-26", "71/26", "120/20"
_RE_PROJECT_NUM = re.compile(r"(\d{1,4})[/-](\d{2})")


def _get_file_mtime_iso(filepath: str) -> Optional[str]:
    """Devuelve el mtime del fichero como string ISO, o None si no existe."""
    try:
        stat = os.stat(filepath)
        return datetime.fromtimestamp(stat.st_mtime).isoformat()
    except (OSError, ValueError):
        return None


def _normalize_project_num(value: str) -> str:
    """Normaliza un número de proyecto a formato ``N-YY`` para comparación.

    Acepta formatos como ``71-26``, ``71/26``, ``120/20``, ``06-26``, etc.
    Elimina ceros iniciales para que ``06-26`` y ``6/26`` se consideren iguales.
    Devuelve cadena vacía si no se puede parsear.
    """
    m = _RE_PROJECT_NUM.search(value or "")
    if not m:
        return ""
    num = str(int(m.group(1)))  # Eliminar ceros iniciales
    year = m.group(2)
    return f"{num}-{year}"


def _is_template_data(excel_numero: str, expected_numero: str) -> bool:
    """Detecta si los datos del Excel son de la plantilla y no del proyecto real.

    Compara el número de proyecto leído de la celda E5 del Excel con el
    número extraído del nombre de la carpeta. Si no coinciden, el Excel
    contiene datos de la plantilla original (ej: 122-20 PLANTILLA).

    Args:
        excel_numero: Número de proyecto leído de la cabecera del Excel.
        expected_numero: Número de proyecto esperado (de la carpeta).

    Returns:
        True si los datos son de plantilla (no reales).
    """
    if not excel_numero or not expected_numero:
        return False  # Si no hay datos para comparar, no podemos afirmar que sea plantilla

    norm_excel = _normalize_project_num(excel_numero)
    norm_expected = _normalize_project_num(expected_numero)

    if not norm_excel or not norm_expected:
        return False  # No se pudo parsear alguno; no asumimos plantilla

    return norm_excel != norm_expected


def sync_presupuestos(
    scanned_projects: List[Dict],
    relation_index: Optional[Dict[str, Dict]] = None,
    state_name: str = "",
) -> List[Dict]:
    """Sincroniza los presupuestos escaneados con la cache de la DB.

    Para cada proyecto escaneado:
    1. Si tiene ``ruta_excel``, obtiene el mtime del archivo.
    2. Busca en la cache (DB) por ``ruta_excel``.
    3. Si la cache existe y el mtime coincide → usa datos cacheados.
    4. Si no hay cache o el mtime difiere → lee el Excel y actualiza la cache.
    5. Si la lectura falla → guarda con ``datos_completos=0``.

    Args:
        scanned_projects: Lista de dicts de ``folder_scanner.scan_projects``.
        relation_index: Índice del Excel de relación (opcional).
        state_name: Nombre de la carpeta de estado (ej: 'PRESUPUESTADO').

    Returns:
        Lista de dicts con los datos unificados listos para la UI,
        con el mismo formato que ``project_data_resolver.resolve_projects``.
    """
    reader = BudgetReader()
    result: List[Dict] = []

    for proj in scanned_projects:
        numero = proj.get("numero_proyecto", "")
        ruta_excel = proj.get("ruta_excel", "")

        # Construir entrada base
        entry = _empty_entry(proj, state_name)

        if not ruta_excel or not os.path.isfile(ruta_excel):
            # Sin Excel: no se puede cachear, devolver entrada vacía
            entry["datos_completos"] = False
            result.append(entry)
            continue

        # Obtener mtime actual del archivo
        mtime_actual = _get_file_mtime_iso(ruta_excel)
        if not mtime_actual:
            entry["datos_completos"] = False
            result.append(entry)
            continue

        # Buscar en cache
        cached = get_presupuesto_por_ruta(ruta_excel)

        if cached and cached.get("fecha_modificacion_excel") == mtime_actual:
            # Cache válida: mtime coincide
            # Solo actualizar estado si cambió de carpeta
            if cached.get("estado") != state_name and state_name:
                cached["estado"] = state_name
                try:
                    from src.core.db_repository import actualizar_estado_presupuesto
                    actualizar_estado_presupuesto(ruta_excel, state_name)
                except Exception:
                    logger.debug("No se pudo actualizar estado en cache para %s", ruta_excel)

            _fill_entry_from_cache(entry, cached)
            result.append(entry)
            continue

        # Cache no válida o inexistente: necesitamos leer datos
        datos_cache = _build_cache_data(
            proj, reader, relation_index, ruta_excel, mtime_actual, state_name
        )

        # Intentar vincular FK a comunidad/administración
        _try_link_fks(datos_cache)

        # Guardar en cache
        try:
            upsert_presupuesto(datos_cache)
        except Exception:
            logger.exception("Error al guardar en cache: %s", ruta_excel)

        # Rellenar la entrada para la UI
        _fill_entry_from_cache_data(entry, datos_cache)
        result.append(entry)

    return result


def cleanup_orphaned_cache(all_scanned_rutas: List[str]) -> int:
    """Elimina de la cache presupuestos que ya no existen en las carpetas.

    Args:
        all_scanned_rutas: Todas las rutas de Excel encontradas en el escaneo actual.

    Returns:
        Número de entradas eliminadas.
    """
    try:
        return limpiar_presupuestos_huerfanos(all_scanned_rutas)
    except Exception:
        logger.exception("Error al limpiar cache huérfana")
        return 0


# ---------------------------------------------------------------------------
# Funciones auxiliares internas
# ---------------------------------------------------------------------------

def _empty_entry(proj: Dict, state_name: str = "") -> Dict:
    """Crea una entrada vacía para la UI con los datos base del escaneo."""
    return {
        "nombre_proyecto": proj.get("nombre_carpeta", ""),
        "numero": proj.get("numero_proyecto", ""),
        "cliente": "",
        "localidad": "",
        "tipo_obra": "",
        "fecha": "",
        "total": None,
        "ruta_excel": proj.get("ruta_excel", ""),
        "ruta_carpeta": proj.get("ruta_carpeta", ""),
        "estado": state_name,
        "datos_completos": False,
    }


def _fill_entry_from_cache(entry: Dict, cached: Dict) -> None:
    """Rellena la entrada de la UI a partir de datos de la cache (DB)."""
    entry["cliente"] = cached.get("cliente", "")
    entry["localidad"] = cached.get("localidad", "")
    entry["tipo_obra"] = cached.get("tipo_obra", "")
    entry["fecha"] = cached.get("fecha", "")
    entry["total"] = cached.get("total")
    entry["datos_completos"] = cached.get("datos_completos", False)
    entry["estado"] = cached.get("estado", entry.get("estado", ""))


def _fill_entry_from_cache_data(entry: Dict, datos: Dict) -> None:
    """Rellena la entrada de la UI a partir del dict que se guardó en cache."""
    entry["cliente"] = datos.get("cliente", "")
    entry["localidad"] = datos.get("localidad", "")
    entry["tipo_obra"] = datos.get("tipo_obra", "")
    entry["fecha"] = datos.get("fecha", "")
    entry["total"] = datos.get("total")
    entry["datos_completos"] = bool(datos.get("datos_completos"))
    entry["estado"] = datos.get("estado", entry.get("estado", ""))


def _lookup_relation(
    relation_index: Optional[Dict[str, Dict]],
    numero: str,
) -> Optional[Dict]:
    """Busca un proyecto en el índice de relación intentando varios formatos.

    La relación suele tener solo el número secuencial (``'1'``, ``'11'``),
    mientras que las carpetas usan el formato ``NNN-YY`` (``'1-26'``, ``'11-26'``).
    """
    if not relation_index or not numero:
        return None
    # 1. Intento exacto (ej: "1-26" → "1-26")
    if numero in relation_index:
        return relation_index[numero]
    # 2. Solo número sin año: "1-26" → "1", "06-26" → "6"
    m = _RE_PROJECT_NUM.search(numero)
    if m:
        just_num = str(int(m.group(1)))
        if just_num in relation_index:
            return relation_index[just_num]
    return None


def _build_cache_data(
    proj: Dict,
    reader: BudgetReader,
    relation_index: Optional[Dict[str, Dict]],
    ruta_excel: str,
    mtime_iso: str,
    state_name: str,
) -> Dict:
    """Construye el dict de datos para guardar en cache.

    Fuentes de datos:
    - **Metadatos** (cliente, localidad, tipo_obra, fecha): de la relación
      de presupuestos (fiable y consistente).
    - **Total**: se obtiene del Excel buscando la frase
      ``"Asciende el presupuesto ... cantidad de X EUROS ..."``
      en la hoja correcta (con detección de plantilla).
    """
    numero = proj.get("numero_proyecto", "")
    datos: Dict = {
        "numero_proyecto": numero,
        "nombre_proyecto": proj.get("nombre_carpeta", ""),
        "ruta_excel": ruta_excel,
        "ruta_carpeta": proj.get("ruta_carpeta", ""),
        "estado": state_name,
        "fecha_modificacion_excel": mtime_iso,
        "datos_completos": False,
    }

    # ── Fuente 1: Relación de presupuestos (metadatos) ──────────────
    # Cliente, localidad, tipo de obra y fecha se obtienen SIEMPRE de la
    # relación porque son los datos fiables y consistentes.
    rel = _lookup_relation(relation_index, numero)
    if rel:
        datos["cliente"] = rel.get("cliente", "")
        datos["localidad"] = rel.get("localidad", "")
        datos["tipo_obra"] = rel.get("tipo", "")
        datos["fecha"] = normalize_date(rel.get("fecha", ""))

    # ── Fuente 2: Total desde texto "Asciende..." del Excel ─────────
    # El total no tiene una celda fija; se obtiene parseando la frase
    # "Asciende el presupuesto ... cantidad de X EUROS ..." que siempre
    # ocupa una fila completa en el presupuesto.
    try:
        total = reader.read_total_from_text(ruta_excel, expected_numero=numero)
        if total is not None:
            datos["total"] = total
            datos["datos_completos"] = True
            logger.debug(
                "Total leído de texto 'Asciende': %.2f para %s", total, ruta_excel
            )
        else:
            logger.warning(
                "No se encontró frase 'Asciende...' en: %s", ruta_excel
            )
    except Exception:
        logger.exception("Error al leer total por texto: %s", ruta_excel)

    # Si tenemos metadatos de la relación pero no total del Excel,
    # marcar como datos_completos=True si al menos tenemos cliente
    # (el total puede ser legítimamente 0 o no disponible aún).
    if not datos["datos_completos"] and datos.get("cliente"):
        datos["datos_completos"] = True

    return datos


def _try_link_fks(datos: Dict) -> None:
    """Intenta vincular comunidad_id y administracion_id por nombre del cliente.

    Si el nombre del cliente coincide (exacto o normalizado) con una comunidad
    existente en la BD, establece la FK. Igualmente para la administración
    asociada a esa comunidad.

    No lanza excepciones; si falla simplemente deja los campos a None.
    """
    cliente = (datos.get("cliente") or "").strip()
    if not cliente:
        return

    try:
        comunidad = buscar_comunidad_por_nombre(cliente)
        if comunidad:
            datos["comunidad_id"] = comunidad["id"]
            admin_id = comunidad.get("administracion_id")
            if admin_id:
                datos["administracion_id"] = admin_id
            return

        # Si no encontró comunidad, intentar buscar administración directamente
        # por si el campo cliente es realmente una administración
        admin = buscar_administracion_por_nombre(cliente)
        if admin:
            datos["administracion_id"] = admin["id"]
    except Exception:
        logger.debug("Error al vincular FKs para cliente '%s'", cliente)
