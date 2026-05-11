"""Abstraccion segura para dictado por voz."""

from __future__ import annotations


class SpeechToTextUnavailable(RuntimeError):
    pass


class SpeechToTextService:
    """Stub inicial: no anade dependencias pesadas ni activa microfono solo."""

    def is_available(self) -> bool:
        return False

    def transcribe_once(self) -> str:
        raise SpeechToTextUnavailable("Dictado no disponible en esta instalacion.")
