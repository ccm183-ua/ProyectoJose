# Criterios de clasificación de partidas históricas

## Línea base (Fase 0 — 2026-07-22)

Resultado de `scripts/audit_historical_memory.py` sobre `Documents/CubiApp/datos.db`
(solo lectura; hash SHA-256 del fichero verificado idéntico antes/después).
Estos números son la **verdad actual del sistema**, no un objetivo: sirven para
medir el efecto de las fases 1-5 del roadmap, no para justificarlas.

| Métrica | Valor |
| --- | --- |
| Partidas históricas totales | 254 |
| Partidas sin clasificar (0 módulos) | 33 |
| Partidas con más de un módulo | 168 |
| Asignaciones partida-módulo totales | 536 |
| Patrones de precio activos | 424 |
| Patrones con frecuencia ≥ 2 | 82 |
| Patrones con frecuencia ≥ 6 | 3 |
| Presupuestos históricos totales | 117 |
| Presupuestos `NOT_COMPATIBLE` | 54 |
| Presupuestos con `learning_status = INCLUDED` | 54 |
| Partidas con precio ≤ 0 | 26 |
| ...de las cuales en presupuestos `INCLUDED` | 3 |

### Lectura de la línea base

- Solo 3 de los 424 patrones alcanzan frecuencia 6, y corresponden a la misma
  partida duplicada entre varios módulos (168 partidas con más de un módulo
  generan hasta 536 asignaciones para 254 líneas) — no son evidencia
  independiente real.
- 33 partidas sin clasificar quedan fuera de cualquier sugerencia histórica.
- 54 de 117 presupuestos están marcados `NOT_COMPATIBLE` (plantilla no
  reconocida o sin partidas válidas) y no deberían alimentar patrones.
- 3 líneas con precio no positivo están dentro de presupuestos ya marcados
  como `INCLUDED` en la memoria de aprendizaje: candidatas a revisión en la
  Fase 5.

Reproducir en cualquier momento:

```
python scripts/audit_historical_memory.py --db "$env:USERPROFILE\Documents\CubiApp\datos.db"
```

