# Diseño: reconducción del histórico evidenciado

## Objetivo

Hacer que cubiApp solo aplique un precio histórico a un borrador cuando existe evidencia privada comparable, y que el usuario pueda ver esa evidencia por partida. Se conservarán las piezas útiles ya creadas, pero se retirará su capacidad de decidir precios cuando no pasan el comparador.

## Decisión

El patrón agregado deja de ser una fuente de precio. Se mantiene únicamente como índice, estadística y resumen de memoria. La decisión se toma por evidencia individual: una partida histórica aprobada, con ficha estructurada válida y un resultado del comparador `exact` o `comparable`.

```text
Excel con origen y hash
  -> partida bruta inmutable
  -> ficha estructurada derivada
  -> índice de candidatos
  -> comparador obligatorio
  -> evidencia enlazada a la partida propuesta
  -> revisión humana y Excel final
```

## Contratos

- Todo fichero importado calcula SHA-256. El mismo contenido no se incorpora dos veces aunque cambie de ruta.
- Todo origen nuevo (`external_excel`, `own_final_budget`, `ai_draft`, `template`) empieza en `PENDING_REVIEW`; solo `approve_budget_for_learning()` puede pasar a `INCLUDED`.
- Una ficha de precio debe tener como mínimo unidad, acción y elemento. Si cualquiera falta, el comparador nunca devuelve `exact`.
- Una línea `composite`, `auxiliary` o `unknown` no alimenta un patrón ni un precio propuesto.
- `exact` exige igualdad de unidad, acción, elemento, sistema/material cuando estén definidos, dimensiones críticas y condiciones críticas.
- `comparable` requiere unidad, acción y elemento conocidos e iguales; las diferencias se muestran. `related` e `incompatible` nunca rellenan precio.
- Toda partida con precio histórico lleva: nivel, diferencias, IDs de partida/presupuesto fuente, fechas, mínimo, mediana y máximo.
- Si no hay evidencia apta, el resultado lleva `source='ai_completion'` o `source='manual_review'`, nunca `historical`.

## Componentes

1. `HistoricalBudgetAnalyzer` calcula hash, evita duplicados y crea ficha derivada.
2. `historical_partida_features` extrae atributos cerrados y explica cada regla aplicada.
3. `historical_comparator` valida la comparabilidad y construye la evidencia.
4. `HistoricalSuggestionService` recupera candidatos, pero devuelve partidas históricas solo desde evidencia apta.
5. `BudgetOrchestrator` usa exclusivamente esas partidas evidenciadas; la IA cubre huecos.
6. `CombinedPartidasReviewDialog` hace visible la fuente y no permite confundir una estimación IA con un dato histórico.

## Migración segura

No se tocará la base activa durante el desarrollo. Tras los tests, se ejecutará el reconstruidor sobre una copia. El informe separará partidas atómicas aptas, compuestas, sin ficha y pendientes. Aplicar a producción requiere backup SHA-256 válido y aceptación manual del informe.

## Fuera de alcance

No incluye API móvil/web, búsqueda de Internet, catálogo externo ni LLM para clasificar precios. Esas capas no se conectarán hasta que esta evidencia local sea fiable.
