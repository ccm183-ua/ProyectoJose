"""
Tests de contrato para AIModuleClassifier (H1.4): siempre dentro del
vocabulario controlado, nunca una excepcion sin tratar. Sin red, sin claves
reales: se sustituye _call_ai por un doble.
"""

from src.core.ai_module_classifier import AI_MODULE_CONFIDENCE, AIModuleClassifier


class _FakeSettings:
    def __init__(self, has_key=True, raises=False):
        self._has_key = has_key
        self._raises = raises

    def has_active_ai_key(self):
        if self._raises:
            raise RuntimeError("configuracion rota")
        return self._has_key


def _classifier(has_key=True, raises=False):
    return AIModuleClassifier(settings=_FakeSettings(has_key=has_key, raises=raises))


def test_is_available_reflects_settings():
    assert _classifier(has_key=True).is_available() is True
    assert _classifier(has_key=False).is_available() is False


def test_is_available_returns_false_on_settings_error():
    assert _classifier(raises=True).is_available() is False


def test_classify_text_empty_returns_empty_without_calling_ai(monkeypatch):
    clf = _classifier(has_key=True)
    called = []
    monkeypatch.setattr(clf, "_call_ai", lambda *a, **k: called.append(1) or "{}")

    assert clf.classify_text("") == []
    assert called == []


def test_classify_text_without_api_key_returns_empty_without_calling_ai(monkeypatch):
    clf = _classifier(has_key=False)
    called = []
    monkeypatch.setattr(clf, "_call_ai", lambda *a, **k: called.append(1) or "{}")

    assert clf.classify_text("cambiar bajante") == []
    assert called == []


def test_classify_text_filters_unknown_modules_and_dedupes(monkeypatch):
    clf = _classifier(has_key=True)
    monkeypatch.setattr(
        clf, "_call_ai",
        lambda *a, **k: '{"modules": ["fachada", "fachada", "modulo_inventado"]}',
    )

    result = clf.classify_text("revisar fachada")

    assert result == [{"module": "fachada", "confidence": AI_MODULE_CONFIDENCE, "source": "ai"}]


def test_classify_text_tolerates_markdown_fenced_json(monkeypatch):
    clf = _classifier(has_key=True)
    monkeypatch.setattr(
        clf, "_call_ai",
        lambda *a, **k: '```json\n{"modules": ["pintura"]}\n```',
    )

    result = clf.classify_text("pintar fachada")

    assert [r["module"] for r in result] == ["pintura"]


def test_classify_text_invalid_json_returns_empty(monkeypatch):
    clf = _classifier(has_key=True)
    monkeypatch.setattr(clf, "_call_ai", lambda *a, **k: "esto no es json")

    assert clf.classify_text("algo") == []


def test_classify_text_missing_modules_key_returns_empty(monkeypatch):
    clf = _classifier(has_key=True)
    monkeypatch.setattr(clf, "_call_ai", lambda *a, **k: '{"otra_cosa": []}')

    assert clf.classify_text("algo") == []


def test_classify_text_provider_error_is_swallowed_not_raised(monkeypatch):
    clf = _classifier(has_key=True)

    def raise_err(*a, **k):
        raise RuntimeError("proveedor caido")

    monkeypatch.setattr(clf, "_call_ai", raise_err)

    assert clf.classify_text("algo") == []
