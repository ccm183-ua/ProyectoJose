"""
Tarea 1-2 del plan docs/superpowers/plans/2026-08-04-paquete-contexto-ia.md.

Exporta a una carpeta el paquete de contexto que se sube a Claude para
redactar borradores de presupuesto: patrones con precio evidenciado,
repertorio de conceptos reales, vocabulario cerrado y un presupuesto de
ejemplo. Solo lectura sobre la base de datos (modo ro, sin migraciones).

scrub_text() es un minimizador best-effort del texto libre de partida: borra
un conjunto estrecho de patrones (direcciones con "C/"/"Avda.", "Comunidad
de Propietarios", CIF/NIF y correos) sin tocar conceptos legitimos que
contengan numeros o palabras parecidas (medidas, codigos de material).

NO es anonimizacion y no se debe presentar como tal: deja fuera formatos de
direccion o identificadores que no reconoce. El paquete exportado incluye un
LIMITES.md con lo que no garantiza, para que se revise a mano antes de
compartirlo. La minimizacion de campos (no exportar cliente, administracion,
contacto, CIF, direccion postal ni nombre del Excel) reduce el riesgo, pero no
sustituye esa revision.
"""

import csv
import io
import os
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple

# Vocabulario cerrado real (Fase 2): se importa en vez de reescribirlo a mano
# para que vocabulario.md no pueda desincronizarse del clasificador real.
from src.core.historical_partida_features import _ACTION_SYNONYMS, _ELEMENT_SYNONYMS

# Vias: "en C/ Mayor 12", "Avda. de la Constitucion 45". Deliberadamente
# restringido a "C/" y "Avda." (no "calle"/"plaza"/"paseo"/"urb..."): sobre
# datos reales, esas palabras aparecen casi siempre como sustantivo comun en
# descripciones de obra ("puerta de la calle", "plaza de garaje") y no como
# marcador de una direccion postal real; "C/" y "Avda." casi no se usan con
# otro sentido. El "en" delante es opcional.
_RE_DIRECCION = re.compile(
    r"(?:\s+en)?\s+(?:c/|avda\.?\b)[^,]*",
    re.IGNORECASE,
)

# "Comunidad de Propietarios Los Olivos" hasta el final del segmento.
_RE_COMUNIDAD = re.compile(
    r"\s*comunidad\s+de\s+propietarios\b[^,]*",
    re.IGNORECASE,
)

# CIF/NIF: letra + 8 digitos, u 8 digitos + letra.
_RE_CIF_NIF = re.compile(r"\b[A-Za-z]\d{8}\b|\b\d{8}[A-Za-z]\b")

# Correo electronico. Nunca es parte de un concepto tecnico facturable, asi
# que eliminarlo no destruye informacion util.
_RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")


LIMITES_FILENAME = "LIMITES.md"

_LIMITES_MD = """# Limites del paquete de contexto

Este paquete **no esta anonimizado**. Se genera con una minimizacion
best-effort del texto libre (direcciones con `C/`/`Avda.`, "Comunidad de
Propietarios", CIF/NIF y correos), pero ese filtro es deliberadamente
estrecho: **no garantiza** que desaparezcan todos los identificadores.

Revisa el contenido a mano antes de compartirlo o subirlo a un proveedor.

## Que incluye

- `patrones.csv`: conceptos con precio evidenciado.
- `repertorio.csv`: conceptos y precios historicos incluidos en memoria.
- `vocabulario.md`: listas cerradas de modulos, acciones, elementos y unidades.
- `estructura.md`: orden y agrupacion de un presupuesto real.

## Que NO se exporta (minimizacion de campos)

- Cliente/comunidad, administracion, CIF, telefono y correo de contacto.
- Direccion postal de cabecera, localidad y nombre/ruta del fichero Excel.
- Cualquier importe o dato que no provenga de partidas incluidas en memoria.

## Que puede quedar en el texto

- Nombres propios, cargos y direcciones con formatos no reconocidos.
- Identificadores embebidos en conceptos tecnicos (p. ej. numeros de via).
"""


def scrub_text(text: str) -> Tuple[str, List[str]]:
    """Minimiza best-effort datos personales de un texto libre de partida.

    NO es anonimizacion: solo retira los patrones estrechos que reconoce.
    Devuelve el texto limpio y la lista de razones por las que se toco
    (vacia si no se elimino nada), para poder auditar el resultado en vez
    de confiar a ciegas en que el filtro acerto.
    """
    reasons: List[str] = []
    cleaned = text

    if _RE_DIRECCION.search(cleaned):
        cleaned = _RE_DIRECCION.sub("", cleaned)
        reasons.append("direccion")

    if _RE_COMUNIDAD.search(cleaned):
        cleaned = _RE_COMUNIDAD.sub("", cleaned)
        reasons.append("comunidad")

    if _RE_CIF_NIF.search(cleaned):
        cleaned = _RE_CIF_NIF.sub("", cleaned)
        reasons.append("cif_nif")

    if _RE_EMAIL.search(cleaned):
        cleaned = _RE_EMAIL.sub("", cleaned)
        reasons.append("email")

    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, reasons


def _connect_ro(db_path: str) -> sqlite3.Connection:
    uri = f"file:{Path(db_path).as_posix()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{round(value, 2)}"
    return str(value)


def _render_patrones_csv(conn: sqlite3.Connection) -> Tuple[str, int]:
    """Precio evidenciado: unica fuente que puede aportar precio al
    validador. Concepto scrubbed igual que en repertorio.csv y estructura.md
    porque suggested_partida_pattern.concepto_normalizado viene tal cual del
    texto libre original, no se limpia al construir el patron."""
    rows = conn.execute(
        """SELECT p.concepto_normalizado, em.nombre, p.unidad_habitual,
                  p.precio_unitario_mediana, p.precio_unitario_min, p.precio_unitario_max,
                  p.frecuencia, p.distinct_budget_count, p.evidence_quality
           FROM suggested_partida_pattern p
           JOIN execution_module em ON em.id = p.module_id
           WHERE p.activo = 1
           ORDER BY em.nombre, p.concepto_normalizado"""
    ).fetchall()

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow([
        "concepto", "modulo", "unidad", "precio_mediana", "precio_min",
        "precio_max", "frecuencia", "presupuestos_distintos", "calidad_evidencia",
    ])
    for concepto, modulo, unidad, mediana, pmin, pmax, freq, distinct, calidad in rows:
        concepto, _ = scrub_text(concepto or "")
        writer.writerow([
            concepto, modulo, unidad or "", _fmt(mediana), _fmt(pmin),
            _fmt(pmax), freq or 0, distinct or 0, calidad or "",
        ])
    return buffer.getvalue(), len(rows)


def _render_repertorio_csv(conn: sqlite3.Connection) -> Tuple[str, int]:
    """Como se redacta y que se cobro de verdad: incluye lineas compuestas,
    a diferencia de patrones.csv. Referencia orientativa, nunca evidencia."""
    rows = conn.execute(
        """SELECT hp.concepto_original, hp.unidad, hp.precio_unitario,
                  COALESCE(f.line_kind, 'sin_clasificar'), COALESCE(f.primary_module_id, '')
           FROM historical_partida hp
           JOIN historical_budget hb ON hb.id = hp.historical_budget_id
           LEFT JOIN historical_partida_feature f ON f.partida_id = hp.id
           WHERE hb.learning_status = 'INCLUDED' AND hp.precio_unitario > 0
           ORDER BY hp.concepto_original, hp.unidad"""
    ).fetchall()

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["concepto", "unidad", "precio_unitario", "tipo_linea", "modulo_principal"])
    for concepto, unidad, precio, tipo_linea, modulo in rows:
        concepto, _ = scrub_text(concepto or "")
        writer.writerow([concepto, unidad or "", _fmt(precio), tipo_linea, modulo])
    return buffer.getvalue(), len(rows)


def _render_vocabulario_md(conn: sqlite3.Connection) -> Tuple[str, int]:
    """Las listas cerradas: fuente de verdad de lo que el futuro validador
    aceptara. Modulos y unidades vienen de la BD; acciones y elementos se
    importan del clasificador real (Fase 2) para no poder desincronizarse."""
    modulos = conn.execute(
        "SELECT nombre, COALESCE(categoria, ''), COALESCE(descripcion, '') "
        "FROM execution_module WHERE activo = 1 ORDER BY nombre"
    ).fetchall()
    unidades = [
        row[0]
        for row in conn.execute(
            """SELECT DISTINCT hp.unidad
               FROM historical_partida hp
               JOIN historical_budget hb ON hb.id = hp.historical_budget_id
               WHERE hb.learning_status = 'INCLUDED' AND hp.precio_unitario > 0
                 AND hp.unidad IS NOT NULL AND hp.unidad <> ''
               ORDER BY hp.unidad"""
        ).fetchall()
    ]

    lines = ["# Vocabulario cerrado", ""]

    lines.append("## Modulos de ejecucion")
    for nombre, categoria, descripcion in modulos:
        sufijo = f" ({categoria})" if categoria else ""
        lines.append(f"- `{nombre}`{sufijo}: {descripcion}" if descripcion else f"- `{nombre}`{sufijo}")
    lines.append("")

    lines.append("## Acciones")
    for action, keywords in _ACTION_SYNONYMS:
        lines.append(f"- `{action}`: {', '.join(keywords)}")
    lines.append("")

    lines.append("## Elementos")
    for element, keywords in _ELEMENT_SYNONYMS:
        lines.append(f"- `{element}`: {', '.join(keywords)}")
    lines.append("")

    lines.append("## Unidades observadas")
    lines.append(", ".join(unidades) if unidades else "(ninguna)")
    lines.append("")

    lines.append("## Criterio atomica frente a compuesta")
    lines.append(
        "Una linea es **atomica** cuando describe una unica accion sobre un "
        "unico elemento facturable. Es **compuesta** cuando el texto "
        "menciona dos o mas acciones distintas, o dos o mas elementos de "
        "familias distintas (una variante mas especifica del mismo elemento, "
        "como `facade_render` frente a `facade`, no cuenta como una segunda "
        "familia). Solo las lineas atomicas con accion, elemento, unidad y "
        "modulo principal completos pueden aportar precio evidenciado."
    )
    lines.append("")

    return "\n".join(lines), len(modulos)


def _render_estructura_md(conn: sqlite3.Connection) -> Tuple[str, int]:
    """Un presupuesto real INCLUDED, el mas representativo por numero de
    partidas, para mostrar orden y agrupacion de una obra real."""
    budget = conn.execute(
        """SELECT hb.id, hb.nombre_proyecto, COUNT(*) n
           FROM historical_budget hb
           JOIN historical_partida hp ON hp.historical_budget_id = hb.id
           WHERE hb.learning_status = 'INCLUDED'
           GROUP BY hb.id
           ORDER BY n DESC, hb.id ASC
           LIMIT 1"""
    ).fetchone()

    lines = ["# Estructura de un presupuesto real", ""]
    if budget is None:
        lines.append("(sin presupuestos incluidos todavia)")
        return "\n".join(lines), 0

    budget_id = budget[0]
    partidas = conn.execute(
        """SELECT orden, concepto_original, unidad, cantidad
           FROM historical_partida
           WHERE historical_budget_id = ?
           ORDER BY orden""",
        (budget_id,),
    ).fetchall()

    lines.append("| orden | concepto | unidad | cantidad |")
    lines.append("|---|---|---|---|")
    for orden, concepto, unidad, cantidad in partidas:
        concepto, _ = scrub_text(concepto or "")
        lines.append(f"| {orden} | {concepto} | {unidad or ''} | {_fmt(cantidad)} |")
    lines.append("")

    return "\n".join(lines), len(partidas)


def _render_limites_md() -> Tuple[str, int]:
    """Declara en el propio paquete que no es una salida anonimizada y que
    hay que revisarlo antes de compartirlo. Sin este fichero, el nombre de la
    carpeta podria leerse como una garantia de anonimizacion."""
    return _LIMITES_MD, 1


def _publish_files(out: Path, contents: Dict[str, str]) -> None:
    """Publica el paquete por staging: escribe cada fichero a un temporal de
    la misma carpeta y solo despues lo mueve a su nombre final. Si algo falla
    antes del primer movimiento, la version anterior queda intacta entera."""
    staged: List[Tuple[Path, Path]] = []
    try:
        for name, content in contents.items():
            tmp = out / f".{name}.tmp"
            tmp.write_text(content, encoding="utf-8")
            staged.append((tmp, out / name))
        for tmp, target in staged:
            os.replace(tmp, target)
    except BaseException:
        for tmp, _target in staged:
            try:
                tmp.unlink()
            except OSError:
                pass
        raise


def export_context_pack(db_path: str, out_dir: str) -> Dict[str, int]:
    """Exporta el paquete de contexto completo. Solo lectura: abre la BD en
    modo ro y no llama a init_schema ni a ninguna migracion.

    Renderiza todos los ficheros desde una unica transaccion de lectura antes
    de publicar ninguno: o se publica una version coherente entera, o la
    version anterior permanece intacta."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    conn = _connect_ro(db_path)
    try:
        conn.isolation_level = None
        conn.execute("BEGIN")
        rendered = {
            "patrones.csv": _render_patrones_csv(conn),
            "repertorio.csv": _render_repertorio_csv(conn),
            "vocabulario.md": _render_vocabulario_md(conn),
            "estructura.md": _render_estructura_md(conn),
            LIMITES_FILENAME: _render_limites_md(),
        }
        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()

    _publish_files(out, {name: content for name, (content, _count) in rendered.items()})

    return {
        "patrones": rendered["patrones.csv"][1],
        "repertorio": rendered["repertorio.csv"][1],
        "vocabulario_modulos": rendered["vocabulario.md"][1],
        "estructura_partidas": rendered["estructura.md"][1],
        "limites": rendered[LIMITES_FILENAME][1],
    }
