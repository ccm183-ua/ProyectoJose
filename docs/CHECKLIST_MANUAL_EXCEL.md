# Checklist manual — Excel real y diálogos nativos

> La suite automática (`python -m pytest`) mockea toda interacción con Excel vía
> COM y no puede pulsar diálogos nativos de Windows (guardar/abrir fichero).
> Este checklist cubre exactamente lo que queda fuera de esa cobertura.
> Rellena la tabla de "Registro de ejecución" al final cada vez que lo hagas.

## Requisitos para ejecutarlo

- Windows real (no CI), con Microsoft Excel instalado si se va a probar exportación a PDF.
- Una BDD y carpeta de trabajo **aisladas** de datos reales:
  ```
  set CUBIAPP_DB_PATH=C:\ruta\temporal\datos.db
  set CUBIAPP_CONFIG_DIR=C:\ruta\temporal\config
  set CUBIAPP_BACKUP_DIR=C:\ruta\temporal\backups
  run.bat
  ```
- Para probar el flujo con IA sin gastar cuota real, siembra un patrón histórico
  con frecuencia/confianza suficiente para el módulo que vayas a describir (ver
  `HISTORICAL_CONFIDENCE_THRESHOLD`/`HISTORICAL_FREQUENCY_THRESHOLD` en
  `src/core/budget_orchestrator.py`), o configura una API key real de prueba.

## Pasos (H1 / Gate E1)

1. **Crear**: `+ Crear nuevo presupuesto` → pegar o cargar datos del proyecto →
   `Crear Presupuesto` → guardar en la carpeta temporal. Confirmar que el Excel
   se crea desde la plantilla con la cabecera correcta.
2. **Añadir partidas** (flujo unificado): describir la obra en texto libre →
   generar → revisar cobertura mostrada (histórico/mezcla/solo IA/incompleto) →
   confirmar selección. Confirmar que las partidas aparecen en el Excel.
3. **Regenerar**: desde el dashboard, "Regenerar partidas" sobre el mismo
   presupuesto → confirmar el aviso de reemplazo total → confirmar que las
   partidas antiguas desaparecen y solo quedan las nuevas.
4. **Añadir de nuevo** sobre un presupuesto con partidas ya existentes →
   confirmar que una partida idéntica a una ya presente no se duplica, y que
   una parecida con precio distinto aparece marcada como posible duplicado
   (no descartada en silencio).
5. **Cancelar**: iniciar generación y cerrar el diálogo antes de terminar (o
   cancelar la revisión) → confirmar que el Excel y la BDD no cambian (mismo
   hash/tamaño de fichero, mismo recuento de partidas que antes de empezar).
6. **Cerrar sin guardar**: abrir el Excel generado, editarlo a mano y cerrarlo
   sin guardar → confirmar que cubiApp no sobrescribe esa edición por su cuenta
   (el escaneo automático de presupuestos finalizados no relee el Excel).
7. **Finalizar**: marcar el presupuesto como finalizado → confirmar que
   `presupuesto`/`presupuesto_partida` quedan protegidos (`es_finalizado=1`) y
   que un rescaneo normal ya no los sobrescribe.
8. **Exportar a PDF** (requiere Excel real instalado): exportar el presupuesto
   finalizado → confirmar que el PDF se genera con los saltos de página y el
   rango de impresión esperados.

## Registro de ejecución

| Fecha | Ejecutado por | Versión/commit | Resultado | Notas |
|---|---|---|---|---|
| _pendiente_ | | | | |
