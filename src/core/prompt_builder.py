"""
Constructor de prompts para la generación de partidas con IA.

Construye el prompt en capas según dos caminos:
- Camino A (con plantilla): system prompt + contexto_ia + partidas_base + datos usuario
- Camino B (sin plantilla): system prompt extendido + datos usuario
"""

import json
from typing import Dict, List, Optional


# Prompt del sistema: siempre presente en ambos caminos
SYSTEM_PROMPT = (
    "Eres un experto presupuestista de construcción y reformas en España. "
    "Tu trabajo es generar partidas presupuestarias detalladas con precios "
    "orientativos de mercado actuales para obras de construcción.\n\n"
    "Cada partida debe incluir:\n"
    "- titulo: nombre MUY BREVE de la acción (2-5 palabras máximo) EN MAYÚSCULAS "
    "(ej: 'ALICATADO.', 'DESMONTAJE BAJANTE.', 'PINTURA INTERIOR.', 'FONTANERÍA.')\n"
    "- descripcion: explicación detallada de la partida, materiales, "
    "método y alcance del trabajo\n"
    "- cantidad: cantidad estimada (número)\n"
    "- unidad: unidad de medida (m2, ml, ud, kg, etc.)\n"
    "- precio_unitario: precio unitario en euros (número)\n\n"
    "Responde ÚNICAMENTE con un objeto JSON válido con la siguiente estructura:\n"
    '{"partidas": [{"titulo": "ALICATADO.", '
    '"descripcion": "Suministro y colocación de alicatado cerámico en '
    'paredes de cocina, incluyendo material, mortero cola y rejuntado.", '
    '"cantidad": 1, "unidad": "m2", "precio_unitario": 45.00}]}\n\n'
    "IMPORTANTE: El campo 'titulo' debe ser MUY BREVE (2-5 palabras), SIEMPRE "
    "en MAYÚSCULAS y terminar en punto. El campo 'descripcion' es un texto "
    "normal explicativo con el detalle técnico completo.\n\n"
    "No incluyas texto adicional fuera del JSON. "
    "Los precios deben ser orientativos pero realistas para el mercado español actual."
)

# Extensión del system prompt para Camino B (sin plantilla de referencia)
SYSTEM_PROMPT_EXTENDED = (
    "\n\nAl no disponer de una plantilla de referencia, estructura las partidas "
    "de forma lógica siguiendo el orden habitual de ejecución de obra:\n"
    "1. Trabajos previos (protecciones, demoliciones, desmontajes)\n"
    "2. Obra principal (según el tipo de trabajo)\n"
    "3. Instalaciones afectadas\n"
    "4. Acabados y reposiciones\n"
    "5. Limpieza y gestión de residuos\n\n"
    "Incluye todas las partidas que un presupuestista profesional consideraría "
    "para este tipo de obra, sin omitir trabajos auxiliares ni complementarios."
)


class PromptBuilder:
    """Construye prompts para la generación de partidas con IA."""

    def build_prompt(
        self,
        tipo_obra: str,
        descripcion: str,
        plantilla: Optional[Dict] = None,
        datos_proyecto: Optional[Dict] = None,
        historical_context: Optional[Dict] = None,
    ) -> str:
        """
        Construye el prompt completo según el camino A o B.

        Args:
            tipo_obra: Tipo de obra escrito por el usuario (texto libre).
            descripcion: Descripción adicional del usuario para dar contexto.
            plantilla: Plantilla seleccionada del catálogo (None = Camino B).
            datos_proyecto: Datos del proyecto (localidad, cliente, calle...).
            historical_context: Sugerencias históricas opcionales para guiar a la IA.

        Returns:
            String con el prompt completo listo para enviar a la IA.
        """
        parts: List[str] = []

        # 1. System prompt (siempre)
        parts.append(SYSTEM_PROMPT)

        # 2. Contexto de plantilla (solo Camino A) o extensión (Camino B)
        if plantilla is not None:
            parts.append(self._build_template_context(plantilla))
        else:
            parts.append(SYSTEM_PROMPT_EXTENDED)

        # 3. Datos del usuario y del proyecto (siempre)
        parts.append(self._build_user_context(tipo_obra, descripcion, datos_proyecto))

        # 4. Contexto histórico opcional para reducir alucinaciones
        if historical_context:
            parts.append(self._build_historical_context(historical_context))

        return "\n".join(parts)

    def _build_template_context(self, plantilla: Dict) -> str:
        """
        Construye la sección de contexto de la plantilla para Camino A.

        Args:
            plantilla: Plantilla del catálogo con contexto_ia y partidas_base.

        Returns:
            String con el contexto de la plantilla formateado.
        """
        lines = [
            "\n--- PLANTILLA DE REFERENCIA ---",
            f"Tipo de referencia: {plantilla.get('nombre', '')}",
            f"Contexto: {plantilla.get('contexto_ia', '')}",
            "",
            "Partidas de referencia (úsalas como base, pero adáptalas al contexto "
            "específico del usuario; puedes añadir, quitar o modificar partidas):",
        ]

        for partida in plantilla.get('partidas_base', []):
            lines.append(
                f"  - {partida['concepto']} | {partida['unidad']} | "
                f"{partida['precio_ref']}€"
            )

        lines.append("--- FIN PLANTILLA ---")
        return "\n".join(lines)

    def _build_user_context(
        self,
        tipo_obra: str,
        descripcion: str,
        datos_proyecto: Optional[Dict],
    ) -> str:
        """
        Construye la sección con los datos del usuario y del proyecto.

        Args:
            tipo_obra: Tipo de obra indicado por el usuario.
            descripcion: Descripción adicional del usuario.
            datos_proyecto: Datos del proyecto (localidad, cliente, etc.).

        Returns:
            String con el contexto del usuario formateado.
        """
        lines = [
            "\n--- SOLICITUD DEL USUARIO ---",
            f"Tipo de obra: {tipo_obra}",
            f"Descripción: {descripcion}",
        ]

        if datos_proyecto:
            if datos_proyecto.get('localidad'):
                lines.append(f"Ubicación: {datos_proyecto['localidad']}")
            if datos_proyecto.get('cliente'):
                lines.append(f"Cliente: {datos_proyecto['cliente']}")
            if datos_proyecto.get('calle'):
                lines.append(f"Dirección: {datos_proyecto['calle']}")

        lines.append("--- FIN SOLICITUD ---")
        lines.append(
            "\nGenera las partidas presupuestarias en formato JSON para esta obra."
        )

        return "\n".join(lines)

    def _build_historical_context(self, historical_context: Dict) -> str:
        """
        Construye la sección de contexto histórico opcional.
        """
        lines = [
            "\n--- CONTEXTO HISTÓRICO (REAL) ---",
            "Estas son partidas históricas reales usadas por la empresa en obras similares.",
            "Prioriza estas partidas. No inventes partidas nuevas salvo que la descripción "
            "del usuario lo justifique claramente.",
        ]

        modules = historical_context.get("detected_modules", []) or []
        if modules:
            lines.append("Módulos detectados:")
            for module in modules[:8]:
                name = module.get("label") or module.get("name", "")
                confidence = int((module.get("confidence", 0) or 0) * 100)
                lines.append(f"  - {name} (confianza: {confidence}%)")

        partidas = historical_context.get("partidas", []) or []
        if partidas:
            lines.append("Partidas históricas recomendadas:")
            for partida in partidas[:20]:
                concepto = partida.get("concepto") or partida.get("titulo") or ""
                unidad = partida.get("unidad", "ud")
                precio = partida.get("precio_unitario", 0)
                freq = partida.get("historical_frequency", 0)
                lines.append(
                    f"  - {concepto} | {unidad} | {precio}€ | frecuencia histórica: {freq}"
                )

        lines.append("--- FIN CONTEXTO HISTÓRICO ---")
        return "\n".join(lines)

    def build_complementary_prompt(
        self,
        project_data: Optional[Dict],
        confirmed_context: str,
        selected_historical_partidas: List[Dict],
        historical_result: Optional[Dict] = None,
        user_instructions: str = "",
    ) -> str:
        """Construye prompt para completar una selección histórica existente."""
        historical_result = historical_result or {}
        lines: List[str] = [SYSTEM_PROMPT]
        lines.append(
            "\n--- MODO COMPLETAR SELECCIÓN HISTÓRICA ---\n"
            "Ya existen estas partidas seleccionadas por el usuario.\n"
            "No las repitas.\n"
            "No las sustituyas.\n"
            "Sugiere únicamente partidas complementarias que falten para completar el presupuesto.\n"
            "Devuelve solo partidas complementarias.\n"
            "Si no falta nada, devuelve lista vacía.\n"
            "--- FIN MODO ---"
        )

        lines.append("\n--- CONTEXTO CONFIRMADO ---")
        lines.append(confirmed_context or "(sin contexto adicional)")
        lines.append("--- FIN CONTEXTO CONFIRMADO ---")

        if project_data:
            lines.append("\n--- DATOS DEL PROYECTO ---")
            for key in ("tipo", "localidad", "cliente", "calle", "num_calle", "codigo_postal"):
                value = str(project_data.get(key, "")).strip()
                if value:
                    lines.append(f"{key}: {value}")
            lines.append("--- FIN DATOS DEL PROYECTO ---")

        if historical_result:
            modules = historical_result.get("detected_modules", []) or []
            if modules:
                lines.append("\n--- MÓDULOS DETECTADOS ---")
                for module in modules[:12]:
                    name = module.get("label") or module.get("name", "")
                    confidence = int((module.get("confidence", 0) or 0) * 100)
                    lines.append(f"- {name} ({confidence}%)")
                lines.append("--- FIN MÓDULOS DETECTADOS ---")

            patterns = historical_result.get("patterns", []) or []
            if patterns:
                lines.append("\n--- PATRONES HISTÓRICOS USADOS ---")
                for pattern in patterns[:20]:
                    concept = pattern.get("concepto") or pattern.get("title") or ""
                    freq = pattern.get("frequency") or pattern.get("historical_frequency") or 0
                    lines.append(f"- {concept} (freq: {freq})")
                lines.append("--- FIN PATRONES HISTÓRICOS USADOS ---")

        lines.append("\n--- PARTIDAS YA SELECCIONADAS (NO REPETIR) ---")
        for partida in selected_historical_partidas or []:
            concepto = partida.get("concepto") or partida.get("titulo") or ""
            cantidad = partida.get("cantidad", 0)
            unidad = partida.get("unidad", "ud")
            precio = partida.get("precio_unitario", 0)
            lines.append(f"- {concepto} | {cantidad} {unidad} | {precio}€")
        lines.append("--- FIN PARTIDAS YA SELECCIONADAS ---")

        if user_instructions and user_instructions.strip():
            lines.append("\n--- INSTRUCCIONES ADICIONALES DEL USUARIO ---")
            lines.append(user_instructions.strip())
            lines.append("--- FIN INSTRUCCIONES ADICIONALES ---")

        lines.append(
            "\nDevuelve exclusivamente las partidas complementarias en JSON válido con clave 'partidas'."
        )
        return "\n".join(lines)
