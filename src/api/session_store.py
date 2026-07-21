"""
Sesiones en memoria del proceso backend (H4).

ponytail: dict + Lock, no tabla SQLite. Alcance solo local, un unico usuario,
un unico proceso uvicorn --workers 1. Perder la sesion al reiniciar el
proceso solo obliga a volver a iniciar sesion, no afecta a los datos.
"""

import secrets
import threading
from datetime import datetime, timedelta
from typing import Dict, Optional

SESSION_TTL = timedelta(hours=8)

_sessions: Dict[str, Dict] = {}
_lock = threading.Lock()


def create_session(email: str) -> str:
    token = secrets.token_urlsafe(32)
    with _lock:
        _sessions[token] = {"email": email, "expires_at": datetime.now() + SESSION_TTL}
    return token


def get_session(token: str) -> Optional[Dict]:
    with _lock:
        session = _sessions.get(token)
        if session is None:
            return None
        if datetime.now() >= session["expires_at"]:
            del _sessions[token]
            return None
        return dict(session)


def delete_session(token: str) -> None:
    with _lock:
        _sessions.pop(token, None)
