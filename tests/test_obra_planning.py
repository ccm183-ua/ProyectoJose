"""Núcleo de la planificación de obras (sin PySide6)."""

from datetime import date

import pytest

from src.core.obra_planning import (
    aviso_text,
    color_category,
    date_from_folder_name,
    duracion_text,
    retraso_text,
)

HOY = date(2026, 11, 13)


@pytest.mark.parametrize("nombre,esperado", [
    # nombres reales de la carpeta EJECUTAR
    ("114-26 C.P. RAFAEL ASÍN 23-GRAL.PINTOS 17 (HUMEDADES)         EJECUTAR EL 13-07-26",
     (date(2026, 7, 13), False)),
    ("208-26 C. P. JUAN DE HERRERA 19 (SUST. BAJANTE E INJERTO)      EJECUTAR EL 25-06-26",
     (date(2026, 6, 25), False)),
    ("48-25 C- MAESTRO MARQUÉS Nº 28-03004-ALICANTE (REP. Y PINTURA PATIOS) EJECUTAR 19-05-26",
     (date(2026, 5, 19), False)),
    ("127-25 C.P. TENIENTE LLORCA Nº 34  ALICANTE (REHABILITACIÓN FACHADA) SE EJECUTARÁ EN JULIO'26",
     (date(2026, 7, 1), True)),
    ("30-26 C.P. DR. FLEMING, 1 - SAN VICENTE (PTO. PINTURA FACHADA P.B.) APROBADO - EJECUTAR EN JULIO'26",
     (date(2026, 7, 1), True)),
    # otros formatos
    ("200-26 OBRA X 03/02/2027", (date(2027, 2, 3), False)),
    ("201-26 OBRA Y empieza en septiembre 2026", (date(2026, 9, 1), True)),
    # sin fecha o con números que no son fecha
    ("137-26 C.P. RABASA Nº 20 - ALICANTE (SUST. VENTANAS Y PINTURA ESCALERA)", None),
    ("152-26 C.P. FLORIDA BABEL - CATRAL Nº 43 -3º -  ALICANTE (TECHO GALERÍA)", None),
    ("99-26 OBRA 31-02-26", None),          # fecha imposible
    ("", None),
])
def test_date_from_folder_name(nombre, esperado):
    assert date_from_folder_name(nombre) == esperado


@pytest.mark.parametrize("inicio,avisado,margen,esperado", [
    (date(2026, 11, 18), None, 7, "en 5 días"),
    (date(2026, 11, 14), None, 7, "mañana"),
    (date(2026, 11, 13), None, 7, "hoy"),
    (date(2026, 12, 30), None, 7, ""),                       # fuera del margen
    (date(2026, 11, 10), None, 7, "debía empezar hace 3 días"),
    (date(2026, 11, 18), date(2026, 11, 3), 7, "avisada el 03/11"),
    (None, None, 7, ""),
])
def test_aviso_text(inicio, avisado, margen, esperado):
    assert aviso_text(inicio, avisado, margen, HOY) == esperado


@pytest.mark.parametrize("inicio,margen,esperado", [
    (date(2026, 11, 18), 7, "warning"),
    (date(2026, 11, 13), 7, "warning"),
    (date(2026, 11, 10), 7, "late"),
    (date(2026, 12, 30), 7, ""),
    (None, 7, ""),
])
def test_color_category(inicio, margen, esperado):
    assert color_category(inicio, margen, HOY) == esperado


def test_retraso_y_duracion():
    assert retraso_text(date(2026, 11, 10), HOY) == "3 días"
    assert retraso_text(date(2026, 11, 12), HOY) == "1 día"
    assert retraso_text(date(2026, 11, 20), HOY) == ""
    assert retraso_text(None, HOY) == ""
    assert duracion_text(date(2026, 10, 1), date(2026, 10, 15)) == "14 días"
    assert duracion_text(date(2026, 10, 1), None) == ""
    assert duracion_text(date(2026, 10, 15), date(2026, 10, 1)) == ""   # incoherente
