import py_compile
from pathlib import Path


def test_recent_gui_and_ai_modules_compile():
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "src/gui/historical_memory_dashboard.py",
        "src/gui/historical_suggestions_dialog.py",
        "src/gui/ai_settings_dialog.py",
        "src/core/ai_clients.py",
        "src/core/settings.py",
        "src/core/historical_context_enhancer.py",
        "src/core/speech_to_text_service.py",
    ):
        py_compile.compile(str(root / relative), doraise=True)
