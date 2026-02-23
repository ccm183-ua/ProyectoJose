"""
Relleno de plantillas Excel 122-20 mediante manipulación XML.
Incluye sustitución de celdas y conversión de números a letras.
"""

import logging
import os
import re
import shutil
import tempfile
import zipfile
from xml.sax.saxutils import escape as xml_escape

logger = logging.getLogger(__name__)

# Hoja de datos en la plantilla 122-20
SHEET_12220 = "xl/worksheets/sheet1.xml"


def replace_cell_in_sheet_xml(sheet_xml, ref, value):
    """Sustituye el valor de la celda ref en el XML de la hoja; conserva el estilo (s=...)."""
    escaped = xml_escape(str(value))
    # Celda: <c r="E5" s="64"/> o <c r="E5" s="64">...</c>; conservar estilo
    pattern = r'<c r="' + re.escape(ref) + r'" ([^>]*?)(?:/>|>.*?</c>)'
    match = re.search(pattern, sheet_xml, re.DOTALL)
    if not match:
        return sheet_xml
    attrs = match.group(1)
    style = re.search(r's="\d+"', attrs)
    style_str = (" " + style.group(0)) if style else ""
    new_cell = f'<c r="{ref}"{style_str} t="inlineStr"><is><t>{escaped}</t></is></c>'
    return re.sub(pattern, new_cell, sheet_xml, count=1, flags=re.DOTALL)


_UNIDADES = (
    '', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO',
    'NUEVE', 'DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE', 'QUINCE',
    'DIECISÉIS', 'DIECISIETE', 'DIECIOCHO', 'DIECINUEVE', 'VEINTE',
    'VEINTIÚN', 'VEINTIDÓS', 'VEINTITRÉS', 'VEINTICUATRO', 'VEINTICINCO',
    'VEINTISÉIS', 'VEINTISIETE', 'VEINTIOCHO', 'VEINTINUEVE',
)
_DECENAS = (
    '', '', '', 'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA',
    'SETENTA', 'OCHENTA', 'NOVENTA',
)
_CENTENAS = (
    '', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS',
    'QUINIENTOS', 'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS',
    'NOVECIENTOS',
)


def numero_a_letras(n: int) -> str:
    """Convierte un entero (0 – 999 999 999) a texto en español (mayúsculas)."""
    if n == 0:
        return 'CERO'
    if n == 100:
        return 'CIEN'

    partes = []

    if n >= 1_000_000:
        millones = n // 1_000_000
        n %= 1_000_000
        if millones == 1:
            partes.append('UN MILLÓN')
        else:
            partes.append(f'{numero_a_letras(millones)} MILLONES')

    if n >= 1000:
        miles = n // 1000
        n %= 1000
        if miles == 1:
            partes.append('MIL')
        else:
            partes.append(f'{numero_a_letras(miles)} MIL')

    if n >= 100:
        if n == 100:
            partes.append('CIEN')
            return ' '.join(partes)
        partes.append(_CENTENAS[n // 100])
        n %= 100

    if 0 < n < 30:
        partes.append(_UNIDADES[n])
    elif n >= 30:
        decena = _DECENAS[n // 10]
        unidad = _UNIDADES[n % 10]
        partes.append(f'{decena} Y {unidad}' if unidad else decena)

    return ' '.join(p for p in partes if p)


def euros_en_letras(importe: float) -> str:
    """Devuelve *importe* en formato 'CIENTO VEINTITRÉS EUROS CON CUARENTA Y CINCO CÉNTIMOS'."""
    centimos_total = round(importe * 100)
    euros = centimos_total // 100
    centimos = centimos_total % 100

    txt = numero_a_letras(euros)
    txt += ' EURO' if euros == 1 else ' EUROS'

    if centimos:
        txt += f' CON {numero_a_letras(centimos)}'
        txt += ' CÉNTIMO' if centimos == 1 else ' CÉNTIMOS'

    return txt


class TemplateFiller:
    """Rellena plantillas Excel 122-20 sin abrir con openpyxl (logo/título intactos)."""

    def create_from_template(self, template_path, output_path, data):
        """
        Crea un archivo Excel desde una plantilla rellenando los datos.

        Args:
            template_path: Ruta de la plantilla
            output_path: Ruta donde guardar el archivo
            data: Diccionario con los datos a rellenar

        Returns:
            bool: True si se creó correctamente, False en caso contrario
        """
        try:
            # Crear directorio de salida primero
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            # Copiar plantilla al destino (logo, imágenes y formato quedan intactos)
            shutil.copy2(template_path, output_path)

            # Preparar datos del proyecto
            nombre_obra = data.get('nombre_obra', '')
            if not nombre_obra:
                nombre_obra = f"{data.get('direccion', '')} {data.get('numero', '')}".strip()
            direccion_parts = []
            if data.get('calle'):
                direccion_parts.append(data.get('calle'))
            if data.get('num_calle'):
                direccion_parts.append(f"Nº {data.get('num_calle')}")
            direccion_solo_calle_numero = ' '.join(direccion_parts)
            if not direccion_solo_calle_numero:
                direccion_solo_calle_numero = (data.get('direccion', '') or '').strip()
                if data.get('numero'):
                    direccion_solo_calle_numero = f"{direccion_solo_calle_numero} Nº {data.get('numero')}".strip()

            # Rellenar solo las celdas de datos en el XML de la hoja
            self._patch_sheet2_cells_12220(output_path, data, nombre_obra, direccion_solo_calle_numero)
            return True

        except Exception as e:
            logger.exception("Error al crear archivo Excel")
            return False

    def _patch_sheet2_cells_12220(self, output_path, data, nombre_obra, direccion_solo_calle_numero):
        """
        Modifica solo el XML de la hoja de datos (sheet2) dentro del xlsx, sin tocar
        medios (logo, imágenes) ni dibujos. Así el logo y el título quedan intactos.
        """
        # Valores para cada celda (inlineStr para no tocar sharedStrings)
        fecha = data.get('fecha', '')
        if fecha:
            try:
                parts = str(fecha).strip().split('-')
                if len(parts) == 3:
                    fecha = f"{parts[0]}/{parts[1]}/{parts[2]}"
            except Exception:
                logger.debug("No se pudo formatear la fecha: %s", fecha)
        obra_texto = (data.get('tipo', '') or nombre_obra or '').strip()
        obra_final = f"Obra: {obra_texto}." if obra_texto else "Obra:"

        numero_pres = str(data.get('numero_proyecto', '') or data.get('numero', '') or '').strip()
        fecha_raw = data.get('fecha', '') or ''
        year_suffix = ''
        try:
            fecha_parts = str(fecha_raw).strip().split('-')
            if len(fecha_parts) == 3:
                year_suffix = fecha_parts[2]
        except Exception:
            logger.debug("No se pudo extraer año de la fecha: %s", fecha_raw)
        if numero_pres and year_suffix:
            numero_pres = f"{numero_pres}/{year_suffix}"

        cliente = (data.get('cliente', '') or '').strip()

        celdas = {
            "E5": numero_pres,
            "H5": fecha or '',
            "B7": cliente,
            "H7": (data.get('admin_cif', '') or '').strip(),
            "B9": (direccion_solo_calle_numero or '').strip(),
            "H9": str(data.get('codigo_postal', '') or '').strip(),
            "B11": (data.get('admin_email', '') or '').strip(),
            "H11": (data.get('admin_telefono', '') or '').strip(),
            "A14": obra_final,
            "A57": cliente,
        }

        with zipfile.ZipFile(output_path, "r") as z_in:
            namelist = z_in.namelist()
            sheet_content = z_in.read(SHEET_12220).decode("utf-8")
            otros = {n: z_in.read(n) for n in namelist if n != SHEET_12220}

        for ref, valor in celdas.items():
            sheet_content = replace_cell_in_sheet_xml(sheet_content, ref, valor)

        fd, tmp_path = tempfile.mkstemp(suffix=".xlsx")
        try:
            os.close(fd)
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as z_out:
                for name in namelist:
                    if name == SHEET_12220:
                        z_out.writestr(name, sheet_content.encode("utf-8"))
                    else:
                        z_out.writestr(name, otros[name])
            shutil.move(tmp_path, output_path)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise
