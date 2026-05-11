import pytest

from src.core.speech_to_text_service import SpeechToTextService, SpeechToTextUnavailable


def test_speech_to_text_transcribe_raises_when_unavailable():
    svc = SpeechToTextService()
    if svc.is_available():
        pytest.skip("Hay microfono y dependencias STT; la prueba manual cubre dictado.")
    with pytest.raises(SpeechToTextUnavailable):
        svc.transcribe_once()
