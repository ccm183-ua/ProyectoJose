# Checklist validacion flujo presupuestos

## Preparacion
- [ ] Abrir la app con una base de datos existente.
- [ ] Verificar que inicia sin errores y que el dashboard carga.

## Creacion y finalizacion
- [ ] Crear un presupuesto nuevo con datos completos de proyecto.
- [ ] Finalizar el flujo (con o sin partidas IA).
- [ ] Confirmar en tabla `presupuesto` que existe registro con `es_finalizado = 1` y `fuente_datos = 'finalizado'`.
- [ ] Confirmar que `calidad_datos`, `motivo_incompleto`, `metodo_resolucion_admin` y `metodo_resolucion_comunidad` tienen valor coherente.

## Detalle de partidas
- [ ] Comprobar que el presupuesto finalizado tiene filas en `presupuesto_partida`.
- [ ] Verificar que `num_partidas` coincide con el numero de filas de detalle.
- [ ] Verificar que `total_partidas` coincide con suma de importes.

## Resolucion de comunidad y administracion
- [ ] Caso A: comunidad seleccionada manualmente -> se guarda `comunidad_id`.
- [ ] Caso B: administracion por email de cabecera -> se guarda `administracion_id`.
- [ ] Caso C: sin match -> queda `sin_resolver` y no rompe guardado.

## Ediciones posteriores
- [ ] Regenerar partidas desde dashboard y confirmar que re-finaliza y actualiza detalle.
- [ ] Anadir partidas y confirmar que se actualiza `num_partidas` y totales.
- [ ] Regenerar cabecera y confirmar actualizacion de datos en `presupuesto`.

## Escaneo y no pisado
- [ ] Ejecutar recarga del dashboard para forzar escaneo.
- [ ] Confirmar que presupuestos finalizados mantienen sus datos aunque cambie el mtime.
- [ ] Confirmar que solo se actualiza el estado de carpeta si el proyecto se mueve.

## Compatibilidad y migracion
- [ ] Probar con una base de datos anterior (sin columnas nuevas) y confirmar migracion automatica.
- [ ] Verificar que no se pierden datos antiguos de `presupuesto`.
