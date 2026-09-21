import pytest

from src.core.speech_to_text_service import SpeechToTextService, SpeechToTextUnavailable


class _FakeMicrophone:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeHttpResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self) -> bytes:
        return self._body


@pytest.fixture
def stub_google_recognition(monkeypatch):
    """Sustituye microfono y red para capturar el timeout del urlopen de recognize_google."""
    sr = pytest.importorskip("speech_recognition")
    from speech_recognition.recognizers import google as sr_google

    captured: dict = {}
    transcript = b'{"result":[{"alternative":[{"transcript":"hola"}],"final":true}]}\n'

    monkeypatch.setattr(sr, "Microphone", _FakeMicrophone)
    monkeypatch.setattr(sr.Recognizer, "adjust_for_ambient_noise", lambda self, source, duration=1: None)
    monkeypatch.setattr(
        sr.Recognizer,
        "listen",
        lambda self, source, timeout=None, phrase_time_limit=None: sr.AudioData(
            b"\x00\x00" * 8000, 16000, 2
        ),
    )

    def fake_urlopen(request, timeout=None):
        captured["timeout"] = timeout
        return _FakeHttpResponse(transcript)

    monkeypatch.setattr(sr_google, "urlopen", fake_urlopen)
    return captured


def test_transcribe_once_pasa_el_recognition_timeout_a_la_red(stub_google_recognition):
    text = SpeechToTextService().transcribe_once(
        timeout=1.0, phrase_time_limit=2.0, recognition_timeout=5.0
    )
    assert text == "hola"
    assert stub_google_recognition["timeout"] == 5.0


def test_transcribe_once_acota_la_red_por_defecto_a_diez_segundos(stub_google_recognition):
    SpeechToTextService().transcribe_once()
    assert stub_google_recognition["timeout"] == 10.0


def test_speech_to_text_transcribe_raises_when_unavailable():
    svc = SpeechToTextService()
    if svc.is_available():
        pytest.skip("Hay microfono y dependencias STT; la prueba manual cubre dictado.")
    with pytest.raises(SpeechToTextUnavailable):
        svc.transcribe_once()
