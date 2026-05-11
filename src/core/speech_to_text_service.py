"""Dictado por voz opcional (SpeechRecognition + microfono)."""

from __future__ import annotations

# Texto para tooltips y avisos cuando faltan dependencias o el microfono no esta disponible.
STT_INSTALL_HINT = (
    "Dictado: los paquetes deben estar en el MISMO Python que ejecuta la app.\n\n"
    "Si usa run.bat / .venv, instale asi (desde la carpeta del proyecto):\n\n"
    "  .venv\\Scripts\\pip install SpeechRecognition PyAudio\n\n"
    "Si arranca con otro Python, use ese pip, por ejemplo:\n"
    "  py -3.11 -m pip install SpeechRecognition PyAudio\n\n"
    "En Windows conceda permiso de microfono a Python o a la app en Privacidad > Microfono."
)


def stt_modules_installed() -> bool:
    """True si SpeechRecognition y PyAudio se pueden importar (sin abrir el microfono)."""
    try:
        import speech_recognition  # type: ignore  # noqa: F401
        import pyaudio  # type: ignore  # noqa: F401
    except ImportError:
        return False
    return True


def stt_import_error_message() -> str:
    """Detalle para diagnosticar que modulo falta en este interprete."""
    parts = []
    try:
        import speech_recognition  # type: ignore  # noqa: F401
    except ImportError as e:
        parts.append(f"SpeechRecognition: {e}")
    try:
        import pyaudio  # type: ignore  # noqa: F401
    except ImportError as e:
        parts.append(f"PyAudio: {e}")
    return "; ".join(parts) if parts else ""


class SpeechToTextUnavailable(RuntimeError):
    pass


class SpeechToTextService:
    """
    Transcripcion corta en español. Requiere paquetes opcionales:
    pip install SpeechRecognition pyaudio
    """

    def is_available(self) -> bool:
        # No instanciar Microphone() aqui: en Windows suele fallar o dar falso negativo
        # (permisos, dispositivo ocupado, indices) aunque el dictado funcione al usarlo.
        return stt_modules_installed()

    def transcribe_once(
        self,
        *,
        timeout: float = 8.0,
        phrase_time_limit: float = 45.0,
        language: str = "es-ES",
    ) -> str:
        if not stt_modules_installed():
            detail = stt_import_error_message()
            extra = f"\n\nDetalle: {detail}" if detail else ""
            raise SpeechToTextUnavailable(STT_INSTALL_HINT + extra)
        import speech_recognition as sr  # type: ignore

        r = sr.Recognizer()
        try:
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.4)
                audio = r.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError as exc:
            raise SpeechToTextUnavailable("No se detectó voz a tiempo. Inténtelo de nuevo.") from exc
        except OSError as exc:
            raise SpeechToTextUnavailable(
                "No se pudo abrir el micrófono. Compruebe permisos y que no esté en uso."
            ) from exc

        try:
            text = r.recognize_google(audio, language=language)
        except sr.UnknownValueError as exc:
            raise SpeechToTextUnavailable("No se entendió el audio. Hable más cerca o más claro.") from exc
        except sr.RequestError as exc:
            raise SpeechToTextUnavailable(
                "Error del servicio de reconocimiento (compruebe conexión a Internet)."
            ) from exc

        return (text or "").strip()
