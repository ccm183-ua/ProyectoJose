"""
Tests del importador del XML de partidas (contrato de docs/esquema-partidas-ia.md).
"""

from datetime import datetime
from pathlib import Path

import pytest

from src.core.repositories import (
    assign_partida_module,
    get_or_create_execution_module,
    insert_historical_partida,
    upsert_historical_budget,
    upsert_partida_features,
)
from src.core.xml_budget_importer import match_partidas_with_evidence, parse_and_validate

VALID_XML = """<?xml version="1.0" encoding="UTF-8"?>
<presupuesto>
  <partida>
    <concepto>Reparacion de grieta en fachada</concepto>
    <unidad>m2</unidad>
    <cantidad estado="conocida">10</cantidad>
    <modulo>fachada</modulo>
    <nueva>false</nueva>
  </partida>
  <partida>
    <concepto>Pergola bioclimatica en azotea</concepto>
    <unidad>m2</unidad>
    <cantidad estado="pendiente"/>
    <modulo>fachada</modulo>
    <nueva>true</nueva>
  </partida>
</presupuesto>
"""


def _write_xml(tmp_path, content) -> str:
    path = tmp_path / "borrador.xml"
    path.write_text(content, encoding="utf-8")
    return str(path)


def _seed_evidence(tmp_path, monkeypatch):
    """Un modulo con una partida atomica evidenciada dos veces (repair/facade/m2)."""
    db_path = tmp_path / "datos_import_test.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))

    module_id, err = get_or_create_execution_module("fachada")
    assert err is None
    get_or_create_execution_module("sustitucion_bajante")

    bid, berr = upsert_historical_budget(
        {
            "ruta_excel": str(tmp_path / "obra.xlsx"),
            "ruta_carpeta": str(tmp_path),
            "nombre_proyecto": "obra",
            "fecha_modificacion_excel": datetime.now().isoformat(),
            "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "analisis_ok": True,
            "analysis_status": "VALID",
            "usable_for_learning": True,
            "learning_status": "INCLUDED",
        }
    )
    assert berr is None

    for orden, precio in ((1, 30.0), (2, 34.0)):
        pid, perr = insert_historical_partida(
            bid,
            {
                "orden": orden,
                "titulo": "Reparacion de grieta en fachada",
                "concepto_original": "Reparacion de grieta en fachada",
                "concepto_normalizado": "reparacion de grieta en fachada",
                "unidad": "m2",
                "precio_unitario": precio,
                "cantidad": 1,
                "total_linea": precio,
            },
        )
        assert perr is None
        assign_partida_module(pid, module_id, 0.9, "rules")
        ferr = upsert_partida_features(
            pid,
            {
                "action": "repair",
                "element": "facade",
                "system": None,
                "unit": "m2",
                "material": None,
                "dimensions": (),
                "conditions": (),
                "line_kind": "atomic",
                "primary_module_id": "fachada",
                "secondary_module_ids": (),
                "confidence": 0.9,
                "reasons": (),
                "classifier_version": "test",
            },
        )
        assert ferr is None

    return db_path


class TestParseAndValidate:
    def test_valid_file_splits_conocida_and_pendiente(self, tmp_path, monkeypatch):
        _seed_evidence(tmp_path, monkeypatch)
        xml_path = _write_xml(tmp_path, VALID_XML)

        result = parse_and_validate(xml_path)

        assert result["ok"] is True
        assert result["rechazadas"] == []
        assert len(result["aceptadas"]) == 2
        conocida, pendiente = result["aceptadas"]
        assert conocida["estado"] == "conocida"
        assert conocida["cantidad"] == 10.0
        assert pendiente["estado"] == "pendiente"
        assert pendiente["cantidad"] is None

    def test_malformed_xml_rejects_whole_file(self, tmp_path, monkeypatch):
        _seed_evidence(tmp_path, monkeypatch)
        xml_path = _write_xml(tmp_path, "<presupuesto><partida>")

        result = parse_and_validate(xml_path)

        assert result["ok"] is False
        assert "mal formado" in result["error"]

    def test_unexpected_element_rejects_whole_file(self, tmp_path, monkeypatch):
        _seed_evidence(tmp_path, monkeypatch)
        xml_path = _write_xml(
            tmp_path,
            """<?xml version="1.0" encoding="UTF-8"?>
<presupuesto>
  <partida>
    <concepto>Reparacion de grieta en fachada</concepto>
    <unidad>m2</unidad>
    <cantidad estado="conocida">10</cantidad>
    <precio>30</precio>
    <modulo>fachada</modulo>
    <nueva>false</nueva>
  </partida>
</presupuesto>
""",
        )

        result = parse_and_validate(xml_path)

        assert result["ok"] is False
        assert "precio" in result["error"]

    def test_missing_estado_attribute_rejects_only_that_partida(self, tmp_path, monkeypatch):
        _seed_evidence(tmp_path, monkeypatch)
        xml_path = _write_xml(
            tmp_path,
            """<?xml version="1.0" encoding="UTF-8"?>
<presupuesto>
  <partida>
    <concepto>Reparacion de grieta en fachada</concepto>
    <unidad>m2</unidad>
    <cantidad>10</cantidad>
    <modulo>fachada</modulo>
    <nueva>false</nueva>
  </partida>
  <partida>
    <concepto>Pergola bioclimatica en azotea</concepto>
    <unidad>m2</unidad>
    <cantidad estado="pendiente"/>
    <modulo>fachada</modulo>
    <nueva>true</nueva>
  </partida>
</presupuesto>
""",
        )

        result = parse_and_validate(xml_path)

        assert result["ok"] is True
        assert len(result["aceptadas"]) == 1
        assert len(result["rechazadas"]) == 1
        assert "estado" in result["rechazadas"][0]["motivo"]

    def test_missing_nueva_rejects_only_that_partida(self, tmp_path, monkeypatch):
        _seed_evidence(tmp_path, monkeypatch)
        xml_path = _write_xml(
            tmp_path,
            """<?xml version="1.0" encoding="UTF-8"?>
<presupuesto>
  <partida>
    <concepto>Reparacion de grieta en fachada</concepto>
    <unidad>m2</unidad>
    <cantidad estado="conocida">10</cantidad>
    <modulo>fachada</modulo>
  </partida>
</presupuesto>
""",
        )

        result = parse_and_validate(xml_path)

        assert result["ok"] is True
        assert result["aceptadas"] == []
        assert "nueva" in result["rechazadas"][0]["motivo"]

    def test_empty_concepto_is_rejected(self, tmp_path, monkeypatch):
        _seed_evidence(tmp_path, monkeypatch)
        xml_path = _write_xml(
            tmp_path,
            """<?xml version="1.0" encoding="UTF-8"?>
<presupuesto>
  <partida>
    <concepto></concepto>
    <unidad>m2</unidad>
    <cantidad estado="conocida">10</cantidad>
    <modulo>fachada</modulo>
    <nueva>false</nueva>
  </partida>
</presupuesto>
""",
        )

        result = parse_and_validate(xml_path)

        assert result["ok"] is True
        assert result["aceptadas"] == []
        assert "concepto" in result["rechazadas"][0]["motivo"]

    def test_unknown_modulo_is_rejected(self, tmp_path, monkeypatch):
        _seed_evidence(tmp_path, monkeypatch)
        xml_path = _write_xml(
            tmp_path,
            """<?xml version="1.0" encoding="UTF-8"?>
<presupuesto>
  <partida>
    <concepto>Poda de jardin</concepto>
    <unidad>m2</unidad>
    <cantidad estado="conocida">10</cantidad>
    <modulo>jardineria</modulo>
    <nueva>true</nueva>
  </partida>
</presupuesto>
""",
        )

        result = parse_and_validate(xml_path)

        assert result["ok"] is True
        assert result["aceptadas"] == []
        assert "vocabulario cerrado" in result["rechazadas"][0]["motivo"]

    def test_unknown_unidad_is_rejected(self, tmp_path, monkeypatch):
        _seed_evidence(tmp_path, monkeypatch)
        xml_path = _write_xml(
            tmp_path,
            """<?xml version="1.0" encoding="UTF-8"?>
<presupuesto>
  <partida>
    <concepto>Reparacion de grieta en fachada</concepto>
    <unidad>quintales</unidad>
    <cantidad estado="conocida">10</cantidad>
    <modulo>fachada</modulo>
    <nueva>false</nueva>
  </partida>
</presupuesto>
""",
        )

        result = parse_and_validate(xml_path)

        assert result["ok"] is True
        assert result["aceptadas"] == []
        assert "unidades observadas" in result["rechazadas"][0]["motivo"]


class TestMatchPartidasWithEvidence:
    def test_pendiente_partidas_are_separated_and_never_priced(self, tmp_path, monkeypatch):
        _seed_evidence(tmp_path, monkeypatch)
        aceptadas = [
            {
                "concepto": "Pergola bioclimatica en azotea",
                "unidad": "m2",
                "cantidad": None,
                "estado": "pendiente",
                "modulo": "fachada",
                "nueva": True,
            }
        ]

        listas, pendientes = match_partidas_with_evidence(aceptadas)

        assert listas == []
        assert len(pendientes) == 1

    def test_matching_evidence_yields_historical_price(self, tmp_path, monkeypatch):
        _seed_evidence(tmp_path, monkeypatch)
        aceptadas = [
            {
                "concepto": "Reparacion de grieta en fachada",
                "unidad": "m2",
                "cantidad": 10.0,
                "estado": "conocida",
                "modulo": "fachada",
                "nueva": False,
            }
        ]

        listas, pendientes = match_partidas_with_evidence(aceptadas)

        assert pendientes == []
        assert len(listas) == 1
        partida = listas[0]
        assert partida["source"].startswith("historical_")
        assert partida["precio_unitario"] == pytest.approx(32.0)
        assert partida["cantidad"] == 10.0

    def test_no_evidence_never_invents_a_price(self, tmp_path, monkeypatch):
        _seed_evidence(tmp_path, monkeypatch)
        aceptadas = [
            {
                "concepto": "Suministro y montaje de pergola bioclimatica",
                "unidad": "m2",
                "cantidad": 12.0,
                "estado": "conocida",
                "modulo": "fachada",
                "nueva": True,
            }
        ]

        listas, pendientes = match_partidas_with_evidence(aceptadas)

        assert len(listas) == 1
        partida = listas[0]
        assert partida["source"] == "sin_evidencia_ia"
        assert partida["precio_unitario"] == 0.0
        assert "Sin evidencia" in partida["reason"]
