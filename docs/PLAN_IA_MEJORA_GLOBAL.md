# Plan: Mejora global del sistema de IA para partidas presupuestarias

## 1. Contexto y problema

### 1.1 Estado actual

La IA se usa para **generar partidas presupuestarias** a partir de:
- Tipo de obra (texto libre)
- Descripción adicional (texto libre)
- Plantilla opcional (del catálogo `work_types.json` + personalizadas)

**Flujo**: `AIBudgetDialog` → `BudgetGenerator.generate()` → `PromptBuilder.build_prompt()` → `AIService.generate_partidas()` → Gemini

### 1.2 Problemas percibidos

- **Muy generalista**: El prompt es genérico ("experto presupuestista en España"); la IA no está especializada en el dominio concreto del usuario
- **Poco predecible**: Misma entrada puede dar salidas muy distintas (número de partidas, estructura, precios)
- **Poca fiable**: Formato JSON a veces incorrecto, partidas incoherentes, precios desviados

### 1.3 Archivos clave

| Archivo | Rol |
|---------|-----|
| `prompt_builder.py` | Construye el prompt (system + plantilla + usuario) |
| `ai_service.py` | Llama a Gemini, parsea JSON, fallback entre modelos |
| `budget_generator.py` | Orquesta IA + fallback offline |
| `work_type_catalog.py` | Catálogo de plantillas |
| `custom_templates.py` | Plantillas personalizadas |
| `ai_budget_dialog.py` | UI de generación |
| `data/work_types.json` | Plantillas predefinidas |

---

## 2. Análisis de causas (por qué es impredecible y poco fiable)

### 2.1 Prompt genérico

- System prompt muy amplio
- Poca restricción en formato y estructura
- Sin ejemplos few-shot en el prompt
- Sin validación post-generación

### 2.2 Variabilidad del modelo

- Los LLMs son inherentemente no deterministas (temperatura > 0)
- Sin control de temperatura en la llamada
- Sin esquema estricto (JSON Schema) exigido al modelo

### 2.3 Plantillas poco constrictivas

- Las plantillas dan "contexto" pero la IA puede ignorarlas o mezclarlas
- No hay obligación de seguir la estructura de partidas_base
- Precios de referencia se mencionan pero no se fuerzan

### 2.4 Falta de feedback loop

- No hay forma de "entrenar" o ajustar con correcciones del usuario
- Las partidas rechazadas o editadas no influyen en futuras generaciones

---

## 3. Estrategias de mejora (no mutuamente excluyentes)

### Estrategia A: Hacer el prompt más específico y constrictivo

**Objetivo**: Reducir variabilidad y aumentar adherencia al formato.

| Acción | Descripción |
|--------|-------------|
| Few-shot | Incluir 1-2 ejemplos completos de partidas en el prompt |
| JSON Schema | Exigir estructura exacta en el prompt |
| Temperatura 0 | Usar temperatura 0 en la API para respuestas más deterministas |
| Instrucciones más estrictas | "Genera EXACTAMENTE N partidas", "Los precios deben estar entre X y Y" |
| Plantilla obligatoria | En modo plantilla, exigir "usa SOLO estas partidas como base, adaptando cantidades y precios" |

### Estrategia B: Validación y corrección post-generación

**Objetivo**: Detectar y corregir errores antes de mostrar al usuario.

| Acción | Descripción |
|--------|-------------|
| Validador de esquema | Comprobar que cada partida tiene titulo, descripcion, cantidad, unidad, precio_unitario |
| Validador de precios | Comprobar que precios están en rango razonable (ej. 0.01 - 100000) |
| Validador de unidades | Comprobar que unidad está en lista permitida (m2, ml, ud, kg, etc.) |
| Reintento automático | Si el JSON es inválido, reintentar con prompt "Corrige el JSON" |
| Normalización | Forzar mayúsculas en título, punto final, etc. |

### Estrategia C: Modo "plantilla estricta"

**Objetivo**: Cuando hay plantilla, la IA solo adapta cantidades y precios, no inventa partidas nuevas.

| Acción | Descripción |
|--------|-------------|
| Prompt específico | "Aquí tienes las partidas. Adapta SOLO cantidades y precios al contexto. No añadas ni quites partidas." |
| Estructura fija | La salida tiene exactamente las mismas partidas que la plantilla, con campos adaptados |
| Fallback directo | Si la IA falla, usar partidas_base sin modificar (ya existe) |

### Estrategia D: Especialización por dominio

**Objetivo**: Que la IA "sepa más" del contexto del usuario.

| Acción | Descripción |
|--------|-------------|
| Base de conocimiento | Inyectar en el prompt partidas de presupuestos finalizados del usuario (anonimizadas) |
| Categorías más granulares | Subdividir tipos de obra (reforma cocina vs reforma baño vs bajante) |
| Precios por zona | Si tenemos localidad, mencionar "precios orientativos para [localidad]" |
| Glosario de términos | Inyectar definiciones de conceptos técnicos que el usuario usa |

### Estrategia E: Reducir dependencia de la IA

**Objetivo**: Dar alternativas que no dependan de la IA para flujos críticos.

| Acción | Descripción |
|--------|-------------|
| Plantillas más ricas | Más plantillas predefinidas con partidas completas |
| "Copiar de presupuesto similar" | Buscar en historial un presupuesto del mismo tipo y copiar partidas |
| Editor rápido | Flujo para añadir partidas manualmente de forma ágil |
| Sugerencias incrementales | En vez de generar todo, sugerir "¿añadir partida X?" una a una |

### Estrategia F: Feedback y aprendizaje (a largo plazo)

**Objetivo**: Mejorar con el uso.

| Acción | Descripción |
|--------|-------------|
| Guardar partidas aceptadas | Cuando el usuario acepta partidas, guardarlas como "buen ejemplo" |
| Guardar partidas rechazadas | Para análisis (no para reentrenar, por ahora) |
| Plantilla desde aceptadas | "Guardar estas partidas como plantilla" ya existe; promover su uso |
| Métricas | Registrar tasa de aceptación, ediciones, etc. |

---

## 4. Plan de implementación por fases

### Fase 0: Diagnóstico (sin código)

| # | Tarea | Resultado |
|---|-------|-----------|
| 0.1 | Recopilar 10-20 casos reales de generación (entrada + salida) | Documento con ejemplos |
| 0.2 | Clasificar fallos: formato JSON, precios, estructura, irrelevancia | Lista priorizada |
| 0.3 | Definir "éxito aceptable": ¿qué nivel de edición manual es tolerable? | Criterios |

### Fase 1: Mejoras de bajo riesgo (rápidas)

| # | Tarea | Archivos | Impacto esperado |
|---|-------|----------|------------------|
| 1.1 | Añadir `temperature=0` (o muy baja) en la llamada a Gemini | `ai_service.py` | Menos variabilidad |
| 1.2 | Validador post-generación: esquema + rangos de precio + unidades | Nuevo `partida_validator.py` | Menos errores mostrados |
| 1.3 | Reintento si JSON inválido (1 reintento con "corrige el JSON") | `ai_service.py` | Menos fallos por parseo |
| 1.4 | Normalización de partidas (mayúsculas, punto final, valores por defecto) | `ai_service.py` | Salida más consistente |

### Fase 2: Prompt más constrictivo

| # | Tarea | Archivos | Impacto esperado |
|---|-------|----------|------------------|
| 2.1 | Incluir 1 ejemplo few-shot completo en el system prompt | `prompt_builder.py` | Mejor adherencia al formato |
| 2.2 | JSON Schema explícito en el prompt | `prompt_builder.py` | Menos JSON malformado |
| 2.3 | Instrucciones más estrictas: "Responde ÚNICAMENTE con el JSON, sin texto adicional" | `prompt_builder.py` | Menos texto extra |
| 2.4 | Si hay plantilla: "Adapta SOLO cantidades y precios. Mantén la estructura." | `prompt_builder.py` | Modo plantilla más predecible |

### Fase 3: Modo "plantilla estricta"

| # | Tarea | Archivos | Impacto esperado |
|---|-------|----------|------------------|
| 3.1 | Nuevo modo en AIBudgetDialog: "Usar plantilla tal cual" vs "Generar con IA" | `ai_budget_dialog.py` | Usuario elige nivel de IA |
| 3.2 | Si "plantilla estricta": no llamar a IA, usar partidas_base con cantidades por defecto | `budget_generator.py` | 100% predecible |
| 3.3 | Opción "IA adaptativa": IA solo puede modificar cantidades y precios, no añadir/quitar | `prompt_builder.py` | Equilibrio |

### Fase 4: Especialización (medio plazo)

| # | Tarea | Archivos | Impacto esperado |
|---|-------|----------|------------------|
| 4.1 | Inyectar en prompt partidas de presupuestos finalizados del mismo tipo_obra | `prompt_builder.py`, `db_repository` | IA más contextual |
| 4.2 | Categorías más granulares en work_types.json | `data/work_types.json` | Mejor matching |
| 4.3 | Mencionar localidad en prompt para "precios de la zona" | `prompt_builder.py` | Precios más realistas |

### Fase 5: Alternativas a la IA (reducir dependencia)

| # | Tarea | Archivos | Impacto esperado |
|---|-------|----------|------------------|
| 5.1 | "Copiar partidas de presupuesto existente" en flujo crear | `main_frame.py`, nuevo diálogo | Sin IA para casos repetidos |
| 5.2 | Ampliar catálogo de plantillas predefinidas | `work_types.json` | Más cobertura offline |
| 5.3 | Sugerir plantilla automáticamente según tipo_obra (fuzzy) | `ai_budget_dialog.py` | Menos pasos manuales |

---

## 5. Métricas de éxito (propuestas)

| Métrica | Cómo medir | Objetivo |
|---------|------------|----------|
| Tasa de JSON válido | % de respuestas que parsean correctamente | > 95% |
| Tasa de aceptación | % de veces que el usuario acepta sin editar | A definir |
| Tiempo de edición | Promedio de ediciones por partida aceptada | Reducir |
| Consistencia | Variación en salida para misma entrada (con temp=0) | Mínima |

---

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Prompt más largo = más coste/token | Monitorizar uso; few-shot con 1 ejemplo corto |
| Modo estricto demasiado rígido | Dar opción al usuario de elegir modo |
| Temperatura 0 = respuestas más "planas" | Probar; si no gusta, usar 0.2-0.3 |
| Cambios rompen flujo actual | Tests existentes; validar manualmente cada fase |

---

## 7. Orden recomendado de ejecución

1. **Fase 1** (bajo riesgo, rápido): Validación, temperatura, reintento, normalización
2. **Fase 2** (prompt): Few-shot, JSON Schema, instrucciones estrictas
3. **Fase 3** (modo plantilla): Opción "sin IA" y "IA adaptativa"
4. **Fase 4 y 5** según prioridad del usuario

---

## 8. Dependencias

- `google-genai`: ya en uso
- Posible uso de `jsonschema` para validación (opcional)
- Sin cambios en BD para Fases 1-3 (Fase 4 podría requerir consultas a presupuestos finalizados)
