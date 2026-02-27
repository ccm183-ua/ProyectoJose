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
    actualizar_estado_presupuesto,
    buscar_administracion_por_nombre,
    buscar_comunidad_por_nombre,
    get_presupuesto_por_ruta,
    limpiar_presupuestos_huerfanos,
    upsert_presupuesto,
)
from src.utils.budget_utils import (
    RE_PROJECT_NUM,
    normalize_date,
    normalize_project_num,
    strip_obra_prefix,
)

logger = logging.getLogger(__name__)


_NUMERIC_TEXT_RE = re.compile(r"^\s*\d+(?:[.,]\d+)?\s*$")


def _is_suspicious_text_value(value: str) -> bool:
    """Detecta valores no textuales usados por error en campos de texto.

    Ejemplos típicos del fallo: ``0.6``, ``0.9`` en cliente/dirección.
    """
    text = (value or "").strip()
    if not text:
        return False
    return bool(_NUMERIC_TEXT_RE.match(text))


def _apply_no_matching_sheet_policy(datos: Dict, numero: str) -> None:
    """Aplica política estricta cuando ninguna hoja coincide con el número esperado.

    Regla funcional: no guardar datos de contenido del presupuesto
    (cabecera/totales/relación), solo identidad del proyecto y aviso.
    """
    datos["cliente"] = ""
    datos["administracion_nombre"] = ""
    datos["direccion"] = ""
    datos["localizacion"] = ""
    datos["localidad"] = ""
    datos["tipo_obra"] = ""
    datos["fecha"] = ""
    datos["total"] = None
    datos["subtotal"] = None
    datos["iva"] = None
    datos["cif_admin"] = ""
    datos["email_admin"] = ""
    datos["telefono_admin"] = ""
    datos["codigo_postal"] = ""
    datos["comunidad_id"] = None
    datos["administracion_id"] = None
    datos["comunidad_nombre"] = ""
    datos["datos_completos"] = False
    datos["motivo_incompleto"] = (
        "Aviso: ninguna hoja del Excel coincide con el número "
        f"de proyecto esperado ({numero}). Puede ser una plantilla provisional."
    )


def _get_file_mtime_iso(filepath: str) -> Optional[str]:
    """Devuelve el mtime del fichero como string ISO, o None si no existe."""
    try:
        stat = os.stat(filepath)
        return datetime.fromtimestamp(stat.st_mtime).isoformat()
    except (OSError, ValueError):
        return None


def _infer_localidad_from_direccion(direccion: str) -> str:
    """Extrae una localidad aproximada desde una dirección textual."""
    text = (direccion or "").strip()
    if not text:
        return ""
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if not parts:
        return ""
    last = parts[-1]
    # Limpiar CP al inicio: "03004 Alicante" -> "Alicante"
    tokens = last.split()
    if tokens and tokens[0].isdigit() and len(tokens[0]) in (4, 5):
        last = " ".join(tokens[1:]).strip()
    return last


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

    norm_excel = normalize_project_num(excel_numero)
    norm_expected = normalize_project_num(expected_numero)

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

        # Si el presupuesto ya está finalizado en DB, el escaneo no debe
        # sobreescribir su contenido aunque el Excel haya cambiado.
        if cached and cached.get("es_finalizado"):
            if cached.get("estado") != state_name and state_name:
                cached["estado"] = state_name
                try:
                    actualizar_estado_presupuesto(ruta_excel, state_name)
                except Exception:
                    logger.debug("No se pudo actualizar estado finalizado para %s", ruta_excel)
            _fill_entry_from_cache(entry, cached)
            result.append(entry)
            continue

        if cached and cached.get("fecha_modificacion_excel") == mtime_actual:
            # Aunque el mtime no cambie, validar la regla de coincidencia de hoja
            # para evitar seguir mostrando datos antiguos/incorrectos en cache.
            has_match = reader.has_matching_project_sheet(ruta_excel, numero) if numero else None
            refresh_due_to_policy = False
            if has_match is False:
                refresh_due_to_policy = True
            elif has_match is True:
                motivo = (cached.get("motivo_incompleto") or "").lower()
                if "ninguna hoja del excel coincide" in motivo:
                    refresh_due_to_policy = True
                elif (cached.get("total") in (None, 0, 0.0)) and not cached.get("es_finalizado"):
                    # Intentar recomputar por si el lector ahora sí puede extraer
                    # los importes (p.ej. formatos K/L/M soportados recientemente).
                    refresh_due_to_policy = True

            if refresh_due_to_policy:
                datos_cache = _build_cache_data(
                    proj, reader, relation_index, ruta_excel, mtime_actual, state_name
                )
                try:
                    upsert_presupuesto(datos_cache)
                except Exception:
                    logger.exception("Error al refrescar cache por política: %s", ruta_excel)
                persisted = get_presupuesto_por_ruta(ruta_excel)
                _fill_entry_from_cache(entry, persisted or datos_cache)
                result.append(entry)
                continue

            # Cache válida: mtime coincide
            # Solo actualizar estado si cambió de carpeta
            if cached.get("estado") != state_name and state_name:
                cached["estado"] = state_name
                try:
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
        persisted = get_presupuesto_por_ruta(ruta_excel)
        _fill_entry_from_cache(entry, persisted or datos_cache)
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
        "administracion_nombre": "",
        "direccion": "",
        "localidad": "",
        "tipo_obra": "",
        "fecha": "",
        "subtotal": None,
        "iva": None,
        "total": None,
        "ruta_excel": proj.get("ruta_excel", ""),
        "ruta_carpeta": proj.get("ruta_carpeta", ""),
        "estado": state_name,
        "datos_completos": False,
        "es_finalizado": False,
        "fuente_datos": "scan",
        "calidad_datos": 0,
        "motivo_incompleto": "",
    }


def _fill_entry_from_cache(entry: Dict, cached: Dict) -> None:
    """Rellena la entrada de la UI a partir de un dict de datos (cache DB o recién construido)."""
    entry["cliente"] = cached.get("cliente", "")
    entry["administracion_nombre"] = cached.get("administracion_nombre", "")
    entry["direccion"] = cached.get("direccion", "")
    entry["localidad"] = cached.get("localidad", "")
    entry["tipo_obra"] = cached.get("tipo_obra", "")
    entry["fecha"] = cached.get("fecha", "")
    entry["subtotal"] = cached.get("subtotal")
    entry["iva"] = cached.get("iva")
    entry["total"] = cached.get("total")
    entry["datos_completos"] = bool(cached.get("datos_completos", False))
    entry["estado"] = cached.get("estado", entry.get("estado", ""))
    entry["es_finalizado"] = bool(cached.get("es_finalizado", False))
    entry["fuente_datos"] = cached.get("fuente_datos", "scan")
    entry["calidad_datos"] = int(cached.get("calidad_datos") or 0)
    entry["motivo_incompleto"] = cached.get("motivo_incompleto", "")


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
    m = RE_PROJECT_NUM.search(numero)
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
        "fuente_datos": "scan",
        "es_finalizado": False,
    }

    # Regla estricta: si ninguna hoja coincide con el número esperado,
    # NO guardar datos de contenido del presupuesto.
    has_match = reader.has_matching_project_sheet(ruta_excel, numero) if numero else None
    if has_match is False:
        _apply_no_matching_sheet_policy(datos, numero)
        return datos

    # ── Fuente 1: Relación de presupuestos (metadatos) ──────────────
    # Cliente, localidad, tipo de obra y fecha se obtienen SIEMPRE de la
    # relación porque son los datos fiables y consistentes.
    rel = _lookup_relation(relation_index, numero)
    if rel:
        datos["cliente"] = rel.get("cliente", "")
        datos["localidad"] = rel.get("localidad", "")
        datos["tipo_obra"] = rel.get("tipo", "")
        datos["fecha"] = normalize_date(rel.get("fecha", ""))

    # ── Fuente 2: Cabecera y totales desde el Excel ─────────
    try:
        budget_data = reader.read(ruta_excel, expected_numero=numero)
        if budget_data:
            cab = budget_data.get("cabecera", {}) or {}
            direccion = (cab.get("direccion") or "").strip()
            direccion_valida = direccion and not _is_suspicious_text_value(direccion)
            if direccion_valida:
                datos["direccion"] = direccion
                datos["localizacion"] = direccion
            if not datos.get("localidad") and direccion_valida:
                datos["localidad"] = _infer_localidad_from_direccion(direccion)
            if not datos.get("tipo_obra"):
                tipo_obra_excel = strip_obra_prefix(cab.get("obra", ""))
                if not _is_suspicious_text_value(tipo_obra_excel):
                    datos["tipo_obra"] = tipo_obra_excel
            if not datos.get("cliente"):
                cliente_excel = (cab.get("cliente") or "").strip()
                if not _is_suspicious_text_value(cliente_excel):
                    datos["cliente"] = cliente_excel
            if not datos.get("fecha"):
                datos["fecha"] = normalize_date((cab.get("fecha") or "").strip())

            total = budget_data.get("total")
            if total is not None:
                datos["total"] = total
            if budget_data.get("subtotal") is not None:
                datos["subtotal"] = budget_data.get("subtotal")
            if budget_data.get("iva") is not None:
                datos["iva"] = budget_data.get("iva")

        if datos.get("total") is not None:
            datos["datos_completos"] = True
            logger.debug(
                "Cabecera/totales leídos de Excel para %s", ruta_excel
            )
        else:
            logger.warning(
                "No se pudo leer total desde Excel en: %s", ruta_excel
            )
    except Exception:
        logger.exception("Error al leer cabecera/totales: %s", ruta_excel)

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
            datos["comunidad_nombre"] = comunidad.get("nombre", "")
            datos["metodo_resolucion_comunidad"] = "por_nombre_cliente"
            admin_id = comunidad.get("administracion_id")
            if admin_id:
                datos["administracion_id"] = admin_id
                datos["metodo_resolucion_admin"] = "por_comunidad"
            return

        # Si no encontró comunidad, intentar buscar administración directamente
        # por si el campo cliente es realmente una administración
        admin = buscar_administracion_por_nombre(cliente)
        if admin:
            datos["administracion_id"] = admin["id"]
            datos["administracion_nombre"] = admin.get("nombre", "")
            datos["metodo_resolucion_admin"] = "por_nombre_cliente"
    except Exception:
        logger.debug("Error al vincular FKs para cliente '%s'", cliente)
