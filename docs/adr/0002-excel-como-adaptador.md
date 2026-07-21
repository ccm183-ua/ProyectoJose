# ADR 0002 — Excel como adaptador legado, no como formato canónico

- **Estado**: Aceptada
- **Fecha**: 2026-07-21
- **Contexto del roadmap**: H2.1 (`docs/ROADMAP_ESTABILIZACION_Y_EVOLUCION_IA.md`)
- **Depende de**: ADR 0001

## Contexto

cubiApp usa un fichero `.xlsx` por presupuesto como artefacto de trabajo: el usuario lo
abre, lo edita a mano si hace falta, y lo entrega al cliente. Toda la lógica de negocio
(cabecera, partidas, totales) vive hoy en ese fichero, y SQLite solo cachea una proyección
de lectura rápida (ver ADR 0001). El roadmap plantea migrar a una web con dominio
canónico server-side (H3+), lo que obliga a decidir qué papel juega Excel a partir de ahí.

## Decisión

1. **Durante la migración (H0–H3)**: Excel se declara **artefacto operativo heredado**.
   Sigue siendo la fuente de verdad de un presupuesto activo (no finalizado), tal como
   hoy. No se toca su rol hasta que exista el dominio canónico funcionando en paralelo.
2. **A partir de H3**: Excel pasa a ser **adaptador de importación/exportación**:
   - *Importación*: cada presupuesto existente se importa una vez como versión inicial
     del dominio canónico, registrando advertencias de reconciliación si algo no cuadra
     (importes, partidas huérfanas, etc.). El Excel original no se borra ni se modifica
     en este paso.
   - *Exportación*: el Excel que ve el cliente se genera desde el dominio canónico bajo
     demanda (misma plantilla, mismos estilos y áreas de impresión que hoy garantiza
     `templates/122-20 PLANTILLA PRESUPUESTO.xlsx`), no al revés.
   - Ninguna escritura de negocio nueva debe implementarse escribiendo directamente en
     Excel; toda escritura nueva pasa por el dominio canónico y se refleja en Excel solo
     como exportación derivada.
3. **Código muerto que no se hereda**: `BudgetEditor.add_budget_row` / `modify_budget_row`
   / `delete_budget_row` / `recalculate_totals` (en `excel_budget_editor.py`) no tienen
   ningún llamador activo en la app actual. No se migran ni se usan como base del
   adaptador de exportación futuro — se documentan aquí para que quien migre H3 no los dé
   por buenos solo porque existen.

## Qué pasa si Excel y el dominio canónico discrepan (post-H3)

Mientras el Excel siga siendo editable a mano (por ejemplo, en el periodo de transición o
para clientes que insistan en editar la plantilla directamente):

- El dominio canónico **nunca acepta un Excel editado externamente como fuente automática
  de verdad** — a diferencia del mecanismo actual basado en mtime (ver `CONTEXT.md`,
  sección de reconciliación), que sí permite que una edición externa sobrescriba la caché
  sin revisión humana cuando la ventana de vigilancia de 6 minutos está activa.
- Toda reimportación de un Excel modificado externamente debe pasar por el mismo flujo de
  "importar con advertencias de reconciliación" que la carga inicial, nunca por un
  sobrescritura silenciosa.
- Esto es una regla más estricta que la actual, y es intencional: el hash/mtime frágil de
  hoy es aceptable para una app de escritorio de un único usuario, pero no lo es en cuanto
  el dominio canónico es la fuente de verdad y puede haber ediciones concurrentes
  (aprobaciones, versiones) que un mtime no puede arbitrar.

## Consecuencias

- No hay cambio de código en H2.1. Esta ADR fija la dirección para H3 (`Convertir Excel en
  adapter de importación/exportación`, según la vista general de hitos) y para H9
  (exportación final).
- La decisión de "Exportable" de la tabla de decisiones del propietario (plantilla exacta
  + PDF vs. Excel normalizado + PDF vs. PDF externo) sigue pendiente y debe cerrarse antes
  de H3/H9; esta ADR no la prejuzga, solo fija que sea cual sea el formato, se genera
  *desde* el dominio canónico, no al revés.
