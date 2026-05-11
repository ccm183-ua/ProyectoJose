import pytest

from src.core.speech_to_text_service import SpeechToTextService, SpeechToTextUnavailable


def test_speech_to_text_stub_is_safe_when_unavailable():
    service = SpeechToTextService()
    assert service.is_available() is False
    with pytest.raises(SpeechToTextUnavailable):
        service.transcribe_once()
