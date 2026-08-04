"""
Tareas 1-2 del plan docs/superpowers/plans/2026-08-04-paquete-contexto-ia.md.

scrub_text() es el filtro de datos personales que se aplica a todo texto
libre de partida antes de exportarlo al paquete de contexto para IA. Debe
eliminar direcciones, referencias a "Comunidad de Propietarios" y CIF/NIF,
sin tocar conceptos legitimos que contengan numeros o palabras parecidas.

export_context_pack() vuelca los cuatro ficheros del paquete (patrones,
repertorio, vocabulario, estructura) desde una base de solo lectura.
"""

from datetime import datetime
from pathlib import Path

from scripts.export_context_pack import export_context_pack, scrub_text
from scripts.rebuild_historical_patterns import sha256_file
from src.core.historical_budget_analyzer import HistoricalBudgetAnalyzer
from src.core.historical_pattern_builder import HistoricalPatternBuilder
from src.core.settings import Settings
from src.core.repositories import (
    assign_partida_module,
    get_or_create_execution_module,
    insert_historical_partida,
    upsert_historical_budget,
    upsert_partida_features,
)


class TestScrubTextRemovesPersonalData:
    def test_removes_calle_and_number(self):
        text, reasons = scrub_text("Reparacion de fachada en C/ Mayor 12")
        assert text == "Reparacion de fachada"
        assert "direccion" in reasons

    def test_removes_avenida(self):
        text, reasons = scrub_text("Pintura interior en Avda. de la Constitucion 45")
        assert text == "Pintura interior"
        assert "direccion" in reasons

    def test_removes_comunidad_de_propietarios(self):
        text, reasons = scrub_text("Pintura Comunidad de Propietarios Los Olivos")
        assert text == "Pintura"
        assert "comunidad" in reasons

    def test_removes_cif(self):
        text, reasons = scrub_text("Obra para cliente B12345678 impermeabilizacion")
        assert "B12345678" not in text
        assert "cif_nif" in reasons

    def test_no_reasons_when_nothing_removed(self):
        text, reasons = scrub_text("Alicatado de cocina")
        assert text == "Alicatado de cocina"
        assert reasons == []


class TestScrubTextPreservesLegitimateContent:
    def test_preserves_generic_calle_as_common_noun(self):
        """'calle' se usa a menudo como palabra comun en descripciones de obra
        ('puerta de la calle', 'segundo escalon de la calle'), no como marcador
        de direccion. Restringido a 'C/'/'Avda.' tras revisar datos reales:
        0 direcciones genuinas capturadas, 3 de 3 casos fueron falsos positivos
        que destrozaban texto tecnico legitimo (ver plan Tarea 1, revision humana
        2026-08-04)."""
        text, reasons = scrub_text("Picar el escalon de la calle, dejarlo lo mas bajo posible")
        assert text == "Picar el escalon de la calle, dejarlo lo mas bajo posible"
        assert reasons == []

    def test_preserves_plaza_de_garaje(self):
        text, reasons = scrub_text("Sellado de juntas en la plaza de garaje n. 54")
        assert text == "Sellado de juntas en la plaza de garaje n. 54"
        assert reasons == []

    def test_preserves_quantity_with_unit(self):
        text, reasons = scrub_text("Suministro de 12 ud de bajante")
        assert text == "Suministro de 12 ud de bajante"
        assert reasons == []

    def test_preserves_material_code_and_dimension(self):
        text, reasons = scrub_text("Mortero R4 espesor 15 mm")
        assert text == "Mortero R4 espesor 15 mm"
        assert reasons == []

    def test_preserves_plain_concept_with_no_address(self):
        text, reasons = scrub_text("Desmontaje de bajante de PVC")
        assert text == "Desmontaje de bajante de PVC"
        assert reasons == []

    def test_empty_string_is_safe(self):
        text, reasons = scrub_text("")
        assert text == ""
        assert reasons == []


def _seed_full_pack(tmp_path, monkeypatch):
    """Base minima con dos modulos, dos presupuestos INCLUDED y una linea
    compuesta sin ficha, para poder afirmar recuentos exactos del paquete
    exportado (no los ~33 patrones de produccion, que no son reproducibles
    en un test unitario). Una de las lineas lleva una direccion incrustada
    en el propio concepto_normalizado (no solo en el original) para
    verificar que el filtro se aplica a los CUATRO ficheros de salida, no
    solo a repertorio.csv."""
    db_path = tmp_path / "datos_pack_test.db"
    monkeypatch.setenv("CUBIAPP_DB_PATH", str(db_path))

    module_bajante, err = get_or_create_execution_module("sustitucion_bajante")
    assert err is None
    module_fachada, err = get_or_create_execution_module("fachada")
    assert err is None

    def _budget(nombre):
        bid, berr = upsert_historical_budget(
            {
                "ruta_excel": str(tmp_path / f"{nombre}.xlsx"),
                "ruta_carpeta": str(tmp_path),
                "nombre_proyecto": nombre,
                "fecha_modificacion_excel": datetime.now().isoformat(),
                "fecha_analisis": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "analisis_ok": True,
                "analysis_status": "VALID",
                "usable_for_learning": True,
                "learning_status": "INCLUDED",
            }
        )
        assert berr is None
        return bid

    def _partida(budget_id, concepto, unidad, precio, orden):
        pid, perr = insert_historical_partida(
            budget_id,
            {
                "orden": orden,
                "titulo": concepto[:40],
                "concepto_original": concepto,
                "concepto_normalizado": concepto.lower(),
                "unidad": unidad,
                "precio_unitario": precio,
                "cantidad": 1,
                "total_linea": precio,
            },
        )
        assert perr is None
        return pid

    def _atomic(pid, module_name, action, element, unit):
        ferr = upsert_partida_features(
            pid,
            {
                "action": action,
                "element": element,
                "system": None,
                "unit": unit,
                "material": None,
                "dimensions": (),
                "conditions": (),
                "line_kind": "atomic",
                "primary_module_id": module_name,
                "secondary_module_ids": (),
                "confidence": 0.9,
                "reasons": (),
                "classifier_version": "test",
            },
        )
        assert ferr is None

    budget_a = _budget("obra_a")
    budget_b = _budget("obra_b")

    p1 = _partida(budget_a, "Desmontaje bajante existente", "ml", 10.0, 1)
    assign_partida_module(p1, module_bajante, 0.9, "rules")
    _atomic(p1, "sustitucion_bajante", "demolish", "downspout", "ml")

    p2 = _partida(budget_a, "Desmontaje bajante existente", "ml", 20.0, 2)
    assign_partida_module(p2, module_bajante, 0.9, "rules")
    _atomic(p2, "sustitucion_bajante", "demolish", "downspout", "ml")

    p3 = _partida(budget_a, "Reparacion de fachada con grieta en C/ Mayor 12", "m2", 30.0, 3)
    assign_partida_module(p3, module_fachada, 0.9, "rules")
    _atomic(p3, "fachada", "repair", "facade", "m2")

    p4 = _partida(budget_b, "Desmontaje bajante existente", "ml", 15.0, 1)
    assign_partida_module(p4, module_bajante, 0.9, "rules")
    _atomic(p4, "sustitucion_bajante", "demolish", "downspout", "ml")

    # Linea compuesta sin ficha: debe salir en repertorio, no en patrones.
    _partida(budget_b, "Picado y reparacion de fachada con mortero", "m2", 55.0, 2)

    result = HistoricalPatternBuilder().rebuild_patterns()
    assert result["patterns_inserted"] == 2

    return db_path


class TestExportContextPack:
    def test_export_is_read_only_and_produces_expected_counts(self, tmp_path, monkeypatch):
        db_path = _seed_full_pack(tmp_path, monkeypatch)
        out_dir = tmp_path / "pack"
        before_hash = sha256_file(db_path)

        summary = export_context_pack(str(db_path), str(out_dir))

        assert sha256_file(db_path) == before_hash, "el exportador no debe escribir en la BD"
        assert summary["patrones"] == 2
        assert summary["repertorio"] == 5

    def test_patrones_csv_has_the_two_evidenced_concepts(self, tmp_path, monkeypatch):
        db_path = _seed_full_pack(tmp_path, monkeypatch)
        out_dir = tmp_path / "pack"
        export_context_pack(str(db_path), str(out_dir))

        text = (out_dir / "patrones.csv").read_text(encoding="utf-8").lower()
        assert "desmontaje bajante existente" in text
        assert "reparacion de fachada con grieta" in text
        # La compuesta no tiene evidencia de precio: no debe aparecer aqui.
        assert "picado y reparacion" not in text

    def test_repertorio_csv_includes_composite_lines(self, tmp_path, monkeypatch):
        db_path = _seed_full_pack(tmp_path, monkeypatch)
        out_dir = tmp_path / "pack"
        export_context_pack(str(db_path), str(out_dir))

        text = (out_dir / "repertorio.csv").read_text(encoding="utf-8").lower()
        assert "picado y reparacion de fachada con mortero" in text

    def test_vocabulario_md_lists_modules_and_closed_actions(self, tmp_path, monkeypatch):
        db_path = _seed_full_pack(tmp_path, monkeypatch)
        out_dir = tmp_path / "pack"
        export_context_pack(str(db_path), str(out_dir))

        text = (out_dir / "vocabulario.md").read_text(encoding="utf-8")
        assert "sustitucion_bajante" in text
        assert "fachada" in text
        assert "repair" in text  # accion del vocabulario cerrado importado, no reescrito a mano

    def test_no_output_file_leaks_the_embedded_address(self, tmp_path, monkeypatch):
        """La direccion iba incrustada en concepto_normalizado, no solo en el
        original: si algun fichero la lee de esa columna sin pasar por
        scrub_text, se filtraria igualmente."""
        db_path = _seed_full_pack(tmp_path, monkeypatch)
        out_dir = tmp_path / "pack"
        export_context_pack(str(db_path), str(out_dir))

        for f in Path(out_dir).iterdir():
            text = f.read_text(encoding="utf-8")
            assert "c/ mayor" not in text.lower(), f"direccion filtrada en {f.name}"

    def test_export_is_deterministic(self, tmp_path, monkeypatch):
        db_path = _seed_full_pack(tmp_path, monkeypatch)
        out_a = tmp_path / "pack_a"
        out_b = tmp_path / "pack_b"

        summary_a = export_context_pack(str(db_path), str(out_a))
        summary_b = export_context_pack(str(db_path), str(out_b))

        assert summary_a == summary_b
        for name in ("patrones.csv", "repertorio.csv", "vocabulario.md", "estructura.md"):
            assert (out_a / name).read_bytes() == (out_b / name).read_bytes()


class TestAutomaticExportTrigger:
    """Tarea 3: analyze_files() debe exportar el paquete tras reconstruir
    patrones, solo si hay ruta configurada, y sin tumbar el analisis si la
    exportacion falla. CUBIAPP_CONFIG_DIR se aisla a un tmp_path en cada test
    para no leer ni escribir la configuracion real del usuario."""

    def test_analyze_exports_pack_when_path_is_configured(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_CONFIG_DIR", str(tmp_path / "config"))
        _seed_full_pack(tmp_path, monkeypatch)

        out_dir = tmp_path / "auto_pack"
        Settings().set_default_path(Settings.PATH_CONTEXT_PACK, str(out_dir))

        result = HistoricalBudgetAnalyzer().analyze_files([], source_folder=str(tmp_path))

        assert result["errores"] == 0
        assert (out_dir / "patrones.csv").exists()
        assert (out_dir / "repertorio.csv").exists()
        assert (out_dir / "vocabulario.md").exists()
        assert (out_dir / "estructura.md").exists()

    def test_analyze_does_not_export_without_configured_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CUBIAPP_CONFIG_DIR", str(tmp_path / "config"))
        _seed_full_pack(tmp_path, monkeypatch)

        before = set(tmp_path.iterdir())
        result = HistoricalBudgetAnalyzer().analyze_files([], source_folder=str(tmp_path))
        after = set(tmp_path.iterdir())

        assert result["errores"] == 0
        assert before == after, "sin ruta configurada no debe crearse ninguna carpeta"

    def test_export_failure_does_not_break_analysis(self, tmp_path, monkeypatch):
        """Si la ruta configurada no se puede usar como carpeta (p. ej. ya
        existe un fichero con ese nombre), analyze_files() debe seguir
        devolviendo un resumen, solo con el fallo contabilizado en errores."""
        monkeypatch.setenv("CUBIAPP_CONFIG_DIR", str(tmp_path / "config"))
        _seed_full_pack(tmp_path, monkeypatch)

        blocked_path = tmp_path / "no_puede_ser_carpeta"
        blocked_path.write_text("soy un fichero, no una carpeta", encoding="utf-8")
        Settings().set_default_path(Settings.PATH_CONTEXT_PACK, str(blocked_path))

        result = HistoricalBudgetAnalyzer().analyze_files([], source_folder=str(tmp_path))

        assert result["errores"] >= 1
        assert "run_id" in result
