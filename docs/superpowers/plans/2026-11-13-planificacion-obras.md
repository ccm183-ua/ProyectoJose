# Planificación de obras (pieza A) — plan de implementación

**Spec:** `docs/superpowers/specs/2026-11-13-planificacion-obras-design.md`.
**Rama:** `planificacion-obras` (desde `prueba-claude`).
**Método:** cada hito = tests que fallan → código mínimo → tests en verde → commit.
Comando de tests: `QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest -q --no-header -p no:cacheprovider <ruta>`.

## Restricciones globales

- Núcleo (`src/core/obra_planning.py`) sin PySide6.
- Nada se guarda en el Excel; ninguna fecha se inventa (deducidas = aproximadas;
  propuestas = no se guardan sin confirmar).
- Clave: `numero_proyecto`; números repetidos o vacíos no se planifican.
- Ningún test toca la BD real (`CUBIAPP_DB_PATH` en `tmp_path`).

## Hitos

| Hito | Entregable | Ficheros | Tests |
|---|---|---|---|
| P1 | Núcleo puro: fecha desde el nombre de la carpeta; textos de Aviso, Retraso y Duración; categoría de color | `src/core/obra_planning.py`, `tests/test_obra_planning.py` | formatos dd-mm-aa, dd/mm/aaaa, "EN JULIO'26", "julio 2026", nombres sin fecha; aviso en N días / hoy / lejos / avisada; retraso; duración; ámbar/rojo |
| P2 | Migración v5 y repositorio | `src/core/database.py`, `src/core/repositories/obra_planificacion_repository.py`, `tests/test_obra_planificacion_repository.py` | tabla creada en BD nueva y migrada; get/upsert; `record_state_change` (exacta al mover); `reconcile_scan` (primer escaneo sin fechas, cambio externo → aproximada, retroceso no borra, repetidos ignorados) |
| P3 | Margen general en Ajustes | `src/core/settings.py`, `tests/test_settings.py` | por defecto 7, guarda y lee, rango 0-365 |
| P4 | Diálogo de planificación | `src/gui/obra_planning_dialog.py`, `tests/test_obra_planning_gui.py` | precarga, valida fin ≥ inicio, "Quitar fechas", devuelve cambios, cancelar no devuelve nada |
| P5 | Dashboard: escaneo, columnas por pestaña y edición | `src/gui/budget_dashboard.py`, `tests/test_obra_planning_gui.py` | columnas solo en EJECUTAR/EJECUTANDO/TERMINADO y detrás de "Proyecto"; propuesta en gris; doble clic en fecha abre diálogo y en otra columna abre Excel; "Planificación…" con varias obras |
| P6 | "Mover a…" registra fechas reales | `src/gui/budget_dashboard.py`, `tests/test_obra_planning_gui.py` | mover a EJECUTANDO pone inicio real hoy; a TERMINADO fin real; fallo de movimiento no registra |
| P7 | Configuración → "Avisos de obras…" | `src/gui/main_frame.py` | test offscreen del diálogo de margen |
| P8 | Validación con datos reales y documentación | `docs/README.md`, `docs/decisiones-pendientes.md` | suite completa; escaneo sobre copia de la carpeta y BD reales: nº de propuestas desde nombres de carpeta, ninguna fecha real inventada en el primer escaneo |
