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
    ) -> str:
        """
        Construye el prompt completo según el camino A o B.

        Args:
            tipo_obra: Tipo de obra escrito por el usuario (texto libre).
            descripcion: Descripción adicional del usuario para dar contexto.
            plantilla: Plantilla seleccionada del catálogo (None = Camino B).
            datos_proyecto: Datos del proyecto (localidad, cliente, calle...).

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
