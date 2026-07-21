"""Dependencias compartidas de FastAPI (H4): autenticacion por cookie de sesion."""

from fastapi import HTTPException, Request, status

from src.api.session_store import get_session

SESSION_COOKIE_NAME = "cubiapp_session"


def require_session(request: Request) -> str:
    """Devuelve el email de la sesion activa, o 401 si no hay sesion valida."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    session = get_session(token) if token else None
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado.")
    return session["email"]
